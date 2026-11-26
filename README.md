# Bewerbungs-Assistent

Ein persönlicher Bewerbungsprozess für Claude und ChatGPT. Ein geführtes Interview klärt deinen Hintergrund, deine Ziele und deine Arbeitsregeln. Daraus entsteht dein eigenes Profil für Stellensuche, Bewertung, Unterlagen und Rückmeldungen.

Die Vorlagen funktionieren in einem privaten ChatGPT- oder Claude-Projekt. Im lokalen Arbeitsordner kannst du Stellen recherchieren, Nachweise zu fertigen PDFs zusammenstellen, Bewerbungsformulare vorbereiten und Rückmeldungen bis zum Gespräch verfolgen. Für die Einrichtung brauchst du keinen API-Schlüssel.

## Schnell starten

**Im Browser:** Erstelle ein privates ChatGPT- oder Claude-Projekt. Kopiere [die Projektanweisung](resources/ASSISTENT.txt) in die Anweisungen und lade [den Interviewleitfaden](resources/INTERVIEW.md) hoch. Schreibe als erste Nachricht `/interview`. Öffnet sich dabei ein Menü, sende „Starte /interview“ als normalen Text.

**Mit lokalem Arbeitsordner:** Installiere bei Bedarf [Node.js ab Version 20 mit npm](https://nodejs.org/) und [Git](https://git-scm.com/downloads). Starte einmal im Terminal:

```sh
npx github:kwinter-onnetworkagency/bewerbungs-assistent#v0.6.0
```

Das persönliche Portfolio ist mit **Ja** voreingestellt. Danach fragt der Wizard, ob du eine eigene Domain besitzt. Du kannst eine vorhandene Domain verbinden, eine neue bei on:NetworkAgency oder Cloudflare registrieren oder mit einer kostenlosen Pages-Adresse starten. [Portfolio einrichten](docs/PORTFOLIO.md)

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
| Stellenbezogenen CV erstellen | `/lebenslauf` | `$lebenslauf` |
| PDF-Paket mit Nachweisen bauen | `/anlagen` | `$anlagen` |
| Formular und Uploads vorbereiten | `/portal` | `$portal` |
| Öffentliche Portfolioseite erstellen | `/portfolio` | `$portfolio` |
| Geschütztes Empfängerportfolio vorbereiten | `/persona` | `$persona` |
| Persönliches Postfach prüfen | `/mail` | `$mail` |
| Kontakt oder Gesprächstermin übernehmen | `/kontakt`, `/termin` | `$kontakt`, `$termin` |
| Wiederkehrende Suche oder Mailprüfung einrichten | `/routine` | `$routine` |

Beispiel für die zweite Nachricht nach dem Interview: „/stellensuche Prüfe die beiden beigefügten Anzeigen anhand meiner Muss-Kriterien.“ [Einrichtung je Assistent](docs/INSTALLATION.md)

## Vom Stellenfund zum Vorstellungsgespräch

Mit `/stellensuche` recherchierst du auch bei Indeed und der Bundesagentur für Arbeit. Mit `/gehalt` vergleichst du den Gehaltsrahmen der konkreten Stelle mit passenden Marktwerten. Nach einer Einladung erstellt `/gespraech` eine Mappe für deine Runde und übt das Gespräch mit dir.

`/dashboard` öffnet die lokale Übersicht mit Aufgaben, Stellenvergleich, Bewerbungsverlauf, Gesprächsmappen und Auswertung. Im Browser kannst du die HTML-Datei aus dem Release öffnen und einen Arbeitsstand von deinem Gerät laden. [Beispiele, Quellen und Bedienung](docs/ARBEITSPLATZ.md)

## Von der Unterlage bis zur Rückmeldung

Für eine konkrete Stellen-ID wählst du belegte Profilfakten, die Sprache des Anschreibens und den passenden Lebenslauf aus. Der Paketplan bestimmt, ob der Arbeitgeber einzelne Anlagen oder eine Gesamt-PDF erhält. Der Assistent prüft Pflichtanlagen, Dateigrößen, Reihenfolge und Seitenformat. Eine neue Fassung lässt sich mit der tatsächlich bestätigten Einreichung verbinden. [Unterlagen](docs/DOKUMENTE.md) · [Anlagenpakete](docs/ANLAGEN.md)

Für ein Onlineformular kannst du die tatsächlich vorhandenen Felder erkunden, Werte zuordnen und geprüfte PDFs im sichtbaren Browser auswählen. Bereits beim Ausfüllen können Daten an den Arbeitgeber übertragen werden. Login, Einwilligungen und der letzte Absende-Schritt liegen bei dir. Für dein Portfolio kannst du eine öffentliche Startseite und eine geschützte Empfängerseite mit freigegebenen Inhalten vorbereiten. [Formularvorbereitung](docs/PORTAL.md) · [Portfolio](docs/PORTFOLIO.md)

Auf macOS lässt sich ein ausgewähltes persönliches Apple-Mail-Konto lesen. Auf anderen Systemen kannst du Originalnachrichten als EML bereitstellen. Empfangsbestätigung, Interview und Absage stehen getrennt im Verlauf. Bestätigte Kontakte und Termine kannst du als vCard und Kalenderdatei übernehmen. [Mail und Routinen](docs/ROUTINEN.md) · [Kontakte und Termine](docs/TERMINE.md)

Die [Funktionsübersicht für Version 0.6.0](docs/FUNKTIONSUMFANG.md) nennt für jede Aufgabe den lokalen Befehl, die Voraussetzungen und den Arbeitsweg im privaten Browserprojekt.

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

Der Python-Kern verwendet die Standardbibliothek ab 3.11. PDF-Prüfung, Browserautomatisierung und PDF-Konvertierung nutzen optionale lokale Werkzeuge. Der Installer und seine Tests benötigen Node.js ab 20.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_public.py
python3 scripts/smoke.py
```

Die CI prüft Linux, Windows und macOS. Eine Anmeldung in fremden ChatGPT-/Claude-Konten oder der echte Versand einer Bewerbung gehören nicht zu diesen Tests. Projektaufbau: [ARCHITECTURE.md](docs/ARCHITECTURE.md).

Lizenz: [MIT](LICENSE).
