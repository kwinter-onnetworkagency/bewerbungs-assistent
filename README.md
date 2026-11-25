# Bewerbungs-Assistent

Ein persönlicher Bewerbungsprozess für Claude und ChatGPT. Ein geführtes Interview klärt deinen Hintergrund, deine Ziele und deine Arbeitsregeln. Daraus entsteht dein eigenes Profil für Stellensuche, Bewertung, Unterlagen und Rückmeldungen.

Die Vorlagen funktionieren in einem privaten ChatGPT- oder Claude-Projekt. Für einen lokalen Arbeitsordner gibt es zusätzlich einen Einrichtungsassistenten und kleine Werkzeuge für Nachweise, Dokumente und Tracking. Kein API-Schlüssel nötig.

## Schnell starten

**Im Browser:** Erstelle ein privates ChatGPT- oder Claude-Projekt. Kopiere [die Projektanweisung](resources/ASSISTENT.txt) in die Anweisungen und lade [den Interviewleitfaden](resources/INTERVIEW.md) hoch. Schreibe als erste Nachricht `/interview`. Öffnet sich dabei ein Menü, sende „Starte /interview“ als normalen Text.

**Mit lokalem Arbeitsordner:** Installiere bei Bedarf [Node.js ab Version 20 mit npm](https://nodejs.org/) und [Git](https://git-scm.com/downloads). Starte einmal im Terminal:

```sh
npx github:kwinter-onnetworkagency/bewerbungs-assistent#v0.3.0
```

Wähle deinen Assistenten, gib deinen Namen ein und wähle einen neuen privaten Ordner. Der Dialog zeigt dir, wie du dort weitermachst. Für Einrichtung und Gespräch genügt Node.js. Die optionalen lokalen Dokument- und Trackingwerkzeuge nutzen Python ab 3.11.

| Was möchtest du tun? | Claude Code oder Nachricht im Chat-Projekt | Codex-Skill |
|---|---|---|
| Persönliches Profil aufbauen | `/interview` | `$interview` |
| Passende Stellen prüfen | `/stellensuche` | `$stellensuche` |
| Anschreiben entwerfen | `/anschreiben` | `$anschreiben` |
| Rückmeldung zuordnen | `/rueckmeldung` | `$rueckmeldung` |
| Gehaltsband und Marktwerte recherchieren | `/gehalt` | `$gehalt` |
| Vorstellungsgespräch vorbereiten und üben | `/gespraech` | `$gespraech` |
| Persönliche Übersicht öffnen | `/dashboard` | `$dashboard` |
| Bewerbungsstand ansehen | `/bericht` | `$bericht` |

Beispiel für die zweite Nachricht nach dem Interview: „/stellensuche Prüfe die beiden beigefügten Anzeigen anhand meiner Muss-Kriterien.“ [Einrichtung je Assistent](docs/INSTALLATION.md)

## Vom Stellenfund zum Vorstellungsgespräch

Mit `/stellensuche` recherchierst du auch bei Indeed und der Bundesagentur für Arbeit. Mit `/gehalt` vergleichst du den Gehaltsrahmen der konkreten Stelle mit passenden Marktwerten. Nach einer Einladung erstellt `/gespraech` eine Mappe für deine Runde und übt das Gespräch mit dir.

`/dashboard` öffnet die lokale Übersicht mit Aufgaben, Stellenvergleich, Bewerbungsverlauf, Gesprächsmappen und Auswertung. Im Browser kannst du die HTML-Datei aus dem Release öffnen und einen Arbeitsstand von deinem Gerät laden. [Beispiele, Quellen und Bedienung](docs/ARBEITSPLATZ.md)

## Was du damit machen kannst

| Aufgabe | Unterstützung |
|---|---|
| Eigenes Profil aufbauen | Stationen, Nachweise, Fähigkeiten, Sprachen, Ziele, Gehalt, Mobilität und Verfügbarkeit im Interview klären |
| Den Prozess anpassen | Branchen, Ausschlüsse, Einzelausnahmen, Schreibstil, Unterlagen, Mailablage und Berichtstakt festlegen |
| Stellen recherchieren | Arbeitsanweisungen für aktuelle offizielle Anzeigen und neun ATS-Domains; vorbereitete Suchanfragen |
| Stellen erfassen | Vollständige Anzeigentexte, Quelle und Referenz speichern; bekannte ATS-IDs deduplizieren |
| Bewerten | Manuelle Scores mit Begründung; erklärbarer Wortabgleich als ergänzende Suchhilfe |
| Unterlagen vorbereiten | Faktenbezogene Anschreibenentwürfe, einfache A4-DOCX-Dateien, PDF optional über lokal installiertes LibreOffice |
| Bewerbungen nachhalten | Tatsächliches Ereignisdatum, Erfassungsdatum, Beleg-Hash und Message-ID; historische Absagen erhalten |
| Arbeitsstand mitnehmen | Markdown-Bericht, CSV-Tabelle und gezielter Export für dein privates Chat-Projekt |

Recherche, individuelle Textarbeit und dynamische Rückfragen übernimmt dein Assistent mit seinen tatsächlich verfügbaren Werkzeugen. Das lokale Programm ruft keine KI-API auf und durchsucht nicht selbst das Web. Mail-/Browserzugriff und wiederkehrende Routinen benötigen deine eigenen Verbindungen und Einstellungen. Die mitgelieferten Vorlagen allein richten sie nicht ein.

Das Werkzeug versendet keine Mail, reicht keine Bewerbung ein, beantwortet keine Captchas und bestätigt keine Termine. Du prüfst Fakten, Dokumente und den letzten Absende-Schritt selbst. Eine Quellenangabe oder ein gespeicherter Beleg ist noch keine automatisch geprüfte Wahrheit.

## Deine Daten

Der öffentliche Quellcode enthält keine echten Bewerbungen oder Kandidatenprofile. Persönliche Arbeitsordner werden außerhalb von Git-Repositories angelegt. Originalnachweise und E-Mails bleiben lokal, soweit du sie nicht selbst in einen Dienst hochlädst.

Ein Chat-Export enthält dein persönliches Profil und ist eine Ansicht, kein Ersatz für deine lokalen Originaldateien. Prüfe die vier Dateien, entpacke das ZIP lokal und lade sie einzeln in dein **privates** Projekt. Der Export hängt keine Originalbelege an; Texte und Stellenlinks können trotzdem persönliche Informationen enthalten. Ein lokaler Ordner ist nicht automatisch verschlüsselt.

- [Installationsanleitung und Einrichtung je Assistent](docs/INSTALLATION.md)
- [Persönliches Interview](resources/INTERVIEW.md)
- [Bewerbungsablauf und Befehle](docs/WORKFLOW.md)
- [Routinen und optionale Verbindungen](docs/ROUTINEN.md)
- [Fehlerbehebung](docs/FEHLERBEHEBUNG.md)
- [Datenschutz und Beitragen](CONTRIBUTING.md)

## Entwicklung

Python ab 3.11, nur Standardbibliothek. Keine Paketinstallation nötig.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
python3 scripts/smoke.py
```

Die CI prüft Linux, Windows und macOS. Eine Anmeldung in fremden ChatGPT-/Claude-Konten oder der echte Versand einer Bewerbung gehören nicht zu diesen Tests. Projektaufbau: [ARCHITECTURE.md](docs/ARCHITECTURE.md).

Lizenz: [MIT](LICENSE).
