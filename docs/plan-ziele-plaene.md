# Plan: Aus „Ziele“ wird „Pläne der Stadt“

Stand 09.11.2026, **überarbeitet nach den Phasen 0 bis 2**. Die erste Fassung
war eine Bestandsaufnahme ohne Code: im Abzug von dev (`data/council.sqlite`,
Sitzungen 11.01.2018 bis 02.11.2026, 5.277 Vorlagen, 9.241 Beschlüsse) und
über die MCP-Werkzeuge (Anlagentexte). Inzwischen stehen Register, Zuordnung,
die erste Seite und fünf Maßnahmenlisten. Wo dabei gemessen wurde, steht hier
jetzt die Messung statt der Schätzung — und an drei Stellen hat sie den Plan
geändert (s. „Was diese Überarbeitung ändert“).

Bis heute wurde **kein bezahltes Modell aufgerufen**. Die verbleibenden
Kostenangaben sind Schätzungen aus Listenpreisen (`kern/usage.py`). Vor jedem
Lauf werden sie mit `limit=20` gemessen, und ab 1 $ fragen wir Tim.

Tim will die Seite **Analyse → Ziele** (`/council?tab=analysis&sub=ziele`) zu
einer Übersicht aller Pläne der Stadt Oldenburg umbauen: laufende und
abgelaufene Pläne, jeweils mit Quelle, Laufzeit, Maßnahmen und
Umsetzungsstand. Bei alten Plänen soll die Seite zeigen, was aus ihnen geworden
ist. Das Programm ist auf mehrere Wochen angelegt.

**Tims Entscheidungen 09.11.2026:**

- Die neue Seite entsteht zuerst auf dev, hinter dem Schalter `plaene`, und
  fährt mit dem nächsten Release. Die heutige Ziele-Seite bleibt auf Prod
  stehen, bis der Schalter dort angeht.
- **Was als Plan zählt:** wie in § 8.1 vorgeschlagen (Klassen 1–3, Pläne
  Dritter und Steuerungskonzepte nur als Verweis).
- **Externe Quellen ja:** das Monitoring im Klimaportal (jetzt Phase 3) und
  Pläne von vor 2018 von oldenburg.de (Phase 5b).
- **Möglichst wenig Handarbeit:** Die Maßnahmenlisten prüft der Agent selbst —
  vollständiger Zählabgleich gegen die Zahl der Stadt, Stichprobe gegen die
  Quelle, Befunde im PR. Tim prüft nicht jede Liste.
- **Neu: „Offene Aufträge“** (§ 3.5, Phase 4b) — wo etwas beschlossen ist und
  keine Umsetzung, kein Bericht, kein Folgebeschluss zu finden ist. Für alle
  interessant, für Ratsmitglieder der Anlass nachzufragen.
- **Einordnung in drei Bausteinen** (§ 3.3a, entschieden nach der
  Überarbeitung): Berichtsstand, Stand laut Stadt und eigene Termine des
  Plans ersetzen die fünf Stufen nach Dritteln.

## Stand der Umsetzung

