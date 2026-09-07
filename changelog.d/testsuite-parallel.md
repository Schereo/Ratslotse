---
kategorie: geaendert
---

**Die Testsuite läuft parallel.** Der Lauf in der CI verteilt sich mit
`pytest -n auto` auf alle Kerne und braucht statt knapp drei Minuten rund
eine; lokal fällt er von 1:42 auf 0:35. Möglich wurde das, indem die
Wegwerf-Datenbanken der Backend-Tests nicht mehr von jedem Testmodul einzeln
über eine Prozessvariable verabredet werden, sondern einmal je Prozess in
`tests/conftest.py`. Vorher entschied die Import-Reihenfolge, welche Datei
galt — seriell war die fest, auf mehrere Prozesse verteilt bei jedem Lauf eine
andere, und ein Test schrieb seine Zeilen in eine andere Datenbank, als die
Anwendung las. Ein Wächter hält die Regel fest, damit die nächste Zuweisung
nicht wieder sporadisch rote Läufe erzeugt.
