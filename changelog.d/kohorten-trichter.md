---
kategorie: hinzugefuegt
---

**Das Admin-Panel zeigt, was aus neuen Konten wird.** Unter *Statistik* steht
jetzt ein Trichter je Registrierungswoche: angemeldet, bestätigt, Einrichtung
begonnen und beendet, erstes Thema oder Gremium binnen 24 Stunden, erste Frage,
und ob jemand an einem zweiten Tag wiederkam. Dazu vier Kennzahlen, an denen
sich künftige Änderungen messen lassen.

Zwei Dinge macht die Ansicht bewusst anders. Sie rechnet **erreicht gegen
erreichbar**: Ein Konto von gestern kann „kam binnen 30 Tagen wieder" weder
geschafft noch verfehlt haben und steht deshalb als „noch offen" da, nicht als
Null — sonst läse sich jede frische Woche als Totalausfall. Und sie lässt
Betreiber- und Testkonten heraus (Recht `admin` plus die Domänen aus
`STATS_EXCLUDE_DOMAINS`), weil sie sonst zum großen Teil das eigene Klicken
misst. Ratsmitglieder bleiben drin: Ausgeschlossen wird ein Recht, keine Rolle.
