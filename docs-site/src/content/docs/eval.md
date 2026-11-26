---
title: Eval-Harness
description: Testsuiten, Baselines und Referenzdaten für die Evaluation der KI-Funktionen.
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

Die Tabelle zeigt die drei Suiten des Harness. Daneben gibt es Messläufe für fast
jeden weiteren Modell-Schritt (Dossiers, Änderungsanträge, Live-Verfolgung,
Städtevergleich, Lottis Erklärungen …). Die vollständige Liste entsteht aus den
Docstrings der Dateien: [Referenz: Eval-Läufe](/docs/referenz/eval-laeufe/).

**Binär**: eine Ja/Nein-Entscheidung pro Fall → TP/FP/TN/FN + Precision/Recall/F1.
**Label-Sets**: pro Fall wird eine *Menge* von Treffern vorhergesagt (z. B. die
`(Thema, TOP)`-Paare). Bewertung als Retrieval-Aufgabe: `TP = vorhergesagt ∩
erwartet`, `FP = zu viel`, `FN = verpasst`, aggregiert über alle Fälle. So werden
Über- *und* Unter-Matching gleichzeitig gemessen.

## Benchmarks im Admin-Panel

Jede Messung erscheint im Admin-Panel unter *Benchmarks*, gegliedert nach
KI-Pipeline (Frag den Rat, Gründliche Recherche, Lotti, …). Katalog und
Format stehen in `kern/benchmarks.py`: Ein **Lauf** ist eine JSON-Datei unter
`eval/runs/<benchmark>/` mit Modell je Stufe, Fällen samt Prüfsumme,
Datenstand, Code-Stand, Kennzahlen, Kosten, Zweck und Fazit; `raw` zeigt auf
das Rohergebnis. Läufe, die auf einem Server entstehen (Gold-Fälle), liegen
dort unter `data/eval_runs/`. Eine Messung gilt als überholt, wenn das Modell
einer gemessenen Stufe seither gewechselt hat, die Fälle sich geändert haben
oder sie älter als 90 Tage ist.

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

Verwende nach Möglichkeit Fälle aus dem Produktivbetrieb, in denen die
Suche falsche Treffer geliefert (False Positives) oder relevante Treffer
übersehen hat (False Negatives).

- **watcher** (`cases_watcher.json`): `{id, note, session:{ksinr,committee,session_date,session_time,location,agenda_items:[{item_number,title,vorlage_nr,is_public}]}, topics:[{id,name,description}], expected_matches:[[topic_id, item_number], …]}`
  (nicht-öffentliche TOPs werden nie klassifiziert → dürfen nicht in `expected_matches` stehen)
- **committee** (`cases_committee.json`): `{id, note, committee, session_date, session_time, location, agenda_items:[…], expected:bool}`

Nur das Erzeugen einer echten Baseline braucht den `OPENROUTER_API_KEY`.

## Golden-Sets außerhalb des Harness

Tests außerhalb des Harness prüfen die Qualität einzelner
**Bewertungen** anhand von Golden-Sets.

| Skript | Prüft | Reißleine |
|--------|-------|-----------|
| `scripts/eval_ai.py` | Klassifikations-Qualität gegen ein Gold-Set | Regressionsguard vor Prompt-Änderungen |
| `scripts/eval_impact.py` | Tragweite-Score gegen `scripts/golden_impact.json` | Rangkorrelation + Band-Trefferquote; unterschritten → kein Rollout |
| `scripts/eval_deep_gold.py` | Gründliche Recherche gegen handgeprüfte Pflichtfakten und verbotene Fehlbehauptungen (`eval/cases_deep_gold.json`); trennt Material (las der Bericht die Belegstelle?) von Bericht (steht der Fakt drin?) | Abdeckung < 60 %, Kernfakt fehlt oder eine verbotene Behauptung → nicht bestanden |
| `eval/run_cities_transfer.py` | Einordnung fremder Ratsvorlagen (`cities_classify`) | „taugt/taugt nicht" unter 80 % → Regression |
| `eval/run_cities_fit.py` | Urteil über Oldenburg (`cities_fit`) | Beleg-Disziplin unter 100 % → Regression |
| `eval/run_cities_sections.py` | Schnitt der Niederschriften (ohne Modell) | unter 75 % der Tagesordnungspunkte mit Abschnitt → Regression |
| `eval/run_cities_reason.py` | Das „Warum" aus der Niederschrift (`cities_reason`) | **eine** erfundene Begründung → Regression |
| `eval/run_cities_idea_fit.py` | Urteil je Idee über Oldenburg (`cities_idea_fit`) | eine erfundene Kennung oder ein falsches „vorhanden" → Regression; Status unter 70 % |

### Warum der Städtevergleich zwei Prüfstände hat

`cities_classify` gibt einer fremden Vorlage ein Etikett und braucht dafür nur
sie selbst. `cities_fit` beantwortet dagegen zwei Fragen über **Oldenburg** —
„hat die Stadt das schon?" und „lohnt ein Antrag?" — und bekommt dafür Belege
aus dem eigenen Bestand mit: die nächsten Oldenburger Vorlagen, Treffer der
Volltextsuche und den Themenfeld-Rückblick.

Die Evaluation prüft zusätzlich die **Gültigkeit der Belege**. Jede vom
Modell genannte Kennung muss im Kontext enthalten sein. Aussagen über
Oldenburg erfordern mindestens eine solche Kennung. Ein erfundener Beleg
macht die Aussage falsch. Deshalb gilt hier als einzigem Maß ein
Schwellenwert von 100 %. Im Betrieb verwirft und zählt
`council/cities/fit.py` solche Antworten.

Beide Evaluationen enthalten ihre Fälle samt Belegen und benötigen keine
Datenbank. Der feste Datensatz macht die Ergebnisse auch bei wachsendem
Oldenburger Bestand vergleichbar.

### Die dritte harte Zusage: kein erfundenes „Warum"

`cities_reason` gibt wieder, was in der Niederschrift einer fremden Sitzung
steht — warum ein Rat so entschieden hat. Das ist das Wertvollste, was der
Vergleich zu bieten hat, und deshalb ist eine **erfundene** Begründung der
teuerste Fehler des ganzen Features: Sie sieht aus wie die beste Information
auf der Seite und ist eine Behauptung über einen echten Ratsbeschluss.

Die Nutzlast trägt dafür ein eigenes Feld: `grounded` — die Selbstauskunft des
Modells, ob im Abschnitt überhaupt eine Begründung steht. Der häufigere Fall
ist „nein"; die meisten Beschlüsse fallen ohne Aussprache. Dann zeigt die
Karte an dieser Stelle nichts. Der Prüfstand zählt `grounded=true` ohne
Begründung im Text wie eine erfundene Beleg-Kennung: Schwelle null.

Die ersten Beispiele im `fit`-Prompt stammten aus dem Evaluationsdatensatz.
Dadurch stieg die Trefferquote, ohne dass die Messung eine bessere
Generalisierung belegte. Der Prompt verwendet jetzt synthetische typische
Beispiele. Keines davon steht in `cases_cities_fit.json`.

`eval_impact.py` ist der erste Schritt des Ops-Workflows für die Tragweite: Nur
wenn das Gate hält, startet der Voll-Backfill. Siehe
[Bewertungs-Scores](/docs/bewertungen/) und [Betrieb](/docs/betrieb/).
