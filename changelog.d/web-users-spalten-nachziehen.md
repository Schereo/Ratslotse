---
kategorie: behoben
---

**Die Einwilligung „Gespräche speichern" war nach dem letzten Update
verschwunden.** Zwei Spalten der Konten-Tabelle hatten beim Umbau auf
englische Bezeichner nur im Code neue Namen bekommen, nicht in der
Datenbank. Der Start legte die neue Spalte daraufhin leer daneben — die
Einwilligung stand für alle wieder auf „nie gefragt", obwohl sie
gespeichert war. Sie wird jetzt übernommen; eine zweite Spalte, die durch
denselben Fehler gar nicht erst entstand, wird nachgelegt.
