# Plan: Aus „Ziele“ wird „Pläne der Stadt“

Stand 09.11.2026. Grundlage ist eine Bestandsaufnahme im Abzug von dev
(`data/council.sqlite`, Sitzungen 11.01.2018 bis 02.11.2026, 5.277 Vorlagen,
9.241 Beschlüsse) und über die MCP-Werkzeuge (Anlagentexte). Es wurde kein
Code geändert und kein bezahltes Modell aufgerufen. Alle Kostenangaben sind
**Schätzungen aus Listenpreisen** (`kern/usage.py`). Vor jedem Lauf werden sie
mit `limit=20` gemessen, und ab 1 $ fragen wir Tim.

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
- **Externe Quellen ja:** das Monitoring im Klimaportal und Pläne von vor 2018
  von oldenburg.de (Phase 5b).
- **Möglichst wenig Handarbeit:** Die Maßnahmenlisten prüft der Agent selbst —
  vollständiger Zählabgleich gegen die Zahl der Stadt, Stichprobe gegen die
  Quelle, Befunde im PR. Tim prüft nicht jede Liste.
- **Neu: „Offene Aufträge“** (§ 3.5, Phase 4b) — wo etwas beschlossen ist und
  keine Umsetzung, kein Bericht, kein Folgebeschluss zu finden ist. Für alle
  interessant, für Ratsmitglieder der Anlass nachzufragen.

## 1. Befund

### 1.1 Was die Seite heute tut

- Sechs Ziele stehen fest im Code (`council/goals.py::GOALS`): Label,
  Beschreibung und Stichwörter.
- `scripts/track_goals.py` läuft im täglichen Protokoll-Cron
  (`check_protocols.py`, Schritt „Ziele“). Er lässt `deepseek-v4-pro` jeden
  Kandidaten-Beschluss als `advances` / `hinders` / `neutral` einstufen und
  schreibt das in `council_goal_links`.
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

#### A. Laufend, mit Maßnahmenliste und Berichtsreihe (Pilotkandidaten)

