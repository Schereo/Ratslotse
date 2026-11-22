# Technische Dokumentation

Die Dokumentation wird mit Astro Starlight gebaut und ist öffentlich unter
[ratslotse.de/docs](https://ratslotse.de/docs/) erreichbar. Sie erklärt
Architektur, Datenverarbeitung, KI-Pipeline, Betrieb und technische Entscheidungen.

## Lokal arbeiten

Vom Repository-Root aus, mit Node.js ab Version 22:

```bash
npm --prefix docs-site ci
npm --prefix docs-site run dev
```

Die Vorschau liegt unter `http://localhost:4321/docs/`. Mit
`npm --prefix docs-site run build` entsteht die statische Ausgabe in `dist/`;
`npm --prefix docs-site run preview` zeigt diesen Build lokal an.

## Seiten pflegen

- Inhalte liegen als Markdown oder MDX in `src/content/docs/`.
- Der Frontmatter-Titel wird als Seitenüberschrift gerendert. Im Text beginnt
  die Gliederung deshalb mit `##`.
- Navigation und Gruppen stehen in `astro.config.mjs`. Eine Seite, die dort
  fehlt, wird gebaut und ist trotzdem unsichtbar.
- Links innerhalb der Doku beginnen mit `/docs/`.
- **Die Seiten unter `src/content/docs/referenz/` sind erzeugt** (Cron-Jobs,
  Feature-Schalter, Rollen, Eval-Läufe, Workflows). Nie von Hand ändern:
  `python scripts/docs_reference.py` im Repository-Root schreibt sie aus den
  Registern im Code.
- Architekturentscheidungen liegen unter `src/content/docs/adr/`. Neue Einträge
  enthalten Status, Kontext, Entscheidung und Konsequenzen sowie einen Verweis
  in `adr/index.md`.

Die Root-README stellt das Projekt vor. `CONTRIBUTING.md` erklärt den Einstieg
für Mitwirkende, `CLAUDE.md` enthält die Projektregeln. Historische Planungen
liegen getrennt unter `docs/archiv/`; sie werden nicht als aktuelle Anleitung
veröffentlicht.

## Was die Doku aktuell hält

`tests/test_docs_current.py` prüft bei jedem Pull Request, was sich ohne Urteil
prüfen lässt: Jeder Pfad, jedes Modell, jede API-Route und jede
Umgebungsvariable (samt Vorgabewert), die die Doku nennt, gibt es im Code.
Jede Variable, die der Code liest, steht in der Doku. Jeder Feature-Schalter
zeigt auf den Abschnitt, der ihn erklärt (`kern/features.py`, Feld `docs`).
Links, Anker und Seitenleiste stimmen. Vor dem Push:

```bash
python scripts/pruefe.py --nur doku           # erzeugte Seiten gegen die Register
.venv/bin/python -m pytest tests/test_docs_current.py -q
```

Ob ein Absatz inhaltlich noch stimmt, sieht kein Test. Wer Verhalten ändert,
ändert den Absatz dazu im selben Pull Request.

## Prüfung und Veröffentlichung

Der Workflow `.github/workflows/docs.yml` baut die Dokumentation bei Änderungen
an `docs-site/` oder dem Workflow selbst. Der produktive Deploy veröffentlicht
sie unter `/docs/`. Betriebsdetails stehen auf der
[Seite Betrieb](https://ratslotse.de/docs/betrieb/).
