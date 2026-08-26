---
kategorie: behoben
---

- Die Tragweite-Bewertung neuer Tagesordnungspunkte lief seit dem 16.08. gar
  nicht mehr: Der tägliche Lauf schloss die Datenbank, bevor er sie dafür
  benutzte, verschluckte den Fehler und meldete sich trotzdem als erfolgreich.
  Die Wochen-Vorschau hob dadurch nach Stichwort-Regeln hervor statt nach
  Tragweite. Ein Lauf, der keinen einzigen offenen Punkt bewerten konnte,
  schlägt jetzt Alarm, statt still „0" zu melden.
