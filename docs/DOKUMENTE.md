# Lebenslauf und Anschreiben

Die Befehle laufen im persönlichen Arbeitsordner mit `python start.py`. Wer den Assistenten von einem anderen Ort startet, gibt vor dem Befehl `--ordner PFAD` an. Die erstellten Dateien liegen unter `dokumente/`. Weitere Fassungen bekommen eine Versionsnummer. Die Standardausgabe ist eine einspaltige A4-DOCX mit auswählbarem Text.

## Einen Lebenslauf zuschneiden

```sh
python start.py lebenslauf
python start.py lebenslauf --stelle STELLEN_ID --fakt projektplanung --fakt fachkurs --pdf
python start.py lebenslauf --stelle STELLEN_ID --sprache en --pdf
```

Der erste Aufruf verwendet alle Profilfakten. Mit einer Stellen-ID erscheinen Zielrolle und Firma als Zielposition. Innerhalb jedes Abschnitts stehen zuerst Fakten, deren Stichwörter in der gespeicherten Anzeige vorkommen. Bei einer ausdrücklichen Auswahl mit `--fakt` bestimmen die genannten IDs Inhalt und Reihenfolge innerhalb ihrer Abschnitte. Stelle und Anzeige liefern keine neuen Qualifikationen. Persönliche Suchbedingungen und Belegpfade bleiben im Arbeitsordner.

Für eine thematische Auswahl verwendest du `--tag` mit den Stichwörtern aus `fakt --stichwort` beziehungsweise dem Feld `keywords`. Speichere jede unabhängig auswählbare Aussage oder jeden Aufzählungspunkt als eigenen belegten Fakt. Dann kann zum Beispiel ein Projekt für Planung erscheinen, während eine andere Leistung aus derselben Station entfällt. Mehrere Tags verwenden eine Oder-Auswahl. Mehr übereinstimmende Stichwörter geben Vorrang, bei Gleichstand zählt die Profilreihenfolge. Die Abschnitte behalten ihre fachliche Reihenfolge. `--max-fakten` begrenzt die Gesamtauswahl. Wenn kein Tag passt, nennt der Assistent den fehlenden Treffer.

```sh
python start.py lebenslauf --stelle STELLEN_ID --tag Projektplanung --tag Auswertung --max-fakten 6
python start.py textpruefung lebenslauf --stelle STELLEN_ID --tag Projektplanung --tag Auswertung --max-fakten 6
```

Im privaten `profil.json` kann ein belegter Fakt eine eigene Übersetzung tragen. Ein fiktives Beispiel für einen Eintrag in `facts` ist

```json
{
  "id": "projektplanung",
  "kind": "achievement",
  "text": "Die Projektplanung vereinheitlicht.",
  "source": "Eigene bestätigte Angabe",
  "language": "de",
  "translations": {"en": "Standardised project planning."},
  "keywords": ["Projektplanung", "project planning"]
}
```

Ohne `language` gilt der Ausgangstext als deutsch. Für ursprünglich englische Fakten funktioniert die Gegenrichtung mit `language: "en"` und `translations.de`. Bestätige die Bedeutung jeder Übersetzung anhand des Originalbelegs. Der Renderer nennt die Fakten-ID, wenn der angeforderten Fassung eine Übersetzung fehlt. Die Kontaktzeilen stammen aus dem Profil, Firmierungen und Stellentitel aus der Anzeige.

## ATS-Fassung, Designfassung und Seitenwechsel

`--layout ats` ist der Standard für schlichte, einspaltige Unterlagen. `--layout design` verwendet eine größere Namenszeile, farbige Abschnittsüberschriften und Trennlinien. Beide Layouts stehen auf Deutsch und Englisch zur Verfügung und behalten die Textreihenfolge. Die Designfassung erhält einen eigenen Dateinamen.

```sh
python start.py lebenslauf --stelle STELLEN_ID --sprache en --layout design --foto unterlagen/portrait.jpg --portfolio-url https://example.org/portfolio --einpassen
python start.py lebenslauf --stelle STELLEN_ID --seite-2-ab fachkurs --einpassen
python start.py anschreiben STELLEN_ID --layout design --unterschrift unterlagen/unterschrift.png --einpassen
```

Ein Foto oder eine Unterschrift wird ausschließlich auf ausdrückliche Auswahl eingebettet. Lege das gewünschte JPEG oder PNG im privaten Arbeitsordner ab. Für die Bildaufbereitung wird das lokal installierte Programm `magick` (ImageMagick) benötigt. Es liest die gewählte Datei, berücksichtigt ihre Ausrichtung und erzeugt eine verkleinerte PNG-Fassung ohne die Originalmetadaten. Das Original bleibt erhalten. Wähle für einen Brief eine eigene freigegebene Unterschriftsgrafik. Die Grafik steht vor dem ausgeschriebenen Namen. Ergänze mit `--portfolio-url` nur einen Link, den die empfangende Stelle tatsächlich erhalten darf.

