---
title: 0004 — Caddy auf der Edge-VM statt nginx
description: TLS-Terminierung und Reverse-Proxy mit Caddy auf der Edge-VM.
sidebar:
  order: 4
---

**Status:** Akzeptiert (ersetzt das frühere lokale-nginx-Setup)

## Kontext

Der Web-Stack besteht aus FastAPI (`nwz-web-api`, Loopback :8000) und Next.js
(`nwz-web-frontend`, :3000) auf dem App-Server `app-server`. Externe Anfragen
benötigen einen TLS-Endpunkt und eine Weiterleitung an den Next.js-Port.
Früher übernahm das nginx auf `app-server`. Die **Edge-VM** (`edge-vm`)
dient bereits als Eintrittspunkt und SSH-Sprungserver. Die TLS-Terminierung
dort spart eine Proxy-Schicht auf dem App-Server.

## Entscheidung

**Caddy auf der Edge-VM** terminiert TLS (automatische Let's-Encrypt-Zertifikate)
und leitet Anfragen per `reverse_proxy` an `app-server:3000` weiter. Auf
`app-server` ist nginx entfallen. Next.js leitet `/api/*` direkt ans
Backend weiter. Der Caddy-Block setzt
`header_up X-Forwarded-For {http.request.remote.host}`.

## Konsequenzen

- **Plus:** Automatisches TLS ohne certbot-Cron; deutlich kürzere Konfiguration
  als das äquivalente nginx-Setup. Eine Proxy-Schicht weniger auf dem App-Server.
- **Sicherheitskritisch:** Das `header_up X-Forwarded-For` ist Pflicht — ohne es
  ließe sich die Client-IP fälschen und das Anfragelimit umgehen. **Nicht
  entfernen.**
- **Minus:** Die Konfiguration für den externen Zugriff liegt jetzt auf
  der Edge-VM. Änderungen an Domains oder Routing erfolgen dort.
- Die alte `deploy/nginx-nwz-web.conf` wurde entfernt (Cleanup vor Go-Live).
