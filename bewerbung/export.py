"""Bewusst gewählte Exporte statt ungeprüftem Hochladen des ganzen Ordners."""
import csv
import hashlib
import io
import json
import zipfile
from .core import now, write, write_bytes


def report(workspace):
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
    return md


def chat_bundle(workspace):
    """Four chosen files; source documents stay local. User reviews all exported text."""
    profile = workspace.profile()
    # Sources may contain local paths or private document links. Export facts, not those locations.
    preference_keys = {"location", "contact", "roles", "work_model", "mobility", "seniority", "salary", "availability",
                       "industries", "must_haves", "exceptions", "writing", "attachments", "search", "mail", "reports"}
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
