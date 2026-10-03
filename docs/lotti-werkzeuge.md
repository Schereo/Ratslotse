# Lotti schlägt nach — Werkzeuge und ihre Messung

Stand 25.09.2026. Code: `council/lotti_werkzeuge.py`, Schleife in
`council/assistant.py::_mit_werkzeugen`, Schalter `lotti-werkzeuge`
(`kern/features.py`). Ohne Schalter ist Lottis Prompt zeichengleich mit dem
von vorher.

## Warum

Lotti bekam einen vorbereiteten Kontext und musste in einem Zug antworten.
Fragen über mehrere Schritte („seit 2010“, „wie viel Prozent“, die Antwort
steht auf einer anderen Seite, die Sitzung davor) beantwortete sie mit „liegt
hier nicht vor“, obwohl die Zahl in der Datenbank stand. Tim, 24.09.2026:
„ob eines der Schwächen von Lotti nicht vielleicht ist, dass sie nicht
agentisch auf den Daten handeln kann“.

## Was sie darf

Nur lesen, höchstens drei Werkzeug-Runden je Antwort, danach antwortet sie
(`tool_choice="none"`). Haushalts-Werkzeuge nur mit dem Recht `budget`.

| Werkzeug | liefert |
|---|---|
| `zeitreihe` | 18 Reihen (Schulden, Steuern, Gewerbesteuer-Plan, Personal, Zinsen, Stellen, Hebesätze, Einwohner …), jedes Jahr mit Beleg |
| `produkt_zeitreihe` | Plan-Aufwand/-Ertrag einer Aufgabe über die Jahre |
| `haushalt_nachschlagen` | der Geld-Kontext mit freien Suchbegriffen, samt Hinweis auf passende Reihen |
| `seite_lesen` | die Zahlen einer anderen Haushaltsseite |
| `betrieb_zeitreihe`, `gebuehren_zeitreihe`, `kassenstand` | Wirtschaftspläne, Gebührenkalkulationen, Liquidität je Monat |
| `rechnen` | Anteil, Veränderung, Differenz, Summe, je Einwohner*in — **nur mit Zahlen, die schon im Gespräch stehen** |
| `ratsarchiv_suchen`, `sitzungen`, `tagesordnung`, `beratungsfolge`, `beschluesse_zaehlen` | Rat: Beschlüsse, Kalender, Tagesordnung, eine Vorlage durch die Gremien, Zählen |

Text aus dem Ratsarchiv läuft durch `kern/foreign_text.defuse` und steht
zwischen `<<<AKTEN … AKTEN>>>`.

## Messung

Fakten-Eval (`eval/run_fakten.py`), GPT-6 Luna, lokale Daten (Abzug dev
vom 24.09.2026). **Schwer**: 66 Fälle `haushalt/mehrstufig/*` und
`rat/mehrstufig/*` (`eval/build_fakten_haushalt.py::mehrstufig*`,
`eval/build_fakten_mehrstufig_rat.py`), je zwei Läufe. **Leicht**: die 122
übrigen Lotti-Haushaltsfälle, ein Lauf. Zwei Läufe desselben Stands
streuen auf den schweren Fällen um bis zu **5 Fälle** — kleinere Unterschiede
sind nicht zu deuten.

Einzeln gemessen, weil Tim nach jedem Schritt wissen wollte, ob er etwas
gebracht hat:

