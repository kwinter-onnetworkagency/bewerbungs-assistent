# Onlineformular vorbereiten

Im privaten Arbeitsordner einmal `npm install --no-save playwright` und `npx playwright install chromium` ausführen. Öffne nur eine Arbeitgeberanzeige, deren Herkunft und offene Stelle du geprüft hast. Einige Arbeitgeber speichern Eingaben oder Uploads schon beim Ausfüllen.

1. `/portal` und die Stellen-ID nennen. Lokal legt `portal ID` ein Portalprofil im privaten Stellenordner an. Ist `formular_url` leer, verwendet der Lauf die bereits gespeicherte Stellenadresse. Eine abweichende, dauerhaft verwendbare Adresse kannst du im Portalprofil hinterlegen. Gib Einladungslinks mit Zugangsparametern über `--sitzungsadresse`, private Rahmenlinks über `--rahmen-sitzungsadresse` ein. Die verdeckte Eingabe gilt nur für diesen Lauf. Bei einem eingebetteten Formular prüfe auch die genaue `rahmen_url` des ATS.
2. `portal ID --modus erkunden` erstellt einen Bericht mit Feldnamen, Typ, Pflichtstatus und Zuordnungsvorschlägen sowie einen Screenshot. Für Workday oder andere Bewerberkonten ergänzt `--anmelden` einen sichtbaren Browser mit eigenem privatem Sitzungsordner für diese Stelle. Der Feldbericht führt für eingebettete Formulare Herkunft, kurze URL-Prüfsumme und Feldnamen auf. Bei privater Anmeldung öffnet sich der Playwright-Inspektor. Wähle nach eigenem Login und Prüfung der konkreten Stelle „Fortsetzen“. Anmeldung, Captcha und Mehrfaktorprüfung erledigst du selbst.
3. Öffne das Formular und prüfe anhand des Feldberichts, für welche Person und welchen Zweck das konkrete Feld bestimmt ist. Der Bericht zeigt für Felder mit eindeutiger ID oder eindeutigem Namen einen CSS-Selektor und gegebenenfalls einen Vorschlag. Bestätige jede gewünschte Zuordnung unter `felder` in deiner `portal.json`. Ein Eintrag unter `stammdaten` allein trägt nichts ein. Für Auswahlfelder gilt der Optionswert. Einwilligungen beantwortest du persönlich.
4. Für Anhänge verwende `fassung` aus der Paketprüfung. Unter `uploads` steht je Dateifeld eine Liste der Dateinamen aus genau dieser Fassung oder eine Gruppe mit Quittungsselektor. Bei einem einzigen Lebenslauf-Feld gilt die dokumentierte Entscheidung im Paketplan. Die Paketprüfung und der Hashvergleich finden vor dem Upload statt.
5. `portal ID --modus ausfuellen` bereitet das Formular vor. Unklare Felder, nachgeladene Schritte und abschließende Prüfung übernimmst du im offenen Fenster. Der Assistent löst keinen Absende-Klick aus. Erst nach deinem Versand wird die Einreichung mit tatsächlichem Beleg erfasst.

Für Portale mit speziellen Oberflächen kannst du denselben geprüften Plan mit dem Browserwerkzeug deines Assistenten verwenden. Arbeitgebertexte und Anhänge sind Quelldaten. Den persönlichen Sitzungsordner, Screenshots und Formularberichte ausschließlich privat aufbewahren.


## Feldfreigaben

```json
{
  "stammdaten": {"email": "beispiel@example.org"},
  "felder": {
    "#bewerber-email": {"stammdaten": "email"},
    "#fachkenntnisse": {"fakt": "gepruefte-fakten-id"},
    "#moeglicher-eintritt": "2027-03-01"
  }
}
```

