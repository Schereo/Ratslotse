---
kategorie: behoben
---

**Ein Test, der ohne Ursache rot wurde, wird es nicht mehr.** Die Prüfung, ob
das Einlesen der Städte-Daten zweimal dasselbe Ergebnis liefert, verglich auch
den Zeitstempel „zuletzt geholt" mit — und der zweite Lauf ist nun einmal ein
zweiter Lauf. Überschritten die beiden Aufrufe eine Sekundengrenze, fiel die
Prüfung um; in der CI unter Last regelmäßig, lokal so gut wie nie.
