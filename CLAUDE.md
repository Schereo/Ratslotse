# Ratslotse

Macht die Arbeit des **Oldenburger Stadtrats** durchsuchbar, vergleichbar und
verständlich — über ein Web-Frontend ([ratslotse.de](https://ratslotse.de)) mit
Web-Push- und E-Mail-Benachrichtigungen. Aus dem amtlichen Ratsinformationssystem,
per LLM aufbereitet.

> Diese Datei ist die Kurz-Orientierung für Contributor:innen und Coding-Agents.
> Ausführliche Technik-Doku: [ratslotse.de/docs](https://ratslotse.de/docs)
> (Quelle in `docs-site/`).

## Repo-Struktur

| Pfad | Inhalt |
|------|--------|
| `council/` | Stadtrat-Scraper (SessionNet/Bürgerinfo), Protokoll-Parsing, LLM-Klassifikation, Watcher |
| `nwz/` | Geteilte Infrastruktur: LLM-Client (`llm.py`), SQLite-Store (`store.py`), E-Mail, Push, Prompts. *(Der Paketname `nwz/` ist historisch.)* |
| `scripts/` | Cron-Jobs & Ops-Tools (`check_*.py`, `daily_digest.py`, `weekly_enrich.py`, …) |
| `web/backend/` | FastAPI-Backend (uvicorn) |
| `web/frontend/` | Next.js-Frontend (+ Capacitor für iOS/Android) |
| `docs-site/` | Astro-Starlight-Technik-Doku |
| `eval/` | Eval-Harness für die LLM-Qualität |

## Zum Paketnamen `nwz/`

Der Paketname `nwz/` ist historisch und enthält heute nur noch geteilte
Infrastruktur (LLM-Client, Store, E-Mail, Push, Prompts). Auf Beschluss-Seiten
gibt es einen Link zur NWZonline-Suche nach dem jeweiligen Thema
(`web/frontend/components/nwz-link.tsx`).

## Lokale Entwicklung

```bash
# Backend (FastAPI)
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -r web/backend/requirements.txt
cd web/backend && ../../.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (Next.js)
cd web/frontend && npm install && npm run dev      # :3000, /api/* → Backend

# Technik-Doku (Astro Starlight, Node ≥ 22)
cd docs-site && npm install && npm run dev

# Tests
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest tests/ -q
```

Zwei SQLite-DBs unter `data/` (gitignored): `nwz.sqlite` (Konten, Themen, Prompts)
und `council.sqlite` (Sitzungen, Beschlüsse). Beide werden lokal beim ersten Lauf
angelegt.

## Deployment

Gehostet auf einem eigenen VPS (privat). **Nur ein gemergter Pull Request nach
`main`** löst die Deploy-Action aus (`.github/workflows/deploy.yml`, Trigger
`pull_request: types:[closed]` + `merged == true`) — ein direkter Push auf `main`
deployt **nicht**. Die Action baut die Doku, rsync't den Code auf den Server (via
SSH-ProxyJump, Ziel-Hosts als GitHub-Secrets) und startet die systemd-Services neu.
Nicht überschrieben werden `.env`, `data/`, `.venv/`.

**GitHub-Secrets:** `SSH_PRIVATE_KEY` (Deploy-Key), `VPS_HOST`, `VPS_PROXY_HOST`,
`VPS_USER`, `VPS_SSH_PORT`, `ANTHROPIC_API_KEY` (für `docs-review.yml`).

## `.env` (nur auf dem Server, nicht im Repo)

```
OPENROUTER_API_KEY=...
WEB_JWT_SECRET=...                   # Signiergeheimnis für Session-Tokens
WEB_ADMIN_EMAIL=...                  # diese E-Mail wird bei Registrierung Admin
CORS_ORIGINS=https://ratslotse.de
RESEND_API_KEY=...                   # E-Mail-Versand (Resend), sending-only Key
EMAIL_FROM=Ratslotse <noreply@ratslotse.de>
APP_BASE_URL=https://ratslotse.de
FEEDBACK_EMAIL=...                   # Empfänger des Nutzer-Feedbacks
ALERT_EMAIL=...                      # Cron-Fehler-Alarme (Fallback: WEB_ADMIN_EMAIL)
FASTEMBED_CACHE_PATH=~/.cache/fastembed  # persistenter Modell-Cache (sonst /tmp → weg beim Reboot)
BACKUP_RSYNC_TARGET=user@host:pfad/  # optional: Off-Site-Mirror der DB-Backups
BACKUP_RSYNC_SSH_PORT=22             # SSH-Port des Backup-Ziels
# Stadtrat-LLM (optional, Defaults greifen)
COUNCIL_PROTOCOL_MODEL=deepseek/deepseek-v4-pro
COUNCIL_TOPIC_MODEL=deepseek/deepseek-v4-pro
COUNCIL_GOAL_MODEL=deepseek/deepseek-v4-pro
COUNCIL_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
COUNCIL_RECAP_MODEL=deepseek/deepseek-v4-pro
# OpenRouter Provider-Routing (DSGVO) — schließt China-Anbieter aus, verlangt ZDR
NWZ_OPENROUTER_ROUTING=on            # "off" = Notausschalter
NWZ_OPENROUTER_IGNORE=deepseek,baidu,streamlake,siliconflow,alibaba
NWZ_OPENROUTER_ZDR=1                 # "0" lockert die Zero-Data-Retention-Pflicht
```

## Wissenswertes

- **Cron-Jobs** (auf dem Server): `backup_db.py` (täglich, mit optionalem
  Off-Site-Mirror per `BACKUP_RSYNC_TARGET`), `check_committees.py`,
  `check_council.py`, `check_protocols.py` (Protokolle → Beschluss-Klassifikation;
  lädt außerdem Vorlagen-Volltexte nach — Sachverhalt/Begründung für
  Beschluss-Seiten, KI-Frage und FTS, `council/vorlagen.py`),
  `weekly_enrich.py` (wöchentliche LLM-/Embedding-Backfills: Entitäten, Geocoding,
  Embeddings, Themen↔Beschlüsse, Themenfeld-Rückblicke). Alle laufen in
  `run_guarded` (`nwz/alerts.py`): Ein Crash wird geloggt **und** per E-Mail an
  `ALERT_EMAIL`/`WEB_ADMIN_EMAIL` gemeldet.
- **„Ähnliche Beschlüsse"** (`scripts/embed_decisions.py`): berechnet semantische
  Nachbarn per **fastembed** (ONNX, kein torch) — bewusst **nicht** in
  `requirements.txt`, damit Deploy + Web-Service unberührt bleiben.
- **Zustellung**: Nutzer wählen pro Konto `email` / `push` / `both`
  (`web_users.delivery_channel`). E-Mail über Resend (`nwz/email.py`), Push über
  APNs/FCM (`nwz/push.py`); ohne `RESEND_API_KEY` wird E-Mail still übersprungen.
- **Prompts** liegen in `nwz/prompts.py` (DB-Tabelle `prompts`) und sind über das
  Admin-UI live editierbar — Defaults greifen, solange kein Override existiert.
- **Sicherheit**: Der Reverse-Proxy setzt `X-Forwarded-For` selbst
  (verhindert Rate-Limit-Bypass via XFF-Spoofing).
