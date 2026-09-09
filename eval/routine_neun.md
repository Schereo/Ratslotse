# Die neun Routine-Verdächtigen — von Hand durchgesehen

**Stand 09.09.2026. Ergebnis: keine einzige ist Routine. Der Regex kommt
nicht in den Code.**

Der Plan zu PR 24 (`docs/plan-cities-phase4.md`) sah vor, Verwaltungsroutine
aus der Ideen-Liste zu nehmen — „Wahlordnung anpassen", „Benutzungsordnung
Sportstätten". Fünf Räte behandeln so etwas, weil jede Kommune es behandelt;
das Signal „in fünf Städten" misst dort Alltäglichkeit, nicht
Übertragbarkeit. Der Plan verlangte ausdrücklich, die Treffer erst von Hand
durchzugehen und erst dann zu entscheiden — mit der Schwelle: **ab 80 %
Routine kommt der Regex in den Code, darunter nicht.**

## Was die Messung ergeben hat

Der Regex trifft auf der bereinigten Liste (fehlt, 2+ andere Räte, je Stadt
und Idee eine Zeile, nur Vorgeschlagenes) noch **9 von 52** Einträgen:

| # | Räte | Stadt | Instrument | Urteil |
|---|---|---|---|---|
| 1 | 5 | Potsdam | Verpackungssteuer-Einführung verschieben | **Idee** — eine politische Entscheidung, keine Verwaltungsroutine |
| 2 | 5 | Braunschweig | Parkgebührenordnung ändern | **Idee** — Parkgebührenreform ist genau das, worüber Räte streiten |
| 3 | 3 | Braunschweig | Mähroboter-Einsatz zum Igelschutz regeln | **Idee** |
| 4 | 3 | Magdeburg | Mietwerterhebungssatzung erlassen | **Idee** — Grundlage für den Mietspiegel |
| 5 | 3 | Potsdam | Nachtmähverbot per Satzung regeln | **Idee** |
| 6 | 2 | Osnabrück | Förderrichtlinie Wohnraum verlängern | **Idee** — grenzwertig, aber mit Inhalt |
| 7 | 2 | Osnabrück | Photovoltaik auf städtischen Dächern prüfen | **Idee** |
| 8 | 2 | Münster | Fortschreibung Wasserversorgungskonzept | **Idee** |
| 9 | 2 | Magdeburg | Klimabeirat-Satzung ändern | **Idee** |

**0 von 9.** Weit unter der Schwelle.

## Warum der Regex falsch lag

Er sucht nach der FORM („Satzung", „Ordnung", „Richtlinie", „anpassen") und
trifft damit jede Idee, die als Satzung umgesetzt wird — und das sind die
meisten kommunalen Ideen. Eine Verpackungssteuer *ist* eine Satzung; ein
Nachtmähverbot *ist* eine Satzung. Die Form sagt nichts über den Inhalt.

Das Routine-Problem steckte woanders, und der Filter dagegen war schon da:
Was auf der Liste wirklich Alltäglichkeit maß, waren **Antworten,
Mitteilungen und Berichte** (`kind` in `answer`, `notice`, `report`) — 35 der
87 Einträge. Die Verwaltung *reagiert* dort; die Idee steht in der Anfrage,
nicht in der Antwort. Dieser Filter kommt in PR 24, der Regex nicht.

## Was das für die Zukunft heißt

Sollte Routine später doch stören, ist der Weg nicht ein Wortmuster, sondern
ein Feld in `classify` — mit Golden Set und Prüfstand, wie jeder andere
Annotator. Bis dahin gilt: gemessen, verworfen, aufgeschrieben.
