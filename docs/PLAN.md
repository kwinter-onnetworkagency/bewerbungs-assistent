# Öffentliche Startversion

Ziel: Anderen Stellensuchenden denselben belegorientierten Bewerbungsablauf zugänglich machen. Persönlicher Zuschnitt entsteht im Interview, nicht durch feste Kandidatenwerte.

Entscheidung: unabhängiges Repository mit neuer Historie, Python ab 3.11 und Standardbibliothek. Ein vollständiger Export des privaten Ursprungsprojekts würde Bewerbungsdaten und lokale Kontenbindungen enthalten. Deshalb werden Prozess und überprüfbare Kernfunktionen als neutrale, portable Fassung umgesetzt. Produktcode und Quellen werden nicht mit persönlichen Beispieldaten vermischt.

1. Einrichtung und Interview: neuer externer privater Ordner, alle vier Assistentenwege, Fortsetzung, offene Antworten, ausdrückliche Profilprüfung. Tests für Abbruch, vorhandene Ordner, Git-Verzeichnisse und Wiederaufnahme.
2. Bewerbungsworkflow: belegte Fakten, aktuelle Anzeigentexte, ATS-Deduplizierung, manuelle Scores, Entwürfe, zwei Prüfnotizen und Ereignisse mit Datum/Beleg/Message-ID. Tests für Statusbelege, falsche Zuordnung, historische Nachträge, geändertes Profil und Symlinks.
3. Auslieferung: DOCX, optional lokale PDF-Konvertierung, Markdown/CSV und Chat-Projektdateien mit Installationsanleitung. Tests für A4-XML, Ausgabegrenzen, Formelzellen und Export-Allowlist.
4. Veröffentlichung: Quellcodeprüfung, Installation aus sauberem Archiv, Betriebssystem-/Python-Matrix in GitHub Actions, frisches unabhängiges Review, Releaseprüfung und erst danach öffentliche Sichtbarkeit.

Der Assistenten-Upload und echte Mail-/Browserzugänge sind nutzerabhängig. Einrichtung und Nutzung dieser externen Oberflächen werden dokumentiert, nicht als automatisch getestet ausgegeben.
