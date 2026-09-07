---
kategorie: geaendert
---

**Die CI-Prüfungen eines Pull Requests sind von 16–21 Minuten auf knapp neun
gefallen.** Das Warten hing praktisch allein an den Browsertests: Sie liefen
auf einem einzigen Läufer, während jede andere Prüfung längst fertig war. Sie
sind jetzt auf vier Läufer aufgeteilt, von denen jeder sein eigenes Backend
auf einer eigenen Wegwerf-Datenbank mitbringt.

Dazu Kleinkram: Der Testbrowser wird zwischengelegt statt je Lauf neu geladen,
in der CI entstehen keine Bildschirmaufnahmen mehr von grünen Tests, die
ohnehin niemand ansieht, und die iOS-App wird nicht mehr zweimal übersetzt —
der frühere Vorab-Build lief gegen ein anderes Ziel als der Testlauf und wurde
deshalb komplett verworfen.
