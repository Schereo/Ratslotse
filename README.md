# Ratslotse

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Tests](https://github.com/Schereo/Ratslotse/actions/workflows/test.yml/badge.svg)](https://github.com/Schereo/Ratslotse/actions/workflows/test.yml)
[![Live: ratslotse.de](https://img.shields.io/badge/live-ratslotse.de-0764a6)](https://ratslotse.de)

Macht die Arbeit des **Oldenburger Stadtrats** durchsuchbar, vergleichbar und
verständlich — über ein Web-Frontend ([ratslotse.de](https://ratslotse.de)) und
einen persönlichen Telegram-Bot, vollautomatisch und personalisiert.

> **Hinweis:** Eine frühere Integration der Nordwest-Zeitung (Scraping und
> KI-Analyse von Zeitungsartikeln) wurde aus rechtlichen Gründen **entfernt**. Im
> Produkt bleibt nur ein **scraping-freier NWZonline-Suchlink** zu Beschluss-Themen.

---

## Features

### 🏛️ Stadtrat-Alerts
Der Bot überwacht automatisch alle kommenden Stadtratssitzungen. Wenn eines deiner
Themen auf der Tagesordnung steht, bekommst du vorab eine Benachrichtigung mit den
relevanten Tagesordnungspunkten.

### 🔔 Ausschuss-Benachrichtigungen
Abonniere einzelne Ausschüsse (Bauausschuss, Verkehrsausschuss, …). Sobald eine
neue Tagesordnung veröffentlicht wird, bekommst du eine KI-generierte
Zusammenfassung der wichtigsten Punkte. Ändert sich die Tagesordnung nachträglich,
wirst du erneut benachrichtigt.

### 🗳️ Beschlüsse durchsuchen & verstehen
Volltextsuche über alle Beschlüsse, Filter nach Fraktion, Themenfeld und
Geldbeträgen, KI-Fragen in normaler Sprache mit Quellen, Themen-Seiten mit Karten
und Analysen (Parteien, Personen, Finanzen, Trends). Zu jedem Beschluss ein
scraping-freier Suchlink zu NWZonline für Presseberichte.

### 📰 Deine Themen
Lege Themen an (z. B. *„Radwege"*, *„Stadtentwicklung"*). Der Bot meldet sich, sobald
der Rat dazu etwas beschließt — per Telegram oder E-Mail.

---

## Bot-Befehle

### Themen
| Befehl | Funktion |
|--------|----------|
| `/neu Name \| Beschreibung` | Thema hinzufügen |
| `/themen` | Gespeicherte Themen anzeigen |
| `/loeschen ID` | Thema löschen |

### Stadtrat & Ausschüsse
| Befehl | Funktion |
|--------|----------|
| `/ausschuesse` | Alle Ausschüsse anzeigen, per Button abonnieren/kündigen |
| `/pruefen` | Tagesordnungen für abonnierte Ausschüsse jetzt abrufen |

### Info & Admin
| Befehl | Funktion |
|--------|----------|
| `/start`, `/hilfe` | Bot vorstellen / Befehlsübersicht |
| `/verbinden CODE` | Web-Konto (ratslotse.de) mit diesem Chat verknüpfen |
| `/nutzer`, `/freischalten`, `/sperren` | Nutzerverwaltung (Admin) |

---

## Cron-Jobs

| Zeit | Script | Aufgabe |
|------|--------|---------|
| 03:00 täglich | `backup_db.py` | SQLite-Backup (hält die letzten 7 Kopien je DB) |
| 07:00 täglich | `check_committees.py` | Ausschuss-Tagesordnungen prüfen, Abonnenten benachrichtigen |
| 08:00 + 14:00 täglich | `check_council.py` | Stadtratssitzungen auf Themen-Matches prüfen |
| 09:00 täglich | `check_protocols.py` | Neue Sitzungsprotokolle parsen + Beschlüsse klassifizieren |
| 03:00 sonntags | `weekly_enrich.py` | Schwerere LLM-/Embedding-Backfills nachziehen (Themen, Karten) |

> Vollständige Cron-/systemd-Einrichtung: siehe [CLAUDE.md](CLAUDE.md). Beim
> Synchronisieren der Zeitpläne ist die laufende `crontab -l` auf dem Server
> maßgeblich.

---

## Konfiguration

Alle Credentials in `~/app/.env` auf dem Server:

```env
OPENROUTER_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...   # Chat-ID des Administrators
```

Die vollständige Variablenliste (Web-Frontend, E-Mail-Zustellung, LLM-Modelle)
steht in [CLAUDE.md](CLAUDE.md). Die `.env` liegt **nur auf dem Server**, nicht
im Repo.

---

## Web-Frontend

Neben dem Telegram-Bot gibt es ein Web-Frontend unter
**[ratslotse.de](https://ratslotse.de)** (FastAPI + Next.js): Themen verwalten,
Stadtratsbeschlüsse nach Themenfeldern erkunden, KI-Fragen stellen, Analysen und
Karten. Setup und Architektur: [web/README.md](web/README.md).

---

## Technische Details

Technik-Doku unter **[ratslotse.de/docs](https://ratslotse.de/docs)** (Quelle in
`docs-site/`): Architektur, KI-Pipeline und ADRs.

**Stack:** Python 3.12 · SQLite (FTS5) · OpenRouter (LLM-Routing, DSGVO-konform) ·
Telegram Bot API · FastAPI + Next.js · systemd · Caddy · GitHub Actions

---

## Mitmachen

Beiträge sind willkommen! Bitte lies [CONTRIBUTING.md](CONTRIBUTING.md) und den
[Code of Conduct](CODE_OF_CONDUCT.md). Für Sicherheitsprobleme siehe
[SECURITY.md](SECURITY.md).

Lokale Entwicklung (Backend, Frontend, Doku, Tests): siehe [CLAUDE.md](CLAUDE.md).

## Lizenz

[GNU AGPL-3.0](LICENSE) © Ratslotse. Wer den Code betreibt — auch als
Web-Service — muss seine Änderungen unter derselben Lizenz offenlegen.
