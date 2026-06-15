# NWZ-Bot

Ein persönlicher Telegram-Bot für Oldenburger Lokalpolitik. Er liest täglich die **Nordwest-Zeitung** und beobachtet den **Oldenburger Stadtrat** — vollautomatisch, personalisiert.

---

## Features

### 📰 Täglicher NWZ-Digest
Der Bot liest jeden Morgen die aktuelle NWZ-Ausgabe und schickt dir nur die Artikel, die zu deinen Themen passen. Du legst die Themen selbst fest — z. B. *„Radwege"*, *„Stadtentwicklung"* oder *„Klimapolitik"*. Die Klassifizierung übernimmt GPT-4o.

### 📅 Wöchentlicher Überblick
Jeden Freitag erscheint eine kompakte Zusammenfassung der Woche: GPT wählt die 3–5 politisch bedeutsamsten Artikel aus der gesamten NWZ-Ausgabe (unabhängig von deinen Themen) und begründet kurz, warum sie relevant sind. Darunter folgen die themenspezifischen Treffer der Woche.

### 🗄️ Artikel-Archiv & Suche
Alle Artikel-Treffer werden dauerhaft gespeichert. Du kannst jederzeit nachschauen, was zu einem Thema in den letzten Wochen erschienen ist — oder per Volltextsuche im gesamten NWZ-Archiv stöbern.

### 🔄 Rückblick bei neuem Thema
Wenn du ein neues Thema hinzufügst, klassifiziert der Bot sofort alle Ausgaben der letzten 30 Tage gegen dieses Thema und schickt dir die historischen Treffer. Du musst nicht bis zum nächsten Morgen warten.

### 🔔 Ausschuss-Benachrichtigungen
Abonniere einzelne Ausschüsse (Bauausschuss, Verkehrsausschuss, etc.). Sobald eine neue Tagesordnung veröffentlicht wird, bekommst du eine GPT-generierte Zusammenfassung der wichtigsten Punkte. Ändert sich die Tagesordnung nachträglich, wirst du erneut benachrichtigt.

### 🏛️ Stadtrat-Alerts
Der Bot überwacht automatisch alle kommenden Stadtratssitzungen. Wenn eines deiner Themen auf der Tagesordnung steht, bekommst du vorab eine Benachrichtigung mit den relevanten Tagesordnungspunkten.

### 📋 Sitzungs-Nachberichte
2–3 Tage nach einer abonnierten Ausschusssitzung sucht der Bot in der NWZ nach Berichten über die Beschlüsse und schickt dir die relevanten Artikel. Schließt den Kreis zwischen Ankündigung und Ergebnis.

### 🔁 Doppelstory-Erkennung
Artikel, die erkennbar eine Fortsetzung einer bereits gemeldeten Geschichte sind, werden mit 🔄 markiert — so siehst du auf einen Blick, ob es sich um Neues oder eine Folgemeldung handelt.

---

## Bot-Befehle

### Themen & Archiv

| Befehl | Funktion |
|--------|----------|
| `/neu Name \| Beschreibung` | Thema hinzufügen (startet sofort 30-Tage-Rückblick) |
| `/themen` | Gespeicherte Themen anzeigen |
| `/loeschen ID` | Thema löschen |
| `/archiv` | Übersicht aller archivierten Treffer |
| `/archiv ID` | Archiv-Treffer für ein bestimmtes Thema |
| `/suche Begriff` | Volltextsuche im NWZ-Artikelarchiv |

### Stadtrat & Ausschüsse

| Befehl | Funktion |
|--------|----------|
| `/ausschuesse` | Alle Ausschüsse anzeigen, per Button abonnieren/kündigen |
| `/pruefen` | Tagesordnungen für abonnierte Ausschüsse jetzt abrufen |

### Info

| Befehl | Funktion |
|--------|----------|
| `/start` | Bot vorstellen / Befehlsübersicht |
| `/hilfe` | Alle Befehle im Überblick |

### Admin

| Befehl | Funktion |
|--------|----------|
| `/nutzer` | Alle registrierten Nutzer anzeigen |
| `/freischalten chat_id [Name]` | Nutzer freischalten |
| `/sperren chat_id` | Nutzer entfernen |

---

## Cron-Jobs

| Zeit | Script | Aufgabe |
|------|--------|---------|
| 06:30 täglich | `daily_digest.py` | NWZ-Ausgabe holen, klassifizieren, Digest versenden |
| 07:00 täglich | `check_committees.py` | Ausschuss-Tagesordnungen prüfen, Abonnenten benachrichtigen |
| 08:00 + 14:00 täglich | `check_council.py` | Stadtratssitzungen auf Themen-Matches prüfen |
| 14:00 täglich | `session_followup.py` | NWZ-Nachberichte zu vergangenen Sitzungen suchen und versenden |
| 17:00 freitags | `weekly_digest.py` | Wöchentlichen Überblick erstellen und versenden |

---

## Konfiguration

Alle Credentials in `~/app/.env` auf dem Server:

```env
NWZ_USERNAME=...
NWZ_PASSWORD=...
OPENAI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...   # Chat-ID des Administrators
```

---

## Technische Details

Siehe [ARCHITECTURE.md](ARCHITECTURE.md) für Infos zu Scraping, Datenbankschema, KI-Klassifizierung und Deployment.

**Stack:** Python 3.12 · SQLite (FTS5) · OpenAI API (GPT-4o / GPT-4o-mini) · Telegram Bot API · systemd · GitHub Actions
