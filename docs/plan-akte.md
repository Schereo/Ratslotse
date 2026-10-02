# Plan: Die Akte — Suche nach Vorgängen statt nach ähnlichem Text

Stand 02.10.2026. Anlass ist die Arbeit vom 30.09. bis 02.10.2026 an „Frag
den Rat“ und der Gründlichen Recherche (Ausgangsfall: Schlossplatz-Spielplatz,
ksinr 4664). In drei Tagen kamen zwölf Fixes zusammen (#1585–#1615). Jeder hat
gewirkt, und jeder hat dieselbe Lücke an einer anderen Stelle geflickt. Dieser
Plan beschreibt den Umbau, der die Lücke selbst schließt, und wie wir ihn
messen.

**Stand 02.10.2026, abends.** Tim hat Phase 0 und 1 freigegeben; beide sind
gebaut. Phase 0: 20 Gold-Fälle (#1621), Belegarten und Messskript (#1622),
Token-Reparatur des Gold-Laufs (#1624). Phase 1: Grundakten (#1623, auf dev).
Phase 2 (freigegeben am selben Tag): Entitäten über Grundakten, Erwähnungen,
`akte_von` (#1626, auf dev).
Die Ergebnisse stehen bei den Phasen; zwei Messziele waren falsch gesetzt und
sind korrigiert (Phase 1 und 2, mit Begründung).

## 1. Befund

### 1.1 Was eine Frage will

Fast jede Frage an „Frag den Rat“ betrifft einen **Vorgang**: das Stadion, den
Spielplatz, die Trinkwasserspender. Ein Vorgang ist eine Folge von Ereignissen
über Jahre: Antrag, Vorberatung, Ratsbeschluss, Bericht, Protokollnotiz,
Pressemitteilung. Eine gute Antwort braucht **alle Stationen dieses Vorgangs**
und **ihre Reihenfolge**, vor allem die letzte.

### 1.2 Wie die Pipeline sucht

Die Pipeline zerlegt die Frage in Suchbegriffe und sucht in jeder Quelle
getrennt nach **ähnlichem Text**: Beschlüsse (Vektor + BM25 + Cross-Encoder,
`QA_TOP_K = 40`), Wortbeiträge (8 Treffer plus Kopplung an die ersten acht
Beschlüsse), Pressemitteilungen (3 bzw. 5), Anlagen. Jede Quelle hat eigene
Ränge, Schwellen und Deckel. Ähnlichkeit sagt aber nicht, ob etwas zum
Vorgang gehört, und sie kennt keine Zeit.

### 1.3 Alle Fehler sind eine Lücke

| Befund (Gold-Fall) | Was fehlte | Flicken |
|---|---|---|
| Schlossplatz: Verwaltung vom 16.04.2026 fehlt | Zugehörigkeit: steht unter TOP „Spielleitplanung“, Vektor-Rang > 150 | Textkanal, „neueste zuerst“ (#1613) |
| Trinkwasser: Protokollnotiz fehlt | Zugehörigkeit: sagt „Trinkwasserbrunnen“, ihr Beschluss stand auf Platz 9 | Titel-Kopplung (#1612) |
| Stadion: Antwort endet im Juni statt August | Zeit: neueste PM verlor gegen ähnlichere ältere | Presse-Titelkanal, 5 statt 3 (#1613) |
| Stadion: Bürgschaft, B-Plan 831 fehlen | Zugehörigkeit: Titel klingen nicht nach „Stadion-Stand“ | — (offen) |
| 25× „Sachstandsbericht Stadionplanung“ | Identität: dieselbe Sache 25-mal statt einmal | Serien-Deckel (#1605, #1608) |
| „Ersatz beschädigter Mülltonnen“ vor „Trinkwasserspender“ | Ähnlichkeit ≠ Zugehörigkeit | Kopplung hinter Platz 8 (#1612) |
| „Trinkwasser**spender**“ → Spenden-Facette | Router sperrt Material | Ausnahmeliste (#1609) |

Jeder Flicken bringt Stellschrauben mit: 40, 8, 150, 700, 3/5, −1,5, −1,0,
50 Titel, 30 Beiträge, Serien-Deckel 3. Sie hängen voneinander ab und werden
einzeln gemessen.

### 1.4 Fünf grundlegende Probleme

1. **Es gibt keine Akte als Objekt.** Die Bausteine liegen vor, sind aber
   nicht verbunden (Zahlen in 1.5).
2. **Zeit ist kein Teil der Suche.** Die Reranker sind zeitblind; bei einer
   Stand-Frage *ist* die neueste Station die Antwort.
3. **Ein Klassifikator steuert alles, und seine Fehler sind still.** Die
   Frage-Analyse entscheidet in einem Aufruf über Fragetyp, Punktfrage,
   Facetten und Kanäle; jede Entscheidung sperrt etwas aus („Wie wurde
   entschieden?“ → Punktfrage → ein Satz; Fraktionsfrage ohne Fraktion → kein
   Material).
4. **Die Antwortstufe bekommt Kanäle statt einer Geschichte.** Sieben Blöcke
   mit eigenen Regeln; das Modell puzzelt den Verlauf selbst und lässt
   Material liegen (Stadion: alles im Kontext, die Hälfte genannt).
5. **Datenfehler fallen nur zufällig auf.** Verwaltungsantworten im falschen
   Feld, fehlende Protokollnotizen, „gilt als behandelt“ als angenommen,
   falsche Parteien an Wortbeiträgen, eine Kurzfassung, die eine hypothetische
   Grundsteuererhöhung als Tatsache führt (Wortbeitrag 46367) — alles durch
   Nutzerfragen oder Gold-Recherche entdeckt, nichts durch eine Prüfung.

### 1.5 Was die Daten schon hergeben (Prod-Abzug 01.10.2026)

| Baustein | Zahl | Taugt für |
|---|---:|---|
| Beschlüsse | 9.524 | |
| … mit Vorlagennummer | 7.032 (74 %) | Grundakte, sicher |
| Vorlagen mit mehreren Stationen | 1.600 (Ø 2,1) | Grundakte, sicher |
| Vorlagen, deren Text eine andere Vorlage nennt | 949 von 5.558 (17 %) | Verbinden, prüfbar |
| Beschlüsse ohne Vorlagennummer | 2.492 | meist Fraktionsanträge/Berichte — unscharf |
| Wortbeiträge mit TOP-Nummer | 52.598 von 52.804 | Kopplung über Sitzung + TOP, sicher |
| Beratungsfolge (`council_deliberations`) | 7.651 Stationen zu 5.558 Vorlagen | Stationen **vor** dem Protokoll (Art, kein Ergebnis) |
| Tagesordnungen (`council_agenda_items`) | alle 24 Sitzungen Jul–Sep 2026 | angekündigte Stationen |
| Sitzungen Jul–Sep 2026 mit Protokoll/Beschlusszeilen | 6 von 24 | Lücke: Beschlüsse entstehen erst aus dem Protokoll |
| Beschlüsse mit Themen-Entität | 42 % (2026: 46 %) | Projekt-Entitäten = große Akten, heute lückenhaft |
| Projekt-Entitäten zum Stadion | 5 („Stadion Oldenburg“, „Stadionneubau Maastrichter Straße“, „Stadion Maastrichter Straße“, „Stadionplanungsgesellschaft“, „Stadionplanung“) | Dubletten, über `council_entity_aliases` zusammenführbar |

Die Entitäten entstehen per Sprachmodell aus Titel und den ersten 300 Zeichen
eines Beschlusses (`council/entities.py`, `deepseek-v4-pro`), zählen erst ab
zwei Beobachtungen (`rebuild_entities_from_obs(min_n=2)`) und laufen **nur im
Wochenlauf** (`weekly_enrich.py`, sonntags). Ein neuer Beschluss steht bis zu
sieben Tage ohne Thema da.

## 2. Ziel

**Eine Akte ist alles, was zu einer Sache gehört, an einer Stelle und in
zeitlicher Reihenfolge.** „Frag den Rat“ findet per Ähnlichkeit nur noch den
**Einstieg** (welcher Vorgang ist gemeint?) und liest dann die **Akte**:
vollständig, chronologisch, die letzte Station zuletzt.

Kein neues sichtbares Konstrukt neben den Entitäten. Zwei Schichten:

1. **Grundakte (unsichtbar):** je Vorlage eine Gruppe aus allen Stationen
   (Beratungsfolge, Tagesordnung, Beschlüsse), den Wortbeiträgen und
   Protokollnotizen ihrer TOPs, der Vorlage selbst. Mechanisch, für jeden
   Beschluss.
2. **Projekt-Entität (sichtbar, wie heute):** verknüpft **Grundakten** statt
   einzelner Beschlüsse. Orte und Organisationen bleiben Querschnitte und
   verknüpfen ebenfalls Grundakten.

Die Themen-Seiten profitieren ohne eigenen Umbau: Sie zeigen dann den ganzen
Vorgang statt einer Beschlussliste.

## 3. Benchmarks

Gemessen wird **vor** jeder Phase (Grundlinie) und **nach** jeder Phase, mit
denselben Daten (eingefrorener Prod-Abzug bzw. Prod direkt) und mindestens
zwei Läufen, wo ein Sprachmodell beteiligt ist. Eine Phase geht nur weiter,
wenn ihr Tor (letzte Spalte) erreicht ist.

| # | Benchmark | Wie gemessen | Grundlinie | Ziel / Tor |
|---|---|---|---|---|
| B1 | **Gold „Frag den Rat“** | `ops-gold.yml weg=ask`, 20 Fälle, Richter Claude Opus 5.5, ≥ 3 Läufe; Abdeckung, bestanden, Verstöße | 7 Fälle: 49–55 %, 2–4/7 (01.10.) — mit 20 Fällen in Phase 0 neu | Phase 3: +10 Pp Abdeckung **und** ≥ 3 Fälle mehr bestanden, keine neuen Verstöße |
| B2 | **Gold Gründliche Recherche** | dieselben Fälle, `weg=deep` | 7 Fälle: ≈ 57–61 %, 3/7 — neu in Phase 0 | wie B1 |
| B3 | **Material vorhanden** (Suche) | aus B1/B2: Anteil der Gold-Material-Einträge im Kontext der Antwort; getrennt von „Fakt genannt“ | neu in Phase 0 | Phase 3: ≥ 90 % |
| B4 | **Akten-Abdeckung** (ohne LLM) | `eval/run_akten.py`: Liegt jedes Gold-Material in der Akte des Kernbeschlusses? Deterministisch, Sekunden; Personen-/Sitzungsfälle zählen nicht; auch **ohne Presse** und mit **Aktengröße** | Entitäten heute: 61,8 %, ohne Presse 77,9 %, Ø 37 Beschlüsse je Akte (02.10.) | Phase 1: ≥ Vorlagennummer allein, alle Beschlüsse in einer Akte; Phase 2: ≥ 90 % ohne Presse, ≥ 85 % gesamt |
| B5 | **Retrieval ki-frage** | `eval/run_qa.py --nur-retrieval`, 22 handgelabelte Fragen inkl. Stadion | hit@8 18/23, recall@8 0,545, MRR 0,523 (lokal, 01.10.) | keine Verschlechterung über die Streuung hinaus (Stadion-Regel) |
| B6 | **Fakten-Eval** | `eval/run_fakten.py`, 233 Fälle (Lotti + Rat) | Stand #1504 | keine Zunahme falscher/erfundener Aussagen |
| B7 | **Zuordnungsqualität** | Handstichprobe je 100 Zuordnungen der unscharfen Stufe: Präzision (gehört dazu?) und Vollständigkeit (fehlt etwas?), Negativliste der Namensvettern (Stadion Marschweg, DB-Huntebrücke, Sechsfeldhalle …) | — | Präzision ≥ 95 %, Namensvettern 0 Fehlgriffe |
| B8 | **Latenz und Kosten** | `timings` aus /ask (p50/p95 bis zum ersten Wort, Gesamt), Kontext-Tokens und Kosten je Antwort aus `llm_usage` | heute messen in Phase 0 | p50 bis zum ersten Wort + ≤ 1 s, Kosten je Antwort ≤ +30 % |
| B9 | **Datenregeln** | täglicher Check (Phase 6): jede Station in genau einer Grundakte, Wortbeitrag in derselben Akte wie sein Beschluss, Waisenquote, Akten-Wachstum | — | 0 Verstöße; Alarm per Mail |

**Kosten der Messung.** Ein Gold-Lauf mit 20 Fällen auf beiden Wegen kostet
rund 1,10 $ für den Richter plus die Antworten (Luna, Cent-Bereich) — etwa
1,50 $ je Lauf, 4,50 $ für drei. Je Phase zwei solcher Messungen (vorher,
nachher): rund 9 $ je Phase, gut 40 $ über den ganzen Umbau. B4, B5 und B9
kosten nichts.

**Streuung.** Die Grundlinie vom 01.10. schwankte bei gleichem Richter um
6 Pp (49 vs. 55 %), einzelne Fälle um 30 Pp. Deshalb drei Läufe und Tore
erst jenseits von 10 Pp.

## 4. Phasen

Jede Phase ist eine Folge kleiner PRs, Squash-Merge, Vorgaben aus
`CLAUDE.md`. Sichtbare Änderungen hinter dem Schalter `akten-suche`
(`kern/features.py`), auf dev an, auf Prod erst nach bestandenem Tor.

### Phase 0 — Messbasis (keine Produktänderung)

| PR | Inhalt |
|---|---|
| 0.1 | **20 Gold-Fälle** nach `eval/cases_deep_gold.json` (7 überarbeitet, 13 neu, recherchiert am 02.10. gegen den Prod-Abzug). `tests/test_gold_faelle.py`: die Bewertungsprobe bekommt ein eigenes Mini-Fixture (sie hing an den Gewichten des Trinkwasser-Falls). |
| 0.2 | **Material-Arten erweitern**: `vorlage` und `beratung` (Tagesordnung/Beratungsfolge) in `_material_pruefen` und `eval_ask_gold.material_form`. Ohne sie lassen sich Belege, die nur in Vorlagen oder angekündigten TOPs stehen, nicht prüfen (drei Fakten der neuen Fälle). |
| 0.3 | **`eval/run_akten.py`** (B4): je Gold-Fall die erwartete Akte aus den Material-Einträgen; Abdeckung heute über Entitäten und Vorlagennummern. |
| 0.4 | **Grundlinie** B1–B8: drei Gold-Läufe auf Prod (beide Wege), `run_qa.py`, `run_fakten.py`, Latenz/Kosten. Ergebnis in diesen Plan. |
| 0.5 | **Offene Datenfrage klären:** Trägt das Ratsinformationssystem das Ergebnis einer Station vor dem Protokoll? `council/ergebnisse.py` sagt am 26.07.2026 nein, der Gold-Agent sah am 02.10. auf Sitzungsseiten „ungeändert beschlossen“. Wenn ja: eigener Ernte-Schritt, eigener PR (er verkürzt die Protokoll-Lücke von Wochen auf Tage). |

Tor: Grundlinie steht, B3 und B4 sind messbar.

**Ergebnis (02.10.2026).**
- **0.5 geklärt:** Das Ratsinformationssystem zeigt Ergebnisse je TOP erst
  zusammen mit dem Protokoll (Rat 28.09.: weder Protokoll noch Ergebnis;
  Finanzausschuss 02.09.: beides). Die drei ältesten Sitzungen ohne Protokoll
  bei uns haben auch dort keins — die Lücke ist der Verzug der Stadt (vier bis
  sieben Wochen), kein Ernte-Fehler. Folge für die Akte: Tagesordnung und
  Beratungsfolge gehören hinein, als „beraten, Ergebnis noch nicht
  protokolliert“.
- **B4-Grundlinie** (18 Vorgangsfälle, 165 Belege; Personen- und
  Sitzungsfall ausgenommen):

  | Methode | gesamt | ohne Presse | Ø Akte |
  |---|---|---|---|
  | Vorlagennummer | 43,0 % | 54,2 % | 3,7 Beschlüsse |
  | Entitäten heute | 61,8 % | 77,9 % | 37,4 Beschlüsse |

  Pressemitteilungen (34 der 165 Belege) hängen an keiner Akte.
- **B1/B2-Grundlinie** (Prod, 02.10., drei Läufe, Richter Opus 5.5):

  | Weg | Abdeckung je Lauf | Mittel | bestanden | Fälle mit Verstoß |
  |---|---|---|---|---|
  | Frag den Rat (B1) | 39 · 38 · 40 % | **39 %** | 5 · 3 · 4 | 1 · 1 · 1 |
  | Gründliche Recherche (B2) | 55,5 · 50,7 · 55,3 % | **53,8 %** | 9 · 5 · 8 | — · 1 · 2 |

  Lokal ohne Akte (Prod-Abzug ohne Embeddings) kam „Frag den Rat“ auf
  38 % — der lokale Messaufbau trifft Prod also gut genug für Vergleiche
  innerhalb einer Phase.

### Phase 1 — Grundakte (Datenschicht, unsichtbar)

**Schema** (Schema *und* Migration, `council/CLAUDE.md`):

```
council_matters        (id, key, kind, title, first_date, last_date, built_at)
                        key  = normalisierte Vorlagennummer ("26/0396")
                               bzw. Antragsschlüssel (s. u.)
                        kind = 'template' | 'motion' | 'single'
council_matter_items   (matter_id, item_type, item_id, source, confidence)
                        item_type = decision | deliberation | agenda_item |
                                    template | speech | press
                        source    = template_number | reference | top |
                                    motion_key | title | model
council_matter_edges   (matter_a, matter_b, source, confidence)
                        -- Vorlagen-Verweise, nicht zusammengelegt
```

**Aufbau** (`council/matters.py`, ohne LLM):

1. **Vorlagenkette:** gleiche Vorlagennummer inkl. `/1`, `/2` → eine
   Grundakte; dazu Beratungsfolge, Tagesordnungspunkte und Vorlagen-Volltext
   mit derselben Nummer bzw. `kvonr`.
2. **Wortbeiträge und Protokollnotizen:** über (ksinr, TOP-Nummer) an den
   Beschluss ihres TOPs → dessen Grundakte. Das ist die heutige Logik aus
   `wortbeitraege_zu_beschluessen`, einmal beim Einlesen statt je Frage und
   ohne Deckel.
3. **Anträge ohne Vorlagennummer:** Schlüssel aus Antragsteller und
   Antragsdatum, wie es im Titel steht („(SPD-Fraktion vom 17.03.2026)“).
   Antrag und „– Bericht“ / „– Antrag mit Bericht“ landen so in derselben
   Grundakte. Rest: `single`.
4. **Verweise** zwischen Vorlagen (17 %) werden als **Kanten** gespeichert,
   nicht zusammengelegt. Ein „vgl. 22/1006“ kann Fortsetzung oder bloßer
   Seitenblick sein; zusammengelegt wird erst in Phase 2 über die
   Projekt-Entität.

**Betrieb:**
- Inkrementell in `check_protocols.py` und `check_council.py` (neue Stationen,
  Tagesordnungen, Wortbeiträge), Presse in `check_presse.py`.
- Vollständiger Neuaufbau im Wochenlauf als Rückhalt; idempotent, bricht
  über `kern/stopp.py` beim Deploy ab, schreibt stapelweise.
- Die Grundakte ist **abgeleitet**: jederzeit aus den Rohdaten neu
  berechenbar, kein Handpflege-Zustand.

**Tests:** jede Station in genau einer Grundakte; Wortbeitrag und Beschluss in
derselben; Migration gegen die eingecheckten Schema-Auszüge
(`test_migration_bestand.py`); Neuaufbau zweimal hintereinander ergibt
dasselbe.

Tor (korrigiert): jeder Beschluss in genau einer Grundakte, Neuaufbau
stabil und < 5 min, B4 mindestens so gut wie die Vorlagennummer allein.
Ursprünglich stand hier „B4 ≥ 80 %“ — das war falsch gedacht: Die Grundakte
ist per Bauart EINE Vorlage, ein Vorgang wie das Stadion besteht aus vielen.
Verklebt werden sie in Phase 2; an der Grundakte allein ist 80 % nicht zu
erreichen, ohne ihren Zweck aufzugeben.

**Ergebnis (02.10.2026, #1623, Prod-Abzug 01.10.):**
- 7.822 Akten, 80.243 Einträge, 1.837 Kanten; **1,0 s** je Vollaufbau, Neuaufbau
  identisch, ids stabil. Läuft jede Nacht in `check_protocols.py`; auf dev
  (ohne Crons) per `scripts/build_matters.py`.
- **Alle 9.524 Beschlüsse** in genau einer Akte: 7.032 über die
  Vorlagennummer, 1.629 über den Titelkern, 850 Teilabstimmungen über ihren
  TOP, 13 einzeln. 41.195 von 52.804 Wortbeiträgen (der Rest steht in
  Sammel-TOPs).
- B4: **55,7 % ohne Presse** bei Ø 5,3 Beschlüssen (Vorlagennummer 54,2 %).
- Tor erreicht.

### Phase 2 — Entitäten auf Grundakten

1. **Verknüpfung erben:** Ist eine Entität mit einem Beschluss verknüpft,
   gilt sie für dessen ganze Grundakte. Eine neue Station einer bekannten
   Vorlage hat ihr Thema damit **sofort**, nicht erst nach dem Wochenlauf.
   (`council_entity_links` bleibt die gespeicherte Beobachtung; die
   Grundakten-Zugehörigkeit wird daraus abgeleitet.)
2. **Dubletten zusammenführen** über `council_entity_aliases` (Stadion: fünf
   → eins). Vorschläge aus dem vorhandenen `entity_duplicates`-Prompt, Freigabe
   im Admin-Panel. Alte Adressen bleiben gültig (Alias-Weiterleitung).
3. **Presse an Entitäten und Grundakten:** über Titelwörter (Bindestriche
   egal, wie `qa.press_title_ids`), Entitätsnamen und die vorhandenen
   Ortsbezüge (`council_press_places`). Unscharf → `source='title'`,
   `confidence`.
4. **Unscharfe Zuordnung** für den Rest (Anträge ohne Schlüssel, neue Vorlage
   zu altem Vorgang): Kandidaten aus Entitäten und Kanten, ein günstiges
   Modell wählt aus wenigen Kandidaten, nie frei. Jede Zuordnung trägt
   `source` und `confidence`; Handkorrekturen überleben den Neuaufbau.

**Vorab gemessen (02.10.2026)** — welcher Klebstoff trägt? (B4, gleiche Fälle)

| Klebstoff | gesamt | ohne Presse | Ø Akte |
|---|---|---|---|
| Grundakte + ein Schritt über Verweise | 49,7 % | 62,6 % | 9,4 Beschlüsse |
| nur Projekt-Entitäten über Grundakten | 45,5 % | 57,3 % | 10,7 |
| Projekte + Organisationen über Grundakten | 55,2 % | 69,5 % | 19,1 |
| alle Entitäten über Grundakten | 65,5 % | 82,4 % | 49,8 |
| **alle Entitäten über Grundakten + Erwähnungen** | **83,0 %** | **90,1 %** | 49,8 (+ 348 Beiträge, 24 PM) |

„Erwähnungen“: Wortbeiträge und Pressemitteilungen, die den Namen einer
Entität des Vorgangs nennen. Das ist die Verallgemeinerung des Textkanals aus
#1613 — und der einzige Weg, auf dem die Aussage der Verwaltung zum
Schlossplatz (sie steht unter TOP „Spielleitplanung“, einem anderen Vorgang)
in die Akte kommt. Zwei Folgerungen:
- **Der Gewinn kommt von Orten und Organisationen**, nicht von Projekten.
  Projekt-Entitäten verknüpfen die Kernbeschlüsse der Gold-Fälle zu selten —
  ihre Extraktion (Titel + 300 Zeichen, ab zwei Beobachtungen, nur sonntags)
  ist die eigentliche Schwachstelle.
- **Die Akten werden groß.** Phase 3 muss innerhalb einer Akte auswählen und
  von alt nach neu verdichten; alles in den Kontext zu legen geht nicht.

Tor (korrigiert): B4 ≥ 90 % ohne Presse und ≥ 85 % gesamt, mittlere Akte
höchstens so groß wie mit allen Entitäten heute (≈ 50 Beschlüsse), B7
Präzision ≥ 95 % und keine Namensvettern-Fehlgriffe,
Entitäts-Abdeckung der Beschlüsse von 42 % auf ≥ 70 %, keine kaputte
Themen-Adresse (Test über alle Slugs und Aliase).

**Ergebnis (02.10.2026, #1626).** Gebaut: `council_entity_matters`,
`council_entity_mentions`, `matters.akte_von` — nur Daten, nichts sichtbar.
Fünf Regeln, jede an einer Handstichprobe (B7) gefunden:
Gremien sind kein Thema; Haushalts- und Stellenplan-Akten vererben nicht (die
Haushaltsvorlage bündelt Eigenbetriebe und Stiftungen); Orte mit mehr als 60
Beschlüssen verkleben nicht; Mehrwortnamen brauchen hinten eine Wortgrenze;
Orte zählen in Pressemitteilungen nur im Titel.

| Tor | gemessen | erreicht |
|---|---|---|
| B4 ≥ 90 % ohne Presse | **90,8 %** | ja |
| B4 ≥ 85 % gesamt | **86,7 %** (Presse 24/34) | ja |
| mittlere Akte ≤ ≈ 50 Beschlüsse | **28,4** (5 PM) | ja |
| B7 Präzision ≥ 95 % | **96/100** (Vererbung 29/30, Beiträge 39/40, Presse 28/30; erste Stichprobe vor den Regeln: Vererbung 18/30) | ja |
| Namensvettern 0 | 0 | ja |
| Beschlüsse mit Thema ≥ 70 % | **48 %** (vorher 42 %) | **nein** |
| keine kaputte Themen-Adresse | keine Slugs geändert | ja |

Das verfehlte Tor liegt nicht an der Vererbung: Die Themen-Extraktion
(Titel + 300 Zeichen, ab zwei Beobachtungen, nur sonntags) erkennt bei 54 %
der Hauptbeschlüsse gar kein Thema, und die verbliebenen B7-Fehler sind
falsch verknüpfte Beschlüsse aus derselben Extraktion. Für die Akte reicht es
(B4 erreicht); für die Themen-Seiten wäre eine bessere Extraktion ein eigener
Schritt. Dubletten mussten nicht zusammengeführt werden — die fünf
Stadion-Einträge sind teils verschiedene Dinge (Gesellschaft ≠ Bauprojekt).

### Phase 3 — Suche über Akten (Schalter `akten-suche`)

1. **Einstieg:** die heutige Suche (hybrid + Rerank) und `finde_entitaeten`
   liefern Kandidaten; daraus die **Akten** (Projekt-Entität, sonst
   Grundakte), bewertet nach ihrem besten Treffer und Entitäts-Treffer in der
   Frage. Höchstens drei Akten.
2. **Akte lesen:** alle Stationen chronologisch. Lange Akten werden von alt
   nach neu verdichtet, nie von neu nach alt: die letzten zwölf Monate
   vollständig, davor nur Beschlüsse mit Ergebnis. Angekündigte, noch nicht
   protokollierte Stationen kommen als „steht am … auf der Tagesordnung“.
3. **Rückfall:** Findet die Frage keine Akte (allgemeine Fragen, „Was hat der
   Rat 2025 zum Klima beschlossen?“), läuft der heutige Weg.
4. **Router entschärfen:** Fragetyp und Punktfrage bestimmen nur noch Form
   und Länge, sperren kein Material mehr (Problem 3). Facetten (Geld) bleiben
   Zusatz.
5. Gründliche Recherche (`deepresearch.py`) nutzt denselben Einstieg.

Tor: B1/B2 +10 Pp und ≥ 3 Fälle mehr bestanden, B3 ≥ 90 %, B5 ohne
Verschlechterung, B6 ohne Zunahme, B8 im Budget. Dann Schalter auf Prod.

**Ergebnis (02.10.2026, #1628, Nachtrag #1630).** Gebaut anders als oben
skizziert, weil die Messung es so wollte: keine „höchstens drei Akten“ und
keine Verdichtung nach zwölf Monaten, sondern eine Auswahl **aus** der Akte
der fünf besten Treffer (`council/akte_suche.py`) — bis zu 12 neueste
Hauptbeschlüsse (Ortsfilter gilt), 30 Wortbeiträge nach Vektor-Nähe zur
Frage, die 4 neuesten Aussagen der Verwaltung, 5 neueste Pressemitteilungen,
6 angekündigte Stationen. Der Cross-Encoder für die Beiträge kostete 9–11 s
und flog raus (Vektor allein: 17 ms). Ausgenommen sind Sitzungsfragen und
Fragen, die eine Ratsperson nennen (#1630).

Lokal gemessen (Prod-Abzug 01.10., 20 Fälle, Richter Opus 5.5):

| Stand | Läufe | Abdeckung | bestanden | B3 Material |
|---|---|---|---|---|
| Schalter aus | 2 | 38,2 / 38,3 % | 3 / 2 | 51,6 % |
| Einstieg 3, 20 Beiträge | 2 | 43,1 / 41,6 % | 4 / 5 | 65,8 / 67,4 % |
| **Einstieg 5, 30 Beiträge** | 1 | **42,9 %** | **5** | **69,5 %** |

| Tor | gemessen | erreicht |
|---|---|---|
| B1 +10 Pp, ≥ 3 Fälle mehr | +4,6 Pp, +2,5 Fälle | **nein** |
| B3 ≥ 90 % | 69,5 % | **nein** |
| B5 | Hybrid-Suche unverändert — die Akte setzt erst danach an | ja (bauartbedingt) |
| B6 | siehe Phase 4 | ja |

Das Material kam an, die Antwort nutzte es nicht: Ein Fakt, dessen Beleg im
Kontext stand, wurde mit Akte **seltener** genannt (46 % statt 50 %) — mehr
Stoff, gleicher Prompt. Genau das ist Phase 4. Tims Entscheidung: trotzdem
nach dev. Von den 65 fehlenden Belegen lagen 24 in der Akte und wurden nicht
gewählt, 14 kamen über einen falschen Einstieg nicht an, 27 liegen gar nicht
in der Akte des Kernbeschlusses.

### Phase 4 — Antwort aus der Zeitleiste

1. **Ein Kontextblock „AKTE“** statt sieben: datierte Zeilen mit Marke
   (Beschluss · Ergebnis · Stimmen | Bericht | Zusage der Verwaltung |
   Wortbeitrag | Pressemitteilung | angekündigt), Belegnummer je Zeile.
2. **Prompt vereinfachen:** Die Regeln für Debatten-Absatz, Presse-Stand und
   „neueste zuerst“ entfallen, weil die Zeitleiste sie trägt. Bleiben:
   Ergebnis-Treue (abgelehnt ≠ beschlossen), Kürze bei Punktfragen, Belege.
3. **Selbstprüfung ohne Zusatzaufruf:** Die Antwort muss die letzte Station
   der Akte nennen. Fehlt sie, hängt der Server einen Hinweis „Zuletzt: …“
   an — deterministisch, kein zweites Modell.

Tor: B1 „Fakt genannt, wenn Material vorhanden“ + 10 Pp gegenüber Phase 3,
B6 ohne Zunahme.

**Ergebnis (02.10.2026, #1629).** Gebaut wie skizziert, aber als
**zusätzlicher** Block: Was in der Akte steht, fliegt aus den übrigen
Blöcken; die alten Regeln bleiben bis Phase 5. „Zuletzt:“ greift, wenn die
Antwort die jüngste Station weder per Belegnummer noch per Monat oder Datum
nennt.

Dazu ein Fund aus der ersten Probe: Eine Vorlage **ohne Protokoll** hat
keinen Beschluss und damit kein Thema — ihre angekündigten Stationen
erreichten keine Akte (Klinikum: Ausfallbürgschaft 13,5 Mio. €, Rat
28.09.2026). Akten ohne Beschluss hängen jetzt über den Titel ihrer Vorlage
an der Entität (187 Verknüpfungen; über alle Vorlagen wären es 740 gewesen,
„Innenstadt“ allein an 42). B4 unverändert.

| Stand | Läufe | Abdeckung | bestanden | Fakt genannt, wenn Material da |
|---|---|---|---|---|
| Schalter aus | 2 | 38,2 / 38,3 % | 3 / 2 | 49,5 / 51,4 % |
| Phase 3 | 3 | 43,1 / 41,6 / 42,9 % | 4 / 5 / 5 | 48,9 / 44,1 / 46,4 % |
| **Phase 3 + 4** | 2 | **48,9 / 48,4 %** | **6 / 7** | **55,7 / 54,3 %** |

| Tor | gemessen | erreicht |
|---|---|---|
| B1 „Fakt genannt“ +10 Pp gegenüber Phase 3 | +8,6 Pp | **knapp nein** |
| B6 ohne Zunahme | 112 Fälle über „Frag den Rat“: falsch 3 → 2, erfunden 0 → 0, in Ordnung 66 → 67 | ja |
| B8 erstes Wort p50 + ≤ 1 s | 15,6 → 14,1 s (p95 22,0 → 23,2 s) | ja |

Phase 3 und 4 **zusammen** erreichen das Tor von Phase 3 gegenüber „aus“:
Abdeckung +10,4 Pp, bestanden +4. Die großen Gewinne: Mobilitätsplan
0,38 → 0,85, Zweckentfremdungssatzung 0,47 → 0,68, Dreifeldhalle
0,57 → 0,78, Grundsteuer 0,19 → 0,38. Lokal fehlen die Embeddings (die Suche
fällt auf Stichworte zurück) — vor dem Schalter auf Prod gehört dieselbe
Messung auf Prod bzw. dev (`ops-gold.yml`).

Bemerkenswert und nicht Teil des Umbaus: Das erste Wort kommt lokal erst nach
rund 15 s, die ganze Antwort nach 17 s — der Strom liefert fast alles am
Stück.

### Phase 5 — Aufräumen

Die Flicken aus 1.3 kommen raus, sobald Phase 3 und 4 sie nachweislich
ersetzen: `title_match_decisions`, `speech_text_ids`, `press_title_ids`,
Kopplung bis Platz 8, Serien-Deckel, „neueste zuerst“, die Kanal-Deckel.
Jeder Ausbau einzeln, jeweils mit B1/B5 gegengeprüft. Danach Schalter
`akten-suche` entfernen (`fertig_wenn` in `kern/features.py`).

**Erster Versuch (02.10.2026, nicht gemergt).** Alle Flicken zugleich hinter
einem Schalter `akten-ohne-flicken` (Titel- und Textkanal, Kopplung bis
Platz 8 und zu titelgleichen Beschlüssen, „neueste zuerst“), gemessen lokal
mit allen Vektoren (Beschlüsse, Vorlagen-Abschnitte, Presse, Beiträge), je
zwei Läufe:

| Arm | Abdeckung | bestanden | Material im Kontext |
|---|---|---|---|
| ohne Akte | 38 / 37 % | 3 / 3 | 55,8 % |
| Akte (Phase 3+4) | 50 / 47 % | 6 / 5 | **75,2 %** |
| Akte ohne Flicken | 46 / 47 % | 4 / 5 | 68,6 % |

**Die Flicken sind noch nicht ersetzt.** Sie holen Belege, die in keiner
Akte-Auswahl landen: Trinkwasserspender (Material 100 → 50 %, der Titelkanal
wurde genau dafür gebaut), Schlossplatz-Spielplatz (82 → 45 %),
Zweckentfremdungssatzung, Cäcilienbrücke. Sie bleiben, bis die Auswahl in
der Akte das selbst leistet; dann einzeln statt als Gruppe.

Nebenbei bestätigt: Phase 3+4 hält auch mit allen Vektoren (+11 Pp,
+2,5 Fälle); die Vektoren von Vorlagen und Presse heben das Material im
Kontext von 69,5 auf 75,2 %.

### Phase 6 — Stehende Datenprüfungen

Ein täglicher Check (eigener Job in `kern/jobs.py` oder Teil von
`check_herzschlag.py`), Mail bei Abweichung:
- B9-Regeln der Akten;
- Anteil der Verwaltungsbeiträge je Monat (der Ausgangsfehler vom 30.09.);
- Wortbeiträge ohne oder mit widersprüchlicher Partei je Monat;
- Beschlüsse, deren `outcome` dem `raw_result` widerspricht;
- Protokoll-Verzug je Gremium (heute 18 von 24 Sitzungen Jul–Sep ohne
  Protokoll — normal oder Ernte-Fehler?);
- Kurzfassungen, die einen nicht gefassten Beschluss als gefasst nennen
  (`outcome_note.states_outcome`).

**Ergebnis (02.10.2026, #1631).** Teil des Herzschlags, kein eigener Cron
(der bräuchte einen crontab-Eintrag auf dem Server). Regeln in
`council/datenpruefung.py`, Doku unter *Betrieb → Der Herzschlag*. Zwei
Sorten: **Bestandsregeln** stehen auf null und melden, solange ein Verstoß
steht; **Stromregeln** schauen nur auf das, was seit dem letzten Herzschlag
neu ist (sonst jeden Tag dieselbe Mail).

Gegenüber der Liste oben zwei Änderungen, beide aus dem Bestand:
- Statt „Anteil der Verwaltungsbeiträge je Monat“ die genaue Spur des
  Ausgangsfehlers: **Ratsbeitrag mit Antwort im eigenen Feld** (0 von 52.804
  nach der Neuextraktion). Der Monatsanteil schwankt mit der Zahl der
  Sitzungen (Januar 0 %, sonst 3–7 %) und hätte grundlos gemeldet.
- „Ohne Partei“ fällt weg: Die Verwaltung hat keine Partei, und die Partei
  wird erst beim Lesen aufgelöst (`qa.parteien_aufloesen`). Gemeldet wird nur
  **eine Person mit zwei Parteien in einer Sitzung**, Schreibweisen gefaltet
  (24 im Bestand, 3 in 2026 — etwa Behrens als SPD und Grüne am 29.06.).

Erster Lauf gegen den Prod-Abzug: **8 Kurzfassungen** aus Juni-Sitzungen
nennen einen abgesetzten, vertagten oder abgelehnten Punkt nicht als solchen
(21047, Bau-Turbo, mit 46 Gegenstimmen abgelehnt: „Änderung des
Grundsatzbeschlusses … um Einzelfallprüfungen auch auf Gewerbeflächen zu
ermöglichen.“), **2 Sitzungen** ohne Protokoll nach über zehn Wochen
(Finanzausschuss 06.05., Abfallwirtschaftsbetrieb 25.06.). Zwei weitere
Treffer waren Fehlalarme der Probe selbst („Vertagung“ statt „vertagt“) —
die Wortliste ist ergänzt.

### Nach Phase 6: Antwortstufe, Auswahl, Gründliche Recherche (02.10.2026)

**Messaufbau ohne Opus-Kosten.** Ab hier richtet Claude in der Sitzung selbst,
**blind**: je Fall Frage und Pflichtfakten einmal, darunter die Antworten der
Arme in zufälliger Reihenfolge ohne Kennzeichnung (Zuordnung in einer Datei,
die erst beim Auswerten gelesen wird). Die Antworten schreibt weiter GPT-6
Luna — gemessen werden soll das Produkt. 60 Antworten kosten rund 0,20 $. Zur
Einordnung: Derselbe Stand bekam von Opus 48,5 %, von Claude 50,9 %.

**Antwortstufe — kein Hebel.** Je ein Lauf, 20 Fälle:

| Arm | Abdeckung | bestanden | Fakt genannt, wenn Beleg da |
|---|---|---|---|
| heute | 50,9 % | 6 | 55,3 % |
| feste Gliederung (Stand → Weg mit Stimmen und Beträgen → Positionen → Offenes), ohne 2–5-Sätze-Grenze | 51,5 % | 6 | 59,6 % |
| Denkaufwand `high` | 51,8 % | 6 | 57,9 % |

Unter einem Punkt — die Antwort lässt Stimmen, Beträge und Bauzeitpläne
weg, egal wie man fragt. Nicht übernommen.

**„Zuletzt“ und Zeitleiste aus den zitierten Beschlüssen (#1633).** Dieselbe
Runde zeigte: Jede sechste Antwort bekam einen sachfremden „Zuletzt“-Satz
(Stadionsingen, Mülltonnen, Sportanlage Ofenerdiek), dieselben Stationen
standen in der Zeitleiste. Ursache war die Akte des Sucheinstiegs. Jetzt:
Grundakten der zitierten Beschlüsse ganz, Geklebtes und Presse nur mit einem
Sachwort der Frage im Titel; kein „Zuletzt“, wenn die Antwort schon einen
späteren Monat nennt.

**Auswahl aus der Akte (#1634).** Neu: `eval/run_akten.py --methode auswahl`
misst ohne Sprachmodell, was die Auswahl an die Antwort weitergibt.
Akte 86,7 % → Auswahl 12/30/5 nur 66,7 % (Wortbeiträge 29 von 50 in der
Akte); 16/50/8 gibt 77,0 % weiter. Rangfolge statt Menge half kaum, Presse
nach Vektor-Nähe war schlechter als nach Datum. Am Ende der Kette (neun
betroffene Fälle, blind): 51,7 → 56,1 %, keine Verstöße.

**Gründliche Recherche mit Akte — der größere Hebel.** Dieselben 20 Fälle,
Bericht mit und ohne Akten-Material (Schalter `akten-suche` und
`akten-zeitleiste`), je ein Lauf, blind gerichtet. Kosten beider Arme
zusammen 0,17 $.

| Arm | Abdeckung | bestanden | Verstöße | Fakt genannt, wenn Beleg da |
|---|---|---|---|---|
| ohne Akte | 56,9 % | 10 | 0 | 78 von 111 = 70,3 % |
| mit Akte | **63,7 %** | **11** | 0 | 101 von 138 = 73,2 % |

Je Fall: zehnmal besser, zweimal schlechter, achtmal gleich. Der Gewinn
kommt fast ganz aus dem Material — 138 statt 111 der 208 Pflichtfakten haben
einen Beleg —, die Berichte werden kaum länger (Median 527 → 549 Wörter,
30 → 34 s). Am deutlichsten: Stadion-Stand 45 → 75 % (Vertrag, EU- und
Aufsichts-Freigabe, Bebauungsplan), Grundschule Wechloy 50 → 77 %,
Zweckentfremdungssatzung 65 → 85 %, Heidbrook 33 → 50 %. Die beiden
Verluste (Schlossplatz, Fliegerhorst) sind je ein einzelner Fakt.

Zur Einordnung, alles mit Claude als Richter: Frag den Rat steht mit Akte
bei rund 51–56 %, die Gründliche Recherche mit Akte bei 63,7 %. Der Abstand
zwischen den beiden bleibt — die Akte hebt beide.

**Eckdaten unter der Antwort (#1635).** Weil das Modell Stimmen, Beträge und
Termine weglässt, zeigt der Server sie selbst, aus den Daten: der jüngste
zitierte Beschluss mit Abstimmung, sein Betrag („größter Betrag im
Beschlusstext“), was danach kam und was als Nächstes ansteht
(`akte_suche.key_facts`, Feld `key_facts`). Nur Titel mit einem Sachwort der
Frage — sonst führte das Schwimmbad BTB die Trinkwasser-Frage an —, Routine
(Jahresabschluss, Wirtschaftsplan, Entlastung) hintan. Über die 20
Gold-Antworten bekommen 16 eine Karte, alle zur Sache. Unter der Antwort,
nicht darüber: Sie braucht die Zitate und käme sonst als Sprung über dem Text.

## 5. Risiken

| Risiko | Gegenmittel |
|---|---|
| Falsches Zusammenlegen (Namensvettern, „vgl.“-Verweise) | Verweise nur als Kanten; Zusammenlegen nur über Projekt-Entitäten mit Freigabe; B7-Negativliste |
| Riesige Akten (Haushalt, Jahresabschlüsse, Sammel-TOPs) | Sammel-TOPs ausnehmen (`_SAMMEL_TOPS`); Haushalt je Jahr eine Akte; Verdichtung von alt nach neu; Kontext-Budget in B8 |
| Längerer Kontext → teurer, langsamer | B8-Budget als Tor; Verdichtung |
| Kaputte Themen-Adressen, App-Links, Abos | nur über Aliase zusammenführen; Test über alle Slugs |
| Migration auf gewachsener DB | Schema *und* Migration; `test_migration_bestand.py` mit Zeilen |
| Neuaufbau blockiert Deploy | stapelweise, `kern/stopp.py` |
| Gold-Set misst falsch | 0.1 hat das schon gezeigt: Das Bürgerbusch-Verbot X2 war falsch (die Vorlage 26/0290 nennt die Gründe ausdrücklich), Opus hatte eine korrekte Antwort als Verstoß gewertet. Jede Änderung am Gold mit Begründung im Fall (`note`) |
| Protokoll-Lücke bleibt | Phase 0.5 klären; bis dahin angekündigte Stationen als solche kennzeichnen |

## 6. Was zu entscheiden ist

1. ~~Freigabe von Phase 0 und 1~~ — erteilt am 02.10.2026, beide gebaut.
2. **Dubletten-Freigabe in Phase 2:** Zusammenführen automatisch ab hoher
   Sicherheit oder immer per Klick im Admin-Panel?
3. **Sichtbarkeit:** Sollen die Themen-Seiten die Zeitleiste in Phase 2
   gleich zeigen (UI-PR, Bild vor dem Merge) oder erst nach Phase 3?
