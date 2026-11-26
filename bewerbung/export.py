"""Bewusst gewählte Exporte statt ungeprüftem Hochladen des ganzen Ordners."""
from pathlib import Path
from collections import Counter
from datetime import date
from html import escape
import re
from urllib.parse import quote
import csv
import hashlib
import io
import json
import zipfile
from .core import identifier, now, url, write, write_bytes
from .anlagen import digest, file_name, package_versions, stored_source


def report(workspace):
    with workspace.locked():
        return _report(workspace)


def _report(workspace):
    jobs = workspace.jobs()
    lines = ["# Bewerbungsübersicht", "", "Stand: " + now(), "",
             "| Unternehmen | Rolle | Status | Score | Letztes Ereignis |", "|---|---|---|---|---|"]
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["ID", "Unternehmen", "Rolle", "Status", "Manueller Score", "URL"])
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    def csv_cell(value):
        s = str(value)
        return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s
    for item in jobs:
        event = max(item["events"], key=lambda e: (e["occurred_on"], e["recorded_at"])) if item["events"] else None
        last = f'{event["occurred_on"]} (erfasst {event["recorded_at"][:10]})' if event else "Noch kein belegtes Ereignis"
        score = item["score_manual"] if item["score_manual"] is not None else "offen"
        lines.append("| " + " | ".join(cell(v) for v in [item["company"], item["role"], item["status"], score, last]) + " |")
        writer.writerow([csv_cell(v) for v in [item["id"], item["company"], item["role"], item["status"], score, item["url"]]])
    lines += ["", "Statusänderungen erfolgen nur anhand ausdrücklich erfasster Nachweise. Ein Entwurf ist keine Einreichung.", ""]
    md = workspace.path("exports", "BERICHT.md")
    write_bytes(md, "\n".join(lines).encode("utf-8"))
    write_bytes(workspace.path("exports", "bewerbungen.csv"), buf.getvalue().encode("utf-8-sig"))
    dashboard(workspace, jobs)
    return md


def esc(value):
    return escape(str(value), quote=True)


def anchor(label, href):
    return f'<a href="{esc(href)}">{esc(label)}</a>'


def original_link(value):
    try:
        return anchor("Originalanzeige", url(value))
    except ValueError:
        return "Quelle offen"


def local_link(workspace, path, label):
    relative = workspace.path(path).relative_to(workspace.root).as_posix()
    return anchor(label, "../" + quote(relative))


def evidence_file(workspace, entry):
    proof = entry.get("evidence") or {}
    checksum = proof.get("sha256", "")
    name = proof.get("file", "")
    if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
        return None
    # Nur von Workspace.evidence erzeugte Nachweispfade als Dokumentlinks freigeben.
    if not isinstance(name, str) or not re.fullmatch(r"belege/" + checksum + r"\.(?:eml|pdf|png|jpe?g|json|txt|md)", name.replace("\\", "/")):
        return None
    try:
        path = workspace.path(*name.replace("\\", "/").split("/"))
        if path.is_file() and digest(path) == checksum:
            return path
    except (OSError, ValueError):
        pass
    return None


def packet_sections(workspace, job):
    sections, versions = [], set()
    try:
        for folder, manifest in package_versions(workspace, job["id"]):
            sections.append(f'<article><h3>{esc(folder.name)}</h3>')
            plan = manifest["plan"]
            if plan.get("vorgabe"):
                sections.append(f'<p>{esc(plan["vorgabe"])}</p>')
            sections.append(local_link(workspace, folder / "manifest.json", "Paketmanifest"))
            valid = True
            for row in manifest["dateien"]:
                try:
                    path = workspace.path(folder, file_name(row["name"]))
                    if not path.is_file() or digest(path) != row["sha256"]:
                        raise ValueError("Geänderte Paketdatei")
                    label = local_link(workspace, path, row["name"])
                except (OSError, ValueError):
                    valid = False
                    label = esc(row["name"]) + " (Datei fehlt oder ist verändert)"
                sections.append(f'<h4>{label}</h4><p>{int(row["seiten"])} Seiten · {int(row["bytes"])} Byte</p><ol>')
                for member in row["inhalt"]:
                    title = esc(member["titel"])
                    try:
                        source, meta = stored_source(workspace, member["id"])
                        if meta["sha256"] == member["sha256"]:
                            title = local_link(workspace, source, member["titel"])
                    except (OSError, ValueError):
                        pass
                    sections.append(f'<li>{title} · S. {int(member["von"])} bis {int(member["bis"])}</li>')
                sections.append("</ol>")
            for key, reason in plan.get("weglassen", {}).items():
                sections.append(f'<p>Ausgelassen: {esc(key)} · {esc(reason)}</p>')
            sections.append("</article>")
            if valid:
                versions.add(folder.name)
    except (OSError, ValueError):
        sections.append("<p>Eine Paketfassung ist beschädigt oder nicht zugänglich. Paketprüfung erforderlich.</p>")
    return "".join(sections), versions


