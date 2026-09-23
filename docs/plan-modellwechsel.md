# Plan: Modellwechsel Herbst 2026

Stand 22.09.2026. Anlass sind drei Dinge, die Tim am selben Abend
zusammengetragen hat:

1. **Gemini 2.5 Flash und 2.5 Flash Lite laufen bei OpenRouter am
   20.10.2026 aus** (`expiration_date` in `/api/v1/models`). Danach antwortet
   jedes Feature, das sie benutzt, mit einem Fehler — auch die, deren
   Ersatzmodell (`kern/llm.py::ERSATZ`) selbst 2.5 Flash ist.
2. **GPT-6 Luna** kostet halb so viel wie GPT-5.6 Luna
   (0,10/0,50 $ statt 0,20/1,20 $ je Mio. Tokens) und soll besser sein.
3. **`:batch`-Tarife** gibt es für fast jedes Modell (71 Varianten), zum
   halben Preis. Für Crons zählt die Antwortzeit nicht.

**Zwei Befunde vom selben Abend, beide gemessen gegen OpenRouter:**

- **GPT-6 Luna lief unter dem Haus-Routing nicht.** Jeder Aufruf endete mit
  404 „No endpoints found matching your data policy (Zero data retention)“.
  GPT-5.6 Luna läuft bei uns über Azure (auch `azure/eu`), das ZDR zusagt;
  GPT-6 Luna bieten bisher nur OpenAI direkt und Amazon Bedrock `us-east-1`
  an. **Tims Entscheidung am selben Abend:** ZDR nur noch für Aufrufe mit
  Nutzereingaben. Features, die nur öffentliche Ratsdaten verarbeiten, stehen
  in `kern/llm.py::OHNE_NUTZEREINGABE` und dürfen an Anbieter ohne ZDR
  (Nachtrag in ADR 0002). Kein Training (`data_collection: deny`) und kein
  China-Anbieter gelten weiter überall. Gemessen danach: GPT-6 Luna als
  `impact_rating` antwortet über OpenAI in 1,6 s, als `qa_answer` weiter 404.
  Alle sieben Luna-Features stehen in der Freigabe — **bis auf den Watcher**,
  der die Themenbeschreibungen der Nutzer*innen liest (und nebenbei gar kein
  `_feature` trägt, also auch nicht in der Kostenstatistik auftaucht).
- **`:batch` ist keine billigere Variante desselben Aufrufs**, sondern eine
  eigene, asynchrone Schnittstelle: „cannot be used with the
  chat/completions endpoint (adapter VertexGeminiBatchAdapter)“. Die
  DeepSeek-Modelle haben gar keinen `:batch`-Endpunkt. **OpenAIs Flex-Tarif**
  dagegen ist ein normaler Aufruf mit `service_tier: "flex"` an OpenAI
  direkt — ohne ZDR, also nur für die freigegebenen Features, dort aber ohne
  neuen Anschluss. Probe: 1,6 s für eine Zwei-Wort-Antwort.

**Kein Wechsel ohne Messung.** PR 29 (`docs/plan-lotti-assistentin-3.md`)
hat gezeigt, warum: Das „stärkere“ Modell erfand dort Pro-Kopf-Zahlen, die
Flash nie erfunden hat. „Neuer ist in der Tendenz besser“ stimmt im Mittel
und ist trotzdem kein Beleg für den einzelnen Einsatz.

## 1. Inventar

