---
kategorie: behoben
---

**Die Wochenvorschau fiel aus, sobald eine frisch veröffentlichte Tagesordnung noch keine KI-Tragweite hatte.** Punkte, die nur nach Regeln bewertet waren, trugen das Feld für den Tragweite-Grund gar nicht, und der Endpunkt brach mit einem Validierungsfehler ab. Am 07.09.2026 blieb deshalb nach einem Deploy die Prod-API gut siebzig Minuten gestoppt: Die Rauchprobe stolperte über genau diesen Endpunkt, und die Wartungssperre hielt fail-closed. Das Feld ist jetzt immer da, notfalls leer.
