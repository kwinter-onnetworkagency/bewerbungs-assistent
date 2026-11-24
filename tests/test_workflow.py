import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

from bewerbung.core import Workspace, identity, keyword_match, read, write, validate_profile
from bewerbung.setup import initialize, wizard
from bewerbung.interview import interview, QUESTIONS
from bewerbung.documents import render
from bewerbung.export import chat_bundle, report
from bewerbung.cli import main


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = initialize(self.base / "Arbeitsordner mit Leerzeichen", "Alex Beispiel", ["Projektmanager"], "Remote", "chatgpt")
        self.w = Workspace(self.root)
        self.profile = self.w.profile()
        self.profile["facts"] = [{"id": "projekt", "text": "Ein internes Projekt koordiniert.", "source": "Nutzerangabe", "keywords": ["Projektkoordination"]}]
        write(self.root / "profil.json", self.profile)
        self.job, _ = self.w.add("Beispiel GmbH", "Projektmanager", "https://jobs.lever.co/example/aaa", "Aufgaben: Projektkoordination und Budgetplanung.")
        self.jid = self.job["id"]
        self.proof = self.base / "nachweis.txt"
        self.proof.write_text("Fiktiver Testbeleg: Absage zur Stelle aaa", encoding="utf-8")

    def test_setup_existing_target_survives(self):
        before = (self.root / "profil.json").read_bytes()
        with self.assertRaises(ValueError):
            initialize(self.root, "Andere Person", [], "", "claude")
        self.assertEqual(before, (self.root / "profil.json").read_bytes())

    def test_setup_never_writes_inside_git(self):
        repo = self.base / "public-source"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: dummy")
        with self.assertRaises(ValueError):
            initialize(repo / "persoenlich", "Alex", [], "", "codex")
        self.assertFalse((repo / "persoenlich").exists())

    def test_four_assistant_modes_and_empty_profile(self):
        for assistant, filename in [("claude-code", "CLAUDE.md"), ("codex", "AGENTS.md"), ("claude", None)]:
            p = initialize(self.base / assistant, "Testperson", [], "", assistant)
            self.assertEqual(read(p / "profil.json")["facts"], [])
            self.assertEqual((p / "integration" / "PROJEKTANWEISUNG.txt").is_file(), True)
            if filename:
                self.assertTrue((p / filename).is_file())

    def test_wizard_cancel_has_no_writes(self):
        dest = self.base / "cancelled"
        answers = iter(["Alex", "Analyst", "", "1", str(dest), "n"])
        self.assertIsNone(wizard(lambda _: next(answers), lambda _: None))
        self.assertFalse(dest.exists())

    def test_wizard_runs_personal_interview_after_install(self):
        dest = self.base / "Direkt eingerichtetes Projekt"
        values = {"location": "Teststadt", "work_model": "Zwei Bürotage", "education": "Berufsausbildung 2021"}
        answers = iter(["Alex", "Projektmanager", "Remote", "3", str(dest), "j", "j"] +
                       [values.get(k, "") for k, _, _ in QUESTIONS] + ["j"])
        self.assertEqual(wizard(lambda _: next(answers), lambda _: None), dest.resolve())
        self.assertEqual(read(dest / "profil.json")["preferences"]["work_model"], "Zwei Bürotage")
        self.assertEqual(read(dest / "interview.json")["status"], "vom_nutzer_geprueft_uebernommen")
        self.assertTrue((dest / "CLAUDE.md").exists())

    def test_concurrent_interview_edit_is_not_overwritten(self):
        counter = 0
        def answer(_):
            nonlocal counter
            counter += 1
            if counter == 1:
                return "Erste Ortsangabe"
            state = read(self.root / "interview.json")
            state["answers"]["location"] = "Korrektur im anderen Fenster"
            write(self.root / "interview.json", state)
            return "Kontakt aus altem Fenster"
        with self.assertRaises(ValueError):
            interview(self.w, answer, lambda _: None)
        self.assertEqual(read(self.root / "interview.json")["answers"], {"location": "Korrektur im anderen Fenster"})

    def test_interview_resume_and_confirm(self):
        answers = iter(["Teststadt", "/pause"])
        self.assertFalse(interview(self.w, lambda _: next(answers), lambda _: None))
        self.assertEqual(read(self.root / "interview.json")["answers"], {"location": "Teststadt"})
        values = {"roles": "Product Owner; Projektmanager", "salary": "70000 EUR Gesamtvergütung",
                  "education": "Berufsausbildung abgeschlossen 2021", "skills": "ERP im Fachbereich eingesetzt",
                  "mail": "Persönliches Postfach; nichts automatisch verschieben"}
        answers = iter([values.get(k, "") for k, _, _ in QUESTIONS if k != "location"] + ["j"])
        self.assertTrue(interview(self.w, lambda _: next(answers), lambda _: None))
        p = self.w.profile()
        self.assertEqual(p["target_roles"], ["Product Owner", "Projektmanager"])
        self.assertEqual(p["preferences"]["salary"], values["salary"])
        self.assertIsNone(p["preferences"]["mobility"])
        self.assertEqual(len(p["facts"]), 3)
        self.assertIn("Nutzerangabe", p["facts"][1]["source"])
        self.assertTrue(any(f["id"] == "projekt" for f in p["facts"]))

    def test_interview_rejected_summary_preserves_profile(self):
        before = (self.root / "profil.json").read_bytes()
        answers = iter(["" for _ in QUESTIONS] + ["n"])
        self.assertFalse(interview(self.w, lambda _: next(answers), lambda _: None))
        self.assertEqual(before, (self.root / "profil.json").read_bytes())

    def test_dedup_keeps_manual_score_and_history(self):
        self.w.score(self.jid, 80, "Belegter fachlicher Fit, Budget offen")
        duplicate, created = self.w.add("Beispiel GmbH", "Neuer Titel", "https://jobs.eu.lever.co/example/aaa?utm_source=mail", "Geänderte Beschreibung")
        self.assertFalse(created)
        self.assertEqual(duplicate["score_manual"], 80)
        self.assertEqual(duplicate["description"], self.job["description"])
        _, created = self.w.add("Beispiel GmbH", "Andere Rolle", "https://jobs.lever.co/example/bbb", "Andere Anforderungen")
        self.assertTrue(created)

    def test_greenhouse_personio_and_query_identity(self):
        self.assertEqual(identity("https://boards.greenhouse.io/demo/jobs/123"), identity("https://job-boards.greenhouse.io/demo/jobs/123?gh_src=source"))
        self.assertEqual(identity("https://demo.jobs.personio.de/job/42?language=de"), identity("https://demo.jobs.personio.com/job/42?language=en"))
        self.assertNotEqual(identity("https://jobs.example.com/?jobId=1"), identity("https://jobs.example.com/?jobId=2"))
        self.assertNotEqual(identity("https://boards.greenhouse.io/other/jobs/123"), identity("https://boards.greenhouse.io/demo/jobs/123"))

    def test_status_requires_real_proof_and_preserves_source(self):
        with self.assertRaises(ValueError):
            self.w.record(self.jid, "beworben", None, "2026-01-01", "Noch kein Beleg")
        self.assertEqual(self.w.jobs()[0]["status"], "recherche")
        before = self.proof.read_bytes()
        self.w.record(self.jid, "beworben", self.proof, "2026-01-01", "Bestätigungsseite selbst geprüft", "receipt-1")
        self.assertEqual(before, self.proof.read_bytes())
        self.assertFalse(self.w.record(self.jid, "beworben", self.proof, "2026-01-01", "Doppelt", "receipt-1"))
        self.assertEqual(len(self.w.jobs()[0]["events"]), 1)

    def test_message_cannot_be_assigned_to_second_role(self):
        j, _ = self.w.add("Beispiel", "Andere Rolle", "https://jobs.example.com/2", "Zweite vollständige Anzeige")
        self.w.record(self.jid, "absage", self.proof, "2026-02-01", "Rolle eindeutig", "same-id")
        with self.assertRaises(ValueError):
            self.w.record(j["id"], "absage", self.proof, "2026-02-01", "Firma reicht nicht", "same-id")

    def test_historical_receipt_does_not_erase_rejection(self):
        self.w.record(self.jid, "absage", self.proof, "2026-02-01", "Absage eindeutig", "reject")
        self.w.record(self.jid, "beworben", self.proof, "2026-01-01", "Alter Eingang nachgetragen", "receipt")
        self.w.record(self.jid, "beworben", self.proof, "2026-02-01", "Gleicher Tag, früherer Eingang", "same-day")
        self.assertEqual(self.w.jobs()[0]["status"], "absage")
        self.assertEqual(len(self.w.jobs()[0]["events"]), 3)

    def test_draft_qa_invalidates_when_profile_changes(self):
        self.w.draft(self.jid, "Sehr geehrtes Team,\nmein belegtes Projekt passt zu den Aufgaben.", ["projekt"])
        self.w.qa(self.jid, "Fakten und Anforderungen gegengeprüft", "DOCX in Word geöffnet, A4 und Text geprüft")
        p = self.w.profile()
        p["facts"][0]["text"] = "Korrigierte Nutzerangabe"
        write(self.root / "profil.json", p)
        with self.assertRaises(ValueError):
            self.w.record(self.jid, "vorbereitet", None, "2026-01-01", "Prüfung ist veraltet")
        self.assertEqual(self.w.jobs()[0]["status"], "recherche")

    def test_unknown_fact_and_changed_draft_do_not_keep_qa(self):
        with self.assertRaises(ValueError):
            self.w.draft(self.jid, "Falsche Qualifikation", ["not-present"])
        self.w.draft(self.jid, "Erster Entwurf", ["projekt"])
        self.w.qa(self.jid, "Inhalt geprüft", "Dokument geprüft")
        self.w.record(self.jid, "vorbereitet", None, "2026-01-01", "Prüfung dokumentiert")
        self.w.draft(self.jid, "Geänderter Entwurf", ["projekt"])
        self.assertIsNone(self.w.jobs()[0]["qa"])
        self.assertEqual(self.w.jobs()[0]["status"], "recherche")

    def test_locks_and_invalid_input_preserve_file(self):
        before = (self.root / "bewerbungen.json").read_bytes()
        with self.w.locked():
            with self.assertRaises(ValueError):
                self.w.score(self.jid, 5, "Race")
        for bad in [-1, 101]:
            with self.assertRaises(ValueError):
                self.w.score(self.jid, bad, "Ungültig")
        self.assertEqual(before, (self.root / "bewerbungen.json").read_bytes())
        with self.assertRaises(ValueError):
            self.w.path("..", "outside.json")
        for value in ["file:///private/test", "javascript:alert(1)", "https://name:password@example.com/path"]:
            with self.assertRaises(ValueError):
                identity(value)

    def test_symlink_proof_rejected(self):
        link = self.base / "linked.txt"
        try:
            link.symlink_to(self.proof)
        except OSError:
            self.skipTest("Betriebssystem erlaubt keine Symlinks im Test")
        with self.assertRaises(ValueError):
            self.w.evidence(link)

    def test_profile_and_word_match_have_no_fabricated_fit(self):
        self.assertEqual(keyword_match(self.profile, "Projektkoordination im Team")["matched_fact_ids"], ["projekt"])
        self.assertEqual(keyword_match(self.profile, "Andere Aufgaben")["keyword_score"], 0)
        empty = {**self.profile, "facts": []}
        self.assertIsNone(keyword_match(empty, "Projektkoordination")["keyword_score"])
        malformed = {**self.profile, "facts": [{"id": 3, "text": "Fakt", "source": "Nutzer"}]}
        with self.assertRaises(ValueError):
            validate_profile(malformed)

    def test_documents_are_a4_xml_and_not_overwritten(self):
        out = render(self.w)
        original = out.read_bytes()
        with zipfile.ZipFile(out) as z:
            ET.fromstring(z.read("[Content_Types].xml"))
            ET.fromstring(z.read("_rels/.rels"))
            root = ET.fromstring(z.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            self.assertEqual(root.find(".//w:pgSz", ns).get("{" + ns["w"] + "}w"), "11906")
            self.assertIn("Ein internes Projekt koordiniert.", "".join(root.itertext()))
        second = render(self.w)
        self.assertNotEqual(second, out)
        self.assertEqual(second.stem, "lebenslauf-v2")
        self.assertEqual(out.read_bytes(), original)

    def test_basic_iso_date_cannot_corrupt_chronology(self):
        self.w.record(self.jid, "absage", self.proof, "2026-12-01", "Absage")
        for value in ["20260101", "2026-W01-1", "2026-02-30"]:
            with self.assertRaises(ValueError):
                self.w.record(self.jid, "beworben", self.proof, value, "Alter Eingang")
        self.assertEqual(self.w.jobs()[0]["status"], "absage")

    def test_later_reference_does_not_split_same_url(self):
        first, _ = self.w.add("Example", "Rolle", "https://jobs.example.com/job/123", "Anforderungen an die Rolle")
        second, created = self.w.add("Example", "Rolle", "https://jobs.example.com/job/123", "Neue Ansicht", "123")
        self.assertFalse(created)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["reference"], "123")
        with self.assertRaises(ValueError):
            self.w.add("Example", "Rolle", "https://jobs.example.com/job/123", "Neue Ansicht", "999")

    def test_submission_snapshot_and_draft_history_survive_edits(self):
        self.w.draft(self.jid, "Tatsächlich eingereichte Fassung", ["projekt"])
        self.w.record(self.jid, "beworben", self.proof, "2026-01-01", "Versand selbst bestätigt")
        self.w.draft(self.jid, "Neue noch nicht eingereichte Fassung", ["projekt"])
        item = self.w.jobs()[0]
        self.assertEqual(item["status"], "beworben")
        self.assertEqual(item["events"][0]["submitted_snapshot"]["draft"]["text"], "Tatsächlich eingereichte Fassung")
        self.assertEqual(item["draft_history"][0]["draft"]["text"], "Tatsächlich eingereichte Fassung")

    def test_altered_stored_evidence_is_rejected(self):
        proof = self.w.evidence(self.proof)
        self.w.path(proof["file"]).write_text("Kopie versehentlich verändert")
        with self.assertRaises(ValueError):
            self.w.record(self.jid, "absage", self.proof, "2026-01-01", "Beleg ist verändert")
        self.assertEqual(self.w.jobs()[0]["events"], [])

    def test_export_symlink_cannot_replace_profile(self):
        before = (self.root / "profil.json").read_bytes()
        link = self.root / "exports" / "BERICHT.md"
        try:
            link.symlink_to(self.root / "profil.json")
        except OSError:
            self.skipTest("Betriebssystem erlaubt keine Symlinks im Test")
        with self.assertRaises(ValueError):
            report(self.w)
        self.assertEqual(before, (self.root / "profil.json").read_bytes())

    def test_bundle_only_four_files_and_no_evidence_sources(self):
        self.profile["facts"][0]["source"] = "https://private.example.com/personal-link"
        self.profile["facts"][0]["origin"] = "interview"
        self.profile["preferences"] = {"sources": "private/nachweis.pdf", "salary": "Band noch offen"}
        write(self.root / "profil.json", self.profile)
        (self.root / "unterlagen" / "vertraulich.txt").write_text("DARF-NICHT-EXPORTIERT-WERDEN")
        self.w.record(self.jid, "absage", self.proof, "2026-02-01", "Interner Zuordnungsgrund", "personal-message-id")
        with zipfile.ZipFile(chat_bundle(self.w)) as z:
            self.assertEqual(set(z.namelist()), {"PROFIL.json", "ARBEITSSTAND.json", "PROJEKTANWEISUNG.txt", "INTERVIEW.md"})
            payload = "\n".join(z.read(n).decode() for n in z.namelist())
            for forbidden in ["private.example.com", "DARF-NICHT-EXPORTIERT", "personal-message-id", "Interner Zuordnungsgrund"]:
                self.assertNotIn(forbidden, payload)
            self.assertNotIn("private/nachweis.pdf", payload)
            self.assertIn("nicht unabhängig geprüft", payload)

    def test_csv_formula_is_escaped_and_report_distinguishes_dates(self):
        self.w.add("=SUM(1+1)", "Andere Rolle", "https://jobs.example.com/formula", "Andere vollständige Anzeige")
        self.w.record(self.jid, "absage", self.proof, "2026-02-01", "Belegt", "reject")
        out = report(self.w)
        self.assertIn("2026-02-01 (erfasst", out.read_text(encoding="utf-8"))
        self.assertIn("'=SUM(1+1)", (self.root / "exports" / "bewerbungen.csv").read_text(encoding="utf-8"))

    def test_cli_end_to_end_and_errors(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            main(["--ordner", str(self.root), "pruefen"])
            main(["--ordner", str(self.root), "bericht"])
        self.assertIn("Profil gültig", out.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            main(["--ordner", str(self.root), "ereignis", self.jid, "--status", "beworben", "--datum", "2026-01-01", "--grund", "Ohne Beleg"])
        self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
