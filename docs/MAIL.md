# Bewerbungsrückmeldungen und Ablage

Mit `/mail` startest du den Abgleich in deinem Assistenten. Lege im Interview fest, welche persönlichen Konten er lesen darf, wohin vollständig erfasste Nachrichten gehören und welche Mails im Posteingang bleiben. Ein zurückgestellter Entwurf ist keine Versandaufgabe. Notiere eine Frist erst, wenn sie aus der Nachricht hervorgeht.

## Quellen beschaffen

Unter macOS zeigt `apple-mail konten` die in Apple Mail eingerichteten Konten und `apple-mail ordner --konto NAME` deren Ordner. Beim ersten Zugriff kann macOS nach der Berechtigung zur Steuerung von Mail fragen. Suche die tatsächlichen Namen des Posteingangs, des Gesendet-Ordners und deines Ablageordners. Für jeden freigegebenen Ordner einzeln abrufen. Beispiel für den Aufruf aus einem persönlichen Arbeitsordner:

```sh
npx github:kwinter-onnetworkagency/bewerbungs-assistent#v0.6.0 run apple-mail abruf --konto Privat --ordner INBOX --seit 2026-01-15T09:00:00+01:00
```

Ersetze Datum, Ordner und Konto durch deinen letzten belegten Abgleich. Apple Mail öffnet sich und fordert neue Nachrichten an. Das private Manifest verzeichnet die lokal gelesenen Originale, Message-IDs und Abruffehler. Ein vollständiger Serverabgleich kann nach dem Anfordern noch ausstehen. Ohne Apple Mail kannst du auf allen Plattformen eine Originalnachricht als EML exportieren.

## Ergebnis und nächster Schritt

Lies den vollständigen Inhalt und prüfe die Stelle anhand von Referenz, Einreichungsbeleg oder Originalthread. `mail-erfassen DATEI.eml --art eingang --stelle JOB-ID --grund "…" --konto Privat --ablage INBOX` zeichnet eine Eingangsbestätigung auf. Für eine ungeklärte Zuordnung verwende `--art ungeklaert` ohne Stellen-ID. Eine spätere eindeutige Erfassung derselben Nachricht löst den offenen Fall auf. Die Auswahlentscheidung und der Eingang erscheinen getrennt im Dashboard. Stelle bei eigener Korrespondenz `--richtung eigen` und bei Begleitnachrichten `--richtung service` ein.

Mit `--schuetzen` kennzeichnest du eine Mail, die im Posteingang bleiben soll. Mit `--schritt` dokumentierst du die nächste Handlung zur Nachricht. Für dauerhafte Aufgaben verwende `notiz --art aufgabe`. Eine Kontakt- oder Budgetanfrage erhält die Art `kontakt`. Eine unterschriebene Rücksendung oder tatsächliche Einreichung erfordert einen separaten Beleg.

## Ablage und Entwürfe

`apple-mail ablegen` erwartet Quellkonto und Quellordner, Message-ID, Zielkonto und Zielordner. Der Befehl prüft die Zuordnung, geschützte Nachrichten, das gelesene Original und bestehende Zielkopien. Er bestätigt den Umzug durch Rücklesen im Ziel. Bei widersprüchlichen Kopien klärst du die Ablage in Mail.

Für eine ausdrücklich gewünschte Antwort nutzt `apple-mail entwurf` die Originalnachricht, einen Absender, der zum gewählten persönlichen Konto gehört, und deinen Text aus `--textdatei`. Prüfe den gespeicherten Entwurf vor dem Versand in Apple Mail. Die vollständigen Optionen stehen unter `apple-mail entwurf --help`.

## Zwischenbericht und Tagesbericht

`mailbericht --abdeckung "…"` schreibt einen Zwischenbericht unter `exports/`. Nenne tatsächlich gelesene Konten, Ordner, Zeitraum und Lücken. `--vollstaendig` setzt die ausdrückliche Bestätigung des geprüften Umfangs voraus. `--tag` erstellt den Tagesbericht, `--zone` setzt die IANA-Zeitzone (Standard Europe/Berlin). Fehlen dem System Zeitzonendaten, installiere das Python-Paket tzdata oder verwende ausdrücklich UTC. Der Bericht unterscheidet heutige Arbeitgebermails, eigene Antworten, Servicenachrichten, ältere Nachträge und Ablageänderungen. Zuordnungen und offene Aufgaben werden über Berichte hinweg fortgeführt. Message-IDs und Belege bleiben im privaten Ordner.

Den persönlichen Zeitplan richtest du in der Aufgabenfunktion deines Assistenten ein. [Routinen einrichten](ROUTINEN.md)

Der Apple-Mail-Adapter liest die von Apple Mail gelieferte Textrepräsentation. Seine Hash-Prüfung vergleicht zwei Abrufe über denselben Adapter. Für eine Prüfung der Transportbytes oder einer kryptografischen Mailsignatur verwende das dafür exportierte Original. Ein bereits zugeordneter Originalbeleg lässt sich durch erneute Erfassung derselben Nachricht nachträglich schützen.
