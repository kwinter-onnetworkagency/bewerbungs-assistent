# Stellen und Gehalt recherchieren

Öffne das Terminal im persönlichen Arbeitsordner. Die Befehle lesen dort dein Profil und erfassen Ergebnisse lokal. In Windows kannst du `python` anstelle von `python3` verwenden.

## Suchlauf

```sh
python3 start.py suchlauf --begriff "Disposition" --ort "Leipzig" --greenhouse BOARD --details
```

Ersetze `BOARD` durch die Kennung aus der Greenhouse-Karriereseite des gewünschten Arbeitgebers. Du kannst `--greenhouse` und `--begriff` mehrmals angeben. Ohne Suchbegriff kommen die Zielrollen aus deinem Profil zum Einsatz. Den Suchort gibst du ausdrücklich an. Ohne Ort sucht der Lauf über alle Standorte.

| Quelle | Was der Lauf tatsächlich verarbeitet |
|---|---|
| Bundesagentur für Arbeit (BA) | Abfrage je Zielrolle. Bei gesetztem Ort mit Umkreis. Standard sind eine Seite mit bis zu 25 Treffern, 25 km und Veröffentlichungen aus den letzten 14 Tagen. `--seiten`, `--umkreis` und `--tage` ändern diese Grenzen. |
| Greenhouse | Ruft veröffentlichte Stellen der angegebenen Arbeitgeber-Boards ab. Die Auswahl nach Titel und Ort erfolgt lokal. Alle Wörter einer Zielrolle müssen im Titel vorkommen. |
| Indeed | Liest auf Wunsch tatsächliche, von dir zuvor gesichtete Funde aus einer lokalen JSON-Datei ein. Der verbundene Assistent kann die Indeed-Suche ausführen und die Funde mit Direktlink und Sichtungsdatum in diesem Format bereitstellen. |
| Weitere Karriereseiten | Mit `suchanfragen` erhältst du Suchausdrücke unter anderem für Personio, Lever, Ashby und Workday. Der Assistent kann diese mit seinem Webzugang ausführen. |

