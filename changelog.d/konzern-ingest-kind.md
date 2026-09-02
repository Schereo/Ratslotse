---
kategorie: behoben
---

**Der Konzern-Ingest brach an einem umbenannten Feld ab.** Die Trägeraufstellung des Gesamtabschlusses liefert seit dem Umbau `kind` statt `art`; der Ingest las noch den alten Namen und riss damit den ganzen Finanzdaten-Lauf auf dev ab, bevor die späteren Schichten an die Reihe kamen.
