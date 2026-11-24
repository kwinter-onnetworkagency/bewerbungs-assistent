# Installation

Du kannst mit einem Chat-Projekt beginnen oder einen lokalen Arbeitsordner einrichten. Jede Person verwendet ihr eigenes Profil und eigene Konten.

## ChatGPT oder Claude im Browser

Dieser Weg braucht keine lokale Installation und keinen API-Schlüssel.

1. Lade das Repository als ZIP herunter und entpacke es. Öffne den Ordner `resources`.
2. Erstelle in deinem eigenen ChatGPT- oder Claude-Konto ein **privates** Projekt, etwa „Meine Bewerbungen“. Teile dieses Projekt nicht mit der Lerngruppe: Hier liegen später deine eigenen Unterlagen.
3. Übernimm den Text aus `ASSISTENT.txt` in die Projektanweisungen. Lade `INTERVIEW.md` als Projektdatei hoch. Wenn dein Konto keine Projekte anbietet, kannst du beide Texte am Anfang eines privaten Chats bereitstellen; prüfe dann den Kontext bei jedem neuen Chat erneut.
4. Schreibe: „Führe mit mir das persönliche Bewerbungsinterview durch. Stelle jeweils eine Frage. Nutze meinen Lebenslauf als Grundlage, soweit ich ihn bereitstelle. Zeige mir am Ende Profil und Arbeitsregeln zur Prüfung.“
5. Lade nur Unterlagen hoch, die der Dienst verarbeiten soll. Zugangsdaten und vertrauliche Unterlagen Dritter gehören nicht dazu.
6. Prüfe das erzeugte `profil.json`, insbesondere Abschlüsse, Zeiträume, Fähigkeiten, Gehaltsbasis und Mobilität. Speichere eine lokale Kopie. Lass den Assistenten Unbekanntes als offene Frage führen.
7. Verwende anschließend die Aufgaben aus `STARTPROMPTS.md`. Ein reines Chat-Projekt kann seinen eigenen Gesprächsstand als Datei zurückgeben. Wenn du bereits eine lokale Installation hast, übernimm nur einzelne geprüfte Änderungen über deren Befehle. Die absichtlich gekürzten Exportansichten dürfen lokale Originaldateien nicht ersetzen. Ein Chat hat keinen automatischen Schreibzugriff auf deinen lokalen Ordner.

Wenn du die lokale Einrichtung benutzt hast, erzeugt `python start.py chat-export` vier Dateien in einem ZIP: `PROFIL.json`, `ARBEITSSTAND.json`, `PROJEKTANWEISUNG.txt`, `INTERVIEW.md`. Entpacke sie, lies sie gegen und füge sie einzeln deinem privaten Projekt hinzu. Ersetze veraltete Arbeitsstände bewusst; lasse keine widersprüchlichen Profilversionen im Projekt.

Datei-, Projekt- und Werkzeugverfügbarkeit hängen von deinem Tarif und den Einstellungen deines Kontos ab. Der Installer prüft deinen Tarif nicht und meldet keine erfolgreiche Verbindung zu einem Dienst.

## Lokaler Einrichtungsassistent

### Voraussetzungen