| Phase | Stand | Wo |
|---|---|---|
| 0 Register und Wächter | auf dev | #1812 |
| 1 Zuordnung, Endpunkte, erste Seite | auf dev | #1818 (#1813 ist darin aufgegangen) |
| 2 Maßnahmenlisten der fünf Pilotpläne | auf dev | #1818 |
| Gestaltungsrunde | auf dev: Zeitbänder auf einer Achse, Kopfbühne, Zeitstrahl mit Lücken | #1818; § 3 beschreibt die Inhalte, die Form steht in `DESIGNSPRACHE.md` |
| 3 Stand, Berichtsstand, Kennzahlen | auf dev: Berichtsstand für alle Pläne; Stand laut Stadt für Klimaschutzplan, Wärmeplan, Aktionsplan Gewalt 2020, Ernährungsstrategie und smv2025; Mobilitätsplan mit Zitat je Maßnahme aus den Sachstandsberichten (ein Modell sucht, geprüft wird ohne Modell); THG-Kennzahl | #1819, #1822, #1823, #1827, #1830 |
| 4 Beschlüsse zu Maßnahmen | auf dev: Zuordnung über die Kennung der Maßnahme (ohne Modell) und Vorlagen, die laut eigenem Text der Umsetzung eines Plans dienen (Modell mit Golden-Set, 25 von Hand geprüfte Bezüge) | #1824, #1828 |
| 4b Wo man nachfragen kann | auf dev: Pläne ohne aktuellen Bericht. „Ratsauftrag ohne Folge“ zweimal gemessen (ohne und mit Modell), Messziel beide Male verfehlt, nicht ausgeliefert | #1825, #1829 |
| 5 Rückblick | auf dev für die zehn abgelaufenen Pläne; Maßnahmenlisten für neun Pläne; iOS-Ansicht im Code (kommt mit dem nächsten App-Build) | #1825, #1830, #1831 |
| Was im Plan steht (nach der Freigabe der Phasen, Tims Wunsch 10.11.2026) | PR offen: Zweck und drei bis sechs Kernpunkte für 36 von 45 Plänen, jeder mit wörtlichem Zitat, Seite und Link; 9 Pläne begründet ohne Block | § 3.2 Punkt 1a; `scripts/plan_kernpunkte.py` |
| Ausbau der Seiten, Paket 3 (Orte, Viertel, Haushalt) | PR offen: Karte für 10 Pläne (Straßen aus Maßnahmentiteln, Orte aus Beschlüssen), „Pläne, die dein Viertel betreffen“ in 25 Ortsbereichen, Haushaltsposten für 8 Pläne (nur Recht `budget`). Ohne Modell | § 3.2 Punkte 8–9; § 3.6 |
| Ausbau der Seiten, Paket 2 (mit Modell) | auf dev (#1834): ein Satz je Bericht mit Zitat (69 Sätze in 23 Plänen), „Neu im jüngsten Bericht“ (6 Reihen), der Plan in einfacher Sprache und drei Fragen (36 Pläne), verwandte Pläne (22 Paare, ohne Modell). Modellkosten zusammen 0,23 $ | § 3.2 Punkte 4a–4c, 1d, 7 |
| Ausbau der Seiten, Paket 1 und Bewegung (Tims Auftrag 10.11.2026) | auf dev (#1833): Kernpunkte nach Art mit Zahlen-Kacheln, Termine des Plans im Zeitband, Sprungleiste, Übersicht mit Aufklapp-Zeilen und drei Reihenfolgen; Bewegung nach DESIGNSPRACHE § 7 | § 3.1, § 3.2 Punkte 1a–1c |
| 5b Seite der Stadt | Verweise für 21 Pläne. Offen: Dokumente der Pläne von vor 2018 | mit Phase 6 |
| 6 Pflege | Kennzahlen im Cron-Protokoll, Hinweise im Prüfskript | mit Phase 5b |
| Kosten | Modell insgesamt rund 0,50 $ (Mobilitätsplan 0,004 $, Bezüge laut Vorlage 0,09 $, Ratsaufträge 0,03 $, Kernpunkte 0,37 $ samt aller Probeläufe); alles andere ohne Modell | gemessen 10.11.2026 |

Gemessen im Abzug nach den Phasen 0 bis 2:

- **Register:** 45 Pläne — 16 Maßnahmenpläne (`action`), 19 Rahmenpläne
  (`framework`), 8 Pflicht- und Fachpläne (`statutory`), 2 Verweise
  (`reference`). 17 tragen ein Enddatum, 5 eine eigene Überprüfungsfrist.
- **Übersicht:** 43 Karten in drei Gruppen (Laufend 31 · In Arbeit 2 ·
  Abgelaufen oder abgelöst 10), dazu die 2 Verweise. **14 der 43 Pläne haben
  keinen Bericht im Bestand.**
- **Zuordnung** (ohne Modell, rund eine Sekunde): 436 Tagesordnungspunkte an
  Plänen, darunter 131 Berichte und Auswertungen; 78 Beschlüsse, deren Vorlage
  die Nummer einer Planvorlage zitiert, verteilt auf 15 Pläne.
- **Maßnahmen:** fünf geprüfte Listen mit zusammen 239 Maßnahmen, alle per
  Parser, 0 $.
- **Messziele der Phase 1 erreicht:** Aktionsplan Gewalt 2020 mit allen 24
  Tagesordnungspunkten; Klimaschutzplan mit allen 15 Vorlagen der
  Berichtsreihe (3 vor dem Planbeschluss, 12 danach).

## Was diese Überarbeitung ändert

1. **Der Zählblock des Klimaschutzplans steht nur in zwei der 15 Berichte**
   (§ 1.3). „Regex über alle Berichte“ gibt es also nicht. Die Reihe 2022 bis
   2026 veröffentlicht die Stadt im Klimaportal, und sie deckt sich mit den
   beiden Vorlagen. Das Klimaportal rückt deshalb von Phase 5b in Phase 3.
2. **Die Drittel-Regel der Einordnung trägt nicht** (§ 3.3a). An den
   Pilotplänen geprüft, passt beim Klimaschutzplan keine Stufe, und welche
   passt, hängt davon ab, welche Wörter der Stadt wir als „umgesetzt“ zählen —
   das wäre unser Urteil und nicht ihres. Stattdessen drei Bausteine:
   Berichtsstand, Stand laut Stadt, eigene Termine. **Tim hat das am
   09.11.2026 so entschieden.**
3. **Die offenen Aufträge sind drei verschieden riskante Dinge** (§ 3.5).
   „Plan ohne Bericht“ fällt in Phase 3 ohne Zusatzkosten ab. „Ratsauftrag
   ohne Folge“ ist der heikle Teil und bekommt, so der Vorschlag, einen
   eigenen Schalter (§ 8, Frage B).
4. **Die Architektur beschreibt, was gebaut ist** (§ 4): andere Namen als im
   Entwurf, und der Stand wird wie die Maßnahmen eine geprüfte Datei statt
   einer Tabelle aus dem Cron.
5. **Die Phasen** (§ 5) stehen in der Reihenfolge, in der sie gebaut werden:
   3 → 4 → 4b → 5 → 5b → 6, ohne Wochenangaben. Phase 4 nimmt den alten
   Stempel nicht mehr aus dem Cron; das passiert nach Tims Entscheidung erst
   zur Freigabe auf Prod.
6. **Kosten** (§ 6): Phasen 0 bis 2 gemessen 0 $, der Rest geschätzt rund 3 $.

## 1. Befund

### 1.1 Was die Seite heute tut

- Sechs Ziele stehen fest im Code (`council/goals.py::GOALS`): Label,
  Beschreibung und Stichwörter.
- `scripts/track_goals.py` läuft im täglichen Protokoll-Cron
  (`check_protocols.py`, Schritt „Ziele“). Er lässt `deepseek-v4-pro` jeden
  Kandidaten-Beschluss als `advances` / `hinders` / `neutral` einstufen und
  schreibt das in `council_goal_links`. **Der Schritt läuft weiter**, bis
  „Pläne“ auf Prod steht (§ 8, Entscheidung 4); der neue Schritt „Pläne“
  läuft im selben Cron dahinter.
- Endpunkte: `GET /council/goals` und `GET /council/goal/{key}`. Sie werden im
  Web von `components/council-goals.tsx` gelesen, in iOS von
  `CouncilInsightsView.swift` (Tab „Ziele“).

Bestand der Stempel im Abzug:

| Ziel | bewertet | relevant | „voran“ | „bremst“ |
|---|---:|---:|---:|---:|
| klima_2035 | 582 | 345 | 212 | 16 |
| verkehrswende | 492 | 341 | 123 | 21 |
| wohnungsbau | 868 | 421 | 209 | 27 |
| bildung_betreuung | 464 | 294 | 140 | 10 |
| innenstadt | 362 | 214 | 113 | 12 |
| digitalisierung | 395 | 122 | 50 | 5 |

Die Recherche vom 09.11. hat die Schwächen schon benannt: Der Stempel
unterscheidet kaum etwas, „voran“ heißt fast nur „angenommen“, und Ausschuss
und Rat werden doppelt gezählt. Dazu kommt ein Grundproblem: Die Seite misst
**Ratsaktivität gegen ein Stichwort**. Ob ein Plan vorankommt, misst sie nicht.
Die Stadt dokumentiert das aber selbst, wie 1.3 zeigt.

### 1.2 Inventar der Pläne

Erfasst ist nur, was sich belegen ließ. „Offen“ heißt: im Bestand nicht
feststellbar. „Rat“ steht für den Ratsbeschluss. „z. K.“ heißt, dass der Rat
den Plan nur **zur Kenntnis genommen** und nicht beschlossen hat. Für die
Anzeige ist das ein wichtiger Unterschied.

**Seit Phase 0 ist das Register die verbindliche Quelle**
(`council/plans.py`, 45 Pläne). Die Tabellen unten bleiben als Beleg der
Bestandsaufnahme stehen. Wo Register und Tabelle auseinandergehen, gilt das
Register, und `scripts/pruefe_plaene.py` hält es gegen den Bestand.

#### A. Laufend, mit Maßnahmenliste und Berichtsreihe (Pilotkandidaten)

| Plan | Beschluss | Laufzeit | Maßnahmen | Berichte | Kennzahl |
|---|---|---|---|---|---|
| **Klimaschutzplan Oldenburg 2035** (mit Klimaziel) | Klimaziel `21/0249/2`, Rat 26.04.2021, einstimmig; Plan `22/0910`, Rat 19.12.2022, angenommen | bis 2035; Vorschlag zur Fortschreibung für 2027 angekündigt (`26/0750`) | 90 (`26/0074`), inzwischen 97 (`26/0750`); Kennungen wie `Gebäude_05`, `Klimapakt_07`, `Beratung_01` | „Klimaschutz-Aktivitäten n/JJJJ“ dreimal im Jahr, 15 Stück von `22/0037` (02/2022) bis `26/0750` (ASUK 08.10.2026), Berichtswesen nach `22/0036`; Statusverteilung in `26/0074` und `26/0750`; externes Fortschrittsbarometer auf klimaportal.oldenburg.de/monitoring | THG-Bilanz (`23/0653`, `25/0131`, `25/0866`): Zwischenziel 2023 −15 %, erreicht −17,9 % gegenüber 2020 (1,14 Mio. t) |
| **Oldenburger Wärmeplan** | `26/0236`, Rat 01.06.2026, mehrheitlich | Überprüfung spätestens nach fünf Jahren (§ 25 WPG); alle Maßnahmen „kurz- oder mittelfristig“ | 18 (K1–K3, F1–F2, T1–T5, O1–O8), je Maßnahme mit Stand und Zielsetzung in der Vorlage | Ergebnisbericht `25/0743`; danach über die Klimaschutz-Berichte (z. B. O7 in `26/0750`) | Zielsetzung je Maßnahme fürs Monitoring (in `26/0236`) |
| **Mobilitätsplan Oldenburg 2030** | `23/0211/2`, Rat 26.06.2023, mehrheitlich; Vorgehen `23/0867`, Rat 27.11.2023; Priorisierung `24/0216`, Rat 27.05.2024 | bis 2030 | über 250 Einzelmaßnahmen, rund 70 priorisiert (Anlage 1 zu `24/0216`) | jährlich im Verkehrsausschuss: `23/0562`, `25/0041`, `26/0190`; Zuordnung zum Klimaschutzplan `25/0379` | Zielzahlen in der Priorisierung (7 Premiumrouten, 4 umgestaltete und 9 neue Fahrradstraßen, Ladepunkte je Quartal); Modal-Split-Erhebung lief 2024 an |
| **Aktionsplan gegen Gewalt an Frauen\* und Häusliche Gewalt** | `20/0564`, Rat 28.09.2020, einstimmig; Evaluation und Fortschreibung `26/0681/1`, Rat 28.09.2026, einstimmig | kein Enddatum; Umsetzungszeitraum 2020–2025, Fortschreibung „für die kommenden Jahre“ | 2020: laut Evaluation 90 (8 übergreifend, 57 Gewalt gegen Frauen\*, 25 Häusliche Gewalt); die Tabelle im Anhang hat 91 Zeilen; 2026: 6 Fokusthemen × 5 = 30 Empfehlungen | schriftlich `21/0704`, `22/0494`, `23/0356`, `26/0080`; 7 Berichte ohne Vorlage und ohne Text (08/2019, dazu sechs „mündliche“ 10/2023–03/2025); Evaluation mit dem Stand **jeder** Empfehlung (Anlage 314635, Anhang 4.1, S. 64–89); künftig jährlicher Bericht | Fallzahlen 2020–2025 (Kap. 1.3), keine Zielwerte |
| **Ernährungsstrategie** | `24/0810` und `24/0811`, Rat 24.02.2025, mehrheitlich | offen | 9 Ziele, 68 Handlungsansätze (A1 …), davon 5 zur Umsetzung beschlossen | `23/0151`, `23/0741`, `24/0390`; Umsetzungsstand **je Ansatz** in `26/0431` (ASUK 06/2026) | qualitative Stufe 0/25/50/75/100 % je Ansatz |
| **Lärmaktionsplan** (Fortschreibung) | `24/0293/1`, Rat 30.09.2024, mehrheitlich; Vorgängerprüfung `20/0049` | Tempo 30, Stufe 1 seit 14.12.2025, Stufe 2 geplant Ende 2027 | offen (Anlage 3 nicht ausgewertet); Tempo-30-Abschnitte auf neun Straßen namentlich im Beschluss | `25/0696` (Umsetzung Tempo 30) | offen |
| **Digitalisierungsstrategie** | `23/0708`, Rat 18.12.2023, einstimmig | Vision bis 2045; erste Phase des Umsetzungsplans 2025–2027 | 40 in fünf Gruppen, nicht nummeriert (Umsetzungsplan `24/0574`) | Statusbericht `25/0796` (11/2025) | z. B. 248 digitale Leistungen im Serviceportal (`25/0796`) |
| **Kita-Ausbaukonzept** | Grundkonzept Rat 30.06.2008 (vor dem Bestand); 4. Fortschreibung `18/0308`, Rat 25.06.2018; 5. Fortschreibung `22/0620`, Rat 26.09.2022 | Ausbau bis 2030 | Gruppenzahlen je Fortschreibung; laufende Vorlagen „Maßnahmenplanung … Kindertagesbetreuung“ | jährlich mit der Kita-Situation (laut `18/0308`) | Zielquoten 55 % Krippe, 10 % Tagespflege, 99,5 % Kindergarten; die Ist-Werte sind offen |
| **Agenda 2025 „Selbstbestimmt und mittendrin!“** (altersgerechte Stadt) | `25/0403`, Rat 30.06.2025, einstimmig | Evaluation 2028 | 4 Bausteine mit 26 Maßnahmenpaketen (1.1 … 4.9); Kapitel „Monitoring“ | noch keiner | offen |
| **Handlungskonzept Kinder- und Jugendbeteiligung** | `26/0710/1`, Rat 28.09.2026, einstimmig | **3 Jahre**, danach Evaluation | 8 Handlungsfelder mit Zielen für die Laufzeit | noch keiner | offen |
| **Konzept treibhausgasneutrale Verwaltung** | `25/0896`, Rat 23.02.2026, einstimmig (am 15.12.2025 ohne Beschluss) | Ziel 2035 (gesetzlich 2040) | offen (identisch mit KSP-Maßnahme `Gebäude_05`) | über die Klimaschutz-Berichte | Ausgangsbilanz der Verwaltung |

#### B. Laufende Rahmenpläne und Strategien, meist ohne eigene Berichtsreihe

| Plan | Beschluss | Laufzeit | Stand und Berichte |
|---|---|---|---|
| ISEK Oldenburg 2035 / Zukunft 2050 | `24/0425`, Rat 30.09.2024, mehrheitlich (Ebene 1) | 2035 bzw. 2050 | Ebene 2 im Bericht `26/0416`; dort ist ein „Zielkatalog mit Indikatoren und Zielzahlen“ angekündigt; Ebene 3 (Fokusräume) läuft bis 2027 |
| Masterplan Stadtgrün | `22/0642`, Rat 26.09.2022, einstimmig | „15 bis 20 Jahre“ | nach dem Beschluss kein Umsetzungsbericht gefunden |
| Baumerhalt- und Entwicklungsstrategie | `25/0388`, Rat 30.06.2025, mehrheitlich | regelmäßige Fortschreibung | `25/0158` (vor dem Beschluss), `26/0634` (mündlich) |
| Spielleitplanung 2026 | `26/0255`, Rat 01.06.2026, mehrheitlich | „15 bis 20 Jahre“, jährliches Arbeitsprogramm | noch keiner |
| Einzelhandelsentwicklungskonzept (EEK) | `24/0717/1`, Rat 16.12.2024, einstimmig | offen | ein Steuerungsinstrument, kein Maßnahmenplan |
| Nachhaltigkeitsleitbild | `22/0240/1`, Rat 30.05.2022, mehrheitlich | offen | Nachhaltigkeitsbericht `25/0077` mit SDG-Indikatoren |
| Integrationskonzept | Fortschreibung `19/0697/2`, Rat 24.02.2020 (z. K. mit Auftrag für Schwerpunktjahre) | Umsetzung 2020–2025 | Maßnahmenkatalog `21/0287`; evaluiert 2025; **Integrationskonzept 2026** am 11.03.2026 im Ausschuss vorgestellt (`26/0191`, Kenntnisnahme), einen Ratsbeschluss gibt es im Bestand nicht; Sachstand `26/0670` |
| Gesamtkonzept niedrigschwellige Wohnungslosen- und Suchthilfe | `19/0239`, Rat 27.05.2019, einstimmig | offen | Sachstand `20/0121`, `21/0121`, `23/0339`, `24/0219`, `26/0484`; Drogenhilfestrategie `26/0469` (Bericht) |
| Orte für Alle | `21/0478/1`, Rat 28.06.2021, einstimmig | offen | Fortschreibung `26/0522` (Bericht 09/2026) |
| Inklusion: Kommunaler Aktionsplan Inklusion (KAI, 2015) und „Oldenburg – eine Stadt für alle“ | KAI vor dem Bestand; Erneuerung `23/0189`, Rat 24.04.2023, einstimmig | Fokusthemen „bis Ende 2025“, **abgelaufen** | KAI: 71 Haupt- und 236 Untermaßnahmen; Stand 31.12.2020 (`21/0355`): 70 in Bearbeitung, 61 zurückgestellt, 70 abgeschlossen (ohne schulische Inklusion); einen Bericht über die Fokusthemen gibt es im Bestand nicht |
| Demografiestrategie | `20/0371/1`, Rat 28.09.2020, z. K. | offen | Zwischenbericht `23/0088` |

#### C. Pflicht- und Fachpläne mit fester Laufzeit

| Plan | Beschluss | Laufzeit | Bemerkung |
|---|---|---|---|
| Gleichstellungsplan 2024–2026 (NGG, Personal der Verwaltung) | `24/0362`, Rat 17.06.2024, z. K. | **endet 31.12.2026** | Vorgänger 2018–2020 (`18/0406`) und 2021–2023 (`21/0399`); jeder Plan evaluiert den vorigen |
| Abfallwirtschaftskonzept 2022–2027 | `21/0668`, Rat 27.09.2021, einstimmig | **endet 2027** | |
| Brandschutzbedarfsplan | `25/0833`, Rat 15.12.2025, einstimmig | offen | schreibt den Plan von 2007 fort |
| Nahverkehrsplan (ZVBN) | Teilfortschreibung beauftragt: `26/0223`, Rat 01.06.2026, einstimmig | Linienbündel bis 01.06.2028 | Plan eines Zweckverbands, nicht der Stadt |
| Rahmenkonzepte Schul- und Kitaverpflegung | `19/0943` (Rat), `21/0459` (Rat) | offen | Bio-Anteil fortgeschrieben (`22/0811/1`, `23/0856`, `24/0688`, `25/0634`); Evaluation `26/0325`, `26/0461`; zugleich A1/A2 der Ernährungsstrategie |

#### D. In Arbeit (noch kein Beschluss)

- **Klimaanpassungskonzept (KLAK):** Auftrag `24/0830` (Ausschüsse 12/2024),
  Zwischenstände `25/0465` und `25/0863`. Von sieben Arbeitspaketen sind vier
  abgeschlossen; Maßnahmenkatalog und Controlling stehen noch aus.
- **Fortschreibung des Klimaschutzplans** (Vorschlag 2027) und
  **ISEK-Fokusräume 2035** (bis 2027).
- **Integrationskonzept 2026:** vorgestellt, Beschlusslage offen (s. B).
- **Kulturentwicklungsplanung:** nur erwähnt (`24/0708`), es gibt keinen Plan.
- **SUMP Oldenburg 2040:** bisher nur eine Anregung (`26/0298`, Bericht).
- **Luftreinhalteplan:** Fortschreibung beschlossen (`17/0844`, Rat
  22.01.2018), Auslegung `18/0264`, Sachstand `19/0636`. Einen Abschluss gibt
  es im Bestand nicht, der Stand ist **offen**.
- **Wohnkonzept:** Das Wohnkonzept 2025 (Rat 2013/2014, vor dem Bestand) hat
  die NBank laut `22/0755` als veraltet eingestuft. Es gibt nur die
  Teilfortschreibung „Wohnraumversorgungskonzept“ (`22/0755`, Bericht). Eine
  neue Gesamtfassung wurde nicht gefunden, der Stand ist **offen**.

#### E. Abgeschlossen oder abgelöst (Kandidaten für den Rückblick)

| Plan | Beleg | Was der Bestand über den Ausgang sagt |
|---|---|---|
| Schulentwicklungsplan 2018 | `18/0420/1`, Rat 25.06.2018 (z. K. mit Auftrag) | 10 Empfehlungen führten zu 12 Vorlagen; im Abschlussbericht `19/0942` (Rat 16.12.2019, z. K.) steht: „Alle Beschlussvorschläge wurden angenommen.“ **Der klarste Rückblick-Fall.** |
| Aktionsplan gegen Gewalt 2020–2025 | `26/0681/1` | Evaluation mit dem Stand jeder Empfehlung; danach fortgeschrieben (s. A) |
| Integrationskonzept 2020–2025 | `26/0191` | 2025 evaluiert, Nachfolger 2026 |
| Stadtentwicklungsprogramm step2025 | Rat 31.03.2014; Evaluation `21/0217` | Viele Maßnahmen umgesetzt oder in Umsetzung, Fortschreibung empfohlen; abgelöst durch das ISEK |
| Strategieplan Mobilität und Verkehr smv2025 | `18/0254`, Rat 27.08.2018 | abgelöst durch den Mobilitätsplan 2030 (`23/0211/2`); Stand jeder der 112 Einzelmaßnahmen (10/2023) im Anhang 1 zur Fortschreibung des Lärmaktionsplans (`24/0293/1`, Anlage 280377) |
| Rad- und Fußverkehrsprogramm (jährlich) | `18/0056` (Rat 19.02.2018), `19/0080`, `19/0916`, `20/0163`, `22/0072` | nach 2022 im Bestand nicht mehr gefunden, Stand **offen** |
| Aktionsplan Energie 2019/2020 | `18/0516`, `19/0836`, `20/0076` | Vorläufer des Klimaschutzplans |
| KAI 2015 / Fokusthemen bis 2025 | `21/0355`, `23/0189` | Stand 2020 bekannt, Ausgang **offen** |
| Gleichstellungspläne 2018–2020 und 2021–2023 | `18/0406`, `21/0399` | jeweils im Folgeplan evaluiert |
| Innenstadtstrategie / Bündnis Innenstadt | Berichte 2018–2020, Grundsatzvereinbarung `20/0820` | Stand **offen** |
| Gewerbeflächenentwicklungskonzept 2018 | `19/0132/1` (Rat) | Stand **offen** |
| Bäderstrategie | `18/0889/1` (Rat, 01/2019) | Stand **offen** |
| Sportentwicklungsplan 2009 | Ratsbeschluss 22.06.2009, zitiert in `18/0192` und `18/0917` | Eine Fortschreibung wurde nicht gefunden, Stand **offen** |
| Leitantrag Fridays for Future 2020 | Dutzende Einzelpunkte als eigene Vorlagen (`20/06xx`–`21/0209`) | eher ein Programm als ein Plan, Stand **offen** |

#### Wie die sechs heutigen Ziele aufgehen

| heutiges Ziel | Plan dahinter |
|---|---|
| klima_2035 | Klimaschutzplan 2035, Wärmeplan, treibhausgasneutrale Verwaltung |
| verkehrswende | Mobilitätsplan 2030 (davor smv2025), Lärmaktionsplan |
| wohnungsbau | **kein aktueller Plan**: Wohnkonzept 2025 veraltet, nur die Teilfortschreibung 2022 |
| bildung_betreuung | Kita-Ausbaukonzept (5. Fortschreibung); der Schulentwicklungsplan 2018 ist abgeschlossen |
| innenstadt | Innenstadtstrategie (2018–2020, offen), EEK 2024, Sanierungsgebiete |
| digitalisierung | Digitalisierungsstrategie mit Umsetzungsplan 2025–2027 |

### 1.3 Die Stadt misst schon, aber jede Stelle anders

Für mehrere Pläne steht der Stand bereits im Bestand, allerdings in fünf
verschiedenen Formen:

| Form | Beispiel | Lesbar wie |
|---|---|---|
| a) Zählblock im Vorlagentext | KSP: „Aktuell sind die 97 Klimaschutzmaßnahmen wie folgt umgesetzt: 10 Zuordnung Amt, 15 In Planung, 9 Umsetzungsreif, 34 In Umsetzung, 20 Realisiert, 9 Ein-/Zurückgestellt“ (`26/0750`) | per Regex — aber **nur in zwei der 15 Berichte** (s. u.) |
| b) Abschnitt oder Tabelle je Maßnahme im Text | Wärmeplan `26/0236`: sechs der 18 Maßnahmen stehen unter „Maßnahmen in Umsetzung“, für die übrigen zwölf nennt die Vorlage ein Vorhaben und keinen Stand. Ernährungsstrategie `26/0431`: alle 68 Ansätze mit Priorität und Stufe (die Tabellen sind Text; Bilder sind nur die Kreisdiagramme darunter — die frühere Angabe „ab A11 nur als Bild“ war falsch) | Parser, ohne Modell |
| c) Tabelle je Maßnahme in einer PDF-Anlage, Stand **als Zellfarbe** | Aktionsplan Gewalt, Anhang 4.1: dunkelgrün = umgesetzt, hellgrün = einmal umgesetzt, wiederholungsbedürftig, pastellgrün = abgegeben, gelb = begonnen, rot = nicht umgesetzt, weiter nötig, grau = eingestellt | Der Text allein verliert den Stand. Die Füllfarben lassen sich mit PyMuPDF (`page.get_drawings()`) lesen. |
| d) Fließtext-Sachstand | Mobilitätsplan `26/0190`, Integrationskonzept `26/0670`, Wohnungslosenhilfe | Modell je Maßnahme mit Zitat, danach Review |
| e) Mündlicher Bericht ohne Text | 7 zum Aktionsplan Gewalt (2019–2025); im ganzen Bestand stehen rund 540 Tagesordnungspunkte „mündlicher Bericht“ | nur Termin und Gremium, dazu das Protokoll, falls vorhanden |

