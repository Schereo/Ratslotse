---
kategorie: behoben
---

**Kein zweiter Deploy mehr über einen laufenden.** Der Wächter, der
liegengebliebene Prod-Deploys nachholt, verglich `main` nur mit dem letzten
*geglückten* Lauf — ein gerade laufender kam in der Rechnung nicht vor.
Dauerte ein Deploy länger als zwanzig Minuten, stieß der Wächter denselben
Stand ein zweites Mal an: zweite Wartungsbarriere, rund zwei Minuten, in denen
die Seite für nichts und wieder nichts pausierte. Er fragt jetzt zuerst, ob
schon einer unterwegs ist.
