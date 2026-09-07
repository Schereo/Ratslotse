---
kategorie: hinzugefuegt
---

**Ein Ausfall meldet sich jetzt von selbst.** Bricht der Prod-Deploy ab, bleibt die Wartungsbarriere absichtlich stehen — die Seite ist dann für Angemeldete unten, bis jemand eingreift. Bisher stand das nur als roter Eintrag in einer Liste, in die man schauen muss: Am 07.09.2026 hat es deshalb 74 Minuten niemand erfahren. Jetzt schickt der Deploy im Fehlerfall eine Mail mit dem Zustand der Barriere und der Dienste. Zusätzlich pingt ein Workflow alle zehn Minuten von außerhalb des Servers die Startseite und die Gesundheitsprüfung an und schlägt Alarm, wenn dreimal hintereinander nichts zurückkommt.
