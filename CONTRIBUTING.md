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

**Ein Befehl prüft alles, was auch die CI prüft:**

```bash
python scripts/pruefe.py
```

Er fährt Adressen-Lint, ruff, den API-Vertrag, die generierten Frontend-Typen,
die Changelog-Fragmente, die Testsuite, den TypeScript-Übersetzer und die
beiden Grafik-Proben. `--schnell` beschränkt ihn auf die fünf Prüfungen unter
vier Sekunden, `--liste` zählt sie auf. Fehlt ein Werkzeug, sagt er, welches.

**Einmal je Checkout einschalten**, dann läuft `--schnell` vor jedem Push und
der Adressen-Lint vor jedem Commit:

```bash
git config core.hooksPath .githooks
```

Was der Befehl nicht abdeckt und je nach Änderung dazugehört:

- **Frontend baut:** `cd web/frontend && npm run build` (der Übersetzer allein
  sieht den Bundler nicht).
- **Doku baut** (falls `docs-site/` betroffen): `cd docs-site && npm run build`.
- **Changelog-Fragment** (falls die Änderung Nutzer\*innen betrifft): eine Datei
  `changelog.d/<slug>.md` mit `kategorie: hinzugefuegt | geaendert | behoben` im
  Frontmatter und dem Eintrag darunter — ohne PR-Nummer, die trägt der
  Versionsschnitt nach. Nicht in `CHANGELOG.md` schreiben: Dort kollidiert jeder
  parallele PR.
- **Regeln der Schicht, in der du arbeitest:** neben dieser Datei liegt in
  jedem größeren Verzeichnis eine eigene `CLAUDE.md` (`council/`, `kern/`,
  `scripts/`, `web/backend/`, `web/frontend/`, `ios/`, `tests/`).
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
