---
title: Architektur
description: Überblick über Scraper, Datenbank, KI-Klassifikation, Bot und Deployment.
---

Zwei unabhängige Scraper speisen eine gemeinsame SQLite-Datenbank. Ein Telegram-Bot
übernimmt die Nutzerverwaltung und liefert personalisierte Benachrichtigungen; ein
Web-Frontend (FastAPI + Next.js) sitzt auf denselben Datenbanken.

```
NWZ ePaper (Visiolink)          Oldenburger Stadtrat (SessionNet)
        │                                    │
   nwz/api.py                        council/scraper.py
   nwz/parse.py                             │
        │                           council/store.py
   nwz/store.py                     (council.sqlite)
   (nwz.sqlite)                             │
        │                           council/watcher.py
   nwz/classify.py                          │
        │                                   │
        └──────────────┬────────────────────┘
                       │
         nwz/bot_commands.py · scripts/bot_poll.py
                       │
                  Telegram API
                       │
                   @RatslotseBot
```

---

## Komponenten

### NWZ-ePaper-Scraper (`nwz/`)

Die NWZ nutzt die **Visiolink**-Plattform. Es gibt keine öffentliche API — der
Auth-Flow wurde aus dem JavaScript-Bundle der SPA rekonstruiert.

**Auth-Flow:**

1. `POST login.nwzonline.de` → JWT
2. `POST login-api.e-pages.dk/v1/.../publication/{catalog}/user` → Session-Key (30-min-TTL, im Speicher gecacht)
3. `GET front.e-pages.dk/session-cc/{key}/nwz/{catalog}/content/default5.php` → XML mit den vollständigen Artikeltexten

`nwz/parse.py` wandelt das XML in `Article`-Dataclasses (Titel, Untertitel,
Autoren, Rubrik, Fließtext, Seitenzahl). `nwz/store.py` persistiert Ausgaben und
Artikel in SQLite mit einer **FTS5**-Volltexttabelle (Tokenizer
`unicode61 remove_diacritics 2` für deutsche Umlaute).

### Stadtrat-Watcher (`council/`)

Das Ratsinformationssystem (`buergerinfo.oldenburg.de`) läuft auf **SessionNet**
(Somacos GmbH). Auch hier keine API — die Seiten werden mit BeautifulSoup4 gescrapt.

- `session_ids_for_month(year, month)` — scrapt die Kalenderseite (`si0040.php`)
- `fetch_session(ksinr)` — scrapt die Sitzungs-Detailseite (`si0057.php`), parst Kopf (Datum/Zeit/Ort) und Tagesordnungstabelle
- TOPs mit `Ö` sind öffentlich, `N` nicht-öffentlich

`council/store.py` merkt sich, welche Sitzungen bereits gesehen und welche Alerts
schon versendet wurden — das verhindert Doppel-Benachrichtigungen.

### KI-Klassifikation

Die Klassifikation läuft über **OpenRouter** (OpenAI-SDK) und ist bewusst
zustandslos — kein Fine-Tuning, strukturierte Prompts mit JSON-Mode. Der
NWZ-Digest nutzt `gpt-4o` (Pass 1) und `gpt-4o-mini` (Pass 2); Ausschuss-
Zusammenfassung und Topic-Matching laufen auf dem günstigeren `gpt-4o-mini`. Die
neueren Protokoll-Pipelines (Beschlussextraktion, Themenfeld-Klassifikation,
Rückblicke) nutzen über Env-Variablen konfigurierbare Modelle (Default:
`deepseek/deepseek-v4-pro`, siehe `CLAUDE.md`).

Details, Schwachstellen und Roadmap: siehe [KI-Pipeline](/docs/ki-pipeline/).

### Multi-User-Telegram-Bot (`nwz/bot_commands.py`, `scripts/bot_poll.py`)