| Schritt | schwer (2 Läufe) | leicht | Urteil |
|---|---|---|---|
| ohne Werkzeuge (30 alte schwere Fälle) | 17/30 | 111 / 108 | — |
| Werkzeuge v1 (30 alte schwere Fälle) | 24/30 | 109 / 107 | +7, leicht in der Streuung |
| **1** Messen: 66 Fälle, Gold 2025, Bewerter | 48 / 41 | 107 | neue Grundlinie |
| **2** Absage nur nach Nachschlagen (A+B) | 46 / 46 | 107 | +1,5 — in der Streuung; Absagen unter den Fehlern 25 → 19. Behalten |
| **3** Vollständigkeits-Regel im Prompt | 47 (1 Lauf) | 105 | nichts; wieder ausgebaut |
| **4** Rats-/Betriebs-/Gebühren-Werkzeuge | **54 / 50** | 106/118 (vs. 104) | **+6**; Beratungsfolge 0 → 2/2, Zählen 0 → 2/2, Haushalt von Rats-Seiten 3 → 8/10, Sitzungen 2 → 5/8 |
| **5** Anschlussfragen (knappe Anschlussfrage schlägt nach, 600 Zeichen Verlauf) | 53 / 57 | 105 | Anschlussfragen 19/20 vorher wie nachher; der Zuwachs kam von der nachlassenden Drosselung (0 statt 5–7 Stromabrisse). Wieder ausgebaut |
| **Endstand** (1, 2, 4, Ersatzweg mit Werkzeugen, Fristen) | **54 / 55** | 104 | schwer 44,5 → 54,5 von 66 (+10) gegenüber der Grundlinie aus Schritt 1; leicht in der Spanne aller Läufe (104–107), keine Fehlerart, die auf die Werkzeuge zeigt |

Kosten im Endstand: rund 0,06 Cent je schwerer Frage, 0,05 Cent je leichter
(GPT-6 Luna, Listenpreis). Wartezeit p50 schwer 7,4–7,8 s, leicht 6,3 s; p95
schwer 14–22 s.

Alle schweren Läufe sind mit demselben Stand von Gold und Bewerter
nachgewertet (`run_fakten.py nachwerten`, 25.09.2026).

### Was nicht half

- **Schritt 3**, eine Regel „die Zahl in den ersten Satz, den jüngsten
  Stand, jede Zeile einer Liste“: Auslassungen 8 → 7 → 8. Viele der
  „Auslassungen“ sind strenges Gold („alte Munition“ statt „Kampfmittel“).
  Die Prüfung vor dem Absenden (zweites Modell) war schon am 24.09. gemessen
  und brachte 163 → 163 bei +1,7 s (`docs/lotti-selbstpruefung.md`).

- **Schritt 5**: „und 2015?“ fängt schon Hebel B aus Schritt 2
  (`muss_nachschlagen`), die übrigen Anschlussfragen standen bei 19/20.

### Fallen beim Messen

- **Gold, das nicht stimmt.** Die Erhöhung des Hebesatzes stand bei 0,0 % —
  SQLite teilt ganze Zahlen ganzzahlig. Und der Bewerter las „124,2 Mio. € →
  176,8 Mio. €“ als zwei Sätze. Beides ist behoben; ein Fall, der auffällig
  oft scheitert, verdient zuerst einen Blick aufs Gold.
- **Der Ersatzweg ohne Werkzeuge.** Riss unter der Drosselung der Strom
  (5–7 von 66 Fällen), antwortete der Router-Ersatzweg ohne Werkzeuge — und
  sagte genau dort „lässt sich nicht sagen“. Er läuft jetzt mit Schalter
  durch dieselbe Schleife (`explain_question(werkzeuge=True)`).

- **Neuer Datenstand, altes Gold.** Mit dem Abzug vom 24.09. kam der
  Jahresabschluss 2025; Lotti nannte richtig 2025, das Gold verlangte 2024.
  Die Fälle nehmen 2025 jetzt als gleichwertig (`oder`).
- **Drosselung.** Am 24./25.09. war GPT-6 Luna auf dem EU-Weg über Stunden
  „temporarily rate-limited upstream“. Ohne Frist hingen einzelne Aufrufe
  über zehn Minuten — der Ersatzweg des Routers (`explain_question`) wartete
  beim EU-Weg auf Antwort-Header. Seitdem: 30 s Frist auf allen Lotti-Wegen
  (`assistant.LLM_FRIST_S`), und mit Frist bekommt der EU-Weg **einen**
  Anlauf (`llm._eu_anlauf`), dann der Verzicht-Weg.