**Der Zählblock steht nur in zwei Berichten.** Von den 15 Vorlagen der Reihe
„Klimaschutz-Aktivitäten“ tragen ihn `26/0074` (90 Maßnahmen) und `26/0750`
(97). `26/0418` nennt zwei Zahlen im Satz („22 realisierte, neun
zurück-/eingestellt“), `25/0742` vergleicht nur in Worten, die älteren
verweisen auf Grafiken und das Klimaportal. Eine Zeitreihe aus den Vorlagen
allein hätte zwei Punkte.

**Die Reihe steht im Klimaportal** (klimaportal.oldenburg.de/monitoring,
Diagramm „Umsetzungsstatus der Klimaschutzmaßnahmen“, Quelle laut Portal:
„Stadt Oldenburg (September 2026)“):

| Status im Wortlaut des Portals | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|
| 0 – Neu/Noch nicht begonnen | 22 | 4 | 1 | 1 | 0 |
| 1 – Zuordnung Amt | 18 | 31 | 12 | 6 | 10 |
| 2 – Planung | 27 | 27 | 24 | 20 | 15 |
| 3 – Umsetzungsreif | 5 | 4 | 9 | 9 | 9 |
| 4 – In Umsetzung | 7 | 9 | 19 | 25 | 34 |
| 5 – Realisiert | 11 | 15 | 20 | 22 | 20 |
| 6 – Ein-/Zurückgestellt | 0 | 0 | 5 | 7 | 9 |
| **Summe** | 90 | 90 | 90 | 90 | 97 |

Die Spalte 2025 ist Zahl für Zahl der Zählblock aus `26/0074`, die Spalte 2026
der aus `26/0750`. Portal und Ratsvorlage sind also dieselbe Zählung, und die
Vorlagen taugen als Gegenprobe. Was das Portal sonst hergibt und was nicht:

- **Stand je Maßnahme** steht auf den Paketseiten
  (`/massnahmen/<handlungsfeld>/<paket>`), im Wortlaut der Stadt („in
  Umsetzung“, „Realisiert, Daueraufgabe“, „Planung“), mit Kennung
  (`FußRad_07`) und Federführung — **aber nicht verlässlich, und deshalb
  übernehmen wir ihn nicht** (Tims Entscheidung 09.11.2026, § 8 Nr. 8).
  Gemessen: Dieselbe Maßnahme steht auf mehreren Seiten mit verschiedenen
  Ständen (sechs Fälle, etwa `Parken_02` einmal „Planung“ und einmal
  „Realisiert“), drei verschiedene Maßnahmen tragen die Kennung `Bildung_01`,
  und nur 57 der 90 Maßnahmen unserer Liste lassen sich nach Kennung und Titel
  eindeutig lesen. Die Summe geht nicht in der Reihe auf. Ein veraltetes
  „Planung“ neben einer Maßnahme, die die Stadt anderswo als „Realisiert“
  führt, wäre ein falscher Vorwurf mit Quellenangabe.
  `python scripts/plan_status.py --portal-massnahmen` zeigt den Abgleich.
- **Die Kurzübersicht der Stadt hat selbst einen Fehler:** `FußRad_01` und
  `FußRad_02` tragen dort denselben Titel. Unsere Liste gibt die Quelle
  wieder; das Portal nummeriert an der Stelle anders.
- **Technik:** eine statische Astro-Seite; die Daten stehen als JSON in den
  `props` der `<astro-island>`-Elemente und lassen sich ohne Browser lesen.
  Das Diagramm „Fortschrittsbarometer“ lädt dagegen erst zur Laufzeit aus
  einer Tabelle bei Google und bleibt außen vor.
- **Erlaubnis:** `robots.txt` erlaubt alles (`User-agent: *`, `Allow: /`), die
  Sitemap nennt 100 Adressen. Diensteanbieter ist laut Impressum nicht die Stadt
  selbst, sondern ein Unternehmen (Wandel WerkStadt UG); eine
  Open-Data-Lizenz steht dort nicht. Daraus folgt die
  Regel: Wir übernehmen **Tatsachen** (Statuswerte, Zahlen, Stichtage) mit
  Quelle und Link, aber weder Texte noch Grafiken.
- **Der Vorbehalt des Portals gehört in die Anzeige.** Das Statussystem soll
  nach eigener Aussage nur einen zusammenfassenden Überblick geben; über die
  tatsächliche Umsetzung der einzelnen Maßnahme will es nichts aussagen. Und
  viele realisierte Maßnahmen laufen laut Portal als Daueraufgaben weiter.

**Die Zahlen der Stadt sind selbst in Bewegung, und das ist der wichtigste
Grund gegen eine eigene Quote.** Die Tabelle zeigt es: Von 2025 auf 2026
wächst die Summe von 90 auf 97, und „Realisiert“ **sinkt** von 22 auf 20,
während „In Umsetzung“ von 25 auf 34 steigt. Laut `26/0418` sind „etliche
Maßnahmen … nicht (mehr) treffend beschrieben“. Eine Quote wie „22 %
umgesetzt“ wäre also Scheinpräzision. Beim KAI addiert sich der Stand von 2020
(70 + 61 + 70) zu 201, nicht zu 236 Untermaßnahmen. Das stimmt aber, denn die
35 Maßnahmen der schulischen Inklusion sind ausgenommen. Solche Fußnoten muss
jede Anzeige mitführen.

**Wirkung ist nicht Umsetzung.** Die THG-Bilanz 2023 (`25/0866`) meldet −17,9 %
gegenüber 2020 und damit mehr als das Zwischenziel. Derselbe Bericht nennt als
Ursache zuerst den bundesweiten Strommix (453 statt 505 g CO₂e/kWh). Ein
Rückblick, der die Minderung dem Plan zuschreibt, wäre falsch.

### 1.4 Wie Beschlüsse zu Plänen finden

Die ersten drei Wege sind seit Phase 1 gebaut; die Spalte „Gemessen“ nennt,
was sie im Abzug liefern.

| Weg | Befund | Taugt für | Gemessen |
|---|---|---|---|
| Vorlage des Plans samt Fassungen (`/1`, `/2`) und Beratungsfolge | immer vorhanden | „Beschluss des Plans“, sicher | 109 Stationen „Beschluss“, 80 „Vorbereitung“, 34 „Änderung“ |
| Berichtsreihe über den Titel | z. B. 15 × „Klimaschutz-Aktivitäten“, 24 Tagesordnungspunkte zum Aktionsplan Gewalt (2018–2026), 8 davon ohne Vorlage | „Bericht“, sicher, sobald das Muster je Plan von Hand gesetzt ist | 131 Berichte und Auswertungen an 29 Plänen; 14 Pläne ohne einen |
| Verweis über die **Nummer** | selten: `22/0910` in 8 fremden Vorlagen, `21/0249` in 14, `20/0564` in 0 | sicher, aber dünn | 78 Beschlüsse an 15 Plänen (Schulverpflegung 30, Klimaschutzplan 22, Gewerbeflächenkonzept 7) |
| Verweis über den **Namen** | häufig: „Klimaschutzplan“ in 103 Vorlagen, „Mobilitätsplan“ in 57, ISEK 59, EEK 64 | nur Kandidaten; **eine Nennung ist keine Umsetzung**, beim EEK sind es fast nur Begründungen von Bebauungsplänen | Phase 4 |
| Maßnahmen-Kennung im Text | KSP-Kennungen (`Gebäude_02`, `Wärme_03` …) kommen in Vorlagen vor (mindestens 44 verschiedene), A1–A68 der Ernährungsstrategie, O1–O8 des Wärmeplans | „setzt Maßnahme X um“, sicher | Phase 4; die Kennungen liegen seit Phase 2 als Datei vor |
| Die Akte (`council_matters`, 7.488; 993 Verweiskanten) | bündelt je Vorlagenstamm, nicht je Plan; der Aktionsplan Gewalt liegt über mehr als 15 Akten verstreut | Bausteine; der Plan ist eine Ebene darüber | Phase 4 |
| Modellurteil über die Kandidaten | heute `track_goals` mit Stempel ohne Plan- oder Maßnahmenbezug | wird ersetzt durch „Welche Maßnahme, welche Beziehung?“ | Phase 4 |

## 2. Ziel

Ein Plan ist ein **eigenes Objekt** mit Quelle, Beschlussart, Laufzeit,
Vorgänger und Nachfolger, Maßnahmen, Berichten und einer Kennzahl. Seinen
Stand zeigen wir **so, wie ihn die Stadt berichtet**, immer mit Datum und
Beleg. Ratslotse vergibt keine Note und rechnet keine Quote über Pläne. Wo
der Bestand schweigt, sagen wir das. Ein Satz wie „seit 2022 kein
Umsetzungsbericht im Rat“ ist selbst eine Information.

## 3. Gestaltung

Grundlage ist die Designsprache (`web/frontend/DESIGNSPRACHE.md`): Mono-Kicker
mit ehrlicher Zählung (§ 5), Quellen-Zeile RG-02, Zeitstrahl RG-03 mit
„AKTUELLER STAND“, Semantik-Tints statt Vollfarben und keine
Selbstvergewisserung (§ 8).

**Eine Gestaltungsrunde läuft** und nimmt sich Übersicht und Detailseite noch
einmal vor. Was sie ändert, wird hier nachgezogen. Fest stehen die Inhalte
(§ 3.1 bis 3.3), die Regeln (§ 3.4) und dass das Backend alles baut, was
Logik ist — daran hält sich jede Fassung.

### 3.1 Übersicht

Drei Gruppen untereinander: **Laufend · In Arbeit · Abgelaufen oder
abgelöst**. Innerhalb der Gruppen sortieren wir nach Themenfeld, dann nach dem
jüngsten Bericht. Eine Karte je Plan zeigt:

- Kicker: `KLIMA · BESCHLOSSEN 12/2022 · BIS 2035`. Ein Plan, den der Rat nur
  zur Kenntnis genommen hat, heißt `ZUR KENNTNIS 06/2018`.
- Titel und Amt, seit Phase 2 auch die Zahl der Maßnahmen.
- **Letzter Bericht**: Titel, Gremium und Datum. Gibt es keinen, steht dort
  „Kein Umsetzungsbericht im Rat seit dem Beschluss“.
- Eine Statusverteilung **nur**, wenn die Stadt selbst eine liefert. Sie
  erscheint als Reihe von Zählern in den Worten der Stadt („34 in Umsetzung ·
  20 realisiert · 9 zurückgestellt“) mit dem Zusatz „laut Bericht vom
  08.10.2026“. Einen Fortschrittsbalken mit Prozentzahl gibt es nicht.
  *(Phase 3)*

Unter den Gruppen steht die Liste „Auch im Register · Steuerungskonzepte und
Pläne Dritter“ mit den Verweisen.

**Aufklappen und Reihenfolgen (11/2026).** Ein Tipp auf eine Zeile klappt
auf, worum es im Plan geht: Zweck, die ersten zwei Kernpunkte, der letzte
Bericht — der Titel bleibt der Weg zum Plan. (Der Zweck-Satz war aus der Karte
geflogen, weil er die Liste rund 40 % länger machte; aufgeklappt kostet er
keinen Platz.) Neben der Gliederung nach Status gibt es drei Reihenfolgen,
gerechnet im Backend (`plan_pages.views`): **Zuletzt berichtet** · **Endet
bald** (laufende Pläne mit Enddatum) · **Lange kein Bericht** (laufend, seit
über einem Jahr kein Bericht gefunden; ohne Bericht zählt der Beschluss).
Jede reiht nach einem Datum, keine nach gut oder schlecht; die dritte trägt
den Satz, dass die Lücke etwas über die Berichte sagt und nichts über die
Arbeit.

Gebaut sind die drei Gruppen, die Karte ohne Statusverteilung und die
Verweisliste. Eine **Zeitleiste** (Balken vom Beschluss bis zum Laufzeitende;
offene Enden laufen blass aus; Vorgänger und Nachfolger sind verbunden) ist
nicht gebaut. Sie bleibt eine zweite Ansicht ab Tablet-Breite; ob und wie sie
kommt, entscheidet die Gestaltungsrunde.

### 3.2 Detailseite je Plan

1. **Kopf:** Name, federführendes Amt, Beschluss-Badge („Beschlossen“ oder
   „Zur Kenntnis genommen“), Gremium, Datum, Link zur Vorlage und zur
   Anlage mit dem Plantext. *(gebaut)*
1a. **WAS DER PLAN FESTLEGT** (direkt unter dem Kopf, vor den Berichten): ein
   Satz, wozu es den Plan gibt, und drei bis sechs Kernpunkte — Ziele,
   Vorgaben, Zahlen, Zuständigkeiten, Fristen. Jeder Satz trägt seinen Beleg:
   ein Tipp klappt die wörtliche Stelle auf, der Link führt ins Dokument, bei
   Anlagen auf die Seite. Wo ein späterer Beschluss den Punkt gesetzt hat,
   steht „Stand <Datum>“ davor (Schulverpflegung: Bio-Anteil nach dem
   Beschluss vom 01.12.2025). Die Überschrift sagt, wie verbindlich der Plan
   ist (Regel 7): „festlegt“ nur bei einem Beschluss, sonst „Was im Plan
   steht“ oder „Was der Entwurf vorsieht“. Ohne Plantext kein Block und kein
   Platzhalter. *(gebaut; Entstehung und Prüfung unten)*
   Die Kernpunkte stehen **nach Art gegliedert** (`CONTENT_GROUPS` in
   `council/plan_pages.py`): Ziele oben, dann die Zahlen als Kacheln mit großer
   Ziffer („100 %“, „226“), dann Regeln und Zuständigkeiten, dann Vorhaben und
   Termine. Die Zahl einer Kachel und ihr Stichwort sind **von Hand gesetzt**
   (`figure` am Kernpunkt) und kommen nur auf die Seite, wenn jede Ziffer im
   Zitat steht (`plan_judge.check_extras`). Eine Kachel zeigt, was der Plan
   festlegt oder annimmt — nie, was daraus geworden ist (§ 3.4 Nr. 4).
   *(gebaut)*
1b. **Termine des Plans im Zeitband:** Nennt ein Kernpunkt einen Termin („bis
   2030“, „ab Schuljahr 2026/2027“), steht er als Wimpel im Zeitband des
   Kopfes und führt per Tipp zu seinem Satz. Auch er ist von Hand gesetzt
   (`due`), und das Jahr muss im Zitat stehen. Der Wimpel ist eine Angabe aus
   dem Plan, keine Frist von uns: Er sieht vor und hinter „heute“ gleich aus
   und sagt nichts darüber, ob der Termin gehalten wurde. Ein Termin im Jahr
   des Laufzeitendes steht nicht doppelt; einer weiter vorn als der Horizont
   der Übersicht (zehn Jahre) bleibt ein Satz und wird keine Marke — „im Jahr
   2050“ stauchte sonst die ganze Achse. *(gebaut)*
