---
kategorie: geaendert
---

**Die Typen der Weboberfläche kommen jetzt aus dem API-Vertrag, statt von Hand
gepflegt zu werden.** Bisher stand neben jeder Serverantwort eine zweite,
abgetippte Beschreibung im Frontend — die veraltete still, sobald sich hinten
etwas änderte, und in jeder Oberfläche einzeln. Jetzt werden sie aus dem
Schema erzeugt; ein umbenanntes Feld bricht sofort den Build statt später die
Anzeige. Sichtbar ändert sich nichts — der Nutzen ist, dass Web-Version und
App aus derselben Quelle arbeiten und seltener auseinanderlaufen.
