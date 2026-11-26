---
name: lebenslauf
description: Einen belegten Lebenslauf in der Sprache der Stelle erstellen.
---

Kläre Stellen-ID, Sprache und die relevanten Fakten-IDs. Lies die Originalanzeige und das freigegebene Profil. Wähle die geeigneten Fakten aus, prüfe jede Übersetzung mit der Person und zeige offene Punkte.

Lokal mit `python start.py lebenslauf --stelle ID` rendern. Die Optionen `--fakt`, `--sprache` und `--pdf` stehen in docs/DOKUMENTE.md. Die konkrete Datei anschließend mit `textpruefung` und `ats-pruefung` kontrollieren. Im Chat einen prüfbaren Textentwurf und die verwendeten Fakten-IDs liefern.

Mit `--tag` und `--max-fakten` kannst du die Auswahl aus belegten Fakten eingrenzen. Für eine neue bereinigte Kopie des selbst erzeugten Dokuments nutze `docx-bereinigen`.
