---
title: "Referenz: Eval-Läufe"
description: Alle Messläufe für die Qualität der Modell-Schritte, erzeugt aus den Docstrings unter eval/.
sidebar:
  label: "Eval-Läufe"
---

<!-- Erzeugt von scripts/docs_reference.py — nicht von Hand ändern. -->

Diese Seite entsteht aus `eval/run_*.py` und `scripts/eval_*.py` (`python scripts/docs_reference.py`). Wer sie von Hand ändert, verliert die Änderung beim nächsten Lauf; `tests/test_docs_current.py` hält sie gegen das Register.

Jeder Lauf misst einen Schritt gegen feste Fälle, damit eine Änderung an Prompt oder Modell messbar besser oder schlechter wird. Wie die Läufe aufgebaut sind und wie man Fälle ergänzt, steht unter [Eval-Harness](/docs/eval/). Die Beschreibung je Zeile ist der erste Satz des Docstrings der Datei.

| Lauf | Was er misst |
|---|---|
| `eval/run_akten.py` | Akten-Abdeckung (Benchmark B4 aus docs/plan-akte.md) — ohne Sprachmodell. |
| `eval/run_all.py` | Run every evaluation suite and print an aggregate scoreboard. |
| `eval/run_assistant.py` | Eval für Lottis Erklärungen — deterministisch geprüft, ohne zweites Modell. |
| `eval/run_cities_effort.py` | Trifft der Annotator `effort` die Aufwandsklasse, die ein Mensch vergibt? |
| `eval/run_cities_evidence.py` | Findet die Belegsuche, was ein Mensch als Beleg bezeichnet hat? — ohne Modell. |
| `eval/run_cities_fit.py` | Misst, wie gut ein Modell beurteilt, ob Oldenburg eine fremde Idee schon hat. |
| `eval/run_cities_idea_fit.py` | Trifft `idea_fit` den Stand Oldenburgs je IDEE? |
| `eval/run_cities_list.py` | Sind die zwanzig obersten Einträge zwanzig, die jemand sehen will? |
| `eval/run_cities_reason.py` | Gibt `reason` wieder, was in der Niederschrift steht — oder erfindet es etwas? |
| `eval/run_cities_sections.py` | Wie gut schneidet der Splitter die Niederschriften? — ohne Modell, ohne Kosten. |
| `eval/run_cities_stance.py` | Trifft `stance` die Richtung, die ein Mensch der Vorlage zuschreibt? |
| `eval/run_cities_transfer.py` | Misst, wie gut ein Modell fremde Ratsvorlagen für Oldenburg einordnet. |
| `eval/run_committee.py` | Evaluate the committee-summary routine filter (summarize_agenda). |
| `eval/run_district.py` | Mein Viertel: Erkennt der Richter, ob ein Beschluss wirklich im Viertel liegt? |
| `eval/run_dossier.py` | Messlauf: Dossier je Vorlage gegen eval/dossier_gold.json (Plan Vorlagen § 7.2). |
| `eval/run_ergebnis_texte.py` | Kennen die erzeugten Beschlusstexte das Ergebnis? — buchstäbliche Prüfung. |
| `eval/run_fakten.py` | Fakten-Eval für Lotti und Frag den Rat: Kontextfehler und Modellfehler getrennt. |
| `eval/run_live_tracker.py` | Live-Verfolgung: Erkennt das Modell, welcher Tagesordnungspunkt gerade läuft? |
| `eval/run_locations.py` | Ortszuordnung gegen feste positive und negative Goldfälle messen. |
| `eval/run_motions.py` | Messlauf: Änderungsanträge lesen gegen eval/motions_gold.json (Plan Vorlagen § 7.3). |
| `eval/run_ortserkennung.py` | Ortserkennung der KI-Frage: Wortabgleich allein gegen Wortabgleich plus Auswahl durch das Analyse-Modell (`qa._ortsblock`). |
| `eval/run_punkt_argumente.py` | Argumente zum Tagesordnungspunkt — die Messung vor dem Ausrollen. |
| `eval/run_punkt_bezug.py` | Wirkt der Punkt-Bezug? — Messung aus Schritt 4.5 der Sitzungsseite. |
| `eval/run_qa.py` | Eval-Suite fuer die KI-Frage ("Frag den Stadtrat"). |
| `eval/run_qa_answer.py` | KI-Frage: nur das ANTWORT-Modell, mit festem Kontext — lokal lauffähig. |
| `eval/run_qa_routing.py` | Gold-Suite für Analyse, Recherchekanäle und Haushalts-Facetten der KI-Frage. |
| `eval/run_selbstpruefung.py` | Kalibrierung von Lottis Selbstprüfung — trifft der Prüfer, was wir schon wissen? |
| `eval/run_sitzung_satz.py` | Lottis Satz zur Sitzung: gerechnet gegen vom Modell geschrieben, an echten vergangenen Sitzungen (Tims Wunsch 11.11.2026: „möglichst natürlich“). |
| `eval/run_social.py` | Social-Karten: der Kartentext und sein Kritiker, je eine Suite. |
| `eval/run_speeches.py` | Wortbeiträge: Findet das Modell alle Redner\*innen eines Protokollabschnitts? |
| `eval/run_speeches_protokolle.py` | Wortbeiträge an GANZEN Niederschriften: Wer fehlt, wem wird was zugeschrieben? |
| `eval/run_spezialleser.py` | Messlauf: Spezialleser gegen eval/spezialleser_gold.json (Plan Vorlagen, Schritt 17). |
| `eval/run_stt.py` | Transkription des Sitzungs-Mitschnitts — die Suite, der das Audio fehlt. |
| `eval/run_video.py` | Video-Ergebnisse: Liest das Modell die Abstimmungen richtig aus dem Transkript? |
| `eval/run_watcher.py` | Evaluate the council watcher's agenda→topic matching (_classify_agenda). |
| `eval/run_zuordnung.py` | Zuordnung Antrag ↔ Teilabstimmung ohne Modell (Plan Vorlagen § 7.3): bis zu 30 Anträge an Punkten mit Teilabstimmungen; jede getroffene Zuordnung wird zur Handprüfung ausgegeben (Label gegen Titel), dazu die Trefferquote. |
| `scripts/eval_agenda_impact.py` | Wochen-Karte gegenprüfen: Wen hätte sie hervorgehoben — und wen jetzt? |
| `scripts/eval_ai.py` | Score the AI features against the fixed gold set in `tests/eval/\*.jsonl`. |
| `scripts/eval_ask_gold.py` | Gold-Fälle für „Frag den Rat“: dieselben Fälle wie die Gründliche Recherche. |
| `scripts/eval_deep_gold.py` | Gold-Fälle für die Gründliche Recherche: Faktenliste statt A/B-Gefühl. |
| `scripts/eval_impact.py` | Golden-Set-Prüfung für den Tragweite-Score (RL-U16). |

41 Läufe.
