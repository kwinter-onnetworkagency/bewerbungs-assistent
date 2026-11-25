"""Geführte Einrichtung in einem neuen privaten Ordner."""
from html import escape
from pathlib import Path
import shutil
import json
import unicodedata
from urllib.parse import quote

from .core import text, validate_profile, write, now, Workspace

SOURCE = Path(__file__).resolve().parent.parent
ASSISTANTS = {"chatgpt": "ChatGPT-Projekt", "claude": "Claude-Projekt", "claude-code": "Claude Code", "codex": "Codex"}


DOMAIN_ROUTES = json.loads((SOURCE / "resources" / "domainwege.json").read_text(encoding="utf-8"))


def domain_guide(portfolio, route, wish):
    if route is not None and (not portfolio or route not in DOMAIN_ROUTES):
        raise ValueError("Bitte einen gültigen Domainweg mit aktivem Portfolio wählen.")
    guide = DOMAIN_ROUTES.get(route, "")
    wish = unicodedata.normalize("NFC", (wish or "").strip())
    if not wish:
        return guide

    invalid = "Für die Agenturbestellung bitte nur eine Wunschdomain mit Endung eingeben, z. B. beispiel.de."
    # Punycode measures the DNS wire label without mapping ß to ss as IDNA 2003 does.
    labels = wish.lower().split(".")
    ascii_labels = [label if label.isascii() else "xn--" + label.encode("punycode").decode("ascii")
                    for label in labels]
    if (route != "onnetwork" or len(labels) < 2 or len(labels[-1]) < 2 or not labels[-1][0].isalpha()
            or len(".".join(ascii_labels)) > 253
            or any(not label.replace("-", "").isalnum() or label.startswith("-") or label.endswith("-")
                   for label in labels)
            or any(len(label) > 63 for label in ascii_labels)):
        raise ValueError(invalid)
    form = "https://customer.onnetwork.agency/portal/domains/new"
    return guide.replace(form, form + "?domain=" + quote(wish, safe=""))


def initialize(destination, name, roles, location, assistant, portfolio=True, route=None, wish=None):
    guide = domain_guide(portfolio, route, wish)
    return _write_workspace(destination, name, roles, location, assistant, portfolio, route, guide)


