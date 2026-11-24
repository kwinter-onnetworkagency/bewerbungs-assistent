# Fehlerbehebung

## Python wird nicht gefunden

Installiere Python ab 3.11 regulär von python.org und öffne dein Terminal neu. Unter Windows funktioniert häufig `py -3`, auf macOS/Linux `python3`. Version prüfen, bevor du `start.py` ausführst. Das Projekt installiert keine fremden Pakete oder Python automatisch.

## Zielordner existiert bereits

Die Einrichtung überschreibt absichtlich keinen Ordner. Wähle einen neuen Namen oder öffne eine vorhandene persönliche Installation. Keine bestehende Installation löschen, nur um den Installer erneut auszuführen.

## Kein Arbeitsordner

Wechsle in den vom Installer ausgegebenen persönlichen Ordner. Der öffentliche Download ist die Vorlage, nicht dein Bewerbungsstand. Alternativ gib vor dem Befehl `--ordner "PFAD-ZU-DEINEM-ORDNER"` an.

## Interview unterbrochen

Erneut `python start.py interview` starten. Bereits gespeicherte Antworten bleiben erhalten. Korrekturen kannst du vor der Übernahme in `interview.json` vornehmen. Ein abgelehntes Endergebnis verändert dein Profil nicht.

## Ordner wird bereits bearbeitet

Beende zuerst den anderen Schreibprozess. Wenn sicher kein Werkzeug mehr auf diesen Ordner schreibt und ein früherer Prozess abgebrochen ist, entferne nur den leeren Ordner `.write-lock` in deinem persönlichen Arbeitsordner. Automatische Zeitablauf-Löschung wäre bei langen Bearbeitungen unsicher; deshalb gibt es sie nicht. Nicht während einer laufenden Bearbeitung entfernen.

## DOCX/PDF existiert schon

Weitere DOCX-Fassungen erhalten automatisch eine neue Versionsnummer. Bereits eingereichte Unterlagen unverändert erhalten. Eine vorhandene gleichnamige PDF wird nicht überschrieben. Ohne LibreOffice bleibt die DOCX-Datei nutzbar; PDF kannst du selbst im Textprogramm exportieren.

## Mail oder Websuche nicht verfügbar

Der Installer richtet keine Kontoverbindungen ein. Prüfe deine im Assistenten verfügbaren Werkzeuge und Berechtigungen. Alternativ vollständige Anzeigen/Mails selbst bereitstellen. Ein Zugangsfehler ist keine Absage und kein Beleg für eine geschlossene Stelle.

## Chat vergisst den Stand

Nutze ein privates Projekt mit aktuellen Profil-/Arbeitsstanddateien. Entferne veraltete widersprüchliche Versionen bewusst. Lade nach einer Änderung den neuen Stand hoch. Ein Modellgedächtnis ersetzt keine konkrete Statusdatei und keine Einreichungsbelege.

## Hilfe im öffentlichen Repository

Beschreibe Befehl, Betriebssystem, Python-Version und Fehlermeldung mit neutralen Beispielen. Keine Lebensläufe, Originalmails, Vertragsdaten, Screenshots mit Personendaten oder Zugangsdaten an Issues anhängen. Gib bei Bedarf ein fiktives Minimalbeispiel an.