| Plan | Beschluss | Laufzeit | Maßnahmen | Berichte | Kennzahl |
|---|---|---|---|---|---|
| **Klimaschutzplan Oldenburg 2035** (mit Klimaziel) | Klimaziel `21/0249/2`, Rat 26.04.2021, einstimmig; Plan `22/0910`, Rat 19.12.2022, angenommen | bis 2035; Vorschlag zur Fortschreibung für 2027 angekündigt (`26/0750`) | 90 (`26/0074`), inzwischen 97 (`26/0750`); Kennungen wie `Gebäude_05`, `Klimapakt_07`, `Beratung_01` | „Klimaschutz-Aktivitäten n/JJJJ“ dreimal im Jahr, 15 Stück von `22/0037` (02/2022) bis `26/0750` (ASUK 08.10.2026), Berichtswesen nach `22/0036`; Statusverteilung in `26/0074` und `26/0750`; externes Fortschrittsbarometer auf klimaportal.oldenburg.de/monitoring | THG-Bilanz (`23/0653`, `25/0131`, `25/0866`): Zwischenziel 2023 −15 %, erreicht −17,9 % gegenüber 2020 (1,14 Mio. t) |
| **Oldenburger Wärmeplan** | `26/0236`, Rat 01.06.2026, mehrheitlich | Überprüfung spätestens nach fünf Jahren (§ 25 WPG); alle Maßnahmen „kurz- oder mittelfristig“ | 18 (K1–K3, F1–F2, T1–T5, O1–O8), je Maßnahme mit Stand und Zielsetzung in der Vorlage | Ergebnisbericht `25/0743`; danach über die Klimaschutz-Berichte (z. B. O7 in `26/0750`) | Zielsetzung je Maßnahme fürs Monitoring (in `26/0236`) |
| **Mobilitätsplan Oldenburg 2030** | `23/0211/2`, Rat 26.06.2023, mehrheitlich; Vorgehen `23/0867`, Rat 27.11.2023; Priorisierung `24/0216`, Rat 27.05.2024 | bis 2030 | über 250 Einzelmaßnahmen, rund 70 priorisiert (Anlage 1 zu `24/0216`) | jährlich im Verkehrsausschuss: `23/0562`, `25/0041`, `26/0190`; Zuordnung zum Klimaschutzplan `25/0379` | Zielzahlen in der Priorisierung (7 Premiumrouten, 4 umgestaltete und 9 neue Fahrradstraßen, Ladepunkte je Quartal); Modal-Split-Erhebung lief 2024 an |
| **Aktionsplan gegen Gewalt an Frauen\* und Häusliche Gewalt** | `20/0564`, Rat 28.09.2020, einstimmig; Evaluation und Fortschreibung `26/0681/1`, Rat 28.09.2026, einstimmig | kein Enddatum; Umsetzungszeitraum 2020–2025, Fortschreibung „für die kommenden Jahre“ | 2020: 87 (8 übergreifend, 56 Gewalt gegen Frauen\*, 23 Häusliche Gewalt); 2026: 6 Fokusthemen × 5 = 30 Empfehlungen | schriftlich `21/0704`, `22/0494`, `23/0356`, `26/0080`; 7 Berichte ohne Vorlage und ohne Text (08/2019, dazu sechs „mündliche“ 10/2023–03/2025); Evaluation mit dem Stand **jeder** der 87 Empfehlungen (Anlage 314635, Anhang 4.1, S. 64–89); künftig jährlicher Bericht | Fallzahlen 2020–2025 (Kap. 1.3), keine Zielwerte |
| **Ernährungsstrategie** | `24/0810` und `24/0811`, Rat 24.02.2025, mehrheitlich | offen | 9 Ziele, 68 Handlungsansätze (A1 …), davon 5 zur Umsetzung beschlossen | `23/0151`, `23/0741`, `24/0390`; Umsetzungsstand **je Ansatz** in `26/0431` (ASUK 06/2026) | qualitative Stufe 0/25/50/75/100 % je Ansatz |
| **Lärmaktionsplan** (Fortschreibung) | `24/0293/1`, Rat 30.09.2024, mehrheitlich; Vorgängerprüfung `20/0049` | Tempo 30, Stufe 1 seit 14.12.2025, Stufe 2 geplant Ende 2027 | offen (Anlage 3 nicht ausgewertet); Tempo-30-Abschnitte auf neun Straßen namentlich im Beschluss | `25/0696` (Umsetzung Tempo 30) | offen |
| **Digitalisierungsstrategie** | `23/0708`, Rat 18.12.2023, einstimmig | Vision bis 2045; erste Phase des Umsetzungsplans 2025–2027 | offen (Umsetzungsplan `24/0574`, 25 Seiten) | Statusbericht `25/0796` (11/2025) | z. B. 248 digitale Leistungen im Serviceportal (`25/0796`) |
| **Kita-Ausbaukonzept** | Grundkonzept Rat 30.06.2008 (vor dem Bestand); 4. Fortschreibung `18/0308`, Rat 25.06.2018; 5. Fortschreibung `22/0620`, Rat 26.09.2022 | Ausbau bis 2030 | Gruppenzahlen je Fortschreibung; laufende Vorlagen „Maßnahmenplanung … Kindertagesbetreuung“ | jährlich mit der Kita-Situation (laut `18/0308`) | Zielquoten 55 % Krippe, 10 % Tagespflege, 99,5 % Kindergarten; die Ist-Werte sind offen |
| **Agenda 2025 „Selbstbestimmt und mittendrin!“** (altersgerechte Stadt) | `25/0403`, Rat 30.06.2025, einstimmig | Evaluation 2028 | 4 Bausteine; Kapitel „Monitoring“ | noch keiner | offen |
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
| Strategieplan Mobilität und Verkehr smv2025 | `18/0254`, Rat 27.08.2018 | abgelöst durch den Mobilitätsplan 2030 (`23/0211/2`) |
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
| a) Zählblock im Vorlagentext | KSP: „Aktuell sind die 97 Klimaschutzmaßnahmen wie folgt umgesetzt: 10 Zuordnung Amt, 15 In Planung, 9 Umsetzungsreif, 34 In Umsetzung, 20 Realisiert, 9 Ein-/Zurückgestellt“ (`26/0750`) | per Regex, automatisch |
| b) Tabelle je Maßnahme im Vorlagentext | Ernährungsstrategie `26/0431` (A1 „Rahmenkonzept Schulverpflegung“, Priorität sehr hoch, 100 % …); Wärmeplan `26/0236` | Parser, Modell nur als Notbehelf |
| c) Tabelle je Maßnahme in einer PDF-Anlage, Stand **als Zellfarbe** | Aktionsplan Gewalt, Anhang 4.1: dunkelgrün = umgesetzt, hellgrün = einmal umgesetzt, wiederholungsbedürftig, pastellgrün = abgegeben, gelb = begonnen, rot = nicht umgesetzt, weiter nötig, grau = eingestellt | Der Text allein verliert den Stand. Die Füllfarben lassen sich mit PyMuPDF (`page.get_drawings()`) lesen, sonst bleibt nur Handarbeit. |
| d) Fließtext-Sachstand | Mobilitätsplan `26/0190`, Integrationskonzept `26/0670`, Wohnungslosenhilfe | Modell je Maßnahme mit Zitat, danach Review |
| e) Mündlicher Bericht ohne Text | 7 zum Aktionsplan Gewalt (2019–2025); im ganzen Bestand stehen rund 540 Tagesordnungspunkte „mündlicher Bericht“ | nur Termin und Gremium, dazu das Protokoll, falls vorhanden |

