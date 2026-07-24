# Ratslotse Web

Web-Frontend: Ratsinformationssystem, Themen-Verwaltung und Admin (Prompts &
Nutzer). Teilt sich die SQLite-Datenbanken und die Python-Logik mit den Cron-Skripten.

```
Browser
   │  HTTPS
 Caddy (Edge-VM)  ── terminiert TLS, reverse_proxy ──▶  app-server:3000
   │
 Next.js (next start :3000)
   ├── /*      → Frontend-Seiten
   └── /api/*  → FastAPI (uvicorn, 127.0.0.1:8000)  ── nwz.sqlite / council.sqlite
```

In Produktion terminiert **Caddy auf der Edge-VM** (`edge-vm`) TLS und proxyt
auf `app-server:3000`; Next.js reicht `/api/*` selbst ans Backend weiter, das damit
auf Loopback bleibt (nicht öffentlich). Lokal/Dev läuft alles ohne Caddy über
denselben Same-Origin-`/api`-Proxy von Next.

- **Backend** (`web/backend/`): FastAPI. Importiert die bestehenden Pakete
  `nwz` und `council` (Stores, `nwz.prompts`). Keine eigene
  Datenhaltung außer der Tabelle `web_users` in `nwz.sqlite`.
- **Frontend** (`web/frontend/`): Next.js (App Router) + Tailwind. Spricht das
  Backend über einen Same-Origin-`/api`-Proxy an (siehe `next.config.mjs`).

## Auth & Aktivierung

- Registrierung/Login per E-Mail + Passwort. Sessions als HS256-JWT in einem
  httpOnly+Secure-Cookie. Passwörter werden mit `scrypt` (stdlib) gehasht.
- **Adminrechte vergibt die Registrierung nicht.** Jedes neue Konto startet als
  `user` — auch die Adresse aus `WEB_ADMIN_EMAIL` und auch das allererste Konto.
  Sonst bekäme Adminrechte, wer die konfigurierte Adresse als Erstes ins
  Formular tippt, ohne je Zugriff auf dieses Postfach nachzuweisen.
  `WEB_ADMIN_EMAIL` wird zum Admin, **sobald sie ihre E-Mail bestätigt hat** —
  und nur, solange es im Deployment noch gar keinen Admin gibt (ein bewusst
  degradiertes oder gesperrtes Konto holt sich die Rechte so nicht zurück).
  Ohne `RESEND_API_KEY` gibt es keinen Bestätigungslink: dann nach der
  Registrierung einmalig auf dem Server
  `.venv/bin/python scripts/grant_admin.py <adresse>` (befördert nur ein
  **bestehendes** Konto, ist idempotent). Auf beides weist das Backend im Log
  hin — bei der Registrierung und bei jedem Start.
- **Aktivierung durch E-Mail-Bestätigung:** Neue Konten starten als `pending`
  und werden mit dem Klick auf den Bestätigungslink (24 h gültig) automatisch
  aktiv — keine manuelle Freischaltung. Admins bekommen eine FYI-Mail und können
  Konten unter Admin → Web-Nutzer:innen jederzeit sperren/entsperren.
  (Ohne konfigurierten `RESEND_API_KEY` — z. B. lokal — sind neue Konten sofort
  aktiv, weil kein Link verschickt werden kann.)

Onboarding-Reihenfolge: registrieren → E-Mail bestätigen → voller Zugriff.

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
| `WEB_ADMIN_EMAIL` | Diese E-Mail wird Admin, sobald sie registriert **und bestätigt** ist (nur solange es keinen Admin gibt); ohne Mail-Versand: `scripts/grant_admin.py` | – |
| `COOKIE_SECURE` | Secure-Flag fürs Session-Cookie. `true` für HTTPS/localhost; nur für Plain-HTTP-Dev auf `false` setzen | `true` |
| `CORS_ORIGINS` | Erlaubte Origins (kommagetrennt). In Prod auf die echte Domain setzen (z. B. `https://ratslotse.de`); same-origin braucht streng genommen kein CORS | `http://localhost:3000` |

Die DB-Pfade (`NWZ_DB`, `COUNCIL_DB`) zeigen standardmäßig auf `data/` im
Repo-Root — dieselben Dateien wie die Cron-Skripte.

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
   tim ALL=(ALL) NOPASSWD: /bin/systemctl restart nwz-web-api, /bin/systemctl restart nwz-web-frontend
   ```

Danach übernimmt die GitHub Action (`deploy.yml`) bei jedem Merge auf `main`
automatisch: rsync, Backend-Deps, `npm ci && npm run build`, Service-Restart.
