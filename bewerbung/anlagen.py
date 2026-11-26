"""Private PDF-Quellen und stellenspezifische, inhaltsadressierte Paketfassungen."""
from collections import Counter
from datetime import datetime
from email import policy
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .core import identifier, now, read, text, write

COMMANDS = ("anlage", "anlagen", "anlagenstandard", "anlagenpaket", "paketliste", "paketpruefung", "paketzuordnung")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def poppler(tool, *args):
    binary = shutil.which(tool)
    if not binary:
        raise ValueError(f"Für die PDF-Verarbeitung fehlt {tool}. Poppler lokal installieren und PATH prüfen.")
    result = subprocess.run([binary, *args], capture_output=True, timeout=120,
                            env={**os.environ, "LC_ALL": "C"}, stdin=subprocess.DEVNULL)
    if result.returncode or result.stderr.strip():
        raise ValueError(f"{tool} konnte das PDF nicht fehlerfrei verarbeiten. Originaldatei prüfen.")
    return result.stdout.decode("utf-8", errors="replace")


def pdf_pages(path):
    info = poppler("pdfinfo", "-f", "1", "-l", "2147483647", "-box", path)
    counts = re.findall(r"^Pages:\s+(\d+)\s*$", info, re.M)
    if len(counts) != 1 or re.findall(r"^Encrypted:\s+(\S+)", info, re.M) != ["no"]:
        raise ValueError("Das PDF muss lesbar und unverschlüsselt sein.")
    pages = int(counts[0])
    # Prüfe MediaBox und CropBox jeder Seite, auch bei gedrehten Querformaten.
    for box in ("MediaBox", "CropBox"):
        rows = re.findall(rf"^Page\s+(\d+) {box}:\s+([^\n]+)$", info, re.M)
        if not pages or len(rows) != pages:
            raise ValueError("Die PDF-Seiten lassen sich nicht vollständig prüfen.")
        for page, coords in rows:
            x1, y1, x2, y2 = map(float, coords.split())
            narrow, wide = sorted((x2 - x1, y2 - y1))
            if not (abs(narrow - 595.28) <= 1 and abs(wide - 841.89) <= 1):
                raise ValueError(f"Seite {page} ist nicht DIN A4. Eine separate A4-Druckfassung verwenden.")
    # Auch Inhaltsströme dekodieren. Bildbasierte Nachweise benötigen keinen Textlayer.
    poppler("pdftotext", path, os.devnull)
    return pages


def stored_source(workspace, key):
    folder = workspace.path("anlagen", "inventar", "id-" + identifier(key))
    pdf = workspace.path(folder, "original.pdf")
    meta = read(workspace.path(folder, "quelle.json"))
    if (not isinstance(meta, dict) or not pdf.is_file() or digest(pdf) != meta.get("sha256")
            or key != meta.get("id") or meta.get("bytes") != pdf.stat().st_size
            or type(meta.get("seiten")) is not int or meta["seiten"] <= 0
            or not isinstance(meta.get("titel"), str)):
        raise ValueError("Inventarquelle verändert: " + key)
    return pdf, meta


def add_source(workspace, key, title, source, kind=None):
    if kind is None:
        prefix = re.split("[-_]", identifier(key))[0]
        kind = {"cv": "lebenslauf", "lebenslauf": "lebenslauf", "anschreiben": "anschreiben"}.get(prefix, "nachweis")
    if kind not in ("lebenslauf", "anschreiben", "nachweis"):
        raise ValueError("Unbekannte Dokumentart.")
    key, title = identifier(key), text(title, "Bezeichnung", 300)
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("Bitte eine reguläre PDF-Datei angeben.")
    with workspace.locked():
        catalog = workspace.path("anlagen", "inventar")
        catalog.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = workspace.path(catalog, "id-" + key)
        if target.exists():
            _, meta = stored_source(workspace, key)
            if meta.get("art", "nachweis") != kind or meta["titel"] != title or meta["sha256"] != digest(source):
                raise ValueError("Anlagen-ID belegt. Für eine geänderte Quelle eine neue ID verwenden.")
            return meta
        with tempfile.TemporaryDirectory(dir=catalog) as scratch:
            folder = Path(scratch) / "quelle"
            folder.mkdir(mode=0o700)
            pdf = folder / "original.pdf"
            shutil.copyfile(source, pdf)
            pdf.chmod(0o600)
            meta = dict(id=key, titel=title, art=kind, sha256=digest(pdf), seiten=pdf_pages(pdf),
                        bytes=pdf.stat().st_size)
            write(folder / "quelle.json", meta)
            folder.rename(target)
            return meta