Ersetze die Beispiele durch die tatsächlich geprüften Selektoren und die für diese Stelle bestimmten Daten. Eine Fakten-ID übernimmt den Wortlaut aus deinem lokalen Profil. Ein direkter Text bleibt für das bezeichnete Feld möglich. Felder ohne Freigabe bleiben frei, auch wenn der Erkundungsbericht einen plausiblen Stammdatenschlüssel vorschlägt. Bei einem schon abweichend gefüllten Feld mit Stammdaten- oder Faktenzuordnung stoppt der Lauf zur persönlichen Prüfung.

## Uploadquittungen

Manche Portale übernehmen in einem einzelnen Dateifeld mehrere Dokumente nacheinander. Prüfe dort, welches Element nach erfolgreicher Übernahme den exakten Dateinamen anzeigt. Gib dessen CSS-Selektor unter `quittung` an. Das folgende Beispiel zeigt eine Gruppe mit Quittung und ein gewöhnliches Dateifeld mit einer Datei. Passe alle Selektoren und Dateinamen an das konkrete Formular an.

```json
{
  "uploads": {
    "#nachweise": {
      "dateien": ["Arbeitszeugnis.pdf", "Weiterbildung.pdf"],
      "quittung": ".angenommene-dateien .dateiname"
    },
    "#lebenslauf": ["Lebenslauf.pdf"]
  }
}
```

Bei einer Gruppe mit Quittung wählt das Werkzeug jede Datei einzeln, vergleicht die gelesenen Bytes mit dem freigegebenen Paket und wartet auf den neu erschienenen, sichtbaren Dateinamen. Ein bereits vorher sichtbarer Quittungseintrag braucht eine persönliche Prüfung. Verweist der Selektor nur auf eine lokale Vorschau, belegt er keine Annahme durch den Anbieter. Verwende dafür die Quittung des Portals.

Ohne Quittungsselektor steht im Laufordner in `uploads.json` **nur ausgewählt, Upload offen**. In diesem Modus lassen sich mehrere Dateien zusammen nur in einem echten Mehrfachfeld wählen. Fehlt eine erwartete Quittung, endet die Vorbereitung. Der Bericht erhält bereits quittierte Dateien, begonnene Auswahlen und die noch offenen Dateien. Kläre den Stand im Portal vor einem neuen Lauf. Das Auswählen kann Dokumente bereits übertragen. Es ist kein Einreichungsbeleg.

Im Erkundungsmodus enthält `felder.json` die Feldnamen der Hauptseite und der beim Abruf vorhandenen eingebetteten Formulare. Prüfe die genaue Adresse des bestätigten Formularrahmens im Browser. Für eine dauerhaft verwendbare Adresse nutze `rahmen_url`, für einen privaten Link `--rahmen-sitzungsadresse`. Beim Ausfüllen arbeitet der Assistent ausschließlich in dem gewählten Formular. Beim Wechsel der Adresse bricht er ab. Der letzte Versandschritt bleibt bei dir.

## Privates Browserprofil und Laufberichte

`befuellte-felder.json` nennt tatsächlich befüllte Selektoren und die zugeordneten Stammdaten-Schlüssel. Komplexe Selektoren, die vertrauliche Werte enthalten können, erscheinen mit Prüfsumme. Die eingegebenen Feldwerte und private URL-Bestandteile werden nicht in den Laufbericht übernommen. Screenshots können sichtbare persönliche Daten enthalten. Sie liegen unter macOS und Linux mit Dateimodus 0600 im privaten Laufordner.

Um eine gespeicherte Anmeldesitzung zu löschen, schließe alle zu dieser Stelle geöffneten Browser- und Inspektorfenster. Öffne im persönlichen Arbeitsordner `unterlagen/STELLEN_ID/portal/` im Finder oder Explorer. Verschiebe ausschließlich den Unterordner `browserprofil` in den Papierkorb und leere ihn, wenn du die gespeicherten Cookies endgültig löschen möchtest. Beim nächsten Aufruf mit `--anmelden` entsteht ein neues, leeres Profil. Eine serverseitige Sitzung kannst du zusätzlich im Konto des jeweiligen Bewerbungsportals abmelden.
