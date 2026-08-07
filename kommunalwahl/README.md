# Wahlprogramm-Vergleich — Ratswahl Oldenburg, 13.09.2026

Alle 16 zugelassenen Wahlvorschläge, Programme im Volltext ausgewertet, entlang von 44 Thesen
vergleichbar gemacht. Eigenständiger Datenbestand — noch **nicht** ins Ratslotse-Backend oder
-Frontend integriert. Fertige Seite: `vergleich.html` (self-contained, keine externen Ressourcen).

## Ablauf

```bash
python3 analyse.py   # digests/ + positionen/ + thesen.json  ->  data.json
python3 build.py     # data.json + vergleich-template.html   ->  vergleich.html
python3 pruefe.py    # Konsistenz der Positionsdateien gegen den Thesenkatalog
```

Nur `pypdf` wird gebraucht (`pip install pypdf`), sonst reine Standardbibliothek.
Alle Skripte lösen ihre Pfade relativ zum eigenen Ort auf und laufen von überall.

## Datenbestand

| Pfad | Inhalt |
|---|---|
| `quellen/` | Amtliche Bekanntmachung der zugelassenen Wahlvorschläge (23.07.2026) + `manifest.json` mit SHA256 aller Quelldateien |
| `programme/<slug>.pdf/.txt` | Originalprogramm und extrahierter Volltext mit `[Seite N]`-Markern |
| `digests/<slug>.json` | Auswertung je Liste: Charakter, Kernpunkte, Positionen je Themenfeld, Prägnanz |
| `positionen/<slug>.json` | Position zu jeder der 44 Thesen mit Belegzitat und Seitenzahl |
| `thesen.json` | Thesenkatalog mit Themenzuordnung und lokalem Kontext |
| `wahl-fakten.json` | Wahltermin, Sitze, Wahlrecht, Wahlvorschläge, OB-Kandidaturen, Bürgerentscheid |
| `parteien-meta.json` | Farben je Liste (nur Datenmarken, hell/dunkel geprüft) |
| `data.json` | Alles gebündelt plus berechnete Paarähnlichkeiten — **die Schnittstelle für eine Integration** |

Slugs: `spd cdu gruene linke fdp fuer-oldenburg buergerbuendnis afd volt piraten bsw pgm partei
echt-oldenburg dava stille` (Reihenfolge = Kandidatenzahl absteigend).

## Werkzeuge

| Skript | Zweck |
|---|---|
| `extract.py <pdf> <txt>` | PDF → Text mit Seitenmarkern |
| `html2text.py <html> <txt> [--append]` | Webseite → Text |
| `entzerre.py <txt> [--pruefen]` | Repariert Sperrsatz-Extraktion (`O l d e n b u r g` → `Oldenburg`) |
| `suche.py <slug\|alle> <regex...>` | Belegsuche im Volltext mit Seitenzahl und Kontext |

`AUFTRAG.md` und `POSITIONEN.md` sind die Arbeitsanweisungen, mit denen die Auswertungen von
Subagenten erzeugt wurden — relevant, um die Analyse zu wiederholen oder auf eine andere Wahl
zu übertragen. `designplan.md` dokumentiert die Gestaltung der Seite.

## Ähnlichkeitsmodell

Position je These: `+1` Zustimmung, `0` teils/teils, `-1` Ablehnung, `null` keine Aussage.
Gewertet werden nur Thesen, zu denen **beide** Listen eine Position haben.
Übereinstimmung je These `1 − |a−b| / 2`, Ähnlichkeit = Mittelwert × 100.

`n` (Zahl gemeinsamer Thesen) wird immer mit ausgewiesen. Unter `n = 5` gilt ein Wert als nicht
belastbar und wird grau dargestellt — ein hoher Prozentwert bei kleinem `n` heißt nur, dass sich
zwei Listen zu wenigem beide geäußert haben.

## Nachvollziehbarkeit

Jede Position trägt ein Belegzitat und, bei PDF-Programmen, die Seitenzahl. Die Seite verlinkt
von dort per `#page=N` direkt in das Original-PDF. `quellen/manifest.json` hält URL, SHA256 und
Größe jeder ausgewerteten Datei fest:

```bash
shasum -a 256 programme/spd.pdf   # mit manifest.json vergleichen
```

## Einschränkungen

- Nur **8 der 16 Listen** haben ein ausformuliertes Kommunalwahlprogramm. Piraten, Die PARTEI
  und PGM haben keins veröffentlicht; BSW tritt mit einem landesweiten Rahmenprogramm an, das
  Oldenburg an keiner Stelle erwähnt. Einstufung explizit in `analyse.py` (`QUELLENART`).
- Verglichen werden **Programme, nicht Politik** — nicht das Abstimmungsverhalten im Rat.
- Programmumfang verzerrt die Zahl der Vergleichspunkte: 71 Seiten äußern sich zu mehr Thesen
  als sieben Stichpunkte.
- Die Auswahl der 44 Thesen ist eine inhaltliche Entscheidung und beeinflusst die Prozentwerte.
- Zahlen zu Wahlvorschlägen stammen aus der amtlichen Bekanntmachung, nicht aus Presseberichten —
  die wichen in zwei Punkten ab (Einzelbewerber Stille, Zuordnung Butzin).
