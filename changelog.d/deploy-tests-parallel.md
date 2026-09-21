---
kategorie: behoben
---

**Jeder Prod-Deploy war fünf Minuten länger unterwegs als nötig.** Die Testsuite läuft seit 09/2026 parallel über alle Kerne — auf den Pull Requests und lokal, aber nicht in dem Testlauf, der dem Deploy vorgeschaltet ist: Dort war die Umstellung übersehen worden. Gemessen am Release 2.7.0: 7 min 25 s dort gegen gut zwei Minuten auf demselben Stand im Pull Request. Nichts wurde dadurch rot, es dauerte nur jedes Mal länger. Ein Wächter hält die drei Stellen, die die ganze Suite fahren, jetzt beieinander.