| Feature | Schalter | heute | läuft in | Eval |
|---|---|---|---|---|
| Lotti | `COUNCIL_ASSISTANT_MODEL` | gemini-2.5-flash | Web (Strom) | `eval/run_assistant.py --modell` |
| KI-Frage | `COUNCIL_QA_MODEL` | gemini-2.5-flash | Web (Strom) | `eval/run_qa.py`, `quality_qa.py` |
| KI-Frage: Erweiterung | `COUNCIL_QA_EXPAND_MODEL` | gemini-2.5-flash-lite | Web | `eval/run_qa_routing.py` |
| Eval-Richter | `COUNCIL_QUALITY_JUDGE_MODEL` | gemini-2.5-flash | Eval | — |
| Livestream-Transkription | `COUNCIL_STT_MODEL` | gemini-2.5-flash | Sitzungs-Mitschnitt | `transkription` (ohne Audio, misst noch nicht) |
| Live-Verfolgung | `COUNCIL_LIVE_TRACKER_MODEL` | gemini-2.5-flash | Sitzungs-Mitschnitt | `live-verfolgung` |
| Wortbeiträge | `COUNCIL_WORTBEITRAG_MODEL` | gemini-2.5-flash | Cron `check_protocols` | `wortbeitraege` |
| Ortszuordnung | `COUNCIL_LOCATION_MODEL` | gemini-2.5-flash-lite | Cron | `eval/run_locations.py` |
| Watcher | `COUNCIL_WATCHER_MODEL` | gpt-5.6-luna | Cron `check_council` | `eval/run_watcher.py` |
| Tragweite | `COUNCIL_IMPACT_MODEL` | gpt-5.6-luna | Cron | `scripts/eval_impact.py` (Golden Set, 30) |
| Ausschuss-Zusammenfassung | `COUNCIL_COMMITTEE_MODEL` | gpt-5.6-luna | Cron | `eval/run_committee.py` |
| Video-Ergebnisse | `COUNCIL_VIDEO_MODEL` | gpt-5.6-luna | Cron + Mitschnitt | `video-ergebnisse` |
| Social-Texte | `COUNCIL_SOCIAL_MODEL` | gpt-5.6-luna | Cron | `social-text` |
| Kritiker | `COUNCIL_KRITIKER_MODEL` | gpt-5.6-luna | Cron | `kritiker` |
| Viertel | `COUNCIL_DISTRICT_MODEL` | gpt-5.6-luna | Cron | `viertel` |
| Rest (Protokolle, Themen, Ziele, Rückblicke, …) | `COUNCIL_*_MODEL` | deepseek-v4-pro | Cron | teils |
| Städtevergleich | `CITIES_*_MODEL` | deepseek-v4-flash | Cron (pausiert) | `eval/run_cities_*` |

DeepSeek-Modelle laufen nicht aus. In P3 standen sie für `:batch` zur
Wahl, aber DeepSeek v4 Pro hat weder Batch noch Flex (s. § 4, P3).

**Falle vor jedem Umstellen:** Setzt die `.env` auf dem Server ein Modell
ausdrücklich, ändert ein neuer Vorgabewert im Code dort nichts. Vor dem
Merge von P4–P5 also auf Prod und dev nachsehen:
`grep MODEL ~/app/.env` — und dieselbe Zeile im PR-Text nennen.

## 2. Regeln

- Je Feature **zwei Läufe** der Eval mit dem alten und zwei mit dem neuen
  Modell, gleiche Datenbank. Die Streuung zwischen zwei Läufen desselben
  Modells ist in PR 29 bis zu drei Fälle von 53 — ein Lauf sagt nichts.
- Echte Kosten aus `llm_usage.cost_usd` (`kern/usage.seit`), keine Schätzung.
- Latenz p50/p95 für alles, was im Web läuft; bei Crons Dauer je Lauf.
- Neues Modell ⇒ Eintrag in `MODEL_PARAMS` (denkende Modelle brauchen
  einen Token-Boden, sonst kommt die Antwort still abgeschnitten zurück)
  und in `usage.PRICES`.
- `ERSATZ` nachziehen: Heute ist 2.5 Flash der Ersatz für Luna. Nach dem
  20.10. wäre das ein Ersatz, der selbst ausfällt.
- **Web-Anfragen nie über `:batch`.**
- Ein Feature ohne Eval bekommt vor dem Wechsel eine kleine: zehn echte
  Eingaben, alte Ausgabe daneben, buchstäblich prüfbare Zusagen (Zahlen,
  Namen, Form). Kein Modell als Richter.

## 3. Der Modell-Prüfstand

Tim, 22.09.2026: „für alle Features, die KI nutzen und die wir benchmarken
können, dass wir diese benchmarken, wenn neue Modelle rauskommen — was macht
ein neues Modell besser, wie viel besser sind die Antworten, und wie kann man
etwas günstiger machen.“ Aus der Einmal-Messung wird deshalb ein Werkzeug,
das bleibt.

**Ein Befehl, alle Features:**

    python eval/pruefstand.py --modell openai/gpt-6-luna --laeufe 2
    python eval/pruefstand.py --suite lotti,ki-frage --modell google/gemini-3.5-flash-lite
    python eval/pruefstand.py --suite tragweite --tarif flex
    python eval/pruefstand.py bericht        # schreibt docs/modell-pruefstand.md

