---
kategorie: geaendert
---

**Jede Serverantwort beschreibt jetzt ihre Form.** Die letzten vierzehn
Endpunkte — Ortskatalog, Wochenvorschau, Haushalts-Fundament, Sitzung,
Beschluss, geteilte Antwort, Recherche-Stand, öffentliche Kennzahlen, Thema,
Person, Wortbeiträge und drei Ansichten im Admin-Bereich — standen im Schema
noch als „irgendein Objekt". Damit ist die Schnittstelle vollständig
beschrieben: Alle 162 Aufrufe tragen ihre Felder, Weboberfläche und App leiten
ihre Datentypen daraus ab, und eine Änderung daran ist ab sofort im Diff zu
sehen. Die drei Endpunkte, die gar kein JSON liefern — die beiden
Ereignis-Ströme der KI-Frage und der tiefen Recherche sowie die gerenderte
Planzeichnung — nennen jetzt ihren echten Medientyp samt der Ereignisse, die
über die Leitung gehen, statt ein JSON-Objekt vorzutäuschen. Für Leser*innen
der Seite ändert sich nichts.
