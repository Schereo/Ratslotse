---
kategorie: behoben
---

**Der Einrichtungs-Assistent reagiert sofort und schlägt Besseres vor.** Drei
Befunde vom ersten Tag auf dev, alle behoben.

**Ein Klick auf einen Stadtteil brauchte Sekunden.** Ein Stadtteil ist ein
Thema, und ein neues Thema gleicht der Server sofort mit dem Beschlussbestand
ab; nach einem Neustart des Dienstes lädt er dafür erst die Modelle. Die Pille
sprang erst danach um, und solange war jeder weitere Klick gesperrt. Jetzt
springt die Anzeige sofort, jeder Stadtteil wartet für sich, und Klicks laufen
nebeneinander; nur wenn der Server nein sagt, fällt die Anzeige zurück.

**Die Vorschläge kamen spät und ohne Hinweis.** Für jeden noch nie gesehenen
Vorschlag entschied ein Modell im laufenden Aufruf, ob der Name als Thema
taugt; beim ersten Aufruf nach einer Neuberechnung waren das Dutzende
Entscheidungen hintereinander. Die Urteile werden jetzt im Wochenlauf
vorgerechnet, und solange der Assistent sucht, sagt er das mit Platzhaltern.

**Unter dem eigenen Stadtteil standen Straßen und Plannummern.** Wer
„Krusenbusch" gewählt hatte, dem wurden „Quartier am Krusenbusch" und
„Grundschule Krusenbusch" als Dubletten des eigenen Themas weggefiltert, also
genau das Beste. Ein Stadtteil-Thema zählt beim Dubletten-Vergleich nicht mehr
mit. Straßen mit zwei, drei Erwähnungen fallen aus den Stadtteil-Listen; starke
Straßen bleiben, hinten. Namen, die nach stadtweitem Vorgang klingen, gehören
in die stadtweite Liste. Und eine Plannummer trägt ihre Erklärung sichtbar auf
dem Chip („Bebauungsplan 862 · Quartier am Krusenbusch"), nicht im Tooltip,
den es auf dem Telefon nicht gibt.

**Eigene Themen standen unter dem sichtbaren Bereich.** Sie stehen jetzt
direkt unter dem Eingabefeld, eine Zeile je Thema, und ein Thema, das gerade
angelegt wird, erscheint dort sofort mit dem Hinweis, dass Lotti noch die
Beschlüsse dazu liest.
