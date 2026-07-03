---
title: Eval-Harness
description: Evaluierungs-Framework für die KI-Qualität (Suiten, Baselines).
---

Misst die **Qualität der KI-Extraktion** (Topic-Matching & Filter) gegen
handgelabelte Ground-Truth-Fälle. Ziel: Änderungen an Prompts oder Modellen
sollen messbar besser/schlechter werden, statt „gefühlt".

## Suiten

| Suite | Misst | Komponente | Scoring | Cases |
|-------|-------|-----------|---------|-------|
| `watcher` | Tagesordnung → Thema | `council/watcher.py` | Label-Sets | `cases_watcher.json` |
| `committee` | Routine-Filter (Inhalt ja/nein) | `council/committee_summary.py` | binär | `cases_committee.json` |

**Binär**: eine Ja/Nein-Entscheidung pro Fall → TP/FP/TN/FN + Precision/Recall/F1.
**Label-Sets**: pro Fall wird eine *Menge* von Treffern vorhergesagt (z. B. die
`(Thema, TOP)`-Paare). Bewertung als Retrieval-Aufgabe: `TP = vorhergesagt ∩
erwartet`, `FP = zu viel`, `FN = verpasst`, aggregiert über alle Fälle. So werden
Über- *und* Unter-Matching gleichzeitig gemessen.

## Ausführen

Braucht `OPENROUTER_API_KEY` in der Umgebung / `.env` (echte LLM-Calls):

```bash
python eval/run_watcher.py    # nur watcher
python eval/run_committee.py  # nur committee
python eval/run_all.py        # alle Suiten + Scoreboard

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

Nur das Erzeugen einer echten Baseline braucht den `OPENROUTER_API_KEY`.
