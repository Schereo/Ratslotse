---
kategorie: geaendert
---

**Die CI-Prüfungen eines Pull Requests laufen jetzt in rund einem Drittel der
Zeit.** Das Warten hing praktisch allein an den Browsertests: Sie liefen auf
einem einzigen Läufer und brauchten 16 bis 21 Minuten, während jede andere
Prüfung längst fertig war. Sie sind jetzt auf vier Läufer aufgeteilt, von denen
jeder sein eigenes Backend auf einer eigenen Wegwerf-Datenbank mitbringt.

Dazu zwei kleinere Hebel: Die Python-Testsuite verteilt sich auf alle Kerne des
Läufers, und die iOS-App wird nicht mehr zweimal übersetzt — der frühere
Vorab-Build lief gegen ein anderes Ziel als der Testlauf und wurde deshalb
komplett verworfen.