Dazu kommt eine **externe Quelle**: das Fortschrittsbarometer im Klimaportal
(klimaportal.oldenburg.de/monitoring). Laut `26/0074` zeigt es je
KSP-Maßnahme Fortschritt, Klimaschutzwirkung und Priorität.

**Die Zahlen der Stadt sind selbst in Bewegung, und das ist der wichtigste
Grund gegen eine eigene Quote.** Beim Klimaschutzplan stehen im Januar 2026
(`26/0074`) 90 Maßnahmen, davon 22 realisiert und 7 ein- oder zurückgestellt.
Im Juni (`26/0418`) sind es weiter 22 realisierte und 9 zurückgestellte. Im
Oktober (`26/0750`) stehen 97 Maßnahmen, davon 20 realisiert. Der Nenner ist
gewachsen und der Zähler gesunken; laut `26/0418` sind „etliche Maßnahmen …
nicht (mehr) treffend beschrieben“. Eine Quote wie „22 % umgesetzt“ wäre also
Scheinpräzision. Beim KAI addiert sich der Stand von 2020 (70 + 61 + 70) zu
201, nicht zu 236 Untermaßnahmen. Das stimmt aber, denn die 35 Maßnahmen der
schulischen Inklusion sind ausgenommen. Solche Fußnoten muss jede Anzeige
mitführen.

**Wirkung ist nicht Umsetzung.** Die THG-Bilanz 2023 (`25/0866`) meldet −17,9 %
gegenüber 2020 und damit mehr als das Zwischenziel. Derselbe Bericht nennt als
Ursache zuerst den bundesweiten Strommix (453 statt 505 g CO₂e/kWh). Ein
Rückblick, der die Minderung dem Plan zuschreibt, wäre falsch.

### 1.4 Wie Beschlüsse zu Plänen finden

| Weg | Befund | Taugt für |
|---|---|---|
| Vorlage des Plans samt Fassungen (`/1`, `/2`) und Beratungsfolge | immer vorhanden | „Beschluss des Plans“, sicher |
| Berichtsreihe über den Titel | z. B. 15 × „Klimaschutz-Aktivitäten“, 24 Tagesordnungspunkte zum Aktionsplan Gewalt (2018–2026), 8 davon ohne Vorlage | „Bericht“, sicher, sobald das Muster je Plan von Hand gesetzt ist |
| Verweis über die **Nummer** | selten: `22/0910` in 8 fremden Vorlagen, `21/0249` in 14, `20/0564` in 0 | sicher, aber dünn |
| Verweis über den **Namen** | häufig: „Klimaschutzplan“ in 103 Vorlagen, „Mobilitätsplan“ in 57, ISEK 59, EEK 64 | nur Kandidaten; **eine Nennung ist keine Umsetzung**, beim EEK sind es fast nur Begründungen von Bebauungsplänen |
| Maßnahmen-Kennung im Text | KSP-Kennungen (`Gebäude_02`, `Wärme_03` …) kommen in Vorlagen vor (mindestens 44 verschiedene), A1–A68 der Ernährungsstrategie, O1–O8 des Wärmeplans | „setzt Maßnahme X um“, sicher |
| Die Akte (`council_matters`, 7.488; 993 Verweiskanten) | bündelt je Vorlagenstamm, nicht je Plan; der Aktionsplan Gewalt liegt über mehr als 15 Akten verstreut | Bausteine; der Plan ist eine Ebene darüber |
| Modellurteil über die Kandidaten | heute `track_goals` mit Stempel ohne Plan- oder Maßnahmenbezug | wird ersetzt durch „Welche Maßnahme, welche Beziehung?“ |

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

### 3.1 Übersicht

Drei Gruppen untereinander: **Laufend · In Arbeit · Abgelaufen oder
abgelöst**. Innerhalb der Gruppen sortieren wir nach Themenfeld, dann nach dem
jüngsten Bericht. Eine Karte je Plan zeigt:

- Kicker: `KLIMA · BESCHLOSSEN 12/2022 · BIS 2035`. Ein Plan, den der Rat nur
  zur Kenntnis genommen hat, heißt `ZUR KENNTNIS 06/2018`.
- Titel und Amt.
- **Letzter Bericht**: Titel, Gremium und Datum. Gibt es keinen, steht dort
  „Kein Umsetzungsbericht im Rat seit dem Beschluss“.
- Eine Statusverteilung **nur**, wenn die Stadt selbst eine liefert. Sie
  erscheint als Reihe von Zählern in den Worten der Stadt („34 in Umsetzung ·
  20 realisiert · 9 zurückgestellt“) mit dem Zusatz „laut Bericht vom
  08.10.2026“. Einen Fortschrittsbalken mit Prozentzahl gibt es nicht.

