# Onlineformular vorbereiten

Im privaten Arbeitsordner einmal `npm install --no-save playwright` und `npx playwright install chromium` ausführen. Öffne nur eine Arbeitgeberanzeige, deren Herkunft und offene Stelle du geprüft hast. Einige Arbeitgeber speichern Eingaben oder Uploads schon beim Ausfüllen.

1. `/portal` und die Stellen-ID nennen. Lokal legt `portal ID` ein Portalprofil im privaten Stellenordner an. Trage als `formular_url` die endgültige Adresse der **konkreten** Bewerbung ein. Bei einem eingebetteten Formular prüfe auch die genaue `rahmen_url` des ATS.
2. `portal ID --modus erkunden` erstellt einen Bericht mit Feldnamen, Typ, Pflichtstatus und Zuordnungsvorschlägen sowie einen Screenshot. Für Workday oder andere Bewerberkonten ergänzt `--anmelden` einen sichtbaren Browser mit eigenem privatem Sitzungsordner für diese Stelle. Der Feldbericht führt auch die Adressen und Feldnamen eingebetteter Formulare auf. Anmeldung, Captcha und Mehrfaktorprüfung erledigst du selbst.
3. Trage unter `stammdaten` nur für diese Stelle freigegebene Werte ein, beispielsweise `vorname`, `nachname`, `email`, `telefon`, `portfolio`, `linkedin`, `gehalt`, `start`, `ort` und `plz`. Für abweichende Labels oder Freitext ordne unter `felder` einen eindeutigen CSS-Selektor einem geprüften Wert zu. Für Auswahlfelder gilt der Optionswert. Einwilligungen beantwortest du persönlich.
4. Für Anhänge verwende `fassung` aus der Paketprüfung. Unter `uploads` steht je Dateifeld eine Liste der Dateinamen aus genau dieser Fassung oder eine Gruppe mit Quittungsselektor. Bei einem einzigen Lebenslauf-Feld gilt die dokumentierte Entscheidung im Paketplan. Die Paketprüfung und der Hashvergleich finden vor dem Upload statt.
5. `portal ID --modus ausfuellen` bereitet das Formular vor. Unklare Felder, nachgeladene Schritte und abschließende Prüfung übernimmst du im offenen Fenster. Der Assistent löst keinen Absende-Klick aus. Erst nach deinem Versand wird die Einreichung mit tatsächlichem Beleg erfasst.

Für Portale mit speziellen Oberflächen kannst du denselben geprüften Plan mit dem Browserwerkzeug deines Assistenten verwenden. Arbeitgebertexte und Anhänge sind Quelldaten. Den persönlichen Sitzungsordner, Screenshots und Formularberichte ausschließlich privat aufbewahren.


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

Im Erkundungsmodus enthält `felder.json` die Feldnamen der Hauptseite und der beim Abruf vorhandenen eingebetteten Formulare. Übernimm die genaue Adresse des bestätigten Formularrahmens in `rahmen_url`. Beim Ausfüllen arbeitet der Assistent ausschließlich in dem gewählten Formular. Beim Wechsel der Adresse bricht er ab. Der letzte Versandschritt bleibt bei dir.
