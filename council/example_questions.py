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
die Seite nur zwei Fragen, also gab es dort nie etwas anderes zu sehen.

**Jede Frage hier hat auf Prod eine gute Antwort bekommen.** Am 23.11.2026
liefen alle Kandidaten über ``ops-frage-probe.yml`` gegen ratslotse.de
(34 Fragen). Herausgefallen sind, mit dem Grund:

* „Was hat der Rat in seiner letzten Sitzung beschlossen?" — „kein
  ausgewertetes Protokoll, daher kann ich nicht sagen …". Protokolle kommen
  Wochen nach der Sitzung; die Frage scheitert also meistens. „Was steht in
  der nächsten Ratssitzung an?" ebenso, solange keine Tagesordnung steht.
* „… zuletzt …" (Radverkehr, Osternburg): Die Frage nach dem Jüngsten bekommt
  genau einen Beschluss in einem Satz. Ohne „zuletzt" eine ganze Antwort.
* Stadtteil-Fragen (Osternburg, in drei Fassungen): vor allem Schulbeschlüsse
  von 2018. Ein Stadtteil ist kein Thema, die Antwort sammelt Einzelnes.
* „Wie viele Bäume werden gefällt und nachgepflanzt?" antwortete nur zum
  Sandweg; „Was plant die Stadt für die Innenstadt?" mit Beschlüssen von
  2021 und ohne das Sanierungsgebiet. Die engere Frage trifft beides.
* Obdachlosigkeit (zwei Fassungen): solide, beginnt aber mit „Die
  Ratsunterlagen geben nur begrenzte Auskunft" — ein schwacher erster Satz
  für ein Aushängeschild.

**Was eine Frage hier braucht:**

* **Eine gute Antwort auf Prod**, nicht nur Treffer: über
  ``ops-frage-probe.yml`` gestellt und gelesen (s. oben). Vorher per
  Volltextsuche ausgesiebt: Bahnumfahrung (fünf Beschlüsse, der jüngste von
  2021) und Schwimmbäder (drei) sind zu dünn.
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
Futur und die Themenstreuung fest. Die Antwort prüft kein Test. Wer eine
Frage tauscht, stellt sie vorher auf Prod (``ops-frage-probe.yml``, mehrere
Fragen mit ‖ getrennt) und liest, was zurückkommt.
"""
from __future__ import annotations

TOP_QUESTIONS: tuple[str, ...] = (
    "Was kostet der Neubau des Stadions?",
    "Was tut die Stadt für bezahlbaren Wohnraum?",
    "Was wurde zur Wärmeplanung beschlossen?",
    "Wie ist der Stand bei der Cäcilienbrücke?",
    "Welche Schulen werden saniert oder neu gebaut?",
    "Was wurde zur Baumschutzsatzung beschlossen?",
    "Was entsteht auf dem Fliegerhorst?",
    "Was hat der Rat zu Parkgebühren entschieden?",
    "Was hat der Rat zur Grundsteuer entschieden?",
    "Was wurde zum Sanierungsgebiet Innenstadt beschlossen?",
    "Wie will die Stadt mehr Kita-Plätze schaffen?",
    "Wie stehen die Fraktionen zum neuen Stadion?",
    "Was passiert mit dem Pferdemarkt?",
    "Was wurde zu Windenergie und Photovoltaik beschlossen?",
    "Wie unterstützt die Stadt das Klinikum?",
    "Was wurde zum Radverkehr beschlossen?",
    "Welche neuen Baugebiete hat der Rat beschlossen?",
    "Wie geht es mit der Weser-Ems-Halle weiter?",
    "Was wurde zu Tempo 30 beschlossen?",
    "Was wurde zum Kramermarkt beschlossen?",
)