Gliedere eine mehrzeilige berufliche Station im Faktentext mit Zeilenumbrüchen, beispielsweise in Rolle und Arbeitgeber, Zeitraum und Tätigkeit. Kurze Stationen bleiben nach Möglichkeit zusammen. Bei längeren Stationen bleibt der Titel am Folgeabsatz. Überschriften bleiben beim ersten zugehörigen Absatz. Über `--seite-2-ab FAKTEN_ID` kannst du den Beginn der zweiten CV-Seite ausdrücklich setzen. Ist der gewählte Fakt der erste eines Abschnitts, wechselt seine Überschrift mit auf die zweite Seite.

`--kompakt` reduziert Abstände und setzt Fließtext auf 10,5 Punkt. Mit `--einpassen` misst der Assistent die PDF-Seitenzahl. Überschreitet eine normal gesetzte Fassung das Limit, versucht er die kompakte Fassung mit sämtlichen gewählten Fakten und Absätzen. Ein erfolgreiches Ergebnis enthält die zusammengehörige DOCX und PDF. Reicht der Platz weiterhin nicht, meldet das Programm den Befund und du kannst die Faktenauswahl oder Textlänge anpassen.

Für ein belegtes Kurzprofil, Stärken und Ehrenamt können Fakten die Arten `profile`, `strength` und `volunteering` tragen. Mit `--fakt` lassen sich zum Beispiel nur die für eine bestimmte Stelle gewünschten Stärken, Sprachkenntnisse oder Zertifikate aufnehmen.

## Einen Brief rendern

```sh
python start.py entwurf STELLEN_ID --textdatei brief.txt --fakt projektplanung
python start.py anschreiben STELLEN_ID --datum 2026-06-15 --empfaengerzeile Personalteam --pdf
```

Der Entwurf enthält den vollständigen Brieftext einschließlich Anrede, Absätzen, Gruß und Unterschrift. Name und Kontakt stammen aus dem Profil. Empfängerfirma, Betreff und vorhandene Referenz stammen aus der gespeicherten Stelle. Datum und weitere Empfängerzeilen sind freiwillig. Für ein englisches Anschreiben zuerst den selbst geprüften englischen Brieftext als Entwurf speichern und beim Rendern `--sprache en` angeben. Änderungen am Entwurf erzeugen eine lokale Entwurfshistorie.

## Text und fertige Datei prüfen

**1. Text gegen Quellen lesen.** Der Textcheck prüft Faktenverweise, ausgewählte Sprachfassungen, typische Platzhalter und unsichtbare Steuerzeichen. Bei eindeutig erkennbaren Anreden überprüft er häufige Fehler am folgenden Absatzbeginn. Lies Namen, Daten, Titel, Zahlen und die Aussagen im Brief gegen deine Belege und die Originalanzeige. Die angegebenen Fakten-IDs helfen beim Nachschlagen.

```sh
python start.py textpruefung lebenslauf --stelle STELLEN_ID --sprache en
python start.py textpruefung anschreiben --stelle STELLEN_ID --datum 2026-06-15 --empfaengerzeile Personalteam
```

**2. Datei lesen lassen.** Setze den tatsächlich ausgegebenen Dateipfad ein. Verwende dieselben Optionen wie beim Rendern, einschließlich Faktenauswahl, Sprache, Datum und Empfängerzeilen.

```sh
python start.py ats-pruefung lebenslauf dokumente/STELLEN_ID-lebenslauf-en.docx --stelle STELLEN_ID --sprache en
python start.py ats-pruefung anschreiben dokumente/STELLEN_ID-anschreiben.pdf --stelle STELLEN_ID --datum 2026-06-15 --empfaengerzeile Personalteam
```

Der lokale Lesetest für Bewerbermanagementsysteme (ATS) liest den Text aus der angegebenen Datei und vergleicht ihn in Reihenfolge und Wortlaut mit der gewählten aktuellen Fassung. Die DOCX-Prüfung liest die Absätze und ihre Gliederung im Hauptdokument. Sie prüft einspaltiges A4 und meldet zusätzliche Textebenen wie Textfelder und Tabellen. Der PDF-Test liest den Text mit Poppler, erkennt die Abschnittsüberschriften als eigene Zeilen und prüft jede Seitengröße. Ein Lebenslauf darf bis zu zwei Seiten haben, ein Anschreiben eine. Bei stellenbezogenen Dokumenten muss die Stellen-ID auch im Metadatenfeld „Betreff“ stehen. Abweichungen führen zu einer Fehlermeldung und Exitcode 2. Eine überlange PDF kürzt du durch eine engere Faktenauswahl oder einen überarbeiteten Brieftext.