Eine **Zeitleiste** (Balken vom Beschluss bis zum Laufzeitende; offene Enden
laufen blass aus; Vorgänger und Nachfolger sind verbunden) kommt erst als
zweite Ansicht ab Tablet-Breite. Auf dem Handy bleibt es bei der Liste.

### 3.2 Detailseite je Plan

1. **Kopf:** Name, federführendes Amt, Beschluss-Badge („Beschlossen“ oder
   „Zur Kenntnis genommen“), Gremium, Datum, Link zur Vorlage und zur
   Anlage mit dem Plantext.
2. **LAUFZEIT:** Beginn, Ende oder „ohne Enddatum“, die nächste vorgesehene
   Überprüfung (z. B. Wärmeplan spätestens 2031) sowie Vorgänger und
   Nachfolger.
3. **MASSNAHMEN** (Kicker: „97 · laut Bericht vom 08.10.2026“): gruppiert
   nach Handlungsfeld, je Maßnahme Kennung, Titel und Statuschip im Wortlaut
   der Stadt samt Datum. Ein Tippen zeigt den Verlauf und den Beleg. Hat sich
   die Zählbasis geändert, sagt ein Hinweis das („2022 mit 90 Maßnahmen
   beschlossen“).
4. **BERICHTE:** Zeitstrahl aller Berichte, mündliche als „mündlich, ohne
   Text“ markiert; die letzte Station ist „AKTUELLER STAND“.
5. **KENNZAHL** (nur wo der Plan eine nennt): Soll und Ist mit Bilanzjahr und
   Quelle, dazu die Einordnung **aus dem Bericht selbst** (Strommix).
6. **BESCHLÜSSE ZUM PLAN:** nach Beziehung getrennt: *beschließt oder ändert
   den Plan* · *setzt Maßnahme X um* · *Antrag oder Anfrage dazu* · *erwähnt*.
   Erwähnungen bleiben hinter „Weitere“.

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

Tims Entscheidung (09.11.2026): Ratslotse ordnet jeden Plan ein — fair, ohne
die Stadt abzustrafen. Begründung: Die Stadt hat die Aufgabe, über den Stand
ihrer Pläne zu berichten; eine Einordnung macht diesen Bericht lesbar und
zeigt, wo er fehlt. Gilt für laufende Pläne (als Zwischenstand) und für den
Rückblick.

**Gemessen am Plan selbst, nicht an uns.** Maßstab sind die eigenen Maßnahmen,
Termine und Zielwerte des Plans — nicht, was Ratslotse für richtig hielte.

**Fünf Stufen, nach einer offengelegten Regel** (im Code, im PR sichtbar,
unter jeder Einordnung verlinkt als „So ordnen wir ein“):

| Stufe | Regel (Entwurf, an den fünf Pilotplänen zu eichen) |
|---|---|
| **Weitgehend umgesetzt** | mindestens zwei Drittel der Maßnahmen von der Stadt als umgesetzt gemeldet, oder Zielwert erreicht |
| **Auf dem Weg** | ein Drittel bis zwei Drittel umgesetzt, und der Zeitplan ist laut Plan noch offen |
| **Hinter dem eigenen Zeitplan** | weniger als ein Drittel umgesetzt, obwohl mehr als die Hälfte der Laufzeit vorbei ist |
| **Neu ausgerichtet** | die Stadt hat Maßnahmen gestrichen, ersetzt oder den Plan fortgeschrieben — „anders gedacht“, kein Scheitern |
| **Stand unbekannt** | kein Umsetzungsbericht im Rat seit dem Beschluss oder seit über zwei Jahren |

**Was die Einordnung fair hält:**

- **Daneben steht immer die Stadt selbst:** ihre eigene Einschätzung im
  Wortlaut und die Gründe, die sie nennt (Personal, Geld, Fördermittel,
  Prioritäten, Bundesrecht). „Hinter dem eigenen Zeitplan · laut Stadt fehlen
  Personal und Mittel (Bericht 10/2026, S. 12)“.
- **Bewegung zählt mit:** „seit dem letzten Bericht 3 Maßnahmen mehr
  umgesetzt“. Ein Plan, der aufholt, steht nicht wie einer, der stillsteht.
- **Neu ausrichten ist kein Makel.** Gestrichene oder ersetzte Maßnahmen
  erscheinen unter „Was anders gedacht wurde“, mit Begründung der Stadt.
- **Stand unbekannt ist eine Aussage über den Bericht, nicht über die
  Arbeit.** Der Text sagt das ausdrücklich: „Ob umgesetzt wurde, wissen wir
  nicht — berichtet wurde im Rat nicht.“
