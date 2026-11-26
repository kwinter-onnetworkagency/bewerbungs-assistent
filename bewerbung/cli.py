import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__
from .core import NOTE_TYPES, Workspace, validate_profile, write, keyword_match, search_queries
from .documents import convert_pdf, office_binary
from . import anlagen, applemail, mailstand, persona, portal, profilvergleich, recherche, unterlagentext, termine
from .gehalt import marktwert
from .export import report, chat_bundle
from .setup import initialize, wizard, ASSISTANTS
from .interview import interview


def parser():
    p = argparse.ArgumentParser(description="Bewerbungs-Assistent: lokal, belegorientiert, ohne automatischen Versand.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--ordner", default=".", help="Dein privater Arbeitsordner, Standard: aktueller Ordner")
    commands = p.add_subparsers(dest="command")
    init = commands.add_parser("einrichten", help="Geführte Einrichtung, ohne Optionen interaktiv")
    init.add_argument("--ziel")
    init.add_argument("--portfolio", choices=["ja", "nein"], nargs="?", const="ja", help="Lokale Portfolio-Startseite und Cloudflare-Wegweiser anlegen")
    init.add_argument("--wunschdomain", help="Wunschdomain für das Agentur-Bestellformular")
    init.add_argument("--domainweg", choices=["vorhanden", "onnetwork", "cloudflare", "spaeter"])
    init.add_argument("--name")
    init.add_argument("--rolle", action="append", default=[])
    init.add_argument("--ort", default="")
    init.add_argument("--assistent", choices=ASSISTANTS, default="chatgpt")
    commands.add_parser("pruefen", help="Lokale Voraussetzungen und Profil prüfen")
    commands.add_parser("interview", help="Persönlichen Zuschnitt erfragen, pausieren, prüfen und als Profil übernehmen")
    fact = commands.add_parser("fakt", help="Einen belegten Profilfakt hinzufügen")
    fact.add_argument("--id", required=True)
    fact.add_argument("--text", required=True)
    fact.add_argument("--quelle", required=True)
    fact.add_argument("--sprache", choices=("de","en"), default="de")
    fact.add_argument("--text-en")
    fact.add_argument("--text-de")
    fact.add_argument("--art", choices=("profile","experience","achievement","education","certificate","skill","strength","language","volunteering"))
    fact.add_argument("--belegart", choices=("nutzerangabe","dokument","unbekannt"), default="nutzerangabe")
    fact.add_argument("--stichwort", action="append", default=[])
    commands.add_parser("suchanfragen", help="ATS-Suchanfragen vorbereiten, führt keine Websuche aus")
    job = commands.add_parser("stelle", help="Gelesene vollständige Stellenanzeige erfassen")
    for arg in ["firma", "rolle", "url", "textdatei"]:
        job.add_argument("--" + arg, required=True)
    job.add_argument("--referenz", default="")
    score = commands.add_parser("bewerten", help="Manuelle Bewertung festhalten")
    score.add_argument("id")
    score.add_argument("--score", type=int, required=True)
    score.add_argument("--grund", required=True)
    match = commands.add_parser("wortabgleich", help="Erklärbarer Wortabgleich, ersetzt keine Eignungsprüfung")
    match.add_argument("id")
    draft = commands.add_parser("entwurf", help="Anschreibenentwurf speichern, keine Einreichung")
    draft.add_argument("id")
    draft.add_argument("--textdatei", required=True)
    draft.add_argument("--fakt", action="append", required=True)
    qa = commands.add_parser("pruefung", help="Von dir durchgeführte Inhalts- und Dokumentprüfung dokumentieren")
    qa.add_argument("id")
    qa.add_argument("--inhalt", required=True)
    qa.add_argument("--dokument", required=True)
    status = commands.add_parser("ereignis", help="Belegtes Ereignis einer eindeutigen Stelle zuordnen")
    status.add_argument("id")
    status.add_argument("--status", required=True)
    status.add_argument("--beleg")
    status.add_argument("--datum", required=True)
    status.add_argument("--grund", required=True)
    status.add_argument("--message-id", default="")
    note = commands.add_parser("notiz", help="Recherche, Gesprächsmappe oder Aufgabe zur Stelle sichern")
    note.add_argument("id")
    note.add_argument("--art", choices=NOTE_TYPES, required=True)
    note.add_argument("--titel", required=True)
    note.add_argument("--textdatei", required=True)
    note.add_argument("--quelle", action="append", default=[])
    note.add_argument("--beleg", help="Privaten Quellbeleg sichern")
    note.add_argument("--datum", help="Frist oder Gesprächsdatum (JJJJ-MM-TT)")
    note.add_argument("--erledigt", action="store_true")
    market = commands.add_parser("gehaltswert", help="Exakten belegten Marktwert vergleichen")
    market.add_argument("id")
    for field in ("titel", "quelle", "beruf", "region", "basis", "wert", "waehrung", "datenstand"):
        market.add_argument("--" + field, required=True)
    market.add_argument("--zeitraum", choices=["Monat", "Jahr", "Stunde"], required=True)
    market.add_argument("--kennzahl", choices=["Median", "Durchschnitt", "Q25", "Q75"], required=True)
    for module in (anlagen, applemail, mailstand, persona, portal, profilvergleich, recherche, unterlagentext, termine):
        module.register(commands)
    commands.add_parser("bericht", help="Markdown-Übersicht und CSV-Tabelle erzeugen")
    chat = commands.add_parser("chat-export", help="Vier selbst zu prüfende Dateien für ein privates Chat-Projekt bündeln")
    chat.add_argument("--mit-kontakt", action="store_true", help="Private Kontakt- und Mailangaben ausdrücklich aufnehmen")
    chat.add_argument("--mit-verlauf", action="store_true", help="Anzeigen, Ereignisdaten, Screening-, Aufgaben- und Gesprächsnotizen ausdrücklich mitnehmen")
    chat.add_argument("--mit-gehalt", action="store_true", help="Persönliche Gehaltspräferenz ausdrücklich aufnehmen")
    routine = commands.add_parser("routine", help="Vorlagen für vom Nutzer einzurichtende Routinen anzeigen")
    routine.add_argument("art", choices=["stellensuche", "rueckmeldungen"])
    return p


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    try:
        if not a.command or a.command == "einrichten" and not a.ziel:
            wizard(portfolio=(a.portfolio == "ja") if getattr(a, "portfolio", None) else None, route=getattr(a, "domainweg", None), wish=getattr(a, "wunschdomain", None))
            return
        if a.command == "einrichten":
            if not a.name:
                raise ValueError("--name ist bei --ziel erforderlich.")
            print(initialize(a.ziel, a.name, a.rolle, a.ort, a.assistent, a.portfolio != "nein", a.domainweg, a.wunschdomain))
            return
        w = Workspace(a.ordner)
        if a.command == "interview":
            interview(w)
        elif a.command == "pruefen":
            profile = w.profile()
            print(f"Version {__version__} | Python {sys.version.split()[0]} | Profil gültig, {len(profile['facts'])} Fakten")
            print("Claude Code: " + ("gefunden" if shutil.which("claude") else "optional, nicht gefunden"))
            print("Codex: " + ("gefunden" if shutil.which("codex") else "optional, nicht gefunden"))
            import platform
            print("PDF-Konvertierung: " + ("verfügbar" if office_binary() else "LibreOffice optional installieren"))
            for tool in ("pdfinfo", "pdftotext", "pdfunite"):
                print(f"{tool}: " + ("gefunden" if shutil.which(tool) else "Poppler für PDF-Prüfung/Pakete installieren"))
            print("Apple Mail, Kalender und Kontakte: " + ("macOS, App-Zugriff separat prüfen" if platform.system() == "Darwin" else "EML, ICS und VCF verwenden"))
            print("Mail-/Browserzugriff und Hintergrundroutinen: persönliche Einrichtung erforderlich.")
            if not profile["facts"]:
                print("Nächster Schritt: belegte Profilfakten ergänzen. Noch keine Unterlagen erzeugen.")
        elif a.command == "fakt":
            with w.locked():
                profile = w.profile()
                profile["facts"].append(dict(id=a.id, text=a.text, source=a.quelle, evidence_type=a.belegart, kind=a.art, language=a.sprache,
                    translations={k: v for k, v in (("en", a.text_en), ("de", a.text_de)) if v}, keywords=a.stichwort))
                validate_profile(profile)
                write(w.path("profil.json"), profile)
            print("Profilfakt gespeichert.")
        elif a.command == "suchanfragen":
            print("\n".join(search_queries(w.profile())))
        elif a.command == "stelle":
            job, created = w.add(a.firma, a.rolle, a.url, Path(a.textdatei).read_text(encoding="utf-8-sig"), a.referenz)
            print(job["id"] + (" neu erfasst" if created else " bereits bekannt, unverändert"))
        elif a.command == "bewerten":
            w.score(a.id, a.score, a.grund)
            print("Manueller Score gespeichert.")
        elif a.command == "wortabgleich":
            print(json.dumps(keyword_match(w.profile(), w.job(w.jobs(), a.id)["description"]), ensure_ascii=False, indent=2))
        elif a.command == "entwurf":
            w.draft(a.id, Path(a.textdatei).read_text(encoding="utf-8-sig"), a.fakt)
            print("Entwurf gespeichert. Eine vorhandene Prüfung ist durch die Änderung ungültig.")
        elif a.command == "pruefung":
            w.qa(a.id, a.inhalt, a.dokument)
            print("Deine beiden Prüfschritte dokumentiert; nicht automatisch als bestanden geprüft.")
        elif a.command == "ereignis":
            changed = w.record(a.id, a.status, a.beleg, a.datum, a.grund, a.message_id)
            print("Ereignis erfasst." if changed else "Ereignis bereits erfasst, unverändert.")
        elif a.command in anlagen.COMMANDS:
            anlagen.run(a, w)
        elif any(module.run(a, w) for module in (applemail, mailstand, persona, portal, profilvergleich, recherche, unterlagentext, termine)):
            pass
        elif a.command == "gehaltswert":
            marktwert(w, a.id, a.titel, a.quelle, a.beruf, a.region, a.basis, a.zeitraum,
                      a.kennzahl, a.wert, a.waehrung, a.datenstand)
            print("Marktvergleich gespeichert.")
        elif a.command == "notiz":
            w.add_note(a.id, a.art, a.titel, Path(a.textdatei).read_text(encoding="utf-8-sig"),
                       a.quelle, a.datum, a.erledigt, a.beleg)
            print("Notiz gespeichert.")
        elif a.command == "bericht":
            print(report(w))
            print(w.path("exports", "Dashboard.html"))
        elif a.command == "chat-export":
            print(chat_bundle(w, contact=a.mit_kontakt, salary=a.mit_gehalt, details=a.mit_verlauf))
            print("Enthält dein Profil. Lokal entpacken, Dateien prüfen und einzeln in dein privates Projekt hochladen.")
        elif a.command == "routine":
            filename = "STELLENSUCHE.txt" if a.art == "stellensuche" else "RUECKMELDUNGEN.txt"
            print(w.path("resources", filename).read_text(encoding="utf-8"))
            print("Vorlage angezeigt. Es wurde kein Zeitplan angelegt.")
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        p.exit(2, "Hinweis: " + str(exc) + "\n")
    except (EOFError, KeyboardInterrupt):
        p.exit(130, "\nAbgebrochen. Bereits gespeicherte Interviewantworten bleiben erhalten.\n")