1c. **Sprungleiste:** unter dem Kopf, beim Rollen oben stehend: die
   Abschnitte, die es auf diesem Plan gibt, mit Zählern (`sections`). *(gebaut)*
1d. **Lotti erklärt's einfach, und drei Fragen:** drei kurze Sätze in
   Alltagssprache, zugeklappt über den Kernpunkten, und unter dem Block drei
   Fragen, die „Frag den Rat“ mit der Frage vorbelegt öffnen (einen eigenen
   Plan-Kontext nimmt die KI-Frage nicht an). Die Quelle sind **nur die
   belegten Kernpunkte**, nicht die Dokumente (`scripts/plan_einfach.py`,
   `council/plan_plain/<plan>.json`): Ohne Modell geprüft wird, dass keine
   Zahl auftaucht, die die Kernpunkte nicht nennen; eine zweite Lesung des
   Modells streicht die Fassung, wenn ein Satz mehr sagt. Die Datei trägt einen
   Fingerabdruck der Kernpunkte — ändert sich einer, zeigt die Seite die
   Fassung nicht mehr, und Test wie Prüfskript melden es. Die Fragen hängen
   je an einem Kernpunkt oder am Stand; nach Geld fragt nur, wer einen Betrag
   vor sich hat (eine Frage, die ins Leere läuft, wäre schlimmer als keine).
   *(gebaut)*
2. **LAUFZEIT:** Beginn, Ende oder „ohne Enddatum“, die nächste vorgesehene
   Überprüfung (z. B. Wärmeplan spätestens 2031) sowie Vorgänger und
   Nachfolger. *(gebaut)*
3. **MASSNAHMEN** (Kicker: „97 · laut Bericht vom 08.10.2026“): gruppiert
   nach Handlungsfeld, je Maßnahme Kennung, Titel und Statuschip im Wortlaut
   der Stadt samt Datum. Ein Tippen zeigt den Verlauf und den Beleg. Hat sich
   die Zählbasis geändert, sagt ein Hinweis das („2022 mit 90 Maßnahmen
   beschlossen“). *(Liste und Hinweis gebaut; Statuschip und Verlauf Phase 3)*
4. **BERICHTE:** Zeitstrahl aller Berichte, mündliche als „mündlich, ohne
   Text“ markiert; die letzte Station ist „AKTUELLER STAND“. *(gebaut)*
4a. **Ein Satz je Bericht:** Die Titel sagen nichts („Klimaschutz-Aktivitäten
   3/2026 - Bericht“). Unter dem Titel steht deshalb, als „Laut Bericht“
   gekennzeichnet (§ 3.4 Nr. 3), in einem Satz, was die Verwaltung meldet — mit
   dem wörtlichen Zitat auf Tipp und als Tooltip an der Marke im Zeitband.
   Ein Modell schlägt vor (`scripts/plan_berichte.py`), in die Datei
   (`council/plan_reports/<plan>.json`) kommt nur, was ohne Modell belegt ist:
   Das Zitat steht wörtlich in der Vorlage, jede Zahl des Satzes im Zitat;
   je Plan zitiert jede Stelle nur ein Bericht, der früheste. Berichte ohne
   Vorlagentext (mündlich, nur als Anlage) bleiben ohne Satz. *(gebaut)*
4b. **Neu im jüngsten Bericht:** Gehören die zwei jüngsten Berichte zur
   selben Reihe (gleicher Titel bis auf Nummer und Jahr), stehen über dem
   Zeitstrahl bis zu drei Dinge, die im jüngsten neu sind. Geprüft ohne
   Modell: Das Zitat steht im jüngsten Bericht und im vorigen **nicht**. Die
   Seite zeigt den Block nur, solange der Bericht wirklich der jüngste und
   nicht älter als zwei Jahre ist. *(gebaut)*
5. **KENNZAHL** (nur wo der Plan eine nennt): Soll und Ist mit Bilanzjahr und
   Quelle, dazu die Einordnung **aus dem Bericht selbst** (Strommix).
   *(Phase 3)*
6. **BESCHLÜSSE ZUM PLAN:** nach Beziehung getrennt: *beschließt oder ändert
   den Plan* · *setzt Maßnahme X um* · *Antrag oder Anfrage dazu* · *erwähnt*.
   Erwähnungen bleiben hinter „Weitere“. *(gebaut ohne „setzt Maßnahme X
   um“; das kommt mit Phase 4)*

7. **VERWANDTE PLÄNE:** bis zu vier, ohne Grad und ohne Begründung. Gemeinsame
   Beschlüsse taugen dafür nicht (gemessen: nur sieben Paare teilen überhaupt
   einen, fast alle Vorgänger und Nachfolger). Vorgeschlagen wird über die
   Nähe der Kernpunkte im selben Themenfeld (Einbettung, offline, ohne
   Sprachmodell: `scripts/plan_verwandt.py`); **jedes Paar ist von Hand
   angenommen oder verworfen** (38 Vorschläge, 17 verworfen, mit Grund im
   Skript), dazu kommt, was das Register selbst nennt (Schulverpflegung ↔
   Ernährungsstrategie). Vorgänger und Nachfolger stehen nicht hier, sondern
   im Kopf. *(gebaut)*

8. **KARTE** (ab drei Orten): wo der Plan etwas vorsieht oder Beschlüsse
   zu ihm etwas festgelegt haben — beides ohne Sprachmodell und ohne neues
   Geocoding. (a) Straßen und Plätze, die ein Maßnahmentitel beim Namen nennt
   („Neue Fahrradstraße Lindenallee“), abgeglichen mit dem Ortskatalog der
   Ratsdaten und von Hand durchgesehen (`scripts/plan_orte.py`,
   `council/plan_places/`; Mobilitätsplan 11 von 33, smv2025 50 von 112,
   Ernährungsstrategie 2), als Linie mit Verlauf. (b) Orte, die die
   Ortszuordnung den Umsetzungs- und Berichtsbeschlüssen schon gegeben hat,
   als Punkt — keine Stadtteile, keine Gattungswörter, nur sichere Zuordnung;
   ein Beschluss „an der Dedestraße“ meint nicht die ganze Straße. Die Karte
   ist neutral gefärbt: Sie sagt, wo, nicht wie weit (§ 3.4). Die
   Spielleitplanung bleibt ohne Karte, der Masterplan Stadtgrün hat nur drei
   Orte aus einem Beschluss: Ihre Beschlüsse tragen kaum Orte, und Neues zu
   verorten hätte ein Geocoding gebraucht. *(gebaut)*
9. **IM HAUSHALT** (nur mit dem Recht `budget`, eigener Endpunkt
   `GET /api/council/budget/plan/{key}`): Haushaltsposten, deren eigener Text
   den Plan beim Namen nennt — ein Produkt, das ihn als Rechtsgrundlage
   führt, eine Investition, deren Bezeichnung ihn nennt, eine Änderung, die
   sich auf ihn beruft (`scripts/plan_haushalt.py`, `council/plan_budget.json`;
   37 Verweise für 8 Pläne). Beträge so, wie sie in der Zeile stehen; von zwei
   Stufen einer Änderung zählt die spätere. Kein Gesamtbetrag: Was ein Plan
   kostet, steht so nirgends im Haushalt. *(gebaut)*

**Mein Viertel:** Die Tafel eines Ortsbereichs nennt die laufenden und
entstehenden Pläne mit mindestens einem Ort dort (`district_plans`). Eine
Straße aus der Maßnahmenliste zählt überall, wo ein nennenswerter Teil von
ihr liegt (Anteil ab 0,3); eine Straße aus einem Beschluss nur in ihrem
Hauptbereich — sonst stünde ein Tagesaufenthalt „an der Alexanderstraße“ in
fünf Stadtteilen.

**Zu 4a, 4b und 1d: gemessen am 10.11.2026.** 73 Berichte mit Vorlagentext in
26 Plänen; 69 bekamen einen belegten Satz, 4 keinen. Von Hand gegen das Zitat
gelesen: alle 69 — 62 unverändert, 3 schief und berichtigt („frühestens“ statt
„voraussichtlich“; ein Anstieg weggelassen; „sollen“ statt „würden“), 2 zu vage
und durch eine bessere Stelle ersetzt, 2 sprachlich geglättet. „Neu“: 17
Vorschläge in 6 Reihen, 3 fielen als Wiederholung des Berichtssatzes, 2
umformuliert, bleiben 14. Einfache Sprache: 108 Sätze gegen die Kernpunkte
gelesen, 6 umgeschrieben (ein Präsens für etwas Künftiges, ein „obwohl“, das
die Kernpunkte nicht hergeben, ein weggelassener Geltungsbereich, drei
Unklarheiten). Fragen: Der erste Satz fragte je Plan pauschal nach Kosten —
verworfen und an die Kernpunkte gebunden neu erzeugt; 10 von 108 von Hand
geglättet. Modellkosten zusammen 0,23 $ (Luna), samt Messläufen und
Wiederholungen; ein neuer Bericht kostet rund 0,001 $.

**Zu 1a: Wie die Kernpunkte entstehen.** Ein Sprachmodell (Luna) liest je
Plan die Beschlüsse aus dem Register mit Beschlusstext und Vorlage und das
Plandokument selbst (von Hand ausgewählt, `DOCUMENTS` in
`scripts/plan_kernpunkte.py`) und schlägt Sätze mit Belegstellen vor. In die
Datei (`council/plan_key_points/<plan>.json`, eingecheckt) kommt nur, was
`council/plan_judge.py` **ohne Modell** belegen kann: Das Zitat steht wörtlich
in der genannten Quelle (bei Anlagen auf der genannten Seite), jede Zahl des
Satzes steht im Zitat, kein Zitat belegt zwei Sätze. Eine zweite Lesung des
Modells kann nur streichen („trägt das Zitat den Satz?“). Gegen den Bestand
halten das `scripts/pruefe_plaene.py` (Beschlusstexte, Vorlagen) und
`scripts/plan_kernpunkte.py --pruefen` (dazu die PDF-Dateien, mit Seite).

Gemessen am 10.11.2026: 36 Pläne mit Datei, 227 Sätze. Von Hand gegen das
Umfeld des Zitats gelesen: 12 Pläne mit 76 Sätzen des Modells — 73 richtig,
1 schief (verallgemeinert: „ab 3 Zügen“ statt „bei 3 und 4 Zügen“), 2
unklar (Straßenlisten ohne den Zusammenhang „Tempo 30“); alle drei
korrigiert. Die übrigen 24 Dateien Satz gegen Zitat gelesen; dabei fielen
vier weitere Sätze (Zustandsbeschreibung statt Vorgabe, eine ältere
Dienstvereinbarung statt einer Vorgabe des Plans, eine Tabellenzeile mit
unsicherer Spaltenfolge), drei wurden umformuliert. **Neun Pläne bleiben ohne Block**, jeder mit Grund
in `WITHOUT_BLOCK`: vier ohne Plantext im Bestand (KAI 2015,
Sportentwicklungsplan 2009, step2025, Klimaanpassungskonzept), vier zu dünn
belegt (Abfallwirtschaftskonzept: Scans ohne Text; Nahverkehrsplan,
Kitaverpflegung, Innenstadtstrategie: nur eine knappe Vorlage), einer
bewusst (Luftreinhalteplan: die Sätze wären belegt, täuschten aber einen
geltenden Plan vor). Auf die Karte der Übersicht passt der Zweck-Satz
nicht: Er bricht dort nach zwei Zeilen mitten im Gedanken ab und macht die
Liste rund 40 % länger — weggelassen.

### 3.3 Rückblick bei abgelaufenen Plänen

Ein fester Aufbau, kein freier Text:

- **Was vorgesehen war:** Zahl der Maßnahmen, Laufzeit, Kennzahl.
- **Was die Verwaltung meldet:** die Verteilung aus der Evaluation, mit Datum
  und Seite.
- **Kennzahl Soll und Ist**, falls vorhanden.
- **Grenzen, die der Bericht selbst nennt**, z. B. Kap. 2.4 der Evaluation
  zum Aktionsplan Gewalt („Fehlende finanzielle und personelle Ressourcen“).
- **Was weitergeführt wird:** Nachfolger und übernommene Maßnahmen.
- Gibt es keine Evaluation, steht dort genau das: „Eine Auswertung liegt im
  Ratsinformationssystem nicht vor.“

### 3.3a Die Einordnung je Plan

Tims Entscheidung (09.11.2026) gilt: Ratslotse ordnet jeden Plan ein — fair,
ohne die Stadt abzustrafen. Begründung: Die Stadt hat die Aufgabe, über den
Stand ihrer Pläne zu berichten; eine Einordnung macht diesen Bericht lesbar
und zeigt, wo er fehlt. Sie gilt für laufende Pläne (als Zwischenstand) und
für den Rückblick. **Gemessen wird am Plan selbst, nicht an uns:** Maßstab
sind die eigenen Maßnahmen, Termine und Zielwerte des Plans.

**Geändert hat sich das Wie.** Die erste Fassung sah fünf Stufen nach
einer Drittel-Regel vor: „Weitgehend umgesetzt“ ab zwei Dritteln der
Maßnahmen, „Auf dem Weg“ zwischen einem und zwei Dritteln, „Hinter dem eigenen
Zeitplan“ unter einem Drittel nach mehr als der halben Laufzeit, dazu „Neu
ausgerichtet“ und „Stand unbekannt“. Sie sollte „an den fünf Pilotplänen
geeicht“ werden. Das ist geschehen, und sie trägt nicht:

- **Klimaschutzplan:** 20 von 97 Maßnahmen sind „Realisiert“, das sind 21 %;
  von 13 Jahren Laufzeit sind 4 vorbei. Für „Hinter dem eigenen Zeitplan“
  fehlt die halbe Laufzeit, für „Auf dem Weg“ das Drittel — **es passt keine
  Stufe.** Zählt man „In Umsetzung“ mit, sind es 54 von 97 und damit „Auf dem
  Weg“. Welche Stufe herauskommt, hängt also daran, welche Wörter der Stadt
  wir als „umgesetzt“ gelten lassen. Genau diese Entscheidung wollten wir
  nicht treffen.
- **Der Nenner wandert.** 90 → 97 Maßnahmen, „Realisiert“ 22 → 20 (§ 1.3).
  Eine Stufe, die daraus rechnet, kann von einem Bericht zum nächsten kippen,
  ohne dass sich an der Arbeit etwas geändert hat.
- **Ernährungsstrategie:** 68 Handlungsansätze, von denen der Rat 5 zur
  Umsetzung beschlossen hat. Ist der Nenner 68 oder 5? Und die Stufen je
  Ansatz nennt die Stadt selbst eine „qualitative Einschätzung“.
- **Wärmeplan:** fünf Monate alt. **Mobilitätsplan:** Die Stadt zählt den
  Stand gar nicht aus.
- **In der Summe** ließe sich die Regel für vier oder fünf der 43 Pläne
  rechnen. Alle übrigen hießen „Stand unbekannt“ oder fielen durch — auch
  solche, über die regelmäßig berichtet wird.

**Deshalb drei Bausteine statt einer Stufe** (Tims Entscheidung 09.11.2026).
Jeder beantwortet eine Frage,
die sich aus dem Bestand beantworten lässt, und keiner verlangt, dass wir die
Wörter der Stadt in „umgesetzt“ und „nicht umgesetzt“ sortieren.