- **Keine Rangliste der Pläne, keine Ampel in Rot.** Die Stufen tragen neutrale
  Tints; Grün nur für „weitgehend umgesetzt“.
- **Ein Modell formuliert höchstens die Zusammenfassung**, und zwar zitierend;
  die Stufe selbst rechnet die Regel aus den Statusdaten. So ist sie
  reproduzierbar und angreifbar, wo sie falsch ist.

### 3.4 Neutralität und Scheinpräzision: die Regeln

1. **Keine Gesamtnote über alle Pläne und keine Quote über Pläne hinweg.**
   Die Einordnung gilt je Plan, nach der Regel in § 3.3a. Die Prozent-Stufen
   der Ernährungsstrategie sind laut Stadt eine „qualitative Einschätzung“.
   Wir zeigen sie als Stufen und mitteln sie nie.
2. **Jede Zahl trägt Datum und Beleg.** Ändert sich die Zählbasis, steht das
   dabei.
3. **Selbstauskunft kennzeichnen.** Der Kicker heißt „NACH ANGABEN DER
   VERWALTUNG“, wenn der Stand aus einem Verwaltungsbericht stammt.
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

- **Register als Code:** `council/plans.py` (Code auf Englisch), nach dem
  Vorbild von `GOALS` und `kommunalwahl/wahlen/`. Je Plan stehen dort `key`,
  `title`, `kind`, `policy_field`, `office`, `adopted` (Vorlage, Datum,
  Gremium, `mode`: `adopted` | `noted`), `start`, `end` | `None`,
  `review_due`, `predecessor` und `successor`, `report_patterns` (Titelmuster
  der Berichtsreihe), `measure_source` (Anlage und Seiten) sowie
  `indicator`. Der Grund für Code statt Datenbank: Das Register ist
  Handarbeit, und jede Änderung soll im PR sichtbar sein (wie bei den
  Prompts).
- **Maßnahmen als geprüfte Dateien:** `council/plans/<key>.json` mit
  Kennung, Titel, Handlungsfeld, Amt und Beleg (Anlage, Seite). Das Modell
  schlägt sie vor, ein Mensch prüft, der PR hält sie fest. So ist das Ergebnis
  reproduzierbar, und für kuratierte Daten braucht es keine Migration.
- **Abgeleitete Tabellen** in `council.sqlite`, im Cron neu gebaut, Schema
  **und** `_migrate()` nach `council/CLAUDE.md`:
  - `council_plan_reports(plan_key, kvonr | agenda_item_id, date, committee, oral)`
  - `council_plan_status(plan_key, measure_code NULL, as_of, status_raw, status_norm, source_kvonr, source_document_id, page, method)`.
    `status_norm` hat fünf Stufen (offen · begonnen · in Umsetzung ·
    umgesetzt · zurückgestellt/eingestellt) plus „unklar“. Es dient nur zum
    Gruppieren; angezeigt wird `status_raw`.
  - `council_plan_links(plan_key, measure_code NULL, decision_id, relation, method, confidence)`
- **Logik ins Backend:** Gruppe (laufend, in Arbeit, abgelaufen), Sortierung,
  Zählungen, „seit X kein Bericht“ und die Normalisierung entstehen im
  Backend. Das Frontend zeichnet nur.
- **Endpunkte:** `GET /council/plans` und `GET /council/plan/{key}`, mit
  Antwortformen in `antworten.py` und neu geschnittenem Vertrag. Die alten
  Endpunkte `/council/goals` und `/council/goal/{key}` **bleiben**, bis
  `APP_MIN_BUILD` auf einem App-Build steht, der die neue Ansicht kennt
  (Prüfung: `scripts/ios_vertrag.py --ausgeliefert`).
- **Schalter** `plaene` in `kern/features.py`, mit `fertig_wenn`. Das
  Changelog-Fragment trägt `schalter: plaene`.
- **Wächter:** Jede Vorlagennummer im Register hat das richtige Format, und
  Vorgänger und Nachfolger zeigen auf vorhandene Schlüssel (CI mit leerer
  Datenbank). Gegen echte Daten prüft `scripts/pruefe_plaene.py`, dass jede
  Vorlage existiert und jede Berichtsreihe mindestens einen Treffer hat. Ist
  die Laufzeit ohne Nachfolger überschritten, erscheint ein Hinweis im
  Admin-Panel und kein Fehler.

## 5. Phasen

### Phase 0: Register und Entscheidungen (Woche 1, kein Modell)

- Fragen aus § 8 klären.
- `council/plans.py` mit den rund 25 belegten Plänen aus 1.2 (A, B, C und die
  wichtigsten aus E), ohne Maßnahmen.
- Wächter wie in § 4.
- **Lieferbar:** Register-PR, Liste der „offen“-Fälle mit Vorschlag, wie sie
  zu klären sind (Luftreinhalteplan, Wohnkonzept, RFP nach 2022,
  Innenstadtstrategie).
