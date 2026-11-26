"""Gelesene Originalmails, eindeutige Entscheidungen und lokale Berichtsmanifeste."""
from datetime import datetime, timezone as utc_offset
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import read, write, now, text

ARTEN = ("eingang", "rueckfrage", "kontakt", "termindetail", "antwort", "service",
         "interview", "absage", "angebot", "zurueckgezogen", "beworben")


def timezone(name):
    if name == "UTC":
        return utc_offset.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        raise ValueError("Zeitzone nicht verfügbar. Namen prüfen oder lokal tzdata installieren.") from None


def mail_info(source):
    path = Path(source)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Original als reguläre EML-Datei bis 20 MiB bereitstellen.")
    raw = path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(raw)
    mid = str(message.get("Message-ID", "")).strip().strip("<>")
    if not mid or len(message.get_all("Message-ID", [])) != 1 or any(c.isspace() for c in mid):
        raise ValueError("Keine eindeutige Message-ID.")
    try:
        received = parsedate_to_datetime(str(message["Date"]))
        if received.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError("EML benötigt ein gültiges Maildatum mit Zeitzone.") from None
    body = message.get_body(preferencelist=("plain", "html"))
    if not body or not str(body.get_content()).strip():
        raise ValueError("Nachrichteninhalt fehlt.")
    return {"message_id": mid, "mail_at": received.isoformat(), "subject": str(message.get("Subject", "")),
            "in_reply_to": str(message.get("In-Reply-To", "")), "sha256": hashlib.sha256(raw).hexdigest()}


def mail_items(w):
    rows = []
    assigned = set()
    for job in w.jobs():
        for event in job["events"]:
            if event.get("message_id"):
                assigned.add(event["message_id"])
            if event.get("mail"):
                rows.append(dict(event["mail"], company=job["company"], role=job["role"], reference=job["reference"],
                                 kind=event["status"], reason=event["note"], recorded_at=event["mail"].get("captured_at", event["recorded_at"])))
    pending = w.path("mail-ungeklaert.json")
    if pending.exists():
        rows.extend(row for row in read(pending) if row["message_id"] not in assigned)
    return rows


def capture(w, a):
    source = Path(a.eml)
    data = mail_info(source)
    reason = text(a.grund, "Gelesener Inhalt und Zuordnungsgrund")
    folder = text(a.ablage, "Tatsächlicher Ordner")
    data.update(folder=folder, next_step=a.schritt or "", protected=a.schuetzen, account=getattr(a, "konto", None),
                direction=a.richtung)
    prior = next((r for r in mail_items(w) if r["message_id"] == data["message_id"]), None)
    if prior:
        if prior.get("sha256") != data["sha256"]:
            raise ValueError("Dieselbe Message-ID mit abweichendem Original. Konten und Kopien manuell klären.")
        data["protected"] |= prior["protected"]
        if prior["kind"] != "ungeklaert" and a.art != prior["kind"]:
            raise ValueError("Die Message-ID ist bereits mit einem anderen Ergebnis erfasst.")
    if not a.stelle:
        if a.art != "ungeklaert":
            raise ValueError("Eindeutige Stellen-ID angeben oder als ungeklärt erfassen.")
        with w.locked():
            if any(r["message_id"] == data["message_id"] for r in mail_items(w)):
                return False
            path = w.path("mail-ungeklaert.json")
            rows = read(path) if path.exists() else []
            rows.append(dict(data, kind=a.art, company="", role="", reference="", reason=reason,
                             recorded_at=now(), evidence=w.evidence(source)))
            write(path, rows)
        return True
    if a.art == "ungeklaert":
        raise ValueError("Ungeklärte Nachricht ohne Stellen-ID erfassen.")
    date = datetime.fromisoformat(data["mail_at"]).astimezone(timezone(a.zone)).date().isoformat()
    return w.record(a.stelle, a.art, source, date, reason, data["message_id"], mail=data)