def note_section(workspace, notes):
    items = []
    for note in notes:
        item = f'<article><h3>{esc(note["title"])}</h3><p class="copy">{esc(note["content"])}</p>'
        for source in note.get("sources", []):
            try:
                item += anchor(source, url(source))
            except ValueError:
                continue
        proof = evidence_file(workspace, note)
        if proof:
            item += local_link(workspace, proof, "Quellbeleg öffnen")
        items.append(item + "</article>")
    return "".join(items)


def report_pages(workspace, jobs, template):
    css = template.split("<style>", 1)[1].split("</style>", 1)[0]
    navigation = " ".join(anchor(label, filename) for filename, label in (
        ("Dashboard.html", "Dashboard"), ("Screening.html", "Screening"), ("Pakete.html", "Paketübersicht"),
        ("Kohorten.html", "Kohorten")))
    def page(filename, title, body):
        markup = (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" '
                  f'content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">'
                  f'<title>{esc(title)}</title><style>{css}</style></head><body>'
                  f'<aside><div class="brand">Bewerbungsassistent</div><nav aria-label="Berichte">{navigation}</nav></aside>'
                  f'<main><header><strong>Mein Arbeitsstand</strong></header><h1>{esc(title)}</h1>{body}</main></body></html>')
        write_bytes(workspace.path("exports", filename), markup.encode("utf-8"))

    screening, packages, cohorts = [], [], {}
    today = date.today()
    for job in jobs:
        jid = identifier(job["id"])
        filename = "Stelle-" + jid + ".html"
        title = job["company"] + " · " + job["role"]
        job_link = anchor(title, filename)
        heading = f'<p>{esc(job["status"])} · {esc(job.get("reference") or jid)} · {original_link(job["url"])}</p>'
        score = job.get("score_manual")
        fit = f'<p>Score: {esc(score) if score is not None else "offen"} · {esc(job.get("score_reason") or "")}</p>'
        latest = {(n["kind"], n["title"]): n for n in job.get("notes", [])}
        screen = note_section(workspace, (n for (kind, _), n in latest.items() if kind == "screening"))
        screening.append(f'<article><h2>{job_link}</h2>{heading}{fit}{screen}</article>')
        packet, valid_versions = packet_sections(workspace, job)
        timeline, receipts, submissions = [], [], []
        for number, event in enumerate(job["events"], 1):
            proof = evidence_file(workspace, event)
            original = local_link(workspace, proof, "Originalbeleg öffnen") if proof else "Originalbeleg nicht verifiziert"
            kind = event["status"]
            mail = event.get("mail") or {}
            label = "Eingangsbestätigung" if mail and kind == "eingang" else kind
            entry = (f'<article><h3>{esc(event["occurred_on"])} · {esc(label)}</h3><p>Ereignis {number} · '
                     f'Erfasst {esc(event["recorded_at"][:10])}</p><p>{esc(event["note"])}</p>')
            if mail.get("original"):
                mail_file = evidence_file(workspace, {"evidence": mail["original"]})
                if mail_file and mail_file != proof:
                    entry += "<p>" + local_link(workspace, mail_file, "Nachgetragenes Mailoriginal öffnen") + "</p>"
            if mail:
                entry += f'<p>{esc(mail.get("subject", ""))} · {esc(mail.get("mail_at", ""))}</p>'
            association = event.get("eingereichtes_paket") or {}
            if kind == "beworben":
                version = association.get("fassung")
                assignment = f'Zugeordnete Fassung: {esc(version)}' if version else "Paketfassung offen"
                if version:
                    method = "PDF-Anhangshashes der Originalmail" if association.get("zuordnung") == "anhang_hash" else "persönliche Zuordnung"
                    assignment += " · " + method
                if version and version not in valid_versions:
                    assignment += " · Dateien nicht verifiziert"
                entry += f'<p>{assignment}</p>'
                try:
                    when = date.fromisoformat(event["occurred_on"])
                    if proof and when <= today:
                        submissions.append((when, number, association if version in valid_versions else {}))
                except ValueError:
                    pass
            entry += original + "</article>"
            (receipts if kind == "eingang" and mail else timeline).append(entry)
        if submissions:
            when, _, association = min(submissions, key=lambda row: row[:2])
            group = tuple(association.get(k) or "unbekannt" for k in ("vorlage", "vorlagenversion", "kanal"))
            cohorts.setdefault(group, []).append((job["status"], (today - when).days, job_link))
        detail = heading + fit + f'<details><summary>Erfasste Anzeige</summary><p class="copy">{esc(job["description"])}</p></details>'
        detail += '<h2>Screening</h2>' + (screen or "<p>Keine Einschätzung erfasst.</p>")
        other = note_section(workspace, (n for (kind, _), n in latest.items() if kind != "screening"))
        if other:
            detail += "<h2>Recherche und Vorbereitung</h2>" + other
        revisions = [*job.get("draft_history", []), {"draft": job.get("draft"), "qa": job.get("qa")}]
        for index, revision in enumerate(revisions, 1):
            draft = revision.get("draft")
            if draft:
                qa = revision.get("qa") or {}
                detail += (f'<details><summary>Lokaler Entwurf {index} · {esc(draft["saved_at"][:10])}</summary>'
                           f'<p class="copy">{esc(draft["text"])}</p><p>Inhaltsprüfung: {esc(qa.get("content", "offen"))}</p>'
                           f'<p>Dokumentprüfung: {esc(qa.get("document", "offen"))}</p></details>')
        for path in sorted(workspace.path("dokumente").glob(jid + "-*")):
            if path.is_file() and not path.is_symlink() and path.suffix in {".pdf", ".docx"}:
                detail += "<p>" + local_link(workspace, path, path.name) + "</p>"
        detail += "<h2>Paketfassungen</h2>" + (packet or "<p>Keine Paketfassung erstellt.</p>")
        detail += "<h2>Eingangsbestätigungen</h2>" + ("".join(receipts) or "<p>Keine Bestätigung erfasst.</p>")
        detail += "<h2>Verlauf und Versandzuordnung</h2>" + ("".join(timeline) or "<p>Keine weiteren Ereignisse.</p>")
        page(filename, title, detail)
        if packet or submissions:
            packages.append(f'<h2>{job_link}</h2>' + (packet or "<p>Paketfassung offen.</p>"))
            for when, _, assoc in submissions:
                method = {"anhang_hash": "PDF-Anhangshashes", "nutzerzuordnung": "persönliche Zuordnung"}.get(assoc.get("zuordnung"), "Zuordnungsart offen")
                packages.append(f'<p>Eingereicht am {esc(when)} · {esc(assoc.get("fassung") or "Zuordnung offen")} · {method}</p>')
    groups = []
    for key, records in sorted(cohorts.items()):
        ages = [age for _, age, _ in records]
        statuses = Counter(status for status, _, _ in records)
        counts = " · ".join(esc(k) + ": " + str(v) for k, v in sorted(statuses.items()))
        groups.append(f'<article><h2>{esc(" / ".join(key))}</h2><p>{len(records)} eingereichte Vorgänge · {counts}</p>'
                      f'<p>Seit Einreichung: {min(ages)} bis {max(ages)} Tage.</p><ul>' +
                      "".join(f'<li>{link}</li>' for _, _, link in records) + "</ul></article>")
    included = sum(map(len, cohorts.values()))
    page("Kohorten.html", "Kohorten", f'<p>Stand {today} · {included} von {len(jobs)} Stellen mit datierter und belegter Einreichung. '
         'Je Stelle zählt die erste belegte Einreichung. Gruppen zeigen Vorlage, Version und Versandkanal. '
         'Vorlagen- und Kanalangaben stammen aus der persönlichen Versandzuordnung. Die Zählung verwendet den aktuellen Bewerbungsstatus.</p>' + "".join(groups))
    page("Screening.html", "Screening", "".join(screening) or "<p>Keine Stellen erfasst.</p>")
    page("Pakete.html", "Paketübersicht", "".join(packages) or "<p>Keine Pakete oder Einreichungen erfasst.</p>")


