from argparse import ArgumentParser
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
from bewerbung.core import Workspace, read, write
from bewerbung.profilvergleich import register, run
from bewerbung.setup import initialize


class NetzwerkprofilTest(unittest.TestCase):
    def test_selected_translation_and_recommendation_proof(self):
        with TemporaryDirectory() as tmp, redirect_stdout(StringIO()):
            w = Workspace(initialize(Path(tmp) / "privat", "Test", [], "", "codex", False))
            profile = w.profile()
            profile["facts"] = [dict(id="plan", text="Ich plane Projekte.", source="Beleg", translations={"en": "I plan projects."}),
                                dict(id="privat", text="Interner Vermerk", source="Gespräch")]
            write(w.path("profil.json"), profile)
            p = ArgumentParser()
            register(p.add_subparsers(dest="command"))
            public = Path(tmp) / "bestand.txt"
            public.write_text("I plan projects.", encoding="utf8")
            run(p.parse_args(["linkedin","--bestand",str(public),"--fakt","plan","--sprache","en"]), w)
            doc = next(w.path("unterlagen","netzwerkprofil").glob("*.md")).read_text(encoding="utf8")
            self.assertIn("wörtlich vorhanden", doc)
            self.assertNotIn("Interner Vermerk", doc)
            args = ["empfehlung","e-1","--kontakt","Testperson","--stand","angefragt"]
            with self.assertRaisesRegex(ValueError, "Beleg"):
                run(p.parse_args(args), w)
            for _ in range(2):
                run(p.parse_args(args + ["--beleg",str(public)]),w)
            self.assertEqual(len(read(w.path("unterlagen","netzwerkprofil","empfehlungen.json"))),1)
