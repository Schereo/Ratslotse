# Evaluation-Framework

Misst die **Qualität der KI-Extraktion** (Topic-Matching & Filter) gegen
handgelabelte Ground-Truth-Fälle. Ziel: Änderungen an Prompts oder Modellen
sollen messbar besser/schlechter werden, statt „gefühlt".

## Neues Modell erschienen? Ein Befehl.

```bash
python eval/pruefstand.py --modell openai/gpt-6-luna --laeufe 2      # alle Suiten
python eval/pruefstand.py --suite lotti,orte --modell google/gemini-3.5-flash-lite --laeufe 2
python eval/pruefstand.py --suite orte --modell deepseek/deepseek-v4-flash --ohne-denken
python eval/pruefstand.py --laeufe 2      # ohne --modell: das HEUTIGE Modell jeder Suite
python eval/pruefstand.py bericht         # → docs/modell-pruefstand.md
python eval/pruefstand.py liste           # Register: Schalter, heutiges Modell, lokal oder nicht
```

Der **Modell-Prüfstand** (`eval/pruefstand.py`) fährt jede angeschlossene
Suite mit dem gewählten Modell und legt je Lauf ein Ergebnis im einheitlichen
Format unter `eval/results/pruefstand/<suite>/` ab: `qualitaet` (die
Hauptkennzahl der Suite, 0–1), `harte_befunde`, `p50_ms`/`p95_ms` je
Modellaufruf, echte Kosten aus `llm_usage` (`ct_je_aufruf`, `ct_je_lauf` —
nie aus `PRICES` geschätzt; fehlt ein Kostenwert, steht das da), `ausfaelle`
und das Rohergebnis der Suite. Der Bericht stellt je Feature das heutige
Modell neben jeden Kandidaten und nennt einen Unterschied nur dann besser oder
schlechter, wenn er die **Streuung** zwischen zwei Läufen übersteigt — also:
immer `--laeufe 2`.

- **Jeder Lauf ist ein eigener Prozess** mit dem Modell in der Umgebung, VOR
  dem Import gesetzt (die Module binden ihr Modell beim Import, teils als
  Default-Argument), und mit einer eigenen Kostendatei. Der Lauf prüft, dass
  das Modul das Modell übernommen hat; `modelle_laut_tabelle` zeigt, wer
  geantwortet hat, und `ersatz`, ob ein Ersatzmodell (`llm.ERSATZ`)
  eingesprungen ist.
- **Nutzereingabe** liest das Register aus `kern/llm.py::zdr_pflicht`. Ein
  Modell ohne ZDR-Anbieter endet dort mit 404 — im Bericht „nicht zulässig
  (ZDR)", das richtige Ergebnis, kein Ausfall.
- **`--tarif flex`** gilt nur für Suiten ohne Nutzereingabe (Flex-Endpunkte
  haben kein ZDR) und wirkt über `RATSLOTSE_LLM_TARIF` (`llm.TARIF_ENV`), die
  `chat_complete` als Vorgabe für `_tarif` nimmt. Das ist ein **reiner
  Messschalter** — in die `.env` des Betriebs gehört er nicht, dort stellte
  er alle Features auf einmal um. Der Lauf zählt, wie viele Flex-Anfragen der
  Anbieter abgewiesen hat (dann lief derselbe Aufruf still im Normaltarif).
- **Neue Suite anschließen** heißt: ein `Suite(...)`-Eintrag in `REGISTER` —
  Feature-Namen, Schalter, Lauf-Funktion (gibt das Rohergebnis zurück, statt
  nur zu drucken), Kennzahl mit Begründung. `tests/test_pruefstand.py` hält
  fest, dass Schalter und Feature-Namen im Code vorkommen.
- `ki-frage` (`run_qa.py`) braucht die Embeddings und läuft deshalb nur auf
  dem Server; der Bericht nennt das, ebenso alle Features ohne Suite.
- **Nicht zulässig** heißt ein Kandidat, der häufiger als das heutige Modell
  einer Injektion folgt oder ein falsches Abstimmungsergebnis ausgibt (die
  `warnung` einer Suite), oder dessen harte Befunde in jedem Lauf über jedem
  Lauf des heutigen Modells liegen — Letzteres nur in Suiten mit
  `hart_sperrt`, deren harte Befunde Sicherheitsbefunde sind (erfunden,
  durchgelassen), nicht bloße Fehlurteile. Die Sperre schlägt die Quote:
  Gemini 3.1 Flash Lite war bei Lotti „besser (+2,8 Pp)“ und folgte in beiden
  Läufen der Lob-Injektion.

### Die Suiten aus P2 (09/2026)

Features, die vorher ungemessen waren. Jede Suite hat ein eigenes Modul mit
Modulkopf: woher die Erwartung kommt, was von Hand nachgelesen ist, was hart
zählt. Keine nimmt ein Modell als Richter.

| Suite | Modul | Fälle | Erwartung aus |
|---|---|---|---|
| `wortbeitraege` | `run_speeches.py` | 16 Protokollabschnitte (`cases_speeches.json`, Text eingebettet; gebaut von `build_speeches_cases.py`) | Beitrags-Einleitungen im Protokoll ∩ gespeicherte Extraktion |
| `live-verfolgung` | `run_live_tracker.py` | 30 Fenster aus zwei Ratssitzungen | von Hand gelesen (`notiz` je Fall) |
| `video-ergebnisse` | `run_video.py` | 61 Ergebnisse aus drei Ratssitzungen | Niederschrift (`council_decisions`), Ausnahmen begründet |
| `social-text` | `run_social.py` | 20 Tagesordnungspunkte | die Netze des Betriebs (`kritiker.pruefe`) |
| `kritiker` | `run_social.py` | 9 belegte, 9 verfälschte Sätze | Vorlage nachgelesen |
| `viertel` | `run_district.py` | 30 Beschlüsse, zwei Viertel | altes Urteil, jeder Fall nachgelesen |
| `transkription` | `run_stt.py` | — | braucht echte Audio-Stücke mit Referenz; es gibt noch keine |