**1. Berichtsstand — für jeden Plan.** *Wird über diesen Plan berichtet?* Eine
Regel im Code, ohne Modell, unter jeder Einordnung als „So ordnen wir ein“
verlinkt. Die Reihenfolge ist die Regel; der erste Treffer gilt:

| # | Berichtsstand | Regel | heute |
|---:|---|---|---:|
| 1 | **Fortgeschrieben** (`continued`) | Das Register nennt einen Nachfolger. | 8 |
| 2 | **In Arbeit** (`in_preparation`) | Es gibt noch keinen Beschluss. | 2 |
| 3 | **Ausgewertet** (`evaluated`) | Die Laufzeit ist vorbei, und eine Auswertung liegt vor. | 1 |
| 4 | **Laufzeit abgelaufen, keine Auswertung gefunden** (`expired_no_evaluation`) | Die Laufzeit ist vorbei, ohne Nachfolger und ohne Auswertung. | 1 |
| 5 | **Berichtet** (`reported`) | Der jüngste Bericht ist höchstens zwei Jahre alt. | 14 |
| 6 | **Noch kein Bericht fällig** (`not_yet_due`) | Es gab noch keinen Bericht, aber die Frist läuft noch: die eigene Überprüfungsfrist des Plans, sonst zwei Jahre ab Beschluss. | 7 |
| 7 | **Kein Bericht gefunden** (`no_report_found`) | Alles Übrige: seit über zwei Jahren kein Bericht, oder nie einer und die Frist ist vorbei. | 10 |

Gerechnet gegen das Register am 09.11.2026 (zusammen 43):

- *Berichtet:* Klimaschutzplan, Mobilitätsplan, Ernährungsstrategie,
  Lärmaktionsplan, Digitalisierungsstrategie, Kita-Ausbau, ISEK,
  Baumstrategie, Nachhaltigkeitsleitbild, Wohnungslosen- und Suchthilfe, Orte
  für Alle, Schulverpflegung, Kitaverpflegung, Innenstadtstrategie.
- *Noch kein Bericht fällig:* Wärmeplan, Aktionsplan Gewalt 2026, Agenda 2025,
  Kinder- und Jugendbeteiligung, treibhausgasneutrale Verwaltung,
  Spielleitplanung, Brandschutzbedarfsplan.
- *Kein Bericht gefunden:* Masterplan Stadtgrün, Demografiestrategie,
  Gleichstellungsplan 2024–2026, Abfallwirtschaftskonzept, Luftreinhalteplan,
  Wohnraumversorgungskonzept, Rad- und Fußverkehrsprogramm,
  Gewerbeflächenkonzept, Bäderstrategie, Sportentwicklungsplan 2009.
- *Fortgeschrieben:* Aktionsplan Gewalt 2020, Integrationskonzept 2020, die
  Gleichstellungspläne 2018 und 2021, step2025, smv2025, Aktionsplan Energie,
  KAI 2015.
- *In Arbeit:* Integrationskonzept 2026, Klimaanpassungskonzept.
  *Ausgewertet:* Schulentwicklungsplan 2018. *Laufzeit abgelaufen, keine
  Auswertung gefunden:* „Oldenburg – eine Stadt für alle“.

Nach der Gegenprobe im Review (09.11.2026) trägt der Gleichstellungsplan
2024–2026 seine eigene Frist im Register: Er sieht keinen Zwischenbericht vor
und wird im Folgeplan ausgewertet. Damit stehen heute 8 Pläne unter „Noch
kein Bericht fällig“ und 9 unter „Kein Bericht gefunden“; die Tabelle oben
zeigt den Stand der ersten Rechnung.

Zwei Folgen der Regel, die man kennen muss:

- **Die eigene Frist des Plans schlägt unsere zwei Jahre.** Der Wärmeplan
  heißt „Noch kein Bericht fällig“ bis 06/2031, weil § 25 WPG die Überprüfung
  erst dann verlangt. Berichtet die Stadt früher, heißt er ab dann
  „Berichtet“. Das ist gewollt: gemessen am Plan selbst.
- **„Kein Bericht gefunden“ braucht vor der Anzeige eine Gegenprobe.** Die
  zehn Pläne dieser Gruppe prüft Phase 3 gegen ihren Plantext. Wo der Plan
  selbst nur eine Auswertung am Ende vorsieht (der Gleichstellungsplan wird
  im Folgeplan evaluiert), bekommt er diese Frist ins Register und wandert zu
  „Noch kein Bericht fällig“. Der Satz darunter bleibt in jedem Fall: „Ob
  umgesetzt wurde, wissen wir nicht — berichtet wurde im Rat nicht.“

**2. Stand laut Stadt — nur wo die Stadt einen meldet.** *Was sagt die Stadt
über den Stand?* Die Verteilung in ihren Worten mit Datum und Beleg, dazu:

- **die Bewegung** seit dem vorigen Bericht („In Umsetzung 25 → 34,
  Realisiert 22 → 20, sieben Maßnahmen neu“) — ein Plan, der aufholt, steht
  nicht wie einer, der stillsteht;
- **die Gründe, die die Stadt selbst nennt** (Personal, Geld, Fördermittel,
  Prioritäten, Bundesrecht), wörtlich und mit Seite;
- **ihre eigenen Vorbehalte** (Daueraufgaben, „qualitative Einschätzung“).

Heute haben das Klimaschutzplan, Aktionsplan Gewalt 2020, Ernährungsstrategie,
Wärmeplan und KAI (Stand 2020). Für alle anderen bleibt der Baustein weg —
ohne Platzhalter.

**3. Eigene Termine des Plans.** *Was hat sich der Plan selbst vorgenommen?*
Laufzeit, Überprüfungsfrist und Fristen einzelner Maßnahmen als Tatsachen
nebeneinander: „Laufzeit bis 2035 · 4 von 13 Jahren vorbei · Fortschreibung
laut Plan 2027“. Das ersetzt „Hinter dem eigenen Zeitplan“: Wer Termin und
Stand nebeneinander sieht, zieht den Schluss selbst, und wir müssen keinen
errechnen, den die Daten nicht tragen. Eine Maßnahme mit verstrichener Frist
erscheint unter den offenen Aufträgen (§ 3.5, Art 1).

**Was aus der ersten Fassung bleibt:**

- **Daneben steht immer die Stadt selbst** — ihre Einschätzung im Wortlaut,
  ihre Gründe.
- **Neu ausrichten ist kein Makel.** Gestrichene oder ersetzte Maßnahmen
  erscheinen unter „Was anders gedacht wurde“, mit der Begründung der Stadt;
  ein fortgeschriebener Plan heißt „Fortgeschrieben“ und nicht „beendet“.
- **Ein fehlender Bericht ist eine Aussage über den Bericht, nicht über die
  Arbeit.**
- **Keine Rangliste der Pläne, keine Ampel in Rot.** Die Berichtsstände tragen
  neutrale Tints.
- **Ein Modell formuliert höchstens eine Zusammenfassung**, und zwar
  zitierend. Was eingeordnet wird, rechnet die Regel — reproduzierbar und
  angreifbar, wo sie falsch ist.

Phase 3 baut alle drei Bausteine. „Stand unbekannt“ der ersten Fassung steckt
im Berichtsstand (Zeilen 5 bis 7); ein bewertendes Wort je Plan gibt es nicht.

### 3.4 Neutralität und Scheinpräzision: die Regeln

1. **Keine Gesamtnote über alle Pläne und keine Quote über Pläne hinweg.**
   Die Einordnung gilt je Plan, nach § 3.3a. Die Prozent-Stufen der
   Ernährungsstrategie sind laut Stadt eine „qualitative Einschätzung“.
   Wir zeigen sie als Stufen und mitteln sie nie.
2. **Jede Zahl trägt Datum und Beleg.** Ändert sich die Zählbasis, steht das
   dabei.
3. **Selbstauskunft kennzeichnen.** Der Kicker heißt „NACH ANGABEN DER
   VERWALTUNG“, wenn der Stand aus einem Verwaltungsbericht stammt, und
   „KLIMAPORTAL DER STADT, STAND …“, wenn er von dort kommt.
4. **Wirkung nicht dem Plan zuschreiben.** Eine Kennzahl steht neben dem
   Plan, nicht als sein Ergebnis.
5. **Nicht Umgesetztes ist kein Fehlerrot.** „Zurückgestellt“ und
   „eingestellt“ bekommen den neutralen Tint. Grün steht nur für das, was die
   Stadt selbst „umgesetzt“ oder „realisiert“ nennt.
6. **Keine Parteiwertung.** Es gibt kein „wer bremst“. Anträge erscheinen
   wie überall mit ihren Antragstellern.
7. **„Zur Kenntnis genommen“ ist nicht „beschlossen“.** Das gilt für den
   Schulentwicklungsplan 2018, die Integrationskonzept-Fortschreibung 2020,
   die Demografiestrategie und den Gleichstellungsplan.

### 3.5 Offene Aufträge: wo man nachfragen kann

Tims Wunsch (09.11.2026): sehen, wo Beschlossenes auf Umsetzung wartet, wo
nichts mehr nachkam und wo man nachfragen kann — auch als Werkzeug für
Ratsmitglieder. Drei Arten, alle aus dem Bestand ableitbar:

1. **Maßnahme mit verstrichenem Termin.** Der Plan nennt für eine Maßnahme
   einen Zeitraum („bis 2025“), und der jüngste Bericht meldet sie nicht als
   umgesetzt. Anzeige: „Laut Plan bis 2025 · letzter gemeldeter Stand
   ‚in Umsetzung‘ (Bericht vom 08.10.2026)“.
2. **Ratsauftrag ohne Folge.** Ein angenommener Beschluss beauftragt die
   Verwaltung, zu prüfen, zu berichten oder etwas vorzulegen („Die
   Verwaltung wird beauftragt …“), und danach findet sich keine Station mehr:
   keine Vorlage derselben Akte, kein Bericht, kein Tagesordnungspunkt in der
   Beratungsfolge, keine Zusage der Verwaltung dazu. Anzeige: „Auftrag vom
   16.04.2025 · seither keine Vorlage und kein Bericht im Rat gefunden“.
   Dazu gehören auch **Zusagen der Verwaltung** aus den Protokollen mit Datum
   („bis zum Sommer“), deren Datum verstrichen ist.
3. **Plan ohne Bericht oder mit fälliger Fortschreibung.** „Seit dem
   Beschluss 2021 kein Umsetzungsbericht im Rat“, „Fortschreibung laut Plan
   2026 fällig“.

**Die drei Arten sind verschieden weit und verschieden riskant.** Deshalb
kommen sie nicht in einer Phase:

| Art | Woher | Menge heute | Risiko eines falschen Treffers | Kommt mit |
|---|---|---|---|---|
| 3 Plan ohne Bericht | fällt aus dem Berichtsstand (§ 3.3a), ohne Modell | 11 Pläne (Zeilen 4 und 7); fällige Fortschreibungen: Gleichstellungsplan Ende 2026, Abfallwirtschaftskonzept 2027; von den fünf Überprüfungsfristen im Register ist noch keine verstrichen | klein — das Register ist Handarbeit und im PR sichtbar | Phase 3 |
| 1 Maßnahme mit verstrichenem Termin | Feld `due` in der Maßnahmendatei, wo der Plan einen Termin nennt, plus Stand aus Phase 3 | noch nicht gezählt; die fünf Listen tragen heute keinen Termin | mittel — hängt an der Güte des Stands je Maßnahme | Phase 4b, erster Teil |
| 2 Ratsauftrag ohne Folge | Beschlusstexte und Zusagen | 341 angenommene Beschlüsse mit „wird beauftragt / gebeten / aufgefordert“ im Beschlusstext; 1.447 Zusagen der Verwaltung in den Wortbeiträgen (`kind = pledge`) | **groß** — die Gegenprobe muss beweisen, dass es *keine* Folge gab, und ein Fehler behauptet, die Stadt sei säumig | Phase 4b, zweiter Teil |

Für Art 2 schlagen wir einen **eigenen Schalter** vor (`offene-auftraege`):
Dann kann „Pläne“ auf Prod angehen, ohne dass die riskanteste Liste mitfährt,
und sie kann dort einzeln wieder aus (§ 8, Frage B).

**Regeln, damit das fair bleibt** — ein falscher Treffer behauptet, die Stadt
sei säumig, wo der Bericht in Wahrheit existiert:

- **Nie „zu langsam“, nie eine Wertung.** Angezeigt wird die Tatsache mit
  Datum („seit 19 Monaten keine Station gefunden“), nicht ihre Deutung.
- **„Nicht gefunden“ statt „gibt es nicht“.** Ein fester Satz unter jeder
  Liste: Nichtöffentliche Sitzungen, Mitteilungen ohne Vorlage und Berichte
  außerhalb des Ratsinformationssystems sieht Ratslotse nicht.
- **Lieber zu wenig als zu viel.** Ein Auftrag erscheint nur, wenn die
  Gegenprobe (Akte, Beratungsfolge, Titelähnlichkeit, Volltext, Zusagen)
  nichts findet und mindestens sechs Monate vergangen sind. Die Präzision
  wird an einem Golden-Set gemessen (Phase 4b), nicht angenommen.
- **Keine Parteibrille.** Wer den Auftrag beantragt hat, steht wie überall
  dabei; sortiert wird nach Alter des Auftrags, nicht nach Fraktion.
- **Nachfragen leicht machen:** Jede Zeile führt zu „Frag den Rat“ mit
  vorbereiteter Frage („Was ist aus dem Auftrag vom … geworden?“) und zur
  Vorlage. Für Konten mit dem Recht `mandate` (Ratsmitglieder) später
  optional ein Entwurf für eine Anfrage — erst nach einem eigenen Beschluss
  von Tim.

Ort: ein eigener Block „Offene Aufträge“ auf jeder Planseite und eine
stadtweite Liste in der Übersicht (filterbar nach Themenfeld und Gremium).

## 4. Architektur

Gebaut ist, was unter „Steht“ aufgeführt ist; „Kommt“ ist der Entwurf für die
Phasen 3 bis 4b.

### Steht (Phasen 0 bis 2)

- **Register als Code:** `council/plans.py`, ein Wörterbuch `PLANS` mit 45
  Einträgen der Datenklasse `Plan`: `key`, `title`, `kind` (`action` |
  `framework` | `statutory` | `reference`), `policy_field`, `office`,
  `adopted` (eine `Decision` mit Datum, Vorlage, Gremium und `mode`:
  `adopted` | `noted`), weitere `decisions`, `start`, `end`, `review_due`,
  `predecessor` und `successor`, `concluded`, die Titelmuster
  `report_patterns` / `exclude_patterns` / `implementation_patterns`,
  `source` (`council` | `website`) und `note` (Auswahl). Datumsangaben dürfen ein Jahr
  oder Jahr und Monat sein. Der Grund für Code statt Datenbank: Das Register
  ist Handarbeit, und jede Änderung soll im PR sichtbar sein (wie bei den
  Prompts).
- **Maßnahmen als geprüfte Dateien:** `council/plan_measures/<key>.json` mit
  Quelle (Anlage, Adresse, Vorlage, Stichtag), der Zahl der Stadt
  (`count_city`) samt Anmerkung zur Zählbasis und je Maßnahme Kennung, Titel,
  Handlungsfeld und Seite. Geschrieben von `scripts/plan_massnahmen.py`
  (Parser, Quellen im Zwischenspeicher `~/.cache/ratslotse/plan-quellen/`),
  im PR festgehalten; `--pruefen` vergleicht Datei und Quelle neu.
