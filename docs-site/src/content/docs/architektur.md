---
title: Architektur
description: Überblick über Stadtrat-Scraper, Datenbank, KI-Klassifikation, Bot und Deployment.
---

Ein Scraper für das Oldenburger Ratsinformationssystem speist eine SQLite-Datenbank.
Ein Telegram-Bot übernimmt die Nutzerverwaltung und liefert personalisierte
Benachrichtigungen; ein Web-Frontend (FastAPI + Next.js) sitzt auf denselben Datenbanken.

```
        Oldenburger Stadtrat (SessionNet)
                     │
             council/scraper.py
             council/protocols.py
                     │
              council/store.py
              (council.sqlite)  ── web_users, topics (nwz.sqlite)
                     │
              council/watcher.py
                     │
     nwz/bot_commands.py · scripts/bot_poll.py
                     │
                Telegram API
                     │
                 @RatslotseBot
```

:::note
Ein früherer NWZ-Zeitungs-Scraper wurde aus rechtlichen Gründen in ein separates,
privates Repository ausgegliedert. Im Produkt bleibt nur ein **scraping-freier
NWZonline-Suchlink** zu Beschluss-Themen. Alles Folgende beschreibt die Stadtrat-Seite.
:::

---

## Komponenten

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
zustandslos — kein Fine-Tuning, strukturierte Prompts mit JSON-Mode. Ausschuss-
Zusammenfassung und Topic-Matching laufen auf `gpt-4o-mini`. Die Protokoll-Pipelines
(Beschlussextraktion, Themenfeld-Klassifikation, Rückblicke) nutzen über Env-Variablen
konfigurierbare Modelle (Default: `deepseek/deepseek-v4-pro`, siehe `CLAUDE.md`).

Details, Schwachstellen und Roadmap: siehe [KI-Pipeline](/docs/ki-pipeline/).

### Multi-User-Telegram-Bot (`nwz/bot_commands.py`, `scripts/bot_poll.py`)

Der Bot nutzt **Long-Polling** (`getUpdates` mit 30-s-Timeout) — kein Webhook,
kein offener Port. Nutzer liegen in der Tabelle `users`; nur freigeschaltete
Nutzer können interagieren. Der Admin (über `TELEGRAM_CHAT_ID` in der `.env`)
schaltet Nutzer mit `/freischalten` und `/sperren`. Themen sind pro `chat_id`
isoliert; die Cron-Skripte iterieren über alle Nutzer und versenden personalisierte
Ratsinfo-Benachrichtigungen. Volle Befehlsübersicht: [Telegram-Bot](/docs/bot/).

---

## Datenbankschema

**`nwz.sqlite`** (Konten & Themen — der Paketname `nwz/` ist historisch)

- `web_users` — Web-Konten (E-Mail, Passwort-Hash, Rolle, Status)
- `topics` — Themen-Watchlist pro Nutzer (`owner_id`, `name`, `description`)
- `committee_subscriptions` — Ausschuss-Abos pro Nutzer
- `push_tokens`, `link_codes`, `email_verification_tokens` — App-Push & Konto-Verknüpfung
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
| 07:00 täglich | `check_committees.py` | Ausschuss-Tagesordnungen zusammenfassen |
| 08:00 + 14:00 täglich | `check_council.py` | Stadtratssitzungen auf Themen-Matches prüfen |
| 09:00 täglich | `check_protocols.py` | Protokolle parsen + Beschlüsse klassifizieren |
| 03:00 sonntags | `weekly_enrich.py` | LLM-/Embedding-Backfills |

---

## Deployment

- **App-Server:** `app-server` (private IP `<app-server>`), erreichbar per SSH-Jump über die Edge-VM `edge-vm` (`<edge-host>:<port>`). Vollständige Topologie in `CLAUDE.md`.
- **Prozesse:** systemd — `nwz-bot` (Bot), `nwz-web-api` (FastAPI/uvicorn), `nwz-web-frontend` (Next.js).
- **TLS/Routing:** **Caddy** auf der Edge-VM terminiert TLS und proxyt auf `app-server:3000` (kein lokales nginx).
- **CI/CD:** GitHub Actions. **Nur ein gemergter Pull Request nach `main`** löst den Deploy aus (rsync + Service-Restart + Frontend-Build). Ein direkter Push auf `main` läuft nur durch die Tests und deployt **nicht**.
- **Secrets:** `.env` liegt nur auf dem Server (nicht im Git); der Deploy-SSH-Key ist GitHub-Actions-Secret.

:::tip
Diese Seite ist die Architektur-Übersicht. Die operative Wahrheit (genaue Hosts,
Cron-Zeilen, sudoers, Server-Setup) steht in `CLAUDE.md` im Repo-Root — dort
pflegen, hier nur referenzieren.
:::
