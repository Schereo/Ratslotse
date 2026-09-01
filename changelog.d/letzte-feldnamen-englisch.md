---
kategorie: geaendert
---

**Die letzten 18 deutschen Feldnamen der Schnittstelle heißen jetzt englisch.** Mit dem vollständigen API-Vertrag wurden sie erst sichtbar: `vorlage`, `beratungsfolge`, `plan_bild` und `haushalts_anschluss` der Beschluss-Seite, `typ`, `art` und die `wortbeitraege`-Felder der Personen-Seite, `aenderungen` der Sitzung, der Beleg-Apparat `herkunft` in elf Haushalts-Antworten, dazu `wahlbereiche`, `gesamt`, `top` und `recherche`. Web und App lesen die neuen Namen; der Ortskatalog liefert `electoral_districts` jetzt so, wie das Web-Frontend es schon immer erwartet hatte — der Wahlbereichs-Filter über den Ortskatalog lief bis dahin ins Leere. Ausgelassen ist `ortsbereich_id`: Das ist zugleich eine Datenbankspalte und braucht einen eigenen Umzug.
