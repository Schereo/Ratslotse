---
kategorie: behoben
---

**„database is locked" bei gleichzeitigen Anfragen.** Jede Anfrage baut ihren Datenbank-Zugriff neu auf und ließ dabei die Werte-Migrationen noch einmal laufen — Dutzende `UPDATE`-Anweisungen ohne Treffer, von denen sich trotzdem jede die Schreibsperre der Datei holte (41 je Anfrage an der Konten-Datenbank, 385 an der Rats-Datenbank). Eine reine Leseanfrage war damit ein Schreiber, und wenn Startseite und Admin-Panel gleichzeitig luden, lief ein Teil der Anfragen nach fünf Sekunden Wartezeit in den Fehler. Die Migrationen fragen jetzt erst lesend nach, ob es etwas umzuschreiben gibt, und schreiben nur dann; ein Wächter-Test öffnet beide Stores neben einem laufenden Schreiber.
