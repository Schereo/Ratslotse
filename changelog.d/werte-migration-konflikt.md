---
kategorie: behoben
---

**Ein Ingest mit neuem Code konnte den Datenbank-Start blockieren.** Schrieb ein Lauf bereits die englische Schreibweise eines Werts, während die deutsche noch daneben lag, brach die Umschreibung beim nächsten Öffnen der Datenbank ab — auf dev starben daran Crons und Ingests. Jetzt weicht die alte Zeile der neuen, wenn beide denselben Schlüssel tragen.
