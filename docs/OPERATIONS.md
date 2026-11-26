# Betrieb

Kein Deploy und kein Serverbetrieb. Der npx-Dialog läuft mit Node.js ab 20, die lokalen Dokument- und Trackingbefehle mit Python ab 3.11. Es öffnet keinen Netzwerkport und richtet keine geplanten Aufgaben ein. Beenden mit Strg+C; ein unterbrochenes Interview lässt sich fortsetzen.

Öffentlicher Quellcode und persönlicher Arbeitsordner sind getrennt. Der Installer legt einen neuen externen Ordner an. Dateimodi schränken auf unterstützenden Systemen den Zugriff ein; sie ersetzen keine Festplattenverschlüsselung, Backups oder Betriebssystemberechtigungen.

Tests: `python -m unittest discover -s tests -v`. Prüfung des öffentlichen Lieferumfangs: `python scripts/check_public.py`. Installation aus sauberem Archiv: `python scripts/smoke.py`. Release-ZIP: `python scripts/package_release.py PFAD.zip`. Kein Upload persönlicher Arbeitsdaten als Release-Anhang.

Versionen sind auf GitHub gekennzeichnet. Die persönliche Installation aktualisiert sich nicht selbst. Vor einem Update sichern; Anleitung in INSTALLATION.md. Profil, Interview, Bewerbungsstand, Belege und Originalunterlagen erhalten.

Vor einer eigenen Veröffentlichung zusätzlich eine private Begriffsliste außerhalb des Repositories anlegen und über BEWERBUNG_PRIVATE_TERMS an check_public.py übergeben. Die generische Prüfung erkennt nicht beliebige Personendaten. Der Git-Index wird ebenfalls gegen die Allowlist geprüft; neue Geheimnisse in ausgeschlossenen, aber versehentlich getrackten Ordnern werden abgewiesen.

Für PDF-Export und Paketprüfung siehe DOKUMENTE.md und ANLAGEN.md. Für die optionale Portalvorbereitung wird Playwright mit Chromium im persönlichen Ordner eingerichtet. Das optionale Portfolio kann auf Cloudflare Pages hochgeladen werden. Private Quellen, Zugangsschlüssel und der gesamte persönliche Arbeitsordner gehören ausschließlich auf das eigene Gerät bzw. in ein privates Backup. Veröffentliche nur den vorgesehenen Ordner portfolio/public. Die lokale Installation benötigt für die Kernfunktionen keinen Server.

Mit `python scripts/release_assets.py NEUER_RELEASEORDNER` aus einem sauberen Quellstand entstehen die Installations-ZIP, die portable Dashboard-Datei, ein fiktives Beispiel mit den verlinkten Übersichten und SHA-256-Prüfsummen. Veröffentliche die Dateien am GitHub-Release für dieselbe Version.
