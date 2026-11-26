"""Unterbrechbares Profilinterview. Antworten bleiben als Nutzerangaben erkennbar."""
import hashlib
from .core import read, write, now, validate_profile, text

QUESTIONS = [
    ("location", "Welcher Wohnort soll in deine Unterlagen? Nur Ort, Suchregion kommt separat.", "text"),
    ("contact", "Welche Kontaktangaben sollen in deine Unterlagen? E-Mail, Telefon, Website/Anschrift nur freiwillig.", "text"),
    ("roles", "Welche Zielrollen interessieren dich? Durch Semikolon trennen.", "list"),
    ("work_model", "Welches Arbeitsmodell passt? Präsenz, hybrid oder remote; gewünschte Bürotage gern ergänzen.", "text"),
    ("mobility", "Sind Umzug, Pendeln oder Dienstreisen möglich? Grenzen nennen, sonst offen lassen.", "text"),
    ("seniority", "Welche Verantwortung suchst du: fachlich, Projekte, Personalführung?", "text"),
    ("salary", "Welches Gehaltsziel oder welche Untergrenze gilt? Währung und Fixgehalt/Gesamtvergütung ausdrücklich nennen.", "text"),
    ("availability", "Ab wann bist du verfügbar, welche Kündigungsfrist oder Arbeitszeit gilt?", "text"),
    ("experience", "Beschreibe deine beruflichen Stationen mit Rolle, Arbeitgeber, Zeitraum und Aufgaben. Jede Station durch Semikolon trennen.", "facts:experience"),
    ("achievements", "Welche konkreten Ergebnisse oder Projekte kannst du belegen? Nur echte Zahlen. Durch Semikolon trennen.", "facts:achievement"),
    ("education", "Welche tatsächlich erworbenen Ausbildungen/Abschlüsse hast du? Keine geplanten Abschlüsse als erworben nennen. Durch Semikolon trennen.", "facts:education"),
    ("certificates", "Welche Zertifikate/Weiterbildungen sind vorhanden? Exakter Titel, Anbieter und Datum. Durch Semikolon trennen.", "facts:certificate"),
    ("skills", "Welche Fähigkeiten und Werkzeuge hast du praktisch eingesetzt? Kontext/Erfahrung nennen. Durch Semikolon trennen.", "facts:skill"),
    ("languages", "Welche Sprachen mit welchen ehrlichen Niveaus? Durch Semikolon trennen.", "facts:language"),
    ("sources", "Welche Lebensläufe/Nachweise willst du für die spätere Prüfung bereitstellen? Lokale Dateinamen nennen, keine Passwörter.", "text"),
    ("industries", "Welche Branchen/Unternehmensarten passen, welche möchtest du ausschließen?", "text"),
    ("must_haves", "Welche Bedingungen sind zwingend, welche Ausschlusskriterien gelten?", "text"),
    ("exceptions", "Welche bewussten Ausnahmen bei Ort, Rolle oder Gehalt würdest du einzeln erlauben?", "text"),
    ("writing", "Wie sollen deine Bewerbungen klingen? Sprache, du/Sie, Länge und gewünschter Ton.", "text"),
    ("attachments", "Welche Unterlagen möchtest du standardmäßig nutzen und welche nur auf Anfrage?", "text"),
    ("search", "Welche Suchregion/Quellen und wie häufig neue Vorschläge?", "text"),
    ("mail", "Welche persönlichen Mailkonten/Ordner möchtest du später selbst verbinden? Was muss im Posteingang bleiben? Keine Zugangsdaten.", "text"),
    ("reports", "Wie oft und in welcher Zeitzone möchtest du Berichte? Auch ohne Änderungen?", "text"),
    ("network_profile", "Möchtest du dein LinkedIn-Profil abgleichen? Welche Sprache und Abschnitte sind dafür freigegeben?", "text"),
    ("known_applications", "Welche bereits beworbenen, besprochenen oder ausgeschlossenen Stellen sind bekannt? Titel, Firma, ID/URL und Beleg nennen.", "text"),
]


