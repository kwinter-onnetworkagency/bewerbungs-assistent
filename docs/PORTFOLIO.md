# Dein persönliches Portfolio mit Cloudflare Pages

Der Wizard fragt einmal: **Möchtest du auch ein persönliches Portfolio erstellen?** Mit **Ja** entsteht in deinem persönlichen Arbeitsordner eine lokale Startseite mit deinem Namen. Mit **Nein** geht es direkt mit den Bewerbungen weiter.

## 1. Seite vorbereiten

Öffne `portfolio/public/index.html` per Doppelklick. Sag deinem Assistenten zum Beispiel: „Ergänze mein Kurzprofil und die beiden Arbeitsproben, die ich für die Veröffentlichung ausgewählt habe.“ Prüfe Namen, Bilder, verlinkte Dokumente und die Seite im Browser. In einem reinen Chat-Projekt lässt du dir die fertige `index.html` als Datei geben und speicherst sie in einem eigenen Ordner `portfolio/public`.

**Alles im Upload-Ordner wird öffentlich abrufbar**, auch unverlinkte Dateien. Lege dort nur die freigegebene Seite und ihre öffentlichen Bilder oder Dokumente ab. Bewerbungsdashboard, Nachweise, Postfachdaten und Zugangsdaten gehören in den privaten Arbeitsordner.

## 2. Kostenloses Konto und erste Webadresse

