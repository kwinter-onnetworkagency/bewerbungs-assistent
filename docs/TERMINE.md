# Kontakte, Termine und Gesprächsrunden

Arbeite im persönlichen Arbeitsordner. Die folgenden Befehle verwenden die ID einer dort gespeicherten Stelle. Für jede Gesprächsrunde vergibst du eine eindeutige Kennung, zum Beispiel `erstkontakt` oder `fachrunde`. Wiederhole dieselbe Kennung bei einer Terminverschiebung und für die spätere Nachbereitung.

## Einen persönlichen Kontakt sichern

```sh
python start.py kontakt STELLEN_ID --name "Beispielperson" --email "kontakt@example.org" --funktion "Fachkontakt"
```

Name, berufliche Adresse, Funktion und optional `--telefon` stammen aus deinem tatsächlichen Austausch. Für getrennte Namensfelder gibt es `--vorname` und `--nachname`. Ohne diese Angaben bleibt der Anzeigename als Ganzes erhalten. Bestätigte Geschäftsanschrift und Website lassen sich mit `--strasse`, `--plz`, `--stadt`, `--region`, `--land` und `--website` ergänzen. Der Betrieb kommt aus der gespeicherten Stelle. Die VCF-Datei unter `kontakte/` erhält eine stabile UID für diese E-Mail-Adresse in deinem Arbeitsordner. Ein weiterer identischer Aufruf liefert dieselbe Datei. Wenn sich eine Angabe geändert hat, prüfe die Adresse und übernimm die Änderung ausdrücklich mit `--aktualisieren`.

## Einen bestätigten Termin übernehmen

```sh
python start.py termin STELLEN_ID --runde fachrunde --start 2027-03-15T10:00+01:00 --ende 2027-03-15T10:45+01:00 --zeitzone Europe/Berlin --quelle "Bestätigte Einladung zur Fachrunde" --ort "Raum A"
```

Trage die Anfangs- und Endzeit jeweils mit dem UTC-Versatz **an diesem Tag** ein. Mit `--zeitzone` prüft der Assistent den Versatz gegen die lokalen Zeitzonendaten. Die doppelte Stunde bei der Umstellung auf Winterzeit lässt sich durch `+02:00` oder `+01:00` eindeutig angeben. Die Kalenderdatei enthält UTC-Zeiten. Die gewählte Kalender-App zeigt sie in ihrer eingestellten Zeitzone an. Falls das System keine IANA-Zeitzonendaten enthält, kannst du die ausdrücklich bestätigten Versätze ohne die zusätzliche Ortszeitprüfung verwenden.

Unter `gespraeche/STELLEN_ID/runde-fachrunde/Termin.ics` entsteht ein privater Kalendereintrag. Die Angabe bei `--quelle` erscheint in seiner Beschreibung. Eine kurze Bezeichnung der Einladung reicht. Die Betreffzeile mit persönlichen Einzelheiten, vertrauliche Originale und private Aktenpfade gehören dort nur hinein, wenn du sie in deinem Kalender speichern möchtest. Einen Terminvorschlag kannst du als Gesprächsnotiz festhalten oder mit `--vormerkung` als ausdrücklich vorläufigen Termin kennzeichnen. Die ICS-Datei erhält dann den Status TENTATIVE.

Bei einer bestätigten Verschiebung wiederholst du den Aufruf mit derselben Runden-ID, den neuen Zeiten und `--aktualisieren`. Die Datei behält ihre UID und erhält eine höhere Revisionsnummer. Der nächste identische Aufruf verändert weder Datei noch Revision.

## Direkt in macOS übernehmen

`--mac` veranlasst einen tatsächlichen Schreibvorgang in Apple Kontakte beziehungsweise dem ausdrücklich benannten Apple-Kalender. macOS kann für das verwendete Terminal oder die Assistenten-App eine Automationsberechtigung verlangen. Der lokale Datei-Export allein funktioniert ohne sie. Ein synchronisierter Kalender oder das Standardadressbuch kann die Daten auf deine weiteren Geräte übertragen.

```sh
python3 start.py kontakt STELLEN_ID --name "Beispielperson" --email "kontakt@example.org" --funktion "Koordination" --abteilung "Personal" --telefon "0123 100" --mobil "0123 200" --fax "0123 300" --mac
python3 start.py termin STELLEN_ID --runde fachrunde --quelle "Terminvorschlag" --start 2027-03-15T10:00+01:00 --ende 2027-03-15T10:45+01:00 --zeitzone Europe/Berlin --vormerkung --mac --kalender "Bewerbungen"
```

