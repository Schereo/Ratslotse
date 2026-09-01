---
kategorie: behoben
---

**Zwei Einlese-Läufe hätten die Herkunft eines Dokuments doppelt angelegt.**
Die Quellenart „Veröffentlichung auf oldenburg.de" heißt gespeichert seit dem
Umbau `city`; drei Stellen im Code schrieben aber weiter `stadt`, und weil der
Fingerabdruck einer Quelle ihre Art mitrechnet, hätte derselbe Haushaltsplan
beim nächsten Einlesen einen zweiten Eintrag bekommen statt seinen alten
wiederzufinden. Der Schuldenreihen-Lauf wäre zusätzlich mit einem Fehler
abgebrochen, weil er das Feld noch unter seinem alten Namen übergab. Ein neuer
Prüflauf hält jeden Herkunfts-Aufruf im Quelltext gegen das Register.
