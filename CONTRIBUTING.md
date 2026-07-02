# Contributing to Ratslotse

Danke, dass du zu Ratslotse beitragen möchtest! Das Projekt macht die Arbeit des
Oldenburger Stadtrats durchsuchbar und verständlich — Beiträge, die das besser,
zugänglicher oder korrekter machen, sind willkommen.

## Erste Schritte

1. **Issue zuerst.** Für alles außer Tippfehlern/Kleinstfixes bitte erst ein Issue
   öffnen (Bug oder Feature), damit wir Ansatz und Scope abstimmen können.
2. **Fork & Branch.** Branch von `main`, sprechender Name (`feat/…`, `fix/…`, `docs/…`).
3. **Lokal entwickeln** — siehe [CLAUDE.md](CLAUDE.md) → „Lokale Entwicklung"
   (Backend, Frontend, Doku, Tests).

## Vor dem Pull Request

- **Tests laufen lassen:** `python -m pytest tests/ -q` (grün halten).
- **Backend-Import prüfen:** `cd web/backend && python -c "import app.main"` und
  `python -c "import scripts.bot_poll"` — beides muss ohne Fehler durchlaufen
  (Python 3.12).
- **Frontend baut:** `cd web/frontend && npm run build`.
- **Doku baut** (falls `docs-site/` betroffen): `cd docs-site && npm run build`.
- **Keine Secrets/Infra** im Diff (Keys, echte Server-IPs/Hosts, personenbezogene
  Daten). Konfiguration gehört in `.env` / GitHub-Secrets, nicht ins Repo.

## Pull Request

- Klein und fokussiert halten; ein Thema pro PR.
- Beschreibe **was** und **warum**; verlinke das Issue.
- CI muss grün sein, bevor gemergt wird — **niemals einen roten Lauf mergen.**
- Deployt wird nur über einen gemergten PR nach `main` (siehe CLAUDE.md).

## Stil

- Halte dich an den umgebenden Code (Namensgebung, Kommentar-Dichte, Idiome).
- Deutschsprachige UI-Texte und nutzerseitige Doku; Code/Kommentare gern gemischt,
  wie im jeweiligen Modul üblich.

## Lizenz

Mit deinem Beitrag stimmst du zu, dass er unter der **AGPL-3.0** (siehe
[LICENSE](LICENSE)) veröffentlicht wird.