- **Kosten:** 0 $.

### Phase 1: Berichte und Planbeschlüsse zuordnen; erste Seite (Woche 2, kein Modell)

- `council_plan_reports` aus Titelmustern und Tagesordnungspunkten,
  mündliche Berichte eingeschlossen, gebaut im Schritt nach `track_goals` in
  `check_protocols.py`.
- `council_plan_links` mit den sicheren Wegen: Planvorlage samt Fassungen,
  Verweis über die Nummer, Maßnahmen-Kennung im Text.
- Endpunkte, Übersicht und Detailseite (Kopf, Laufzeit, Berichte,
  Beschlüsse), alles hinter `plaene`.
- **Lieferbar:** Die Seite steht auf dev, noch ohne Maßnahmen. Bild vor dem
  Merge.
- **Messziel:** Für den Aktionsplan Gewalt erscheinen alle 24
  Tagesordnungspunkte aus 2018–2026, für den KSP alle 15 Berichte.
- **Kosten:** 0 $.

### Phase 2: Maßnahmenlisten für fünf Pilotpläne (Woche 3–4)

Klimaschutzplan (Kurzübersicht, Anlage 255735, 2 Seiten), Wärmeplan (aus
`26/0236`), Aktionsplan Gewalt (Fassungen 2020 und 2026), Ernährungsstrategie
(Tabelle in `26/0431`) und Mobilitätsplan (rund 70 priorisierte Maßnahmen,
Anlage 275932).

- Wo der Text schon Tabellen trägt (Ernährungsstrategie, Wärmeplan), reicht
  ein Parser. Sonst schlägt ein Modell die Liste vor (Luna,
  `_tarif="flex"`, Batch mit `_geduld`), und ein Mensch prüft vollständig.
- **Lieferbar:** fünf geprüfte `council/plans/<key>.json` und der Block
  MASSNAHMEN auf der Detailseite.
- **Messziel:** Die Zahl der Maßnahmen stimmt mit der Zählung der Stadt
  überein (KSP 90 bzw. 97, Wärmeplan 18, Gewalt 87 und 30, Ernährung 68,
  Mobilitätsplan laut Anlage 1); für jede Maßnahme ist die Seite belegt.
- **Kosten (Schätzung):** rund 400 Seiten, etwa 300.000 Eingabe-Tokens, mit
  Luna ≈ 0,15 $, mit drei Stimmen ≈ 0,50 $. Eine Gegenprobe an zwei Plänen
  mit einem größeren Modell kostet ≈ 0,60 $.

### Phase 3: Status als Zeitreihe und Kennzahlen (Woche 4–5)

- Form a: Regex für den KSP-Zählblock über alle 15 Berichte. Daraus entsteht
  eine Zeitreihe samt Wechsel der Zählbasis.
- Form b: Parser für die Ernährungsstrategie (`26/0431`) und den Wärmeplan.
- Form c: Füllfarben aus Anhang 4.1 der Evaluation Gewalt mit PyMuPDF. Klappt
  das nicht, bleiben 87 Zeilen Handarbeit, eine Stunde.
- Form d: Modell je Maßnahme mit wörtlichem Beleg für den Mobilitätsplan
  (`23/0562`, `25/0041`, `26/0190`). Die Antwort „unklar“ ist erlaubt und kein
  Fehler.
- Kennzahl THG-Bilanz als Reihe aus `23/0653`, `25/0131` und `25/0866`,
  getrennt nach Soll und Ist.
- **Lieferbar:** Statuschips mit Verlauf, der Block KENNZAHL und die
  Statuszeile auf den Karten.
- **Messziel:** 100 % der Status aus den Formen a bis c stimmen mit der Quelle
  überein (Stichprobe von 30). Bei Form d wird höchstens 1 von 20 einer
  falschen Maßnahme zugeordnet.
- **Kosten (Schätzung):** rund 60 Berichte, etwa 250.000 Tokens, also
  ≈ 0,10–0,30 $.

### Phase 4: Beschlüsse den Maßnahmen zuordnen; der Stempel tritt ab (Woche 5–6)

- Kandidaten kommen über den Plannamen, die Kennungen, die Akte (Vorlagen
  einer Akte mit Planbezug) und die vorhandenen Embeddings. Das Modell urteilt
  über die Beziehung (*setzt Maßnahme um* | *ändert Plan* | *Antrag dazu* |
  *erwähnt* | *kein Bezug*) und die Maßnahme. Im Zweifel lautet das Urteil
  „erwähnt“.
- Vorab ein Golden-Set aus 40 von Hand bewerteten Paaren, die meisten aus
  Klima und Mobilität, darunter EEK-Erwähnungen in Bebauungsplänen als
  Fallen.
