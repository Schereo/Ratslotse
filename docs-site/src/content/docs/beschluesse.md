---
title: "Feature: Ratsdokumente & Beschlüsse"
description: Welche Dokumente ausgewertet werden — Protokolle, Vorlagen, Anlagen — und das Datenmodell dahinter.
---

Auswertung der öffentlichen Dokumente des Oldenburger Ratsinformationssystems:
**Sitzungsprotokolle** (→ Beschlüsse, Abstimmungen, Anwesenheit), **Vorlagen**
(→ Sachverhalt & Begründung) und **Anlagen** (→ Original-Anträge der Fraktionen
mit Antragsteller-Erkennung) — durchsuchbar im Web, verknüpft mit den Themen
der Nutzer:innen.

![Diagramm: Welche Dokumente Ratslotse auswertet — Sitzungskalender, Protokolle, Vorlagen und Anlagen — und welche Features daraus entstehen](../../assets/dokumente-pipeline.svg)

## Faktenlage (an echten Dokumenten verifiziert)

- Vergangene Sitzungen tragen ein **„Protokoll (öffentlich)"-PDF** (`getfile.php?id=…`),
  erkennbar am Label. Veröffentlicht mit Verzögerung (Tage–Wochen).
- Inhalt pro Protokoll: Metadaten (Protokoll-Nr., Datum, Beginn/Ende), **Teilnehmer
  mit Fraktion**, und pro TOP **Beschlusstext + Abstimmungsergebnis** (einstimmig /
  mehrheitlich bei N Gegenstimmen, welche Fraktion, angenommen/abgelehnt/vertagt).
- **Bestand:** lückenlos **seit Januar 2018** (~100 Sitzungen/Jahr, ~820 Protokolle,
  über 7.700 Beschlüsse). Kalendereinträge ohne veröffentlichtes Protokoll (Absagen)
  sind normal und werden bei jedem Lauf erneut geprüft.
- **Vorlagen** (~5.000) tragen ihren Inhalt **nur im PDF** — die `vo0050`-Seite
  liefert bloß Metadaten (Betreff, Nr., Art). Es gibt **keine Vorlagen-Art
  „Antrag"**: Die Original-Anträge der Fraktionen hängen als **Anlagen-PDFs**
  an den Vorlagen.
- **Kosten:** LLM braucht nur die Protokoll-Extraktion ≈ **$0,007/Protokoll**
  (1 Call/Protokoll) und die Klassifikation. Vorlagen und Anlagen werden **ohne
  LLM** ausgewertet (pypdf + Wortlisten) — ihr Backfill kostet $0.

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

### Vorlagen & Anlagen (`council/vorlagen.py`)

Seither dazugekommen — beide Dokumentklassen werden **ohne LLM** ausgewertet:

```
council_vorlagen           -- eine Zeile je Vorlage (kvonr = SessionNet-Dokument-ID)
  kvonr PK, vorlage_nr, title, art,      -- art: Beschlussvorlage | Berichtsvorlage | …
  document_id, document_url,
  raw_text, n_pages,                     -- pypdf-Volltext (Sachverhalt & Begründung)
  fetched_at, status,                    -- ok | empty | no_pdf | failed
  anlagen_scanned

council_anlagen            -- eine Zeile je Anlage einer Vorlage
  document_id PK, kvonr, label, url,
  is_antrag,                             -- Label-Muster: Antrag/Änderungsantrag/Anfrage
  antragsteller,                         -- JSON, erkannte Fraktionen (Wortlisten, parties_in_text)
  raw_text, n_pages,                     -- Volltext NUR für Anträge
  fetched_at, status                     -- listed | ok | empty | failed
```

- **Beschluss ↔ Vorlage** läuft über `vorlage_nr` (mit Basis-Fallback:
  `22/0348/1` → `22/0348`) — Protokolle liefern nie ein `kvonr`.
- **Antragsteller-Erkennung:** Label zuerst („Antrag der SPD-Fraktion …"), sonst
  erste PDF-Seite; Mehrparteien-Labels („Antrag SPD CDU Grüne FDP") zählen für
  alle. Wortgrenzen verhindern Fehltreffer („Begrünung" ≠ Grüne).
- **Täglicher Rescan** der letzten 45 Tage: Änderungsanträge landen oft erst
  kurz vor der Sitzung auf der Vorlagen-Seite; bereits eingelesene Dokumente
  werden nicht erneut geladen.
- Daraus entstehen: „Aus der Vorlage" + Anlagen-Dossier auf der Beschluss-Seite,
  die **Erfolgsquoten je Fraktion** in der Analyse, Vorlagen-/Antragstext im
  FTS-Index und im Kontext der KI-Frage.

### Forward-looking (vom Schema vorbereitet)

- **`council_persons`** — normalisierte Politiker:innen aus `council_attendance`
  → Anwesenheits-Statistik, perspektivisch Abstimmungs-/Wahlverhalten je Person.
  (Die Personen-/Gremien-Stammdatenseiten des SessionNet sind noch nicht angebunden.)
- **`council_decision_matches`** (owner_id, topic_id, ksinr, decision_id) —
  Beschlüsse gegen Nutzer-Themen klassifizieren (+ strenger Verify-Pass) →
  „Beschlüsse zu deinen Themen" + Benachrichtigung.

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

1. **Daten:** Schema + Extraktionsmodul + Store-Methoden + Backfill/Cron. ✅
2. **Web:** Tabs auf `/council`, Beschluss-Suche + -Detail, Anwesenheit. ✅
3. **Themen-Tie-in:** Beschlüsse↔Nutzer-Themen (+ Verify-Pass) + Benachrichtigung. ✅
4. **Vorlagen & Anlagen:** Volltexte, Antragsteller, Erfolgsquoten. ✅
5. **Offen:** Personen-/Gremien-Stammdaten (kp-Seiten), Redebeiträge.