- **Abgeleitete Tabellen** in `council.sqlite`, bei jedem Lauf neu gebaut
  (`council/plan_tracking.py`), Schema **und** `_migrate()` nach
  `council/CLAUDE.md`:
  - `council_plan_items` — jeder Tagesordnungspunkt an einem Plan, mit `role`
    (`adoption`, `amendment`, `preparation`, `report`, `evaluation`,
    `implementation`, `motion`, `decision`), `oral`, Gremium, Datum und
    Ergebnis. Eine eigene Berichtstabelle gibt es nicht: Berichte sind die
    Rollen `report` und `evaluation`.
  - `council_plan_links(plan_key, decision_id, measure_code, relation,
    method, confidence)` — heute nur `mentions` über die Nummer.
- **Wann gebaut wird:** auf Prod nachts im Protokoll-Cron (Schritt „Pläne“
  in `scripts/check_protocols.py`, nach „Ziele“); auf dev, wo keine Crons
  laufen, bei jedem Deploy (`scripts/build_plans.py` in `deploy-dev.yml`);
  lokal mit `scripts/lokale_daten.py setz`. Der Lauf braucht kein Netz und
  kein Modell.
- **Logik im Backend:** `council/plan_pages.py` baut Gruppe, Sortierung,
  Kicker, „letzter Bericht“, den Satz, wenn der Bestand schweigt, und den
  Maßnahmenblock; `council/store_plaene.py` liest. Das Frontend zeichnet nur.
- **Endpunkte:** `GET /council/plans` und `GET /council/plan/{key}`, mit
  Antwortformen in `antworten.py` und geschnittenem Vertrag. Die alten
  Endpunkte `/council/goals` und `/council/goal/{key}` **bleiben**, bis
  `APP_MIN_BUILD` auf einem App-Build steht, der die neue Ansicht kennt
  (Prüfung: `scripts/ios_vertrag.py --ausgeliefert`).
- **Schalter** `plaene` in `kern/features.py`, mit `fertig_wenn`. Die
  Changelog-Fragmente tragen `schalter: plaene`.
- **Wächter:** `tests/test_plaene_register.py` (Format jeder Vorlagennummer,
  Vorgänger und Nachfolger zeigen auf vorhandene Schlüssel — läuft in der CI
  gegen die leere Datenbank), `tests/test_plaene_zuordnung.py`,
  `tests/test_plaene_massnahmen.py`. Gegen echte Daten prüft
  `scripts/pruefe_plaene.py`: Jede Vorlage existiert, jeder Beschluss liegt an
  dem genannten Tag im genannten Gremium, „beschlossen“ und „zur Kenntnis“
  stimmen, jede Berichtsreihe hat mindestens einen Treffer. Eine
  überschrittene Laufzeit ohne Nachfolger ist ein Hinweis und kein Fehler.

### Kommt (Phasen 3 bis 4b)

- **Der Stand wird eine geprüfte Datei, keine Tabelle aus dem Cron:**
  `council/plan_status/<key>.json` mit einer Liste von Momentaufnahmen. Jede
  trägt `as_of`, die Quelle (`kind`: `template` | `attachment` |
  `klimaportal`, dazu Vorlage oder Adresse und Abrufdatum), die Verteilung
  (`status_raw`, `status_norm`, `count`), die Summe und — wo vorhanden — den
  Stand je Maßnahme. Drei Gründe:
  1. Auf dev laufen keine Crons, und `build_plans.py` läuft dort bei jedem
     Deploy. Ein Abruf beim Klimaportal gehört nicht in einen Deploy.
  2. Nur zwei der 15 Berichte tragen den Zählblock; was automatisch
     nachwüchse, wäre wenig. Farben, Bilder und Fließtext brauchen ohnehin
     einen geprüften Lauf.
  3. Dasselbe Muster wie bei den Maßnahmen: Skript schreibt, PR hält fest,
     `--pruefen` vergleicht.

  Damit ein neuer Bericht nicht unbemerkt bleibt, meldet
  `scripts/pruefe_plaene.py`, wenn der jüngste Bericht einer Reihe neuer ist
  als die jüngste Momentaufnahme. Eine abgeleitete Tabelle
  `council_plan_status` entsteht erst, wenn eine Abfrage sie braucht.
- **`status_norm`** hat fünf Stufen plus „unklar“ (`open`, `started`,
  `in_progress`, `done`, `paused`, `unclear`). Es dient nur zum Gruppieren und
  für den Tint; angezeigt wird immer `status_raw`.
- **Berichtsstand** (`report_state`, § 3.3a) als Feld neben dem vorhandenen
  `status` der Karte, gerechnet in `council/plan_pages.py`.
- **Kennzahlen** als kuratierte Datei `council/plan_indicators/<key>.json`:
  Jahr, Wert, Einheit, Soll oder Ist, Quelle.
- **Termine von Maßnahmen:** optionales Feld `due` in der Maßnahmendatei.
- **Offene Aufträge:** Tabelle `council_open_mandates` und
  `GET /council/open-mandates` (Phase 4b), hinter eigenem Schalter, falls Tim
  Frage B bejaht.

## 5. Phasen

Reihenfolge: 3 → 4 → 4b → 5 → 5b → 6. Jede Phase ist ein eigener PR gegen
`dev`; jeder PR, der die Oberfläche ändert, geht erst nach Bild und Tims OK
hinein.

### Phase 0: Register und Entscheidungen — erledigt (#1812)

- `council/plans.py` mit 45 Plänen (geplant waren „rund 25“; dazu kamen die
  Vorgänger, die Pläne in Arbeit und alle belegten Fälle aus E), ohne
  Maßnahmen.
- Zwei Wächter: Register-Test in der CI, `scripts/pruefe_plaene.py` gegen
  echte Daten.
- **Kosten:** 0 $.

### Phase 1: Berichte und Planbeschlüsse zuordnen; erste Seite — PR offen (#1813)

- `council_plan_items` aus Planvorlagen, Titelmustern und
  Tagesordnungspunkten, mündliche Berichte eingeschlossen;
  `council_plan_links` über die Vorlagennummer.
- Endpunkte, Übersicht und Detailseite (Kopf, Laufzeit, Berichte,
  Beschlüsse), alles hinter `plaene`.
- **Messziel erreicht:** Aktionsplan Gewalt 2020 mit allen 24
  Tagesordnungspunkten; Klimaschutzplan mit allen 15 Vorlagen der Reihe.
- **Kosten:** 0 $. **Offen:** Tims Bild-OK.

### Phase 2: Maßnahmenlisten für fünf Pilotpläne — fertig, PR folgt

| Plan | Maßnahmen | Zahl der Stadt | Anmerkung |
|---|---:|---:|---|
| Klimaschutzplan 2035 | 90 | 90 | so beschlossen am 19.12.2022; laut `26/0750` inzwischen 97 |
| Wärmeplan | 18 | 18 | Tabelle 7 des Abschlussberichts |
| Ernährungsstrategie | 68 | 68 | fünf davon hat der Rat zur Umsetzung beschlossen (`24/0811`) |
| Aktionsplan Gewalt 2026 | 30 | 30 | sechs Fokusthemen mit je fünf Handlungsempfehlungen |
| Mobilitätsplan 2030 | 33 | — | die Anlage nennt diese namentlich; priorisiert wurden laut Anlage „ca. 70“ von über 250 |

- Alle fünf per Parser, **kein Modell, 0 $** (geschätzt war rund 1 $).
- Der Block MASSNAHMEN auf der Detailseite und die Zahl auf der Karte.
- **Verschoben nach Phase 3:** die Liste des Aktionsplans Gewalt 2020 (87).
  Sie steht nur in Anhang 4.1 der Evaluation, und dort hängt der Stand als
  Zellfarbe an jeder Zeile — Liste und Stand werden in einem Zug gelesen.
- **Vor dem PR:** auf den Stand von #1813 bringen (die generierten Typen neu
  schneiden) und einen Befund der Typprüfung in `scripts/plan_massnahmen.py`
  beheben.

### Phase 3: Stand als Zeitreihe, Berichtsstand, Kennzahlen

Was sich ohne Modell lesen lässt, zuerst:

- **Berichtsstand** nach § 3.3a für alle 43 Pläne, als Feld im Backend. Dazu
  die Gegenprobe der zehn Pläne „Kein Bericht gefunden“ gegen ihren Plantext
  und, wo nötig, `review_due` im Register. Daraus fällt Art 3 der offenen
  Aufträge ab (§ 3.5).
- **Klimaschutzplan:** die Reihe 2022 bis 2026 aus dem Klimaportal — ohne den
  Stand je Maßnahme, s. § 1.3 (`scripts/plan_status.py`, eigener User-Agent, mindestens
  zwei Sekunden Abstand, Abzug im Zwischenspeicher). Gegenprobe: Die Spalten
  2025 und 2026 müssen den Zählblöcken in `26/0074` und `26/0750`
  entsprechen. Sperrt das Portal den Abruf, fragen wir Tim — es gibt keinen
  Umweg auf eigene Faust.
- **Wärmeplan:** aus `26/0236`, Parser: sechs von 18 Maßnahmen „in
  Umsetzung“, gegen das Zahlwort der Vorlage geprüft.
- **Aktionsplan Gewalt 2020:** Liste und Zellfarben aus Anhang 4.1 der
  Evaluation mit PyMuPDF — gebaut. Die Verteilung zählt der Text der
  Evaluation (56 umgesetzt, 3 in Umsetzung, 14 nicht umgesetzt und weiter
  gebraucht, 9 nicht weiterverfolgt; der Rest von 8 steht nur in der Tabelle),
  den Stand je Empfehlung trägt die Zellfarbe. Das Skript prüft beides
  gegeneinander. Zwei Abweichungen von der ersten Fassung dieses Plans: Die
  Evaluation zählt 90 Empfehlungen, nicht 87, und ihre Tabelle hat 91 Zeilen
  (bei „nicht weiterverfolgt“ Text 9, Tabelle 10). Beides steht auf der Seite
  als Hinweis.
- **Kennzahl (gebaut):** THG-Bilanz als `council/plan_indicators/klimaschutzplan_2035.json`
  aus `23/0653`, `25/0131` und `25/0866`, getrennt nach Soll und Ist, mit dem
  Hinweis des Berichts auf den Strommix.
- **Stand laut Stadt:** Die Bewegung zwischen zwei Momentaufnahmen rechnet
  das Backend; Gründe und Vorbehalte der Stadt kommen als kurze Zitate mit
  Vorlage und Seite in die Statusdatei.
- **Eigene Termine:** Laufzeit, vergangener Anteil und Überprüfungsfrist aus
  dem Register, im Backend als Tatsachen formuliert.

Dann, jeweils erst nach einer Messung mit `limit=20`:

- **Ernährungsstrategie (gebaut, ohne Modell):** alle 68 Zeilen per Parser aus
  `26/0431`. Gegenprobe: jede Kennung der Maßnahmenliste genau einmal, die Zahl
  des Berichts (68) und je Handlungsfeld die Zählung der Kreisdiagramme (zwei
  von fünf von Hand verglichen).
- **Mobilitätsplan (gebaut, mit Modell):** Ein Sprachmodell sucht je Bericht
  (`23/0562`, `25/0041`, `26/0190`) heraus, was er über die 33 benannten
  Maßnahmen sagt — ein Aufruf je Bericht, jede Angabe mit wörtlichem Zitat.
  Was sich nicht belegen lässt, fällt ohne Modell weg (`council/plan_judge.py`);
  `scripts/plan_modell.py mobilitaet --pruefen` prüft die Datei später gegen
  den Bestand. Golden-Set von Hand aus `26/0190`: 16 Maßnahmen mit Stand, 16
  ohne Nennung — gemessen 0 falsch zugeordnet, 0 übersehen, 0 Stufen
  abweichend. **Kosten gemessen: 0,0038 $** für alle drei Berichte (Luna).
  Die Stadt zählt den Stand hier nicht aus, deshalb gibt es keine Verteilung;
  der Stand steht an der Maßnahme, mit Zitat.

- **Lieferbar:** die drei Bausteine der Einordnung (Berichtsstand, Stand laut
  Stadt mit Statuszeile auf den Karten und Statuschips mit Verlauf, eigene
  Termine) und der Block KENNZAHL. Bild vor dem Merge.
- **Messziel:** 100 % der Status aus Portal, Parser und Farben stimmen mit
  der Quelle überein (Stichprobe von 30). Beim Mobilitätsplan wird höchstens
  1 von 20 einer falschen Maßnahme zugeordnet.
- **Kosten (Schätzung):** Portal, Parser und Farben 0 $; fünf Bilder wenige
  Cent; Mobilitätsplan ≈ 0,10–0,30 $.

### Phase 4: Beschlüsse den Maßnahmen zuordnen

**Erster Teil gebaut, ohne Modell:** Eine Vorlage, die eine Maßnahme bei ihrer
Kennung nennt (`PV_05`, „Wärmeplan-Maßnahme O7“, „Handlungsansatz A12“),
ordnet ihre Beschlüsse dieser Maßnahme zu (`council_plan_links`, Beziehung
`names_measure`). Kurze Kennungen zählen nur, wenn die Vorlage den Plan nennt
und die Kennung als Maßnahme anspricht; Übersichten mit mehr als fünf
Kennungen und die Berichte des Plans selbst zählen nicht. Gemessen: 9
Vorlagen mit 21 Beschlüssen (8 zum Klimaschutzplan, 1 zum Wärmeplan), alle
neun von Hand gegen Titel und Maßnahme geprüft. Die Seite sagt „nennt eine
Maßnahme“, nicht „setzt um“ — das wäre ein Urteil.

**Zweiter Teil gebaut, mit Modell (10.11.2026):** die Vorlagen, die einen Plan
nur beim Namen nennen — neun Pläne mit eindeutigem Namen, 302 Paare aus Plan
und Vorlage. Ein Sprachmodell (Luna) urteilt je Paar *dient der Umsetzung* |
*Antrag oder Anfrage* | *erwähnt* | *etwas anderes gemeint*; im Zweifel
„erwähnt“. Gezeigt wird nur *dient der Umsetzung*, und nur mit einem Beleg,
der ohne Modell prüfbar ist: Das Zitat steht wörtlich in der Vorlage und nennt
den Plan beim Namen (`plan_judge.checked_relation`).

- **Golden-Set** (`eval/cases_plan_links.json`): 40 Paare, von Hand bewertet,
  geschichtet gezogen, darunter sechs EEK-Nennungen in Bebauungsplänen als
  Fallen und ein falscher Freund (ein anderes „ISEK“). Gemessen in zwei
  Läufen: 39 von 40 Urteilen vertretbar, „dient der Umsetzung“ 3 von 3 richtig,
  keine Erwähnung in der Umsetzungsliste. Die eine Abweichung ist eine
  übersehene Umsetzung — die vorsichtige Richtung.
- **Alle Treffer von Hand durchgesehen:** 27 im vollen Lauf, davon 25 richtig.
  Die zwei falschen waren ein Sachstandsbericht und eine Anfrage; beide Arten
  werden seitdem gar nicht mehr gefragt (Berichte irgendeines Plans, Anträge
  und Anfragen nach Titel). Eingecheckt sind die 25 geprüften
  (`council/plan_links/`, acht Pläne).
