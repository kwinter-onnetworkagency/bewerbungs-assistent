import argparse
import contextlib
import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from bewerbung import applemail, mailstand
from bewerbung.core import Workspace, read
from bewerbung.setup import initialize


class MailTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.w = Workspace(initialize(root / "privat", "Beispiel", [], "", "codex", False))
        self.j = self.w.add("Testfirma", "Entwicklung", "https://example.com/123", "Vollständiger Beispieltext.")[0]["id"]
        self.file = root / "original.eml"
        self.raw = (b"From: Hiring <hiring@example.com>\r\nTo: alex@example.com\r\n"
                    b"Date: Tue, 10 Feb 2026 09:11:00 +0100\r\nMessage-ID: <case@example.org>\r\n"
                    b"Subject: Bewerbung Vorgang 123\r\n\r\nWir bestaetigen den Eingang.\r\n")
        self.file.write_bytes(self.raw)
        p = argparse.ArgumentParser()
        s = p.add_subparsers(dest="command")
        mailstand.register(s)
        applemail.register(s)
        self.args = p.parse_args
        self.inbox = ["--konto", "Privat", "--ordner", "Inbox"]
        self.move = self.args(["apple-mail", "ablegen", *self.inbox, "--message-id", "case@example.org",
                               "--zielkonto", "Privat", "--zielordner", "Bewerbung"])

    def capture(self, kind="eingang", *extra):
        return mailstand.capture(self.w, self.args(["mail-erfassen", str(self.file), "--art", kind, "--zone", "UTC",
            "--grund", "Bezug zur Referenz 123 im Original geprüft.", "--ablage", "Inbox", "--konto", "Privat", *extra]))

    def report(self, *flags):
        return mailstand.mailreport(self.w, self.args(["mailbericht", "--zone", "UTC", "--abdeckung",
                                    "Nur bereitgestellte Originale.", *flags])).read_text(encoding="utf-8")

    def test_ambiguous_to_resolved_original_and_history(self):
        self.assertTrue(self.capture("ungeklaert"))
        self.assertIn("ungeklaert", self.report())
        self.w.record(self.j, "absage", self.file, "2026-02-11", "Früher bestätigter Status.")
        self.assertTrue(self.capture("eingang", "--stelle", self.j))
        self.assertFalse(self.capture("eingang", "--stelle", self.j))
        self.assertEqual(self.w.jobs()[0]["status"], "absage")
        report = self.report()
        self.assertIn("10.02.2026 08:11", report)
        self.assertNotIn("Offene Aufgaben und Zuordnungen", report)
        self.assertNotIn("case@example", report)
        self.assertIn("Ausschnitt", self.report())
        self.assertIn("heute nachgetragen: 1", self.report("--tag"))
        self.file.write_bytes(self.raw + b"Different body")
        with self.assertRaisesRegex(ValueError, "abweichendem"):
            self.capture("eingang", "--stelle", self.j)

    def test_older_tracking_can_acquire_original(self):
        self.w.record(self.j, "interview", self.file, "2026-02-10", "Bestätigte Einladung", "case@example.org")
        self.assertTrue(self.capture("interview", "--stelle", self.j))
        events = self.w.jobs()[0]["events"]
        self.assertEqual(len(events), 1)
        self.assertIn("sha256", events[0]["mail"]["original"])
        self.assertFalse(self.capture("interview", "--stelle", self.j))

    def test_unreadable_original_protection_and_retry(self):
        self.file.write_bytes(b"Subject: Test\n\nHallo")
        with self.assertRaisesRegex(ValueError, "Message-ID"):
            self.capture("eingang", "--stelle", self.j)
        self.file.write_bytes(self.raw)
        self.capture("eingang", "--stelle", self.j, "--schuetzen")
        with patch.object(applemail, "call") as api, self.assertRaisesRegex(ValueError, "ungesch"):
            applemail.run(self.move, self.w)
        api.assert_not_called()

    def test_verified_move_and_resume(self):
        self.capture("eingang", "--stelle", self.j)
        # Source already gone after an interruption; re-read the exact destination copy.
        with patch.object(applemail, "call", side_effect=[b"0", self.raw]) as api, contextlib.redirect_stdout(io.StringIO()):
            applemail.run(self.move, self.w)
        self.assertEqual([c.args[0] for c in api.call_args_list], ["anzahl", "quelle"])
        self.assertIn("case@example.org", read(self.w.path("mailablage.json")))
        with patch.object(applemail, "call", return_value=b"Wrong"), self.assertRaisesRegex(ValueError, "weicht"):
            applemail.run(self.move, self.w)

    def test_report_counts_directions_and_current_tasks(self):
        self.w.add_note(self.j, "aufgabe", "Bestaetigung lesen", "offen")
        self.w.add_note(self.j, "aufgabe", "Bestaetigung lesen", "abgeschlossen", done=True)
        from email.utils import format_datetime
        stamp = format_datetime(datetime.now(timezone.utc)).encode("ascii")
        for kind, direction in [("eingang", "arbeitgeber"), ("antwort", "eigen"), ("service", "service")]:
            self.file.write_bytes(self.raw.replace(b"Tue, 10 Feb 2026 09:11:00 +0100", stamp)
                                 .replace(b"case@", kind.encode() + b"@"))
            self.capture(kind, "--stelle", self.j, "--richtung", direction)
        report = self.report("--tag")
        self.assertIn("Arbeitgebereingänge heute: 1. Eigene Nachrichten: 1. Servicenachrichten: 1.", report)
        self.assertNotIn("Bestaetigung lesen", report)

    def test_supplemental_protection_and_proof_rejection(self):
        self.capture("eingang", "--stelle", self.j)
        self.assertTrue(self.capture("eingang", "--stelle", self.j, "--schuetzen", "--schritt", "Lesen"))
        self.assertTrue(self.w.jobs()[0]["events"][0]["mail"]["protected"])
        with self.assertRaisesRegex(ValueError, "anderes dokumentiertes Ergebnis"):
            self.w.record(self.j, "absage", self.file, "2026-02-10", "Widersprüchlich", "case@example.org")
        with patch.object(applemail, "call") as api, self.assertRaisesRegex(ValueError, "ungesch"):
            applemail.run(self.move, self.w)
        api.assert_not_called()
        fake = self.w.path("unterlagen", self.j, "portal", "lauf-test", "vorschau.png")
        fake.parent.mkdir(parents=True)
        fake.write_bytes(b"pre-submission only")
        copied = self.file.parent / "beleg.png"
        copied.write_bytes(fake.read_bytes())
        previous = set(self.w.path("belege").iterdir())
        with self.assertRaisesRegex(ValueError, "kein Versandbeleg"):
            self.w.record(self.j, "beworben", copied, "2026-02-10", "Versuch einer falschen Zuordnung")
        self.assertEqual(set(self.w.path("belege").iterdir()), previous)
