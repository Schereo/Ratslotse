---
title: "Feature: Sitzungsprotokolle & Beschlüsse"
description: Datenmodell und Pipeline der Protokoll-Auswertung.
---

Auswertung der öffentlichen Sitzungsprotokolle (Niederschriften) des Oldenburger
Stadtrats: strukturierte **Beschlüsse**, **Abstimmungen/Fraktionen** und
**Anwesenheit** — durchsuchbar im Web, optional verknüpft mit den Themen der
Nutzer.

## Faktenlage (an echten Protokollen verifiziert)

- Vergangene Sitzungen tragen ein **„Protokoll (öffentlich)"-PDF** (`getfile.php?id=…`),
  erkennbar am Label. Veröffentlicht mit Verzögerung (Tage–Wochen).
- Inhalt pro Protokoll: Metadaten (Protokoll-Nr., Datum, Beginn/Ende), **Teilnehmer
  mit Fraktion**, und pro TOP **Beschlusstext + Abstimmungsergebnis** (einstimmig /
  mehrheitlich bei N Gegenstimmen, welche Fraktion, angenommen/abgelehnt/vertagt).
- **Volumen:** ~8,8 Sitzungen/Monat, Archiv ≥ 2023, ~85–90 % der vergangenen
  Sitzungen haben ein öffentliches Protokoll → **~300–350 Protokolle** für den
  Backfill 2023–heute.
- **Kosten:** LLM-Extraktion ≈ **$0,007/Protokoll** (deepseek-v4-pro, 1 Call/Protokoll)
  → Komplett-Backfill **~$2–3 einmalig**, laufend ~$1/Jahr.

## Datenmodell (`council.sqlite`)

Phase 1 baut drei Tabellen. Sie sind bewusst so geschnitten, dass spätere Features
andocken können (siehe „Forward-looking").

```
council_protocols          -- eine Zeile je verarbeitetem Protokoll
  ksinr PK, document_id, document_url, protocol_nr,
  session_start, session_end, raw_text, n_pages,
  model, extracted_at, status            -- ok | failed

council_decisions          -- eine Zeile je TOP/Beschluss
  id PK, ksinr, position, item_number, title,
  beschluss, outcome,                    -- angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss
  vote,                                  -- einstimmig|mehrheitlich|null
  gegenstimmen, enthaltungen,            -- nullable INTEGER
  factions,                              -- JSON-Array (z.B. ["SPD","CDU","FDP"])
  vorlage_nr, kvonr,                     -- Link zur Vorlage (für später)
  raw_result                             -- Roh-String der Abstimmung

council_attendance         -- eine Zeile je Person je Sitzung
  id PK, ksinr, name, party, role, note  -- role: vorsitz|mitglied|verwaltung|protokoll|gast
```

`raw_text` wird gespeichert, damit wir Protokolle **ohne erneuten Download** mit
besseren Prompts neu auswerten können. Beschlüsse tragen `vorlage_nr`/`kvonr`, damit
sie später mit Vorlagen verknüpfbar sind.

### Forward-looking (NICHT in Phase 1, aber vom Schema vorbereitet)

- **`council_proposals`** (kvonr, vorlage_nr, title, full_text, type) — Vorlagen
  speichern (Scraper hat `fetch_proposal_text`); Beschlüsse linken via kvonr →
  „was wurde vorgeschlagen vs. beschlossen", Volltextsuche in Vorlagen.
- **`council_persons`** — normalisierte Politiker:innen aus `council_attendance`
  → Anwesenheits-Statistik, perspektivisch Abstimmungs-/Wahlverhalten je Person.
- **`council_decision_matches`** (owner_id, topic_id, ksinr, decision_id) — Phase 3:
  Beschlüsse gegen Nutzer-Themen klassifizieren (+ strenger Verify-Pass) →
  „Beschlüsse zu deinen Themen" + Benachrichtigung. Spiegelt `article_topic_matches`.
- **`council_documents`** (ksinr, doc_id, label, type) — alle Anhänge katalogisieren
  (Aushang/Vorlage/Anträge/Protokoll).
- **FTS** auf `council_decisions` (title+beschluss) für schnelle Volltextsuche.

## Pipeline (Phase 1)

Neues Modul **`council/protocols.py`**:

- `find_protocol(ksinr, scraper) -> dict|None` — öffentliches Protokoll-PDF auf der
  Sitzungsseite erkennen (`getfile`-Link mit „Protokoll … öffentlich").
- `extract_pdf_text(url) -> (text, n_pages)` — via `pypdf`.
- `extract_protocol(text, model) -> dict` — **ein LLM-Call** → `{protocol_nr, start,
  end, attendance[], decisions[]}`. Robust gegen deepseek-null-content (Retry/Guard,
  ). **Kein** Themen-Matching hier (das ist per-owner, Phase 3).

**`scripts/backfill_protocols.py`** — Backfill über Datumsbereich (`--since`, Default
`2023-01-01`, `--until`, `--force`, `--delay`): Sitzungen je Monat enumerieren →
vergangene mit öffentlichem Protokoll, die noch nicht verarbeitet sind (`has_protocol`)
→ Download, Extraktion, Speicherung. Idempotent, fehlertolerant pro Protokoll,
Token-/Kostenausweis.

**`scripts/check_protocols.py`** — Cron: kürzlich vergangene Sitzungen auf **neu
veröffentlichte** Protokolle prüfen und nachziehen (z. B. `0 9 * * *`).

`pypdf` kommt in `requirements.txt`.

## Phase 2 (Frontend) — Notiz zur Integration

Statt einer neuen Seite bekommt **`/council` (Ratsinformationssystem) Tabs**:

- **„Sitzungen & Tagesordnungen"** (bestehende TOP-Suche)
- **„Beschlüsse"** (neue Suche: Volltext + Filter Ausschuss / Datum / Ergebnis /
  Fraktion / Thema)

Die Backend-Such-API für Beschlüsse (`search_decisions(...)`) wird bewusst wie die
bestehende `search_sessions(...)` geformt, damit das Frontend dieselben Muster
wiederverwenden kann. Beschluss-Detail kann Anwesenheit + Link zum Protokoll-PDF
und zur Vorlage zeigen.

## Phasen

1. **Daten (dieser PR):** Schema + Extraktionsmodul + Store-Methoden + Backfill/Cron.
   Lokal getestet; Prod-Backfill nach Deploy.
2. **Web:** Tabs auf `/council`, Beschluss-Suche + -Detail, Anwesenheit.
3. **Themen-Tie-in:** Beschlüsse↔Nutzer-Themen (+ Verify-Pass) + Benachrichtigung.
4. **Optional später:** Vorlagen-Texte, Personen-/Fraktions-Statistiken, Redebeiträge.
