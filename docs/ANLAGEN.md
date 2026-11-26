# Anlagen pro Stelle zusammenstellen

Du kannst aus demselben privaten Inventar für jede Stelle die geforderten Dokumente zusammenstellen. Für ein Portal mit zwei Uploadfeldern erzeugst du zwei PDFs. Verlangt ein Arbeitgeber eine Gesamtbewerbung, fasst du die Dokumente in der gewünschten Reihenfolge in einer PDF zusammen.

## Quellen aufnehmen

Lege zuerst die fertigen PDFs bereit. Verwende Originaltitel und nimm die fachliche Zuordnung zum Lebenslauf oder zur Anzeige selbst vor. Die PDF-Prüfung benötigt die lokalen Poppler-Werkzeuge `pdfinfo` und `pdftotext`. Mehrere Quellen in einer Datei benötigen zusätzlich `pdfunite`. Prüfe die Installation mit `pdfinfo -v`, `pdftotext -v` und `pdfunite -v`.

Führe die Befehle im eingerichteten privaten Arbeitsordner aus. Eine ID bezeichnet genau eine Quellfassung. Für überarbeitete Unterlagen vergibst du eine neue ID.

```sh
python start.py anlage anschreiben --titel "Anschreiben zur Stelle" --datei "Anschreiben.pdf"
python start.py anlage cv --titel "Lebenslauf" --datei "Lebenslauf.pdf"
python start.py anlage kurs --titel "Kursnachweis" --datei "Kurs.pdf"
python start.py anlagen
```

Der Assistent kopiert jede Datei, liest die Seiten und speichert Titel, Größe, Seitenzahl und SHA-256-Prüfsumme. Er prüft Papierformat und sichtbaren Seitenbereich aller Seiten auf DIN A4 im Hoch- oder Querformat. Liegt ein Beleg in einem anderen Format vor, bewahre das Original auf und exportiere separat eine proportionale A4-Druckfassung. Verwende dafür eine eigene Quellen-ID.

Kennzeichne Lebensläufe und Anschreiben bei der Aufnahme mit `--art lebenslauf` bzw. `--art anschreiben`. Bei IDs mit dem Präfix `cv`, `lebenslauf` oder `anschreiben` erkennt das Programm die Art auch automatisch. Eigene Dokumente benötigen die Stellen-ID im PDF-Feld „Betreff“ (Subject). Bei einem extern erstellten Original ohne Stellen-ID kannst du im Paketplan `"externe_originale": {"cv": "Original und Stellenbezug persönlich abgeglichen."}` angeben. Eine fremde Stellen-ID blockiert die Zuordnung.

Gibt es Nachweise, die du bei jeder Stelle berücksichtigen möchtest, speichere ihre IDs als Standardliste. Der Befehl ersetzt die bisherige Liste. Beim Paketbau muss jede Standard-ID im Plan vorkommen. So erscheint etwa ein gewöhnlich mitgeschickter Kursnachweis auch dann im Manifest, wenn der Arbeitgeber ausdrücklich nur den Lebenslauf sehen möchte.

```sh
python start.py anlagenstandard --anlage kurs
```

Wiederhole `--anlage` für weitere IDs. Mit `anlagenstandard --leeren` entfernst du die Liste für zukünftige Fassungen. Frühere Pakete behalten ihre damalige Standardliste.

## Vorgaben des Arbeitgebers erfassen

Speichere die folgende Vorlage als `paketplan.json` im privaten Arbeitsordner. Übernimm Dateianzahl und Byte-Grenzen aus der konkreten Anzeige oder dem Portal. Größenangaben im Beispiel sind fiktiv. Lass unbekannte Limits weg.

```json
{
  "vorgabe": "Laut Stellenanzeige zwei PDF-Felder für Anschreiben sowie Lebenslauf mit Nachweisen.",
  "pflicht": ["anschreiben", "cv"],
  "optional": ["kurs", "arbeitsprobe"],
  "weglassen": {
    "arbeitsprobe": "Laut Anzeige werden Arbeitsproben erst im Gespräch benötigt."
  },
  "max_dateien": 2,
  "max_bytes_pro_datei": 5000000,
  "max_bytes_gesamt": 8000000,
  "dateien": [
    {"name": "Anschreiben.pdf", "anlagen": ["anschreiben"]},
    {"name": "Lebenslauf-und-Nachweise.pdf", "anlagen": ["cv", "kurs"], "max_bytes": 3000000}
  ]
}
```

