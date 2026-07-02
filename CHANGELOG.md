# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Betrieb
- **Cron-Alarme per E-Mail:** Schlägt ein Cron-Job fehl, geht zusätzlich zum
  Log eine E-Mail an `ALERT_EMAIL` (Fallback `WEB_ADMIN_EMAIL`) — bisher waren
  Fehler nach dem Telegram-Aus nur im Server-Log sichtbar. Alle Cron-Skripte
  (auch `check_protocols`, `weekly_enrich`, `backup_db`) laufen jetzt in dieser
  Absicherung.
- **Off-Site-Backups:** `backup_db.py` spiegelt die tägliche 7-Tage-Rotation
  optional per rsync auf einen zweiten Host (`BACKUP_RSYNC_TARGET`) — bisher
  lagen alle Backups nur auf demselben Server.
- **Deploy nur noch mit grünen Tests:** Der Deploy-Workflow führt den
  pytest-Lauf jetzt selbst aus und deployt nur bei Erfolg.

### Geändert
- **Keine Admin-Freischaltung mehr:** Neue Konten sind direkt nach der
  E-Mail-Bestätigung aktiv — niemand wartet mehr auf manuelle Freigabe. Admins
  bekommen weiterhin eine Info-Mail zu neuen Registrierungen und können Konten
  im Admin-Bereich sperren/entsperren (Moderation bleibt möglich).

### Entfernt
- **Telegram-Bot entfernt:** Benachrichtigungen laufen jetzt ausschließlich über
  **Web-Push** (iOS/Android-App) und **E-Mail**. Der Telegram-Bot, die
  Konto-Verknüpfung (`/verbinden`) und die Zustelloption „Telegram" sind weg; die
  Zustellkanäle sind jetzt `email` / `push` / `both`. Bestehende Konten mit Kanal
  „Telegram" werden serverseitig auf E-Mail/Push migriert.

---

*Dieser Changelog beginnt mit dem Open-Source-Release von Ratslotse. Die
Entwicklungshistorie davor ist nicht Teil dieses Repositories.*

[Unreleased]: https://github.com/Schereo/Ratslotse/commits/main