Bürotelefon, Mobilnummer und Fax kannst du je Nummer wiederholen. Die Kontakte-App speichert neue Kontakte im dort gewählten Standardadressbuch. Beim Abgleich berücksichtigt das Werkzeug die genaue E-Mail-Adresse sowie Namens- und Firmenkombination. Bereits eindeutig bekannte, passende Daten werden zurückgelesen. Unklare Dubletten bleiben zur persönlichen Zuordnung offen. Änderungen am bereits bestätigten Kontakt brauchen `--aktualisieren`. Dabei bleiben andere vorhandene Telefonnummern und Anschriften erhalten.

Der Kalenderabgleich prüft den ausgewählten Kalender, vorhandene native Kennungen sowie gleichnamige Termine zum selben Zeitpunkt. Die absolute Zeit bleibt auch beim Wechsel zwischen Sommer- und Winterzeit erhalten. Bei Bestätigung einer Vormerkung nutze dieselbe Runden-ID mit `--aktualisieren` und lasse `--vormerkung` weg. Es werden keine Gäste angelegt. Bestehende Termine mit Teilnehmern oder Wiederholungen bearbeitest du persönlich. Der Bewerbungsstatus bleibt unabhängig davon.

Nach dem Speichern werden die angegebenen Felder anhand des nativen Datensatzes erneut gelesen. Neben der VCF- oder ICS-Datei dokumentiert `*.native.json` die bestätigte native Kennung. Bei fehlender Berechtigung, Mehrdeutigkeit oder offenem Rücklesen prüfe den Bestand, bevor du den identischen Auftrag wiederholst. Für andere Systeme nutze die VCF- beziehungsweise ICS-Datei.

## Die Datei in der eigenen App öffnen

Öffne die ausgegebene VCF- oder ICS-Datei selbst oder ergänze beim ausdrücklich gewünschten Import `--oeffnen`. Das übergibt genau diese Datei an das Standardprogramm des Betriebssystems. Prüfe dort das ausgewählte Adressbuch oder den Kalender, insbesondere bei synchronisierten Konten. Suche vor einem erneuten Import nach der E-Mail-Adresse beziehungsweise nach Betrieb, Rolle und Runde. Wie aktualisierte Einträge mit gleicher UID übernommen werden, entscheidet die jeweilige App. Der Assistent versendet keine Einladung und verändert durch diese Befehle keinen Bewerbungsstatus.

Die Exporte verwenden die veröffentlichten Austauschformate für Kontakte und Kalender. [vCard 4.0](https://www.rfc-editor.org/rfc/rfc6350) · [iCalendar](https://www.rfc-editor.org/rfc/rfc5545)

## Für eine Runde üben und das Ergebnis festhalten

1. Bitte den Gesprächs-Skill, die konkrete Runde anhand der vollständigen Anzeige, bestätigter Fakten und benannter Quellen vorzubereiten. Im lokalen Assistenten kannst du seinen Text mit einem eindeutigen Titel sichern.
2. Erzeuge die Arbeitsmappe aus den Fakten und Notizen dieser Runde. Jeder `--notiz`-Wert bezeichnet einen vollständigen Titel einer Gesprächsnotiz genau dieser Stelle. Die jüngste gespeicherte Fassung je Titel zählt. Ohne Auswahl wird eine vorhandene Notiz mit dem Titel der Runden-ID berücksichtigt.
3. Öffne die ausgegebene Vorbereitungsdatei. Übe die Vorstellung, Praxisbeispiele, Fallfrage und eigene Rückfragen laut. Bearbeite deine Antworten in einer eigenen Kopie. Das Rollenspiel im Gesprächs-Skill wartet nach jeder Frage auf deine Antwort.
4. Fülle nach dem Gespräch die Datei `Nachbereitung.txt` aus. Trenne tatsächliche Aussagen der Beteiligten, eigene Einschätzung und offene Punkte. Sichere bei Bedarf anschließend die durchgesehene Gesprächsnotiz unter einem eigenen Titel im Dashboard. Für Aufgaben mit Frist verwende `notiz --art aufgabe`.

```sh
python start.py notiz STELLEN_ID --art gespraech --titel "Fachrunde Recherche" --textdatei briefing.txt --quelle https://example.org/team
python start.py gespraechsmappe STELLEN_ID --runde fachrunde --fakt projektplanung --notiz "Fachrunde Recherche"
python start.py notiz STELLEN_ID --art gespraech --titel "Fachrunde Nachbereitung" --textdatei gespraeche/STELLEN_ID/runde-fachrunde/Nachbereitung.txt
python start.py bericht
```

Der Assistent übernimmt die Anzeige, ausgewählte Fakten mit ihrer Quelle, mögliche Termindaten und die gewählten Gesprächsnotizen. Gesicherte Belegdateien werden per Prüfsumme kontrolliert. Im Rundenordner steht nur ihr Nachweisverweis. Geändertes Material erzeugt eine neue Vorbereitungsfassung im selben Ordner. Eine bereits ausgefüllte Nachbereitung bleibt bei Wiederholung erhalten. Die Mappe bestätigt weder die Teilnahme noch ein Gesprächsergebnis.
