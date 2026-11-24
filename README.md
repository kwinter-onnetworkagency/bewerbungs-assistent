# Bewerbungs-Assistent

Ein persönlicher Bewerbungsprozess für Claude und ChatGPT. Ein geführtes Interview klärt deinen Hintergrund, deine Ziele und deine Arbeitsregeln. Daraus entsteht dein eigenes Profil für Stellensuche, Bewertung, Unterlagen und Rückmeldungen.

Die Vorlagen funktionieren in einem privaten ChatGPT- oder Claude-Projekt. Für einen lokalen Arbeitsordner gibt es zusätzlich einen Einrichtungsassistenten und kleine Werkzeuge für Nachweise, Dokumente und Tracking. Kein API-Schlüssel nötig.

## Schnell starten

**Du möchtest im Chat arbeiten:** Folge [Installation: ChatGPT oder Claude](docs/INSTALLATION.md#chatgpt-oder-claude-im-browser). Lade das Interview in dein privates Projekt und beginne mit deinem vorhandenen Lebenslauf oder einem Gespräch. Dafür musst du Python nicht installieren.

**Du möchtest einen lokalen Arbeitsordner:** Lade [das Repository als ZIP](https://github.com/kwinter-onnetworkagency/bewerbungs-assistent/archive/refs/heads/main.zip) herunter und entpacke es. Installiere bei Bedarf [Python ab 3.11](https://www.python.org/downloads/). Öffne ein Terminal im entpackten Ordner und starte:

```sh
python3 start.py
```

Unter Windows: `py -3 start.py`. Alternativ stehen `Start.command` für macOS und `Start.bat` für Windows bereit. Falls dein System den Doppelklick blockiert, nutze den Terminalbefehl aus der [Installationsanleitung](docs/INSTALLATION.md).

Der Assistent fragt nach Name, Zielrollen, Ort und gewünschtem Assistenten. Er legt einen neuen privaten Arbeitsordner an. Anschließend führst du dort das persönliche Interview durch:

```sh
python3 start.py interview
```

Das Interview ist mit `/pause` unterbrechbar. Offene Antworten bleiben offen. Das Profil wird erst nach deiner Bestätigung übernommen. Für ein Gespräch mit Rückfragen gibt es [die Interviewvorlage](resources/INTERVIEW.md); der lokale Fragebogen funktioniert auch ohne KI-Zugang.

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
