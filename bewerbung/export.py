"""Bewusst gewählte Exporte statt ungeprüftem Hochladen des ganzen Ordners."""
import csv
import hashlib
import io
import json
import zipfile
from .core import now, write


def report(workspace):
    jobs = workspace.jobs()
    lines = ["# Bewerbungsübersicht", "", "Stand: " + now(), "",
             "| Unternehmen | Rolle | Status | Score | Letztes Ereignis |", "|---|---|---|---|---|"]
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["ID", "Unternehmen", "Rolle", "Status", "Manueller Score", "URL"])
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    def csv_cell(value):
        s = str(value)
        return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s
    for item in jobs:
        event = item["events"][-1] if item["events"] else None
        last = f'{event["occurred_on"]} (erfasst {event["recorded_at"][:10]})' if event else "Noch kein belegtes Ereignis"
        score = item["score_manual"] if item["score_manual"] is not None else "offen"
        lines.append("| " + " | ".join(cell(v) for v in [item["company"], item["role"], item["status"], score, last]) + " |")
        writer.writerow([csv_cell(v) for v in [item["id"], item["company"], item["role"], item["status"], score, item["url"]]])
    lines += ["", "Statusänderungen erfolgen nur anhand ausdrücklich erfasster Nachweise. Ein Entwurf ist keine Einreichung.", ""]
    md = workspace.path("exports", "BERICHT.md")
    md.write_text("\n".join(lines), encoding="utf-8")
    workspace.path("exports", "bewerbungen.csv").write_text(buf.getvalue(), encoding="utf-8", newline="")
    return md


def chat_bundle(workspace):
    """Four chosen files; source documents stay local. User reviews all exported text."""
    profile = workspace.profile()
    # Sources may contain local paths or private document links. Export facts, not those locations.
    preference_keys = {"location", "contact", "roles", "work_model", "mobility", "seniority", "salary", "availability",
                       "industries", "must_haves", "exceptions", "writing", "attachments", "search", "mail", "reports"}
    public_profile = {k: profile[k] for k in ["schema_version", "name", "target_roles", "location"]}
    public_profile["preferences"] = {k: v for k, v in profile.get("preferences", {}).items() if k in preference_keys}
    public_profile["facts"] = [{"id": f["id"], "text": f["text"], "source":
        "Nutzerangabe im Interview; nicht unabhängig geprüft." if f.get("origin") == "interview" else
        "Quelle vom Nutzer angegeben, Originalquellenort bleibt lokal. Nicht durch das Programm geprüft.",
        "kind": f.get("kind"), "keywords": f.get("keywords", [])} for f in profile["facts"]]
    summary = [{k: j[k] for k in ["id", "company", "role", "url", "reference", "status", "score_manual", "score_reason"]} for j in workspace.jobs()]
    files = {
        "PROFIL.json": json.dumps(public_profile, ensure_ascii=False, indent=2),
        "ARBEITSSTAND.json": json.dumps(summary, ensure_ascii=False, indent=2),
        "PROJEKTANWEISUNG.txt": workspace.path("integration", "PROJEKTANWEISUNG.txt").read_text(encoding="utf-8"),
        "INTERVIEW.md": workspace.path("resources", "INTERVIEW.md").read_text(encoding="utf-8")}
    output = workspace.path("exports", "chat-projekt.zip")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name, value in files.items():
            z.writestr(name, value)
    output.chmod(0o600)
    write(workspace.path("exports", "chat-manifest.json"), {
        "created_at": now(), "files": [{"name": n, "sha256": hashlib.sha256(v.encode()).hexdigest()} for n, v in files.items()],
        "notice": "Enthält dein persönliches Profil. Nur nach eigener Prüfung in dein privates Projekt hochladen. ZIP lokal entpacken und Dateien einzeln hinzufügen."})
    return output
