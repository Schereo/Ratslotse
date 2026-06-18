# NWZ-Bot Web

Web-Frontend für die Bot-Capabilities: NWZ-Suche, Ratsinformationssystem,
Themen-Verwaltung und Admin (Prompts & Nutzer). Teilt sich die SQLite-Datenbanken
und die Python-Logik mit dem Bot.

```
Browser
   │
 nginx  (Port 80/443)
   ├── /api/*  → FastAPI  (uvicorn, 127.0.0.1:8000)  ── nwz.sqlite / council.sqlite
   └── /*      → Next.js  (next start, 127.0.0.1:3000)
```

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
  Ratsinformationssystem ist öffentlich und braucht das nicht.)
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
| `TELEGRAM_BOT_USERNAME` | Für die Verbinden-Anleitung im UI | `mein_nwz_bot` |
| `COOKIE_SECURE` | Secure-Flag fürs Session-Cookie. `true` für HTTPS/localhost; nur für Plain-HTTP-Dev auf `false` setzen | `true` |
| `CORS_ORIGINS` | Nur für getrennte Dev-Origins nötig (kommagetrennt) | `http://localhost:3000` |

Die DB-Pfade (`NWZ_DB`, `COUNCIL_DB`) zeigen standardmäßig auf `data/` im
Repo-Root — dieselben Dateien wie der Bot.

## Deployment auf tk-nwz (einmalige Einrichtung)

1. **Node installieren** (für das Frontend), z. B. via nvm oder distro-Paket
   (Node ≥ 18).
2. **Backend-Deps** in das bestehende venv: `cd ~/app && .venv/bin/pip install -r web/backend/requirements.txt`
3. **Frontend bauen**: `cd ~/app/web/frontend && npm ci && npm run build`
4. **Secrets** in `~/app/.env` ergänzen: `WEB_JWT_SECRET` (zufällig), `WEB_ADMIN_EMAIL`, `TELEGRAM_BOT_USERNAME`.
5. **systemd-Units** kopieren (als root):
   `cp deploy/nwz-web-api.service deploy/nwz-web-frontend.service /etc/systemd/system/`
   dann `systemctl daemon-reload && systemctl enable --now nwz-web-api nwz-web-frontend`
6. **nginx**: `deploy/nginx-nwz-web.conf` nach `/etc/nginx/sites-available/nwz-web`,
   `server_name` anpassen, in `sites-enabled` verlinken, `nginx -t && systemctl reload nginx`.
   TLS z. B. mit `certbot --nginx`.
7. **Passwordless sudo** (`/etc/sudoers.d/tim-nwz`) um die neuen Services ergänzen:
   ```
   tim ALL=(ALL) NOPASSWD: /bin/systemctl restart nwz-bot, /bin/systemctl restart nwz-web-api, /bin/systemctl restart nwz-web-frontend
   ```

Danach übernimmt die GitHub Action (`deploy.yml`) bei jedem Merge auf `main`
automatisch: rsync, Backend-Deps, `npm ci && npm run build`, Service-Restart.
