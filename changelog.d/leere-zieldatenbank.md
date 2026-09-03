---
kategorie: behoben
---

**Eine leere Datei hätte den Datenbank-Umzug blockiert.** Beim Start benennt
sich die Konten-Datenbank selbst von ihrem alten Namen auf den neuen um.
Lag am neuen Ort schon eine leere Datei, galt der Umzug als erledigt — die
App hätte das Schema dort neu angelegt und wäre mit leeren Konten
hochgekommen, während die echten Daten unberührt unter dem alten Namen
liegen. Eine 0 Byte große Datei zählt jetzt als „nicht da"; liegen zwei
gefüllte Datenbanken nebeneinander, sagt es das Log statt zu raten.
