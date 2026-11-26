"""Je Empfänger getrennte Portfolio-Fassungen für statisches Hosting."""
import base64
from html import escape
import hashlib
import json
import re
import shutil
import time
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .core import read, write, write_bytes, url, text, now

RESOURCES = Path(__file__).resolve().parents[1] / "resources"


def selection_args(parser):
    parser.add_argument("--fakt", action="append", required=True, help="Geprüfte Profilfakt-ID, wiederholbar")
    parser.add_argument("--sprache", choices=("de", "en"), default="de")
    parser.add_argument("--link", action="append", nargs=2, metavar=("TITEL", "URL"), default=[])
    parser.add_argument("--titel", help="Freigegebene Überschrift")
    parser.add_argument("--akzent", default="#245c49", help="Akzentfarbe als #RRGGBB")


def register(commands):
    public = commands.add_parser("portfolio", help="Öffentliche Portfolio-Startseite aus gewählten Fakten und Links erzeugen")
    selection_args(public)
    inspect = commands.add_parser("portfolio-pruefen", help="Aktuelle öffentliche Startseite am angegebenen Ziel vergleichen")
    inspect.add_argument("--url", required=True)
    versions = commands.add_parser("persona-liste", help="Empfängerfassungen ohne Zugangsschlüssel anzeigen")
    versions.add_argument("--id", help="Nur Fassungen dieser Stelle anzeigen")
    p = commands.add_parser("persona", help="Geschützte Portfolioseite aus ausdrücklich ausgewählten Fakten erstellen")
    p.add_argument("id")
    p.add_argument("--basis-url", required=True)
    p.add_argument("--anrede", required=True)
    selection_args(p)
    p.add_argument("--fassung")
    p.add_argument("--cv", help="PDF-Dateiname in der geprüften Paketfassung")
    p = commands.add_parser("persona-pruefen", help="Ausgelieferte Bytes mit der lokalen Fassung vergleichen")
    p.add_argument("id")
    p.add_argument("--version", help="Ohne Angabe wird die zuletzt erzeugte Empfängerfassung geprüft")


def web_address(value):
    address = url(value)
    parts = urlsplit(address)
    if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("HTTPS-Adresse des öffentlichen Ziels angeben.")
    return address


def check_live(address, page):
    address = web_address(address)
    for attempt in range(3):
        try:
            with urlopen(Request(address, headers={"Cache-Control": "no-cache"}), timeout=15) as response:
                if response.geturl() != address or response.status != 200:
                    raise ValueError("Endgültige Seitenadresse und HTTP-Status am Ziel prüfen.")
                actual = response.read(len(page) + 1)
            break
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ValueError(f"Ziel meldet HTTP {exc.code}.") from None
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise ValueError("Portfolioziel nicht erreichbar.") from None
        time.sleep(0.4 * (2 ** attempt))
    if actual != page:
        raise ValueError("Ausgelieferte Seite weicht von der lokalen Fassung ab.")
    print(f"Auslieferung bestätigt. HTTP 200, {len(page)} Bytes, SHA-256 {hashlib.sha256(page).hexdigest()}")


def selected_profile(a, w):
    profile = w.profile()
    facts = {f["id"]: f for f in profile["facts"]}
    selected = []
    for fid in dict.fromkeys(a.fakt):
        fact = facts.get(fid)
        if not fact:
            raise ValueError("Unbekannte Fakten-ID.")
        value = fact["text"] if fact.get("language", "de") == a.sprache else fact.get("translations", {}).get(a.sprache)
        if not value:
            raise ValueError("Übersetzung fehlt für " + fid)
        selected.append(text(value, "Fakt"))
    links = [{"title": text(title, "Linktitel", 300), "url": web_address(link)} for title, link in a.link]
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", a.akzent):
        raise ValueError("Akzentfarbe muss #RRGGBB entsprechen.")
    return dict(name=profile["name"], facts=selected, links=links, language=a.sprache, accent=a.akzent,
                title=text(a.titel, "Überschrift", 300) if a.titel else "")


def public_page(w, payload):
    template = (RESOURCES / "Portfolio.html").read_text(encoding="utf8")
    name = escape(payload["name"], quote=False)
    starter = template.replace("__NAME__", name)
    pieces = []
    if payload["title"]:
        pieces.append("<h2>" + escape(payload["title"]) + "</h2>")
    pieces.extend("<p>" + escape(value) + "</p>" for value in payload["facts"])
    if payload["links"]:
        pieces.append("<ul>" + "".join('<li><a rel="noreferrer" href="' + escape(link["url"], quote=True) + '">'
                                        + escape(link["title"]) + "</a></li>" for link in payload["links"]) + "</ul>")
    rendered = starter.replace('lang="de"', 'lang="' + payload["language"] + '"', 1)
    rendered = rendered.replace("#245c49", payload["accent"]).replace("</main>", "\n".join(pieces) + "\n  </main>")
    page = rendered.encode()
    with w.locked():
        folder = w.path("portfolio", "public")
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = w.path("portfolio", "public", "index.html")
        drafts = w.path("portfolio", "entwuerfe")
        drafts.mkdir(exist_ok=True, mode=0o700)
        if target.exists():
            previous = target.read_bytes()
            saved = w.path("portfolio", "entwuerfe", hashlib.sha256(previous).hexdigest() + ".html")
            managed = previous in (starter.encode(), page) or saved.is_file() and saved.read_bytes() == previous
        else:
            managed = True
        draft = w.path("portfolio", "entwuerfe", hashlib.sha256(page).hexdigest() + ".html")
        if draft.exists():
            if draft.read_bytes() != page:
                raise ValueError(f"Der vorhandene Portfolioentwurf wurde bearbeitet. Zuerst separat sichern: {draft}")
        else:
            write_bytes(draft, page)
        if managed:
            write_bytes(target, page)
            print(f"Öffentliche Startseite lokal vorbereitet: {target}")
        else:
            print(f"Die vorhandene Startseite enthält eigene Änderungen. Neuer Entwurf zur Übernahme: {draft}")


