import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bewerbung import recherche as r
from bewerbung.core import Workspace, read, write


class RechercheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write(self.root / "workspace.json", {"schema_version": 1})
        write(self.root / "profil.json", dict(schema_version=1, name="Test", target_roles=["Disposition"],
                                               facts=[], location="Privater Wohnort"))
        write(self.root / "bewerbungen.json", [])
        (self.root / "exports").mkdir()
        self.w = Workspace(self.root)
        self.parser = argparse.ArgumentParser()
        r.register(self.parser.add_subparsers(dest="command"))

    def command(self, *cmd):
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(r.run(self.parser.parse_args(cmd), self.w))
        return output.getvalue()

    def search(self, *args):
        self.command("suchlauf", *args)
        return read(sorted((self.root / "exports").glob("Suchlauf-*.json"))[-1])

    def job(self):
        return self.w.add("Testbetrieb", "Disposition", "https://example.org/stelle/57",
                          "Wir suchen Erfahrung mit Warenwirtschaft und Inventur.")[0]["id"]

    @patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": "test"})
    def test_ba_page_failure_retains_first_page_and_known_ids(self):
        sample = dict(referenznummer="ref/1", stellenangebotsTitel="Disposition", firma="Test AG",
                      stellenlokationen=[{"adresse": {"ort": "Bonn"}}], gehaltsspanneBis=2000)
        self.w.add("Test AG", "Disposition", "https://www.arbeitsagentur.de/jobsuche/jobdetail/ref%2F1", "Volltext")
        with patch.object(r, "fetch", side_effect=[{"ergebnisliste": [sample] * 25}, ValueError("HTTP 503")]) as get:
            report = self.search("--seiten", "2")
        self.assertNotIn("wo", parse_qs(urlsplit(get.call_args_list[0].args[0]).query))
        self.assertIn("page=2", get.call_args_list[1].args[0])
        self.assertEqual(len(report["treffer"]), 1)
        ad = report["treffer"][0]
        self.assertTrue(ad["bekannt"])
        self.assertEqual(ad["gehaltsangabe_der_anzeige"], {"gehaltsspanneBis": 2000})
        self.assertEqual(report["abdeckung"][0]["status"], "teilweise")
        self.assertIn("503", report["abdeckung"][0]["grund"])
        self.assertEqual(len(self.w.jobs()), 1)

    @patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": "test"})
    def test_source_schema_failure_and_detail_failure_do_not_hide_other_sources(self):
        listing = {"jobs": [{"id": 5, "title": "Disposition", "location": {"name": "Leipzig"},
                             "absolute_url": "https://job-boards.greenhouse.io/demo/jobs/5"}]}
        with patch.object(r, "fetch", side_effect=[{"error": True}, listing, ValueError("HTTP 429")]):
            report = self.search("--greenhouse", "demo", "--details")
        self.assertEqual([c["status"] for c in report["abdeckung"][:2]], ["fehlgeschlagen", "teilweise"])
        self.assertEqual(report["treffer"][0]["detailfehler"], "HTTP 429")
        self.assertFalse(self.w.jobs())

    @patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": "test"})
    def test_ba_detail_text_and_null_detail(self):
        listing = {"ergebnisliste": [{"referenznummer": "a/9", "stellenangebotsTitel": "Disposition", "firma": "A"},
                                     {"referenznummer": "b", "stellenangebotsTitel": "Disposition", "firma": "B"}]}
        with patch.object(r, "fetch", side_effect=[listing, {"stellenangebotsBeschreibung": "Volltext A"}, {}]):
            report = self.search("--details", "--ort", "Bonn")
        self.assertEqual(report["treffer"][0]["description"], "Volltext A")
        self.assertNotIn("description", report["treffer"][1])
        self.assertEqual(report["abdeckung"][0]["detailfehler"][0]["referenz"], "b")

    @patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": ""})
    def test_board_detail_indeed_provenance_filters_and_repeated_report(self):
        export = self.root / "indeed.json"
        write(export, [dict(role="Disposition", company="Demo", location="Bonn", gesehen_am="2025-01-01",
                            indeed_url="https://de.indeed.com/viewjob?jk=123",
                            url="https://boards.greenhouse.io/demo/jobs/5?utm_source=indeed")])
        listing = {"jobs": [
            {"id": 4, "title": "Buchhaltung", "location": {"name": "Bonn"}},
            {"id": 3, "title": "Disposition", "location": {"name": "Berlin"}},
            {"id": 5, "title": "Disposition", "location": {"name": "Bonn"},
             "absolute_url": "https://job-boards.greenhouse.io/demo/jobs/5"}]}
        with patch.object(r, "fetch", side_effect=[listing, {"content": "&lt;p&gt;Text &amp;amp; Absatz&lt;/p&gt;"}]):
            report = self.search("--greenhouse", "demo", "--ort", "Bonn", "--details", "--indeed-datei", str(export))
        self.assertEqual(len(report["treffer"]), 1)
        ad = report["treffer"][0]
        self.assertEqual(ad["description"], "Text & Absatz")
        self.assertEqual([(x["quelle"]) for x in ad["fundstellen"]], ["Greenhouse", "Indeed"])
        self.assertEqual(ad["fundstellen"][1]["gesehen_am"], "2025-01-01")
        self.assertEqual(report["abdeckung"][2]["zugang"], "Dateiimport")
        name = next((self.root / "exports").glob("*.json")).name
        with self.assertRaises(ValueError):
            self.command("suchfund", name, "1")
        self.command("suchfund", name, "1", "--firma", "Beispielunternehmen")
        self.command("suchfund", name, "1", "--firma", "Beispielunternehmen")
        self.assertEqual(len(self.w.jobs()), 1)
        job = self.w.jobs()[0]
        self.assertEqual(job["description"], "Text & Absatz")
        self.assertEqual(len(job["notes"]), 1)
        self.assertIn("https://de.indeed.com/viewjob?jk=123", job["notes"][0]["sources"])
        with self.assertRaises(ValueError):
            self.command("suchfund", "../" + name, "1", "--firma", "Demo")
        with patch.object(r, "fetch") as net:
            self.search()
            net.assert_not_called()
        self.assertEqual(len(list((self.root / "exports").glob("*.json"))), 2)

    @patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": ""})
    def test_invalid_indeed_host_and_missing_key_are_not_zero_results(self):
        file = self.root / "indeed.json"
        write(file, [dict(role="Disposition", indeed_url="https://indeed.com.example.org/viewjob")])
        with patch.object(r, "fetch") as net:
            report = self.search("--indeed-datei", str(file))
            net.assert_not_called()
        self.assertEqual(report["abdeckung"][0]["status"], "fehlgeschlagen")
        self.assertEqual(report["abdeckung"][-1]["status"], "fehlgeschlagen")
        self.assertFalse(report["treffer"])
        with self.assertRaises(ValueError):
            self.search("--greenhouse", "../invalid")

    def test_scores_keep_manual_zero_and_explain_missing_dimensions(self):
        jid = self.job()
        profile = self.w.profile()
        profile["facts"] = [dict(id="skill1", text="Inventur", source="Beispiel", kind="skill"),
                            dict(id="f1", text="Praxis", source="Beispiel", keywords=["Warenwirtschaft"])]
        write(self.w.path("profil.json"), profile)
        self.w.score(jid, 0, "Ein geprüfter Ausschlussgrund.")
        score = json.loads(self.command("passung", "--alle"))[0]
        self.assertEqual((score["score"], score["score_automatisch"]), (0, 100))
        self.assertEqual(score["fakten_treffer"], ["f1"])
        self.assertEqual(score["kompetenztreffer"], ["skill1"])
        self.assertEqual(self.w.jobs()[0]["score_manual"], 0)
        profile.update(target_roles=[], facts=[])
        self.assertIsNone(r.fit(profile, self.w.jobs()[0])["score_automatisch"])

    def test_atlas_source_numbers_missing_values_and_employer_band_are_separate(self):
        jid = self.job()
        self.command("gehaltsband", jid, "--bis", "3200,50", "--waehrung", "EUR", "--zeitraum", "Monat",
                     "--basis", "Fixgehalt brutto für 36 Stunden/Woche", "--quelle", "https://example.org/tarif",
                     "--stand", "2025-01-01")
        with patch.dict(os.environ, {"BA_ENTGELTATLAS_API_KEY": "test"}), patch.object(
                r, "fetch", return_value=[dict(entgelt=-1, entgeltQ25=2500.5, entgeltQ75=None, besetzung=20)]):
            result = json.loads(self.command("entgeltatlas", "--id", jid, "--kldb", "83112", "--niveau", "2"))
        row = result["ergebnisse"][0]["kennzahlen"]
        self.assertEqual(result["ergebnisse"][0]["quellwerte"]["entgelt"], -1)
        self.assertIsNone(row["Median"])
        self.assertEqual(row["Q25"]["hochrechnung_jahr_eur"], 30006)
        notes = self.w.jobs()[0]["notes"]
        self.assertEqual([n["kind"] for n in notes], ["arbeitgeberband", "marktvergleich"])
        self.assertIn("bis 3200.50 EUR", notes[0]["content"])
        self.assertNotIn("von 0", notes[0]["content"])

    def test_bad_pay_and_invalid_schema_fail_without_saving(self):
        jid = self.job()
        with self.assertRaises(ValueError):
            self.command("gehaltsband", jid, "--von", "99", "--bis", "75", "--waehrung", "EUR",
                         "--zeitraum", "Stunde", "--quelle", "https://example.org", "--stand", "2025-01-01",
                         "--basis", "Fixum")
        with patch.dict(os.environ, {"BA_ENTGELTATLAS_API_KEY": "test"}):
            for response in ({"error": 1}, [{}], [{"entgelt": "gesperrt"}]):
                with self.subTest(response=response), patch.object(r, "fetch", return_value=response), self.assertRaises(ValueError):
                    self.command("entgeltatlas", "--id", jid, "--kldb", "83112", "--niveau", "2")
        self.assertFalse(self.w.jobs()[0].get("notes"))

    def test_provider_urls_variants_and_legacy_jobs(self):
        ashby = "bfeae0f2-6440-476d-80bd-42e6f664d596"
        pairs = [
            (f"https://jobs.ashbyhq.com/demo/{ashby}", f"https://jobs.ashbyhq.com/demo/{ashby}/application?src=X"),
            ("https://demo.wd5.myworkdayjobs.com/en-US/site/job/Berlin/Old_JR-914",
             "https://demo.wd3.myworkdayjobs.com/de-DE/site/job/New_JR-914/apply"),
            ("https://www.smartrecruiters.com/Demo/12345678-first-role",
             "https://jobs.smartrecruiters.com/Demo/12345678-new-role?trid=123"),
            ("https://demo.recruitee.com/o/first-role", "https://demo.recruitee.com/l/de/o/first-role/c/new"),
        ]
        for old, new in pairs:
            with self.subTest(old=old):
                self.assertEqual(r.identity(old), r.identity(new))
                self.assertNotEqual(r.identity(new), r.identity(new.replace("demo", "other").replace("Demo", "Other")))
                job, _ = self.w.add("Arbeitgeber", "Rolle", old, "Ursprung")
                jobs = self.w.jobs()
                self.w.job(jobs, job["id"])["identity"] = old
                write(self.w.path("bewerbungen.json"), jobs)
                again, created = self.w.add("Arbeitgeber", "Rolle", new, "Änderung")
                self.assertFalse(created)
                self.assertEqual(job["id"], again["id"])

    def test_known_changes_closure_and_access_are_separate(self):
        jid = self.job()
        job = self.w.jobs()[0]
        found = self.root / "indeed.json"
        sample = dict(role="Disposition", company="Testbetrieb", location="Bonn", gesehen_am="2024-08-02",
                      indeed_url="https://de.indeed.com/viewjob?jk=abc", url=job["url"],
                      anforderungen="Deutsch", arbeitsmodell="Remote", gehaltsangabe_der_anzeige="50.000 EUR")
        with patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": ""}):
            write(found, [sample])
            self.search("--indeed-datei", str(found))
            changed = {**sample, "anforderungen": "Deutsch und Englisch", "arbeitsmodell": "Hybrid",
                       "gehaltsangabe_der_anzeige": "55.000 EUR", "description": "Aktuelle Anforderungen"}
            write(found, [changed])
            ad = self.search("--indeed-datei", str(found))["treffer"][0]
            self.assertEqual(set(ad["aenderungen"]), {"anforderungen", "arbeitsmodell", "gehaltsangabe_der_anzeige", "description"})
            self.assertEqual(ad["aenderungen"]["arbeitsmodell"], {"vorher": "Remote", "jetzt": "Hybrid"})
            report = self.search()
            self.assertEqual(report["nicht_wiedergefunden"], [jid])
            self.assertEqual(self.w.jobs()[0]["description"], job["description"])
        base = ["anzeigenstand", jid, "--quelle", job["url"]]
        self.command(*base, "--zustand", "zugang_offen", "--beleg", "HTTP 403")
        self.command(*base, "--zustand", "geschlossen", "--beleg", "Anzeige meldet, die Bewerbungsfrist sei beendet.")
        self.command(*base, "--zustand", "geschlossen", "--beleg", "Anzeige meldet, die Bewerbungsfrist sei beendet.")
        new = self.root / "aktuell.txt"
        new.write_text("Neue Bedingungen", encoding="utf-8")
        self.command(*base, "--zustand", "offen", "--beleg", "Wieder ausgeschrieben", "--textdatei", str(new), "--uebernehmen")
        current = self.w.jobs()[0]
        self.assertEqual(current["description"], "Neue Bedingungen")
        self.assertEqual(current["anzeigenstaende"][-1]["ersetzter_volltext"], job["description"])
        self.assertEqual([s["zustand"] for s in current["anzeigenstaende"]], ["zugang_offen", "geschlossen", "offen"])
        self.assertEqual(current["events"], [])

    def test_structure_unknown_experience_gap_exception_and_profile_revision(self):
        job = self.w.add("B", "Disposition", "https://example.org/str", "Mindestens 5 Jahre Führungserfahrung. Standort Bonn.")[0]
        profile = self.w.profile()
        profile["facts"] = [{"id": "f1", "text": "3 Jahre Führungserfahrung", "source": "Tätigkeitsnachweis", "keywords": ["Führungserfahrung"]}]
        profile["preferences"] = {"erfahrungsfelder": {"leitung": ["Führungserfahrung"]},
                                  "strukturgewichte": {"titel": 1, "erfahrung": 3, "ort": 2}}
        write(self.w.path("profil.json"), profile)
        score = json.loads(self.command("passung", "--id", job["id"]))[0]
        structure = score["struktur"]
        self.assertEqual(structure["wert"], 25)
        self.assertIn("gehalt", structure["offen"])
        gap = structure["pruefungen"][0]
        self.assertEqual((gap["urteil"], gap["gefordert_jahre"], gap["belegt_jahre"], gap["fakten"]), ("luecke", 5, 3, ["f1"]))
        self.assertIn("standort", score["anzeigenbegriffe_ohne_worttreffer"])
        self.assertIn("führungserfahrung", score["anzeigenbegriffe_im_cv"])
        self.command("strukturcheck", job["id"], "--kriterium", "ort", "--anzeige", "Standort Bonn", "--urteil", "ausnahme",
                     "--grund", "Für diese Stelle persönlich akzeptiert.")
        self.command("strukturcheck", job["id"], "--kriterium", "erfahrung", "--name", "leitung",
                     "--anzeige", "5 Jahre Führungserfahrung", "--grund", "Bestätigter Tätigkeitszeitraum.",
                     "--gefordert-jahre", "5", "--belegt-jahre", "3", "--fakt", "f1")
        with self.assertRaisesRegex(ValueError, "Fakten-ID"):
            self.command("strukturcheck", job["id"], "--kriterium", "musskriterium", "--anzeige", "5 Jahre",
                         "--urteil", "luecke", "--grund", "Ungeprüft")
        self.w.score(job["id"], 0, "Bewusster Ausschluss")
        final = json.loads(self.command("passung", "--id", job["id"]))[0]
        self.assertEqual(final["score"], 0)
        self.assertEqual(final["struktur"]["wert"], 50)
        profile["facts"] = []
        write(self.w.path("profil.json"), profile)
        stale = json.loads(self.command("passung", "--id", job["id"]))[0]
        self.assertEqual(stale["score"], 0)
        self.assertTrue(all(x["urteil"] == "offen" for x in stale["struktur"]["pruefungen"]))
        self.assertEqual(r.experience_checks(profile, {**job, "description": "Nicht mindestens 5 Jahre Führungserfahrung notwendig."}), [])
