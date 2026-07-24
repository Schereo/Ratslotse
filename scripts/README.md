# scripts/

Übersicht aller Skripte und wie sie ausgeführt werden. **Nicht verschieben** —
mehrere Skripte importieren sich gegenseitig per `from scripts.<name> import …`
und die Cron-/systemd-Pfade auf dem Server verweisen auf diese Speicherorte.

## Geplant (Cron)

Zeitpläne stehen in den jeweiligen Docstrings; maßgeblich ist die laufende
`crontab -l` auf dem Server (Einrichtung: [../CLAUDE.md](../CLAUDE.md)).

| Skript | Schedule | Zweck |
|--------|----------|-------|
| `backup_db.py` | `0 3 * * *` | SQLite-Backup (7 Kopien je DB) |
| `check_committees.py` | `0 7 * * *` | Ausschuss-Tagesordnungen prüfen, benachrichtigen |
| `check_council.py` | `0 8,14 * * *` | Stadtratssitzungen auf Themen-Matches prüfen |
| `check_protocols.py` | `0 9 * * *` | Protokolle parsen → ruft die Sub-Steps (s.u.) |
| `weekly_enrich.py` | `0 3 * * 0` | LLM-/Embedding-Backfills → ruft die Sub-Steps (s.u.) |

## Sub-Steps (von einem Cron-Skript aufgerufen, nicht selbst geplant)

`check_protocols.py` importiert und ruft der Reihe nach:
`backfill_protocols.py` · `classify_decisions.py` · `extract_amounts.py` · `track_goals.py`

`weekly_enrich.py` startet per Subprocess:
`extract_entities.py` → `describe_entities.py` → `geocode_entities.py` →
`embed_decisions.py` → `match_topics_decisions.py` → `generate_field_recaps.py`

> `embed_decisions.py` braucht **fastembed** (ONNX), das bewusst **nicht** in
> `requirements.txt` steht. Details: [../CLAUDE.md](../CLAUDE.md) → „Ähnliche Beschlüsse".

## Manuelle Ops-/Backfill-Tools (bei Bedarf von Hand)

| Skript | Wann |
|--------|------|
| `grant_admin.py` | Adminrechte an ein **bestehendes** Konto geben (Erst-Einrichtung ohne Mail-Versand, ausgesperrter Admin) |
| `reextract_protocols.py` | Beschlüsse neu extrahieren nach Prompt-Änderung |
| `build_decisions_fts.py` | Volltext-Index der Beschlüsse neu bauen |
| `purge_nwz_data.py` | Gescrapte NWZ-Artikeldaten aus den DBs entfernen (Dry-Run-Default) |

> **Ersten Admin einrichten:** Die Registrierung vergibt keine Rollen. Die Adresse
> aus `WEB_ADMIN_EMAIL` wird zum Admin, sobald sie ihre E-Mail bestätigt hat (und
> nur, solange es noch keinen Admin gibt). Ohne `RESEND_API_KEY` gibt es keinen
> Bestätigungslink — dann nach der Registrierung:
> `.venv/bin/python scripts/grant_admin.py <adresse>`. Das Skript legt nie ein
> Konto an; Exit-Code 1 heißt „Adresse nicht registriert".

## Entwicklung / QA

| Skript | Zweck |
|--------|-------|
| `eval_ai.py` | Regressions-Guard gegen das Gold-Set (siehe [../eval/README.md](../eval/README.md)) |
