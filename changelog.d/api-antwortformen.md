---
kategorie: geaendert
---

**Die API beschreibt jetzt, was sie zurückgibt.** Bisher lieferten fast alle
Endpunkte „irgendein Objekt" — im maschinenlesbaren Schema stand kein einziges
Feld. Damit konnte niemand Typen daraus ableiten, und eine Änderung an der
Schnittstelle war in keinem Diff zu sehen. Die Antwortformen stehen jetzt an
einer Stelle beisammen, das Schema liegt versioniert im Repo, und ein Test
verhindert, dass ein neuer Endpunkt wieder ohne Form durchrutscht. Für
Leser*innen der Seite ändert sich nichts — der Nutzen liegt darin, dass
Web-Version und App künftig aus derselben Quelle arbeiten.
