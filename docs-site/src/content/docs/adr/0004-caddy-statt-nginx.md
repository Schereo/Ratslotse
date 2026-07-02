---
title: 0004 — Caddy auf der Edge-VM statt nginx
description: Reverse-Proxy/TLS auf der Edge-VM mit Caddy statt lokalem nginx.
sidebar:
  order: 4
---

**Status:** Akzeptiert (ersetzt das frühere lokale-nginx-Setup)

## Kontext

Der Web-Stack besteht aus FastAPI (`nwz-web-api`, Loopback :8000) und Next.js
(`nwz-web-frontend`, :3000) auf dem App-Server `app-server`. Nach außen muss jemand
TLS terminieren und auf den Next.js-Port proxen. Frühere Variante: lokales nginx
auf `app-server`. Die Topologie hat aber bereits eine **Edge-VM** (`edge-vm`) als
Eintrittspunkt/SSH-Jump — TLS dort zu terminieren ist naheliegender und spart eine
Proxy-Schicht auf dem App-Server.

## Entscheidung

**Caddy auf der Edge-VM** terminiert TLS (automatische Let's-Encrypt-Zertifikate)
und `reverse_proxy`t auf `app-server:3000`. Auf `app-server` läuft **kein** nginx mehr;
Next.js reicht `/api/*` selbst ans Backend weiter. Der Caddy-Block trägt
`header_up X-Forwarded-For {http.request.remote.host}`.

## Konsequenzen

- **Plus:** Automatisches TLS ohne certbot-Cron; deutlich kürzere Konfiguration
  als das äquivalente nginx-Setup. Eine Proxy-Schicht weniger auf dem App-Server.
- **Sicherheitskritisch:** Das `header_up X-Forwarded-For` ist Pflicht — ohne es
  ließe sich der echte Client-IP fälschen und der Rate-Limiter umgehen. **Nicht
  entfernen.**
- **Minus:** Die Public-Facing-Konfiguration lebt nun auf der Edge-VM, nicht beim
  App-Code — beim Domain-/Routing-Change muss man dort ran.
- Die alte `deploy/nginx-nwz-web.conf` wurde entfernt (Cleanup vor Go-Live).