Für DOCX ohne Bild genügt Python. Der PDF-Export benötigt lokal LibreOffice. Zum Lesen der PDF müssen `pdftotext` und `pdfinfo` aus Poppler im Suchpfad liegen. Für eine Fassung mit Foto oder Unterschrift bestätigt `pdfimages` die Präsenz eines Bildobjekts. Die DOCX-Prüfung vergleicht zusätzlich die eingebetteten Bilddaten mit der gewählten Eingabedatei. Gib beim Prüfen dieselben Layout-, Bild- und Umbruchoptionen an. Ob das Bild korrekt positioniert und erkennbar ist, prüfst du in der fertigen PDF. Ein Word-Export muss die Dokumenteigenschaften mitführen. Scans ohne Textebene, alte unstrukturierte Fassungen und nachträglich bearbeitete Dateien können den Lesetest verfehlen. Bei geändertem Profil oder Entwurf prüft der Befehl gegen den heutigen Datenstand. Historische Unterlagen bleiben erhalten.

Lies die fertigen Dateien selbst und öffne die PDF zur Layoutkontrolle. Halte deine beiden tatsächlichen Prüfungen mit `python start.py pruefung STELLEN_ID --inhalt "…" --dokument "…"` fest. Ein lokaler Lesetest bestätigt weder die Verarbeitung durch ein konkretes Portal noch die inhaltliche Richtigkeit eines Entwurfs.


## Eigene Entwürfe und DOCX-Eigenschaften bereinigen

```sh
python start.py entwurf-bereinigen STELLEN_ID
python start.py docx-bereinigen anschreiben dokumente/STELLEN_ID-anschreiben.docx --stelle STELLEN_ID
python start.py docx-bereinigen lebenslauf dokumente/lebenslauf.docx --ohne-autor
```

Der erste Befehl schreibt den aktuell gespeicherten eigenen Briefentwurf in eine neue UTF-8-Textdatei unter `dokumente/`. Er entfernt weiche Trennzeichen, unsichtbare Leerzeichen, Wortverbinder und BOM-Zeichen. Er vereinheitlicht Tabulatoren, Leerzeichenvarianten und Zeilenenden. Sichtbare Aussagen, Absätze und sprachlich bedeutsame Verbindungszeichen bleiben erhalten. Lies die Datei und übernimm sie bei Bedarf mit `entwurf STELLEN_ID --textdatei PFAD --fakt FAKTEN_ID` als neue Entwurfsfassung.

Der DOCX-Befehl erzeugt eine neue Kopie. Gib dieselben Profil-, Sprach-, Bild- und Layoutoptionen wie beim Rendern an. Bei einer automatisch kompakt gesetzten Fassung gehört `--kompakt` dazu. Das Programm rekonstruiert die Unterlage aus den eigenen aktuellen Angaben und vergleicht Hauptdokument, Medien und Beziehungen mit der ausgewählten Datei aus `dokumente/`. Bei abweichendem Inhalt oder zusätzlichen Bestandteilen wie Signaturen bricht es ab. Zeugnisse, Originalbelege und fremde Dokumente bleiben in ihrer ursprünglichen Form.

Aus der kontrollierten Kopie entfernt der Assistent den letzten Bearbeiternamen, die Revisionsnummer und das letzte Druckdatum sowie vorhandene technische Angaben zu Firma, Leitung, Bearbeitungsdauer, Vorlage und Programmversion. Standardmäßig bleiben dein Autorname, der Stellenbetreff sowie Rechte- und Herkunftsangaben erhalten. Mit `--ohne-autor` kannst du zusätzlich deinen eigenen Namen im Office-Autorenfeld entfernen. Der sichtbare Dokumenttext ändert sich dabei nicht. Eine bereits auf andere Weise umformatierte oder neu gespeicherte Datei kann vom Originalaufbau abweichen. Erzeuge in diesem Fall aus deinen aktuellen Quellen eine neue Fassung.

Für den gesamten Ablauf im Assistenten nutze `/bewerbung` mit der konkreten Stelle. Damit lassen sich Dokumentauswahl, Prüfung und Anlagenpaket gemeinsam vorbereiten.
