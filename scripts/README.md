# scripts/

Übersicht aller Skripte und wie sie ausgeführt werden. **Nicht verschieben** —
mehrere Skripte importieren sich gegenseitig per `from scripts.<name> import …`
und die Cron-/systemd-Pfade auf dem Server verweisen auf diese Speicherorte.

## Dauerläufer (systemd)

| Skript | Service | Zweck |
|--------|---------|-------|
| `bot_poll.py` | `nwz-bot` | Telegram-Bot, pollt dauerhaft |

## Geplant (Cron)

Zeitpläne stehen in den jeweiligen Docstrings; maßgeblich ist die laufende
`crontab -l` auf dem Server (Einrichtung: [../CLAUDE.md](../CLAUDE.md)).

| Skript | Schedule | Zweck |
|--------|----------|-------|
| `backup_db.py` | `0 3 * * *` | SQLite-Backup (7 Kopien je DB) |
| `daily_digest.py` | `30 6 * * *` | NWZ-Ausgabe holen, klassifizieren, Digest versenden |
| `check_committees.py` | `0 7 * * *` | Ausschuss-Tagesordnungen prüfen, benachrichtigen |
| `check_council.py` | `0 8,14 * * *` | Stadtratssitzungen auf Themen-Matches prüfen |
| `check_protocols.py` | `0 9 * * *` | Protokolle parsen → ruft die Sub-Steps (s.u.) |
| `session_followup.py` | `0 14 * * *` | NWZ-Nachberichte zu vergangenen Sitzungen |
| `weekly_digest.py` | `0 17 * * 5` | Wöchentlicher NWZ-Überblick (freitags) |
| `weekly_enrich.py` | `0 3 * * 0` | LLM-/Embedding-Backfills → ruft die Sub-Steps (s.u.) |

## Sub-Steps (von einem Cron-Skript aufgerufen, nicht selbst geplant)

`check_protocols.py` importiert und ruft der Reihe nach:
`backfill_protocols.py` · `classify_decisions.py` · `extract_amounts.py` · `track_goals.py`

`weekly_enrich.py` startet per Subprocess:
`extract_entities.py` → `describe_entities.py` → `geocode_entities.py` →
`link_news.py` → `embed_decisions.py` → `match_topics_decisions.py` →
`generate_field_recaps.py`

> `embed_decisions.py` braucht **fastembed** (ONNX), das bewusst **nicht** in
> `requirements.txt` steht. Details: [../CLAUDE.md](../CLAUDE.md) → „Ähnliche Beschlüsse".

## Manuelle Ops-/Backfill-Tools (bei Bedarf von Hand)

| Skript | Wann |
|--------|------|
| `fetch_recent.py` | Die N letzten NWZ-Ausgaben einer Rubrik nachladen |
| `backfill_nwz.py` | NWZ-Artikel über einen Datumsbereich nachladen |
| `reextract_protocols.py` | Beschlüsse neu extrahieren nach Prompt-Änderung |
| `classify_archive.py` | Einmalig: Altartikel nachträglich klassifizieren |
| `build_decisions_fts.py` | Volltext-Index der Beschlüsse neu bauen |
| `seed_demo.py` | Lokale Testdaten erzeugen (Entwicklung) |

## Entwicklung / QA

| Skript | Zweck |
|--------|-------|
| `eval_ai.py` | Regressions-Guard gegen das Gold-Set (siehe [../eval/README.md](../eval/README.md)) |
