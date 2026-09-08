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
| `qa` | KI-Frage: findet sie die richtigen Beschlüsse? | `council/qa.py` | Label-Sets | `cases_qa.json` |

Jede Suite hat ein `run_<suite>.py`; `eval/run_all.py` fährt alle nacheinander.

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

## Golden-Sets außerhalb des Harness

Zwei Prüfungen liegen bewusst neben dem Harness, weil sie nicht Treffer-Mengen
messen, sondern die Qualität einer **Bewertung**:

| Skript | Prüft | Reißleine |
|--------|-------|-----------|
| `scripts/eval_ai.py` | Klassifikations-Qualität gegen ein Gold-Set | Regressionsguard vor Prompt-Änderungen |
| `scripts/eval_impact.py` | Tragweite-Score gegen `scripts/golden_impact.json` | Rangkorrelation + Band-Trefferquote; unterschritten → kein Rollout |
| `eval/run_cities_transfer.py` | Einordnung fremder Ratsvorlagen (`cities_classify`) | „taugt/taugt nicht" unter 80 % → Regression |
| `eval/run_cities_fit.py` | Urteil über Oldenburg (`cities_fit`) | Beleg-Disziplin unter 100 % → Regression |

### Warum der Städtevergleich zwei Prüfstände hat

`cities_classify` gibt einer fremden Vorlage ein Etikett und braucht dafür nur
sie selbst. `cities_fit` beantwortet dagegen zwei Fragen über **Oldenburg** —
„hat die Stadt das schon?" und „lohnt ein Antrag?" — und bekommt dafür Belege
aus dem eigenen Bestand mit: die nächsten Oldenburger Vorlagen, Treffer der
Volltextsuche und den Themenfeld-Rückblick.

Das macht ein drittes Maß nötig, und es ist das wichtigste: die
**Beleg-Disziplin**. Jede Kennung, die das Modell nennt, muss ihm vorgelegen
haben, und eine Behauptung über Oldenburg braucht mindestens eine. Ein Urteil,
das sich auf einen erfundenen Beleg beruft, ist nicht ungenau, sondern falsch —
deshalb als einziges Maß mit Schwelle 100 %. Im Betrieb verwirft
`council/cities/fit.py` solche Antworten und zählt sie.

Beide Prüfstände tragen ihre Fälle **samt Belegen** bei sich und brauchen keine
Datenbank. Das ist keine Bequemlichkeit: Oldenburgs Bestand wächst, und ein
Maßstab, der sich unter der Hand ändert, misst nichts.

**Eine Falle, in die ich selbst getappt bin:** Die ersten durchgerechneten
Beispiele im `fit`-Prompt waren Fälle aus dem Prüfstand. Die Trefferquote stieg
prompt — und maß ab da sich selbst. Die Beispiele sind jetzt erfunden, aber
typisch; keiner davon steht in `cases_cities_fit.json`.

`eval_impact.py` ist der erste Schritt des Ops-Workflows für die Tragweite: Nur
wenn das Gate hält, startet der Voll-Backfill. Siehe
[Bewertungs-Scores](/docs/bewertungen/) und [Betrieb](/docs/betrieb/).