def mailreport(w, a):
    tz = timezone(a.zone)
    stamp = datetime.fromisoformat(now()).astimezone(tz)
    day = stamp.date()
    def dayof(value):
        return datetime.fromisoformat(value).astimezone(tz).date()
    def cell(value):
        return str(value or "–").replace("|", r"\|").replace("\r", " ").replace("\n", " ")
    with w.locked():
        path = w.path("mailberichte.json")
        runs = read(path) if path.exists() else []
        rows = mail_items(w)
        seen = {tuple(key) for run in runs for key in run["reported"]}
        def key(row):
            return [row["message_id"], row["kind"]]
        selected = [row for row in rows if (dayof(row["mail_at"]) == day or dayof(row["recorded_at"]) == day)
                    ] if a.tag else [row for row in rows if tuple(key(row)) not in seen]
        selected.sort(key=lambda r: datetime.fromisoformat(r["mail_at"]))
        heading = "Tagesbericht" if a.tag else "Zwischenbericht"
        lines = [f"# {heading} {stamp:%d.%m.%Y %H:%M} ({a.zone})", "", "Prüfumfang: " + a.abdeckung, "",
                 "| Unternehmen | Stelle / Referenz | Maildatum | Änderung / Ergebnis | Nächster Schritt | Ablage |",
                 "|---|---|---|---|---|---|"]
        moves_path = w.path("mailablage.json")
        moves = read(moves_path) if moves_path.exists() else {}
        for row in selected:
            when = datetime.fromisoformat(row["mail_at"]).astimezone(tz)
            result = row["kind"] + ": " + row["reason"]
            if when.date() != dayof(row["recorded_at"]):
                result += " (nachgetragen " + str(dayof(row["recorded_at"])) + ")"
            values = [row["company"], " ".join(filter(None, [row["role"], row["reference"]])),
                      when.strftime("%d.%m.%Y %H:%M"), result, row["next_step"], "/".join(moves[row["message_id"]]["target"]) if row["message_id"] in moves else row["folder"]]
            lines.append("| " + " | ".join(cell(v) for v in values) + " |")
        if not selected:
            result = "Keine neuen relevanten Rückmeldungen" if a.vollstaendig else "Keine neu erfasste Nachricht im geprüften Ausschnitt"
            lines.append(f"| – | – | – | {result} | – | – |")
        current_tasks = {(j["id"], n["title"]): n for j in w.jobs() for n in j.get("notes", []) if n["kind"] == "aufgabe"}
        tasks = [n["title"] for n in current_tasks.values() if not n.get("done")]
        unresolved = [r["subject"] for r in rows if r["kind"] == "ungeklaert"]
        if a.tag:
            todays = [r for r in selected if dayof(r["mail_at"]) == day]
            counts = {direction: len({r["message_id"] for r in todays if r.get("direction", "arbeitgeber") == direction})
                      for direction in ("arbeitgeber", "eigen", "service")}
            backfills = {r["message_id"] for r in selected if dayof(r["mail_at"]) != day and dayof(r["recorded_at"]) == day}
            moved = [move for move in moves.values() if dayof(move["at"]) == day]
            lines += ["", f"Arbeitgebereingänge heute: {counts['arbeitgeber']}. Eigene Nachrichten: {counts['eigen']}. Servicenachrichten: {counts['service']}. Ältere Nachrichten heute nachgetragen: {len(backfills)}. Heute bestätigte Ablageänderungen: {len(moved)}."]
        if tasks or unresolved:
            lines.extend(["", "## Offene Aufgaben und Zuordnungen", ""] + ["- " + cell(s) for s in tasks + unresolved])
        name = "Mailbericht-" + stamp.strftime("%Y%m%d-%H%M%S-%f") + ".md"
        from .core import write_bytes
        dest = w.path("exports", name)
        write_bytes(dest, ("\n".join(lines) + "\n").encode())
        runs.append({"at": stamp.isoformat(), "type": heading, "coverage": a.abdeckung, "complete": a.vollstaendig,
                     "since": next((r["at"] for r in reversed(runs) if r["complete"]), None),
                     "reported": [tuple(key(r)) for r in selected], "file": name})
        write(path, runs)
        return dest


def register(commands):
    p = commands.add_parser("mail-erfassen", help="Gelesene EML einer Stelle zuordnen oder offenhalten")
    p.add_argument("eml")
    p.add_argument("--stelle")
    p.add_argument("--art", choices=(*ARTEN, "ungeklaert"), required=True)
    p.add_argument("--grund", required=True)
    p.add_argument("--ablage", required=True)
    p.add_argument("--konto", help="Tatsächliches persönliches Quellkonto, für spätere Ablage erforderlich")
    p.add_argument("--richtung", choices=("arbeitgeber", "eigen", "service"), default="arbeitgeber")
    p.add_argument("--schritt")
    p.add_argument("--schuetzen", action="store_true")
    p.add_argument("--zone", default="Europe/Berlin")
    p = commands.add_parser("mailbericht")
    p.add_argument("--tag", action="store_true")
    p.add_argument("--zone", default="Europe/Berlin")
    p.add_argument("--abdeckung", required=True, help="Geprüfte Konten, Ordner, Zeitraum und Zugangsfehler")
    p.add_argument("--vollstaendig", action="store_true", help="Nur für tatsächlich vollständig gelesenen Zeitraum")


def run(a, w):
    if a.command == "mail-erfassen":
        print("Erfasst." if capture(w, a) else "Bereits erfasst.")
    elif a.command == "mailbericht":
        print(mailreport(w, a))
    else:
        return False
    return True
