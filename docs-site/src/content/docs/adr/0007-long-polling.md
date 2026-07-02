---
title: 0007 — Long-Polling statt Webhook
description: Der Telegram-Bot pollte, statt einen Webhook-Endpunkt zu betreiben (abgelöst).
sidebar:
  order: 7
  badge: Abgelöst
---

**Status:** Abgelöst — der Telegram-Bot wurde entfernt; **Web-Push** (APNs/FCM) und
**E-Mail** übernehmen die Benachrichtigungen. Dieser ADR bleibt als historischer
Kontext erhalten.

## Kontext

Der Telegram-Bot muss eingehende Updates empfangen. Telegram bietet zwei Wege:
**Webhook** (Telegram ruft eine öffentliche HTTPS-URL auf) oder **Long-Polling**
(der Bot fragt aktiv `getUpdates` ab). Ein Webhook bräuchte einen öffentlich
erreichbaren, TLS-terminierten Endpunkt nur für den Bot.

## Entscheidung

Der Bot nutzt **Long-Polling** (`getUpdates` mit 30-s-Timeout) in einem
systemd-Service (`nwz-bot`, `scripts/bot_poll.py`).

## Konsequenzen

- **Plus:** Kein öffentlicher Port und keine eingehende Route für den Bot — die
  Angriffsfläche bleibt klein, und das Edge-/Caddy-Setup muss nichts für den Bot
  vorhalten. Lokales Entwickeln funktioniert ohne Tunnel.
- **Plus:** Einfaches Betriebsmodell: ein dauerlaufender Prozess unter systemd,
  Neustart per `systemctl restart nwz-bot`.
- **Minus:** Eine dauerhaft offene Verbindung mit minimaler Latenz beim Poll-
  Intervall; bei sehr hohem Nachrichtenaufkommen wäre ein Webhook effizienter —
  für die aktuelle Nutzerzahl irrelevant.
- **Minus:** `bot_poll.py` muss seine eigene Fehler-/Restart-Resilienz mitbringen
  (grober `except` + `sleep`), da kein externer Aufrufer Retries übernimmt.