def dashboard(workspace, jobs):
    template = (Path(__file__).resolve().parents[1] / "resources" / "Dashboard.html").read_text(encoding="utf-8")
    report_pages(workspace, jobs, template)
    template = template.replace('id="local-reports" hidden', 'id="local-reports"')
    keys = ("id", "company", "role", "status", "url", "reference", "score_manual", "score_reason", "notes", "checked_at")
    snapshot = []
    docs = [f.name for f in sorted(workspace.path("dokumente").glob("*"))
            if f.is_file() and not f.is_symlink() and f.suffix in {".docx", ".pdf"}]
    for job in jobs:
        row = {k: job[k] for k in keys if k in job}
        row["notes"] = [{**{k: n[k] for k in ("kind", "title", "content", "sources", "due", "done", "recorded_at") if k in n},
                         "evidence": bool(n.get("evidence"))} for n in job.get("notes", [])]
        row["events"] = [{k: e[k] for k in ("status", "occurred_on", "recorded_at", "note") if k in e}
                         for e in job["events"]]
        row["local_detail"] = True
        row["documents"] = [name for name in docs if name.startswith(job["id"] + "-")]
        snapshot.append(row)
    payload = json.dumps(snapshot, ensure_ascii=True).replace("<", r"\u003c")
    before, marker, remainder = template.partition('id="snapshot">')
    empty, end, after = remainder.partition("</script>")
    if not marker or not end or empty.strip() != "[]":
        raise ValueError("Dashboard-Vorlage enthält keinen leeren Datenbereich.")
    write_bytes(workspace.path("exports", "Dashboard.html"), (before + marker + payload + end + after).encode("utf-8"))