Python 3.11 oder neuer. Installation: [python.org](https://www.python.org/downloads/). Für das Grundprogramm brauchst du weder Git noch Zusatzpakete. Falls du PDF-Dateien automatisch aus DOCX erstellen möchtest, installiere zusätzlich [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/). Du kannst DOCX auch selbst in Word öffnen und als PDF exportieren.

### macOS

Lade das ZIP von GitHub herunter und entpacke es. Öffne Terminal, wechsle in den entpackten Ordner und starte:

```sh
python3 --version
python3 start.py
```

`Start.command` führt denselben lokalen Befehl aus. Ein aus dem Internet heruntergeladenes Skript kann vom System blockiert werden; der Terminalweg bleibt eine Alternative. Es wird nichts mit Administratorrechten installiert.

### Windows

Installiere Python mit Python Launcher. Öffne PowerShell im entpackten Ordner:

```powershell
py -3 --version
py -3 start.py
```

Alternativ `Start.bat` öffnen. Wenn `py` nicht gefunden wird, probiere `python start.py` nach einer regulären Python-Installation. Ein Klick auf „ausführen“ bei einer Betriebssystemwarnung ersetzt nicht die Prüfung des heruntergeladenen Quellcodes.

### Linux

```sh
python3 --version
python3 start.py
```

### Was abgefragt wird

Name, gewünschte Rollen, Region/Arbeitsmodell, Assistent und Zielordner. Vorgabe ist ein eigener Ordner unter `Bewerbungen` in deinem Benutzerverzeichnis. Ein vorhandener Ordner wird nicht überschrieben. Ziele innerhalb eines Git-Repositories werden abgewiesen.

Nach der Einrichtung wechselst du in deinen **neuen privaten Ordner**, nicht zurück in das heruntergeladene Repository. Dort:

```sh
python3 start.py interview
python3 start.py pruefen
```

Unter Windows jeweils `py -3` anstelle von `python3`. Das Interview fragt unter anderem Ausbildung, Erfahrung, Zielrollen, Gehaltsbasis, Mobilität, Unterlagen und Mailregeln ab. Mit `/pause` fortsetzen, mit leerer Antwort einen Punkt offen lassen. Nach der Zusammenfassung entscheidest du, ob die Angaben übernommen werden. Mit `resources/INTERVIEW.md` kann dein KI-Assistent dynamisch nachfragen und bereitgestellte Nachweise einbeziehen.

## Claude Code

Wähle bei der Einrichtung „Claude Code“. Öffne deinen persönlichen Arbeitsordner in deinem bereits eingerichteten Claude Code. Der Installer hat dort eine `CLAUDE.md` mit den Bewerbungsregeln angelegt, ohne globale Einstellungen zu verändern.

Erster Auftrag: „Lies CLAUDE.md und resources/INTERVIEW.md. Führe mit mir das persönliche Bewerbungsinterview durch und prüfe profil.json.“

Installation, Anmeldung und Tarif von Claude Code richtest du selbst nach der offiziellen Dokumentation ein. Dieses Projekt startet keinen kostenpflichtigen API-Aufruf.

## Codex

Wähle „Codex“. Öffne deinen persönlichen Arbeitsordner in der von dir genutzten Codex-Oberfläche. Dort liegt die erzeugte `AGENTS.md`. Lass Codex Interview und Profil prüfen, bevor du konkrete Bewerbungsunterlagen erstellst.

Der Einrichtungsassistent installiert weder Codex noch Kontoverbindungen oder Automationen. In einem reinen ChatGPT-Projekt verwendest du stattdessen den Abschnitt oben; eine lokale `AGENTS.md` wird dort nicht automatisch vom Rechner gelesen.

## Aktualisieren und sichern

Die persönliche Installation enthält eine Kopie des Werkzeugs. Neue GitHub-Versionen ändern deinen Arbeitsordner nicht automatisch. Sichere den ganzen persönlichen Ordner an einem privaten Ort, bevor du Werkzeugdateien aktualisierst. Tausche nur `start.py`, `bewerbung`, `resources` und `docs` gegen die neue Version aus. `profil.json`, `interview.json`, `bewerbungen.json`, Belege und Unterlagen erhalten. Lies vor einem Versionssprung die Release-Hinweise.

## Offizielle Quellen

Quellenstand 24.11.2026. Bedienoberflächen und Tarife können sich ändern:

- [Projects in ChatGPT](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)
- [ChatGPT: Projects and chats, lokale und Chat-Projekte](https://learn.chatgpt.com/docs/projects)
- [Claude: What are projects?](https://support.claude.com/en/articles/9517075-what-are-projects)
- [Claude Code: Projektanweisungen und Memory](https://code.claude.com/docs/en/memory)
- [Codex: AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
