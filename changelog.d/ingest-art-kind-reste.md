---
kategorie: behoben
---

**Zwei weitere Ingest-Skripte lasen ein umbenanntes Feld.** Die Nachbewilligungen und die Steuertabellen des Jahrbuchs fragten noch `art` statt `kind` ab und rissen damit den Finanzdaten-Lauf auf dev, sobald er bis zu ihnen kam.
