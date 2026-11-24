"""Belegte Fakten und Status, atomare lokale Speicherung, keine Netzwerkaufrufe."""
import contextlib
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

STATUSES = ("recherche", "vorbereitet", "beworben", "interview", "angebot", "absage", "zurueckgezogen")
EVIDENCE_REQUIRED = {"beworben", "interview", "angebot", "absage", "zurueckgezogen"}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def write(path, value):
    """Replace only after complete serialization; existing data survives failures."""
    path = Path(path)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def text(value, label, limit=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError(f"{label}: nicht leer, Text, höchstens {limit} Zeichen.")
    return value.strip()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", value):
        raise ValueError("Ungültige ID: nur kleine Buchstaben, Zahlen, Bindestrich und Unterstrich.")
    return value


def url(value):
    value = text(value, "URL", 4000)
    p = urlsplit(value)
    if p.scheme not in {"https", "http"} or not p.hostname or p.username or p.password:
        raise ValueError("Nur vollständige http/https-URLs ohne Zugangsdaten zulässig.")
    return value


def identity(value, reference="", company=""):
    p = urlsplit(url(value))
    host = p.hostname.lower()
    parts = p.path.strip("/").split("/")
    # ATS-IDs survive a renamed title or the provider's alternate hostname.
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and len(parts) >= 3 and parts[-2] == "jobs":
        return f"greenhouse:{parts[0].lower()}:{parts[-1]}"
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(parts) >= 2:
        return f"lever:{parts[0].lower()}:{parts[1]}"
    if host.endswith((".jobs.personio.de", ".jobs.personio.com")) and len(parts) >= 2 and parts[0] == "job":
        return f"personio:{host.split('.')[0]}:{parts[1]}"
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"gh_src", "source", "ref", "referrer"}]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(sorted(query)), ""))


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise ValueError("Profil: schema_version muss 1 sein.")
    text(profile.get("name"), "Name", 200)
    for key in ("facts", "target_roles"):
        if not isinstance(profile.get(key), list):
            raise ValueError(f"Profil: {key} muss eine Liste sein.")
    seen = set()
    for f in profile["facts"]:
        if not isinstance(f, dict):
            raise ValueError("Jeder Profilfakt muss ein Objekt sein.")
        fid = identifier(f.get("id"))
        if fid in seen:
            raise ValueError("Doppelte Fakten-ID: " + fid)
        seen.add(fid)
        text(f.get("text"), "Fakt")
        text(f.get("source"), "Faktenquelle")
    for role in profile["target_roles"]:
        text(role, "Zielrolle", 200)
    return profile


