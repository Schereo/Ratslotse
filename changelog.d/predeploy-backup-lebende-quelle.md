---
kategorie: behoben
---

**Deploy scheiterte am Backup-Vergleich, sobald nebenher ein Cron schrieb.** Das Sicherungs-Backup vor dem Deploy wurde Zeile für Zeile gegen die laufende Datenbank gehalten — aber das Backup entsteht, bevor das Prüfskript zum ersten Mal hinsieht, und bis dahin darf sich jede Tabelle bewegt haben. Am 20.09. blockierte das drei Deploys hintereinander, weil der Städte-Lauf nebenher Modellaufrufe zählte. Geprüft wird weiter, dass das Backup in diesem Lauf entstand, dasselbe Schema hat und gefüllt ist; Zeilenunterschiede werden nur noch genannt.