- **Kosten gemessen:** 0,0031 $ für die 40 Paare, 0,025 $ für alle 302;
  mit Wiederholungen beim Schärfen der Regel zusammen rund 0,09 $.
- Das Modell antwortet von Lauf zu Lauf nicht völlig gleich (27 Treffer, aber
  nicht dieselben). Deshalb gilt die eingecheckte Datei, nicht der Lauf; wer
  neu laufen lässt, sieht den Unterschied im PR und prüft ihn.

- Kandidaten kommen über den Plannamen, die Kennungen aus den
  Maßnahmendateien, die Akte (Vorlagen einer Akte mit Planbezug) und die
  vorhandenen Embeddings. Das Modell urteilt über die Beziehung (*setzt
  Maßnahme um* | *ändert Plan* | *Antrag dazu* | *erwähnt* | *kein Bezug*)
  und die Maßnahme. Im Zweifel lautet das Urteil „erwähnt“.
- Vorab ein Golden-Set aus 40 von Hand bewerteten Paaren, die meisten aus
  Klima und Mobilität, darunter EEK-Erwähnungen in Bebauungsplänen als
  Fallen.
- **Der Stempel bleibt im Cron.** Nach Tims Entscheidung 4 läuft
  `track_goals` weiter, bis „Pläne“ auf Prod steht. Phase 4 liefert den
  Ersatz und misst die Kosten des Features `goal_rating`, damit die Ersparnis
  belegt ist; der Ausbau ist ein eigener kleiner PR zur Freigabe.
- **Lieferbar:** der Teil „setzt Maßnahme X um“ im Block BESCHLÜSSE ZUM PLAN
  und der Zuordnungsschritt im täglichen Cron (mit Kostenmeldung und
  Stückgrenze je Lauf).
- **Messziel:** Präzision für „setzt Maßnahme um“ ≥ 90 % im Golden-Set,
  „erwähnt“ landet nie in der Umsetzungsliste.
- **Kosten (Schätzung):** Erstlauf rund 1.500 Kandidaten in Stapeln zu 20,
  etwa 0,7 Mio. Tokens, ≈ 0,20–0,40 $; laufend wenige Cent pro Woche.

### Phase 4b: Offene Aufträge

**Stand nach dem Bau (09.11.2026):**

- **Art 3 — Plan ohne aktuellen Bericht: gebaut.** Die Übersicht trägt den
  Block „Wo man nachfragen kann“: die Pläne mit Berichtsstand „Kein Bericht
  gefunden“ oder „Laufzeit abgelaufen, keine Auswertung gefunden“, am längsten
  Stillen zuerst, je Zeile die Tatsache mit Datum und die vorbereitete Frage
  für „Frag den Rat“. Darunter der feste Satz, was Ratslotse nicht sieht.
- **Art 1 — Maßnahme mit verstrichenem Termin: nichts zu zeigen.** Keine der
  sieben Maßnahmenlisten nennt einen Termin je Maßnahme.
- **Art 2 — Ratsauftrag ohne Folge: gemessen, verfehlt, nicht gebaut.** Die
  enge Regel („Die Verwaltung wird beauftragt / gebeten / aufgefordert“ in
  einem angenommenen Beschluss) findet 153 Aufträge. Nach der Gegenprobe ohne
  Modell (spätere Station in der Akte, spätere Vorlage, die die Nummer zitiert,
  späterer Tagesordnungspunkt mit seltenen Titelwörtern) bleiben 22 ohne
  gefundene Folge. In einer Stichprobe von zehn sind mindestens sechs falsch:
  Es gibt Folgevorlagen unter anderem Titel (Stadtmuseum, Haus der Jugend,
  Smart City, Haarenesch), oder der Auftrag war ein Vollzugsauftrag, auf den
  gar kein Bericht folgen muss. Das Messziel von 90 % ist damit weit verfehlt;
  nach der Regel unten erscheint die Liste nicht. Was sie bräuchte: die
  Unterscheidung von Berichts- und Vollzugsaufträgen und eine Gegenprobe über
  den Inhalt statt über Titel — also ein Modell und ein Golden-Set. Frage B
  (eigener Schalter) stellt sich erst dann.

**Zweite Messung, mit Modell (10.11.2026) — wieder verfehlt, weiter nicht
ausgeliefert.** Zwei Modellschritte (`council/plan_judge.py`, Luna): erst die
Art des Auftrags — soll dem Rat etwas vorgelegt werden (Bericht, Prüfergebnis,
Konzept) oder ist es Vollzug? —, dann je Berichtsauftrag die Frage, ob einer
der späteren Tagesordnungspunkte mit passenden Titelwörtern die Folge ist.

| Schritt | Zahl |
|---|---:|
| Aufträge nach enger Regel | 153 |
| davon Berichtsaufträge (Modell; Golden-Set 19 von 20 vertretbar) | 57 |
| davon älter als sechs Monate | 51 |
| ohne gefundene Folge | 16 |
| **davon von Hand nachgeprüft falsch** | **mindestens 8** |

Die Präzision für „ohne Folge“ liegt damit bei höchstens 50 %, das Messziel
sind 90 %. Von den neun Aufträgen des Golden-Sets, die nachweislich
fortgeführt wurden, landete nach dem Weiten der Kandidatensuche keiner mehr
unter „ohne Folge“ — die Fehler sitzen woanders:

1. **Die Folge kam unter anderem Namen oder ging in etwas Größerem auf.** Das
   Park-and-Ride-Konzept von 2019 wurde ein Teilkonzept des Mobilitätsplans,
   das Aufforstungs- und Baumprogramm die Baumerhalt- und Stadtgrünstrategie,
   das Verpflegungskonzept die Rahmenkonzepte für Schulen und Kitas, die
   Leitlinien für die Beschaffung kamen fünf Jahre später als „Nachhaltige
   Beschaffung“. Eine Suche über Titelwörter findet das nicht.
2. **Das Modell übersieht eine passende Folge**, obwohl sie unter den
   Kandidaten steht (Evaluation des step2025, `21/0217`).
3. **Verfahrensaufträge:** „für die Sitzung am selben Tag eine aktualisierte
   Vorlage erstellen“ ist ein Auftrag, dessen Folge die Fassung `/1` ist.
4. **Vollzug als Berichtsauftrag eingeordnet** (Schottergärten beseitigen
   lassen).

Fünf bis sieben der 16 sind vermutlich wirklich ohne Folge geblieben
(Wärmeversorgungsleitlinie, Bündelung der Wettbewerbe, jährlicher Bericht zum
Begrüßungsgeld) — aber „vermutlich“ reicht für eine Liste nicht, die sagt, wo
die Stadt etwas schuldig geblieben ist. Was ein dritter Anlauf bräuchte: eine
Suche über den INHALT späterer Vorlagen (die Embeddings liegen auf dem Server,
nicht im lokalen Abzug) statt über Titel, und einen Menschen, der jede Zeile
vor dem Erscheinen bestätigt. Naheliegender ist eine andere Form: nicht
„ohne Folge“ behaupten, sondern zu jedem Auftrag die gefundenen späteren
Punkte zeigen — das wäre eine Auskunft und kein Vorwurf.

**Kosten gemessen:** 0,0034 $ für das Golden-Set, 0,018 $ für alle 153; mit
Wiederholungen rund 0,03 $. Die Messung lässt sich wiederholen:
`python scripts/plan_modell.py auftraege [--golden]`.

Art 3 steht seit Phase 3. Hier kommen die beiden anderen, in dieser
Reihenfolge:

**Erster Teil — Maßnahme mit verstrichenem Termin (Art 1):**

- Feld `due` in den Maßnahmendateien, wo der Plan einen Termin nennt
  (Wärmeplan „kurz-“ und „mittelfristig“ zählen nicht, ein Jahr zählt).
- Anzeige nur, wenn der jüngste Stand der Maßnahme nicht `done` ist, mit
  beiden Daten.
- Kein Modell.

**Zweiter Teil — Ratsauftrag ohne Folge (Art 2):**

- **Aufträge erkennen:** angenommene Beschlüsse, deren Text die Verwaltung
  beauftragt (prüfen, berichten, vorlegen, erarbeiten, umsetzen). Die enge
  Regel „wird beauftragt / gebeten / aufgefordert“ trifft 341 angenommene
  Beschlüsse; weitere Verbmuster werden hier gemessen, ein Modell nur für die
  unklaren Fälle. Dazu die 1.447 Zusagen der Verwaltung (`kind = pledge`),
  soweit sie ein Datum nennen.
- **Gegenprobe ohne Modell:** Beratungsfolge der Vorlage, Akte, spätere
  Vorlagen mit gleichem Gegenstand (Titelähnlichkeit, Embeddings), Volltext
  nach Vorlagennummer. Was danach offen bleibt, prüft ein Modell noch einmal
  gegen die drei nächsten Kandidaten („ist das die Folge?“).
- Tabelle `council_open_mandates(decision_id | speech_id, kind, since,
  last_station_date, checked_at, method)`, im Cron neu gebaut;
  Endpunkt `GET /council/open-mandates` (Filter Themenfeld, Gremium, Plan).
- **Golden-Set:** 40 Aufträge von Hand (durch den Agenten, gegen Protokolle
  und Beratungsfolge) als „offen“ oder „erledigt“ bewertet.
- **Messziel:** Präzision für „offen“ ≥ 90 %; jeder falsche Treffer im
  Golden-Set bekommt eine Ursache (fehlende Akte, Bericht ohne Vorlage …).
  **Wird das Ziel verfehlt, erscheint die Liste nicht** — auch nicht auf dev
  ohne Kennzeichnung.
- **Kosten (Schätzung):** Modell nur für Unklares und Gegenproben
  ≈ 0,30–0,60 $; vorher mit `limit=20` messen.

### Phase 5: Rückblick, restliche Pläne, iOS

**Rückblick gebaut, ohne Modell:** Jeder der zehn abgelaufenen oder abgelösten
Pläne trägt den festen Aufbau aus § 3.3 — was vorgesehen war, was die
Verwaltung meldet, welche Grenzen der Bericht selbst nennt, was weiterläuft.
Die Sätze der Verwaltung sind wörtlich und kuratiert
(`council/plan_reviews/<key>.json`, bisher Schulentwicklungsplan 2018,
step2025 und Aktionsplan Gewalt 2020); `scripts/pruefe_plaene.py` prüft gegen
den Bestand, dass jeder Satz so in seiner Vorlage steht. Wo es keine
Auswertung gibt, steht „Eine Auswertung hat Ratslotse im
Ratsinformationssystem nicht gefunden“ — vier Pläne. Ein Modell schreibt
nichts.

