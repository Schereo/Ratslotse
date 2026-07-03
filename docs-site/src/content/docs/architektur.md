---
title: Architektur
description: Überblick über Stadtrat-Scraper, Datenbank, KI-Klassifikation, Benachrichtigungen und Deployment.
---

Ein Scraper für das Oldenburger Ratsinformationssystem speist eine SQLite-Datenbank.
Ein Web-Frontend (FastAPI + Next.js) sitzt auf denselben Datenbanken und liefert
personalisierte Benachrichtigungen per E-Mail und Web-Push.

```
        Oldenburger Stadtrat (SessionNet)
                     │
             council/scraper.py
             council/protocols.py
             council/vorlagen.py          ← Vorlagen- & Anlagen-PDFs (ohne LLM)
                     │
              council/store.py
              (council.sqlite)  ── web_users, topics (nwz.sqlite)
                     │
              council/watcher.py
                     │
                nwz/delivery.py
                     │
        E-Mail (Resend) · Web-Push (APNs/FCM)
```

Welche Dokumente im Einzelnen ausgewertet werden und was daraus entsteht, zeigt
die Übersichtsgrafik unter [Ratsdokumente & Beschlüsse](/docs/beschluesse/).

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

### Benachrichtigungen (`nwz/delivery.py`)

Jeder Nutzer wählt pro Konto einen Zustellkanal (`email` / `push` / `both`,
`web_users.delivery_channel`). Die Cron-Skripte iterieren über alle Nutzer mit
Themen und liefern personalisierte Ratsinfo-Benachrichtigungen über
`nwz/delivery.py`: **E-Mail** via Resend (`nwz/email.py`) und **Web-Push** auf die
registrierten App-Geräte via APNs/FCM (`nwz/push.py`). Fehlt das Secret eines
Kanals, wird dieser Kanal still übersprungen.

---

## Datenbankschema

**`nwz.sqlite`** (Konten & Themen — der Paketname `nwz/` ist historisch)

- `web_users` — Web-Konten (E-Mail, Passwort-Hash, Rolle, Status)
- `topics` — Themen-Watchlist pro Nutzer (`owner_id`, `name`, `description`)
- `committee_subscriptions` — Ausschuss-Abos pro Nutzer
- `push_tokens`, `email_verification_tokens` — App-Push & E-Mail-Verifikation
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
- **Prozesse:** systemd — `nwz-web-api` (FastAPI/uvicorn), `nwz-web-frontend` (Next.js).
- **TLS/Routing:** **Caddy** auf der Edge-VM terminiert TLS und proxyt auf `app-server:3000` (kein lokales nginx).
- **CI/CD:** GitHub Actions. **Nur ein gemergter Pull Request nach `main`** löst den Deploy aus (rsync + Service-Restart + Frontend-Build). Ein direkter Push auf `main` läuft nur durch die Tests und deployt **nicht**.
- **Secrets:** `.env` liegt nur auf dem Server (nicht im Git); der Deploy-SSH-Key ist GitHub-Actions-Secret.

:::tip
Diese Seite ist die Architektur-Übersicht. Die operative Wahrheit (genaue Hosts,
Cron-Zeilen, sudoers, Server-Setup) steht in `CLAUDE.md` im Repo-Root — dort
pflegen, hier nur referenzieren.
:::
