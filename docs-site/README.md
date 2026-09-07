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
- Navigation und Gruppen stehen in `astro.config.mjs`.
- Architekturentscheidungen liegen unter `src/content/docs/adr/`. Neue Einträge
  enthalten Status, Kontext, Entscheidung und Konsequenzen sowie einen Verweis
  in `adr/index.md`.

Die Root-README stellt das Projekt vor. `CONTRIBUTING.md` erklärt den Einstieg
für Mitwirkende, `CLAUDE.md` enthält die Projektregeln. Historische Planungen
liegen getrennt unter `docs/archiv/`; sie werden nicht als aktuelle Anleitung
veröffentlicht.

## Prüfung und Veröffentlichung

Der Workflow `.github/workflows/docs.yml` baut die Dokumentation bei Änderungen
an `docs-site/` oder dem Workflow selbst. Der produktive Deploy veröffentlicht
sie unter `/docs/`. Betriebsdetails stehen auf der
[Seite Betrieb](https://ratslotse.de/docs/betrieb/).
