# Wahlprogramm-Vergleich — Ratswahl Oldenburg, 13.09.2026

Alle 16 zugelassenen Wahlvorschläge, Programme im Volltext ausgewertet, entlang von 44 Thesen
vergleichbar gemacht. Der Vergleich selbst ist ein eigenständiger Datenbestand — noch **nicht**
ins Ratslotse-Backend oder -Frontend integriert. Fertige Seite: `vergleich.html` (self-contained,
keine externen Ressourcen). Das Kandidatenregister und die Referenz von 2021 liegen ebenfalls
hier und werden vom Backend gelesen — s. „Wahlabend" unten.

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
| `programme/<slug>.txt` | Extrahierter Volltext mit `[Seite N]`-Markern (die PDFs selbst liegen **nicht** im Repo — Entscheidung vom 07.08.2026, s. u.) |
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
von dort per `#page=N` direkt in das **Original bei der Partei** — Kopien der PDFs liegen
bewusst nicht im Repo (42 MB fremdes Material; die Belegkette hängt an den Prüfsummen, nicht
an den Dateien). `quellen/manifest.json` hält URL, SHA256 und Größe jeder ausgewerteten Datei
fest; der Backend-Endpunkt `/api/kommunalwahl/quelle/{slug}` lädt das gehostete PDF und
meldet, ob es noch die ausgewertete Datei ist:

```bash
curl -L <partei-url> | shasum -a 256   # mit manifest.json vergleichen
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

## Wahlabend

Zwei Bestände in diesem Verzeichnis gehören nicht zum Programmvergleich, sondern zur Seite
`/wahlabend`: das **Kandidatenregister zur Ratswahl 2026** und die **Referenz von 2021**. Beide
liest das Backend direkt aus dem Repo (`web/backend/app/election/`) — es gibt dafür keine
Datenbank und keinen Cron. Die Technik dahinter steht in der Doku unter
[ratslotse.de/docs/wahlabend](https://ratslotse.de/docs/wahlabend/).

| Pfad | Inhalt |
|---|---|
| `kandidaten.py` | Liest `quellen/zulassung-wahlvorschlaege.pdf` und schreibt `kandidaten.json` |
| `kandidaten.json` | 16 Wahlvorschläge, 6 Wahlbereiche, 383 Bewerber\*innen mit Listenplatz, Name, Beruf, Jahrgang, Wohnort; dazu Termin, Sitzzahl (52) und die Quellenangabe |
| `referenz-2021/ratswahl-2021-{stadt,wahlbereiche,wahlbezirke}.csv` | Die Open-Data-Dateien der Ratswahl 2021 (altes Spaltenschema) |
| `referenz-2021/ratswahl-2021.json` | Amtliche Sitzverteilung 2021 (50 Sitze) und die Zuordnung 2021er Spalte → Liste 2026 |

```bash
python3 kandidaten.py            # schreibt kandidaten.json
python3 kandidaten.py --pruefen  # vergleicht nur — was die CI prüft
```

**Die Reihenfolge der Wahlvorschläge ist die des Stimmzettels** und damit zugleich die der Spalten
`D1 … D16` in den Open-Data-CSVs des Votemanagers. Der Index einer Liste in `kandidaten.json` ist
also ihre Spaltennummer; eine Zuordnungstabelle braucht es nicht. `tests/test_wahlabend.py` hält
das fest, indem es die Höchstzahl an Bewerber\*innen je Liste gegen die CSV-Köpfe prüft — und dass
die eingecheckte `kandidaten.json` unverändert der Stand des Skripts ist.

Gelesen wird das PDF über die **Koordinaten** der Textstücke, nicht über den extrahierten Text: In
`zulassung-wahlvorschlaege.txt` stehen Name und Beruf in einer Zeile, ohne Grenze dazwischen; im
PDF stehen sie in Spalten, deren Kanten oben in `kandidaten.py` als Konstanten liegen.

Die Referenz von 2021 dient zwei Zwecken: als Vergleichswert je Liste (Sitze und Stimmenanteil) und
als Basis der Hochrechnung — die Wahlbezirke sind 2026 genauso geschnitten und nummeriert wie 2021,
weshalb ein noch nicht ausgezählter Bezirk mit seinem damaligen Ergebnis geschätzt werden kann.
Listen ohne Nachfolger 2026 fallen dabei weg, neue Listen haben keine Referenz.

`parteien-meta.json` wird von beiden Beständen benutzt: Die Farben je Liste stehen dort einmal, für
die Vergleichsseite wie für den Wahlabend.
