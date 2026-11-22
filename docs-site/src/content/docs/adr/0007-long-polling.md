---
title: 0007 — Long-Polling statt Webhook
description: Historische Entscheidung zum Long-Polling des früheren Telegram-Bots.
sidebar:
  order: 7
  badge: Abgelöst
---

**Status:** Abgelöst. Seit der Entfernung des Telegram-Bots übernimmt
Ratslotse die Benachrichtigungen per **Web-Push** (APNs/FCM) und **E-Mail**.
Der ADR dokumentiert die frühere Entscheidung.

## Kontext

Der Telegram-Bot muss eingehende Updates empfangen. Telegram bietet zwei Wege:
**Webhook** (Telegram ruft eine öffentliche HTTPS-URL auf) oder **Long-Polling**
(der Bot fragt aktiv `getUpdates` ab). Ein Webhook bräuchte einen öffentlich
erreichbaren, TLS-terminierten Endpunkt nur für den Bot.

## Entscheidung

Der Bot nutzt **Long-Polling** (`getUpdates` mit 30-s-Timeout) in einem
systemd-Service (`nwz-bot`, `scripts/bot_poll.py`).

## Konsequenzen

- **Plus:** Der Bot benötigt keinen öffentlichen Port und keine eingehende
  Route in Caddy. Das begrenzt die Angriffsfläche. Die lokale Entwicklung
  ist ohne Tunnel möglich.
- **Plus:** Einfaches Betriebsmodell: ein dauerlaufender Prozess unter systemd,
  Neustart per `systemctl restart nwz-bot`.
- **Minus:** Eine dauerhaft offene Verbindung mit minimaler Latenz beim Poll-
  Intervall; bei sehr hohem Nachrichtenaufkommen wäre ein Webhook effizienter —
  für die aktuelle Nutzerzahl irrelevant.
- **Minus:** `bot_poll.py` muss Fehler abfangen und Aufrufe selbst erneut
  versuchen (allgemeiner `except` mit `sleep`). Ein externer Aufrufer
  übernimmt keine Wiederholungsversuche.
