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
| `remind_setup.py` | `0 11 * * *` | Eine Erinnerungsmail je Konto mit offener Einrichtung (≥ 48 h) |
| `abendmeldungen.py` | `0 18 * * *` | Vorabend-Erinnerung (täglich) + Wochenüberblick (sonntags), Design 30a |
| `weekly_enrich.py` | `0 3 * * 0` | LLM-/Embedding-Backfills → ruft die Sub-Steps (s.u.) |
| `check_finanzdaten.py` | 14-tägig `30 4 * * 0` | Neue Haushalts-Jahrgänge aus dem Anlagenbestand nachziehen; meldet ausbleibende Jahrgänge |

## Sub-Steps (von einem Cron-Skript aufgerufen, nicht selbst geplant)

`check_protocols.py` importiert und ruft der Reihe nach:
`backfill_protocols.py` · `classify_decisions.py` · `extract_amounts.py` · `track_goals.py` ·
`extract_decision_locations.py` · `geocode_decision_locations.py`

`weekly_enrich.py` startet per Subprocess:
`extract_entities.py` → `describe_entities.py` → `geocode_entities.py` →
`embed_decisions.py` → `match_topics_decisions.py` → `generate_field_recaps.py`

> `embed_decisions.py` braucht **fastembed** (ONNX), das bewusst **nicht** in
> `requirements.txt` steht. Details: [../CLAUDE.md](../CLAUDE.md) → „Ähnliche Beschlüsse".

## Manuelle Ops-/Backfill-Tools (bei Bedarf von Hand)

| Skript | Wann |
|--------|------|
| `grant_admin.py` | Adminrechte an ein **bestehendes** Konto geben (Erst-Einrichtung ohne Mail-Versand, ausgesperrter Admin) |
| `grant_moderator.py` | Ein **bestehendes** Konto idempotent für ausschließlich private Meldungsmoderation aktivieren und verifizieren |
| `reextract_protocols.py` | Beschlüsse neu extrahieren nach Prompt-Änderung |
| `build_decisions_fts.py` | Volltext-Index der Beschlüsse neu bauen |
| `extract_decision_locations.py --full` | Einmaliger Orts-Backfill; danach inkrementell über `check_protocols.py` |
| `geocode_decision_locations.py` | Neue Beschluss-Orte geokodieren sowie stabile Katalog- und Ortsbereichs-IDs ableiten |
| `revalidate_decision_locations.py [--apply]` | Gespeicherte Ortslinks mit aktuellen Präzisionsregeln prüfen/reparieren (Dry-Run-Default) |
| `purge_nwz_data.py` | Gescrapte NWZ-Artikeldaten aus den DBs entfernen (Dry-Run-Default) |
| `ingest_finanzberichte.py`, `ingest_pruefberichte.py` | **Alle** Haushalts-Jahrgänge neu einlesen — der Weg, einen verbesserten Parser über den Bestand zu ziehen. Neue Jahrgänge holt `check_finanzdaten.py` von allein; diese Skripte fassen auch Vorhandenes an |
| `ingest_haushalt.py` | Haushaltsplan eines Jahres von oldenburg.de laden (der Cron lädt bewusst nichts herunter) |
| `check_namensformen.py` | Bericht: Welche Namensformen könnten zu **einer** Person gehören? Schreibt nichts — geprüfte Paare trägt ein Mensch in `council/namensformen.py` ein |

> **Ersten Admin einrichten:** Die Registrierung vergibt keine Rollen. Die Adresse
> aus `WEB_ADMIN_EMAIL` wird zum Admin, sobald sie ihre E-Mail bestätigt hat (und
> nur, solange es noch keinen Admin gibt). Ohne `RESEND_API_KEY` gibt es keinen
> Bestätigungslink — dann nach der Registrierung:
> `.venv/bin/python scripts/grant_admin.py <adresse>`. Das Skript legt nie ein
> Konto an; Exit-Code 1 heißt „Adresse nicht registriert".

> **Moderationskonto einrichten:** Konto zuerst regulär mit einer ausschließlich
> fiktiven QA-Adresse registrieren, dann im Checkout `app-feature` auf dem Server
> `.venv/bin/python scripts/grant_moderator.py <adresse>` ausführen. Das Skript
> legt nie ein Konto an, kann gefahrlos wiederholt werden und verweigert die
> Vergabe außerhalb der freigeschalteten Bürgerportal-Umgebung.

## Entwicklung / QA

| Skript | Zweck |
|--------|-------|
| `eval_ai.py` | Regressions-Guard gegen das Gold-Set (siehe [../eval/README.md](../eval/README.md)) |
| `changelog_schnitt.py` | Versionsschnitt: die Fragmente aus `../changelog.d/` in `../CHANGELOG.md` gießen (`<x.y.z>`, `--trocken`, `--pruefen`). Läuft im Release-PR, nicht per Cron |
