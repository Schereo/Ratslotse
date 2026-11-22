---
title: 0010 — Doku aus dem Code erzeugen und gegen ihn prüfen
description: Listen mit einer Quelle im Code werden zu erzeugten Seiten, alles Prüfbare hält ein Wächter, und jeder Feature-Schalter nennt seine Doku-Stelle.
sidebar:
  order: 10
---

**Status:** Akzeptiert

## Kontext

Diese Doku ist Prosa über Code, und Prosa bricht nicht, wenn der Code sich
ändert. Eine Bestandsaufnahme am 22.11.2026 ergab:

- 24 von 34 Feature-Schaltern kamen in der Doku nicht vor, darunter ganze
  Bereiche (die Sitzungsseite, die Punkt-Seite, „Mein Viertel“, die Pläne der
  Stadt).
- 83 von 153 Umgebungsvariablen, die der Code liest, standen nirgends.
- Der Wochenlauf hatte 23 Schritte, die Doku beschrieb 14. Zwei Cron-Jobs,
  drei Rollen, 26 Eval-Läufe und 21 Workflows fehlten.
- 14 Pfade zeigten auf Dateien, die umgezogen oder gelöscht waren.
- Ein Release-Dossier beschrieb einen Stand von vor drei Monaten als aktuell.

Dagegen stand bis dahin ein KI-Review je Pull Request
(`.github/workflows/docs-review.yml`). Er berät nur, er sieht den Diff und
nicht den Bestand, und er war mindestens seit dem 12.11.2026 ausgefallen
(kein Guthaben am Schlüssel), ohne dass es auffiel: Der Lauf darf scheitern,
ohne den Pull Request rot zu machen.

## Entscheidung

Drei Mechanismen, nach abnehmender Härte:

1. **Was im Code eine Quelle hat, wird erzeugt.** Cron-Jobs, Feature-Schalter,
   Rollen, Eval-Läufe und Workflows stehen als Seiten unter
   [Referenz](/docs/referenz/cron-jobs/), geschrieben von
   `scripts/docs_reference.py`. Die Seiten sind eingecheckt, weil die Doku mit
   Node baut und die Register Python sind; eine Prüfung in `scripts/pruefe.py`
   und in der Testsuite meldet, wenn sie dem Register nachlaufen.
2. **Was sich ohne Urteil prüfen lässt, prüft ein Wächter.**
   `tests/test_docs_current.py` hält die geschriebenen Seiten gegen den Code:
   genannte Pfade, Symbole, Modelle, API-Routen und Umgebungsvariablen samt
   Vorgabewert; umgekehrt jede Variable, die der Code liest; dazu Cron-Jobs,
   Schritte des Wochenlaufs, MCP-Werkzeuge, Links, Anker und die Seitenleiste.
3. **Wo ein Feature entsteht, wird seine Beschreibung verlangt.** Jeder
   Eintrag in `kern/features.py` nennt im Feld `docs` die Seite oder den
   Abschnitt, der das Feature erklärt. Ohne gültiges Ziel ist die Testsuite
   rot.

Der KI-Review bleibt als vierte, weiche Stufe für das, was kein Test sieht:
ob ein Absatz noch stimmt. Fällt er aus, steht das jetzt als Warnung am Lauf.

## Konsequenzen

- **Plus:** Die Listen können nicht mehr veralten, und ein neuer Schalter,
  ein neuer Job oder eine neue Variable erzwingt die Zeile in der Doku im
  selben Pull Request, also dann, wenn die Person noch weiß, was sie gebaut
  hat.
- **Plus:** Die Prüfung kostet nichts und läuft in rund zwei Sekunden, ohne
  die Doku zu bauen. Die Anker rechnet der Wächter selbst nach; verglichen
  mit dem gebauten HTML stimmten alle 360.
- **Minus:** Kein Test sieht, ob ein Satz inhaltlich falsch geworden ist. Wer
  Verhalten ändert, muss den Absatz dazu weiter selbst ändern.
- **Minus:** Überschriften sind damit Schnittstelle. Wer eine umbenennt, auf
  die ein Schalter oder ein Link zeigt, bekommt das vom Wächter gesagt und
  zieht das Ziel nach.
- **Minus:** Die Erkennung von Pfaden und Variablen im Fließtext ist ein
  Muster, kein Parser. Fehlalarme gehören mit Grund in die Ausnahmelisten des
  Wächters; die werden in beide Richtungen geprüft.