def run(a, w):
    if a.command == "portfolio":
        public_page(w, selected_profile(a, w))
        return True
    if a.command == "portfolio-pruefen":
        check_live(a.url, w.path("portfolio", "public", "index.html").read_bytes())
        return True
    if a.command == "persona-liste":
        jobs = w.jobs()
        for job in [w.job(jobs, a.id)] if a.id else jobs:
            folder = w.path("unterlagen", job["id"], "portfolio")
            for path in sorted(folder.glob("*.json")):
                if re.fullmatch(r"[0-9a-f]{32}", path.stem):
                    meta = read(w.path("unterlagen", job["id"], "portfolio", path.name))
                    print(job["id"], job["company"], meta["version"], meta.get("erstellt_am", ""), meta["url"])
        return True
    if a.command not in ("persona", "persona-pruefen"):
        return False
    job = w.job(w.jobs(), a.id)
    private = w.path("unterlagen", a.id, "portfolio")
    if a.command == "persona-pruefen":
        version = a.version
        if not version:
            current = w.path("unterlagen", a.id, "portfolio", "aktuell.json")
            if not current.exists():
                raise ValueError("Aktuelle Fassung fehlt. Vorhandene Fassung mit --version wählen.")
            version = read(current)["version"]
        if not re.fullmatch(r"[0-9a-f]{32}", version):
            raise ValueError("Ungültige Empfängerfassung.")
        meta = read(w.path("unterlagen", a.id, "portfolio", version + ".json"))
        page = w.path("portfolio", "public", "p", version, "index.html").read_bytes()
        if meta["version"] != version or hashlib.sha256(page).hexdigest() != meta["sha256"]:
            raise ValueError("Lokale Empfängerfassung stimmt nicht mit dem privaten Beleg überein.")
        check_live(meta["url"], page)
        return True
    base = web_address(a.basis_url)
    if urlsplit(base).query or urlsplit(base).fragment:
        raise ValueError("Basisadresse ohne Parameter oder Fragment angeben.")
    payload = selected_profile(a, w)
    payload.update(role=job["role"], salutation=text(a.anrede, "Anrede"))
    if bool(a.fassung) != bool(a.cv):
        raise ValueError("CV-Dateiname und Paketfassung gemeinsam angeben.")
    if a.cv:
        from .anlagen import checked_cv_files
        files = checked_cv_files(w, a.id, a.fassung)
        if a.cv not in files:
            raise ValueError("CV fehlt in ausgewählter Fassung.")
        manifest = w.path("anlagen", "pakete", a.id, a.fassung, "manifest.json").read_bytes()
        if "v-" + hashlib.sha256(manifest).hexdigest() != a.fassung:
            raise ValueError("Paketmanifest wurde verändert.")
        expected = next(row["sha256"] for row in json.loads(manifest)["dateien"] if row["name"] == a.cv)
        content = files[a.cv].read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Lebenslauf wurde nach der Paketprüfung verändert.")
        payload["cv"] = {"name": a.cv, "content": base64.b64encode(content).decode()}
    binary = shutil.which("node")
    if not binary:
        raise ValueError("Für ein geschütztes Portfolio wird Node.js benötigt.")
    result = subprocess.run([binary, str(RESOURCES / "persona.cjs")], input=json.dumps(payload).encode(),
                            capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("Portfolio-Verschlüsselung fehlgeschlagen.")
    encrypted = json.loads(result.stdout)
    key = encrypted.pop("key")
    version = uuid4().hex
    dest = w.path("portfolio", "public", "p", version)
    template = (RESOURCES / "Persona.html").read_text(encoding="utf8")
    page = template.replace("__LANG__", a.sprache).replace("__PACKET__", json.dumps(encrypted)).encode()
    with w.locked():
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        dest.mkdir(parents=True, mode=0o700)
        try:
            write_bytes(dest / "index.html", page)
            meta_path = w.path("unterlagen", a.id, "portfolio", version + ".json")
            address = base.rstrip("/") + "/p/" + version + "/"
            write(meta_path, dict(version=version, url=address, key=key, bytes=len(page),
                                  sha256=hashlib.sha256(page).hexdigest(), fact_ids=a.fakt, erstellt_am=now()))
            write(w.path("unterlagen", a.id, "portfolio", "aktuell.json"), {"version": version})
        except Exception:
            w.path("unterlagen", a.id, "portfolio", version + ".json").unlink(missing_ok=True)
            shutil.rmtree(dest)
            raise
    print(f"Lokale Fassung: {dest}. URL nach Veröffentlichung: {address}\nZugangsschlüssel im privaten Beleg: {meta_path}")
    return True
