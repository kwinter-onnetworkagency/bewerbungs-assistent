import argparse
import contextlib
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bewerbung import anlagen
from bewerbung.core import Workspace, read, write
from bewerbung.setup import initialize


def pdf(path, pages, subject=None):
    """Kleine echte PDF mit Schrifteinträgen, Seitenbaum und Cross-Reference-Tabelle."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    references = []
    for label, width, height in pages:
        page_id = len(objects) + 1
        references.append(f"{page_id} 0 R")
        page = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id+1} 0 R >>")
        content = f"BT /F1 12 Tf 40 40 Td ({label}) Tj ET".encode()
        objects.extend([page.encode(), f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"])
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(references)}] >>".encode()
    trailer = ""
    if subject:
        objects.append(f"<< /Subject ({subject}) >>".encode())
        trailer = f" /Info {len(objects)} 0 R"
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R{trailer} >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(data)
    return path


def plan():
    return dict(pflicht=["cv"], optional=["kurs", "probe"], weglassen={"probe": "Für diese Stelle nicht angefordert."},
                dateien=[dict(name="Bewerbung.pdf", anlagen=["cv", "kurs"])], max_dateien=1)


def tools_available(*names):
    return all(shutil.which(name) for name in names)


class PackageTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.workspace = Workspace(initialize(self.base / "Privat", "Testperson", [], "", "chatgpt"))
        self.jid = self.workspace.add("Beispiel", "Rolle", "https://example.org/rolle", "Fiktive Aufgabe")[0]["id"]
        self.cv = pdf(self.base / "A.pdf", [("Vita", 595, 842)], self.jid)
        self.certificate = pdf(self.base / "B.pdf", [("Kurs1", 842, 595), ("Kurs2", 595, 842)])
        self.plan = self.base / "plan.json"
        parser = argparse.ArgumentParser()
        anlagen.register(parser.add_subparsers(dest="command"))
        self.parser = parser

    def command(self, *args):
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            anlagen.run(self.parser.parse_args(args), self.workspace)
        return log.getvalue().strip()

    def add_docs(self):
        self.command("anlage", "cv", "--titel", "Lebenslauf", "--datei", str(self.cv))
        self.command("anlage", "kurs", "--titel", "Kursnachweis", "--datei", str(self.certificate))

    def build(self, spec):
        write(self.plan, spec)
        return Path(self.command("anlagenpaket", self.jid, "--plan", str(self.plan)))

    @unittest.skipUnless(tools_available("pdfinfo", "pdftotext"), "Lokale Poppler-Werkzeuge erforderlich")
    def test_mail_timestamp_resolves_submission_across_calendar_days(self):
        self.add_docs()
        spec = {"pflicht": ["cv"], "dateien": [{"name": "Vita.pdf", "anlagen": ["cv"]}]}
        # Die Uhrzeiten liegen fünf Minuten auseinander, die Datumsangaben in UTC und New York auf zwei Tagen.
        with patch("bewerbung.anlagen.now", return_value="2022-06-01T00:05:00+00:00"):
            checked = self.build(spec)
        eml = self.base / "quittung.eml"
        eml.write_bytes(b"Date: Tue, 31 May 2022 20:10:00 -0400\r\nMessage-ID: <probe@example.org>\r\n\r\nBestaetigung")
        from bewerbung.mailstand import mail_info
        mail = mail_info(eml)
        self.workspace.record(self.jid, "beworben", eml, "2022-05-31", "Versand bestätigt", mail["message_id"], mail=mail)
        anlagen.associate(self.workspace, self.jid, checked.name, 1, "Anlagen geprüft")
        self.assertEqual(self.workspace.jobs()[0]["events"][0]["eingereichtes_paket"]["fassung"], checked.name)
        jobs = self.workspace.jobs()
        jobs[0]["events"][0]["mail"]["mail_at"] = "2022-05-31T20:01:00-04:00"
        write(self.workspace.path("bewerbungen.json"), jobs)
        with self.assertRaisesRegex(ValueError, "nach der belegten"):
            anlagen.associate(self.workspace, self.jid, checked.name, 1, "Vorzeitige Mail")

    def test_validation_limits_assignments_and_paths(self):
        self.assertEqual(self.command("anlagen"), "[]")
        for key, value in [
            ("weglassen", {"cv": "Kein Platz"}), ("weglassen", {"probe": ""}),
            ("weglassen", {}), ("optional", ["../../x"]), ("pflicht", ["cv", "cv"]),
            ("max_dateien", False), ("max_dateien", 0), ("max_datei", 2),
            ("dateien", [{"name": "Kurs.pdf", "anlagen": ["kurs"]}]),
            ("dateien", [{"name": "../a.pdf", "anlagen": ["cv", "kurs"]}]),
            ("dateien", [{"name": "CON.pdf", "anlagen": ["cv", "kurs"]}]),
            ("dateien", [{"name": "A.pdf", "anlagen": ["cv"]}, {"name": "a.pdf", "anlagen": ["kurs"]}]),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                spec = {**plan(), "max_dateien": 2, key: value}
                self.build(spec)
        with self.assertRaises(ValueError):
            anlagen.checked_upload_files(self.workspace, self.jid, "../outside")

    def test_missing_pdf_tool_is_actionable_and_leaves_no_inventory_item(self):
        with patch("bewerbung.anlagen.shutil.which", return_value=None), self.assertRaisesRegex(ValueError, "pdfinfo"):
            self.command("anlage", "cv", "--titel", "CV", "--datei", str(self.cv))
        self.assertEqual(list(self.workspace.path("anlagen", "inventar").iterdir()), [])

    @unittest.skipUnless(tools_available("pdfinfo", "pdftotext", "pdfunite"), "Lokale Poppler-Werkzeuge erforderlich")
    def test_real_versions_separate_merged_order_receipt_and_integrity(self):
        self.add_docs()
        self.add_docs()  # Identische Registrierung ist sicher wiederholbar.
        with self.assertRaisesRegex(ValueError, "neue ID"):
            self.command("anlage", "kurs", "--titel", "Kursnachweis", "--datei", str(self.cv))
        spec = plan()
        merged = self.build(spec)
        self.assertIn("Bewerbung.pdf", self.command("paketpruefung", self.jid, merged.name))
        self.assertEqual(self.build(spec), merged)
        self.assertIn(merged.name, self.command("paketliste", self.jid))
        result = read(merged / "manifest.json")
        self.assertEqual(result["arbeitgeber"]["url"], "https://example.org/rolle")
        table = result["dateien"][0]["inhalt"]
        self.assertEqual([(r["id"], r["von"], r["bis"]) for r in table], [("cv", 1, 1), ("kurs", 2, 3)])
        self.assertEqual(table[0]["sha256"], hashlib.sha256(self.cv.read_bytes()).hexdigest())
        self.assertEqual(result["plan"]["weglassen"], spec["weglassen"])
        texts = subprocess.check_output(["pdftotext", merged / "Bewerbung.pdf", "-"]).decode()
        self.assertEqual(texts.split(), ["Vita", "Kurs1", "Kurs2"])
        split_spec = {**spec, "max_dateien": 2, "dateien": [
            {"name": "Vita.pdf", "anlagen": ["cv"]}, {"name": "Nachweis.pdf", "anlagen": ["kurs"]}]}
        separate = self.build(split_spec)
        files = anlagen.checked_upload_files(self.workspace, self.jid, separate.name)
        self.assertEqual(list(files), ["Vita.pdf", "Nachweis.pdf"])
        self.assertEqual(list(anlagen.checked_cv_files(self.workspace, self.jid, separate.name)), ["Vita.pdf"])
        self.assertEqual(anlagen.checked_cv_files(self.workspace, self.jid, merged.name), {})
        self.assertEqual(files["Vita.pdf"].read_bytes(), self.cv.read_bytes())
        self.assertEqual(files["Nachweis.pdf"].read_bytes(), self.certificate.read_bytes())
        self.assertEqual(self.build(split_spec), separate)
        other = self.workspace.add("B", "R", "https://example.org/b", "Aufgabe")[0]["id"]
        with self.assertRaises((OSError, ValueError)):
            anlagen.checked_upload_files(self.workspace, other, separate.name)
        self.assertEqual(self.workspace.jobs()[0]["events"], [])
        with self.assertRaisesRegex(ValueError, "Ereignisnummer"):
            anlagen.associate(self.workspace, self.jid, separate.name, 1, "Test")
        receipt = self.base / "best.txt"
        receipt.write_text("Eingang bestätigt", encoding="utf-8")
        self.workspace.record(self.jid, "beworben", receipt, date.today().isoformat(), "Bestätigung zur Stelle")
        self.command("paketzuordnung", self.jid, separate.name, "--ereignis", "1", "--grund", "Dateinamen abgeglichen.",
                     "--vorlage", "Kurzprofil", "--vorlagenversion", "1", "--kanal", "Portal")
        event = self.workspace.jobs()[0]["events"][0]
        self.assertEqual(event["eingereichtes_paket"]["fassung"], separate.name)
        self.assertEqual(event["eingereichtes_paket"]["kanal"], "Portal")
        self.assertEqual(event["eingereichtes_paket"]["zuordnung"], "nutzerzuordnung")
        message = EmailMessage()
        message["Subject"] = "Einreichung"
        message["Date"] = format_datetime(datetime.now(timezone.utc))
        message["Message-ID"] = "<eigene-kopie@example.org>"
        message.set_content("Übermittlung mit den Anlagen.")
        for name, path in files.items():
            message.add_attachment(path.read_bytes(), maintype="application", subtype="pdf", filename="Kopie-" + name)
        original = self.base / "original.eml"
        original.write_bytes(message.as_bytes())
        # Other attachments are a contradiction even if the claimed submission date matches.
        extra_message = EmailMessage()
        extra_message.set_content("Bestätigung")
        extra_message.add_attachment(b"%PDF-fremd", maintype="application", subtype="pdf", filename="anderer-cv.pdf")
        different = self.base / "andere.eml"
        different.write_bytes(extra_message.as_bytes())
        jobs = self.workspace.jobs()
        jobs[0]["events"][0]["mail"] = {"original": self.workspace.evidence(different)}
        write(self.workspace.path("bewerbungen.json"), jobs)
        with self.assertRaisesRegex(ValueError, "weichen vom Paket ab"):
            anlagen.associate(self.workspace, self.jid, separate.name, 1, "Nicht dasselbe Paket")

        jobs = self.workspace.jobs()
        forwarded = EmailMessage()
        forwarded.set_content("Weiterleitung")
        forwarded.add_attachment(extra_message)
        different.write_bytes(forwarded.as_bytes())
        jobs[0]["events"][0]["mail"] = {"original": self.workspace.evidence(different)}
        write(self.workspace.path("bewerbungen.json"), jobs)
        with self.assertRaisesRegex(ValueError, "Weitergeleitete"):
            anlagen.associate(self.workspace, self.jid, separate.name, 1, "Weitergeleiteter Thread")
        jobs[0]["events"][0]["mail"] = {"original": self.workspace.evidence(original)}
        write(self.workspace.path("bewerbungen.json"), jobs)
        anlagen.associate(self.workspace, self.jid, separate.name, 1, "Anhänge später erhalten")
        self.assertEqual(self.workspace.jobs()[0]["events"][0]["eingereichtes_paket"]["zuordnung"], "anhang_hash")
        with self.assertRaisesRegex(ValueError, "andere Fassung"):
            anlagen.associate(self.workspace, self.jid, merged.name, 1, "Andere PDF")
        self.workspace.path(event["evidence"]["file"]).write_bytes(b"geaendert")
        with self.assertRaisesRegex(ValueError, "Einreichungsbeleg"):
            anlagen.associate(self.workspace, self.jid, separate.name, 1, "Kontrolle")
        files["Vita.pdf"].write_bytes(self.certificate.read_bytes())
        with self.assertRaisesRegex(ValueError, "verändert"):
            anlagen.checked_upload_files(self.workspace, self.jid, separate.name)
        self.assertEqual(list(anlagen.checked_upload_files(self.workspace, self.jid, merged.name)), ["Bewerbung.pdf"])
        (merged / "extra.txt").touch()
        with self.assertRaisesRegex(ValueError, "unerwartete"):
            anlagen.checked_upload_files(self.workspace, self.jid, merged.name)
        (merged / "manifest.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Manifest"):
            anlagen.checked_upload_files(self.workspace, self.jid, merged.name)

    @unittest.skipUnless(tools_available("pdfinfo", "pdftotext"), "Lokale Poppler-Werkzeuge erforderlich")
    def test_standard_sources_must_be_included_or_explicitly_omitted(self):
        self.add_docs()
        self.command("anlagenstandard", "--anlage", "kurs")
        spec = {"pflicht": ["cv"], "dateien": [{"name": "Vita.pdf", "anlagen": ["cv"]}],
                "vorgabe": "Laut Anzeige nur den Lebenslauf einreichen."}
        with self.assertRaisesRegex(ValueError, "Standardnachweise.*kurs"):
            self.build(spec)
        spec.update(optional=["kurs"], weglassen={"kurs": "Es ist ausschließlich ein Lebenslauf angefordert."})
        checked = self.build(spec)
        data = read(checked / "manifest.json")
        self.assertEqual(data["standard"], ["kurs"])
        self.assertEqual(data["plan"]["vorgabe"], spec["vorgabe"])
        self.command("anlagenstandard", "--leeren")
        self.assertEqual(read(checked / "manifest.json")["standard"], ["kurs"])
        receipt = self.base / "retrospektiv.txt"
        receipt.write_text("Eingang belegt", encoding="utf-8")
        self.workspace.record(self.jid, "beworben", receipt, "2020-01-01", "Historischer Eingang")
        with self.assertRaisesRegex(ValueError, "nach der belegten"):
            anlagen.associate(self.workspace, self.jid, checked.name, 1, "Historisch")
        evidence = self.workspace.evidence(checked / "Vita.pdf")
        jobs = self.workspace.jobs()
        jobs[0]["events"][0]["evidence"] = evidence
        write(self.workspace.path("bewerbungen.json"), jobs)
        with self.assertRaisesRegex(ValueError, "kein Einreichungsbeleg"):
            anlagen.associate(self.workspace, self.jid, checked.name, 1, "Kopie des Anhangs")
        renamed = self.base / "Quittung.pdf"
        renamed.hardlink_to(checked / "Vita.pdf")
        self.assertTrue(anlagen.is_application_artifact(self.workspace, anlagen.digest(renamed)))

    @unittest.skipUnless(tools_available("pdfinfo", "pdftotext", "pdfunite"), "Lokale Poppler-Werkzeuge erforderlich")
    def test_limits_invalid_sources_symlinks_and_partial_failure(self):
        self.add_docs()
        base_plan = plan()
        for settings in ({"max_bytes_gesamt": 1}, {"max_bytes_pro_datei": 1},
                         {"dateien": [{**base_plan["dateien"][0], "max_bytes": 1}]}):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, "überschritten"):
                self.build({**base_plan, **settings})
        incomplete = {"pflicht": ["cv", "fehlt"], "dateien": [{"name": "Vita.pdf", "anlagen": ["cv"]},
                                                               {"name": "Fehlt.pdf", "anlagen": ["fehlt"]}]}
        with self.assertRaises((ValueError, OSError)):
            self.build(incomplete)
        self.assertEqual(list(self.workspace.path("anlagen", "pakete", self.jid).iterdir()), [])
        self.cv.write_bytes(b"%PDF-1.7\ntruncated\n%%EOF")
        with self.assertRaisesRegex(ValueError, "pdfinfo"):
            self.command("anlage", "kaputt", "--titel", "Fehler", "--datei", str(self.cv))
        pdf(self.cv, [("Eins", 595, 842), ("US", 612, 792)])
        with self.assertRaisesRegex(ValueError, "Seite 2"):
            self.command("anlage", "format", "--titel", "Fehler", "--datei", str(self.cv))
        generic = pdf(self.cv, [("Extern", 595, 842)])
        self.command("anlage", "extern", "--art", "lebenslauf", "--titel", "Externes Original", "--datei", str(generic))
        spec = {"pflicht": ["extern"], "dateien": [{"name": "CV.pdf", "anlagen": ["extern"]}]}
        with self.assertRaisesRegex(ValueError, "Subject"):
            self.build(spec)
        spec["externe_originale"] = {"extern": "Original persönlich auf Stellenbezug geprüft."}
        self.assertEqual(list(anlagen.checked_cv_files(self.workspace, self.jid, self.build(spec).name)), ["CV.pdf"])
        other = self.workspace.add("B", "R", "https://example.org/b", "Aufgabe")[0]["id"]
        with self.assertRaisesRegex(ValueError, "Subject"):
            anlagen.build_package(self.workspace, other, {**base_plan, "externe_originale": {"cv": "Geprüft."}})
        catalog = self.workspace.path("anlagen", "inventar")
        source = catalog / "id-cv" / "original.pdf"
        source.write_bytes(self.certificate.read_bytes())
        with self.assertRaisesRegex(ValueError, "verändert"):
            self.build(base_plan)
        source.unlink()
        try:
            source.symlink_to(self.certificate)
        except OSError:
            self.skipTest("Konto darf keine Symlinks anlegen")
        with self.assertRaisesRegex(ValueError, "Pfad|Symlink"):
            self.build(base_plan)
