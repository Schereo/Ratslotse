# Deployment on a Proxmox VPS

This guide sets up the NWZ scraper + council watcher on a bare-metal Linux server running Proxmox, using an **LXC container** (lighter than a full VM) and **systemd** for process management.

---

## 1. Create an LXC Container in Proxmox

In the Proxmox web UI (`https://<your-server-ip>:8006`):

1. **Node → CT → Create CT**
2. Settings:
   - **Template**: Ubuntu 22.04 or Debian 12
   - **Disk**: 8 GB is plenty
   - **CPU**: 1 core
   - **Memory**: 512 MB RAM (1 GB if you want headroom)
   - **Network**: DHCP or a static IP on your bridge (e.g. `vmbr0`)
   - **Unprivileged container**: yes
3. Start the container and open a shell (Console tab or `pct enter <vmid>`).

---

## 2. Base OS Setup

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git curl
```

Create a non-root user:

```bash
useradd -m -s /bin/bash nwz
```

---

## 3. Transfer the Project

**Option A — git** (if you push it to a private repo):

```bash
su - nwz
git clone https://github.com/youruser/kommunalwahl-scraper.git ~/app
```

**Option B — rsync** from your dev machine:

```bash
rsync -av --exclude '.venv' --exclude 'data' --exclude '.env' \
  /path/to/kommunalwahl-scraper/ nwz@<vps-ip>:~/app/
```

---

## 4. Python Environment

```bash
su - nwz
cd ~/app
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## 5. Create the `.env` File

```bash
cat > ~/app/.env << 'EOF'
NWZ_USERNAME=mueller-sigl@gmx.de
NWZ_PASSWORD=Tim1997UNDbirte1
OPENAI_API_KEY=sk-proj-...
TELEGRAM_BOT_TOKEN=8871466953:AAH...
TELEGRAM_CHAT_ID=528411185
EOF
chmod 600 ~/app/.env
```

---

## 6. Create the Data Directory

```bash
mkdir -p ~/app/data
```

Run the initial data fetch to populate the database:

```bash
cd ~/app
.venv/bin/python scripts/fetch_recent.py --folder 8389 --limit 10 --db data/nwz.sqlite
.venv/bin/python scripts/check_council.py
```

---

## 7. Systemd Services

Create the service file as **root** (it runs as the `nwz` user).

### Telegram Bot (command listener)

```bash
cat > /etc/systemd/system/nwz-bot.service << 'EOF'
[Unit]
Description=NWZ Telegram Bot
After=network.target

[Service]
User=nwz
WorkingDirectory=/home/nwz/app
EnvironmentFile=/home/nwz/app/.env
ExecStart=/home/nwz/app/.venv/bin/python scripts/bot_poll.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable --now nwz-bot
systemctl status nwz-bot
```

---

## 8. Cron Jobs

Add daily jobs for the `nwz` user:

```bash
crontab -u nwz -e
```

Paste:

```cron
# NWZ daily digest — 06:30 every morning
30 6 * * * /home/nwz/app/.venv/bin/python /home/nwz/app/scripts/daily_digest.py >> /home/nwz/app/data/digest.log 2>&1

# Council watcher — twice a day (08:00 and 14:00)
0 8,14 * * * /home/nwz/app/.venv/bin/python /home/nwz/app/scripts/check_council.py >> /home/nwz/app/data/council.log 2>&1
```

---

## 9. Firewall (optional but recommended)

```bash
apt install -y ufw
ufw allow OpenSSH
ufw enable
```

---

## Useful Commands

| Task | Command |
|------|---------|
| View bot logs | `journalctl -u nwz-bot -f` |
| Restart after code update | `systemctl restart nwz-bot` |
| Manual digest send | `cd ~/app && .venv/bin/python scripts/daily_digest.py` |
| Manual council check | `cd ~/app && .venv/bin/python scripts/check_council.py` |
| Deploy code update | `cd ~/app && git pull && systemctl restart nwz-bot` |