def inventory(workspace):
    catalog = workspace.path("anlagen", "inventar")
    return [stored_source(workspace, entry.name[3:])[1] for entry in sorted(catalog.glob("id-*"))]


def standard_sources(workspace, keys):
    keys = id_list(keys, "Standardnachweise")
    with workspace.locked():
        for key in keys:
            stored_source(workspace, key)
        path = workspace.path("anlagen", "standard.json")
        path.parent.mkdir(mode=0o700, exist_ok=True)
        write(path, keys)


def object_fields(value, allowed, label):
    if not isinstance(value, dict) or value.keys() - set(allowed.split()):
        raise ValueError(f"{label}: Objekt mit den dokumentierten Schlüsseln erforderlich.")


def id_list(value, label):
    if not isinstance(value, list) or len({identifier(x) for x in value}) != len(value):
        raise ValueError(f"{label}: Liste eindeutiger Anlagen-IDs erforderlich.")
    return value


def file_name(name):
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_ -]{0,79}\.pdf", name)
            or re.fullmatch(r"CON|PRN|AUX|NUL|(?:COM|LPT)[0-9]", name[:-4].rstrip(), re.I)):
        raise ValueError("Ungültiger PDF-Dateiname. Buchstaben (A-Z), Ziffern, Leerzeichen, _ oder - verwenden.")
    return name


def limit(record, field, measured):
    if field in record:
        ceiling = record[field]
        if type(ceiling) is not int or ceiling < 1:
            raise ValueError(f"{field} muss eine positive ganze Zahl sein.")
        if measured > ceiling:
            raise ValueError(f"{field} überschritten: {measured} bei einem Limit von {ceiling}.")


def validate_plan(plan):
    object_fields(plan, "pflicht optional weglassen dateien vorgabe externe_originale max_dateien max_bytes_gesamt max_bytes_pro_datei", "Paketplan")
    if "vorgabe" in plan:
        text(plan["vorgabe"], "Arbeitgebervorgabe")
    required = set(id_list(plan.get("pflicht"), "pflicht"))
    optional = set(id_list(plan.get("optional", []), "optional"))
    omitted = plan.get("weglassen", {})
    if not isinstance(omitted, dict) or required & optional or omitted.keys() - optional:
        raise ValueError("Nur optionale Anlagen dürfen begründet entfallen. Pflicht und optional müssen eindeutig sein.")
    for reason in omitted.values():
        text(reason, "Grund der Auslassung")
    groups = plan.get("dateien")
    if not isinstance(groups, list) or not groups:
        raise ValueError("Mindestens eine Ausgabedatei angeben.")
    limit(plan, "max_dateien", len(groups))
    used, names = set(), set()
    for group in groups:
        object_fields(group, "name anlagen max_bytes", "Dateivorgabe")
        name = file_name(group.get("name")).casefold()
        keys = id_list(group.get("anlagen"), "Reihenfolge")
        if not keys or name in names or used.intersection(keys):
            raise ValueError("Jede Gruppe benötigt Anlagen, jede Anlage und jeder Dateiname muss eindeutig sein.")
        used.update(keys)
        names.add(name)
    exceptions = plan.get("externe_originale", {})
    if not isinstance(exceptions, dict) or exceptions.keys() - used:
        raise ValueError("Ausnahmen für externe Originale müssen verwendete Quellen benennen.")
    for reason in exceptions.values():
        text(reason, "Begründung für externes Original")
    if used != required | (optional - omitted.keys()):
        raise ValueError("Dateiauswahl widerspricht Pflichtanlagen, optionalen Anlagen oder dokumentierten Auslassungen.")


def package_versions(workspace, jid):
    parent = workspace.path("anlagen", "pakete", identifier(jid))
    for folder in sorted(parent.glob("v-*")):
        manifest = workspace.path(folder, "manifest.json")
        if not manifest.is_file() or "v-" + digest(manifest) != folder.name:
            raise ValueError("Beschädigte Paketfassung gefunden: " + folder.name)
        data = read(manifest)
        if data.get("schema_version") != 1 or data.get("stelle") != jid:
            raise ValueError("Unbekannte oder falsch zugeordnete Paketfassung: " + folder.name)
        yield folder, data