- Danach wird `track_goals` aus dem Cron genommen. Die Kosten des Features
  `goal_rating` vorher messen, damit die Ersparnis belegt ist.
- **Lieferbar:** der Block BESCHLÜSSE ZUM PLAN nach Beziehung und der
  Zuordnungsschritt im täglichen Cron.
- **Messziel:** Präzision für „setzt Maßnahme um“ ≥ 90 % im Golden-Set,
  „erwähnt“ landet nie in der Umsetzungsliste.
- **Kosten (Schätzung):** Erstlauf rund 1.500 Kandidaten in Stapeln zu 20,
  etwa 0,7 Mio. Tokens, ≈ 0,20–0,40 $; laufend wenige Cent pro Woche.

### Phase 5: Rückblick, restliche Pläne, iOS (Woche 6–7)

- Rückblick nach § 3.3 für den Schulentwicklungsplan 2018, den Aktionsplan
  Gewalt 2020–2025, das Integrationskonzept 2020–2025, step2025 und den KAI.
  Die Teile kommen aus Register, Status und Berichten. Ein Modell schreibt
  höchstens die Zusammenfassung der „Grenzen“, und zwar zitierend.
- Maßnahmenlisten für die übrigen Pläne aus A und B, soweit die Dokumente das
  hergeben.
- Die iOS-Ansicht „Pläne“ mit handgeschriebenen Modellen nach
  `ios/CLAUDE.md`, im nächsten App-Build. Danach steigt `APP_MIN_BUILD`, und
  die alten Ziel-Endpunkte können gehen.
- **Lieferbar:** Rückblick auf dev, iOS-Build in TestFlight und die
  Freigabe-Entscheidung für Prod (Schalter).
- **Kosten (Schätzung):** weitere ≈ 1–1,50 $ für rund 20 Pläne. Das liegt über
  1 $, also vorher fragen.

### Phase 4b: Offene Aufträge (Woche 6–7)

- **Aufträge erkennen:** angenommene Beschlüsse, deren Text die Verwaltung
  beauftragt (prüfen, berichten, vorlegen, erarbeiten, umsetzen). Erst Regeln
  über den Beschlusstext, ein Modell nur für die unklaren Fälle. Dazu die
  Zusagen der Verwaltung aus den Wortbeiträgen (`kind = pledge`) mit Datum.
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
- **Kosten (Schätzung):** rund 2.000 Auftrags-Kandidaten, Modell nur für
  unklare und Gegenproben ≈ 0,30–0,60 $; vorher mit `limit=20` messen.

### Phase 5b: Externe Quellen (Woche 7–8)

- **Klimaportal-Monitoring:** Stand je Maßnahme des Klimaschutzplans aus dem
  Portal der Stadt — vorher Nutzungsbedingungen und `robots.txt` prüfen,
  höflich abrufen (Regeln wie bei den Städten: ≥ 1 s, eigener User-Agent),
  Quelle sichtbar als „Klimaportal der Stadt, Stand …“.
- **Pläne vor 2018 von oldenburg.de:** die Planseiten der Stadt durchsehen,
  PDFs mit Datum und Herkunft ablegen, ins Register mit `source = "website"`.
  Ohne Ratsbeschluss im Bestand heißt der Kicker „VERÖFFENTLICHT 2014“, nicht
  „BESCHLOSSEN“.
- **Kosten:** Abruf und Text 0 $, Maßnahmenlisten wie Phase 2 ≈ 0,50 $.

### Phase 6: Pflege (laufend)

- Neue Berichte einer Reihe hängen sich im Cron selbst an.
- Hinweise im Admin-Panel bei „Fortschreibung fällig“ (Gleichstellungsplan
  31.12.2026, Abfallwirtschaftskonzept 2027, Kinder- und Jugendbeteiligung
  09/2029, Wärmeplan 2031) und bei Plänen ohne Bericht seit über zwei Jahren.
- Neue Pläne (KLAK, Integrationskonzept 2026, KSP-Fortschreibung) gehen
  per PR ins Register.
- „Frag den Rat“ kann das Register nutzen, um Fragen wie „Was ist aus dem
  Plan X geworden?“ zu beantworten (Anschluss an die Akte).

## 6. Kosten im Überblick

| Phase | Modell | geschätzt |
|---|---|---:|
| 0, 1 | keins | 0 $ |
| 2 Maßnahmen, 5 Pläne | Luna flex, Gegenprobe größer | ≈ 1 $ |
| 3 Status | Regex, Parser, Luna für Fließtext | ≈ 0,30 $ |
| 4 Zuordnung | Luna/DeepSeek, Golden-Set | ≈ 0,40 $ + laufend Cent |
| 4b offene Aufträge | Regeln, Luna für Unklares und Gegenprobe | ≈ 0,60 $ |
| 5 übrige Pläne, Rückblick | Luna | ≈ 1,50 $ |
| 5b externe Quellen | Abruf, Luna für Maßnahmen | ≈ 0,50 $ |
| **Summe Erstaufbau** | | **≈ 4–5 $** |

