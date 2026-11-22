"""Die Beispielfragen auf der leeren Fragen-Seite: eine kuratierte Top 20.

Die Clients zeigen davon zwei oder drei und rücken bei jedem Besuch weiter,
bis alle zwanzig einmal dran waren (Web: ``lib/qa-zuletzt.ts``, App:
``QuestionsView.swift``). Die Liste steht hier und nicht in den Clients,
damit Web und App dieselben Fragen zeigen und eine bessere Frage ohne
App-Update ankommt.

**Warum es keine erzeugten Fragen mehr gibt.** Bis 22.11.2026 standen dort
zwei Vorschläge aus der jüngsten Sitzung: „Was hat der Ausschuss für
Allgemeine Angelegenheiten am 28.09.2026 beschlossen?" und „Was wurde zu
‚Änderung der Entschädigungssatzung' entschieden?". Beide waren technisch
richtig und trotzdem schlecht (Tims Befund 22.11.2026): ein Gremium, das
kaum jemand kennt, ein Datum, das zwei Monate alt war, ein Gegenstand aus
der Verwaltung. Sie standen immer ganz oben, und mit Gesprächsverlauf zeigt
die Seite nur zwei Fragen, also gab es dort nie etwas anderes zu sehen. Das
Aktuelle vertritt jetzt eine Frage, die nicht altert: „Was hat der Rat in
seiner letzten Sitzung beschlossen?" (Sitzungs-Fragetyp, ``qa.finde_sitzungen``).

**Was eine Frage hier braucht:**

* **Material.** Die Themen stammen aus der Liste, die am 10.08.2026 durch das
  echte Retrieval gegen Prod lief (mindestens vier Volltreffer mit Relevanz
  ≥ 0,7, zweistellig viele brauchbare Treffer, Material bis mindestens 2025).
  Neu sind Klinikum, Innenstadt und Grundsteuer: am 22.11.2026 per
  Volltextsuche auf dev gegengeprüft (21, 69 und 9 Beschlüsse seit 2024/25,
  jeweils bis 2026). Zu dünn und deshalb nicht dabei: Bahnumfahrung (fünf
  Beschlüsse, der jüngste von 2021), Schwimmbäder (drei).
* **Etwas, das man wissen will.** Ein Projekt, eine Summe, ein Stadtteil, eine
  Streitfrage. Nicht „Welche Beschlüsse gibt es zum Thema …", sondern die
  Frage, die man im Gespräch stellen würde.
* **Kein Futur ohne Beratung.** „Was ist … geplant?" schaltet die
  Zukunftsregel ein (``qa.zukunftsfrage``). Steht zu der Sache keine
  kommende Beratung an, beginnt die Antwort mit genau diesem Hinweis. Das ist
  für eine echte Frage richtig, für ein Aushängeschild aber ein schwacher
  erster Satz. Deshalb „Was entsteht auf dem Fliegerhorst?".
* **Kein Datum und kein „dieses Jahr".** Eine Beispielfrage altert sonst.
* **Höchstens 60 Zeichen.** Die Zeile ist auf zwei Textzeilen geklemmt, und
  die App zeigt sie in voller Breite eines kleinen Telefons.

**Die Reihenfolge zählt.** Drei aufeinanderfolgende Fragen stehen zusammen
auf der Seite, auch über das Ende hinweg. Sie dürfen also nicht dasselbe
Thema treffen (beide Stadion-Fragen liegen deshalb weit auseinander). Die
ersten drei sieht jede*r beim allerersten Besuch.

``tests/test_qa_beispiele.py`` hält Länge, Anzahl, Eindeutigkeit, Datum,
Futur und die Themenstreuung fest. Wer eine Frage tauscht, prüft vorher ihr
Material.
"""
from __future__ import annotations

TOP_QUESTIONS: tuple[str, ...] = (
    "Was kostet der Neubau des Stadions?",
    "Was tut die Stadt für bezahlbaren Wohnraum?",
    "Was hat der Rat in seiner letzten Sitzung beschlossen?",
    "Wie ist der Stand bei der Cäcilienbrücke?",
    "Welche Schulen werden saniert oder neu gebaut?",
    "Wie viele Bäume werden gefällt und nachgepflanzt?",
    "Was entsteht auf dem Fliegerhorst?",
    "Was tut die Stadt gegen Obdachlosigkeit?",
    "Was hat der Rat zur Grundsteuer entschieden?",
    "Was plant die Stadt für die Innenstadt?",
    "Wie will die Stadt mehr Kita-Plätze schaffen?",
    "Wie stehen die Fraktionen zum neuen Stadion?",
    "Was passiert mit dem Pferdemarkt?",
    "Was wurde zu Windenergie und Photovoltaik beschlossen?",
    "Wie unterstützt die Stadt das Klinikum?",
    "Was hat der Rat zuletzt für den Radverkehr beschlossen?",
    "Welche neuen Baugebiete hat der Rat beschlossen?",
    "Wie geht es mit der Weser-Ems-Halle weiter?",
    "Was wurde zu Tempo 30 beschlossen?",
    "Was wurde zuletzt in Osternburg beschlossen?",
)
