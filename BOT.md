# Telegram-Bot – Anleitung

Der Bot (`@RatslotseBot`) arbeitet mit einer **Whitelist**: Nur freigeschaltete
Nutzer können ihn verwenden. Jeder Nutzer hat seine **eigenen** Themen und Abos.

---

## Einen Nutzer hinzufügen

1. Die Person schreibt `@RatslotseBot` ein `/start`.
2. Der Bot antwortet mit ihrer Chat-ID, z. B. `Deine Chat-ID: 123456789`.
3. Du (Admin) schickst dem Bot:
   ```
   /freischalten 123456789 Anna
   ```
4. Der Bot bestätigt dir und schickt Anna eine Willkommensnachricht — sie kann
   den Bot sofort nutzen.

Alternativ verknüpft sich ein bestehendes Web-Konto (ratslotse.de) selbst per
`/verbinden <CODE>` mit dem Telegram-Chat — das ist auch vor der Freischaltung
erlaubt.

---

## Nutzer-Befehle (für alle auf der Whitelist)

| Befehl | Wirkung |
|---|---|
| `/start` | Registrierung / eigene Chat-ID anzeigen |
| `/hilfe` | Befehlsübersicht |
| `/themen` | Eigene gespeicherte Themen anzeigen |
| `/neu <Name> \| <Beschreibung>` | Neues Thema anlegen |
| `/loeschen <ID>` | Thema per ID löschen |
| `/archiv [<ID>]` | Archivierte Artikel-Treffer (alle Themen oder ein Thema) |
| `/suche <Begriff>` | Volltextsuche im Artikel-Archiv |
| `/ausschuesse` | Ausschüsse anzeigen und abonnieren (✅ = abonniert) |
| `/pruefen` | Sitzungsagendas für deine Abos jetzt abrufen |
| `/verbinden <CODE>` | Web-Konto mit diesem Chat verknüpfen |

**Beispiel:**
```
/neu Radwege | Ausbau und Planung von Radwegen in Oldenburg
```
Nach dem Hinzufügen sucht der Bot sofort in den letzten 30 Tagen nach passenden
Artikeln.

---

## Admin-Befehle

Admin = wer `TELEGRAM_CHAT_ID` in der `.env` gesetzt hat.

| Befehl | Wirkung |
|---|---|
| `/nutzer` | Alle registrierten Nutzer anzeigen |
| `/freischalten <chat_id> [Name]` | Nutzer freischalten und benachrichtigen |
| `/sperren <chat_id>` | Nutzer entfernen (inkl. all seiner Themen) |

---

## So funktioniert's

- Der tägliche NWZ-Digest und der Stadtrat-Watcher laufen **pro Nutzer** — jeder
  bekommt nur Treffer zu seinen eigenen Themen und Abos.
- Themen-IDs sind persönlich; `/loeschen 3` löscht nur *dein* Thema #3.

---

## Bot betreiben

Der Bot pollt Telegram dauerhaft. In Produktion läuft er als systemd-Service
`nwz-bot` (Einrichtung siehe `CLAUDE.md` → „Server-Setup"):

```bash
# Manuell
python scripts/bot_poll.py

# Als systemd-Service
systemctl start nwz-bot
```