Die Modellkosten sind klein. Teuer ist das **Prüfen**: Maßnahmenlisten,
Golden-Sets und die „offen“-Fälle. Das übernimmt der Agent (Tims Entscheidung
09.11.2026) — mit Zählabgleich, Stichprobe und den Befunden im PR.

## 7. Risiken

- **Die Stadt ändert ihre Zählung** (KSP 90 → 97). Deshalb zeigen wir eine
  Zeitreihe mit dem Wortlaut der Stadt und keine eigene Quote.
- **Status nur als Farbe oder nur mündlich:** Lässt sich das nicht lesen,
  sagen wir „Stand nicht im Text“ statt zu raten.
- **Pläne vor 2018** (KAI 2015, Wohnkonzept 2025, step2025,
  Sportentwicklungsplan 2009) liegen außerhalb des Bestands. Ohne Nachladen
  bleiben sie Stammdaten ohne Maßnahmen.
- **Externe Quellen** wie das Klimaportal sind genauer als die
  Ratsberichte, aber eine neue Quelle mit eigener Pflege, und sie dürfen nicht
  wie Beschlüsse aussehen.
- **Politische Lesart:** Eine Liste „nicht umgesetzt“ kann wie eine Anklage
  wirken. Dagegen helfen die Regeln aus § 3.4 und Bild plus OK vor jedem
  UI-PR.
- **App:** Die neue Antwortform braucht einen Build. Bis dahin müssen beide
  Endpunkte gepflegt werden.

## 8. Was zu entscheiden ist

Stand 09.11.2026: Entschieden sind 1 (wie vorgeschlagen), 2 (ja, beides),
3 (ja zu einer eigenen, fairen Einordnung je Plan, § 3.3a), 5 (dev zuerst,
Prod mit dem nächsten Release, sobald fertig) und 6 (der Agent prüft). Für 4 gilt bis auf Widerruf: Die alte Bewertung („bringt voran /
bremst“ samt Stempel „überwiegend vorangebracht“, täglich per Modell aus
`track_goals`) läuft weiter, bis „Pläne“ auf Prod ist; dann hört der tägliche
Lauf auf, und die alten Endpunkte liefern den letzten Stand für die
ausgelieferte App, bis deren nächster Build „Pläne“ kennt. Offen bleibt 7; den klärt der Agent erst selbst (MCP, oldenburg.de) und fragt nur, was übrig
bleibt.

1. **Was zählt als Plan der Stadt?** Vorschlag: Klasse 1 sind Pläne mit
   Maßnahmen und Ratsbeschluss (A), Klasse 2 Rahmenstrategien (B), Klasse 3
   Pflicht- und Fachpläne (C). Ein Nahverkehrsplan des ZVBN und
   Steuerungskonzepte wie EEK oder Vergnügungsstättenkonzept laufen nur als
   Verweis mit.
2. **Externe Quellen:** Binden wir das Klimaportal-Monitoring ein? Laden wir
   Pläne von vor 2018 von oldenburg.de nach?
3. **Rückblick:** Einverstanden, dass Ratslotse den Erfolg nicht selbst
   bewertet und nur die Evaluation der Verwaltung, Soll und Ist sowie die
   genannten Grenzen zeigt? Sollen Anfragen und Anträge aus dem Rat zum Stand
   eines Plans im Rückblick erscheinen?
4. **Die sechs Ziele und der Stempel:** Schalten wir `track_goals` mit
   Phase 4 ab, oder läuft er bis zum App-Build weiter?
5. **Sichtbarkeit:** Auf Prod erst mit dem Rückblick (Phase 5) oder schon
   nach Phase 3?
6. **Prüfaufwand:** Prüft Tim die Maßnahmenlisten selbst, oder reicht eine
   Stichprobe durch den Agenten mit vollständigem Zählabgleich?
7. **Offene Fälle:** Kann Tim die Stände von Luftreinhalteplan, Wohnkonzept,
   Innenstadtstrategie und Rad- und Fußverkehrsprogramm nach 2022 aus eigener
   Kenntnis einordnen, bevor wir weiter suchen?

## Anhang: Messbefehle

```bash
# Planvorlagen nach Titel (Beispiel); Datenbank nur lesend
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
```

Anlagentexte fehlen im lokalen Abzug (`council_attachments.raw_text` ist leer).
Gelesen wurden sie über das MCP-Werkzeug `get_attachment`: 314635 (Evaluation
Gewalt), 275932 (Priorisierung Mobilitätsplan) und 293527 (Agenda 2025).