`pflicht` und `optional` beziehen sich auf diese Stelle. Prüfe sie gegen die Arbeitgebervorgaben und dein Inventar. Jeder gewünschte Nachweis steht genau einmal in der Ausgabereihenfolge. Optionale, ausgelassene Nachweise brauchen einen Grund. Eine fehlende Pflichtanlage blockiert das Paket.

Ein Eintrag in `dateien` entspricht einem Uploadfeld. Die Reihenfolge der IDs bestimmt die Seitenfolge. Bei nur einem Uploadfeld für die Gesamtbewerbung verwende zum Beispiel `"dateien": [{"name": "Bewerbung.pdf", "anlagen": ["anschreiben", "cv", "kurs"]}]` und setze `max_dateien` auf 1. Verlangt das Feld ausdrücklich nur einen Lebenslauf, ordne ihm ausschließlich die Lebenslauf-ID zu. Ein Einzeldokument bleibt bytegenau erhalten. Mehrere Quellen werden als neue PDF zusammengeführt.

## Fassung erzeugen und prüfen

Ersetze `STELLEN_ID` durch die ID aus dem Befehl `stelle` und `FASSUNG` durch den vollständigen ausgegebenen Ordnernamen mit `v-`.

```sh
python start.py anlagenpaket STELLEN_ID --plan paketplan.json
python start.py paketliste STELLEN_ID
python start.py paketpruefung STELLEN_ID FASSUNG
```

Das fertige Paket liegt unter `anlagen/pakete/STELLEN_ID/FASSUNG/`. Das interne `manifest.json` dokumentiert Unternehmen, Rolle, Anzeigen-URL, Stellenreferenz, Standardliste, die Vorgaben des Arbeitgebers, den Plan, begründete Auslassungen und die tatsächlichen PDF-Dateien mit Größen, Prüfsummen, Quellen und Seitenbereichen. Wähle beim Upload nur die von `paketpruefung` aufgelisteten PDFs. Lies die fertigen Unterlagen vor der Einreichung selbst gegen und kontrolliere die Dateinamen im Portal.

Der Ordnername enthält die Prüfsumme des Manifests. Eine neue Fassung überschreibt frühere Fassungen nicht. Bei einer ungültigen PDF oder einer überschrittenen Grenze entsteht kein Teilpaket. Die erneute Prüfung erkennt unter anderem geänderte PDF-Inhalte, ein verändertes Manifest und zusätzliche Dateien.

## Bestätigte Einreichung dokumentieren

Erfasse die Einreichungsbestätigung mit `ereignis` und dem Status `beworben`. Wenn du die tatsächlich eingereichten Dateien geprüft hast, kannst du genau diese Fassung mit dem vorhandenen Ereignis verbinden. Die Ereignisse in der Chronik der betreffenden Stelle sind ab 1 nummeriert. Schau im Zweifel in der privaten `bewerbungen.json` unter `events` nach.

```sh
python start.py paketzuordnung STELLEN_ID FASSUNG --ereignis 1 --grund "Dateien mit dem Uploadbeleg abgeglichen."
```

Der Assistent prüft Paket und Einreichungsbeleg erneut. Deine Bestätigung wird am bestehenden Ereignis mit Zeitstempel gespeichert. Mit den optionalen Angaben `--vorlage`, `--vorlagenversion` und `--kanal` erfasst du die beim Versand belegte Gestaltung und den tatsächlichen Einreichungsweg für die Kohortenauswertung. Eine erst nach der Einreichung erzeugte Fassung lässt sich ihr nicht zuordnen. Eigene Unterlagen und deren Kopien sind als Einreichungsbeleg ungeeignet. Eine bereits zugeordnete Fassung bleibt erhalten. Paketbau und Paketprüfung lösen weder Versand noch Statuswechsel aus.

Bei einer vorliegenden Original-EML vergleicht der Assistent die Prüfsummen sämtlicher angehängter PDFs mit der Paketfassung. Stimmen sie vollständig überein, erscheint die Zuordnung als `anhang_hash`. Andernfalls wird die ausdrücklich bestätigte Zuordnung als `nutzerzuordnung` geführt. Das gilt auch bei einem Portalbeleg.

Bei einer Zuordnung über eine E-Mail mit PDF-Anhängen müssen die Dateihashes mit der gewählten Fassung übereinstimmen. Bei abweichenden Anhängen verlangt der Assistent einen passenden Einreichungsbeleg.