def build_package(workspace, jid, plan):
    validate_plan(plan)
    with workspace.locked():
        job = workspace.job(workspace.jobs(), jid)
        employer = {field: job.get(field, "") for field in ("company", "role", "url", "reference")}
        default_path = workspace.path("anlagen", "standard.json")
        standard = id_list(read(default_path), "Standardnachweise") if default_path.exists() else []
        missing = set(standard) - set(plan["pflicht"]) - set(plan.get("optional", []))
        if missing:
            raise ValueError("Standardnachweise im Paketplan berücksichtigen: " + ", ".join(sorted(missing)))
        sources = {key: stored_source(workspace, key) for group in plan["dateien"] for key in group["anlagen"]}
        parent = workspace.path("anlagen", "pakete", jid)
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # pdfunite erzeugt auch bei identischen Quellen neue PDF-IDs. Vor dem Neubau abgleichen.
        for previous, candidate in package_versions(workspace, jid):
            if (candidate.get("plan") == plan and candidate.get("standard", []) == standard
                    and candidate.get("arbeitgeber") == employer):
                members = {entry["id"]: {k: entry[k] for k in ("id", "titel", "art", "sha256", "seiten", "bytes") if k in entry}
                           for output in candidate["dateien"] for entry in output["inhalt"]}
                if members == {key: meta for key, (_, meta) in sources.items()}:
                    checked_upload_files(workspace, jid, previous.name)
                    return previous
        with tempfile.TemporaryDirectory(dir=parent) as scratch:
            folder = Path(scratch) / "paket"
            folder.mkdir(mode=0o700)
            outputs = []
            for group in plan["dateien"]:
                paths, entries = [], []
                pages = 0
                for key in group["anlagen"]:
                    source, meta = sources[key]
                    path = Path(scratch) / ("id-" + key + ".pdf")
                    shutil.copyfile(source, path)
                    count = pdf_pages(path)
                    if digest(path) != meta["sha256"] or count != meta["seiten"]:
                        raise ValueError("Quelle beim Zusammenstellen verändert: " + key)
                    if meta.get("art") in ("lebenslauf", "anschreiben"):
                        info = poppler("pdfinfo", path)
                        subject = re.findall(r"^Subject:[ \t]*(.*)$", info, re.M)
                        if subject != [jid]:
                            if (key not in plan.get("externe_originale", {}) or
                                    any(value.strip().startswith("job-") for value in subject)):
                                raise ValueError("PDF-Subject muss zur Stelle passen: " + key)
                    entries.append(dict(meta, von=pages + 1, bis=pages + count))
                    paths.append(path)
                    pages += count
                output = folder / group["name"]
                if len(paths) == 1:
                    shutil.copyfile(paths[0], output)
                else:
                    poppler("pdfunite", *paths, output)
                output.chmod(0o600)
                if pdf_pages(output) != pages:
                    raise ValueError("Seitenzahl der Paketdatei widerspricht dem Inhaltsverzeichnis.")
                size = output.stat().st_size
                limit(plan, "max_bytes_pro_datei", size)
                limit(group, "max_bytes", size)
                outputs.append(dict(name=output.name, bytes=size, seiten=pages,
                                    sha256=digest(output), inhalt=entries))
            limit(plan, "max_bytes_gesamt", sum(row["bytes"] for row in outputs))
            write(folder / "manifest.json", dict(schema_version=1, stelle=jid, erstellt=now(), arbeitgeber=employer,
                                                 standard=standard, plan=plan, dateien=outputs))
            version = "v-" + digest(folder / "manifest.json")
            target = workspace.path(parent, version)
            if target.exists():
                checked_upload_files(workspace, jid, version)
            else:
                folder.rename(target)
            return target


def checked_upload_files(workspace, jid, version):
    """Gibt nur die im unveränderten Manifest erfassten, erneut geprüften PDFs zurück."""
    identifier(jid)
    if not isinstance(version, str) or not re.fullmatch(r"v-[0-9a-f]{64}", version):
        raise ValueError("Ungültige Paketfassung. Den vollständigen Ordnernamen v-… angeben.")
    folder = workspace.path("anlagen", "pakete", jid, version)
    manifest = workspace.path(folder, "manifest.json")
    if digest(manifest) != version[2:]:
        raise ValueError("Manifest dieser Paketfassung wurde verändert.")
    data = read(manifest)
    if data["schema_version"] != 1 or data["stelle"] != jid:
        raise ValueError("Paketfassung oder Stellenzuordnung ungültig.")
    files = {}
    for entry in data["dateien"]:
        name = file_name(entry["name"])
        path = workspace.path(folder, name)
        if (not path.is_file() or digest(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]
                or pdf_pages(path) != entry["seiten"]):
            raise ValueError("Paketdatei fehlt oder wurde verändert: " + name)
        files[name] = path
    if {item.name for item in folder.iterdir()} != set(files) | {"manifest.json"}:
        raise ValueError("Paketordner enthält unerwartete Dateien.")
    return files


