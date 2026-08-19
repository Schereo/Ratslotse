---
kategorie: behoben
---

**Kein iOS-Zoom mehr beim Antippen kleiner Eingabefelder.** Safari/WKWebView
zoomt automatisch rein, sobald ein Eingabefeld eine Schriftgröße unter 16px
hat — auf dem iPhone (und, weil `sm:` an der Fensterbreite statt am
Eingabegerät hing, auch auf dem iPad) blieb dieser Zoom in Feldern wie
„Gespräch umbenennen", „Neues Thema anlegen" oder der Admin-Suche oft
hängen. Betroffene Felder zeigen jetzt überall mindestens 16px, sobald kein
Mauszeiger vorhanden ist; am Desktop bleibt die kompaktere Schrift wie
gewohnt.
