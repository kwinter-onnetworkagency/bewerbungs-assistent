# Mein Bewerbungsarbeitsplatz

Öffne `exports/Dashboard.html` aus deinem persönlichen Ordner. Für den ersten Blick kannst du im Menü **Arbeitsstand laden** die fiktive Datei [Beispiel-Arbeitsstand](https://github.com/kwinter-onnetworkagency/bewerbungs-assistent/releases/download/v0.3.0/dashboard-demo.json) auswählen. Bei einer lokalen Installation lädt dasselbe Menü deine eigene `bewerbungen.json`. Das Laden erfolgt im Browser auf deinem Gerät. Die mit persönlichen Daten erzeugte HTML-Datei gehört in deinen privaten Ordner.

| Ansicht | Wofür du sie verwendest |
|---|---|
| Heute | Offene Aufgaben, Fristen, Gespräche, Angebote und die zuletzt erfassten Rückmeldungen durchgehen. |
| Stellen | Screening und Arbeitgeberbänder vergleichen. Nach Unternehmen, Status oder Erfassungstag filtern. Den manuellen Score und seine Begründung am Original prüfen. |
| Bewerbungen | Von der Vorbereitung bis zur Entscheidung jede Stelle mit Referenz, Verlauf und zugehörigen Unterlagen öffnen. |
| Gespräche | Vorbereitung je Runde lesen. Über „Nur diese Runde öffnen“ und „Drucken“ erhältst du die einzelne Mappe auch als PDF über den Druckdialog. |
| Auswertung | Die Anzahl eindeutiger Vorgänge je aktuellem Status vergleichen. Mehrere Nachrichten zu einer Stelle zählen als ein Vorgang. |

Beim Aufruf von `/bericht` soll der lokale Assistent das Dashboard, Markdown und CSV gemeinsam aktualisieren. Ohne lokale Werkzeuge zeigst du den Stand direkt im Chat. Für die HTML-Ansicht lade die neutrale Dashboard-Datei aus dem Release und wähle den freigegebenen JSON-Arbeitsstand auf deinem Gerät. Ein gekürzter Chat-Export enthält weniger Details als der lokale Arbeitsstand.

## Von der Suche zum Tagesbericht

Schreibe zum Beispiel „/stellensuche Finde Teilzeitstellen im Einkauf rund um Leipzig“. Der Assistent sucht mit deinen verfügbaren Werkzeugen bei Arbeitgebern, Bewerberportalen, der [BA-Jobsuche](https://www.arbeitsagentur.de/jobsuche/) und [Indeed](https://de.indeed.com/). Im Dashboard kannst du unter „Stellen“ die beiden Portale direkt mit Rolle und Region öffnen. Bei einer Indeed-Verbindung nutzt der Assistent deren Stellensuche und verfügbare Unternehmensinformationen. Der Abruf persönlicher Profildaten ist dafür entbehrlich.

Halte Fundquelle und offene Originalanzeige fest. Vergleiche Arbeitgeber, Stellen-ID und Bewerbungslink über die Portale hinweg. Merke je Stelle Anforderungen, belegten Fit, Lücken, Standort, Arbeitsmodell und Empfehlung vor. Eine zweite Rolle beim selben Unternehmen bekommt ihren eigenen Vorgang. Wenn eine Seite gesperrt ist, dokumentiere die Lücke und prüfe die weiteren Quellen. Aus einer nicht erreichbaren Seite lässt sich keine Schließung ableiten.

Für eine Tagesübersicht filtere „Stellen“ oder „Bewerbungen“ über „Erfasst am“. Der Filter umfasst neue Stellen, erfasste Notizen und nachgetragene Ereignisse. Die Detailseite zeigt das tatsächliche Ereignisdatum und den Erfassungstag. Drucke die gefilterte Liste oder öffne den Vorgang mit den zugehörigen Unterlagen.

## Gehalt mit Quellen vergleichen

„/gehalt Vergleiche diese Stelle mit meinem Ziel. Welche Budgetfrage ist noch offen?“ Der Assistent prüft das ausgeschriebene Arbeitgeberband, danach den [Entgeltatlas](https://web.arbeitsagentur.de/entgeltatlas/) für die passende Berufsgruppe und Region sowie [Indeed Gehälter](https://de.indeed.com/career/salaries). Direkte Arbeitgeberangaben, Tarifgruppe, Plattformschätzung und Selbstauskunft jeweils kennzeichnen. Erfasse Rolle, Niveau, Gebiet, Arbeitszeit, Währung, Fixum oder Gesamtvergütung, Zeitraum, Datenstand und Quellenlink. Stehen Quartile oder Stichprobengröße in der Quelle, übernimm sie mit ihrer Bezeichnung. Eine gekennzeichnete Jahreshochrechnung aus zwölf Monatswerten bildet keinen gesonderten Bonus ab. Im Ergebnis stehen Arbeitgeberbudget, Marktvergleich, Passung zum Profil und die nächste Budgetfrage getrennt. [Methodik der Bundesagentur](https://www.arbeitsagentur.de/hilfe-entgeltatlas)

## Ein Gespräch vorbereiten und üben

„/gespraech Bereite mich auf die zweite Fachrunde zu dieser Stellen-ID vor. Übe danach eine Frage nach der anderen.“ Kläre Format, Sprache, Teilnehmende, Terminstand und Ziel dieser Runde. Nutze die vollständige Anzeige, Einladung, bisherige Antworten, bestätigte Profilfakten und freigegebene Portfolio-Beispiele. Liefere Kurzbriefing, 90-Sekunden-Einstieg, zwei oder drei belegbare Beispiele, Fachfragen mit Antwortansätzen, Übungsfall, eigene Fragen und Abschluss. Im Rollenspiel auf die Antwort warten und gezielt nachfragen. Nachbereitung und nächste Runde erhalten eigene datierte Einträge. Ein unverbindlicher Terminvorschlag bleibt als solcher bezeichnet.

## Für lokale Assistenten

Die Person arbeitet mit Kurzbefehlen. Die folgenden Aufrufe dienen dem Assistenten als Schreibweg. Sichere Text im privaten Arbeitsordner. Notizen mit derselben Art und demselben Titel sind Versionen. Die Übersicht zeigt die jüngste Fassung. Verwende pro Gesprächsrunde und Marktquelle eigene Titel. Der Bewerbungsstatus folgt weiterhin ausschließlich dem belegten Ereignis.

```sh
python3 start.py notiz STELLEN-ID --art screening --titel "Ersteinschätzung" --textdatei screening.txt
python3 start.py notiz STELLEN-ID --art marktvergleich --titel "Regionaler Vollzeitmedian" --textdatei markt.txt --quelle https://web.arbeitsagentur.de/entgeltatlas/beruf/BELEGTE-ID
python3 start.py notiz STELLEN-ID --art gespraech --titel "Fachrunde" --textdatei fachrunde.txt
python3 start.py notiz STELLEN-ID --art aufgabe --titel "Termin abstimmen" --textdatei aufgabe.txt
python3 start.py bericht
```

Für eine schriftlich belegte Gehaltsspanne verwende `arbeitgeberband`. Beträge gehören zusammen mit ihrer Bezugsbasis in den Text. Nutze einen belegten Direktlink oder den privaten Nachweis mit `--beleg DATEI`. Wiederhole `--quelle` für weitere URLs. Ergänze `--datum JJJJ-MM-TT` für eine belegte Frist oder einen Termin. Eine Aufgabe lässt sich mit gleichem Titel, Textdatei und `--erledigt` abschließen. Die letzte Fassung zeigt den neu übergebenen Text. Eine zuvor erfasste Frist wird übernommen. Beim Wechsel auf Windows ist der lokale Interpreter meist `python`. Ohne lokale Schreibmöglichkeit gib die Mappe und die Änderungen direkt im Chat zur Prüfung zurück.

Exakte Vergleichswerte kann der Assistent über `gehaltswert` strukturiert erfassen. Beispiel mit fiktiven Daten:

```sh
python3 start.py gehaltswert STELLEN-ID --titel "Beispielquelle" --quelle https://example.org/markt --beruf Einkauf --region Sachsen --basis Vollzeit --kennzahl Median --zeitraum Monat --wert 4000 --waehrung EUR --datenstand "2025, fiktiv"
```

Die Originaleinheit bleibt sichtbar. Monatswerte erhalten zusätzlich eine gekennzeichnete Jahreshochrechnung. Für gedeckelte Angaben wie „größer als“ oder fehlende Werte verwende eine Textnotiz, damit die Aussage der Quelle erhalten bleibt.