def checked_cv_files(workspace, jid, version):
    files = checked_upload_files(workspace, jid, version)
    manifest = read(workspace.path("anlagen", "pakete", jid, version, "manifest.json"))
    return {row["name"]: files[row["name"]] for row in manifest["dateien"]
            if len(row["inhalt"]) == 1 and row["inhalt"][0].get("art") == "lebenslauf"}


def is_application_artifact(workspace, checksum):
    """Ein eigener Anhang, lokaler Text oder Paketnachweis belegt keinen Versand."""
    for base in ("dokumente", "anlagen", "exports", "portfolio"):
        for path in workspace.path(base).rglob("*"):
            if path.is_file() and not path.is_symlink() and digest(workspace.path(path)) == checksum:
                return True
    for job in workspace.jobs():
        # Browser previews and field/upload receipts describe the state before submission.
        portal = workspace.path("unterlagen", job["id"], "portal")
        for pattern in ("lauf-*/*", "portal.json"):
            for path in portal.glob(pattern):
                if path.is_file() and not path.is_symlink() and digest(workspace.path(path)) == checksum:
                    return True
        drafts = [job.get("draft"), *(d.get("draft") for d in job.get("draft_history", []))]
        for draft in filter(None, drafts):
            body = draft["text"]
            for ending in ("", "\n", "\r\n"):
                if hashlib.sha256((body + ending).encode()).hexdigest() == checksum:
                    return True
    return False


def associate(workspace, jid, version, index, reason, *, vorlage=None, vorlagenversion=None, kanal=None):
    reason = text(reason, "Grund der bestätigten Zuordnung")
    with workspace.locked():
        jobs = workspace.jobs()
        events = workspace.job(jobs, jid)["events"]
        if not 1 <= index <= len(events):
            raise ValueError("Ereignisnummer außerhalb der Historie.")
        event = events[index - 1]
        proof = event.get("evidence") or {}
        if event["status"] != "beworben" or not proof.get("file"):
            raise ValueError("Eine Zuordnung benötigt ein belegtes Bewerbungsereignis.")
        path = workspace.path(proof["file"])
        if not path.is_file() or digest(path) != proof.get("sha256"):
            raise ValueError("Der Einreichungsbeleg fehlt oder wurde verändert.")
        if is_application_artifact(workspace, proof["sha256"]):
            raise ValueError("Eigene Unterlagen sind kein Einreichungsbeleg.")
        checked_upload_files(workspace, jid, version)
        manifest = read(workspace.path("anlagen", "pakete", jid, version, "manifest.json"))
        if not manifest.get("erstellt"):
            raise ValueError("Erstellzeitpunkt dieser Paketfassung ist unbelegt.")
        created = datetime.fromisoformat(manifest["erstellt"])
        recorded = datetime.fromisoformat(event["recorded_at"])
        mail_date = event.get("mail", {}).get("mail_at")
        if mail_date:
            # Das Maildatum enthält seinen UTC-Versatz und ist sekundengenau.
            after_submission = created.replace(microsecond=0) > datetime.fromisoformat(mail_date)
        else:
            after_submission = created.astimezone().date().isoformat() > event["occurred_on"]
        if created > recorded or after_submission:
            raise ValueError("Die Fassung entstand nach der belegten Einreichung.")
        attributes = {name: text(value, name, 200) for name, value in
                      (("vorlage", vorlage), ("vorlagenversion", vorlagenversion), ("kanal", kanal)) if value is not None}
        previous = event.get("eingereichtes_paket")
        if previous and (previous["fassung"] != version or any(previous.get(k) != v for k, v in attributes.items())):
            raise ValueError("Diesem Ereignis ist bereits eine andere Fassung zugeordnet.")
        assignment = "nutzerzuordnung"
        original = (event.get("mail") or {}).get("original") or proof
        eml = workspace.path(original["file"])
        if eml.suffix.lower() == ".eml":
            if not eml.is_file() or digest(eml) != original.get("sha256"):
                raise ValueError("Das zugeordnete Mailoriginal fehlt oder wurde verändert.")
            message = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
            attachments = []
            for part in message.iter_attachments():
                if (part.get_filename() or part.get_content_disposition() == "attachment") and not part.is_multipart():
                    data = part.get_payload(decode=True)
                    if data is not None and (part.get_content_type() == "application/pdf" or data.startswith(b"%PDF-")):
                        attachments.append(hashlib.sha256(data).hexdigest())
            if attachments:
                if Counter(attachments) != Counter(row["sha256"] for row in manifest["dateien"]):
                    raise ValueError("PDF-Anhänge der E-Mail weichen vom Paket ab. Einen passenden Einreichungsbeleg prüfen.")
                assignment = "anhang_hash"
        if previous:
            if assignment == "anhang_hash" and previous.get("zuordnung") != assignment:
                previous.update(zuordnung=assignment, hashpruefung=now())
                write(workspace.path("bewerbungen.json"), jobs)
            return
        event["eingereichtes_paket"] = dict(fassung=version, grund=reason, erfasst=now(), zuordnung=assignment, **attributes)
        write(workspace.path("bewerbungen.json"), jobs)


