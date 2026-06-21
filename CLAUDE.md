# kommunalwahl-scraper

## Infrastruktur

- **Proxmox-Host**: `tk-host` (65.108.8.13, root)
- **Jump-Server**: `tk-edge-vm` (65.108.8.59, User: tim, Port 2102)
- **App-Server**: `tk-nwz` (10.10.10.11, User: tim, Port 2102, via ProxyJump tk-edge-vm) — VM 105 auf Proxmox (`tk-tim-4C16G`)
- SSH-Keys über 1Password-Agent (`~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock`)

## Deployment

Push auf `main` löst automatisch die GitHub Action aus (`.github/workflows/deploy.yml`):

1. Checkout des Repos auf dem GitHub Actions Runner
2. rsync der Dateien auf `tk-nwz:~/app/` (via ProxyJump durch `tk-edge-vm`)
3. `sudo systemctl restart nwz-bot`

Folgende Pfade werden beim rsync **nicht** überschrieben:
- `.env` — Credentials, liegt nur auf dem Server
- `data/` — SQLite-Datenbank und Logs
- `.venv/` — Python-Virtualenv

### Manuell deployen

```bash
rsync -az --delete \
  --exclude '.env' --exclude 'data/' --exclude '.venv/' --exclude '.git/' \
  /Users/tim/Documents/kommunalwahl-scraper/ tk-nwz:~/app/
ssh tk-nwz "sudo systemctl restart nwz-bot"
```

### GitHub Secrets

| Secret | Zweck |
|--------|-------|
| `SSH_PRIVATE_KEY` | Dedizierter Ed25519-Key für GitHub Actions (public key in `authorized_keys` auf `tk-edge-vm` und `tk-nwz`) |

## Server-Setup (einmalig)

Beim Wechsel auf einen neuen Server:

1. `python3.12-venv` installieren (als root via QEMU-Agent: `qm guest exec <vmid> -- apt install -y python3.12-venv`)
2. Dateien per rsync übertragen (s.o.)
3. Venv erstellen: `cd ~/app && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
4. `.env` anlegen: `~/app/.env` (chmod 600) — Vorlage siehe unten
5. `data/`-Verzeichnis anlegen: `mkdir -p ~/app/data`
6. systemd-Service anlegen (als root via QEMU-Agent):
   ```
   /etc/systemd/system/nwz-bot.service
   User=tim, WorkingDirectory=/home/tim/app
   ExecStart=/home/tim/app/.venv/bin/python scripts/bot_poll.py
   ```
7. Passwordless sudo einrichten: `/etc/sudoers.d/tim-nwz`
   ```
   tim ALL=(ALL) NOPASSWD: /bin/systemctl restart nwz-bot, ...
   ```
8. Cron-Jobs für `tim` einrichten:
   - `30 6 * * *` — daily_digest.py
   - `0 7 * * *` — check_committees.py
   - `0 8,14 * * *` — check_council.py
9. Actions-SSH-Key in `authorized_keys` auf **beiden** VMs eintragen (tk-edge-vm + tk-nwz)

## .env Variablen

```
NWZ_USERNAME=...
NWZ_PASSWORD=...
OPENROUTER_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
# Web-Frontend (web/)
WEB_JWT_SECRET=...          # zufälliges Signiergeheimnis für Session-Tokens
WEB_ADMIN_EMAIL=...         # diese E-Mail wird bei Registrierung Admin
TELEGRAM_BOT_USERNAME=RatslotseBot
CORS_ORIGINS=https://ratslotse.de   # erlaubte Origins (Prod-Domain)
```

Credentials liegen in 1Password.

## Web-Frontend (`web/`)

FastAPI-Backend (`web/backend/`) + Next.js-Frontend (`web/frontend/`), läuft auf
`tk-nwz` neben dem Bot. Teilt sich die SQLite-DBs und die Python-Pakete
(`nwz`, `council`, `nwz.prompts`). Details + einmalige Einrichtung: `web/README.md`.

- **Services**: `nwz-web-api` (uvicorn 127.0.0.1:8000), `nwz-web-frontend`
  (next start :3000). Öffentlich über **Caddy auf der Edge-VM** (`tk-edge-vm`),
  das TLS terminiert und auf `tk-nwz:3000` proxyt; Next.js reicht `/api/*` selbst
  ans Backend weiter (kein lokales nginx). Live unter **ratslotse.de**. Der
  Caddy-Block trägt `header_up X-Forwarded-For {http.request.remote.host}`
  (sicherheitskritisch — verhindert Rate-Limit-Bypass via XFF-Spoofing).
- **Deploy**: Die GitHub Action baut bei jedem Merge auf `main` zusätzlich das
  Frontend (`npm ci && npm run build`), installiert Backend-Deps und startet
  `nwz-web-api` + `nwz-web-frontend` neu.
- **sudoers** (`/etc/sudoers.d/tim-nwz`) muss die neuen Services erlauben:
  `systemctl restart nwz-web-api`, `systemctl restart nwz-web-frontend`.
- **Prompts** liegen jetzt in `nwz/prompts.py` (DB-Tabelle `prompts` in `nwz.sqlite`)
  und sind über das Admin-UI live editierbar — Defaults greifen, solange kein Override existiert.
- **Bot-Befehl** `/verbinden <CODE>` verknüpft einen Web-Account mit dem Telegram-Chat.

## Nützliche Befehle

```bash
# Bot-Logs live
ssh tk-nwz "journalctl -u nwz-bot -f"
# Als root (für System-Logs ohne adm-Gruppe)
ssh tk-host "qm guest exec 105 -- journalctl -u nwz-bot -n 50 --no-pager"

# Service-Status
ssh tk-nwz "systemctl status nwz-bot"

# Digest manuell auslösen
ssh tk-nwz "cd ~/app && .venv/bin/python scripts/daily_digest.py"
```