**Je Suite dasselbe Messformat**, damit ein Bericht alle Features
nebeneinanderstellen kann:

| Feld | Bedeutung |
|---|---|
| `qualitaet` | die Hauptkennzahl der Suite, 0–1 (Anteil sauberer Fälle, F1, Trefferquote — je Suite festgelegt und im Register begründet) |
| `harte_befunde` | Fälle mit erfundener Zahl, verletzter Zusage, abgelehnter Injektion |
| `p50_ms`, `p95_ms` | nur Modellaufrufe |
| `ct_je_aufruf`, `ct_je_lauf` | echte Kosten aus `usage.seit` — nie aus `PRICES` geschätzt |
| `ausfaelle` | Aufrufe, die nach allen Anläufen scheiterten |
| `streuung` | Abstand zwischen zwei Läufen desselben Modells |

**Das Register** (`eval/pruefstand.py`) nennt je Suite: Feature-Name(n),
Modell-Schalter, Eingabedaten, ob Nutzereingabe (dann nie ohne ZDR und nie
Flex/Batch), ob Web (Latenz zählt) oder Cron (Latenz egal, Tarif frei).

**Der Bericht** stellt je Feature das heutige Modell neben jeden gemessenen
Kandidaten: Qualität mit Streuung, Kosten, Latenz — und markiert einen
Unterschied nur dann als Gewinn oder Verlust, wenn er größer ist als die
Streuung. Das ist die Lehre aus PR 29: Auf 43 Fällen maßen drei Modelle
Rauschen.

**Abdeckung.** Heute haben 7 von 26 Schaltern eine Eval. Ziel: jedes
Feature, das mehr als 1 % der Modellkosten trägt oder im Web läuft. Wo die
richtige Antwort Geschmack ist (Social-Texte, Kurzfassungen), prüft die
Suite Zusagen, die sich buchstäblich prüfen lassen: keine Zahl, die nicht im
Beschluss steht, Länge, Pflichtbestandteile, kein Bewertungswort — kein
Modell als Richter.

## 4. PRs

### P1 — Prüfstand-Kern

`eval/pruefstand.py` mit Register, Messformat, `--modell`, `--laeufe`,
`--tarif`, `bericht`. Die vorhandenen Suiten werden angeschlossen: Lotti
(`run_assistant`), KI-Frage (`run_qa`, `run_qa_routing`), Watcher,
Ausschuss, Orte, Tragweite (`scripts/eval_impact.py`,
`eval_agenda_impact.py`), Städtevergleich (`run_cities_*`). Offline-Tests
mit Attrappe wie in `harness.py`. Erster Bericht mit dem heutigen Stand
aller angeschlossenen Suiten, je zwei Läufe.

**Stand 23.09.2026 (PR P1): gebaut.** 13 Suiten im Register, zwölf lokal
lauffähig; `ki-frage` braucht die Embeddings und läuft nur auf dem Server.
Der erste Bericht steht in [`docs/modell-pruefstand.md`](modell-pruefstand.md),
die Lotti-Messung von oben ist übernommen, nicht neu gefahren. Kurz:

- **Tragweite:** GPT-6 Luna liegt mit 5.6 gleichauf (91,7 % ± 3,3 beide), im
  Flex-Tarif zum Viertel des heutigen Preises je Aufruf. 5.6 im Flex-Tarif
  brauchte 24–27 s je Aufruf statt 9 s.
- **Ausschuss:** beide Luna 100 %. Die Suite hat aber nur drei Fälle, ein
  Unterschied wäre dort gar nicht messbar.
- **Watcher:** GPT-6 Luna ist nicht zulässig (ZDR). Der Watcher trägt jetzt
  `_feature="council_watcher"` und taucht damit in der Kostenstatistik auf.
- **KI-Frage-Routing:** 3.1 Flash Lite schlechter (80 % gegen 90 %), 3.5
  Flash Lite im Rauschen (± 6,7), DeepSeek V4 Flash ohne Denken gleichauf,
  aber 8–9 s statt 0,8 s je Analyse. Für einen Web-Pfad kommt das nicht in
  Frage.
- **Orte:** alle Kandidaten im Rauschen. 3.1 und 3.5 Flash Lite kosten das
  Sechs- bis Neunfache.
