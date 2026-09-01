---
kategorie: behoben
---

**Der API-Vertrag beschreibt optionale Felder jetzt so, dass auch die native
App sie sieht.** Optionale Angaben standen in einer Schreibweise im Schema,
die der Swift-Codegenerator stillschweigend übergeht — 139 Felder wären in
einer nativen App schlicht nicht angekommen, ohne dass irgendwo ein Fehler
aufgetaucht wäre. Die Schreibweise ist umgestellt, ein Test hält sie fest.
Nebenbei wurden fünf Stellen im Vertrag genauer, an denen er ungenauer war
als die Weboberfläche.
