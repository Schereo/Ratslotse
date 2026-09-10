# Rechte an den Assets der App

Stand: 10. September 2026. Für die Store-Einreichung (App Review 4.1/5.2,
Feld „Content Rights" in App Store Connect steht auf „nutzt Drittinhalte").

## Eigene Werke (Rechte beim Betreiber, Tim Sigl)

| Asset | Wo | Herkunft |
|---|---|---|
| Lotti, die Lotsenmöwe (2D) | `web/frontend/components/mascot.tsx`, Logo/BrandMark | eigene SVG-Geometrie, seit 07/2026 im Repo |
| Lotti 3D und Küken | `ratslotse-social/studio/lotti-modell.js`, gerendert nach `Assets.xcassets/Lotti3D*` | eigenes three.js-Modell, headless gerendert; kein Bildgenerator |
| Lotti-Sprites | `Assets.xcassets/LottiSprite*`, Herkunft in `Resources/LOTTI-SPRITES-SOURCE.md` | aus demselben Modell gerendert |
| App-Icon | `Assets.xcassets/AppIcon.appiconset` | aus der BrandMark-Geometrie abgeleitet |
| Screenshots, Clips, Texte | Store-Eintrag, `web/frontend/public/neuigkeiten/` | selbst aufgenommen aus der eigenen App |

Der Quellcode selbst steht unter AGPL-3.0 (`LICENSE` im Repo-Root); die
Marke, das Maskottchen und die Bildwelt sind davon nicht erfasst.

## Drittinhalte mit Lizenz

| Asset | Lizenz | Nachweis im Bundle |
|---|---|---|
| Inter (Schrift) | SIL Open Font License 1.1 | `Resources/Fonts/OFL-Inter.txt` |
| Bricolage Grotesque (Schrift) | SIL Open Font License 1.1 | `Resources/Fonts/OFL-BricolageGrotesque.txt` |
| IBM Plex Mono (Schrift) | SIL Open Font License 1.1 | `Resources/Fonts/OFL-IBMPlexMono.txt` |
| Lucide Icons | ISC | `Resources/LucideIcons-LICENSE.txt` |
| Stadtteil-Grenzen | ODbL, © OpenStreetMap-Mitwirkende, vereinfacht | `attribution`-Feld in `Resources/stadtteile-oldenburg.json` |
| Kartenkacheln | CARTO Basemaps (mit API-Key) auf OpenStreetMap-Daten (ODbL) | Attribution in der Karte, URL-Bau in `web/frontend/lib/basemap.ts` |
| Bebauungsplan-Umringe | Stadt Oldenburg, Datensatz „Umringe Bplan", dl-de/zero | `council/bplan.py` |

Die OFL erlaubt das Einbetten der Schriften in eine App ohne Namensnennung
im Store-Eintrag; die Lizenztexte liegen im Bundle. ODbL verlangt die
Nennung „© OpenStreetMap contributors", die in der Karte steht.

## Amtliche Inhalte

Beschlüsse, Vorlagen, Protokolle und Tagesordnungen stammen aus dem
Ratsinformationssystem der Stadt Oldenburg (buergerinfo.oldenburg.de). Es
sind amtliche Werke nach § 5 UrhG und damit gemeinfrei; jede Darstellung
verlinkt das Original. Pressemitteilungen der Stadt werden per RSS gelesen
und nur in Auszügen mit Quellenlink gezeigt. Haushaltsdaten und Statistiken
tragen ihre Lizenz je Quelle in `docs-site/src/content/docs/haushalt-quellen-recherche.md`.

## Was es nicht gibt

Keine Stockfotos, keine lizenzierten Illustrationen, keine Musik, keine
Inhalte aus Bildgeneratoren, keine Logos der Stadt, der Fraktionen oder
Parteien als Grafik.
