# Routinen und Kontoverbindungen

Das Interview fragt nach deinen gewünschten Quellen, Mailkonten, Ordnern, geschützten Nachrichten, Berichtstakten und der Zeitzone. Damit stehen die persönlichen Regeln fest. Ein gewünschter Zeitplan ist erst aktiv, nachdem du ihn in einem tatsächlich verfügbaren Werkzeug angelegt und kontrolliert hast.

## Stellensuche

`python start.py routine stellensuche` zeigt eine neutrale Vorlage. Kombiniere sie mit deinen Regeln aus `profil.json`. Wenn dein Assistent geplante Aufgaben unterstützt, beauftrage ihn, eine Routine mit deinem Zeitplan einzurichten. Lass dir den angelegten Eintrag zeigen. Ohne diese Funktion kannst du den Suchauftrag selbst starten.

Die Routine liest Profil und bisherigen Stand, recherchiert aktuelle offizielle Anzeigen, vermeidet Dubletten und empfiehlt passende Stellen. Sie erstellt keine Bewerbungen allein aufgrund eines Suchtreffers. Fehlende Webwerkzeuge und Zugangsfehler müssen im Bericht stehen.

## Rückmeldungen

`python start.py routine rueckmeldungen` zeigt die Vorlage. Verbinde zuerst selbst ein Mailwerkzeug für deine persönlichen Konten. Welche Anbieter und Betriebssysteme unterstützt sind, hängt vom gewählten Assistenten und der Integration ab. Hier werden weder Apple Mail noch Outlook, Gmail oder ein fremdes Postfach automatisch angebunden.

Lass tatsächliche Konten und Ordner entdecken. Prüfe mindestens eine bekannte Mail als Gegenprobe. Lege fest, ob Nachrichten abgelegt werden dürfen und was im Posteingang bleiben muss. Nach einer erlaubten Verschiebung dieselbe Message-ID im Ziel prüfen. Unklare Vorgänge und persönliche Ausnahmen unverändert lassen.

Ein Mailabruf ist nicht automatisch eine vollständig bestätigte Serversynchronisation. Der Bericht muss lokale Daten, gelesene Inhalte und Serverbestätigung auseinanderhalten. Keine Mails senden, löschen oder Termine zusagen. Antworten entstehen nur als beauftragte Entwürfe im richtigen persönlichen Originalthread.

## Kein Zugang

Du kannst relevante Originalmails oder deren vollständigen Inhalt selbst bereitstellen. Der Assistent wertet dann diese Quellen aus. Er darf daraus keinen vollständigen Kontenabgleich behaupten. Persönliche Links, Codes und Anhänge gehören nicht in öffentliche Issues oder Beispieldaten.

## Einen persönlichen Tagesplan einrichten

Beispiel für die Aufgabenfunktion deines Assistenten: „Prüfe meine persönlichen Bewerbungspostfächer täglich um 09:00, 12:00, 15:00 und 18:00 Uhr Europe/Berlin gemäß der Vorlage Rückmeldungen. Nutze den letzten vollständigen Prüfzeitpunkt als Beginn. Erstelle zu den ersten drei Zeiten einen Zwischenbericht und um 18:00 Uhr den Tagesbericht.“ Ersetze den Beispielplan durch deinen Interviewstand. Lege die Stellensuche separat an, damit du sie bei einem Angebot beenden und die Rückmeldungen zu laufenden Bewerbungen weiter prüfen kannst.

Kontrolliere mit der Aufgabenliste Name, Aktivierung, Zeitzone und nächsten Lauf. Prüfe beim ersten Lauf, ob das ausführende Gerät tatsächlich den privaten Ordner und die freigegebenen Konten erreicht. Ein Chat ohne diese Verbindung kann bereitgestellte EML-Dateien auswerten. Ein lokaler macOS-Durchlauf kann mit dem mitgelieferten Apple-Mail-Adapter arbeiten. [Abruf und Bericht](MAIL.md)
