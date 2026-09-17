---
kategorie: geaendert
---

**Ein wackelnder Cron-Schritt macht nicht mehr den ganzen Lauf rot.** Die
Straßen-Geometrie holt ihre Daten von der öffentlichen Overpass-Instanz, und
die ist gelegentlich schlicht überlastet — dieselbe Abfrage antwortet mal in
einer Sekunde, mal viermal hintereinander mit „server too busy". Bisher zählte
das wie ein Absturz: Alarm-Mail und rote Kachel für etwas, das sich am nächsten
Sonntag von selbst erledigt. Jetzt steht so ein Schritt gelb in der
Cron-Übersicht, während der Lauf grün bleibt. Erst wenn er dreimal in Folge
ausfällt, wird er rot und meldet sich — dann ist es kein Ausrutscher mehr.
