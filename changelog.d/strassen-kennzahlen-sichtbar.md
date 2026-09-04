---
kategorie: behoben
---

**Die Kennzahlen der Straßen-Geokodierung stehen jetzt wirklich im
Admin-Panel.** Der tägliche Lauf rechnete sie zwar aus — wie oft Overpass
ausfiel, wie viele Straßen nur ein Teilstück tragen —, aber
`check_protocols` nahm sie nie entgegen; in keinem einzigen Eintrag unter
*Statistik → Cron-Jobs* stand je eine davon. Damit konnte ein Ausfall nur als
Mail auffallen, und weil eine Mail sonst nie käme, war ihre Schwelle so tief
gesetzt, dass eine einzelne abgewiesene Anfrage sie auslöste.

Neu sichtbar: wie viele Straßen aus dem Schnappschuss kamen (ohne jede
Anfrage), wie viele Overpass-Ausfälle es gab, wie viele Namen OpenStreetMap
gar nicht führt, und wie viele Straßen im Bestand keine vollständige
Geometrie tragen.
