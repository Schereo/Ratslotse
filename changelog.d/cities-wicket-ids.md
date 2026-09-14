---
kategorie: behoben
---

**Wolfsburgs Wochenlauf holte jedes Mal den ganzen Bestand neu.** Das dortige
Ratsinformationssystem liefert dieselbe Seite nie bitgleich aus: Element-IDs,
Sitzungs-Token und Seitenzähler ändern sich bei jedem Abruf. Für den Vergleich
werden sie jetzt herausgerechnet — abgelegt wird weiterhin die Antwort des
Servers, unverändert. Statt 2.261 Abrufen je Woche bleiben die übrig, hinter
denen wirklich etwas Neues steht.
