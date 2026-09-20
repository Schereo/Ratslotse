---
kategorie: behoben
---

**Deploy blockierte sich selbst.** Die Prüfung „läuft noch ein Cron?" vor dem Deploy hielt den laufenden API-Dienst für einen Cron, weil er auf dem Server als `python3 …/uvicorn` in der Prozessliste steht — damit war jeder Deploy blockiert. Und der Backup-Vergleich davor nennt jetzt Tabelle und Zeilenzahlen, wenn er abbricht, statt nur „abweichendes Tabellenmanifest".
