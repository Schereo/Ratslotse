---
kategorie: geaendert
---

**Aus dem Tag wird jetzt automatisch ein GitHub-Release.** Der Versionsschnitt
setzte bisher nur den Changelog-Abschnitt; das Release auf GitHub musste
jemand danach von Hand anlegen — und genau das fiel dreimal aus: v1.14.0,
v1.15.0 und v2.0.0 lagen wochenlang als bloße Tags im Repository, während die
Release-Seite v1.13.2 als neuesten Stand zeigte. `changelog_schnitt.py` kann
den Schritt jetzt selbst (`--release`): Es liest den fertigen Abschnitt aus
`CHANGELOG.md`, prüft, dass der Tag wirklich bei GitHub liegt und das Release
noch nicht existiert, und legt es an. Ist ein Jahrgang zu umfangreich für einen
Release-Text — GitHub nimmt 125.000 Zeichen, der Abschnitt zu 1.14.0 hat
181.451 — gehen statt eines Fehlers nur die Kernsätze aller Einträge raus,
darüber der Verweis auf den vollständigen Text. Und „Latest" bekommt nur, wer
im Changelog obenauf steht: Ein nachgereichtes Release für einen alten Tag darf
den aktuellen Stand nicht verdrängen.
