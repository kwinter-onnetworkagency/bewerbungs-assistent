# Aufbau

Der öffentliche Quellcode enthält ausschließlich Programmcode, neutrale Vorlagen und fiktive Beispiele. Die Einrichtung kopiert die benötigten Dateien in einen neuen persönlichen Ordner außerhalb jedes Git-Repositories. Das Originalprojekt und dessen Historie werden nicht kopiert.

`setup.py` richtet diesen Ordner ein. `interview.py` fragt den persönlichen Zuschnitt ab und hält einen unterbrechbaren Interviewstand. `core.py` verwaltet Profilfakten, eindeutige Stellen, manuelle Bewertungen, Entwürfe, Prüfnotizen und belegte Ereignisse. `documents.py` erstellt einfache DOCX-Dateien. `export.py` liefert Markdown, CSV und vier gezielt ausgewählte Dateien für Chat-Projekte. `cli.py` verbindet die Befehle.

Es gibt keine Netzwerkbibliothek, API-Schlüssel, laufenden Dienste, Telemetrie oder automatischen Versand. Recherche und intelligente Gesprächsführung finden mit den vom Nutzer tatsächlich verfügbaren Werkzeugen in Claude, ChatGPT oder einem lokalen Coding-Assistenten statt. Das lokale Interview ist zusätzlich ohne KI-Zugang nutzbar.

Profilfakten sind die einzige Quelle für Qualifikationen. Das Interview unterscheidet Nutzerangaben von unabhängig bereitgestellten Nachweisen. Arbeitsregeln liegen in `preferences`; feste persönliche Gehalts-, Wohnort-, Abschluss- oder Mailkontenvorgaben gibt es nicht. Der Assistent lässt das Ergebnis vor Nutzung gegenlesen.

Ein neuer Stellenlink erzeugt eine stabile Kennung. Für bekannte ATS werden alternative Hostnamen und gleiche Stellen-IDs vereinheitlicht. Sonst werden relevante URL-Parameter erhalten oder eine ausdrücklich genannte Arbeitgeber-/Referenzkombination verwendet. Eine weitere Rolle beim selben Arbeitgeber bleibt zulässig.

Dateischreibvorgänge erfolgen mit Prozesssperre und atomarem Dateiersatz. Ein zweiter Schreibprozess bricht ab. Ein Entwurf ist keine Einreichung. Ereignisse benötigen Datum, Zuordnungsgrund und bei Auswahlstatus einen geprüften Beleg. Die CLI prüft Belegvorhandensein und Hash, nicht dessen semantische Wahrheit. Nachrichtendubletten werden anhand Message-ID erkannt. Historische Nachträge ersetzen neuere Auswahlentscheidungen nicht. Bei gleichem Tagesdatum bleibt konservativ die fortgeschrittenere Entscheidung maßgeblich; eine spätere Rücknahme am selben Tag muss vor Erfassung fachlich geklärt werden.

Prüfnotizen werden an Profil, Anzeigeninhalt und Entwurf gebunden. Eine spätere Änderung macht die Freigabe zum Status `vorbereitet` ungültig. Die Dokumentprüfung selbst führt der Nutzer mit seinem Assistenten durch.

Bewusste Grenzen: kein ATS-Autofill, keine Kontenanmeldung, kein Mailadapter, kein Kalenderadapter und keine automatisch angelegten Hintergrundroutinen. Dafür werden neutrale Arbeitsanweisungen mitgeliefert. Anbieter-/Betriebssystemzugriff lässt sich ergänzen, ohne den portablen lokalen Kern zu verändern.

Chat-Dateien sind mit export_only gekennzeichnete Ansichten. Die lokale Profil-/Arbeitsstandvalidierung lehnt sie als Ersatz für vollständige Originaldateien ab. Änderungen werden gezielt übernommen. Belegart und ursprüngliche Faktenherkunft bleiben im Export sichtbar; lokale Quellenorte bleiben zurück. Bereits bekannte Bewerbungen werden als ungeprüfte Hinweise mitgegeben.

Das Interview verwendet inhaltsbezogene Fakten-IDs. Noch in einem aktuellen Entwurf verwendete Fakten dürfen bei erneuter Übernahme nicht verschwinden. Leere neue Antworten löschen keine bereits geklärten Präferenzen. Ein bei der Ereigniserfassung gesicherter lokaler Entwurfsstand ist ausdrücklich kein Nachweis, dass genau diese Fassung eingereicht wurde; dafür gilt allein der vom Nutzer zugeordnete Originalbeleg.