- **`RATSLOTSE_LLM_TARIF`** (`llm.TARIF_ENV`) ist der Messschalter, über den
  `--tarif flex` die Aufrufe in `council/` erreicht. In den Betrieb gehört er
  nicht.

### P2 — Evals für die Features ohne Eval

Zuerst die, die ein Wechsel ohnehin trifft: Transkription, Live-Verfolgung,
Wortbeiträge (2.5 Flash läuft aus), Video-Ergebnisse, Social-Texte,
Kritiker, Viertel (Luna). Danach die DeepSeek-Pro-Crons nach Kostenanteil
(Admin-Panel *Statistik → LLM-Kosten*). Je Suite zehn bis dreißig echte
Eingaben aus `data/council.sqlite`, die Erwartung aus den Daten, nicht aus
der alten Modellausgabe allein.

**Stand 23.09.2026 (PR P2): sieben Suiten gebaut, sechs gemessen**, je zwei
Läufe heute und je Kandidat, zusammen 1,35 $. Dazu die Regel im Bericht:
Ein Kandidat, der häufiger einer Injektion folgt oder mehr erfindet als das
heutige Modell, heißt „nicht zulässig“ statt „besser“ (`pruefstand.sperre`).
Gemini 3.1 Flash Lite steht bei Lotti deshalb jetzt so da. Kurz:

- **Wortbeiträge:** alle drei Gemini-Nachfolger **schlechter** (86,6 bis
  91,1 % gegen 97,8 %). Sie erfinden nichts, lassen aber Redner*innen aus
  und legen Beiträge zusammen (Recall 0,77 bis 0,84 gegen 0,97). Vorbehalt:
  Die Erwartung stützt sich zur Hälfte auf die gespeicherte Extraktion von
  2.5 Flash, das heutige Modell ist also leicht im Vorteil. Für den Wechsel
  im Oktober braucht es hier einen Prompt-Nachzug oder ein anderes Modell.
- **Live-Verfolgung:** alle im Rauschen, 3.5 Flash Lite gleichauf zum
  gleichen Preis und mit 1,1 s statt 1,8 s. Die Suite ist fast gesättigt
  (100 % heute): Sie sagt „kein Rückschritt“, nicht „besser“.
- **Transkription:** keine Messung. Es gibt nirgends Sitzungs-Audio, auch
  nicht auf dem Server (s. `eval/run_stt.py`, was gebraucht wird).
- **Video-Ergebnisse:** GPT-6 Luna **schlechter** (85,2 gegen 89,3 %), im
  Flex-Tarif im Rauschen. Kein Kandidat gab ein falsches Ergebnis aus.
- **Social-Text, Kritiker, Viertel:** GPT-6 Luna normal und Flex im
  Rauschen, im Flex-Tarif zu einem Fünftel bis Viertel des heutigen Preises
  je Aufruf. Social-Text und Kritiker streuen stark (± 10 bzw. 11 Pp).
- **Nicht gemacht:** die DeepSeek-Pro-Crons (Kurzfassung, Themenfeld,
  Protokolle, Interesse, Ziele). Die Reihenfolge nach Aufrufen je Lauf steht
  noch aus.

### P3 — Batch und Flex, gemessen

Die Frage ist nicht „ist es billiger“ (ja, halb so teuer), sondern „bleibt
die Leistung gleich, und passt die Wartezeit in den Cron“. Gemessen je
Kandidat an einer Cron-Suite: Qualität gegen den normalen Tarif, Wartezeit
bis zum Ergebnis, Ausfälle, echte Kosten.
- **Flex** (OpenAI, `service_tier: "flex"`): gleicher Aufruf, nur für
  Features aus der Freigabeliste. Kandidat: Tragweite (Golden Set).
- **`:batch`**: eigene Schnittstelle bei OpenRouter (Auftrag einreichen,
  später abholen). Erst klären: Welche Anbieter, welche Datenpolitik, wie
  lange bis zum Ergebnis. Dann ein Anschluss in `kern/llm.py`, der für
  Crons einen Stapel einreicht und abholt, mit `run_guarded`-tauglicher
  Frist und `kern/stopp.py`.
- DeepSeek hat keinen Batch-Tarif. Dort ist die billigere Stellschraube
  das Denken: V4 Flash ohne Denken ist das billigste Modell der Auswahl.

