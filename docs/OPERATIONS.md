# Betrieb

Kein Deploy und kein Serverbetrieb. Das Werkzeug läuft lokal mit Python ab 3.11. Es öffnet keinen Netzwerkport und richtet keine geplanten Aufgaben ein. Beenden mit Strg+C; ein unterbrochenes Interview lässt sich fortsetzen.

Öffentlicher Quellcode und persönlicher Arbeitsordner sind getrennt. Der Installer legt einen neuen externen Ordner an. Dateimodi schränken auf unterstützenden Systemen den Zugriff ein; sie ersetzen keine Festplattenverschlüsselung, Backups oder Betriebssystemberechtigungen.

Tests: `python -m unittest discover -s tests -v`. Prüfung des öffentlichen Lieferumfangs: `python scripts/check_public.py`. Installation aus sauberem Archiv: `python scripts/smoke.py`. Release-ZIP: `python scripts/package_release.py PFAD.zip`. Kein Upload persönlicher Arbeitsdaten als Release-Anhang.

Versionen sind auf GitHub gekennzeichnet. Die persönliche Installation aktualisiert sich nicht selbst. Vor einem Update sichern; Anleitung in INSTALLATION.md. Profil, Interview, Bewerbungsstand, Belege und Originalunterlagen erhalten.
