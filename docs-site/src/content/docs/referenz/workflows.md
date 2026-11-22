---
title: "Referenz: Workflows"
description: Alle GitHub-Actions-Workflows mit Auslöser und Zweck, erzeugt aus .github/workflows/.
sidebar:
  label: "Workflows"
---

<!-- Erzeugt von scripts/docs_reference.py — nicht von Hand ändern. -->

Diese Seite entsteht aus `.github/workflows/*.yml` (`python scripts/docs_reference.py`). Wer sie von Hand ändert, verliert die Änderung beim nächsten Lauf; `tests/test_docs_current.py` hält sie gegen das Register.

Alles, was GitHub Actions für dieses Repo tut: Prüfungen je Pull Request, die beiden Deploys und die Werkzeuge für den Betrieb, die sich von Hand starten lassen (`Ops: …`). Der Zusammenhang steht unter [Betrieb](/docs/betrieb/#ops-workflows-manuell-auslösbar). Die Spalte „Wozu“ ist der erste Satz des Kommentars am Kopf der Datei.

| Workflow | Auslöser | Wozu |
|---|---|---|
| **Claude (@claude im PR)** (`claude.yml`) | Kommentar, Kommentar an einer Zeile, Review | Code-Review auf Zuruf: Wer in einem Pull Request `@claude` schreibt — als Kommentar, als Review oder als Kommentar an einer Zeile —, bekommt eine Antwort von Claude. |
| **Deploy to Dev** (`deploy-dev.yml`) | Push auf `dev`, von Hand | Dev-Deploy: Jeder Push auf den Branch `dev` deployt auf die Dev-VM (dev.ratslotse.de). |
| **Deploy to VPS** (`deploy.yml`) | Pull Request auf `main` (beim Schließen), von Hand | Der Prod-Deploy: Nur ein gemergter Pull Request nach `main` löst ihn aus. Erst läuft die Testsuite, dann baut der Lauf die Doku, überträgt den Code, startet die Dienste neu und prüft sie mit der Rauchprobe. |
| **Docs-Review (KI)** (`docs-review.yml`) | Pull Request | Prüft bei jedem PR, ob Code-Änderungen die Dokumentation veralten lassen, und postet Vorschläge als PR-Kommentar. |
| **Docs** (`docs.yml`) | Push auf `main`, Pull Request | Baut die Starlight-Doku (docs-site/) bei jedem PR und Push auf main. |
| **Browsertests** (`e2e.yml`) | Pull Request, Push auf `main` | Die Browser-Suite prüft, was keine andere Prüfung sieht: dass die Seiten im Browser wirklich erscheinen und die Wege durch sie funktionieren — Anmelden, Themen anlegen und löschen, eine Tagesordnung aufklappen, eine Frage stellen, eine Antwort bewerten. |
| **Frontend** (`frontend.yml`) | Push auf `main`, Pull Request | Prüft das Next-Frontend bei jedem PR, der es anfasst. |
| **iOS** (`ios.yml`) | Pull Request, Push auf `main`, `dev` | `api/openapi.json` steht bewusst in den Pfaden: Die App liest ihre Felder aus handgeschriebenen `CodingKeys`, und eine Umbenennung im BACKEND erreichte sie auf keinem Weg — dieser Workflow lief nur bei Änderungen unter `ios/`. |
| **Ops: Gescannte Anlagen lesen (dev)** (`ops-anlagen-ocr.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: liest die gescannten Anlagen per Sehmodell (`scripts/backfill_anlagen_ocr.py`) — den GANZEN Bestand, nicht nur die Finanzdokumente. |
| **Ops – Deploy-Rückstand (Prod)** (`ops-deploy-rueckstand.yml`) | Zeitplan (`*/30 * * * *`), von Hand | Holt einen ausgefallenen Prod-Deploy nach — und meldet, wenn das nicht geht. |
| **Ops: Themen-Dubletten zusammenführen** (`ops-entity-dubletten.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: sucht doppelte Themen (derselbe Gegenstand unter mehreren Namen) und führt die vom LLM bestätigten zusammen. |
| **Ops – Erreichbarkeit (Prod)** (`ops-erreichbarkeit.yml`) | Zeitplan (`*/10 * * * *`), von Hand | Prüft von AUSSERHALB der Maschine, ob ratslotse.de antwortet. |
| **Ops: KI-Eval (Frag den Rat)** (`ops-eval-ai.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: misst die KI-Frage gegen das QA-Golden-Set auf der Prod-Datenbank (eval/run_qa.py) — Retrieval-Trefferquote/MRR, Antwort-A/B und Latenz je Pipeline-Schritt. |
| **Ops: Finanzdaten einlesen** (`ops-finanzdaten-ingest.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: liest die Finanzdaten des Haushalts-Bereichs auf der DEV-VM ein und meldet, was danach im Bestand steht. |
| **Ops: KI-Frage stellen** (`ops-frage-probe.yml`) | von Hand | Manuell auslösbar: eine KI-Frage auf dev oder prod stellen und die Antwort samt Quellen im Lauf-Protokoll lesen. |
| **Ops: Gold-Fälle messen** (`ops-gold.yml`) | von Hand | Manuell auslösbar: die Gold-Fälle (eval/cases_deep_gold.json) auf dem Server gegen die echten Daten — für „Frag den Rat“ (scripts/eval_ask_gold.py, über den laufenden Dienst) und/oder die Gründliche Recherche (scripts/eval_deep_gold.py). |
| **Ops: Finanzdaten dev↔prod vergleichen** (`ops-haushalt-vergleich.yml`) | von Hand | Vergleicht die Finanzdaten von dev und Prod — Zahl für Zahl. |
| **Ops: Modelle in der .env** (`ops-modelle.yml`) | von Hand | Manuell auslösbar: Welche Sprachmodelle setzt die .env einer VM? |
| **Ops: Ortskandidaten-Backfill** (`ops-ortskandidaten-backfill.yml`) | von Hand | Manuell auslösbarer, wiederholbarer Datenlauf für redaktionell geprüfte Beschlussorte. |
| **Ops: Argumente je Tagesordnungspunkt** (`ops-punkt-argumente.yml`) | von Hand | Manuell auslösbar: die Argumente je Tagesordnungspunkt für die Punkt-Seite (Reiter „Argumente“/„Fraktionen“, Schalter `punkt-argumente`, Plan docs/plan-punkt-argumente.md) — scripts/punkt_argumente.py auf dem Server. |
| **Ops: Quiz-Backfill** (`ops-quiz-backfill.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: generiert auf dem Server die Quizfragen für alle Gebiete (Stadtteile + große Themen) bis zur Ziel-Fragenzahl. |
| **Ops: Rückblicke regenerieren** (`ops-recaps-regenerieren.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: generiert alle Themenfeld-Rückblicke neu (scripts/generate_field_recaps.py --force). |
| **Ops: Gilt als behandelt (settled)** (`ops-settled-ergebnis.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: „gilt als behandelt" im Bestand auf das eigene Ergebnis `settled` umstellen (`scripts/fix_settled_outcomes.py`) und danach die Kurzfassungen der umgestellten Punkte neu schreiben (`scripts/fix_outcome_summaries.py`). |
| **Ops: Sitzungsorte nachtragen** (`ops-sitzungsorte.yml`) | von Hand | Manuell auslösbarer Ops-Lauf zum Sitzungsort-Fix (#426): trägt die Orte für Bestandssitzungen nach (der Scraper riet sie bis dahin aus der Überschrift, die keinen Ort nennt — alle Sitzungen standen ohne Ort da) und verwirft die gecachten … |
| **Ops: Lottis Sätze zu Sitzungen** (`ops-sitzungssaetze.yml`) | von Hand | Manuell auslösbar: Lottis Satz zur Sitzung für den Bestand nachziehen (scripts/sitzungssaetze.py, council/session_summary.py, Schalter `sitzung-kurs`). |
| **Ops: Stammdaten-Backfill** (`ops-stammdaten-backfill.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: holt auf dem Server die Beratungsfolge aller eingelesenen Vorlagen (vo0053) und die Personen-/Gremien-Stammdaten (Mandatsträger aller Wahlperioden + Mitgliedschaften) nach. |
| **Ops: Straßen vollständig nachtragen** (`ops-strassen-neu.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: Straßen, von denen nur EIN Segment gespeichert ist, vollständig nachtragen. |
| **Ops: Transkriptions-Modelle vergleichen** (`ops-stt-vergleich.yml`) | von Hand | Manuell auslösbar: Audio-Modelle für die Livestream-Transkription an den aufbewahrten Sitzungs-Stücken vergleichen. |
| **Ops: TOP-Kurzfassungen nachgenerieren** (`ops-top-kurzfassungen.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: erzeugt die Kurzfassungen je Tagesordnungspunkt (#449) für alle KOMMENDEN Sitzungen und die letzten N vergangenen nach. |
| **Ops: Tragweite-Rollout** (`ops-tragweite-rollout.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: Tragweite-Score (RL-U16) auf Prod scharf schalten. |
| **Ops: Vorlagen aufbereiten** (`ops-vorlagen-aufbereiten.yml`) | von Hand | Manuell auslösbar: die einmaligen Nachläufe und die crontab-Zeilen des Plans „Vorlagen aufbereiten“ (docs/plan-vorlagen-aufbereiten.md, Schritte 2, 6, 12, 17) — auf dev sofort, auf Prod erst nach dem Release, das die Skripte bringt. |
| **Ops: Vorlagen-Backfill** (`ops-vorlagen-backfill.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: holt alle fehlenden Vorlagen-Volltexte und Anlagen (inkl. Fraktions-Anträge mit Antragsteller-Erkennung) auf dem Server nach und baut anschließend den FTS-Index neu. |
| **Ops – Wartungsbarriere & Generalprobe (Prod)** (`ops-wartungsbarriere.yml`) | von Hand | Notausgang für einen abgebrochenen Deploy. |
| **Ops: Wortbeiträge neu extrahieren** (`ops-wortbeitraege-neu.yml`) | von Hand | Manuell auslösbarer Ops-Lauf: extrahiert die Wortbeiträge des Bestands neu (`scripts/extract_wortbeitraege.py --neu-vor`). |
| **Statusseite veröffentlichen** (`statusseite.yml`) | Push auf `main`, von Hand | Veröffentlicht die Statusseite auf GitHub Pages. |
| **Sync production back to dev** (`sync-main-to-dev.yml`) | Push auf `main`, von Hand | Produktion darf nie dauerhaft Commits enthalten, die im Integrationsbranch fehlen. |
| **Tests** (`test.yml`) | Push auf `main`, Pull Request | Die Prüfungen je Pull Request: Linter, Typprüfung, API-Vertrag und die Testsuite — dasselbe, was `scripts/pruefe.py` lokal vor dem Push fährt. |

37 Workflows unter `.github/workflows/`.
