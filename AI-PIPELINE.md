# KI-Pipeline — Ist-Stand & Verbesserungspotenzial

> Stand: 2026-06-17. Dieses Dokument beschreibt, wie die KI-gestützte Extraktion
> und das Topic-Matching aus **NWZ** (Nordwest-Zeitung) und dem **Ratsinformationssystem**
> (Oldenburger Stadtrat) aktuell funktionieren, ob aktuell Testdaten vorhanden sind,
> und welche Best Practices die Qualität verbessern würden.

---

## 1. Überblick

Die Pipeline-Qualität entscheidet über den Produktwert: Sie bestimmt, wie zuverlässig
relevante Artikel und Tagesordnungspunkte zu den Themen der Nutzer gefunden werden —
bei hoher **Precision** (keine Fehltreffer) *und* brauchbarer **Recall** (nichts Wichtiges verpassen).

Es gibt **drei** LLM-gestützte Teilpipelines, alle über **OpenRouter** (OpenAI-SDK):

| Pipeline | Quelle | Trigger | Modell(e) |
|----------|--------|---------|-----------|
| **NWZ-Digest** | Zeitungsartikel | `daily_digest.py` (06:30), `weekly_digest.py` (Fr) | `gpt-4o` (Pass 1) + `gpt-4o-mini` (Pass 2) |
| **Ratsinfo-Ausschuss-Zusammenfassung** | Tagesordnungen | `check_committees.py` (07:00) | `gpt-4o-mini` |
| **Ratsinfo-Watcher (Topic-Matching)** | Tagesordnungen | `check_council.py` (08:00, 14:00) | `gpt-4o-mini` |
| **Sitzungs-Follow-up** | Ratsinfo → NWZ | `session_followup.py` (täglich) | `gpt-4o-mini` |

Wichtig vorab: **Das Scraping selbst nutzt kein LLM.** NWZ-Artikel werden aus dem
Visiolink-Kiosk-XML geparst (`nwz/parse.py`), Tagesordnungen per BeautifulSoup aus dem
HTML des Bürgerinfo-Portals (`council/scraper.py`). Das LLM kommt **erst beim Matching/
Zusammenfassen** zum Einsatz, nicht bei der Strukturextraktion.

---

## 2. NWZ-Digest-Pipeline (Ist-Stand)

**Code:** `nwz/classify.py`, `scripts/daily_digest.py`, Prompts in `nwz/prompts.py`.

### Ablauf (täglich)

1. `daily_digest.py` baut `NWZClient` (`from_env()`), öffnet `data/nwz.sqlite`.
2. `_backfill_missing()` lädt fehlende Ausgaben der letzten 14 Tage nach.
3. Neueste Ausgabe herunterladen → `parse_publication()` → `Store.save_edition()`.
4. `store.articles_for_date()` → alle Artikel des Tages.
5. **Pro Nutzer**: `recent_context` (Titel der letzten 5 Tage je Thema, für
   Fortsetzungs-Erkennung) zusammenstellen, dann `build_digest(...)`.

### Zwei-Pass-Klassifikation (`build_digest`, `nwz/classify.py:75`)

- **Pass 1 — ein einziger Call über ALLE Themen × ALLE Artikel.**
  Modell `gpt-4o`, `temperature=0`, JSON-Mode, `max_tokens=2048`.
  Artikeltext je auf **900 Zeichen** gekürzt (`_format_articles`, `classify.py:61`).
  Liefert `{"digest":[{topic, articles:[{refid,title,summary,is_continuation}]}]}`.