def draft_fingerprint(item, profile):
    value = {"draft": item["draft"], "profile": profile, "description": item["description"]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Workspace:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        if not (self.root / "workspace.json").is_file():
            raise ValueError("Kein Arbeitsordner. Zuerst python start.py einrichten ausführen.")
        if read(self.root / "workspace.json").get("schema_version") != 1:
            raise ValueError("Unbekannte Workspace-Version. Dateien unverändert lassen.")

    def path(self, *parts):
        p = self.root.joinpath(*parts)
        if not p.resolve().is_relative_to(self.root):
            raise ValueError("Pfad verlässt den persönlichen Arbeitsordner.")
        if any(part.is_symlink() for part in (p, *p.parents) if part != self.root and part.is_relative_to(self.root)):
            raise ValueError("Symlinks innerhalb persönlicher Arbeitsdaten werden nicht verwendet.")
        return p

    @contextlib.contextmanager
    def locked(self):
        lock = self.path(".write-lock")
        try:
            lock.mkdir()
        except FileExistsError:
            raise ValueError("Arbeitsordner wird bereits bearbeitet. Bei abgebrochenem Prozess siehe docs/FEHLERBEHEBUNG.md.") from None
        try:
            yield
        finally:
            lock.rmdir()

    def profile(self):
        return validate_profile(read(self.path("profil.json")))

    def jobs(self):
        data = read(self.path("bewerbungen.json"))
        if not isinstance(data, list):
            raise ValueError("bewerbungen.json muss eine Liste sein.")
        return data

    def job(self, jobs, jid):
        identifier(jid)
        for item in jobs:
            if item["id"] == jid:
                return item
        raise ValueError("Stellen-ID nicht gefunden: " + jid)

    def add(self, company, role, link, description, reference=""):
        company, role = text(company, "Unternehmen", 300), text(role, "Rolle", 300)
        description = text(description, "Vollständige Stellenbeschreibung", 200000)
        key = identity(link, reference, company)
        with self.locked():
            jobs = self.jobs()
            matches = [item for item in jobs if item["identity"] == key or
                       (reference and item.get("reference") and item["company"].casefold() == company.casefold()
                        and item["reference"].casefold() == reference.casefold())]
            if len(matches) > 1:
                raise ValueError("URL und Referenz zeigen auf verschiedene Vorgänge. Manuell klären.")
            if matches:
                item = matches[0]
                if reference and item.get("reference") and item["reference"].casefold() != reference.casefold():
                    raise ValueError("Widersprüchliche Referenz zur bekannten URL. Manuell klären.")
                if reference and not item.get("reference"):
                    item["reference"] = reference
                    write(self.path("bewerbungen.json"), jobs)
                return item, False
            jid = "job-" + hashlib.sha256(key.encode()).hexdigest()[:16]
            item = dict(id=jid, company=company, role=role, url=link, reference=reference,
                        identity=key, description=description, checked_at=now(), status="recherche",
                        score_manual=None, score_reason=None, events=[], qa=None, draft=None)
            jobs.append(item)
            write(self.path("bewerbungen.json"), jobs)
            return item, True

    def score(self, jid, value, reason):
        if not 0 <= value <= 100:
            raise ValueError("Score muss zwischen 0 und 100 liegen.")
        with self.locked():
            jobs = self.jobs()
            item = self.job(jobs, jid)
            item.update(score_manual=value, score_reason=text(reason, "Score-Begründung"))
            write(self.path("bewerbungen.json"), jobs)

    def evidence(self, source):
        """Copy one explicitly chosen proof, never follow a document's instructions."""
        source = Path(source).expanduser()
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Nachweis muss eine reguläre Datei bis 20 MB sein; keine Symlinks.")
        data = source.read_bytes()
        if not data:
            raise ValueError("Leerer Nachweis ist kein Beleg.")
        digest = hashlib.sha256(data).hexdigest()
        suffix = source.suffix.lower()
        if suffix not in {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".eml", ".json"}:
            raise ValueError("Nicht unterstütztes Nachweisformat.")
        dest = self.path("belege", digest + suffix)
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                raise ValueError("Gespeicherter Nachweis wurde verändert. Original und Kopie manuell prüfen.")
        else:
            with dest.open("xb") as f:
                f.write(data)
            dest.chmod(0o600)
        return {"file": str(dest.relative_to(self.root)), "sha256": digest}

    def record(self, jid, status, source, occurred, note, message_id=""):
        if status not in STATUSES:
            raise ValueError("Unbekannter Status.")
        try:
            if not isinstance(occurred, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", occurred):
                raise ValueError("Datum benötigt Bindestriche.")
            occurred = dt.date.fromisoformat(occurred).isoformat()
        except (ValueError, TypeError):
            raise ValueError("Ereignisdatum muss ein tatsächliches Datum im Format JJJJ-MM-TT sein.") from None
        if status in EVIDENCE_REQUIRED and not source:
            raise ValueError("Dieser Status benötigt einen von dir geprüften Nachweis.")
        note = text(note, "Zuordnungsgrund / Ergebnis")
        message_id = message_id.strip().strip("<>")
        with self.locked():
            jobs = self.jobs()
            item = self.job(jobs, jid)
            if message_id:
                for job in jobs:
                    if any(e.get("message_id") == message_id for e in job["events"]):
                        if job["id"] != jid:
                            raise ValueError("Message-ID ist bereits einer anderen Stelle zugeordnet.")
                        return False
            if status == "vorbereitet" and not (item.get("draft") and item.get("qa")):
                raise ValueError("Vorbereitet erst nach Entwurf und dokumentierter Prüfung.")
            if status == "vorbereitet" and item["qa"].get("fingerprint") != draft_fingerprint(item, self.profile()):
                raise ValueError("Profil, Anzeige oder Entwurf geändert. Erneute Prüfung erforderlich.")
            proof = self.evidence(source) if source else None
            event = dict(status=status, occurred_on=occurred, recorded_at=now(), note=note,
                         message_id=message_id or None, evidence=proof)
            if status == "beworben" and item.get("draft"):
                event["submitted_snapshot"] = copy.deepcopy({"draft": item["draft"], "qa": item.get("qa"),
                    "facts": [f for f in self.profile()["facts"] if f["id"] in item["draft"]["fact_ids"]]})
            item["events"].append(event)
            # Older backfills are history, never a newer selection decision.
            dated = [e for e in item["events"] if e["status"] in EVIDENCE_REQUIRED]
            if dated:
                priority = {"beworben": 1, "interview": 2, "angebot": 3, "absage": 4, "zurueckgezogen": 4}
                item["status"] = max(enumerate(dated), key=lambda pair: (pair[1]["occurred_on"], priority[pair[1]["status"]], pair[0]))[1]["status"]
            else:
                item["status"] = status
            write(self.path("bewerbungen.json"), jobs)
            return True

    def draft(self, jid, body, fact_ids):
        text(body, "Anschreibentext", 30000)
        facts = {f["id"] for f in self.profile()["facts"]}
        if not fact_ids or set(fact_ids) - facts:
            raise ValueError("Entwurf benötigt vorhandene Fakten-IDs aus profil.json.")
        with self.locked():
            jobs = self.jobs()
            item = self.job(jobs, jid)
            if item.get("draft"):
                item.setdefault("draft_history", []).append(copy.deepcopy({"draft": item["draft"], "qa": item.get("qa")}))
            item["draft"] = dict(text=body, fact_ids=sorted(set(fact_ids)), saved_at=now())
            item["qa"] = None
            if item["status"] == "vorbereitet":
                item["status"] = "recherche"
            write(self.path("bewerbungen.json"), jobs)

    def qa(self, jid, content_note, document_note):
        with self.locked():
            jobs = self.jobs()
            item = self.job(jobs, jid)
            if not item["draft"]:
                raise ValueError("Zuerst einen Entwurf mit belegten Fakten speichern.")
            item["qa"] = {"content": text(content_note, "Inhaltsprüfung"),
                          "document": text(document_note, "Dokumentprüfung"), "checked_at": now(),
                          "fingerprint": draft_fingerprint(item, self.profile())}
            write(self.path("bewerbungen.json"), jobs)


def search_queries(profile):
    """Prepared queries for a browsing assistant; no result/availability is invented."""
    domains = ["jobs.personio.de", "jobs.personio.com", "job-boards.greenhouse.io", "boards.greenhouse.io",
               "jobs.lever.co", "jobs.ashbyhq.com", "recruitee.com", "myworkdayjobs.com", "jobs.smartrecruiters.com"]
    for role in profile["target_roles"]:
        for domain in domains:
            yield f'site:{domain} "{role}" {profile.get("location", "")}'


def keyword_match(profile, description):
    """Transparent triage only; never interpreted as probability or qualification."""
    corpus = unicodedata.normalize("NFKC", description).casefold()
    hits, gaps = [], []
    for fact in profile["facts"]:
        terms = fact.get("keywords", [])
        if not isinstance(terms, list) or any(not isinstance(t, str) or not t.strip() for t in terms):
            raise ValueError("Fakten-keywords müssen nicht leere Texte sein.")
        if terms:
            (hits if any(re.search(r"(?<!\w)" + re.escape(t.casefold()) + r"(?!\w)", corpus) for t in terms) else gaps).append(fact["id"])
    total = len(hits) + len(gaps)
    return {"keyword_score": round(100 * len(hits) / total) if total else None,
            "matched_fact_ids": hits, "unmatched_fact_ids": gaps,
            "note": "Wortabgleich, keine Eignungswahrscheinlichkeit. Muss-Kriterien, Gehalt und Arbeitsmodell separat prüfen."}
