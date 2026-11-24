# Mithelfen

Fehlerberichte und Verbesserungen sind willkommen. Nutze ausschließlich fiktive Beispiele. Persönliche Profile, Bewerbungen, Mails, Belege, Browserdaten und Secrets gehören nie in einen Commit, Pull Request oder Issue.

Für Änderungen an Einrichtung oder Speicherung müssen bestehende Arbeitsordner unverändert bleiben. Neue Statuslogik braucht einen Test gegen falsche Zuordnung und historische Nachträge. Unterstützte Python-Version ist mindestens 3.11; Zusatzabhängigkeiten nur mit nachvollziehbarem Nutzen.

Vor einem Pull Request:

```sh
python -m unittest discover -s tests -v
python scripts/check_public.py
python scripts/smoke.py
```

Beschreibe den konkreten Fehler, die Änderung und die Prüfung. Nenne Grenzen offen. Keine automatisch versendenden Mail-/Bewerbungsfunktionen und keine Annahme von Kontenzugängen oder kostenpflichtigen Werkzeugen.