def interview(workspace, input_fn=input, output=print):
    file = workspace.path("interview.json")
    state = read(file) if file.exists() else {"answers": {}, "status": "in_bearbeitung"}
    answers = state["answers"]
    output("Persönliches Bewerbungsinterview. Eingabetaste: unbekannt. /pause: später fortsetzen.")
    output("Die Antworten sind deine Angaben, keine unabhängig geprüften Zeugnisse. Keine Zugangsdaten eingeben.")
    for index, (key, question, _) in enumerate(QUESTIONS, 1):
        if key in answers:
            continue
        value = input_fn(f"{index}/{len(QUESTIONS)}: {question}\n> ").strip()
        if value == "/pause":
            output("Interview gesichert. Mit python start.py interview fortsetzen.")
            return False
        if len(value) > 20000 or "\x00" in value:
            raise ValueError("Antwort zu lang oder enthält ein ungültiges Steuerzeichen. Vorherige Antworten bleiben gesichert.")
        with workspace.locked():
            if file.exists() and read(file)["answers"] != answers:
                raise ValueError("Interview wurde in einem anderen Fenster geändert. Neu starten; beide Stände nicht überschreiben.")
            answers[key] = value or None
            state.update(updated_at=now(), status="in_bearbeitung")
            write(file, state)
    output("\nDeine Zusammenfassung:")
    for key, question, _ in QUESTIONS:
        output(question + "\n  " + (answers[key] or "OFFEN"))
    if input_fn("Diese Angaben nach eigener Prüfung als Profil übernehmen? [j/N]: ").strip().lower() not in {"j", "ja", "y", "yes"}:
        output("Interview gespeichert; Profil bleibt unverändert. Antworten bei Bedarf in interview.json korrigieren.")
        return False
    with workspace.locked():
        if file.exists() and read(file)["answers"] != answers:
            raise ValueError("Interview wurde inzwischen geändert. Vor der Übernahme neu starten.")
        profile = workspace.profile()
        # Re-running the interview replaces only its own facts. Imported facts stay intact.
        previous = profile["facts"]
        facts = [f for f in previous if f.get("origin") != "interview"]
        old_interview = {f["id"]: f for f in previous if f.get("origin") == "interview"}
        new_ids = set()
        for key, _, kind in QUESTIONS:
            if kind.startswith("facts:") and answers[key]:
                for value in answers[key].split(";"):
                    if value.strip():
                        fid = f"interview-{key}-" + hashlib.sha256(value.strip().encode()).hexdigest()[:12]
                        if fid in new_ids:
                            continue
                        if any(f["id"] == fid for f in facts):
                            raise ValueError("Fakten-ID belegt. Importierten Fakt vor Übernahme umbenennen: " + fid)
                        new_ids.add(fid)
                        facts.append(old_interview.get(fid) or dict(id=fid, text=text(value, "Profilfakt"),
                            source="Nutzerangabe im geführten Interview", evidence_type="nutzerangabe", kind=kind.split(":")[1], origin="interview", keywords=[]))
        removed = {f["id"] for f in previous} - {f["id"] for f in facts}
        if any(removed.intersection(j.get("draft", {}).get("fact_ids", [])) for j in workspace.jobs() if j.get("draft")):
            raise ValueError("Ein entfallender Profilfakt wird noch in einem Entwurf verwendet. Entwurfzuordnung zuerst prüfen; Profil bleibt erhalten.")
        profile["facts"] = facts
        if answers["location"]:
            profile["location"] = answers["location"]
        if answers["roles"]:
            profile["target_roles"] = [v.strip() for v in answers["roles"].split(";") if v.strip()]
        prefs = dict(profile.get("preferences", {}))
        for key, _, kind in QUESTIONS:
            if not kind.startswith("facts:") and (answers[key] is not None or key not in prefs):
                prefs[key] = answers[key]
        profile["preferences"] = prefs
        profile["interview_reviewed_at"] = now()
        validate_profile(profile)
        write(workspace.path("profil.json"), profile)
        state.update(status="vom_nutzer_geprueft_uebernommen", reviewed_at=now())
        write(file, state)
    output("Profil übernommen. Unbeantwortetes bleibt offen. Qualifikationen bei der Dokumentprüfung gegen Originale prüfen.")
    return True
