# Bewerbungsablauf

Das Gespräch im Assistenten und die lokalen Werkzeuge ergänzen sich. Das Interview hält deine Ziele und Arbeitsregeln fest. Du kannst Lebenslauf und Nachweise bereitstellen oder die Informationen einzeln besprechen. Angaben bleiben als Nutzerangaben erkennbar, bis Originale geprüft sind. Persönliche Bedingungen werden weder aus einem Musterprofil noch aus einer Anzeige übernommen.

## 1. Profil

Arbeite in deinem persönlichen Ordner. `python start.py interview` führt den lokalen Fragebogen aus. Für ein Gespräch mit Rückfragen nutze `resources/INTERVIEW.md`. Prüfe danach `profil.json`. Ein vollständiger Gesprächsstand liegt lokal in `interview.json`; unbekannte Antworten sind `null`.

Ein einzelner belegter Fakt kann auch so ergänzt werden:

```sh
python start.py fakt --id projekt-1 --text "Ein internes Projekt koordiniert." --quelle "Eigene bestätigte Angabe, Nachweis wird ergänzt" --stichwort Projektkoordination
```

Die Aussage hier ist ein fiktives Syntaxbeispiel. Verwende sie nur, wenn sie bei dir tatsächlich zutrifft. Kopiere niemals Beispielfakten als eigene Qualifikation.

## 2. Stellen recherchieren

`python start.py suchanfragen` zeigt Suchanfragen für deine Rollen und Region. Diese Ausgabe führt selbst keine Websuche aus. Gib sie deinem Assistenten mit verfügbaren Webwerkzeugen. Prüfe aktuelle offizielle Anzeigen, vollständige Anforderungen und einen offenen Bewerbungsweg. Quellenstand und Gehaltsband gehören zur Bewertung.

Speichere den vollständig gelesenen Anzeigentext als UTF-8-Datei und erfasse eine Stelle:

```sh
python start.py stelle --firma "Beispiel GmbH" --rolle "Projektmanager" --url "https://jobs.example.com/stellen/123" --referenz "123" --textdatei anzeige.txt
```

Die Ausgabe nennt die erzeugte ID `job-…`. Verwende diese konkrete ID in den folgenden Befehlen. ATS-Dubletten bleiben unverändert, einschließlich manuellem Score und Historie. Eine geänderte Anzeige ist separat neu zu prüfen; die Dublettenerkennung überschreibt den gespeicherten Text nicht stillschweigend.

## 3. Bewerten

Lass den Assistenten Aufgaben, fachliche Erfahrung, Muss-Kriterien, Arbeitsmodell, Seniorität und Gehalt gegen deine Profilfakten prüfen. Nutze deine persönlichen Prioritäten aus `preferences`. Dokumentiere Lücken ebenso wie Fit. Ein unbekanntes Gehaltsband bleibt offen.

```sh
python start.py bewerten DEINE-ID --score 75 --grund "Aufgaben passen zu belegten Projekten; Arbeitgeberbudget noch offen"
python start.py wortabgleich DEINE-ID
```

Ersetze `DEINE-ID` durch die ausgegebene ID. Der Wortabgleich zählt nur explizit hinterlegte Fakten-Stichwörter. Er misst keine Einstellungswahrscheinlichkeit und vergibt ohne Stichwörter keinen Score. Er verändert deinen manuellen Score nicht.

## 4. Unterlagen und Prüfung

Lass einen individuellen Anschreibentext anhand der Anzeige und Fakten-IDs entwerfen. Speichere ihn als Textdatei. Das Werkzeug schreibt keine erfundenen Qualifikationen hinzu:

```sh
python start.py entwurf DEINE-ID --textdatei anschreiben.txt --fakt projekt-1
python start.py anschreiben DEINE-ID
python start.py lebenslauf
```

DOCX-Dateien liegen in `dokumente`. Vorhandene Dateien werden nicht überschrieben; weitere Fassungen erhalten automatisch `-v2`, `-v3` und so weiter. Der einfache Lebenslauf enthält die belegten Fakten. Individuelle Gliederung und sprachliche Überarbeitung erfolgen anschließend mit deinem Assistenten oder Textprogramm. Prüfe Seitenumbrüche und Darstellung selbst.

Mit `--pdf` wird zusätzlich ein lokal installiertes LibreOffice genutzt. Es gibt keinen Online-Konverter. Prüfe danach die tatsächliche PDF. Belege/Nachweise hängst du entsprechend Arbeitgebervorgaben selbst an; das Grundprogramm stellt keine automatisch vollständige Anlagenmappe her.

Prüfe zwei Dinge: Inhalt gegen Profil/Anzeige, dann die tatsächlich erzeugten Dokumente. Halte deine Prüfergebnisse fest:

```sh
python start.py pruefung DEINE-ID --inhalt "Fakten-IDs und Anforderungen selbst geprüft" --dokument "Erzeugtes DOCX geöffnet, Inhalt und Seitenformat geprüft"
python start.py ereignis DEINE-ID --status vorbereitet --datum 2026-01-15 --grund "Entwurf und Dokument gegengeprüft"
```

Datum durch dein tatsächliches Datum ersetzen. Die Prüfnotizen dokumentieren deine Prüfung; sie führen sie nicht automatisch durch. Nach Änderungen an Profil, Entwurf oder Anzeige ist eine erneute Prüfung erforderlich.

## 5. Einreichen und Rückmeldungen

Du sendest selbst. Erst danach erfasst du den tatsächlich geprüften Beleg, zum Beispiel eine Bestätigungsseite oder Original-E-Mail:

```sh
python start.py ereignis DEINE-ID --status beworben --datum 2026-01-16 --beleg bestaetigung.txt --grund "Diese konkrete Stelle wurde eingereicht; Inhalt der Bestätigung geprüft" --message-id receipt-123
```

Statuswerte: `recherche`, `vorbereitet`, `beworben`, `interview`, `angebot`, `absage`, `zurueckgezogen`. Auswahlstatus benötigen einen Beleg. Die CLI prüft Datei und Hash; die Wahrheit und eindeutige Zuordnung prüfst du. Eine allgemeine Kontoanlage oder Budgetantwort reicht nicht.

Für Mails nutze die echte Message-ID, nicht den Betreff. Bei mehreren Rollen reicht der Firmenname nicht. Falls Rolle/Referenz/Thread nicht eindeutig sind, halte den Fall separat offen. Trage ihn nicht vorschnell bei einer bestehenden Bewerbung ein. Versuche niemals dieselbe Nachricht auf zwei Rollen zu verteilen.

Alte Ereignisse können später erfasst werden. `occurred_on` ist das tatsächliche Ereignisdatum, `recorded_at` die heutige Erfassung. Ältere Eingänge überschreiben keine jüngeren Absagen. Bei gleichem Tagesdatum bleibt die fortgeschrittenere Auswahlentscheidung maßgeblich; komplizierte Rücknahmen am selben Tag musst du gesondert klären.

## 6. Bericht und Chat-Projekt

```sh
python start.py bericht
python start.py chat-export
```

Der Bericht erzeugt Markdown und CSV. Der Chat-Export enthält vier ausdrücklich ausgewählte Projektdateien, keine Originalbelege, E-Mailtexte oder Anhänge. Trotzdem enthält er persönliche Profilangaben. Prüfe alle Texte und Stellenlinks vor einem Upload. Chats verändern deine lokalen Daten nicht von selbst; sichere zurückgegebene Aktualisierungen bewusst.