1. Erstelle bei Cloudflare ein Konto mit deiner E-Mail-Adresse und bestätige die Bestätigungsmail. Für ein statisches Portfolio reicht der kostenlose Tarif **Free**. [Konto erstellen](https://dash.cloudflare.com/sign-up) · [Pages Free und Tarifgrenzen](https://developers.cloudflare.com/pages/platform/limits/)
2. Öffne im Dashboard **Workers & Pages → Create application**. Wähle **Pages** und den **Direct Upload** per Drag-and-drop. Gib deinem Projekt einen Namen.
3. Ziehe ausschließlich den Ordner `portfolio/public` in das Upload-Feld. Die `index.html` muss direkt auf der obersten Ebene liegen. Prüfe die Dateiliste und klicke selbst auf **Deploy**.
4. Öffne die von Pages angezeigte HTTPS-Adresse in einem privaten Browserfenster. Prüfe Startseite, Bilder, Downloads und Links. Diese Adresse kannst du bereits in deine Bewerbungen aufnehmen. [Cloudflare Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)

## 3. API-Token für spätere Uploads

Beim Upload im Browser genügt die Anmeldung. Möchtest du später mit dem Cloudflare-Werkzeug **Wrangler** veröffentlichen, erstelle einen eingeschränkten **API-Token**. Cloudflare unterscheidet ihn vom kontoweit nutzbaren „Global API Key“.

1. Öffne **API Tokens → Create Token → Custom Token**. Gib dem Token einen verständlichen Namen, etwa „Portfolio Pages“.
2. Wähle unter **Permissions** die Berechtigung **Account → Cloudflare Pages → Edit**. Begrenze den Token auf dein Cloudflare-Konto. Für den Datei-Upload genügen die Pages-Rechte. Domainregistrierung und DNS richtest du im Dashboard ein.
3. Prüfe die Zusammenfassung, erstelle den Token und sichere den einmal angezeigten Wert im Passwortmanager. Gib ihn weder in den Bewerbungswizard noch in einen Chat ein. [Token für Pages erstellen](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/)
4. Stelle Wrangler den Token über die geheime Umgebungsvariable `CLOUDFLARE_API_TOKEN` und die Konto-ID über `CLOUDFLARE_ACCOUNT_ID` bereit. Die Konto-ID findest du im Cloudflare-Dashboard. Im persönlichen Arbeitsordner lädt der folgende Befehl den ausgewählten Ordner zu deinem **bereits angelegten** Projekt hoch. Ersetze `DEIN-PROJEKTNAME` durch den Namen aus Pages. Führe ihn erst aus, wenn du diese Fassung veröffentlichen willst.

```sh
npx wrangler pages deploy portfolio/public --project-name DEIN-PROJEKTNAME
```

## 4. Eigene Domain auswählen

| Was möchtest du? | So gehst du vor |
|---|---|
| Ohne zusätzliche Kosten starten | Verwende die von Pages angezeigte Adresse. Du kannst später eine Domain verbinden. |
| Eine neue Domain kaufen | Suche beim Registrar nach deinem Wunschnamen. Prüfe Erstpreis, Verlängerungspreis, Vertragslaufzeit und automatische Verlängerung. Schließe den Kauf selbst ab und bestätige die Registrierungs-E-Mail. Die Domain kostet separat. |
| Eine vorhandene Domain verwenden | Behalte sie beim bisherigen Registrar. Gehe für die Hauptdomain zu Schritt 5 oder für eine einzelne Subdomain zu Schritt 6. |

Für den Kauf über **Cloudflare Registrar** öffne im Dashboard **Register domains**, suche den gewünschten Namen und wähle **Purchase**. Prüfe Laufzeit, Gesamtpreis und Kontaktdaten. Erst **Complete purchase** löst die kostenpflichtige Bestellung aus. Nach dem Kauf ist Cloudflare bereits als DNS-Anbieter eingetragen. Verbinde die Domain direkt in Pages unter **Custom domains**. Bei einem Kauf bei einem anderen Registrar folge für die Hauptdomain Schritt 5. [Domain bei Cloudflare registrieren](https://developers.cloudflare.com/registrar/get-started/register-domain/)

## 5. Hauptdomain mit externem Registrar verbinden

Beispiel: Das Portfolio soll direkt unter `example.org` erreichbar sein. Der Registrar verwaltet den Domainvertrag. Die Nameserver legen fest, welcher Anbieter die DNS-Einträge für Website, Subdomains und E-Mail ausliefert.

1. Füge die Domain in deinem Cloudflare-Konto hinzu und wähle den Free-Tarif. Cloudflare nennt dir **zwei konkrete Nameserver für diese Domain**. Notiere auch die bisherigen Nameserver.
2. Exportiere oder sichere beim bisherigen DNS-Anbieter die vorhandenen Einträge. Vergleiche sie mit dem Import bei Cloudflare und ergänze fehlende Einträge, insbesondere MX, SPF, DKIM und DMARC für E-Mail sowie bestehende Subdomains. Der automatische Scan kann Einträge übersehen.
3. Ist DNSSEC beim bisherigen Anbieter aktiv, deaktiviere es nach dessen Anleitung und entferne den bisherigen DS-Eintrag beim Registrar. Warte, bis der alte DS-Eintrag öffentlich nicht mehr aufgelöst wird. Ein veralteter DS-Eintrag kann die gesamte Domain unerreichbar machen.
4. Öffne **beim Registrar** die Nameserver-Einstellungen der Domain. Ersetze dort die bisherige Delegation durch genau die beiden Werte aus Cloudflare und speichere. Die Delegation wird beim Registrar geändert, nicht als gewöhnlicher DNS-Eintrag in der Zone.
5. Warte, bis Cloudflare die Domain als **Active** meldet. Verbinde sie in **Workers & Pages → dein Pages-Projekt → Custom domains → Set up a domain**. Prüfe bestehende Einträge am gewünschten Hostnamen, bevor du ihn auf das Portfolio umstellst. Eine dort laufende Website würde dadurch ersetzt.
6. Prüfe Portfolio, bestehende Subdomains und E-Mail-Funktion. Wenn du vorher DNSSEC verwendet hast, aktiviere es bei Cloudflare wieder und hinterlege die neuen DS-Daten nach Anleitung beim Registrar. [Nameserver umstellen](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/) · [Eigene Domain in Pages](https://developers.cloudflare.com/pages/configuration/custom-domains/)

## 6. Nur eine Subdomain verwenden

Für `portfolio.example.org` kannst du die Nameserver beim bisherigen DNS-Anbieter belassen. Füge **zuerst** die Subdomain im Pages-Projekt unter **Custom domains** hinzu. Lege dann beim bisherigen DNS-Anbieter für `portfolio` den angeforderten **CNAME** auf die tatsächliche Pages-Adresse an, ohne `https://` oder Pfad. Warte auf die Aktivierung und das Zertifikat. Öffne die neue HTTPS-Adresse und teste die Arbeitsproben, bevor du sie in Lebenslauf oder Anschreiben einträgst. [Cloudflare-Anleitung für Subdomains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
