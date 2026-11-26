from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bewerbung import recherche
from bewerbung.cli import main
from bewerbung.core import Workspace, read, write
from bewerbung.export import followup_date, report
from bewerbung.setup import initialize


class WeekTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.w = Workspace(initialize(self.base / "Privat", "Person", ["Disposition"], "", "codex"))
        self.job = self.w.add("Alfa", "Disposition", "https://example.org/1", "Original A")[0]
        self.plan = self.w.path("wochenplan.json")

    def html(self):
        return self.w.path("exports", "Dashboard.html").read_text(encoding="utf-8")

    def test_dashboard_follows_real_contact_ignores_auto_receipt_closed_and_unverified(self):
        jid = self.job["id"]
        origin = self.w.path("beleg.txt")
        origin.write_text("Versandbeleg", encoding="utf-8")
        dates = [(date.today() - timedelta(days=n)).isoformat() for n in (28, 14, 1)]
        self.w.record(jid, "beworben", origin, dates[0], "Belegt")
        jobs = self.w.jobs()
        event = jobs[0]["events"][0]
        jobs[0]["events"].extend([dict(event, status="kontakt", occurred_on=dates[1]),
                                  dict(event, status="eingang", occurred_on=dates[2])])
        write(self.w.path("bewerbungen.json"), jobs)
        write(self.w.path("dashboard.json"), {"faellig_ab": 7, "dringend_ab": 20,
              "status": {"beworben": {"name": "Antwort offen", "ampel": "gelb"}},
              "je_stelle": {jid: {"dringend_ab": 16}}})
        report(self.w)
        snapshot = json.loads(self.html().split('id="snapshot">')[1].split('</script>')[0])
        self.assertEqual(snapshot[0]["followup_from"], dates[1])
        self.assertEqual(snapshot[0]["followup_days"], {"faellig_ab": 7, "dringend_ab": 16})
        self.assertIn("Antwort offen", self.html())
        with self.subTest("Geschlossene Anzeige"):
            self.assertIsNone(followup_date(self.w, dict(jobs[0], anzeigenstaende=[{"zustand": "geschlossen"}, {"zustand": "zugang_offen"}])))
        self.assertIsNone(followup_date(self.w, dict(jobs[0], status="absage")))
        self.assertIsNone(followup_date(self.w, dict(jobs[0], events=[jobs[0]["events"][-1]])))
        self.w.path(event["evidence"]["file"]).write_bytes(b"geaendert")
        self.assertIsNone(followup_date(self.w, jobs[0]))
        write(self.w.path("dashboard.json"), {"faellig_ab": 29, "dringend_ab": 28})
        with self.assertRaisesRegex(ValueError, "Fristen"):
            report(self.w)

    def test_real_entry_point_search_review_score_cluster_and_report(self):
        profile = self.w.profile()
        profile["facts"] = [{"id": "eins", "text": "Original B", "source": "eigene Angabe", "keywords": ["Original"]}]
        write(self.w.path("profil.json"), profile)
        source = self.w.path("gesehen.txt")
        source.write_text("Original B", encoding="utf-8")
        ads = [dict(rolle="Disposition", firma="Firma", beschreibung=text, url="https://example.org/" + str(i))
               for i, text in enumerate(("Original A", "Original B", "Ungeprüft"), 1)]
        indeed = self.w.path("funde.json")
        write(indeed, [dict(role=ad["rolle"], company=ad["firma"], description=ad["beschreibung"], url=ad["url"],
                            indeed_url="https://indeed.com/viewjob?jk=" + str(i), gesehen_am=date.today().isoformat())
                       for i, ad in enumerate(ads)])
        cluster = dict(titelbegriffe=["Disposition"], kldb="12345", region=1, niveau=3)
        write(self.plan, dict(bestaetigt=[dict(url=ads[1]["url"], firma="Firma", textdatei=source.name,
                                               gesehen_am=date.today().isoformat())], gehaltscluster=[cluster]))
        result = {"ergebnisse": [{"Median": 2000}], "quelle": "https://example.org/markt"}
        with patch.dict(os.environ, {"BA_JOBSUCHE_API_KEY": ""}), patch.object(recherche, "atlas", return_value=result) as market:
            with redirect_stdout(StringIO()):
                main(["--ordner", str(self.w.root), "wochenlauf", "--plan", str(self.plan), "--indeed-datei", str(indeed)])
            market.assert_called_once_with("12345", 1, 3)
        data = read(next(self.w.path("exports").glob("Wochenlauf-*.json")))
        self.assertEqual(len(data["bestaetigt"]), 2)
        self.assertEqual(len(data["ungesichtet"]), 1)
        self.assertTrue(all(row["passung"]["score"] is not None for row in data["bestaetigt"]))
        self.assertEqual(data["abdeckung"][0]["status"], "fehlgeschlagen")
        self.assertEqual(len(self.w.jobs()), 2)
        self.assertTrue(all(j["status"] == "recherche" and not j["events"] for j in self.w.jobs()))
        self.assertIn("Entgeltatlas 12345", self.html())
        with redirect_stdout(StringIO()), patch.object(recherche, "atlas", side_effect=ValueError("HTTP 503")), patch.object(recherche, "fetch") as fetch:
            main(["--ordner", str(self.w.root), "wochenlauf", "--bericht", data["suchbericht"], "--plan", str(self.plan)])
            fetch.assert_not_called()
        rerun = read(sorted(self.w.path("exports").glob("Wochenlauf-*.json"))[-1])
        self.assertEqual(rerun["gehaltsquellen"][0]["status"], "zugang_offen")
        self.assertEqual(len(self.w.jobs()), 2)

    def test_new_text_requires_confirmation_and_absent_job_is_not_scored(self):
        report_name = "Suchlauf-20260102T120000000000Z.json"
        write(self.w.path("exports", report_name), dict(abdeckung=[], treffer=[
            dict(nummer=1, url=self.job["url"], role="Disposition", description="Andere Bedingungen")]))
        write(self.plan, {})
        with redirect_stdout(StringIO()):
            main(["--ordner", str(self.w.root), "wochenlauf", "--plan", str(self.plan), "--bericht", report_name])
        data = read(next(self.w.path("exports").glob("Wochenlauf-*.json")))
        self.assertEqual(data["bestaetigt"], [])
        self.assertIn("erneute Sichtung", data["ungesichtet"][0]["grund"])
        self.assertEqual(self.w.jobs()[0]["description"], "Original A")