def _write_workspace(destination, name, roles, location, assistant, portfolio, route, guide):
    dest = Path(destination).expanduser().absolute()
    if assistant not in ASSISTANTS:
        raise ValueError("Unbekannter Assistent.")
    if dest.is_symlink() or dest.exists():
        raise ValueError("Ziel existiert bereits. Einen neuen, leeren Ordnernamen wählen; vorhandene Daten bleiben erhalten.")
    resolved = dest.resolve()
    if resolved.is_relative_to(SOURCE):
        raise ValueError("Persönlichen Ordner außerhalb des heruntergeladenen Quellordners anlegen.")
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise ValueError("Persönliche Einrichtung außerhalb eines Git-Repositories anlegen.")
    profile = validate_profile(dict(schema_version=1, name=text(name, "Name", 200),
                                    target_roles=roles, location=location, facts=[]))
    dest.mkdir(parents=True, mode=0o700)
    try:
        dest.chmod(0o700)
        for folder in ["belege", "dokumente", "exports", "integration", "unterlagen"]:
            (dest / folder).mkdir(mode=0o700)
        shutil.copytree(SOURCE / "bewerbung", dest / "bewerbung", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copyfile(SOURCE / "start.py", dest / "start.py")
        shutil.copyfile(SOURCE / "LICENSE", dest / "LICENSE")
        shutil.copytree(SOURCE / "resources", dest / "resources")
        shutil.copytree(SOURCE / "docs", dest / "docs")
        (dest / ".gitignore").write_text("*\n", encoding="utf-8")
        write(dest / "profil.json", profile)
        write(dest / "bewerbungen.json", [])
        shutil.copyfile(SOURCE / "resources" / "Dashboard.html", dest / "exports" / "Dashboard.html")
        instructions = (SOURCE / "resources" / "ASSISTENT.txt").read_text(encoding="utf-8")
        portfolio_guide = ""
        if portfolio:
            folder = dest / "portfolio" / "public"
            folder.mkdir(parents=True)
            template = (SOURCE / "resources" / "Portfolio.html").read_text(encoding="utf-8")
            (folder / "index.html").write_text(template.replace("__NAME__", escape(profile["name"], quote=False)), encoding="utf-8")
            portfolio_guide = "\n" + (SOURCE / "resources" / "PORTFOLIO.txt").read_text(encoding="utf-8")
        if portfolio is not None:
            instructions += "\nPortfolio-Auswahl im Wizard: " + ("Ja" if portfolio else "Nein") + ". Im Interview berücksichtigen.\n"
        if route:
            portfolio_guide += "\n" + guide + "\n"
            instructions += "\nDomainweg: " + guide + "\n"
        instructions += "\nArbeitsmodus: " + ASSISTANTS[assistant] + ".\n"
        (dest / "integration" / "PROJEKTANWEISUNG.txt").write_text(instructions, encoding="utf-8")
        if assistant in {"claude-code", "codex"}:
            (dest / ("CLAUDE.md" if assistant == "claude-code" else "AGENTS.md")).write_text(instructions, encoding="utf-8")
            skill_dir = ".agents" if assistant == "codex" else ".claude"
            shutil.copytree(dest / "resources" / "skills", dest / skill_dir / "skills")
        write(dest / "workspace.json", dict(schema_version=1, assistant=assistant, portfolio=portfolio, domainweg=route, created_at=now()))
        (dest / "START_HIER.md").write_text(
            "# Dein persönlicher Bewerbungsordner\n\n"
            "Dieser Ordner enthält private Daten. Nicht auf GitHub hochladen.\n\n"
            "1. Öffne docs/INSTALLATION.md und den Abschnitt für deinen Assistenten.\n"
            "2. Beginne im Assistenten mit /interview, in Codex mit $interview.\n"
            "3. Ergänze belegte Fakten aus Lebenslauf/Nachweisen und prüfe das erzeugte Profil selbst.\n"
            "4. Starte python start.py pruefen.\n"
            "5. Nutze resources/STARTPROMPTS.md für die erste Stellensuche.\n\n"
            "In ChatGPT/Claude im Browser: PROJEKTANWEISUNG.txt als Projektanweisung übernehmen, "
            "python start.py chat-export ausführen, ZIP lokal entpacken und die vier Exportdateien "
            "nach eigener Prüfung einzeln hochladen. Lokale Originaldateien profil.json und "
            "bewerbungen.json nicht hochladen oder durch Exporte ersetzen. "
            "Ein ZIP allein richtet dort kein Projekt ein.\n" + portfolio_guide, encoding="utf-8")
    except Exception:
        # Only this call's newly created directory, never an existing workspace.
        shutil.rmtree(dest)
        raise
    return dest.resolve()


def wizard(input_fn=input, output=print, portfolio=None, route=None, wish=None):
    output("Bewerbungs-Assistent: persönliche Einrichtung")
    output("Benötigt Python ab 3.11. Kein API-Schlüssel, kein Versand, keine Anmeldung durch dieses Programm.")
    name = input_fn("Wie möchtest du im Profil heißen? ").strip()
    roles = [r.strip() for r in input_fn("Welche Zielrollen? Mit Komma trennen: ").split(",") if r.strip()]
    location = input_fn("Wohnort für Unterlagen, nur Ort (freiwillig): ").strip()
    output("1 ChatGPT | 2 Claude | 3 Claude Code | 4 Codex")
    choice = input_fn("Dein Assistent [1]: ").strip() or "1"
    if choice not in {"1", "2", "3", "4"}:
        raise ValueError("Bitte 1, 2, 3 oder 4 wählen.")
    assistant = list(ASSISTANTS)[int(choice)-1]
    default = str(Path.home() / "Bewerbungen" / "Mein-Bewerbungsprojekt")
    destination = input_fn(f"Neuer privater Ordner [{default}]: ").strip() or default
    def yes_no(prompt, default):
        while True:
            answer = input_fn(prompt).strip().lower()
            if not answer:
                return default
            if answer in {"j", "ja", "y", "yes"}:
                return True
            if answer in {"n", "nein", "no"}:
                return False
            output("Bitte antworte mit ja oder nein.")

    if portfolio is None:
        portfolio = yes_no("Möchtest du auch ein persönliches Portfolio erstellen? [J/n]: ", True)
    if portfolio and route is None:
        if yes_no("Besitzt du eine eigene Domain? [j/N]: ", False):
            route = "vorhanden"
        else:
            options = {"1": "onnetwork", "2": "cloudflare", "3": "spaeter"}
            while route is None:
                pick = input_fn("Wie möchtest du starten? 1 Domain bei on:NetworkAgency registrieren, 2 bei Cloudflare registrieren, 3 kostenlose pages.dev-Adresse [3]: ").strip()
                route = options.get(pick or "3")
                if route is None:
                    output("Bitte wähle 1, 2 oder 3.")
    if portfolio and route == "onnetwork" and wish is None:
        while True:
            wish = input_fn("Welche Wunschdomain soll im Bestellformular stehen? (optional, z. B. beispiel.de): ")
            try:
                guide = domain_guide(portfolio, route, wish)
                break
            except ValueError as error:
                output(str(error))
    else:
        guide = domain_guide(portfolio, route, wish)
    output(f"Anlegen: {destination}\nProfil: {name}\nAssistent: {ASSISTANTS[assistant]}\nPortfolio: {'Ja' if portfolio else 'Nein'}")
    if input_fn("Jetzt lokal anlegen? [j/N]: ").strip().lower() not in {"j", "ja", "y", "yes"}:
        output("Abgebrochen. Keine Dateien angelegt.")
        return None
    path = _write_workspace(destination, name, roles, location, assistant, portfolio, route, guide)
    if portfolio:
        output((path / "resources" / "PORTFOLIO.txt").read_text(encoding="utf-8"))
        if route:
            output(guide)
    output(f"Eingerichtet: {path}\nWeiter mit START_HIER.md. Dein Profil enthält noch keine erfundenen Qualifikationen.")
    if input_fn("Möchtest du das persönliche Interview jetzt starten? [J/n]: ").strip().lower() not in {"n", "nein", "no"}:
        from .interview import interview
        interview(Workspace(path), input_fn, output)
    return path
