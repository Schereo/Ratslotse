---
kategorie: hinzugefuegt
---

**Nach jedem Deploy prüft der Server sich selbst.** Bisher galt ein Deploy als
geglückt, sobald die Dienste überhaupt antworteten — eine Abfrage, die nach
einer Datenbank-Änderung ins Leere zeigt, wäre dabei nicht aufgefallen, weil
der Lebenszeichen-Aufruf die Datenbank gar nicht anfasst. Jetzt werden die
öffentlichen Seiten wirklich abgerufen und ihre Antworten gegen die
beschriebene Form gehalten.
