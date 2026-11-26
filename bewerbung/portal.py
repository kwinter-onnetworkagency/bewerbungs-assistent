"""Lokale Feldzuordnung und kontrollierte Übergabe ans sichtbare Bewerbungsportal."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

from .core import identifier, read, write, url, text


def form_url(value):
    link = url(value)
    parts = urlsplit(link)
    if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Portal und Formularrahmen benötigen HTTPS.")
    return link


def selected_fields(config, workspace):
    personal = config.get("stammdaten", {})
    if not isinstance(personal, dict):
        raise ValueError("Stammdaten als Objekt angeben.")
    facts = None
    fields = []
    for selector, entry in config["felder"].items():
        selector = text(selector, "Bestätigter Feldselektor", 2000)
        key = "explizit"
        if isinstance(entry, str):
            value = entry
        elif isinstance(entry, dict) and set(entry) == {"stammdaten"}:
            name = identifier(entry["stammdaten"])
            value = personal.get(name)
            key = "stammdaten:" + name
        elif isinstance(entry, dict) and set(entry) == {"fakt"}:
            fid = identifier(entry["fakt"])
            if facts is None:
                facts = {fact["id"]: fact["text"] for fact in workspace.profile()["facts"]}
            value = facts.get(fid)
            key = "fakt:" + fid
        else:
            raise ValueError("Je Feldselektor einen Text, einen Stammdatenschlüssel oder eine Fakten-ID angeben.")
        if not isinstance(value, str):
            raise ValueError("Das bestätigte Feld verweist auf einen fehlenden Textwert: " + key)
        fields.append({"selector": selector, "value": value, "key": key})
    return fields


def register(commands):
    p = commands.add_parser("portal", help="Portalprofil anlegen, Felder entdecken oder Formular vorbereiten")
    p.add_argument("id")
    p.add_argument("--sitzungsadresse", action="store_true", help="Vertrauliche Formularadresse verdeckt nur für diesen Lauf eingeben")
    p.add_argument("--rahmen-sitzungsadresse", action="store_true", help="Vertrauliche Rahmenadresse nur für diesen Lauf eingeben")
    p.add_argument("--anmelden", action="store_true", help="Geschützten Browserordner verwenden und persönliches Login abwarten")
    p.add_argument("--modus", choices=("vorlage", "erkunden", "ausfuellen"), default="vorlage")


def run(a, w):
    if a.command != "portal":
        return False
    item = w.job(w.jobs(), a.id)
    folder = w.path("unterlagen", item["id"], "portal")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_path = w.path("unterlagen", item["id"], "portal", "portal.json")
    if a.modus == "vorlage":
        with w.locked():
            if not config_path.exists():
                write(config_path, {"stelle": item["id"], "formular_url": "", "felder": {},
                                    "stammdaten": {}, "rahmen_url": "", "fassung": "", "uploads": {}})
        print(config_path)
        return True
    config = read(config_path)
    if config.get("stelle") != item["id"]:
        raise ValueError("Portalprofil gehört zu einer anderen Stelle.")
    link = form_url(getpass.getpass("Formularadresse für diesen Lauf: ") if a.sitzungsadresse else
                    config.get("formular_url") or item["url"])
    if not isinstance(config["felder"], dict) or not isinstance(config["uploads"], dict):
        raise ValueError("Felder und Uploads müssen Zuordnungen sein.")
    fields = []
    uploads = []
    if a.modus == "ausfuellen":
        fields = selected_fields(config, w)
        if config["uploads"]:
            from .anlagen import checked_upload_files
            files = checked_upload_files(w, item["id"], config["fassung"])
            manifest = w.path("anlagen", "pakete", item["id"], config["fassung"], "manifest.json").read_bytes()
            if "v-" + hashlib.sha256(manifest).hexdigest() != config["fassung"]:
                raise ValueError("Freigegebenes Paketmanifest wurde verändert.")
            hashes = {entry["name"]: entry["sha256"] for entry in json.loads(manifest)["dateien"]}
            for selector, group in config["uploads"].items():
                receipt = None
                names = group
                if isinstance(group, dict):
                    if set(group) != {"dateien", "quittung"}:
                        raise ValueError("Uploadgruppe benötigt dateien und quittung.")
                    receipt = text(group["quittung"], "Quittungsselektor", 2000)
                    names = group["dateien"]
                if not isinstance(names, list) or not names or any(not isinstance(n, str) or n not in files for n in names):
                    raise ValueError("Upload benötigt Dateinamen dieser geprüften Paketfassung.")
                if len(set(names)) != len(names):
                    raise ValueError("Doppelter Dateiname im Uploadfeld.")
                uploads.append({"selector": text(selector, "Uploadselektor", 2000), "receipt": receipt, "files": [
                    {"name": name, "path": str(files[name]), "sha256": hashes[name]}
                    for name in names]})
    runner = Path(__file__).resolve().parents[1] / "resources" / "portal.cjs"
    node = shutil.which("node")
    if not node:
        raise ValueError("Für die Portalvorbereitung Node.js installieren.")
    dest = tempfile.mkdtemp(prefix="lauf-", dir=folder)
    frame = getpass.getpass("Rahmenadresse für diesen Lauf: ") if a.rahmen_sitzungsadresse else config.get("rahmen_url") or ""
    if frame:
        frame = form_url(frame)
    browser_profile = ""
    if a.anmelden:
        browser_profile = str(w.path("unterlagen", item["id"], "portal", "browserprofil"))
        os.makedirs(browser_profile, mode=0o700, exist_ok=True)
    data = {"url": link, "frame": frame, "profile": browser_profile, "fields": fields, "uploads": uploads, "mode": a.modus, "output": dest}
    result = subprocess.run([node, str(runner)], input=json.dumps(data), text=True, cwd=w.root)
    if result.returncode:
        raise ValueError(f"Portalvorbereitung abgebrochen. Feldbericht und Uploadstand vor einem erneuten Versuch prüfen: {dest}")
    print(dest)
    return True