Der Bot nutzt **Long-Polling** (`getUpdates` mit 30-s-Timeout) — kein Webhook,
kein offener Port. Nutzer liegen in der Tabelle `users`; nur freigeschaltete
Nutzer können interagieren. Der Admin (über `TELEGRAM_CHAT_ID` in der `.env`)
schaltet Nutzer mit `/freischalten` und `/sperren`. Themen sind pro `chat_id`
isoliert; die Cron-Skripte iterieren über alle Nutzer und versenden je einen
personalisierten Digest. Volle Befehlsübersicht: [Telegram-Bot](/docs/bot/).

---

## Datenbankschema

**`nwz.sqlite`**

- `editions` — eine Zeile je geladene ePaper-Ausgabe
- `articles` — vollständiger Artikelinhalt, an `editions` gekoppelt
- `articles_fts` — FTS5-Volltexttabelle (Spiegel von `articles`)
- `topics` — Themen-Watchlist pro Nutzer (`chat_id`, `name`, `description`)
- `users` — freigeschaltete Telegram-Nutzer
- `committee_subscriptions` — Ausschuss-Abos pro Nutzer
- `prompts` — live editierbare Prompt-Overrides (Admin-UI)

**`council.sqlite`**

- `council_sessions` — gescrapte Sitzungs-Metadaten
- `council_agenda_items` — Tagesordnungspunkte je Sitzung
- `council_alerts_sent` — Deduplizierung (`ksinr` + `topic_id`)
- `committee_notifications` — Deduplizierung der Ausschuss-Benachrichtigungen
- `committee_summaries` — gecachte Agenda-Zusammenfassung (`ksinr` + `agenda_hash`)
- `council_protocols`, `council_decisions`, `council_attendance` — Protokoll-Auswertung (siehe [Beschlüsse](/docs/beschluesse/))

---

## Geplante Jobs (Cron)

Die vollständige, maßgebliche Liste steht in `CLAUDE.md` (und gespiegelt in
`scripts/README.md`). Kurzfassung:

| Zeit | Skript | Aufgabe |
|---|---|---|
| 03:00 täglich | `backup_db.py` | SQLite-Backup (7 Kopien je DB) |
| 06:30 täglich | `daily_digest.py` | NWZ-Ausgabe holen, klassifizieren, Digest versenden |
| 07:00 täglich | `check_committees.py` | Ausschuss-Tagesordnungen zusammenfassen |
| 08:00 + 14:00 täglich | `check_council.py` | Stadtratssitzungen auf Themen-Matches prüfen |
| 09:00 täglich | `check_protocols.py` | Protokolle parsen + Beschlüsse klassifizieren |
| 14:00 täglich | `session_followup.py` | NWZ-Nachberichte zu vergangenen Sitzungen |
| 17:00 freitags | `weekly_digest.py` | Wöchentlicher Überblick |
| 03:00 sonntags | `weekly_enrich.py` | LLM-/Embedding-Backfills |

---

## Deployment

- **App-Server:** `tk-nwz` (private IP `10.10.10.11`), erreichbar per SSH-Jump über die Edge-VM `tk-edge-vm` (`65.108.8.59:2102`). Vollständige Topologie in `CLAUDE.md`.
- **Prozesse:** systemd — `nwz-bot` (Bot), `nwz-web-api` (FastAPI/uvicorn), `nwz-web-frontend` (Next.js).
- **TLS/Routing:** **Caddy** auf der Edge-VM terminiert TLS und proxyt auf `tk-nwz:3000` (kein lokales nginx).
- **CI/CD:** GitHub Actions. **Nur ein gemergter Pull Request nach `main`** löst den Deploy aus (rsync + Service-Restart + Frontend-Build). Ein direkter Push auf `main` läuft nur durch die Tests und deployt **nicht**.
- **Secrets:** `.env` liegt nur auf dem Server (nicht im Git); der Deploy-SSH-Key ist GitHub-Actions-Secret.

:::tip
Diese Seite ist die Architektur-Übersicht. Die operative Wahrheit (genaue Hosts,
Cron-Zeilen, sudoers, Server-Setup) steht in `CLAUDE.md` im Repo-Root — dort
pflegen, hier nur referenzieren.
:::