- **Pass 2 — Verifikation pro Paar** (`classify.py:140`).
  Für **jedes** Kandidaten-Paar (Thema, Artikel) ein eigener Call an
  `gpt-4o-mini` (`_verify_match`, `classify.py:26`), `temperature=0`, JSON-Mode,
  `max_tokens=20`, Text auf **1500 Zeichen** gekürzt. Liefert `{"relevant": bool}`.
  Begründung im Code (`classify.py:140-145`): Pass 1 über-matched breite Themen
  auf Stichworte (z. B. Parteiname auf „grün"); der Einzelcheck filtert das raus.

> **Fail-open:** Schlägt das JSON-Parsing im Verify fehl, wird der Match **behalten**
> (`classify.py:58`). Lässt sich Thema/Artikel nicht auflösen, ebenfalls behalten
> (`classify.py:153`). Das schützt Recall, kann aber Fehltreffer durchlassen.

### Relevanzkriterium (das qualitätstragende Stück)

Liegt im Prompt `nwz_digest_user` (`prompts.py:41-95`). Kernregel: Ein Artikel passt
**nur**, wenn er das Thema *konkret behandelt* oder eine *konkrete, faktische Information*
liefert. Explizit verboten sind: spekulative Bezüge („könnte interessant sein"),
reine Stichwort-Überschneidung, bundesweiter Bezug bei lokal verlangtem Thema, sowie
Nennung einer Organisation/Person, die im Artikel gar nicht vorkommt. Leitsatz:
**„Im Zweifel: NICHT aufnehmen. Lieber kein Treffer als ein falscher."**

### Topic-Qualitäts-Gate

Beim Anlegen eines Themas prüft `_vagueness_hint` (`bot_commands.py:588`) per
`gpt-4o-mini`, ob die Beschreibung zu vage ist, und schlägt eine präzisere vor —
eine *präventive* Maßnahme, um das Matching scharf zu halten.

### Wöchentlich

`build_weekly_digest` (`classify.py:215`) rankt 3–5 Wochen-Highlights via `gpt-4o-mini`
(JSON-Mode, `max_tokens=600`, **keine** Temperatur gesetzt), nur ab ≥3 Quellartikeln.

---

## 3. Ratsinfo-Pipeline (Ist-Stand)

**Code:** `council/scraper.py` (kein LLM), `council/committee_summary.py`,
`council/watcher.py`, `scripts/session_followup.py`.

### A. Ausschuss-Zusammenfassungen (`check_committees.py`, 07:00)

- Ausschussliste aktualisieren, kommende Sitzungen (3 Monate voraus) scannen.
- Pro Sitzung mit Tagesordnung: **SHA-256-Hash der Agenda** (`_agenda_hash`) →
  dient Caching *und* Änderungserkennung (neue vs. geänderte Tagesordnung).
- `summarize_agenda()` (`committee_summary.py:18`): filtert Routine-TOPs +
  „Fragestunde" bereits **im Code** vor (`committee_summary.py:30-36`), dann
  `gpt-4o-mini`, JSON-Mode, `max_tokens=1024`, **keine** Temperatur.
  Ergebnis `{has_content, items:[{number, summary}]}` wird per
  `CouncilStore.save_summary(ksinr, agenda_hash, summary)` **gecacht** —
  das ist der einzige LLM-Output-Cache der gesamten App.

### B. Watcher / Topic-Matching (`check_council.py`, 08:00 & 14:00)

- Pro Nutzer `run_watcher(...)` (`watcher.py:105`); klassifiziert nur **zukünftige**
  Sitzungen mit Agenda, die noch nicht gesehen wurden.
- `_classify_agenda()` (`watcher.py:29`): öffentliche TOPs + nummerierte Themenliste →
  `gpt-4o-mini`, JSON-Mode, `max_tokens=512`, **keine** Temperatur.
  Liefert `{"matches":[{topic_index, item_numbers}]}`. Alerts werden dedupliziert.

### C. Sitzungs-Follow-up (`session_followup.py`)

- Für **vergangene** abonnierte Sitzungen: Keywords im Code extrahieren
  (Regex + Stoppwortliste), per **FTS5-OR-Suche** (`search_any_terms`) NWZ-Artikel
  der Folgetage finden (Recall-Filter), dann `_verify_with_gpt()` (`gpt-4o-mini`,
  JSON-Mode, `max_tokens=512`) als Präzisionsfilter.
- ⚠️ Der Prompt ist hier **inline hartkodiert** (`session_followup.py:101-126`),
  **nicht** in `prompts.py` — also nicht über das Admin-UI editierbar, ohne
  System-Message und ohne Temperatur.

---

## 4. LLM-Integration (Ist-Stand)

| Aspekt | Status |
|--------|--------|
| Provider | OpenRouter via `openai`-SDK, `base_url=…/api/v1` |
| Modelle | `gpt-4o` nur Digest-Pass-1; sonst überall `gpt-4o-mini` |
| Structured Output | **Nur JSON-Mode** (`response_format={"type":"json_object"}`). **Kein** Function-Calling, **kein** JSON-Schema-Enforcement. |
| Parsing | Schlicht `json.loads(...)`. |
| Fehlerbehandlung | Nur `_verify_match` fängt Parse-Fehler ab (fail-open). Alle anderen Call-Sites **können einen Cron-Lauf crashen**. |
| Retry / Backoff / Rate-Limit | **Nirgends.** Kein `tenacity`, keine Sleeps. Einzig `bot_poll.py` hat einen groben `except Exception` + `sleep(5)`. |
| Caching | Nur Ausschuss-Zusammenfassungen (per Agenda-Hash). NWZ dedupliziert nur das *Versenden*, nicht das *Aufrufen*. |
| Client-Konstruktion | In **5** Modulen dupliziert; 3 davon cachen den Client nicht. |
| Kosten-Treiber | Der Pass-2-Verifier macht **N Einzel-Calls** (ein Call pro Kandidatenpaar) — der teuerste Teil. |

---

## 5. Datenbank & Testdaten — Antwort auf die konkrete Frage

**Frage: Hat die Datenbank aktuell Testdaten (ganze Zeitungen, mehrere Ratssitzungen)?**

**Kurz: Nein.**

- Es gibt zwei DBs, beide in `data/` und **gitignored** (nicht eingecheckt):
  `data/nwz.sqlite` und `data/council.sqlite`.
- **Aktueller Stand im Checkout:** Nur `data/nwz.sqlite` existiert (12 KB) und enthält
  **eine einzige Tabelle `prompts` mit 0 Zeilen**. **Keine Artikel, keine Ausgaben,
  keine Ratssitzungen.** `council.sqlite` existiert gar nicht.
- Das Schema *kann* Vollinhalte speichern: `articles.content_html` / `articles.content_text`
  (beide unbegrenztes `TEXT`, `nwz/store.py:37-38`) halten den kompletten Artikeltext;
  `council_sessions` (Schlüssel `ksinr`) + `council_agenda_items` (Schlüssel
  `(ksinr, item_number)`) unterstützen beliebig viele Sitzungen mit ihren TOPs.
- **Realistische Volltexte existieren nur** in `eval/cases.json` (21 handgelabelte Fälle,
  s. u.) — diese laufen aber **an der DB vorbei** direkt in den Klassifikator.
- Die pytest-Tests legen jeweils **frische, leere** Temp-DBs an und fügen winzige
  Inline-Objekte ein (z. B. eine Sitzung `Bauausschuss` mit einem TOP). Die Playwright-
  E2E-Tests faken Daten per HTTP-Route-Mocks im Browser, nicht in der DB.
- In Produktion wird die DB **nur durch Live-Scraping** befüllt (`daily_digest.py`
  scrapt die NWZ-Ausgabe selbst, `check_council.py` den Stadtrat; `fetch_recent.py`
  bzw. `backfill_nwz.py` sind manuelle Nachlade-Tools). Es gibt **kein**
  Seed-/Import-Kommando, das einen realistischen Datensatz (ganze Ausgaben,
  mehrere Sitzungen) lokal lädt.

**Konsequenz:** Um die *DB-gestützte* End-to-End-Pipeline lokal zu testen, müsste man
entweder die Live-Scraper laufen lassen (braucht NWZ- + OpenRouter-Credentials) **oder
einen Seeder schreiben**.

> **Update (Roadmap-Punkt 2 umgesetzt):** `scripts/seed_demo.py` befüllt jetzt beide
> DBs mit realistischen Demo-Daten — 3 ganze NWZ-Ausgaben (10 Volltext-Artikel über
> aufeinanderfolgende Tage) und 4 Ratssitzungen (vergangene + zukünftige, mit TOPs),
> plus einen Demo-Nutzer mit Themen und Ausschuss-Abos. Die Themen sind so gewählt,
> dass das Matching echte True/False-Positives hat (z. B. Stadion-Beschluss vs.
> Handballspiel, lokale Volt-Liste vs. bundesweiter Grünen-Parteitag). Damit lassen
> sich Digest, Watcher, Ausschuss-Zusammenfassung und Follow-up lokal **ohne
> Live-Scraping** durchspielen (LLM-Schritte brauchen weiterhin `OPENROUTER_API_KEY`).
> Aufruf: `python scripts/seed_demo.py [--reset|--clear]`; Ziel-DBs über `NWZ_DB`/
> `COUNCIL_DB` überschreibbar, Demo-Zeilen nutzen reservierte IDs (≥ 900000).

---

## 6. Evaluation (Ist-Stand)

Es **gibt** ein Eval-Harness — ein echter Pluspunkt:

- `eval/run.py` testet `_verify_match()` (den Pass-2-Verifier) gegen `eval/cases.json`.
- `eval/cases.json`: **21 gelabelte Fälle** (10 erwartet-true, 11 erwartet-false),
  je `{id, note, topic, article, expected}` mit synthetischen Oldenburg-Artikeln.
- Metriken: **Precision, Recall, F1** + TP/FP/TN/FN + Liste der Fehlklassifikationen.
  `--save` schreibt ein Zeitstempel-JSON, `--compare` difft gegen den letzten Lauf
  (Regressions-Tracking).
- **Aber:** `eval/results/` enthält nur `.gitkeep` — **kein gespeicherter Baseline-Lauf**.

> **Update (Roadmap-Punkt 1 weitgehend umgesetzt):** Das Eval-Harness wurde zu einem
> Framework mit **vier Suiten** ausgebaut (`eval/harness.py` + Runner + `eval/README.md`):
> `verify` (Pass 2), **`digest`** (Pass 1 + Verify gesamt), **`watcher`** (Tagesordnung →
> Thema) und **`committee`** (Routine-Filter). Digest/Watcher nutzen mengenbasiertes
> Scoring (Precision/Recall/F1 über `(Thema, Artikel)`- bzw. `(Thema, TOP)`-Paare),
> messen also Über- und Unter-Matching zugleich. `python eval/run_all.py` liefert ein
> Scoreboard; `--save`/`--compare` ermöglichen Baseline-Tracking pro Suite.
> Die Harness-Logik und die LLM-Verdrahtung sind in `tests/test_eval_harness.py`
> **offline** (Mock-Klassifikator + Fake-OpenAI-Client, 19 Tests) verifiziert.
> **Offen:** echte Baseline-Zahlen erzeugen (braucht `OPENROUTER_API_KEY`) und den
> jeweils besten Lauf einchecken; Cases mit echten Produktiv-Fehltreffern erweitern.

---

## 7. Schwachstellen / Lücken (zusammengefasst)

1. **Keine lokalen Testdaten / kein Seeder** → die DB-gestützte Pipeline ist lokal
   nicht reproduzierbar testbar (ganze Ausgaben, mehrere Sitzungen fehlen).
2. **Eval-Abdeckung lückenhaft** → nur der Verifier wird gemessen; das eigentlich
   teure & fehleranfällige Pass-1-Matching, der Ratsinfo-Watcher und die
   Zusammenfassungen haben **keinerlei** Qualitätsmessung. Kein eingecheckter Baseline.
3. **Kein Schema-Enforcement** → JSON-Mode garantiert nur *gültiges JSON*, nicht die
   *erwartete Struktur*. Felder können fehlen/umbenannt sein → stille Fehler.
4. **Keine Retries/Backoff** → ein transienter OpenRouter-/Rate-Limit-Fehler crasht
   einen ganzen Cron-Lauf (außer beim Verifier).
5. **Inkonsistente Parameter** → `temperature=0` nur an 3 von ~7 Call-Sites; der
   Follow-up-Prompt ist hartkodiert und nicht admin-editierbar.
6. **Kosten/Latenz** → der N-fache Pass-2-Verifier ist der Hauptkostentreiber; kein
   Caching der NWZ-Klassifikation, kein Prefilter vor Pass 1.
7. **Code-Duplizierung** → OpenRouter-Client an 5 Stellen, 3 ohne Caching.

---

## 8. Best Practices & konkrete Verbesserungsvorschläge

Recherchierte Best Practices für LLM-Klassifikations-/Extraktions-Pipelines, jeweils
auf konkrete Schritte in diesem Repo gemappt.

### 8.1 Strukturierte Ausgabe erzwingen (Schema statt nur JSON-Mode)
**BP:** Schema-geführte Extraktion + strikte Validierung + automatischer Retry bei
Schema-Verletzung sind 2025-Standard (vgl. PARSE, Instructor-Pattern).
**Hier:** Statt `json.loads` ein Pydantic-Modell pro Antwort definieren und entweder
OpenRouters Structured-Outputs (`response_format={"type":"json_schema", …}`) nutzen
oder die Antwort mit Pydantic validieren + bei Fehler **einmal** mit Fehlertext
nachfragen. Das eliminiert Lücke #3 und macht das fail-open in `_verify_match` sauberer.

### 8.2 Eval ausbauen + Baseline einchecken (das Wichtigste) — 🟡 Framework umgesetzt
**BP:** Held-out, handgelabeltes Ground-Truth-Set; Precision/Recall/F1 gegen den Judge;
mindestens ~80 % P/R anstreben; gleiche Judge-Config über Vergleiche hinweg; Baseline
versionieren, um Regressionen zu sehen.
**Hier:**
- ✅ Eval-Sets ergänzt: **Pass-1-Digest**, **Ratsinfo-Watcher**, **Ausschuss-Filter**
  (`eval/cases_*.json` + Runner, mengenbasiertes Scoring). Siehe `eval/README.md`.
- ✅ Save/Compare-Workflow pro Suite (`--save`/`--compare`), Harness offline getestet.
- ⏳ **Offen:** echte `--save`-Baseline pro Suite einchecken (braucht Key).
- ⏳ Fälle aus **echten** False Positives/Negatives wachsen lassen, nicht nur synthetisch.
- ⏳ Eval in CI: bei jedem Prompt-Change `--compare` gegen Baseline (Regressions-Gate).

### 8.3 Realistischer Seeder / Fixture-Datensatz — ✅ umgesetzt
**BP:** Reproduzierbare, realistische Testdaten sind Voraussetzung für End-to-End-Tests.
**Hier:** `scripts/seed_demo.py` schreibt die DB mit **mehreren ganzen NWZ-Ausgaben**
und **mehreren Ratssitzungen samt TOPs** (synthetisch, reservierte IDs ≥ 900000,
idempotent, `--reset`/`--clear`). Damit lassen sich Digest, Watcher und Zusammenfassung
lokal ohne Live-Scraping durchspielen. *Nächster Schritt:* optional einen Teil als
eingefrorene JSON-Fixture aus einem einmaligen Live-Pull ergänzen, um echte
NWZ-/Ratsinfo-Formatierung abzudecken.

### 8.4 Robustheit: Retry/Backoff + zentraler Client
**BP:** Exponentielles Backoff respektiert Rate-Limits ohne Durchsatzverlust.
**Hier:** Einen einzigen `llm_client`-Helper (z. B. `nwz/llm.py`) mit `tenacity`-Retry
(exp. Backoff, nur transiente Fehler) und gecachtem Client. Alle 5 Call-Sites darauf
umstellen → behebt Lücken #4 und #7, ein Cron-Lauf stirbt nicht mehr an einem 429.

### 8.5 Kosten/Latenz senken
**BP:** Mehrstufige Pipelines mit billigem Recall-Filter vor teurer Präzision schlagen
oft das Einzelmodell; Caching/Batching reduziert Kosten.
**Hier:**
- **Prefilter vor Pass 1**: FTS5/Keyword-Vorfilter (existiert schon für `/search` &
  Follow-up) auch im Digest nutzen, um offensichtlich themenfremde Artikel gar nicht
  erst ans Modell zu geben.
- **Pass-2 batchen**: mehrere (Thema, Artikel)-Paare pro Verify-Call bündeln statt N
  Einzel-Calls — deutlich günstiger bei gleicher Logik.
- **NWZ-Klassifikation cachen** analog zum Agenda-Hash (Edition+Topic-Set-Hash).

### 8.6 Konsistenz & Prompt-Hygiene
**BP:** Reproduzierbarkeit erfordert dokumentierte Modelle/Prompts/Parameter; CoT macht
Judges konsistenter.
**Hier:** `temperature=0` an **allen** Klassifikations-Calls setzen; den Follow-up-Prompt
nach `prompts.py` migrieren (admin-editierbar, mit System-Message); Modellnamen zentral
als Konstanten/Config bündeln (statt verteilt hartkodiert).

---

## 9. Priorisierte Roadmap

| Prio | Maßnahme | Aufwand | Wirkung |
|------|----------|---------|---------|
| **1** | 🟡 Eval-Framework (4 Suiten, offline getestet) — **gebaut**; Live-Baseline einchecken offen | M | Macht Qualität überhaupt messbar |
| **2** | ✅ `scripts/seed_demo.py` (ganze Ausgaben + mehrere Sitzungen) — **erledigt** | M | Lokale E2E-Tests der Pipeline |
| **3** | Zentraler LLM-Client mit Retry/Backoff (`tenacity`) | S | Keine Crash-Cron-Läufe mehr |
| **4** | Pydantic-Schema-Validierung der LLM-Antworten | M | Schluss mit stillen Strukturfehlern |
| **5** | `temperature=0` überall + Follow-up-Prompt nach `prompts.py` | S | Konsistenz, Admin-Editierbarkeit |
| **6** | Prefilter + Pass-2-Batching + NWZ-Klassifikations-Cache | M–L | Kosten/Latenz runter |
| **7** | Eval als CI-Regressions-Gate bei Prompt-Changes | S | Schützt vor Prompt-Regressionen |

---

## Quellen (Best-Practice-Recherche)

- [A Guide to LLM Evals — ByteByteGo](https://blog.bytebytego.com/p/a-guide-to-llm-evals)
- [LLM-as-a-judge: a complete guide — Evidently AI](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Best Practices and Methods for LLM Evaluation — Databricks](https://www.databricks.com/blog/best-practices-and-methods-llm-evaluation)
- [Multi-stage LLM Pipelines Can Outperform GPT-4o in Relevance Assessment (arXiv 2501.14296)](https://arxiv.org/pdf/2501.14296)
- [PARSE: LLM-Driven Schema Optimization for Reliable Entity Extraction (arXiv 2510.08623)](https://arxiv.org/pdf/2510.08623)
- [A Survey on LLM-as-a-Judge (arXiv 2411.15594)](https://arxiv.org/pdf/2411.15594)
- [Generate structured output from LLMs with Outlines — AWS](https://aws.amazon.com/blogs/machine-learning/generate-structured-output-from-llms-with-dottxt-outlines-in-aws/)
