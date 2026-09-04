---
kategorie: behoben
---

**Der Cron für die Kartentexte lief unbeobachtet — jetzt steht er im
Admin-Panel wie alle anderen.** Er schreibt täglich einen erklärenden Satz je
Tagesordnungspunkt, kostet dabei Geld, und war als einziger Job nicht in die
Absicherung eingehängt: kein Eintrag unter *Statistik → Cron-Jobs*, keine
Fehlermeldung beim Absturz. Wäre er ausgefallen, hätte es niemand bemerkt.

Damit sich das nicht wiederholt, prüft ein Test das jetzt am Quelltext statt
an einer abgeschriebenen Liste: Jedes Skript, das einen Lauf protokolliert,
muss entweder ein eingetragener Cron sein oder ausdrücklich als Unterschritt
eines anderen geführt werden.
