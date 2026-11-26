"""Explizite Apple-Mail-Arbeit. Es gibt keinen Sende- oder Löschbefehl."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

from .core import now, read, write, write_bytes
from .mailstand import mail_info, mail_items

SCRIPT = Path(__file__).resolve().parents[1] / "resources" / "apple-mail.applescript"


def call(*args):
    if sys.platform != "darwin":
        raise ValueError("Apple Mail benötigt macOS. EML-Import ist auf allen Plattformen verfügbar.")
    p = subprocess.run(["osascript", str(SCRIPT), *args], capture_output=True, timeout=120)
    if p.returncode:
        raise ValueError(p.stderr.decode("utf8", errors="replace").strip())
    return p.stdout


def register(commands):
    p = commands.add_parser("apple-mail")
    sub = p.add_subparsers(dest="operation", required=True)
    for op in ("konten", "ordner", "abruf", "ablegen", "entwurf"):
        s = sub.add_parser(op)
        if op != "konten":
            s.add_argument("--konto", required=True)
        if op in ("abruf", "ablegen", "entwurf"):
            s.add_argument("--ordner", required=True)
        if op == "abruf":
            s.add_argument("--seit", required=True, help="ISO-Zeitpunkt mit Zeitzone")
        if op in ("ablegen", "entwurf"):
            s.add_argument("--message-id", required=True)
        if op == "ablegen":
            s.add_argument("--zielkonto", required=True)
            s.add_argument("--zielordner", required=True)
        if op == "entwurf":
            s.add_argument("--absender", required=True)
            s.add_argument("--textdatei", required=True)


def run(a, w):
    if a.command != "apple-mail":
        return False
    if a.operation in ("konten", "ordner"):
        print(call(a.operation, *([a.konto] if a.operation == "ordner" else [])).decode().strip())
        return True
    src = [a.konto, a.ordner]
    if a.operation == "abruf":
        start = datetime.fromisoformat(a.seit)
        if not start.tzinfo or start > datetime.now(timezone.utc):
            raise ValueError("Abrufbeginn braucht Zeitzone und muss in der Vergangenheit liegen.")
        seconds = int((datetime.now(timezone.utc) - start).total_seconds()) + 1
        root = w.path("belege", "mailabrufe")
        root.mkdir(exist_ok=True, mode=0o700)
        folder = Path(tempfile.mkdtemp(prefix="abruf-", dir=root))
        manifest = dict(konto=a.konto, ordner=a.ordner, seit=a.seit, start=now(), messages=[], errors=[],
                        server_sync_confirmed=False)
        try:
            ids = call("liste", *src, str(seconds)).decode().splitlines()
            for mid in dict.fromkeys(filter(None, ids)):
                dest = folder / (hashlib.sha256(mid.encode()).hexdigest() + ".eml")
                try:
                    write_bytes(dest, call("quelle", *src, mid))
                    data = mail_info(dest)
                    if data["message_id"] != mid.strip("<>"):
                        raise ValueError("Message-ID stimmt nicht überein.")
                    manifest["messages"].append(dict(data, file=dest.name))
                except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                    manifest["errors"].append({"id": mid, "error": str(error)})
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            manifest["errors"].append({"error": str(error)})
        manifest["ende"] = now()
        write(folder / "manifest.json", manifest)
        print(folder / "manifest.json")
        if manifest["errors"]:
            raise ValueError("Teilabdeckung. Einzelne Zugangsfehler stehen im Prüfmanifest.")
    elif a.operation == "entwurf":
        file = Path(a.textdatei).resolve(strict=True)
        if not file.is_file() or not file.read_text(encoding="utf8").strip():
            raise ValueError("Geprüfter Antworttext fehlt.")
        print(call("entwurf", *src, a.message_id, a.absender, str(file)).decode().strip())
    else:
        mid = a.message_id.strip("<>")
        with w.locked():
            row = next((r for r in mail_items(w) if r["message_id"] == mid), None)
            if not row or row["kind"] == "ungeklaert" or row["protected"]:
                raise ValueError("Ablage benötigt eine dokumentierte eindeutige und ungeschützte Nachricht.")
            if src == [a.zielkonto, a.zielordner]:
                raise ValueError("Quelle und Ziel sind identisch.")
            if row.get("account") != a.konto or row["folder"] != a.ordner:
                raise ValueError("Quelle stimmt nicht mit dokumentiertem Konto und Ordner überein.")
            path = w.path("mailablage.json")
            moves = read(path) if path.exists() else {}
            if mid in moves:
                if moves[mid]["target"] != [a.zielkonto, a.zielordner]:
                    raise ValueError("Ablage bereits für ein anderes Ziel bestätigt.")
                if hashlib.sha256(call("quelle", a.zielkonto, a.zielordner, mid)).hexdigest() != row["sha256"]:
                    raise ValueError("Bestätigte Zielnachricht weicht vom Original ab.")
                print("Vorhandene Zielnachricht erneut gelesen.")
                return True
            # Match the raw source acquired through the same adapter before moving.
            target = [a.zielkonto, a.zielordner]
            count = int(call("anzahl", *src, mid))
            if count:
                original = call("quelle", *src, mid)
                if hashlib.sha256(original).hexdigest() != row["sha256"]:
                    raise ValueError("Inhalt der Quellnachricht weicht vom gelesenen Beleg ab.")
                if call("ablage", *src, mid, *target).decode().strip() != mid:
                    raise ValueError("Ablageprüfung fehlgeschlagen.")
            if hashlib.sha256(call("quelle", *target, mid)).hexdigest() != row["sha256"]:
                raise ValueError("Ablageprüfung fehlgeschlagen.")
            moves[mid] = dict(at=now(), source=src, target=[a.zielkonto, a.zielordner])
            write(path, moves)
        print("Ablage anhand derselben Message-ID geprüft.")
    return True
