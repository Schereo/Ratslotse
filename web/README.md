# Webanwendung

Ratslotse verbindet ein Next.js-Frontend mit einem FastAPI-Backend. Backend und
Betriebsskripte verwenden dieselben Python-Pakete und SQLite-Datenbanken.

## Aufbau

```text
Browser → Caddy (HTTPS) → Next.js
                           └── /api/* → FastAPI → ratslotse.sqlite / council.sqlite
```

- `frontend/`: Next.js mit App Router und Tailwind; API-Zugriffe über `lib/api.ts`.
- `backend/`: FastAPI; nutzt `kern/` und `council/` aus dem Repository-Root.
- `../api/openapi.json`: versionierter Schnittstellenvertrag. Daraus werden die
  Frontend-Typen erzeugt.

Next.js leitet API-Anfragen an das Backend weiter. Die native iOS-App spricht
mit der API direkt; für ihre Streaming-Anfragen gelten die Hinweise in der
[iOS-Anleitung](../ios/README.md#streaming-und-produktiver-proxy).

## Lokal entwickeln

Die vollständige Einrichtung steht im [Beitragsleitfaden](../CONTRIBUTING.md#lokal-einrichten).
Nach der Installation startest du das Backend vom Repository-Root aus:

```bash
.venv/bin/python scripts/dev.py start
```

Der Starter gibt den Frontend-Befehl mit dem gewählten Backend-Port aus.
Führe ihn in einem zweiten Terminal unter `web/frontend/` aus. Setze zusätzlich
`BACKEND_URL` auf dieselbe Adresse, damit auch der Next.js-Proxy und seine
Streaming-Routen das richtige Backend erreichen.

Eigene Backend-Prozesse lassen sich mit `scripts/dev.py status` und
`scripts/dev.py stop` verwalten. Belegte Ports anderer Arbeitskopien bleiben
unangetastet.

## Konten und Berechtigungen

Die Anmeldung unterstützt E-Mail und Passwort sowie Sign in with Apple.
Web-Sitzungen verwenden ein HttpOnly-Cookie; die native App verwendet ein
Bearer-Token. Rollen und Rechte stehen zentral in `kern/roles.py`.

Die Registrierung selbst vergibt keine Adminrechte. Die bestätigte Adresse aus
`WEB_ADMIN_EMAIL` erhält sie nur, wenn noch kein Admin existiert. Ohne
E-Mail-Versand kann ein vorhandenes Konto über `scripts/grant_admin.py`
berechtigt werden. Neue Konten werden bei eingerichtetem Mailversand durch
E-Mail-Bestätigung aktiviert; ohne Mailversand entfällt dieser Schritt.

Prompts liegen in `kern/prompts.py`. Der Adminbereich verwaltet unter anderem
Konten, Rollen und Betriebsinformationen; Prompts werden im Code geändert.

## Konfiguration

Die lokale `.env` im Repository-Root und `web/frontend/.env.local` werden nicht
eingecheckt. Für den Server wird die Konfiguration getrennt gepflegt.

| Variable | Zweck |
| --- | --- |
| `WEB_JWT_SECRET` | Signiergeheimnis für Sitzungen; auf dem Server einen eigenen zufälligen Wert verwenden |
| `WEB_ADMIN_EMAIL` | Adresse für die erstmalige Admin-Einrichtung |
| `COOKIE_SECURE` | Cookie nur über HTTPS senden; für lokale HTTP-Entwicklung gegebenenfalls `false` |
| `CORS_ORIGINS` | Erlaubte Browser-Origins |
| `RATSLOTSE_DB`, `COUNCIL_DB` | Pfade zu den Datenbanken; standardmäßig unter `data/` |
| `RATSLOTSE_SQLITE` | Datenbankpfad des Kosten-Trackings; bei abweichendem Kontenpfad ebenfalls setzen |
| `BACKEND_URL` | Backend-Ziel des Next.js-Proxys und seiner Streaming-Routen |
| `NEXT_PUBLIC_API_BASE` | API-Basis für direkte Client-Zugriffe; der Starter nennt den passenden Wert |

Weitere Einstellungen stehen in `backend/app/config.py` und in der
[Betriebsdokumentation](https://ratslotse.de/docs/betrieb/).

## Deployment auf app-server (einmalige Einrichtung)

1. **Node installieren** (für das Frontend) — **systemweit** (z. B. NodeSource
   Node 22 LTS). Wichtig: kein nvm, sonst findet der nicht-interaktive
   SSH-Build der GitHub-Action `node`/`npm` nicht im `PATH`.
2. **Backend-Deps** in das bestehende venv: `cd ~/app && .venv/bin/pip install -r web/backend/requirements.txt`
3. **Frontend bauen**: `cd ~/app/web/frontend && npm ci && npm run build`
4. **Secrets** in `~/app/.env` ergänzen: `WEB_JWT_SECRET` (zufällig), `WEB_ADMIN_EMAIL`.
   Danach mit dieser Adresse registrieren und die Bestätigungsmail anklicken —
   das macht sie zum Admin. Ohne `RESEND_API_KEY` stattdessen einmalig
   `cd ~/app && .venv/bin/python scripts/grant_admin.py <adresse>`.
5. **systemd-Units** kopieren (als root):
   `cp deploy/nwz-web-api.service deploy/nwz-web-frontend.service /etc/systemd/system/`
   dann `systemctl daemon-reload && systemctl enable --now nwz-web-api nwz-web-frontend`
6. **Reverse-Proxy: Caddy auf der Edge-VM** (kein lokales nginx auf app-server).
   In `/etc/caddy/Caddyfile` auf `edge-vm` einen Block ergänzen, der die
   Domain auf `app-server:3000` proxyt, dann `systemctl reload caddy`:
   ```caddyfile
   ratslotse.de {
       reverse_proxy <app-server>:3000 {
           header_up X-Forwarded-For {http.request.remote.host}
       }
   }
   ```
   Caddy holt das TLS-Zertifikat automatisch. Das `header_up` ist
   **sicherheitskritisch** (sonst lässt sich `X-Forwarded-For` spoofen und der
   Rate-Limiter umgehen) — nicht entfernen.
7. **Passwordless sudo** (`/etc/sudoers.d/tim-nwz`) um die neuen Services ergänzen:
   ```
   tim ALL=(ALL) NOPASSWD: /bin/systemctl stop nwz-web-api, /bin/systemctl start nwz-web-api, /bin/systemctl restart nwz-web-frontend
   ```
   Der Release-Preflight prüft diese drei exakten Befehle vor dem ersten
   Dateitransfer über die ausführliche Policy-Ausgabe von `sudo -n -ll`
   (benötigt sudo 1.9.15 oder neuer) und verlangt dort ausdrücklich
   `!authenticate`; weiter gefasste Service-Rechte sind nicht erforderlich.

Danach übernimmt die GitHub Action (`deploy.yml`) bei jedem Merge auf `main`
automatisch: rsync, Backend-Deps, `npm ci && npm run build`, Service-Restart.