Für den BA-Zugriff übergibst du deinen vorhandenen Zugang über die lokale Umgebungsvariable `BA_JOBSUCHE_API_KEY`. Greenhouse erlaubt Lesezugriff ohne Zugangsdaten. Der Suchlauf sendet nur die benötigten Suchparameter an die BA. Bei Greenhouse fragt er die Board-Kennung und für optionale Details die Stellen-ID ab. [BA-Jobsuche](https://www.arbeitsagentur.de/jobsuche/) · [Offizielle Greenhouse-Dokumentation](https://developers.greenhouse.io/job-board.html#list-jobs)

**Indeed-Import**. Speichere die Treffer als Liste, zum Beispiel in `indeed-funde.json`. Ersetze die Beispielangaben durch echte Funde. `indeed_url` ist der gesichtete Stellenlink. Unter `url` kannst du zusätzlich die Originalanzeige des Arbeitgebers angeben. Fehlt diese, bleibt der Indeed-Link die Fundstelle.

```json
[
  {
    "role": "Disposition",
    "company": "Beispielunternehmen",
    "location": "Leipzig",
    "gesehen_am": "2025-03-12",
    "indeed_url": "https://de.indeed.com/viewjob?jk=BEISPIEL",
    "url": "https://example.org/karriere/disposition"
  }
]
```

```sh
python3 start.py suchlauf --begriff "Disposition" --indeed-datei indeed-funde.json
```

Jeder Lauf legt in `exports` eine eigene Datei `Suchlauf-…json` ab. Sie enthält nummerierte Treffer, Fundquellen, bekannte Stellen und pro Quelle das Ergebnis des Abrufs. Ein erreichtes Seitenlimit, fehlende Zugänge, Anbieterfehler und fehlende Details sind im Bericht sichtbar. Schon gelesene Seiten bleiben bei einem späteren Fehler erhalten. Die ersten zehn Treffer stehen zusätzlich im Terminal. Ein Indeed-Import belegt die damalige Sichtung. Die Anzeige kann inzwischen geschlossen sein.

Öffne die vollständige Anzeige und prüfe Arbeitgeber und Bewerbungsweg. Ersetze anschließend den Dateinamen und die Nummer durch die Werte des Laufs.

```sh
python3 start.py suchfund Suchlauf-20250312T103000000000Z.json 1 --firma "Beispielunternehmen"
```

Mit `--details` holt der Suchlauf auf Wunsch die Anzeigentexte bei BA und Greenhouse. Fehlt der Volltext, übergib die gelesene Fassung zusätzlich mit `--textdatei anzeige.txt`. `suchfund` speichert den Vorgang und die Fundstellen. Die Board-Kennung bei Greenhouse identifiziert die Karriereseite. Prüfe im Impressum oder in der Anzeige, welches Unternehmen die Stelle ausschreibt, und übergib dessen Namen mit `--firma`.

## Passung prüfen

```sh
python3 start.py passung --alle
python3 start.py passung --id JOB-ID
python3 start.py bewerten JOB-ID --score 70 --grund "Das Arbeitszeitmodell ist verbindlich geklärt."
```

Die Ausgabe nennt den wirksamen Score und zeigt, welche belegten Aussagen und Kompetenzen der Anzeigentext enthält. Der Faktenabgleich gewichtet hinterlegte Stichwörter mit 55 Prozent, Kompetenzen aus Profilfakten der Art `skill` mit 25 Prozent und Zielrollen im Titel mit 20 Prozent. Bei fehlenden Dimensionen verteilt sich das Gewicht auf die verfügbaren. Für eine Kompetenz ohne Stichwörter verwendet das Werkzeug deren genaue Bezeichnung. Ohne vergleichbare Fakten oder Kompetenzen bleibt der automatische Score offen.

Eine manuelle Bewertung hat Vorrang, auch bei null Punkten. Die Liste sortiert nach dem wirksamen Score. Muss-Kriterien, Gehaltswunsch, Mobilität und Arbeitsmodell aus dem Interview sind als persönliche Prüfpunkte sichtbar. Gleiche die Anforderungen mit dem Original ab. Synonyme, Verneinungen und fachliche Tiefe brauchen eine inhaltliche Prüfung.

## Gehaltsangaben belegen

**Arbeitgeberband.** Erfasse die Angabe zur konkreten Stelle oder eine belegbar geltende Tarifregel. Für eine einseitige Angabe reicht `--von` oder `--bis` allein. Nenne Fixum oder Gesamtvergütung, Arbeitszeit und Brutto-/Nettobasis nach Quelle.

```sh
python3 start.py gehaltsband JOB-ID --von 42000 --bis 46000 --zeitraum Jahr --waehrung EUR --basis "Bruttofixum bei 38 Wochenstunden" --quelle https://example.org/karriere/disposition --stand 2025-03-12
```

**Entgeltatlas.** Prüfe in der BA-Quelle den passenden fünfstelligen Code der Klassifikation der Berufe, das Anforderungsniveau und die Regions-ID. Die Abfrage braucht den eigenen Zugang in `BA_ENTGELTATLAS_API_KEY`. Die Regions-ID 1 steht für Deutschland. Ersetze die Beispielwerte nach deiner Recherche. [Entgeltatlas](https://web.arbeitsagentur.de/entgeltatlas/) · [Methodik der Bundesagentur](https://www.arbeitsagentur.de/hilfe-entgeltatlas)

```sh
python3 start.py entgeltatlas --kldb 83112 --niveau 2 --region 1 --id JOB-ID
```

Die Ausgabe enthält den Vollzeit-Bruttomonatsmedian, das untere und das obere Quartil, soweit ausgewiesen. Eine Jahreshochrechnung entspricht zwölf Monatswerten. Bei unterdrückten Werten steht die Kennzahl auf `null`, der Originalcode bleibt unter `quellwerte` erhalten. Der Abrufzeitpunkt ist separat ausgewiesen. Mit `--id` wird das Ergebnis als Marktvergleich zur Stelle abgelegt. Anbieterfehler führen zu einer Fehlermeldung. Eine gültige leere Ergebnisliste bleibt leer.

Ein in der Quelle belegter Durchschnitt, etwa bei Indeed Gehälter, lässt sich mit dem bestehenden Befehl `gehaltswert` erfassen. Gib Bezugsgruppe, Region, Basis, Datenstand und Originalkennzahl an. Das Budget des konkreten Arbeitgebers braucht eine eigene Quelle. [Indeed Gehälter](https://de.indeed.com/career/salaries)

## Änderungen und offene Zugänge verfolgen

Bei bereits bekannten Stellen enthält der Suchbericht die Stellen-ID und einen Vergleich der erneut gelieferten Angaben mit dem vorherigen Suchstand. Bei Volltexten steht der Textunterschied im Bericht. Ein Indeed-Import kann zusätzlich die tatsächlich gelesenen Felder `anforderungen`, `arbeitsmodell`, `gehaltsangabe_der_anzeige` und `description` enthalten. Fehlt ein Wert beim Abruf, bleibt die Änderung offen. `nicht_wiedergefunden` gilt nur für diesen Suchlauf und dessen Filter.

Mit `anzeigenstand` dokumentierst du eine tatsächlich gelesene Arbeitgeberaussage. Ein Login, ein HTTP-Fehler oder ein nicht wiedergefundener Treffer lässt die Erreichbarkeit offen. Für eine bestätigte Schließung gib die geprüfte Originaladresse und den Wortlaut des Arbeitgebers an. Diese Angaben verändern keinen Bewerbungsstatus.

```sh
python start.py anzeigenstand JOB-ID --zustand zugang_offen --quelle https://example.org/stelle --beleg "Login erforderlich"
python start.py anzeigenstand JOB-ID --zustand offen --quelle https://example.org/stelle --beleg "Aktuelle Stellenanzeige gelesen" --arbeitsmodell "Zwei Präsenztage pro Woche" --textdatei anzeige.txt --uebernehmen
```

Die ausdrückliche Übernahme ersetzt den aktuellen Anzeigentext, archiviert den vorigen und hebt eine frühere Prüfung auf. Für die reine Beobachtung lässt du `--uebernehmen` weg.

Stellen- und Bewerbungslinks werden bei bekannten URL-Mustern über Anbieter, Arbeitgeber und Stellenkennung zusammengeführt. Das umfasst Ashby-UUIDs, Workday-Requisitionsnummern, numerische SmartRecruiters-Kennungen sowie die Stellen- und Formularansicht desselben Recruitee-Slugs. Neue Recruitee-Slugs oder eigene Arbeitgeberdomains benötigen bei fehlender gemeinsamer Kennung die geprüfte Firmenreferenz. [Ashby Job Posting](https://developers.ashbyhq.com/reference/jobpostinglist) · [SmartRecruiters Job Postings](https://developers.smartrecruiters.com/docs/get-job-postings) · [Recruitee-Formularadressen](https://support.recruitee.com/en/articles/1066259-create-an-application-form-for-each-job)

## Wöchentliche Suche mit Gehaltsvergleich und Dashboard

Im persönlichen Arbeitsordner kombiniert `wochenlauf` die Suche mit Volltextabruf, bestätigten Funden, Passung, passenden BA-Gehaltsclustern und aktualisiertem Dashboard. Ein Zeitplan kann denselben Befehl ausführen. Gib Suchbegriffe, Orte, Arbeitgeber-Boards und die optionalen Quellen so an wie bei `suchlauf`.

Speichere die folgende Struktur als `wochenplan.json`. Für einen ersten Lauf kannst du beide Listen leer lassen. Das Beispiel zeigt die Form einer Freigabe und eines Gehaltsclusters. Ersetze die URL, die Firma, den relativen Pfad zum selbst gelesenen Volltext, das Sichtungsdatum und die Klassifikation durch geprüfte Werte. Der Regionsschlüssel gilt für den gewählten Vergleichsmarkt.

```json
{
  "bestaetigt": [
    {"url": "https://example.org/karriere/disposition", "firma": "Beispielbetrieb", "textdatei": "anzeige.txt", "gesehen_am": "2025-03-12"}
  ],
  "gehaltscluster": [
    {"titelbegriffe": ["Disposition"], "kldb": "51622", "region": 1, "niveau": 2}
  ]
}
```

```sh
python start.py wochenlauf --plan wochenplan.json --begriff "Disposition" --ort Leipzig --greenhouse BOARD
```

Ein neuer Fund benötigt den persönlich bestätigten Originaltext. Bei bekannten Stellen kann der Lauf einen erneut gelieferten unveränderten Volltext mit dem gespeicherten Original vergleichen. Abweichungen und ungesichtete Funde bleiben als offene Sichtungen im Bericht. Ändert sich eine bekannte Anzeige, kannst du die neue Fassung mit `anzeigenstand` ausdrücklich übernehmen. Nach der Sichtung lässt sich derselbe Suchbericht weiterverarbeiten; ersetze den Dateinamen durch die Ausgabe des ersten Laufs.

```sh
python start.py wochenlauf --plan wochenplan.json --bericht Suchlauf-20250312T103000000000Z.json
```

Die Datei `exports/Wochenlauf-…json` enthält den verwendeten Suchbericht, Quellenabdeckung, offene Treffer, bestätigte Stellen mit Passung und separat die BA-Vergleichswerte. Jeder passende Cluster wird pro Lauf einmal abgerufen. Unterdrückte Werte, leere Ergebnisse und Zugangsfehler bleiben erkennbar. Das Dashboard zeigt die gespeicherten Stellen und Marktvergleiche. Eine gesichtete Stelle erhält durch den Wochenlauf keinen Versandstatus.