def chat_bundle(workspace, *, contact=False, salary=False):
    """Four chosen files; source documents stay local. User reviews all exported text."""
    profile = workspace.profile()
    # Sources may contain local paths or private document links. Export facts, not those locations.
    preference_keys = {"location", "roles", "work_model", "mobility", "seniority", "availability",
                       "industries", "must_haves", "exceptions", "writing", "attachments", "search", "reports"}
    if contact:
        preference_keys.update(("contact", "mail"))
    if salary:
        preference_keys.add("salary")
    public_profile = {k: profile[k] for k in ["schema_version", "name", "target_roles", "location"]}
    public_profile["export_only"] = True
    public_profile["preferences"] = {k: v for k, v in profile.get("preferences", {}).items() if k in preference_keys}
    if profile.get("preferences", {}).get("known_applications"):
        public_profile["known_applications_unverified"] = {
            "text": profile["preferences"]["known_applications"],
            "status": "ungepruefte_nutzerhinweise_keine_belegten_einreichungen"}
    source_labels = {"nutzerangabe": "Nutzerangabe, nicht unabhängig geprüft.",
                     "dokument": "Dokumentquelle vom Nutzer benannt, nicht durch das Programm geprüft.",
                     "unbekannt": "Belegart unbekannt, nicht unabhängig geprüft."}
    public_profile["facts"] = [{"id": f["id"], "text": f["text"], "source": source_labels[f.get("evidence_type", "unbekannt")],
        "evidence_type": f.get("evidence_type", "unbekannt"), "origin": f.get("origin"),
        "kind": f.get("kind"), "keywords": f.get("keywords", [])} for f in profile["facts"]]
    summary = [{k: j[k] for k in ["id", "company", "role", "url", "reference", "status", "score_manual", "score_reason"]} for j in workspace.jobs()]
    files = {
        "PROFIL.json": json.dumps(public_profile, ensure_ascii=False, indent=2),
        "ARBEITSSTAND.json": json.dumps({"export_only": True, "jobs": summary}, ensure_ascii=False, indent=2),
        "PROJEKTANWEISUNG.txt": workspace.path("integration", "PROJEKTANWEISUNG.txt").read_text(encoding="utf-8"),
        "INTERVIEW.md": workspace.path("resources", "INTERVIEW.md").read_text(encoding="utf-8")}
    output = workspace.path("exports", "chat-projekt.zip")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, value in files.items():
            z.writestr(name, value)
    write_bytes(output, buffer.getvalue())
    write(workspace.path("exports", "chat-manifest.json"), {
        "created_at": now(), "files": [{"name": n, "sha256": hashlib.sha256(v.encode()).hexdigest()} for n, v in files.items()],
        "notice": "Enthält dein persönliches Profil. Nur nach eigener Prüfung in dein privates Projekt hochladen. ZIP lokal entpacken und Dateien einzeln hinzufügen."})
    return output
