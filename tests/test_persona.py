import argparse
from contextlib import redirect_stdout
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from bewerbung import persona
from bewerbung.core import Workspace, read, write
from bewerbung.setup import initialize


class QuietServer(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class PersonaTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.w = Workspace(initialize(Path(tmp.name) / "privat", "Profilbeispiel", [], "", "chatgpt"))
        profile = self.w.profile()
        profile["facts"] = [
            dict(id="test", text="Gezeigte <Praxis>", translations={"en": "Inventory practice"}, source="Interner Beleg"),
            dict(id="nicht-gewaehlt", text="Interne Reserve", source="Privater Nachweis")]
        write(self.w.path("profil.json"), profile)
        self.jid = self.w.add("Testbetrieb", "Disposition", "https://example.org/stelle", "Aufgaben")[0]["id"]
        self.parser = argparse.ArgumentParser()
        persona.register(self.parser.add_subparsers(dest="command"))

    def command(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(persona.run(self.parser.parse_args(args), self.w))
        return output.getvalue()

    def serve(self):
        handler = partial(QuietServer, directory=self.w.path("portfolio", "public"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:" + str(server.server_port)

    def generate(self, base, *args):
        self.command("persona", self.jid, "--basis-url", base, "--anrede", "Für das Testteam",
                     "--fakt", "test", "--link", "Arbeitsprobe", "https://example.org/probe", *args)
        folder = self.w.path("unterlagen", self.jid, "portfolio")
        version = read(folder / "aktuell.json")["version"]
        return read(folder / (version + ".json"))

    def test_public_selection_and_wizard_edits_are_preserved(self):
        page = self.w.path("portfolio", "public", "index.html")
        content = self.command("portfolio", "--fakt", "test", "--link", "Beispiel", "https://example.org/probe")
        self.assertIn("lokal vorbereitet", content)
        body = page.read_text()
        self.assertIn("Gezeigte &lt;Praxis&gt;", body)
        self.assertIn("https://example.org/probe", body)
        self.assertNotIn("Interne Reserve", body)
        self.assertNotIn("Interner Beleg", body)
        self.command("portfolio", "--fakt", "test", "--titel", "Überarbeitet")
        self.assertIn("Überarbeitet", page.read_text())
        page.write_text("<p>Selbst geschrieben</p>")
        self.assertIn("eigene Änderungen", self.command("portfolio", "--fakt", "test"))
        self.assertEqual(page.read_text(), "<p>Selbst geschrieben</p>")
        drafts = self.w.path("portfolio", "entwuerfe")
        latest = next(f for f in drafts.glob("*.html") if "Beispiel" not in f.read_text() and "Überarbeitet" not in f.read_text())
        latest.write_text("Eigene Entwurfsnotiz")
        with self.assertRaisesRegex(ValueError, "Entwurf wurde bearbeitet|Portfolioentwurf wurde bearbeitet"):
            self.command("portfolio", "--fakt", "test")
        self.assertEqual(latest.read_text(), "Eigene Entwurfsnotiz")
        with self.assertRaises(ValueError):
            self.command("portfolio", "--fakt", "test", "--link", "Beispiel", "javascript:void(0)")

    def test_optional_public_site_and_live_stale_page(self):
        other = self.w.root.parent / "ohne-portfolio"
        empty = Workspace(initialize(other, "Beispiel", [], "", "chatgpt", portfolio=False))
        self.assertFalse(empty.path("portfolio", "public", "index.html").exists())
        base = self.serve()
        self.command("portfolio", "--fakt", "test")
        self.assertIn("HTTP 200", self.command("portfolio-pruefen", "--url", base + "/"))
        self.w.path("portfolio", "public", "veraltet.html").write_text("alte Fassung")
        with self.assertRaisesRegex(ValueError, "weicht"):
            self.command("portfolio-pruefen", "--url", base + "/veraltet.html")

    @unittest.skipUnless(shutil.which("node"), "Node.js für die Empfänger-Verschlüsselung erforderlich")
    def test_independent_keys_and_current_version(self):
        base = self.serve()
        old = self.generate(base)
        new = self.generate(base)
        self.assertNotEqual(old["key"], new["key"])
        self.assertNotEqual(old["url"], new["url"])
        listing = self.command("persona-liste", "--id", self.jid)
        self.assertIn(old["version"], listing)
        self.assertIn(new["version"], listing)
        self.assertNotIn(old["key"], listing)
        public = self.w.path("portfolio", "public", "p", new["version"], "index.html")
        page = public.read_text()
        for value in (new["key"], "Für das Testteam", "Gezeigte <Praxis>", "https://example.org/probe", "Interne Reserve"):
            self.assertNotIn(value, page)
        self.assertIn("HTTP 200", self.command("persona-pruefen", self.jid))
        public.write_text("Veränderte lokale Fassung")
        with self.assertRaisesRegex(ValueError, "Lokale Empfängerfassung"):
            self.command("persona-pruefen", self.jid)
        self.assertIn("HTTP 200", self.command("persona-pruefen", self.jid, "--version", old["version"]))

    def test_only_designated_cv_files_and_explicit_translation(self):
        with patch("bewerbung.anlagen.checked_cv_files", return_value={}) as checked:
            with self.assertRaisesRegex(ValueError, "CV fehlt"):
                self.generate("https://example.org", "--fassung", "v-test", "--cv", "Zeugnis.pdf")
            checked.assert_called_once_with(self.w, self.jid, "v-test")
        with self.assertRaisesRegex(ValueError, "Übersetzung"):
            self.command("portfolio", "--sprache", "en", "--fakt", "nicht-gewaehlt")

    @unittest.skipUnless(os.getenv("PERSONA_BROWSER_TEST") == "1", "Echter Browser mit PERSONA_BROWSER_TEST=1")
    def test_chromium_unlocks_correct_version_only_and_shows_public_selection(self):
        base = self.serve()
        self.command("portfolio", "--fakt", "test", "--link", "Arbeitsprobe", "https://example.org/probe")
        first = self.generate(base)
        from test_anlagen import pdf
        from bewerbung.anlagen import add_source, build_package
        cv = pdf(self.w.root.parent / "CV.pdf", [("Test", 595, 842)], subject=self.jid)
        add_source(self.w, "cv", "Lebenslauf", cv)
        version = build_package(self.w, self.jid, {"pflicht": ["cv"], "dateien": [{"name": "CV.pdf", "anlagen": ["cv"]}]})
        second = self.generate(base, "--sprache", "en", "--titel", "For the team", "--fassung", version.name, "--cv", "CV.pdf")
        probe = r"""
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PORTAL_CHROMIUM_EXECUTABLE});
 try{
  const page=await browser.newPage();
  await page.goto(input.base);
  assert.ok((await page.locator('main').innerText()).includes('Gezeigte <Praxis>'));
  await page.goto(input.current.url);
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  await page.locator('#key').fill(input.wrong);
  await page.locator('button').click();
  await page.getByText('Could not open portfolio.', {exact:false}).waitFor();
  assert.equal(await page.locator('#profile').isVisible(),false);
  await page.locator('#key').fill(input.current.key);
  await page.locator('button').click();
  await page.locator('#profile').waitFor();
  const body=await page.locator('#profile').innerText();
  assert.ok(body.includes('Inventory practice'));
  assert.ok(body.includes('For the team'));
  assert.ok(!body.includes('Interne Reserve'));
  assert.equal(await page.getByRole('link',{name:'Arbeitsprobe'}).getAttribute('href'),'https://example.org/probe');
  const downloaded = await page.getByRole('link',{name:'CV.pdf'}).evaluate(async link=>{
    const raw=await (await fetch(link.href)).arrayBuffer();
    const hash=await crypto.subtle.digest('SHA-256',raw);
    return Array.from(new Uint8Array(hash),n=>n.toString(16).padStart(2,'0')).join('');
  });
  assert.equal(downloaded,input.pdfhash);
  process.stdout.write('BROWSER VERIFIED');
 }finally{await browser.close();}
})().catch(()=>{process.stderr.write('Browserprüfung fehlgeschlagen');process.exitCode=1;});
"""
        proc = subprocess.run(["node", "-e", probe], input=json.dumps({"base": base, "current": second, "wrong": first["key"],
                                                                      "pdfhash": hashlib.sha256(cv.read_bytes()).hexdigest()}),
                              capture_output=True, text=True, timeout=50)
        self.assertEqual((proc.returncode, proc.stdout), (0, "BROWSER VERIFIED"), msg=proc.stderr)