**Drei weitere Maßnahmenlisten, ohne Modell (10.11.2026, #1830):**

| Plan | Quelle | Gelesen | Wie |
|---|---|---:|---|
| Digitalisierungsstrategie | Umsetzungsplan `24/0574`, Abschnitte 2.2.1–2.2.5 | 40 | fette Zeilen unter ihrer Abschnittsüberschrift; die Stadt nummeriert nicht |
| Agenda 2025 (altersgerechte Stadt) | `25/0403`, Tabellen der vier Bausteine | 26 | Nummer am Rand, Titel aus der Spalte daneben; je Baustein lückenlos |
| smv2025 | Anhang 1 zu `24/0293/1` | 112 | Tabelle mit neun Spalten, **mit Stand je Maßnahme** |

Der Fund dabei: Den Stand jeder Einzelmaßnahme des smv2025 hat die Stadt nie
als eigene Vorlage vorgelegt — er steht in einem Anhang zur Fortschreibung des
**Lärmaktionsplans** (Grundlage laut Anhang: Evaluationsbericht des
Fachdienstes Mobilität von 2021, aktualisiert 10/2023). Verteilung: 40
umgesetzt, 35 in Umsetzung, 11 in Planung, 15 Vorüberlegungen, 2 noch nicht
begonnen, 9 nicht umgesetzt oder aufgegeben. Der Anhang nummeriert bis 126,
enthält aber 112 Zeilen; bei zehn Zeilen weicht das Wort der Spalte „Status“
vom Kürzel der letzten Spalte ab. Beides steht als Hinweis auf der Seite. Im
Rückblick heißt es dazu: keine eigene Vorlage zur Auswertung gefunden, den
Stand nennt die Stadt in einer Anlage — ein Stand ist keine Auswertung.

Nicht aufgenommen, weil die Dokumente es nicht hergeben: das Handlungskonzept
Kinder- und Jugendbeteiligung (`26/0710/1` nennt operative Ziele, keine
Maßnahmen), der Maßnahmenkatalog zum Integrationskonzept (`21/0287`, nur das
Handlungsfeld Bildung und Arbeit) und der Lärmaktionsplan selbst (172 Seiten
Fließtext; die Tempo-30-Abschnitte stehen im Beschluss). Die Agenda 2025 nennt
je Paket auch einen Stand („laufend“, „ggf. zu entwickeln“) — das ist der
Stand bei Beschluss, kein Bericht, und ist bewusst nicht übernommen.

**Ein Fehler, den diese Durchsicht fand:** 44 Tagesordnungspunkte trugen das
Ergebnis einer Einzelabstimmung über einen Änderungsantrag statt das des
Hauptbeschlusses (beide stehen unter derselben TOP-Nummer). Bei 17 davon war
das Ergebnis dadurch falsch — der Ratsbeschluss zur Ernährungsstrategie, zum
ISEK, zum Einzelhandelsentwicklungskonzept und zum smv2025 stand als
„abgelehnt“ da. Behoben in `store_plaene.plan_tracking_rows`, mit Wächter in
`tests/test_plaene_zuordnung.py`.

**iOS-Ansicht gebaut (10.11.2026):** In der Analyse steht an der Stelle des
Reiters „Ziele“ der Reiter „Pläne“, solange der Schalter `plaene` an ist
(`CouncilPlansView.swift`). Die Übersicht zeigt alle Pläne mit Berichtsstand
und — wo die Stadt eine Verteilung meldet — einem Band; die Planseite öffnet
als Blatt mit Rückblick, Berichten im Rat, Stand laut Stadt, Kennzahl,
Maßnahmen und Beschlüssen. Die Modelle sind handgeschrieben und laufen durch
`scripts/ios_vertrag.py` (beide Aufrufstellen gebunden, null Befunde). Alle
Sätze kommen vom Server. Bewusst klein gehalten: keine eigene Route (ein Link
`/council/plan?key=…` öffnet weiter das Web), kein Zeitband, keine Suche in
den Maßnahmen. Die alten Ziel-Endpunkte bleiben, bis die ausgelieferte App
sie nicht mehr braucht.

Geprüft im Simulator gegen ein lokales Backend mit dem echten Bestand, nicht
nur gegen die Sichtprobe — und dabei fiel auf, dass die **Analyse-Seite der
App seit 09/2026 gar nicht mehr lud** („unerwartetes Format“): Der Server
sendet `accepted`/`rejected`/`postponed`, die App las `angenommen`/
`abgelehnt`/`vertagt`, nicht optional. Der Vertrag führte diese Felder als
`Any`, also hatte `ios_vertrag.py` nichts zu prüfen. Behoben an drei Stellen:
die App liest die englischen Namen; die Antwortform ist ausgeschrieben
(`AnalysisSuccessRate` u. a.), sodass der Wächter die Felder jetzt bindet; und
der Server schickt die alten Namen daneben, bis `APP_MIN_BUILD` über dem
Build mit der Korrektur liegt — damit auch die installierte App wieder lädt.

**Offen:** der App-Build mit dieser Ansicht (TestFlight), danach
`APP_MIN_BUILD`; Listen für Pläne, deren Maßnahmen nur im Fließtext stehen.

- Rückblick nach § 3.3 für den Schulentwicklungsplan 2018, den Aktionsplan
  Gewalt 2020–2025, das Integrationskonzept 2020–2025, step2025 und den KAI.
  Die Teile kommen aus Register, Stand und Berichten. Ein Modell schreibt
  höchstens die Zusammenfassung der „Grenzen“, und zwar zitierend.
- Maßnahmenlisten für die übrigen Pläne aus A und B, soweit die Dokumente das
  hergeben — zuerst per Parser wie in Phase 2, ein Modell nur, wo keine
  Tabelle im Text steht.
- Die iOS-Ansicht „Pläne“ mit handgeschriebenen Modellen nach
  `ios/CLAUDE.md`, im nächsten App-Build. Danach steigt `APP_MIN_BUILD`, und
  die alten Ziel-Endpunkte können gehen.
- **Lieferbar:** Rückblick auf dev, iOS-Build in TestFlight und die
  Freigabe-Entscheidung für Prod (Schalter).
- **Kosten (Schätzung):** ≈ 1–1,50 $ für rund 20 Pläne, falls ein Modell
  nötig wird. Das liegt über 1 $, also vorher fragen. Phase 2 lässt erwarten,
  dass es weniger wird.

### Phase 5b: Pläne von vor 2018

**Gebaut (09.11.2026): der Verweis auf die Seite der Stadt.** `robots.txt` von
oldenburg.de erlaubt den Abruf (gesperrt sind nur Systemordner und Adressen
mit `?id=`). Aus der Seitenübersicht der Stadt (2.072 Adressen, vier Abrufe)
sind 21 Pläne des Registers ihrer Seite zugeordnet, jede Adresse einzeln
abgerufen und gegen ihre Überschrift geprüft (`PLAN_WEBSITES` in
`council/plans.py`). Die Planseite verlinkt sie als „Seite der Stadt“;
übernommen wird nur der Verweis, kein Text und kein Dokument.

**Was die Seiten zu den offenen Fällen sagen:**

- *Wohnkonzept:* Die Stadt stellt weiter das Wohnkonzept 2025 vor (Kurzfassung,
  Ratsbeschluss 28.10.2013); eine neue Gesamtfassung nennt die Seite nicht.
- *Sportentwicklungsplan:* Die Seite stellt den Plan von 2009 als geltend vor
  (Ratsbeschluss Juni 2009, einstimmig); eine Fortschreibung nennt sie nicht.
- *Innenstadtstrategie:* Die Seite beschreibt die Strategie, nennt aber keinen
  Stand. *Luftreinhalteplan* und *Rad- und Fußverkehrsprogramm* haben in der
  Seitenübersicht keine eigene Seite.

**Offen:** die Dokumente der Pläne von vor 2018 selbst (PDF) als Quelle mit
Maßnahmenliste aufzunehmen (`source = "website"`).

Das Klimaportal ist nach Phase 3 gewandert. Hier bleibt:

- **Pläne vor 2018 von oldenburg.de:** die Planseiten der Stadt durchsehen
  (vorher Nutzungsbedingungen und `robots.txt` lesen, höflich abrufen), PDFs
  mit Datum und Herkunft ablegen, ins Register mit `source = "website"`.
  Heute trägt kein Eintrag diese Quelle. Ohne Ratsbeschluss im Bestand heißt
  der Kicker „VERÖFFENTLICHT 2014“, nicht „BESCHLOSSEN“.
- **Die offenen Fälle aus § 8, Frage C** (Luftreinhalteplan, Wohnkonzept,
  Innenstadtstrategie, Rad- und Fußverkehrsprogramm nach 2022) werden hier
  gegen die Seiten der Stadt geklärt.
- **Kosten:** Abruf und Text 0 $, Maßnahmenlisten ≈ 0,30 $.

### Phase 6: Pflege (laufend)

**Gebaut:** Der nächtliche Protokoll-Lauf trägt zwei Kennzahlen ins
Cron-Protokoll des Admin-Panels: „Pläne: Stand veraltet“ (ein Bericht ist
jünger als die geprüfte Statusdatei) und „Pläne: Frist fällig“ (Laufzeitende
oder Überprüfung in den nächsten sechs Monaten oder schon verstrichen, ohne
Nachfolger). `scripts/pruefe_plaene.py` nennt die Pläne beim Namen; beide
rechnen mit derselben Regel (`plan_state.maintenance`).

- Neue Berichte einer Reihe hängen sich im Cron selbst an.
- **Neuer Bericht, alter Stand:** `pruefe_plaene.py` meldet es; der Stand wird
  per Skript und PR nachgezogen. Beim Klimaschutzplan ist das dreimal im
  Jahr.
- Hinweise im Admin-Panel bei „Fortschreibung fällig“ (Gleichstellungsplan
  31.12.2026, Abfallwirtschaftskonzept 2027, Klimaschutzplan und
  Digitalisierungsstrategie 2027, Agenda 2025 Evaluation 2028, Lärmaktionsplan 09/2029, Kinder- und
  Jugendbeteiligung 09/2029, Wärmeplan 06/2031) und bei Plänen, die in „Kein
  Bericht gefunden“ wechseln.
- Neue Pläne (KLAK, Integrationskonzept 2026, KSP-Fortschreibung) gehen
  per PR ins Register.
- „Frag den Rat“ kann das Register nutzen, um Fragen wie „Was ist aus dem
  Plan X geworden?“ zu beantworten (Anschluss an die Akte).

## 6. Kosten im Überblick

| Phase | Modell | Kosten |
|---|---|---:|
| 0, 1, 2 | keins | **0 $ gemessen** |
| 3 Stand | Portal, Parser, Farben; Bildmodell für fünf Bilder; Luna für den Mobilitätsplan | ≈ 0,30 $ |
| 4 Zuordnung | Luna/DeepSeek, Golden-Set | ≈ 0,40 $ + laufend Cent |
| 4b offene Aufträge | Regeln, Luna für Unklares und Gegenprobe | ≈ 0,60 $ |
| 5 übrige Pläne, Rückblick | Parser zuerst, Luna wo nötig | ≤ 1,50 $ |
| 5b Pläne vor 2018 | Abruf, Luna für Maßnahmen | ≈ 0,30 $ |
| **Summe bis zur Freigabe** | | **≈ 3 $** |

Die erste Fassung schätzte 4 bis 5 $. Die Modellkosten sind klein. Teuer ist
das **Prüfen**: Maßnahmenlisten, Golden-Sets und die „offen“-Fälle. Das
übernimmt der Agent (Tims Entscheidung 09.11.2026) — mit Zählabgleich,
Stichprobe und den Befunden im PR.

## 7. Risiken

- **Die Stadt ändert ihre Zählung** (KSP 90 → 97, „Realisiert“ 22 → 20).
  Deshalb zeigen wir eine Zeitreihe mit dem Wortlaut der Stadt und keine
  eigene Quote — und deshalb die drei Bausteine in § 3.3a.
- **Das Klimaportal ist eine fremde Seite.** Ihr Aufbau kann sich ändern (die
  Daten stehen in Attributen eines Seitengenerators, nicht in einer
  Schnittstelle), eine Lizenz nennt sie nicht, und sie kann den Abruf
  sperren. Dagegen: nur Tatsachen mit Quelle, Abzug im Zwischenspeicher, die
  Ratsvorlagen als Gegenprobe, und bei einer Sperre fragen statt umgehen.
  Fällt das Portal weg, bleiben die zwei Punkte aus den Vorlagen.
- **Status nur als Farbe, Bild oder mündlich:** Lässt sich das nicht lesen,
  sagen wir „Stand nicht im Text“ statt zu raten.
- **Pläne vor 2018** (KAI 2015, Wohnkonzept 2025, step2025,
  Sportentwicklungsplan 2009) liegen außerhalb des Bestands. Ohne Nachladen
  bleiben sie Stammdaten ohne Maßnahmen.
- **Externe Quellen dürfen nicht wie Beschlüsse aussehen.** Der Kicker nennt
  die Herkunft (§ 3.4 Nr. 3).
- **Politische Lesart:** Eine Liste „nicht umgesetzt“ kann wie eine Anklage
  wirken, „Kein Bericht gefunden“ ebenso. Dagegen helfen die Regeln aus
  § 3.4, die Gegenprobe in Phase 3 und Bild plus OK vor jedem UI-PR.
- **Offene Aufträge, Art 2:** das größte Risiko des Programms (§ 3.5). Ein
  eigener Schalter und ein Messziel, unter dem nichts erscheint.
- **Gestapelte PRs und generierte Dateien:** Solange #1813 offen ist, bauen
  Phase 2 und die Gestaltungsrunde darauf auf, und jede Vertragsänderung auf
  `dev` kollidiert in `lib/api-schema.ts` (so geschehen am 09.11.). Die
  Auflösung ist immer dieselbe — neu schneiden —, kostet aber je PR einen
  Durchgang. Je früher #1813 hineingeht, desto weniger davon.
- **App:** Die neue Antwortform braucht einen Build. Bis dahin müssen beide
  Endpunkte gepflegt werden.

## 8. Was zu entscheiden ist

### Entschieden (09.11.2026)

Die Nummern 1 bis 6 sind die der ersten Fassung.

1. **Was zählt als Plan der Stadt?** Wie vorgeschlagen: Klasse 1 sind Pläne
   mit Maßnahmen und Ratsbeschluss (A), Klasse 2 Rahmenstrategien (B),
   Klasse 3 Pflicht- und Fachpläne (C). Ein Nahverkehrsplan des ZVBN und
   Steuerungskonzepte wie das EEK laufen nur als Verweis mit.
2. **Externe Quellen:** ja, beides — Klimaportal und Pläne von vor 2018.
3. **Rückblick und Einordnung:** ja zu einer eigenen, fairen Einordnung je
   Plan (§ 3.3a). Das Wie regelt Nr. 7.
4. **Die sechs Ziele und der Stempel:** Die alte Bewertung („bringt voran /
   bremst“ samt Stempel, täglich per Modell aus `track_goals`) läuft weiter,
   bis „Pläne“ auf Prod ist. Dann hört der tägliche Lauf auf, und die alten
   Endpunkte liefern den letzten Stand für die ausgelieferte App, bis deren
   nächster Build „Pläne“ kennt.
5. **Sichtbarkeit:** dev zuerst, Prod mit dem nächsten Release, sobald
   fertig.
6. **Prüfaufwand:** Der Agent prüft, mit vollständigem Zählabgleich.
7. **Einordnung in drei Bausteinen** (neu, nach der Überarbeitung):
   Berichtsstand, Stand laut Stadt und eigene Termine des Plans ersetzen die
   fünf Stufen nach Dritteln (§ 3.3a). Ein bewertendes Wort je Plan gibt es
   nicht; auch eine Zwischenlösung (Stufen nur für ausgezählte, abgelaufene
   Pläne) entfällt.
8. **Kein Stand je Maßnahme aus dem Klimaportal** (neu, 09.11.2026): Die
   Paketseiten widersprechen sich selbst (§ 1.3). Übernommen wird nur die
   Jahresreihe, die sich mit den Ratsvorlagen deckt.

### Offen

**B. Eigener Schalter für „Ratsauftrag ohne Folge“?** Stellt sich vorerst
nicht: Die Liste verfehlt das Messziel und ist nicht gebaut (§ 5, Phase 4b).
Die Frage kommt wieder, wenn eine Gegenprobe über den Inhalt die 90 % erreicht.

**C. Die offenen Fälle** (alte Frage 7): Zum Wohnkonzept und zum
Sportentwicklungsplan sagen die Seiten der Stadt, dass die alten Fassungen
weiter gelten (§ 5, Phase 5b). Luftreinhalteplan und Rad- und
Fußverkehrsprogramm nach 2022 bleiben ungeklärt; sie stehen unter „Wo man
nachfragen kann“. Falls Tim einen der Stände aus eigener Kenntnis weiß, spart
das die Suche.

**D. Wie weiter mit dem, was ein Modell braucht?** Drei Stücke sind bewusst
offen, weil sie ein Modell und ein Golden-Set brauchen und nicht nachts ohne
Rückfrage laufen sollten: der Stand je Maßnahme beim Mobilitätsplan, die
Zuordnung von Vorlagen, die einen Plan nur beim Namen nennen, und die
Gegenprobe für „Ratsauftrag ohne Folge“. Jedes kostet nach Schätzung unter
1 $; teurer ist das Prüfen.

## Anhang: Messbefehle

```bash
# Zuordnung neu bauen (ohne Modell, rund eine Sekunde)
python scripts/build_plans.py

# Register gegen den echten Bestand prüfen (nur lesend; Exit 1 bei Fehlern)
python scripts/pruefe_plaene.py

# Maßnahmendateien gegen ihre Quelle prüfen; --nur <key> für einen Plan
python scripts/plan_massnahmen.py --pruefen

# Rollen der zugeordneten Tagesordnungspunkte
sqlite3 "file:data/council.sqlite?mode=ro" "
select role, count(*) from council_plan_items group by 1 order by 2 desc;"

# Pläne ohne Bericht
sqlite3 "file:data/council.sqlite?mode=ro" "
select plan_key, max(date) from council_plan_items
where role in ('report','evaluation') group by 1 order by 2;"

# Planvorlagen nach Titel (Beispiel)
sqlite3 "file:data/council.sqlite?mode=ro" "
select t.template_number, t.title,
       (select min(date) from council_deliberations d where d.kvonr=t.kvonr)
from council_templates t
where t.title like '%aktionsplan%' or t.title like '%konzept%' or t.title like '%strategie%'
order by 3;"

# Ratsbeschluss und Ergebnis je Planvorlage
sqlite3 "file:data/council.sqlite?mode=ro" "
select d.template_number, s.session_date, d.outcome, d.vote
from council_decisions d join council_sessions s on s.ksinr=d.ksinr
where s.committee='Rat' and d.template_number in ('20/0564','22/0910','26/0236');"

# Alle Tagesordnungspunkte eines Plans, auch mündliche Berichte ohne Vorlage
sqlite3 "file:data/council.sqlite?mode=ro" "
select s.session_date, s.committee, coalesce(a.template_number,'—'), a.title
from council_agenda_items a join council_sessions s on s.ksinr=a.ksinr
where a.title like '%Aktionsplan%Gewalt%' order by 1;"

# Namens- statt Nummernverweise
sqlite3 "file:data/council.sqlite?mode=ro" "
select count(*) from council_templates where raw_text like '%Klimaschutzplan%';"

# Auftrags-Kandidaten für Phase 4b (enge Regel)
sqlite3 "file:data/council.sqlite?mode=ro" "
select outcome, count(*) from council_decisions
where official_text like '%wird beauftragt%' or official_text like '%wird gebeten%'
   or official_text like '%wird aufgefordert%' group by 1 order by 2 desc;"
```

Anlagentexte fehlen im lokalen Abzug (`council_attachments.raw_text` ist leer).
Gelesen wurden sie über das MCP-Werkzeug `get_attachment`: 314635 (Evaluation
Gewalt), 275932 (Priorisierung Mobilitätsplan) und 293527 (Agenda 2025). Die
Quellen der Maßnahmenlisten liegen nach dem ersten Lauf von
`plan_massnahmen.py` im Zwischenspeicher `~/.cache/ratslotse/plan-quellen/`.
