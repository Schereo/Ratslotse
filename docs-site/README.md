# docs-site — Technische Doku (Astro Starlight)

Interne Technik-Doku, ausgeliefert unter **ratslotse.de/docs**. Quelle für
Architektur, KI-Pipeline und die Architekturentscheidungen (ADRs).

## Lokal

```bash
cd docs-site
npm install            # einmalig (Node ≥ 22)
npm run dev            # http://localhost:4321/docs/
npm run build          # statische Ausgabe nach dist/ (base = /docs)
npm run preview        # gebaute Site lokal ansehen
```

## Inhalt

- Seiten liegen als `.md`/`.mdx` in `src/content/docs/`. Der Dateiname bestimmt
  die Route (`architektur.md` → `/docs/architektur/`).
- Frontmatter `title` wird als H1 gerendert — die erste `#`-Zeile im Body daher weglassen.
- Navigation/Gruppen: `astro.config.mjs` → `sidebar`.
- **ADRs**: neue Datei `src/content/docs/adr/NNNN-titel.md` (Schema:
  Status · Kontext · Entscheidung · Konsequenzen) + Zeile in `adr/index.md`.

## Verhältnis zu den Markdown-Docs im Repo-Root

Die ursprünglichen `ARCHITECTURE.md`, `AI-PIPELINE.md`, `MODELLVERGLEICH.md`,
`BOT.md`, `eval/README.md`, `docs/beschluesse-feature.md` wurden hierher migriert.
`CLAUDE.md` bleibt die maßgebliche **Betriebs-/Infra-Doku** im Root und wird hier
nur referenziert, nicht dupliziert.

## CI / Deployment

- `.github/workflows/docs.yml` baut die Site bei jedem PR (Build-Gate).
- Hosting unter `/docs`: siehe Projekt-README / Deployment-Plan (Caddy auf der
  Edge-VM liefert `dist/` unter `/docs` aus).