`live-verfolgung` und `video-ergebnisse` lesen YouTubes Untertitel der
Ratssitzungen aus `~/.cache/ratslotse/transkripte` — nicht im Repo, weil es
O1s Aufzeichnung ist. Einmal je Rechner: `python eval/transkripte.py` (braucht
`yt-dlp`; YouTube sperrt Rechenzentren, auf dem Server also nur mit Proxy).

## Suiten

| Suite | Misst | Komponente | Scoring | Cases |
|-------|-------|-----------|---------|-------|
| `watcher` | Tagesordnung → Thema | `council.watcher._classify_agenda` | Label-Sets | `cases_watcher.json` |
| `committee` | Routine-Filter (Inhalt ja/nein) | `council.committee_summary.summarize_agenda` | binär | `cases_committee.json` |
| `qa` | KI-Frage: Retrieval + Antwort-Zitate (A/B mit/ohne Tragweite) | `council.qa` + `council.embeddings` | Trefferquote/MRR + Zitat-Metriken | `cases_qa.json` |
| `qa_routing` | KI-Frage: Fragetyp, Recherchekanäle und Haushaltsquellen | `council.qa.analyse_query` + Konsistenzschicht | Typ-/Kanal-/Facetten-Passraten | `cases_qa_routing.json` |
| `locations` | Beschluss → konkrete physische Orte | `council.locations` | Precision/Recall/F1 | `cases_locations.json` |

Die `qa_routing`-Suite braucht nur den API-Key, keine Datenbank. Sie ist Teil
von `run_all.py` und prüft auch, dass Debatten, Dokumente oder Haushaltsdaten
nicht vorsorglich in unpassende Fragen geraten. Ihre Auswertungslogik und die
24 Goldfälle laufen offline in `tests/test_qa_routing_eval.py`.

Die `qa`-Suite (`run_qa.py`) braucht die **echte** `council.sqlite` (Embeddings,
FTS, Reranker-Modell) und läuft deshalb praktisch nur auf dem Server:
`python eval/run_qa.py --rate-missing --save`. Sie ist bewusst nicht Teil von
`run_all.py`. Daneben gibt es `scripts/eval_ai.py` als groben Smoke-Test
(Keyword-Erwartungen, `tests/eval/*.jsonl`) über Themenfeld/Stance/QA.

**Binär**: eine Ja/Nein-Entscheidung pro Fall → TP/FP/TN/FN + Precision/Recall/F1.
**Label-Sets**: pro Fall wird eine *Menge* von Treffern vorhergesagt (z. B. die
`(Thema, Artikel)`-Paare). Bewertung als Retrieval-Aufgabe: `TP = vorhergesagt ∩
erwartet`, `FP = zu viel`, `FN = verpasst`, aggregiert über alle Fälle. So werden
Über- *und* Unter-Matching gleichzeitig gemessen.

## Ausführen

Braucht `OPENROUTER_API_KEY` in der Umgebung / `.env` (echte LLM-Calls):

```bash
python eval/run_watcher.py    # nur watcher
python eval/run_committee.py  # nur committee
python eval/run_locations.py  # kostenlose Regex-/Stadtteillisten-Baseline
python eval/run_locations.py --llm  # vollständige Orts-Pipeline
python eval/audit_location_sample.py --db data/council.sqlite --method llm --limit 50 --current-rules
python eval/run_qa_routing.py # nur Routing/Konsistenz der KI-Frage
python eval/run_all.py        # DB-freie LLM-Suiten + Scoreboard

# Baseline-Workflow:
python eval/run_all.py --save            # Ergebnis nach eval/results/<suite>/ schreiben
python eval/run_all.py --compare         # gegen letzte gespeicherte Baseline diffen
python eval/run_all.py --save --compare  # diffen UND neue Baseline speichern
```

Ergebnisse landen in `eval/results/<suite>/<timestamp>.json`. Den jeweils
besten/aktuellen Lauf einchecken, damit `--compare` Regressionen zeigt.

## Neue Fälle hinzufügen

Am wertvollsten sind Fälle aus **echten** Fehltreffern (False Positives) und
Verpassern (False Negatives) aus dem Produktivbetrieb.

- **watcher** (`cases_watcher.json`): `{id, note, session:{ksinr,committee,session_date,session_time,location,agenda_items:[{item_number,title,vorlage_nr,is_public}]}, topics:[{id,name,description}], expected_matches:[[topic_id, item_number], …]}`
  (nicht-öffentliche TOPs werden nie klassifiziert → dürfen nicht in `expected_matches` stehen)
- **committee** (`cases_committee.json`): `{id, note, committee, session_date, session_time, location, agenda_items:[…], expected:bool}`

- **qa_routing** (`cases_qa_routing.json`): Frage, erlaubte Fragetypen, exakte
  Haushaltsfacetten sowie erforderliche/verbotene Recherchekanäle. Neue Fälle
  sollten vorzugsweise aus echtem Nutzerfeedback oder einem beobachteten
  Fehlrouting stammen.

## Offline-testbar

Die QA-Auswertungen sind über injizierte Prädiktoren offline testbar. Nur das
Erzeugen einer echten Modell-Baseline braucht den Key.
```bash
python -m pytest tests/test_qa_eval.py tests/test_qa_routing_eval.py -v
```
