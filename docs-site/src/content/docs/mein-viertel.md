---
title: Mein Viertel
description: Was sich in einem Ortsbereich in den nächsten Jahren ändert — das Register der Vorhaben, seine zwei Prüfstufen und die Quellen der Karte.
---

„Mein Viertel“ beantwortet eine Frage, die keine Tagesordnung beantwortet:
Was ändert sich vor meiner Tür? Die Seite `/viertel` zeigt je Ortsbereich eine
Tafel mit Vorhaben, ihrem Stand und einer Karte. Sie liegt hinter dem Schalter
`mein-viertel` und verlangt ein Konto; eine öffentliche Ansicht gibt es nicht,
ein geteilter Link führt über die Anmeldung zurück auf die Tafel.

Die 31 Ortsbereiche und ihre Grenzen stammen aus dem
[zentralen Ortskatalog](/docs/adr/0009-zentraler-ortskatalog/).

## Das Register der Vorhaben

Die Tafel liest ein Register, das `scripts/build_district_projects.py`
wöchentlich im Wochenlauf rechnet (`council/viertel.py`). Drei Stufen:

1. **Kandidaten** aus der Orts-Erkennung: alle Beschlüsse der letzten
   24 Monate, deren erkannte Orte zu mindestens der Hälfte im Ortsbereich
   liegen.
2. **Richter** (Modell, fünf Beschlüsse je Aufruf): Liegt der Gegenstand
   wirklich hier, ändert sich etwas Spürbares, was, wann, welcher Stand? Das
   Urteil ist über einen Hash der Eingabe gespeichert, ein Wochenlauf schickt
   also nur Neues.
3. **Bündelung** (Modell, ein Aufruf je Ortsbereich): Alle Treffer werden zu
   Vorhaben mit Stand. Ausschuss und Rat, Aufstellungs- und Satzungsbeschluss,
   Bericht und Antrag zum selben Gegenstand sind **eine** Karte.

**Warum zwei Modell-Stufen und nicht die Orts-Erkennung allein.** Gemessen am
05.09.2026 an drei Ortsbereichen mit 163 Kandidaten: Die Hälfte gehörte nicht
ins Viertel. Es waren stadtweite Berichte mit einem Beispielort, das Klinikum,
Gedenktitel mit Straßennamen, lange Straßen. Nach Richter und Bündelung
blieben 31 Vorhaben, 30 davon im richtigen Viertel. Der eine Fehler war eine
Namensgleichheit (ein Schießstand in Eversten, einer am Fliegerhorst). Die
Namensvettern anderer Viertel gehen deshalb mit in den Prompt, und ein
Vorhaben mit Namensvetter ohne Beleg aus der Vorlage fällt unter die Schwelle.

Das Register meldet nichts, es ist Lesestoff. Wer daraus einmal
Benachrichtigungen baut, geht über `notify.einreihen`
(siehe [App & Konten](/docs/app-und-konten/#benachrichtigungen-sechs-anlässe-vier-grenzen)).

### Ist der Zeitraum schon vorbei?

Das Register hält den Stand so fest, wie ihn der jüngste Beschluss nennt:
„Im Bau, bis Januar 2026“. Ein Jahr später steht dort dasselbe. Am 03.10.2026
zeigten vier von sechs hervorgehobenen Vorhaben eine Bauzeit, die längst
vorbei war. Ob die Sache fertig ist, weiß der Rat nicht, er beschließt keinen
Bauabschluss.

`council/viertel_zeitplan.py` rechnet daraus einen abgeleiteten Zustand,
ohne Modell: Den Zeitraum liest ein kleiner Parser, das Datum ist das
heutige. Die Tafel sagt dann, dass der genannte Zeitraum vorbei ist oder seit
über einem Jahr kein Beschluss dazukam, statt einen alten Stand als Gegenwart
zu zeigen.

### Gehört nicht hierher

Jede Karte hat eine Meldung „Gehört nicht hierher“
(`POST /api/districts/projects/{project_id}/report`, zurücknehmbar). Sie ist
das Korrektiv für das, was beide Modell-Stufen durchlassen.

**Eine Meldung blendet nichts aus.** Bis 10/2026 verschwand ein Vorhaben ab
zwei Meldungen dauerhaft. Zwei Konten konnten so jede Tafel leeren, und
niemand sah die Meldungen. Jetzt landet jede in einer Liste im Admin-Panel,
die erste je Vorhaben zusätzlich als Mail, und ausgeblendet wird erst, wenn
die Redaktion bestätigt. Die Meldung hängt am Konto und geht mit dessen
Löschung.

## Was neben den Beschlüssen auf der Tafel steht

Neben den Vorhaben zeigt die Tafel, was demnächst im Rat ansteht und was im
Investitionsprogramm steht. Dazu kommt ohne Modell, aus Quellen der Stadt:

| Was | Quelle | Wo im Code |
|---|---|---|
| Pressemitteilungen zum Ortsbereich | RSS der Stadt, zugeordnet mit derselben Orts-Erkennung wie die Beschlüsse | `council/presse_orte.py` |
| Flächen der Bebauungspläne | Geoportal der Stadt: je Plan Nummer, Name, Beschlussdaten, Rechtskraft, Fläche | `council/bplan.py` |
| Aktuelle Straßensperrungen | Geoportal der Stadt: Straße, Grund, von/bis, Art, Linie | `council/sperrungen.py` |
| Stadterneuerungsgebiete | Geoportal der Stadt: Umriss, Laufzeit, Fördermittel | `council/stadterneuerung.py` |
| Laufende Bauleitplan-Beteiligungen | Beteiligungsportal der Stadt | `council/beteiligung.py` |

**Warum die Flächen aus dem Geoportal kommen und nicht aus den Vorlagen.**
Was ein Bebauungsplan umfasst, steht als Planzeichnung im Anhang der Vorlage:
ein Bild, aus dem sich keine Fläche für eine Karte gewinnen lässt. Die Stadt
führt die Umringe aller Pläne aber selbst. Damit bekommt ein Vorhaben seine
Fläche auf die Karte, auch wenn die Straße noch nicht gebaut ist und
OpenStreetMap sie deshalb nicht kennt.

Sperrungen und Pressemitteilungen holt `scripts/check_presse.py` täglich. Das
Geoportal sperrt Adressen aus Rechenzentren; der Abruf läuft deshalb über den
[Heim-Proxy](/docs/betrieb/#heim-proxy-gegen-adress-sperren).

## Schnittstellen

| Route | Zweck |
|---|---|
| `GET /api/districts/lookup` | „Ich wohne in der …“: Straße, Platz oder Stadtteilname wird zum Ortsbereich, ohne Modell |
| `GET /api/districts/projects` | alle Ortsbereiche mit der Zahl ihrer Vorhaben, die Stadtzahlen und die Vorhaben, die gerade herausstechen |
| `GET /api/districts/{place_id}/projects` | die Tafel eines Ortsbereichs |
| `POST` und `DELETE /api/districts/projects/{project_id}/report` | „Gehört nicht hierher“ melden und zurücknehmen |

Die Kartenkacheln kommen von einem Kachel-Anbieter mit Schlüssel. Die Adresse
baut `web/frontend/lib/basemap.ts` an einer Stelle; keine Komponente schreibt
eine Kachel-Adresse selbst.
