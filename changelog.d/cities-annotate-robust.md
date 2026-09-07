---
kategorie: behoben
---

**Der Einordnungslauf über fremde Ratsvorlagen bricht nicht mehr ab, wenn ein
Modell Unsinn antwortet.** Kam ein Batch als Liste von Zeichenketten statt als
Liste von Objekten zurück, warf der Zugriff im Arbeitsthread und riss den
ganzen Lauf um — gemessen nach 520 von 619 Batches. Solche Antworten werden
jetzt verworfen und die betroffenen Vorlagen einzeln nachgereicht.
