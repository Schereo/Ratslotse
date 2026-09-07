# Zu Ratslotse beitragen

Du kannst mit Code, Dokumentation, verständlicheren Texten und Fehlerberichten
helfen. Besprich größere Änderungen vorab in einem Issue, damit Ziel und Umfang
klar sind. Kleine Korrekturen können direkt als Pull Request kommen.

## Lokal einrichten

Du brauchst Git, Python 3.12 und Node.js ab Version 22. Für die native App gelten
zusätzlich die Voraussetzungen in der [iOS-Anleitung](ios/README.md).
Die folgenden Befehle beginnen im Root deines geklonten Repositorys.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r web/backend/requirements.txt \
  -r requirements-dev.txt -c constraints.txt
npm --prefix web/frontend ci
git config core.hooksPath .githooks
```

Starte das Backend im Root:

```bash
.venv/bin/python scripts/dev.py start
```

Der Starter wählt einen freien Port und gibt den passenden Frontend-Befehl aus.
Führe diesen in einem zweiten Terminal unter `web/frontend/` aus und setze
zusätzlich `BACKEND_URL` auf dieselbe Backend-Adresse. Beispiel für Port 8600:

```bash
cd web/frontend
BACKEND_URL=http://127.0.0.1:8600 NEXT_PUBLIC_API_BASE=http://127.0.0.1:8600 npm run dev
```

Verwende den tatsächlich ausgegebenen Port. Mit
`.venv/bin/python scripts/dev.py status` und `stop` kannst du den eigenen
Backend-Prozess prüfen und beenden.

Lokale Daten liegen unter `data/` und werden nicht eingecheckt. Eine frische
Installation enthält keine Ratsdaten. Hinweise zu Beispieldaten und optionalen
Zugangsdaten stehen unter [Lokale Entwicklung](CLAUDE.md#lokale-entwicklung).
KI-Antworten, E-Mail und Push benötigen die jeweiligen Dienstzugänge.

## Den richtigen Branch wählen

| Änderung | Ausgangspunkt und PR-Ziel | Merge |
| --- | --- | --- |
| Neue Funktion | `dev` | Squash |
| Fehlerbehebung oder Korrektur der veröffentlichten Dokumentation | `main` | Squash; anschließend `main` nach `dev` übernehmen |
| Release | `dev` → `main` | Merge-Commit |

Verwende für jeden Auftrag einen eigenen Branch. Nimm keine fremden Änderungen
in deinen Commit auf. `feature` ist eine zusätzliche Vorschauumgebung; fertige
Funktionen gehen regulär per PR nach `dev`.

Ein gemergter PR nach `main` löst den produktiven Deploy aus. Pushes auf `dev`
und `feature` aktualisieren die jeweilige Vorschau. Details stehen in den
[Projektregeln](CLAUDE.md#deployment--branch-modell).

## Änderungen prüfen

```bash
.venv/bin/python scripts/pruefe.py
```

Der Prüflauf bündelt unter anderem Python- und Frontend-Tests, Linter,
Typprüfungen, den API-Vertrag und Changelog-Prüfungen. `--liste` zeigt die
aktuelle Auswahl, `--schnell` führt eine kürzere Auswahl aus. Fehlende Werkzeuge
werden als übersprungen gemeldet; das ersetzt keine erfolgreiche Prüfung.

Je nach Änderung kommen hinzu:

- Frontend-Build: `npm --prefix web/frontend run build`.
- Browsertests: in `web/frontend/` mit `npx playwright test`; bei belegten Ports
  beispielsweise `E2E_PORT=3010 E2E_API_PORT=8012 npx playwright test`.
- Dokumentation: `npm --prefix docs-site ci` und
  `npm --prefix docs-site run build`.
- iOS: die Tests und Builds aus [ios/README.md](ios/README.md).

Die Hooks führen vor Commits den Adressen-Lint und vor Pushes die schnelle
Prüfauswahl aus. Alle verpflichtenden CI-Prüfungen müssen am aktuellen
PR-Stand erfolgreich sein, bevor gemergt wird.

## Den Pull Request vorbereiten

Beschreibe das Problem, die Änderung und die durchgeführten Prüfungen.
Verlinke ein zugehöriges Issue, falls vorhanden. Für Änderungen am Verhalten
der Anwendung gehört ein Fragment unter `changelog.d/<slug>.md` dazu:

```markdown
---
kategorie: behoben
---

**Kurze Beschreibung der Änderung.** Erkläre, was sich für Nutzer*innen ändert.
```

Mögliche Kategorien sind `hinzugefuegt`, `geaendert` und `behoben`. Keine
Überschriften oder PR-Nummern im Fragment; die Nummer ergänzt der Versionsschnitt.
Reine Dokumentations- und Repositorypflege braucht keinen Produkteintrag.

## Sprache und Projektregeln

Schreibe UI-Texte und Dokumentation auf Deutsch: konkret, verständlich und ohne
unnötige Werbesprache. Verwende Fachbegriffe dort, wo sie etwas erklären, und
beschreibe Einschränkungen ebenso klar wie Funktionen. Halte dich im Code an
die Konventionen des jeweiligen Moduls.

Die [Projektregeln](CLAUDE.md) und die `CLAUDE.md` im betroffenen Unterverzeichnis
enthalten die technischen Vorgaben. Die [Entwicklungsrezepte](REZEPTE.md)
helfen, die relevanten Dateien zu finden.

Zugangsdaten, private Serveradressen und personenbezogene Testdaten gehören
nicht ins Repository. Nutze für Beispieladressen `example.org`.

## Zusammenarbeit und Lizenz

Es gilt der [Verhaltenskodex](CODE_OF_CONDUCT.md). Sicherheitslücken werden über
den [vertraulichen Meldeweg](SECURITY.md) gemeldet. Beiträge werden unter der
[AGPL-3.0](LICENSE) veröffentlicht.
