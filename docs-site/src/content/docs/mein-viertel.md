---
title: Mein Viertel
description: Register der Vorhaben je Ortsbereich, Modellprüfung und Datenquellen der Karte.
---

„Mein Viertel“ zeigt auf `/viertel` die Vorhaben und ihren Stand je
Ortsbereich sowie eine Karte. Der Zugriff setzt den Feature-Schalter
`mein-viertel` und ein Konto voraus. Geteilte Links öffnen die jeweilige
Ansicht nach der Anmeldung.

Die 31 Ortsbereiche und ihre Grenzen stammen aus dem
[zentralen Ortskatalog](/docs/adr/0009-zentraler-ortskatalog/).

## Das Register der Vorhaben

Die Seite nutzt das Register, das `scripts/build_district_projects.py`
im Wochenlauf aktualisiert (`council/viertel.py`). Der Lauf besteht aus
drei Schritten.

1. **Kandidaten** aus der Orts-Erkennung: alle Beschlüsse der letzten
   24 Monate, deren erkannte Orte zu mindestens der Hälfte im Ortsbereich
   liegen.
2. **Modellprüfung** (fünf Beschlüsse je Aufruf). Das Modell prüft den
   Ortsbezug und beschreibt konkrete Änderungen, ihren Zeitraum und Stand.
   Ein Cache speichert die Bewertung unter einem Hash der Eingabe, sodass
   der Wochenlauf nur neue Eingaben an das Modell sendet.
3. **Bündelung** (ein Modellaufruf je Ortsbereich). Das Modell fasst
   zusammengehörige Treffer zu Vorhaben mit Status zusammen. Ausschuss- und
   Ratsberatungen, Aufstellungs- und Satzungsbeschlüsse sowie Berichte und
   Anträge zum selben Gegenstand erscheinen auf einer gemeinsamen Karte.

**Qualitätsmessung der beiden Modellschritte.** Gemessen am
05.09.2026 an drei Ortsbereichen mit 163 Kandidaten: Die Hälfte gehörte nicht
ins Viertel. Es waren stadtweite Berichte mit einem Beispielort, das Klinikum,
Gedenktitel mit Straßennamen, lange Straßen. Nach Modellprüfung und Bündelung blieben 31 Vorhaben, davon 30 im richtigen
Ortsbereich. Der einzige Fehler betraf zwei gleichnamige Schießstände in
Eversten und am Fliegerhorst. Der Prompt enthält deshalb gleichnamige Orte
in anderen Ortsbereichen. Bei Namensgleichheit bleibt ein Vorhaben ohne
Beleg aus der Vorlage unter dem Schwellenwert.

Das Register dient der Anzeige. Falls Benachrichtigungen hinzukommen,
müssen sie über `notify.einreihen` laufen
(siehe [App & Konten](/docs/app-und-konten/#benachrichtigungen-sechs-anlässe-vier-grenzen)).

### Ist der Zeitraum schon vorbei?

Das Register speichert den Stand aus dem jüngsten Beschluss, etwa „Im
Bau, bis Januar 2026“. Diese Angabe ändert sich durch Zeitablauf allein
nicht. Am 03.10.2026 lag die angegebene Bauzeit bei vier von sechs
hervorgehobenen Vorhaben in der Vergangenheit. Aus Ratsbeschlüssen geht
der tatsächliche Abschluss nicht hervor, da der Rat ihn nicht beschließt.

`council/viertel_zeitplan.py` leitet den Zustand ohne Modell ab. Ein
Parser liest den Zeitraum und gleicht ihn mit dem aktuellen Datum ab.
Die Ansicht weist darauf hin, wenn der genannte Zeitraum abgelaufen
ist oder seit mehr als einem Jahr kein Beschluss hinzugekommen ist.

### Gehört nicht hierher

Jede Karte hat eine Meldung „Gehört nicht hierher“
(`POST /api/districts/projects/{project_id}/report`, zurücknehmbar). Sie ist
das Korrektiv für das, was beide Modell-Stufen durchlassen.

**Die Redaktion entscheidet, ob ein Vorhaben ausgeblendet wird.** Bis
10/2026 genügten zwei Meldungen, um es dauerhaft auszublenden. Zwei Konten
konnten dadurch eine ganze Ansicht leeren, ohne dass die Meldungen sichtbar
waren. Das Admin-Panel listet jetzt jede Meldung auf. Bei der ersten Meldung
pro Vorhaben verschickt Ratslotse zusätzlich eine E-Mail. Beim Löschen des
Kontos entfernt Ratslotse auch die zugehörigen Meldungen.

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