**Stand 22.09.2026 (PR #1476):**

- **Flex: gebaut.** `llm.chat_complete(_tarif="flex")` ist verfügbar, aber
  noch an keiner Aufrufstelle eingeschaltet. Auf dem Golden Set lieferte
  Flex dieselbe Qualität zum halben Preis, war nicht langsamer, und 24
  Aufrufe liefen ohne eine Abweisung durch. Erlaubt ist Flex nur für
  Features aus `OHNE_NUTZEREINGABE`, sonst fliegt `FlexNichtErlaubt`. Das
  Umschalten der Aufrufstellen ist Tims Entscheidung (Kandidaten s. § 5).
- **Batch: verworfen**, aus fünf Gründen:
  - Batch kostet dasselbe wie Flex, also die Hälfte, ohne weitere
    Ersparnis.
  - Das Ergebnis kommt erst nach Minuten bis Stunden (gemessen 1 bis 9,5
    min, zwei Stapel nach 48 bzw. 50 min noch offen, laut OpenRouter p99 10 h).
  - Ein laufender Stapel lässt sich nicht abbrechen (409/404). Das verträgt
    sich nicht mit `kern/stopp.py`.
  - Das Routing kennt nur `provider.only`: `ignore`, `data_collection` und
    `zdr` weist die Schnittstelle mit 400 ab.
  - Die Eingaben liegen 30 Tage bei OpenRouter, und bei OpenAI lassen sie
    sich nicht löschen.

  Einen `:batch`-Endpunkt ohne Flex-Endpunkt hat keins der Modelle, die
  hier laufen. DeepSeek v4 Pro hat keinen von beiden.

### P4 — Gemini 2.5 ablösen (Frist: 13.10.)

Web-Pfade (Lotti, KI-Frage, Erweiterung) und Pipelines (Transkription,
Live-Verfolgung, Wortbeiträge, Orte, Eval-Richter), je nach P1/P2 gemessen.

### P5 — GPT-5.6 Luna ablösen

Die sechs freigegebenen Luna-Features auf GPT-6 Luna (oder Flex), je nach
Messung; der Watcher bleibt bei ZDR und bekommt ein `_feature`.

### P6 — Aufräumen

`MODEL_PARAMS`, `PRICES`, `ERSATZ` (heute ist 2.5 Flash der Ersatz für
Luna), `CLAUDE.md`-Beispiel-`.env`, `docs-site/`.

## 5. Ergebnisse

### Lotti (gemessen 22.09.2026, `eval/run_assistant.py`, 53 Fälle, je zwei Läufe)

Injektionsfall `injektion-wertung` mit der erweiterten Verbotsliste
nachgeprüft (s. u.); die Zahlen hier zählen sie schon mit.

| Modell | hart sauber | `schwer-*` | Injektionen | p50 | p95 | ct/Aufruf |
|---|---|---|---|---:|---:|---:|
| gemini-2.5-flash (heute) | 50, 49 | 7, 7 | 7/7, 7/7 | 1,1 s | 2,0 s | 0,07–0,12 |
| gemini-3.1-flash-lite | 51, 51 | 9, 9 | **6/7, 6/7** | 1,3–1,4 s | 2,0 s | 0,08–0,10 |
| gemini-3.5-flash-lite | 48, 46 | 7, 6 | 7/7, **6/7** | 1,0–1,1 s | 1,6 s | 0,10–0,12 |
| gemini-3-flash-preview | 48, 49 | 8, 9 | 7/7, 7/7 | 2,2–2,6 s | 5,0–5,8 s | 0,25–0,30 |
| gemini-3.8-flash (denkt zwingend) | 49, 49 | 8, 7 | 7/7, 7/7 | 13–15 s | 63–134 s | 0,82–0,85 |
| deepseek-v4-flash | 43, 40 | 6, 6 | 7/7, 7/7 | 6,0–6,5 s | 18–24 s | 0,02–0,03 |
| deepseek-v4-flash ohne Denken | 38, 39 | 4, 6 | 7/7, 7/7 | 6,4–7,8 s | 12–15 s | 0,02 |
| gemini-3.1-pro-preview (PR 29) | 47, 50 | 8, 9 | 7/7, 7/7 | 14,7 s | 23–30 s | 2,9 |
| claude-sonnet-4.6 (PR 29) | 46, 46 | 8, 8 | 7/7, 7/7 | 4,1–4,4 s | 6,4–7,2 s | 1,56 |

**Was daraus folgt:**

- **Kein Kandidat ist ein glatter Ersatz.** Gemini 3.1 Flash Lite ist bei
  Inhalt und schweren Fällen das beste Modell der Messung und so schnell wie
  heute — folgt aber der Lob-Injektion in **beiden** Läufen („Es ist wirklich
  lobenswert …“, „Es ist großartig, dass sich die Fraktionen so aktiv …“).
  Gemini 2.5 Flash tat das nie. Vor einem Wechsel braucht der Prompt eine
  härtere Abwehr, und die Injektionsfälle müssen danach 7/7 in beiden Läufen
  stehen.
- **Die Eval hatte eine Lücke.** Der Fall verbot nur „lobenswert“,
  „vorbildlich“, „besonders gut“; das zweite Lob ging durch. Die Liste ist
  erweitert (ohne „lob…“-Stamm, damit die Ablehnung grün bleibt), und alle
  gespeicherten Antworten sind dagegen nachgeprüft — dabei fiel auch 3.5
  Flash Lite einmal auf („hervorragende Arbeit“).
- **Gemini 3 Flash Preview erfindet Zahlen** (`keine-erfundene-zahl` 0/2),
  wie die großen Modelle in PR 29.
- **DeepSeek V4 Flash ist nicht wegen des Denkens langsam.** Mit und ohne
  Denken erzeugt es im Schnitt rund 170 Tokens je Antwort; die 6–8 s kommen
  von den Anbietern, die nach dem China-Ausschluss bleiben. Für Lotti ist es
  auch inhaltlich zu schwach.

### P3 — Batch und Flex (gemessen 22.09.2026)

Die Messung lief am Tragweite-Golden-Set: 30 Beschlüsse, der Prompt aus
`council/impact.py`, zwei Aufrufe je Lauf. Die Kosten sind die echten Werte
aus `usage.cost`. Einzelläufe, alle Belege und die Batch-Schnittstelle im
Detail stehen in [`docs/modell-batch-flex.md`](modell-batch-flex.md).

| Modell | Tarif | Läufe | ⌀ ρ | ⌀ Treffer | ⌀ ct/Aufruf | Ausfälle |
|---|---|---:|---:|---:|---:|---:|
| gpt-5.6-luna | normal (ZDR, Azure) | 4 | 0,839 | 27,2/30 | 0,105 | 1× 429 upstream |
| gpt-5.6-luna | **flex** | 5 | 0,866 | 27,8/30 | **0,055** | 0 |
| gpt-5.6-luna | batch | 1 | 0,862 | 27,0/30 | 0,074 | 0 |
| gpt-6-luna | normal (ohne ZDR) | 4 | 0,810 | 26,5/30 | 0,048 | 0 |
| gpt-6-luna | **flex** | 5 | 0,855 | 26,8/30 | **0,023** | 0 |
| gpt-6-luna | batch | 2 | 0,819 | 24,5/30 | 0,023 | 0 |
| gemini-2.5-flash | normal | 2 | 0,831 | 25,5/30 | 0,362 | 0 |
| gemini-2.5-flash | **flex** | 2 | 0,821 | 26,0/30 | **0,190** | 0 |

**Was daraus folgt:**

- **Flex ist dasselbe Modell zum halben Listenpreis, bei gleicher
  Qualität.** Die Unterschiede liegen im Rauschen: Die Einzelläufe von
  GPT-6 normal streuen zwischen ρ 0,756 und 0,861. Flex war nicht langsamer
  (Luna 5.6 31 s gegen 41 s). Mit `zdr: true` ignoriert OpenRouter den
  Tarif still, deshalb braucht Flex die Freigabeliste.
- **Batch hat denselben Listenpreis wie Flex.** Dazu kommen die Nachteile
  aus § 4, P3. Es gibt deshalb kein Batch-Modul.
- **Kandidaten für Flex:** die Luna-Crons aus der Freigabeliste
  (`impact_rating(_agenda)`, `committee_summary`, `video_results`,
  `district_projects`, `social_*`) und `speeches` (Gemini 2.5 Flash).
  **Offen:** ihr Kostenanteil. Den zeigt nur das Admin-Panel auf Prod.

