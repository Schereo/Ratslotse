# NWZ-Bot Web

Web-Frontend für die Bot-Capabilities: NWZ-Suche, Ratsinformationssystem,
Themen-Verwaltung und Admin (Prompts & Nutzer). Teilt sich die SQLite-Datenbanken
und die Python-Logik mit dem Bot.

```
Browser
   │  HTTPS
 Caddy (Edge-VM)  ── terminiert TLS, reverse_proxy ──▶  tk-nwz:3000
   │
 Next.js (next start :3000)
   ├── /*      → Frontend-Seiten
   └── /api/*  → FastAPI (uvicorn, 127.0.0.1:8000)  ── nwz.sqlite / council.sqlite
```

In Produktion terminiert **Caddy auf der Edge-VM** (`tk-edge-vm`) TLS und proxyt
auf `tk-nwz:3000`; Next.js reicht `/api/*` selbst ans Backend weiter, das damit
auf Loopback bleibt (nicht öffentlich). Lokal/Dev läuft alles ohne Caddy über
denselben Same-Origin-`/api`-Proxy von Next.

- **Backend** (`web/backend/`): FastAPI. Importiert die bestehenden Pakete
  `nwz` und `council` (Stores, `nwz.prompts`, `classify`). Keine eigene
  Datenhaltung außer den Tabellen `web_users` und `link_codes` in `nwz.sqlite`.
- **Frontend** (`web/frontend/`): Next.js (App Router) + Tailwind. Spricht das
  Backend über einen Same-Origin-`/api`-Proxy an (siehe `next.config.mjs`).

## Auth, Freischaltung & Verknüpfung

- Registrierung/Login per E-Mail + Passwort. Sessions als HS256-JWT in einem
  httpOnly+Secure-Cookie. Passwörter werden mit `scrypt` (stdlib) gehasht.
- Der erste registrierte Account **oder** die Adresse aus `WEB_ADMIN_EMAIL`
  wird automatisch aktiver Admin.
- **Freischaltung durch Admin:** Alle anderen Konten starten als `pending`.
  Bis ein Admin sie unter Admin → Web-Nutzer freischaltet, sehen sie nur einen
  Wartehinweis und haben keinen Zugriff auf Inhalte.
- **Eigene NWZ-Zugangsdaten:** Für die NWZ-Suche muss jeder Nutzer einmalig
  seine eigenen NWZ-Login-Daten hinterlegen. Diese werden live bei der NWZ
  geprüft; gespeichert wird nur ein „verifiziert"-Marker und der Benutzername,
  **nicht das Passwort**. Erst danach sind NWZ-Inhalte zugänglich. (Das
  Ratsinformationssystem braucht keine NWZ-Zugangsdaten, ist aber **nicht**
  anonym öffentlich — jedes freigeschaltete Konto kann es einsehen.)
- **Telegram-Verknüpfung:** Im Frontend unter „Telegram verbinden" einen Code
  erzeugen und dem Bot mit `/verbinden <CODE>` schicken. Themen und
  Ausschuss-Abos sind danach zwischen Web und Bot geteilt.

Onboarding-Reihenfolge: registrieren → Admin schaltet frei → NWZ-Login
verifizieren + Telegram verbinden → voller Zugriff.

## Lokale Entwicklung

Backend:
```bash
cd web/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # liest ../../.env
```

Frontend:
```bash
cd web/frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

## Environment-Variablen (in der bestehenden `.env`)

| Variable | Zweck | Default |
|----------|-------|---------|
| `WEB_JWT_SECRET` | Signiergeheimnis für Session-Tokens — **unbedingt setzen** | `dev-insecure-change-me` |
| `WEB_ADMIN_EMAIL` | Diese E-Mail wird bei Registrierung Admin | – |
| `TELEGRAM_BOT_USERNAME` | Für die Verbinden-Anleitung im UI | `RatslotseBot` |
| `COOKIE_SECURE` | Secure-Flag fürs Session-Cookie. `true` für HTTPS/localhost; nur für Plain-HTTP-Dev auf `false` setzen | `true` |
| `CORS_ORIGINS` | Erlaubte Origins (kommagetrennt). In Prod auf die echte Domain setzen (z. B. `https://ratslotse.de`); same-origin braucht streng genommen kein CORS | `http://localhost:3000` |

Die DB-Pfade (`NWZ_DB`, `COUNCIL_DB`) zeigen standardmäßig auf `data/` im
Repo-Root — dieselben Dateien wie der Bot.

## Deployment auf tk-nwz (einmalige Einrichtung)

1. **Node installieren** (für das Frontend) — **systemweit** (z. B. NodeSource
   Node 22 LTS). Wichtig: kein nvm, sonst findet der nicht-interaktive
   SSH-Build der GitHub-Action `node`/`npm` nicht im `PATH`.
2. **Backend-Deps** in das bestehende venv: `cd ~/app && .venv/bin/pip install -r web/backend/requirements.txt`
3. **Frontend bauen**: `cd ~/app/web/frontend && npm ci && npm run build`
4. **Secrets** in `~/app/.env` ergänzen: `WEB_JWT_SECRET` (zufällig), `WEB_ADMIN_EMAIL`, `TELEGRAM_BOT_USERNAME`.
5. **systemd-Units** kopieren (als root):
   `cp deploy/nwz-web-api.service deploy/nwz-web-frontend.service /etc/systemd/system/`
   dann `systemctl daemon-reload && systemctl enable --now nwz-web-api nwz-web-frontend`
6. **Reverse-Proxy: Caddy auf der Edge-VM** (kein lokales nginx auf tk-nwz).
   In `/etc/caddy/Caddyfile` auf `tk-edge-vm` einen Block ergänzen, der die
   Domain auf `tk-nwz:3000` proxyt, dann `systemctl reload caddy`:
   ```caddyfile
   ratslotse.de {
       reverse_proxy 10.10.10.11:3000 {
           header_up X-Forwarded-For {http.request.remote.host}
       }
   }
   ```
   Caddy holt das TLS-Zertifikat automatisch. Das `header_up` ist
   **sicherheitskritisch** (sonst lässt sich `X-Forwarded-For` spoofen und der
   Rate-Limiter umgehen) — nicht entfernen.
7. **Passwordless sudo** (`/etc/sudoers.d/tim-nwz`) um die neuen Services ergänzen:
   ```
   tim ALL=(ALL) NOPASSWD: /bin/systemctl restart nwz-bot, /bin/systemctl restart nwz-web-api, /bin/systemctl restart nwz-web-frontend
   ```

Danach übernimmt die GitHub Action (`deploy.yml`) bei jedem Merge auf `main`
automatisch: rsync, Backend-Deps, `npm ci && npm run build`, Service-Restart.
