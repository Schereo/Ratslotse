---
kategorie: geaendert
---

**Die Änderungslisten werden jetzt mit dem übrigen Haushalt eingelesen.** Ihr
Ingest war der einzige der Finanz-Läufe, der nach jedem Parser-Merge von Hand
angestoßen werden musste — vergaß man ihn, zeigte die Seite neuen Code auf
altem Bestand, und das ist der unangenehmere Fall als eine leere Tabelle: Sie
bleibt nicht leer, sie wird falsch. Der Ops-Lauf ruft ihn jetzt mit auf und
zieht sich die dafür nötige PDF-Bibliothek bei Bedarf selbst nach. Sein
Bestandsbericht zählt die beiden Änderungs-Tabellen mit und nennt, für welche
Jahrgänge ein Urheber je Position vorliegt — bliebe der weg, würde die
Zeilenzahl allein es nicht verraten.
