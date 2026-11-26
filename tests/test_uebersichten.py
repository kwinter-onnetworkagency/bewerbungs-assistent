from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

from bewerbung import anlagen
from bewerbung.core import Workspace, write
from bewerbung.export import chat_bundle, report
from bewerbung.mailstand import mail_info
from bewerbung.setup import initialize
from test_anlagen import pdf, tools_available


class Links(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.urls = []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.append(dict(attrs)["href"])


class ViewsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.folder = initialize(self.base / "Privat", "Testperson", [], "", "chatgpt")
        self.workspace = Workspace(self.folder)
        self.exports = self.folder / "exports"
        self.job, _ = self.workspace.add('Test <img onerror="x">', "Assistenz", "https://example.org/job", "Originalanzeige als Text.")

    def test_offline_reports_and_untrusted_inputs(self):
        jid = self.job["id"]
        note = self.base / "notiz.txt"
        note.write_text("Fiktive Quelle", encoding="utf-8")
        self.workspace.add_note(jid, "screening", "Erste Sichtung", "</script> Quelle", ["https://example.org/quelle"], evidence=note)
        self.workspace.score(jid, 0, "Musskriterium fehlt.")
        eml = self.base / "eingang.eml"
        eml.write_bytes(b"From: Team <team@example.org>\r\nDate: Wed, 1 Jan 2020 12:00:00 +0000\r\n"
                        b"Subject: Ihre Bewerbung\r\nMessage-ID: <empfang@example.org>\r\n\r\nEingang bestaetigt.")
        mail = mail_info(eml)
        self.workspace.record(jid, "eingang", eml, "2020-01-01", "Eingangsbestätigung",
                              mail["message_id"], mail=mail)
        report(self.workspace)
        for path in self.exports.glob("*.html"):
            for href in Links(path).urls:
                if not urlsplit(href).scheme and not href.startswith("#"):
                    self.assertTrue((path.parent / unquote(href)).is_file(), (path.name, href))
        detail_path = self.exports / ("Stelle-" + jid + ".html")
        jobs = self.workspace.jobs()
        jobs[0]["events"][0]["mail"]["original"] = jobs[0]["events"][0]["evidence"]
        jobs[0]["events"][0]["evidence"] = self.workspace.evidence(note)
        write(self.workspace.path("bewerbungen.json"), jobs)
        report(self.workspace)
        detail = detail_path.read_text(encoding="utf-8")
        self.assertIn("Nachgetragenes Mailoriginal öffnen", detail)
        self.assertIn("Eingangsbestätigungen", detail)
        self.assertIn("Ihre Bewerbung", detail)
        self.assertIn("Originalanzeige als Text.", detail)
        self.assertNotIn('<img onerror', detail)
        self.assertIn("Score: 0", (self.exports / "Screening.html").read_text(encoding="utf-8"))
        self.assertIn("0 von 1 Stellen", (self.exports / "Kohorten.html").read_text(encoding="utf-8"))
        evidence = self.workspace.jobs()[0]["events"][0]["mail"]["original"]["file"]
        original = self.workspace.path(evidence)
        self.assertIn("../" + Path(evidence).as_posix(), Links(detail_path).urls)
        original.write_bytes(b"changed")
        report(self.workspace)
        self.assertNotIn("../" + Path(evidence).as_posix(), Links(detail_path).urls)
        jobs = self.workspace.jobs()
        jobs[0]["notes"][0]["evidence"]["file"] = "../../secret.txt"
        jobs[0]["notes"][0]["sources"] = ["javascript:alert(1)"]
        write(self.workspace.path("bewerbungen.json"), jobs)
        report(self.workspace)
        self.assertFalse(any("secret.txt" in href or "javascript:" in href for href in Links(detail_path).urls))
        profile = self.workspace.profile()
        profile.setdefault("preferences", {}).update(contact="Person@example.org", salary="56000 EUR", mail="Bewerbungskonto")
        write(self.workspace.path("profil.json"), profile)
        with ZipFile(chat_bundle(self.workspace, contact=True)) as bundle:
            exported = json.loads(bundle.read("PROFIL.json"))["preferences"]
            self.assertEqual(exported["contact"], "Person@example.org")
            self.assertNotIn("salary", exported)
        with ZipFile(chat_bundle(self.workspace, salary=True)) as bundle:
            exported = json.loads(bundle.read("PROFIL.json"))["preferences"]
            self.assertEqual(exported["salary"], "56000 EUR")
            self.assertNotIn("contact", exported)
        with ZipFile(chat_bundle(self.workspace)) as bundle:
            exported = json.loads(bundle.read("PROFIL.json"))["preferences"]
            self.assertFalse({"contact", "mail", "salary"} & exported.keys())
            self.assertEqual(len(bundle.namelist()), 4)
            self.assertFalse(any(b"Ihre Bewerbung" in bundle.read(f) for f in bundle.namelist()))
            self.assertFalse(any(b"secret.txt" in bundle.read(f) for f in bundle.namelist()))

    def test_unknown_groups_and_multiple_receipts_count_one_job(self):
        other, _ = self.workspace.add("Zwei", "Rolle", "https://example.org/zwei", "Zweite Anzeige")
        for jid in (self.job["id"], other["id"]):
            evidence = self.base / (jid + ".txt")
            evidence.write_text("Versand " + jid, encoding="utf-8")
            self.workspace.record(jid, "beworben", evidence, "2020-02-01", "Bestätigter Versand")
            self.workspace.record(jid, "beworben", evidence, "2020-02-02", "Nachtrag")
        self.workspace.record(other["id"], "interview", evidence, "2020-02-03", "Einladung zur Stelle")
        report(self.workspace)
        content = (self.exports / "Kohorten.html").read_text(encoding="utf-8")
        self.assertIn("2 von 2 Stellen", content)
        self.assertIn("unbekannt / unbekannt / unbekannt", content)
        self.assertIn("interview: 1", content)
        self.assertIn("beworben: 1", content)

    @unittest.skipUnless(tools_available("pdfinfo", "pdftotext"), "Lokale Poppler-Werkzeuge erforderlich")
    def test_verified_original_package_and_submitted_cohort(self):
        jid = self.job["id"]
        source = pdf(self.base / "Anlage.pdf", [("Kontrolle", 595, 842)])
        anlagen.add_source(self.workspace, "kurs", "Kursoriginal", source)
        plan = dict(pflicht=["kurs"], optional=["probe"], weglassen={"probe": "Nur der Kurs ist angefordert."},
                    dateien=[dict(name="Kurs.pdf", anlagen=["kurs"])])
        packet = anlagen.build_package(self.workspace, jid, plan)
        receipt = self.base / "quittung.txt"
        receipt.write_text("Einreichung bestätigt", encoding="utf-8")
        self.workspace.record(jid, "beworben", receipt, date.today().isoformat(), "Bestätigung erfasst")
        anlagen.associate(self.workspace, jid, packet.name, 1, "Anhänge gegen den Beleg geprüft",
                          vorlage="Kompakt", vorlagenversion="2", kanal="Portal")
        report(self.workspace)
        packets = self.exports / "Pakete.html"
        hrefs = Links(packets).urls
        for path in (packet / "Kurs.pdf", packet / "manifest.json",
                     self.workspace.path("anlagen", "inventar", "id-kurs", "original.pdf")):
            self.assertIn("../" + path.relative_to(self.folder).as_posix(), hrefs)
        self.assertIn("Nur der Kurs ist angefordert.", packets.read_text(encoding="utf-8"))
        contents = (self.exports / "Kohorten.html").read_text(encoding="utf-8")
        self.assertIn("Kompakt / 2 / Portal", contents)
        (packet / "Kurs.pdf").write_bytes(b"kaputt")
        report(self.workspace)
        self.assertNotIn("../" + (packet / "Kurs.pdf").relative_to(self.folder).as_posix(), Links(packets).urls)
        self.assertNotIn("Kompakt / 2 / Portal", (self.exports / "Kohorten.html").read_text(encoding="utf-8"))
