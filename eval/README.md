# Evaluation-Framework

Misst die **Qualität der KI-Extraktion** (Topic-Matching & Filter) gegen
handgelabelte Ground-Truth-Fälle. Ziel: Änderungen an Prompts oder Modellen
sollen messbar besser/schlechter werden, statt „gefühlt".

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
