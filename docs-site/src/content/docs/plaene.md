---
title: Pläne der Stadt
description: Register der städtischen Pläne mit Ratsbeschlüssen, Laufzeiten, Berichten und Statusangaben der Stadt.
---

Die Stadt hat Dutzende Pläne: Klimaschutzplan, Mobilitätsplan,
Schulentwicklungsplan, Strategien und Konzepte. Der Rat beschließt sie,
bekommt Berichte dazu und fasst Beschlüsse, die sie umsetzen sollen. In den
Tagesordnungen steht das verstreut über Jahre. „Pläne der Stadt“ (Schalter
`plaene`, Seite `/council/plan`, Übersicht `GET /api/council/plans`) stellt je
Plan zusammen: Beschluss, Laufzeit, Berichte im Rat, die Beschlüsse dazu und
den Stand, wie die Stadt ihn selbst berichtet.

Die Seite ersetzt die frühere Auswertung „Ziele“ in der Analyse. Jene ließ
ein Modell urteilen, ob ein Beschluss ein Ziel voranbringt
(`council/goals.py`). Das maß Aktivität und Richtung des Rats, keinen
Fortschritt in der Stadt.

## Was die Seite nicht tut

Die Seite zeigt den Wortlaut der Stadt (`status_raw`). Ein normalisierter
Status steuert nur Gruppierung und Farbe. Die Seite vergibt keine Noten,
berechnet keine planübergreifenden Quoten und bewertet das Tempo nicht.
Fehlen Berichte im Bestand, weist sie mit Datum darauf hin. Die Regeln dahinter stehen in `docs/plan-ziele-plaene.md`.

## Das Register

`council/plans.py` führt die Pläne als Code: Quelle, Beschlussart, Laufzeit,
Vorgänger und Nachfolger, Berichtsreihe. Das Register wird manuell gepflegt.
Da jeder Eintrag eine Aussage über die Stadt enthält, sollen Änderungen wie
bei den Prompts im Pull Request nachvollziehbar sein und in der
Versionshistorie stehen.

Vier Klassen (Stand 11/2026: 45 Pläne):

| Klasse | Was | Anzahl |
|---|---|---:|
| `action` | Pläne mit Maßnahmen und Ratsbeschluss | 16 |
| `framework` | Rahmenpläne und Strategien | 19 |
| `statutory` | Pflicht- und Fachpläne mit fester Laufzeit | 8 |
| `reference` | Pläne Dritter und Steuerungskonzepte, nur als Verweis | 2 |

**„Zur Kenntnis genommen“ ist nicht „beschlossen“.** Wo der Rat einen Plan
nur zur Kenntnis genommen hat, steht das so im Register, auch wenn das
Ergebnis im Ratsinformationssystem „ungeändert beschlossen“ heißt, weil der
Beschlusstext einen Auftrag an die Verwaltung enthält.

Daten stehen in der Genauigkeit, die der Beleg hergibt: `"2035"`,
`"2026-06"` oder `"2026-06-01"`.

`tests/test_plaene_register.py` prüft die Struktur ohne Datenbank.
`scripts/pruefe_plaene.py` vergleicht die Einträge mit dem Datenbestand.

## Was zu einem Plan gehört

`council/plan_tracking.py` ordnet ohne Modell zu, auf drei Wegen, die sicher
genug sind, um ohne Prüfung angezeigt zu werden:

1. **Tagesordnungspunkte über den Titel.** Jeder Punkt, dessen Titel ein
   Berichtsmuster des Plans trifft oder dessen Vorlage das Register nennt,
   bekommt eine Rolle: Beschluss des Plans, Fortschreibung, Auswertung,
   Bericht, Vorbereitung, Umsetzung, Antrag. Mündliche Berichte ohne Vorlage
   zählen mit; sie haben keinen Text, aber Termin und Gremium sind selbst
   eine Aussage.
2. **Verweis über die Vorlagennummer.** Eine andere Vorlage nennt die Nummer
   des Plans in ihrem Text. Das ist eine Erwähnung, keine Umsetzung, und
   steht auf der Seite hinter „Weitere“.
3. **Kennung einer Maßnahme im Text.** Eine Vorlage nennt eine Maßnahme bei
   ihrer Kennung (`PV_05`, „Handlungsansatz A12“). Das sagt, dass sie die
   Maßnahme nennt, nicht, dass sie sie umsetzt.

Ein Verweis über den **Namen** allein („Klimaschutzplan“ steht in 103
Vorlagen) ist nur ein Kandidat.

## Wo ein Modell hilft, und wie es gehalten wird

Drei Aufgaben kann nur ein Sprachmodell (`council/plan_judge.py`), alle über
öffentliche Ratsdokumente und keine mit Nutzereingabe:

- den Stand je Maßnahme aus einem Fließtext-Bericht lesen,
- beurteilen, ob eine Vorlage, die einen Plan beim Namen nennt, ihn umsetzt
  oder nur erwähnt,
- die Gegenprobe für „Ratsauftrag ohne Folge“.

Das Modell muss jede Angabe wörtlich belegen. Ratslotse verwirft Angaben,
deren Zitat nicht exakt im Quelltext steht. Dieselbe Regel gilt für die
[Dossiers](/docs/sitzungen/#aus-den-unterlagen-das-dossier). Die geprüften
Ergebnisse werden als Dateien eingecheckt (`scripts/plan_modell.py`,
`scripts/plan_status.py`, Ablage `council/plan_status/`). Dadurch lassen
sie sich im Pull Request ohne Modell prüfen. Ein Cron-Job ist nicht nötig.

## Der Stand eines Plans

Die Einordnung je Plan besteht aus drei Bausteinen, und keiner davon bewertet
(`council/plan_state.py`):

1. **Berichtsstand:** Wird über den Plan berichtet?
2. **Stand laut Stadt:** die Verteilung im Wortlaut der Stadt, mit Datum und
   Beleg, und was sich seit dem vorigen Bericht bewegt hat.
3. **Eigene Termine:** Laufzeit und Überprüfungsfrist als Tatsachen.

`council/plan_pages.py` berechnet die Gruppe (laufend, in Arbeit,
abgelaufen, abgelöst), die Sortierung, den „letzten Bericht“ und
die Hinweise auf fehlende Berichte. Web und App verwenden dieselben
Felder aus dem Backend.

## Ratsaufträge ohne Folge

Ein angenommener Beschluss beauftragt die Verwaltung, dem Rat etwas
vorzulegen, und danach findet sich keine Station mehr
(`council/open_mandates.py`). Ein falscher Treffer behauptet, die Stadt sei
säumig, wo der Bericht in Wahrheit existiert. Deshalb gilt: lieber zu wenig
als zu viel, „nicht gefunden“ statt „gibt es nicht“, und angezeigt wird nur,
was das Messziel erreicht. Ohne Modell erkennt der Code Aufträge und sucht
spätere Tagesordnungspunkte als Kandidaten zusammen; welcher Art ein Auftrag
ist und ob ein Kandidat die Folge ist, entscheidet `plan_judge.py`.

## Planzeichnungen

Unabhängig vom Register rendert `scripts/render_plaene.py` sonntags neue
Anlagen der Bauleitplanung (Planzeichnung, Lageplan) zu Bildern unter
`data/plaene/`. Sie erscheinen an den Beschlüssen zu Bebauungsplänen.
