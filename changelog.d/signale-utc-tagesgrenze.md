---
kategorie: behoben
---

**Registrierungs-Signale und Kohorten rechnen in UTC.** Die Tagesreihe der Registrierungen und die Reife der Kohorten liefen über die Ortszeit, die gespeicherten Zeitstempel stehen aber in UTC. Zwischen 22 und 24 Uhr CEST fehlte deshalb der jüngste Tag im Admin-Panel; die Abweisungen werden jetzt ebenfalls auf den UTC-Tag gezählt, und zwei Tests halten den Grenzfall mit gestellter Uhr fest.
