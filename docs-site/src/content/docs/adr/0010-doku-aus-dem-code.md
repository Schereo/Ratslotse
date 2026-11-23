---
title: 0010 — Doku aus dem Code erzeugen und gegen ihn prüfen
description: Aus Code erzeugte Referenzseiten, automatisierte Doku-Prüfungen und Verweise für Feature-Schalter.
sidebar:
  order: 10
---

**Status:** Akzeptiert

## Kontext

Änderungen im Code können die Dokumentation veralten lassen, ohne dass
der Build fehlschlägt. Eine Bestandsaufnahme am 22.11.2026 ergab die
folgenden Abweichungen.

- 24 von 34 Feature-Schaltern kamen in der Doku nicht vor, darunter ganze
  Bereiche (die Sitzungsseite, die Punkt-Seite, „Mein Viertel“, die Pläne der
  Stadt).
- 83 von 153 Umgebungsvariablen, die der Code liest, standen nirgends.
- Der Wochenlauf hatte 23 Schritte, die Doku beschrieb 14. Zwei Cron-Jobs,
  drei Rollen, 26 Eval-Läufe und 21 Workflows fehlten.
- 14 Pfade zeigten auf Dateien, die umgezogen oder gelöscht waren.
- Ein Release-Dossier beschrieb einen Stand von vor drei Monaten als aktuell.

Bis dahin prüfte ein KI-Review je Pull Request den Diff
(`.github/workflows/docs-review.yml`). Der Review gab Hinweise zu
Änderungen, prüfte jedoch keine unveränderten Seiten. Seit mindestens
dem 12.11.2026 war er mangels Guthaben für den API-Key ausgefallen.
Da dieser Lauf den Pull Request nicht blockiert, fiel der Ausfall nicht auf.

## Entscheidung

Drei verbindliche Mechanismen halten die Dokumentation aktuell.

1. **Referenzseiten entstehen aus den Registern im Code.** Cron-Jobs, Feature-Schalter,
   Rollen, Eval-Läufe und Workflows stehen als Seiten unter
   [Referenz](/docs/referenz/cron-jobs/), geschrieben von
   `scripts/docs_reference.py`. Die Seiten sind eingecheckt, weil die Doku mit
   Node baut und die Register in Python definiert sind. Eine Prüfung in
   `scripts/pruefe.py` und in der Testsuite meldet Abweichungen vom Register.
2. **Automatisierte Tests prüfen die Angaben auf den geschriebenen Seiten.**
   `tests/test_docs_current.py` prüft genannte Pfade, Symbole, Modelle,
   API-Routen und Umgebungsvariablen samt Standardwert. Der Test prüft auch,
   ob alle vom Code gelesenen Variablen dokumentiert sind. Weitere Prüfungen
   decken Cron-Jobs, Schritte des Wochenlaufs, MCP-Werkzeuge, Links, Anker
   und die Seitenleiste ab.
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
- **Plus:** Die Prüfung benötigt keine kostenpflichtigen Dienste und läuft
  in rund zwei Sekunden ohne Doku-Build. Sie berechnet die Anker selbst.
  Im Vergleich mit dem gebauten HTML stimmten alle 360 Anker überein.
- **Minus:** Kein Test sieht, ob ein Satz inhaltlich falsch geworden ist. Wer
  Verhalten ändert, muss den Absatz dazu weiter selbst ändern.
- **Minus:** Überschriften dienen als Linkziele. Ändert sich eine
  Überschrift, meldet der Test ungültige Feature- oder Linkverweise. Die
  Verweise müssen dann angepasst werden.
- **Minus:** Die Erkennung von Pfaden und Variablen im Fließtext ist ein
  Muster, kein Parser. Fehlalarme gehören mit Grund in die Ausnahmelisten des
  Wächters; die werden in beide Richtungen geprüft.
