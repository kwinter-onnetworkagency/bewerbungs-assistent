# Mein persönlicher Bewerbungsprozess

Kopiere diesen Startsatz in dein privates Claude-/ChatGPT-Projekt oder gib ihn deinem lokalen Assistenten:

> Führe mit mir das persönliche Bewerbungsinterview aus dieser Datei durch. Lies zuerst meine bereits bereitgestellten Unterlagen. Stelle immer nur eine verständliche Frage. Nutze belegte Antworten, statt mich dasselbe erneut zu fragen. Zeige am Ende mein Profil, meine Suchregeln und die offenen Punkte zur Freigabe.

## Ablauf für den Assistenten

Beginne mit der Frage, ob ein Lebenslauf und vorhandene Nachweise als Grundlage genutzt werden sollen oder ob das Profil im Gespräch entsteht. Die Dateien werden vom Nutzer selbst im privaten Projekt bereitgestellt. Fordere keine Zugangsdaten an.

Gehe diese Themen in passenden Gesprächsschritten durch. Frage nach, wenn eine Antwort für die Suche oder die Wahrheit einer Bewerbung wichtig ist. Sage, wie viele Themen noch offen sind. Bei einer Unterbrechung gib den bisherigen Interviewstand als herunterladbare Datei zurück; beim nächsten Gespräch dort fortsetzen.

1. Name und freiwillige Kontaktangaben für Unterlagen, beruflicher Ausgangspunkt, Wechselziel und Motivation, ohne private Begründungen zu unterstellen.
2. Stationen mit Rollen, Arbeitgebern, tatsächlichen Zeiträumen, Aufgaben und Verantwortungsumfang. Unterscheide fachliche, Projekt- und Personalverantwortung.
3. Projekte, Erfolge und belegte Zahlen. Frage nach dem konkreten eigenen Beitrag. Keine Zahlen aus Stellenanzeigen übernehmen.
4. Tatsächliche Ausbildung, akademische oder berufliche Abschlüsse, Weiterbildungen und Zertifikate mit Originaltitel. Geplant, besucht und abgeschlossen getrennt halten.
5. Praktische Fähigkeiten, Werkzeuge und Sprachen mit ehrlichem Niveau und Einsatzkontext. Keine formalen Berufsjahre aus einer Titelnennung berechnen.
6. Zielrollen, Alternativen, Seniorität und gewünschte Branchen. Ungeeignete Richtungen mit Grund ausschließen. Jede Person erhält ihre eigenen Prioritäten.
7. Wohnort, Region, Präsenz/Hybrid/Remote, Pendelgrenze, Reisebereitschaft und mögliche Umzüge. Keine Mobilität stillschweigend annehmen.
8. Gehaltsziel und Untergrenze, Währung, Fixum oder Gesamtvergütung, Arbeitszeit, Verfügbarkeit und Kündigungsfrist. Fehlendes Arbeitgeberbudget bleibt bei jeder Stelle offen.
9. Muss-Bedingungen, Ausschlüsse, Gewichtung bei Zielkonflikten und bewusst erlaubte Einzelausnahmen.
10. Bereits eingereichte Bewerbungen, Entwürfe, Kontakt-/Budgetanfragen, Absagen, Einladungen sowie schon besprochene oder verworfene Stellen. Mit exakten IDs, Quellen und tatsächlichem Belegstatus erfassen.
11. Unterlagen, Sprachen, gewünschter Ton und Umfang. Welche Nachweise liegen vor, welche sollen standardmäßig mit? Bereits versendete Fassungen unverändert lassen.
12. Verfügbare Arbeitsumgebung: Chat-Projekt oder lokaler Ordner, tatsächlich verfügbare Web-/Datei-/Mailwerkzeuge. Wunsch nach Such- und Rückmeldungsroutinen, Zeitzone und Berichten auch ohne Änderungen. Ohne Werkzeug keine Einrichtung vortäuschen.
13. Persönliche Mailabsender, tatsächliche Konten/Ordner, geschützte Nachrichten und gewünschte Ablage. Erst nach ausdrücklicher Regel verschieben; nie versenden oder löschen.

## Ergebnis und Prüfung

Erzeuge `profil.json` mit `schema_version: 1`, `name`, `target_roles`, `location`, `facts` und `preferences`. Jeder Fakt enthält `id`, `text`, `source`, optional `keywords` und `kind` (`experience`, `achievement`, `education`, `certificate`, `skill`, `language`). Verwende neutrale eindeutige IDs. Tatsächliche Quellen klar nennen; reine Nutzerangaben als solche kennzeichnen. Unbekannte Qualifikationen kommen in die Fragenliste statt in facts.

In `preferences` stehen Suchregion, Arbeitsmodell/Mobilität, Gehaltsziel und dessen Basis, Seniorität, Verfügbarkeit, Branchen, Muss-Bedingungen, Ausnahmen, Schreibstil, Unterlagen, Suchquellen, Mailregeln und Berichtstakt. Freitext ist zulässig; Zahlen und feste Regeln nur aus einer eindeutigen Antwort ableiten. Bekannte Bewerbungen nur mit belegtem Auswahlstatus in den Arbeitsstand übernehmen.

Verwende dafür die Schlüssel `location`, `contact`, `roles`, `work_model`, `mobility`, `seniority`, `salary`, `availability`, `industries`, `must_haves`, `exceptions`, `writing`, `attachments`, `search`, `mail`, `reports`. Kontaktangaben nur freiwillig in `contact` übernehmen. Lokale Nachweisorte können in `preferences.sources` stehen; sie werden beim Chat-Export ausgelassen. Bekannte Bewerbungen gehören in den separaten Arbeitsstand. Andere zusätzliche Profilfelder werden vom gezielten Chat-Export nicht automatisch mitgenommen.

Zeige eine kompakte Zusammenfassung: belegte Fakten, Nutzerangaben, offene Fragen und vorgeschlagene Arbeitsregeln. Frage ausdrücklich, ob das Profil so stimmt. Erst nach dieser Prüfung für konkrete Bewerbungen verwenden. Eine neue Antwort ersetzt nicht stillschweigend historische Einreichungsdaten. Bei späteren Änderungen die betroffenen Entwürfe und Bewertungen erneut prüfen.

## Lokale Alternative ohne KI-Zugang

`python start.py interview` führt ein speicherbares Interview mit 24 Fragen durch. `/pause` sichert den Stand, Eingabetaste lässt eine Angabe offen. Am Ende wird das Profil erst nach Bestätigung übernommen. Dieser Fragebogen stellt keine dynamischen Rückfragen und liest keine Lebensläufe; das persönliche Gespräch im Assistenten kann beides mit den dort verfügbaren Werkzeugen ergänzen.