def register(commands):
    add = commands.add_parser("anlage", help="A4-PDF mit stabiler Quellen-ID ins private Inventar übernehmen")
    add.add_argument("id")
    add.add_argument("--titel", required=True)
    add.add_argument("--datei", required=True)
    add.add_argument("--art", choices=["anschreiben", "lebenslauf", "nachweis"])
    commands.add_parser("anlagen", help="Private Inventar-IDs, Titel, Seitenzahlen und Prüfsummen anzeigen")
    standard = commands.add_parser("anlagenstandard", help="Standardnachweise für neue Bewerbungen festlegen")
    choice = standard.add_mutually_exclusive_group(required=True)
    choice.add_argument("--anlage", action="append", help="Inventar-ID, wiederholbar")
    choice.add_argument("--leeren", action="store_true", help="Standardliste ausdrücklich leeren")
    build = commands.add_parser("anlagenpaket", help="Paketplan für eine Stelle als neue PDF-Fassung erzeugen")
    build.add_argument("id")
    build.add_argument("--plan", required=True)
    versions = commands.add_parser("paketliste", help="Paketfassungen und Dateinamen einer Stelle anzeigen")
    versions.add_argument("id")
    check = commands.add_parser("paketpruefung", help="Dateien einer bestehenden Paketfassung erneut prüfen")
    check.add_argument("id")
    check.add_argument("fassung")
    link = commands.add_parser("paketzuordnung", help="Tatsächlich eingereichte Paketfassung einem Beleg zuordnen")
    link.add_argument("id")
    link.add_argument("fassung")
    link.add_argument("--ereignis", type=int, required=True, help="Nummer ab 1 in der Ereignisliste der Stelle")
    link.add_argument("--grund", required=True)
    for field in ("vorlage", "vorlagenversion", "kanal"):
        link.add_argument("--" + field, help="Beim tatsächlichen Versand belegte Angabe")


def run(args, workspace):
    if args.command == "anlage":
        result = add_source(workspace, args.id, args.titel, args.datei, args.art)
    elif args.command == "anlagen":
        result = inventory(workspace)
    elif args.command == "anlagenstandard":
        result = args.anlage or []
        standard_sources(workspace, result)
    elif args.command == "anlagenpaket":
        print(build_package(workspace, args.id, read(args.plan)))
        return
    elif args.command == "paketliste":
        workspace.job(workspace.jobs(), args.id)
        result = [{"fassung": path.name, "dateien": [row["name"] for row in data["dateien"]]}
                  for path, data in package_versions(workspace, args.id)]
    elif args.command == "paketzuordnung":
        associate(workspace, args.id, args.fassung, args.ereignis, args.grund,
                  vorlage=args.vorlage, vorlagenversion=args.vorlagenversion, kanal=args.kanal)
        print("Paketzuordnung zum belegten Ereignis gespeichert.")
        return
    else:
        result = list(checked_upload_files(workspace, args.id, args.fassung))
    print(json.dumps(result, ensure_ascii=False, indent=2))
