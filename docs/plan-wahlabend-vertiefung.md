# Umsetzungsplan: der Wahlabend in die Tiefe — Wahlbereiche je Liste, echte Wahlkarten, Beobachtungsliste

Stand: 14.09.2026, abends, einen Tag nach der Ratswahl. Dieser Plan folgt auf
[`plan-wahlen-generalisieren.md`](plan-wahlen-generalisieren.md) (PR 1–7
gemergt) und auf #1350 (Kandidaten-Rangliste, Reiter *Ergebnis · Wahlbereiche
· Kandidat\*innen*). Er ist wie seine Vorgänger geschrieben: **ohne das
Gespräch dahinter ausführbar**. Jeder Abschnitt ist ein Pull Request, nennt
Dateien, Signaturen, Tests und woran man erkennt, dass er fertig ist. Was
gemessen ist, steht als Zahl, und Anhang C nennt den Befehl dazu.

Wer das umsetzt, liest vorher: die Wurzel-`CLAUDE.md`, `web/backend/CLAUDE.md`,
`web/frontend/CLAUDE.md`, **`web/frontend/DESIGNSPRACHE.md`** (Parteifarben
nur als Punkte, nie als Flächen — die Wahl-Ebene der Stadtkarte hat dafür
bereits eine Regel, s. §2.2), `tests/CLAUDE.md`, und die Docstrings von
`web/backend/app/election/service.py`, `seats.py`, `candidates.py` sowie
`web/frontend/lib/wahl-flaechen.ts` und `components/stadt-karte.tsx`.

> ## Stand 14.09.2026, abends — was daraus geworden ist
>
> Tim: „bitte implementiere den plan". Umgesetzt in derselben Nacht:
>
> | PR | Was | Stand |
> |---|---|---|
> | **A** | Rangfolge der Wahlbereiche je Liste, „Zugriff" auf den letzten Sitz | #1352 |
> | **B+C** | Amtliche Wahlbereichs- **und** Wahlbezirks-Karte, Ergebnis je Bezirk | ein PR (s. u.) |
> | **D** | Höchstens drei Kandidaturen je Karte | eigener PR |
> | **E** | Beobachtungsliste | **offen** — s. Anhang D |
>
> **Drei Abweichungen vom Plan, alle bewusst:**
>
> 1. **Keine Leaflet-Karte, kein Kachel-Grund** (PR B sah Leaflet vor). Die
>    Ortsbereichs-Karte des Einrichtungs-Assistenten beantwortet dieselbe Art
>    Frage seit 09/2026 als **Inline-SVG** und begründet das ausführlich: Für
>    „wo liegt das?" braucht es keine Straßen, keinen CARTO-Schlüssel und
>    keine Netz-Runde zu einem fremden Server, und ein SVG folgt dem Theme.
>    Die Rechnung dahinter stand in `stadtteil-karte.tsx` und liegt jetzt als
>    `lib/gebiete.ts` unter beiden Karten — eine zweite Abschrift wäre die
>    Fassung gewesen, die als Erste veraltet.
> 2. **B und C sind EIN Pull Request.** Die Wahlbezirke sind eine zweite Ebene
>    derselben Karte (Umschalter, dieselben Flächen-Bausteine); als zwei PRs
>    hätte man dieselbe Komponente zweimal gebaut.
> 3. **Die Stadtkarte behält ihre Ortsbereiche.** Der Plan wollte die Ebene
>    „Wahlergebnis" der Stadtkarte auf die amtlichen Polygone umstellen. Die
>    Stadtkarte ist aber durchgehend auf Ortsbereiche gebaut (Vorhaben,
>    Themen-Orte, Baustellen); eine einzelne Ebene mit anderer Geometrie
>    hieße zwei Rasterungen in einer Karte. Der Wahlabend hat seine eigene
>    Karte, und dort sind die Grenzen amtlich. Wenn die Näherung auf der
>    Stadtkarte jemanden stört, ist das ein eigener PR mit eigener
>    Entscheidung.

## 0. Was Tim gesagt hat (14.09.2026, abends)

> 1) ggf. Pro Partei die Rangfolge der Wahlbereiche hervorheben und zwar bei
> den absoluten Stimmen der Partei im Wahlbereich optische Betonung und
> „1. Zugriff" … Die Prozentwerte im Wahlbereich etwas weniger prominent.
> 2) die openstreetmap der Wahlbereiche mit klickbaren shades näher
> ranbringen … (Wo is eigentlich nochmal Wahlbereich 5)
> 3) ggf die Wahlbezirke ebenfalls aus opendata als Geodaten mitverwenden für
> visuelle Filterung
> 4) bei großen Listen die Boxen der Kandidaten nur pro Wahlbereich mit
> jeweils max drei Kandidaten … Weitere aufklappen oder nach links Blättern
> 5) bestimmte Kandidaten aus allen Parteien zum beobachten auswählen

Und die Regeln, die hier durchgehend gelten:

- **Logik ins Backend.** Rangfolgen, Filter, Zuordnungen rechnet der Server;
  die Seite zeigt. Web und App sollen dieselbe Zahl sehen (Tims Regel vom
  30.08.2026, Beispiel #831).
- **Parteifarben nur als Punkte.** Eine Fläche in Parteifarbe gibt es in der
  Designsprache nicht; die Wahl-Ebene der Stadtkarte tönt deshalb mit
  `--primary` nach Stärke und setzt den Punkt daneben (`stadt-karte.tsx`,
  Schritt 7 des Stadtkarten-Plans). Das bleibt so — auch für die neuen
  Wahlbezirks-Flächen.
- **Ein UI-PR ist erst fertig, wenn Tim ein Bild gesehen hat.** Desktop und
  Handy, per `SendUserFile`, Gegenlesen abwarten.

## 1. Die Reihenfolge — und warum

| PR | Was | Hängt an | Aufwand |
|---|---|---|---|
| **A** | Je Liste die Rangfolge ihrer Wahlbereiche — absolute Stimmen vorn, Prozente zurück, „Zugriff" (§ 36 Abs. 4) | — | klein |
| **B** | Die amtlichen Wahlbereichs-Grenzen (6 Polygone) als Karte auf dem Reiter *Wahlbereiche*, anklickbar | — | mittel |
| **C** | Die 91 Wahlbezirke als Geodaten: Filter auf der Karte, Ergebnis je Wahlbezirk | B | mittel |
| **D** | Große Listen: je Wahlbereich drei Kandidaturen, Rest aufklappen | — | klein |
| **E** | Beobachtungsliste: Kandidaturen quer über alle Listen merken | — | mittel |

A und D sind reine Darstellung auf vorhandenen Zahlen und gehen zuerst — sie
sind vor der **Stichwahl am 27.09.** noch drin. B und C hängen an einem
Datensatz, den es erst zu holen gilt (gemessen, s. §2.1: er ist da, offen
lizenziert, und passt zur Nummerierung von 2026). E braucht eine Konto-Tabelle
und lohnt erst, wenn es etwas zu beobachten gibt — für die Ratswahl 2026 ist
der Abend vorbei; E zielt auf die nächste Wahl und auf den Rückblick.

## 2. Was gemessen ist

### 2.1 Die Geodaten der Stadt gibt es — und sie passen

Die Stadt Oldenburg veröffentlicht über ihr openGEOdata-Portal einen Feature
Service **„Wahlen"** mit drei Ebenen, Lizenz **dl-zero-de/2.0** (Datenlizenz
Deutschland – Zero, entspricht CC0 — keine Namensnennung nötig, wir nennen
sie trotzdem), zuletzt geändert 20.09.2024:

| Ebene | Inhalt | Features | Felder |
|---|---|---|---|
| `…/Wahlen/FeatureServer/0` | **Wahlbezirke** | 91 | `BezirksNr` (101…), `Wahlbereiche` (1–6), `Stadtbezirk` (Name), `Wahllokal_ID` |
| `…/Wahlen/FeatureServer/1` | **Wahlbereiche** | 6 | `Wahlbereiche` (1–6) |
| `…/Wahlen/FeatureServer/2` | Wahlkreise (Landtag) | – | für uns ohne Belang |

Basis: `https://services5.arcgis.com/kqBnwL0FsBhsJf2P/arcgis/rest/services/Wahlen/FeatureServer`.
Native Projektion EPSG 25832; `outSR=4326` liefert WGS 84 direkt. Als GeoJSON
mit `f=geojson`: **439 KB** (Wahlbezirke), **118 KB** (Wahlbereiche) —
unvereinfacht. Die Ortsbereichs-Datei (`/geo/stadtteile-oldenburg.json`,
31 Polygone) ist nach Douglas-Peucker auf 25 m **18 KB**; dieselbe
Vereinfachung dürfte die Wahlbezirke auf 60–100 KB bringen (nicht gemessen,
gehört in PR B als erste Zahl).

**Die Nummerierung passt zu 2026.** Die 91 `BezirksNr` der Geodaten sind
genau die 91 Urnenwahlbezirke der Ergebnisdatei `ratswahl-2026-wahlbezirke.csv`
(133 Zeilen = 91 Urnen- + 42 Briefwahlbezirke `9xx`, die keine Fläche haben
und keine brauchen). Kein Bezirk nur auf einer Seite. Das ist die Zahl, die
über PR C entscheidet: Ergebnis je Wahlbezirk und Fläche je Wahlbezirk lassen
sich über `gebiet-nr` = `BezirksNr` verbinden, ohne Zuordnungstabelle.

**Was wir heute stattdessen tun** (`lib/wahl-flaechen.ts`, `council/geo.py`):
Die Wahl-Ebene der Stadtkarte legt das Wahlbereichs-Ergebnis auf die 31
**Ortsbereiche** (OSM) und nimmt bei Grenzgebieten den ersten Wahlbereich des
Ortskatalogs — „ungefähr, und die Quellenzeile sagt es". Mit den amtlichen
Polygonen entfällt das Ungefähre. Die Ortsbereichs-Ebene bleibt für alles
andere (Vorhaben, Themen-Orte) bestehen.

### 2.2 „Zugriff" gibt es im Verfahren wirklich

§ 36 Abs. 4 NKWG verteilt die Sitze einer Liste auf die Wahlbereiche **nach
Hare/Niemeyer über ihre Stimmen je Wahlbereich** — der Wahlbereich mit dem
größten Rest bekommt den ersten Restsitz. `seats.py::allocate` rechnet das
(Stufe 2), `Allocation.seats_by_list[(party, district)]` trägt das Ergebnis;
die Reste selbst sind in `hare_niemeyer` lokal und **nicht** nach außen
sichtbar. PR A macht sie sichtbar: Rang nach absoluten Stimmen, Sitze je
Wahlbereich, und für den letzten Sitz der Liste, welcher Wahlbereich ihn
bekam (der „1. Zugriff" auf den Rest) und welcher ihn als Nächster bekäme.

### 2.3 Wie groß die Listen wirklich sind

Höchste Kandidaturenzahl je Liste in einem Wahlbereich (Referenz 2026): SPD
12, Linke 12, CDU 11, Grüne 10, FDP 8, Bürger Bündnis 4, AfD 3, Volt 3. Auf
dem Reiter *Wahlbereiche* zeigt jede der sechs Karten heute ALLE — bei der
SPD also bis zu zwölf Zeilen je Karte, sechs Karten untereinander auf dem
Handy: gut 70 Zeilen. PR D kürzt auf drei und klappt auf.

### 2.4 Was für die Beobachtungsliste schon da ist

`kern/store.py` hat `bookmarks(owner_id, kind, target_key, …)` mit
`UNIQUE(owner_id, target_key)` und Arten `session`, `agenda_item`, `decision`
(`routers/bookmarks.py`), dazu `template_follows`. Eine Kandidatur als
`kind="candidate"` mit `target_key="candidate:<wahl>:<liste>:<wb>:<platz>"`
passt in dieselbe Tabelle — die Merkliste ist bereits je Konto, in beiden
Frontends, und beim Konto-Löschen dabei (`USER_OWNED_TABLES`). Ein Tipp: Die
Kandidaten-Rangliste (#1350) trägt jede Kandidatur schon als eindeutiges
Tripel `(party, area, position)`.

## 3. Die Pull Requests

### PR A — Je Liste: die Rangfolge ihrer Wahlbereiche

**Frage, die es beantwortet:** „Wo ist diese Liste stark — in Stimmen, nicht
in Prozent — und wo hat sie ihren Sitz geholt?"

**Backend.** Neues Feld an `ElectionParty` (`antworten.py`) — nicht ein neuer
Endpunkt, denn die Zahl gehört zur Liste und die App liest `ElectionNight`
schon:

```python
class ElectionPartyArea(TypedDict):
    area: int
    roman: str
    #: Rang nach absoluten Stimmen innerhalb der Liste (1 = stärkster WB).
    rank: int
    votes: int | None
    share_pct: float | None
    seats: int | None
    #: Hare/Niemeyer-Rest der Liste in diesem WB (§ 36 Abs. 4) — die Zahl
    #: hinter dem „Zugriff". None, solange nichts ausgezählt ist.
    remainder: int | None
    #: True: der letzte Sitz der Liste ging hierhin (größter Rest).
    took_last_seat: bool
    #: True: der nächste Sitz der Liste ginge hierhin (zweitgrößter Rest).
    next_seat: bool

class ElectionParty(TypedDict):
    …
    areas: list[ElectionPartyArea]   # in Rangfolge, stärkster zuerst
```

- `seats.py::hare_niemeyer` gibt heute `(sitze, lose)` zurück; ergänze eine
  Schwester `hare_niemeyer_detail(...) -> tuple[dict, list, dict[K, int]]`
  mit den Resten (oder erweitere die Rückgabe; `allocate` und die 15 Tests in
  `test_wahlabend.py` müssen unverändert grün bleiben — der Kern ist gegen
  2021 amtlich verifiziert, **nicht anfassen**, nur beobachten).
- `service.compose`: je Liste die Reste aus Stufe 2 durchreichen, Rang nach
  `votes` (None ans Ende), `took_last_seat` = größter Rest unter denen, die
  einen Restsitz bekamen; `next_seat` = größter Rest ohne Restsitz.
- `archive.night` läuft über `compose` — der Rückblick bekommt es geschenkt.

**Frontend.** Reiter *Wahlbereiche* (`view.tsx::Bereiche`): über den sechs
Karten eine **Rangzeile** der Liste — sechs Punkte in Rangfolge, je Wahlbereich
römische Zahl, absolute Stimmen **groß** (22 px display, tabular), der Prozent
darunter klein (11 px, `text-muted-foreground`), Sitze als Zahl, und das
Etikett „letzter Sitz" bzw. „nächster Sitz" (Signal-Orange-Text, kein
Hintergrund). Die Karten selbst **in Rangfolge sortieren** statt I–VI, und in
`BereichKarte` die `dl` umbauen: Stimmen zuerst und groß, Anteil dahinter
klein — Tims Satz „Prozentwerte etwas weniger prominent" wörtlich.

**Tests.** `tests/test_wahlabend_zugriff.py`: gegen Referenz 2026 — Rang 1
der SPD ist WB II (Prange), `took_last_seat` steht bei genau einem WB je
Liste mit Restsitz, die Reste summieren sich je Liste zu `stimmen mod sitze`
… (Formel aus `hare_niemeyer` ablesen), und `areas` ist stabil sortiert.
Browsertest 15: die Karten stehen nach Stimmen.

**Fertig, wenn:** Bild von Tim gegengelesen; `ios_vertrag.py --ausgeliefert`
zeigt für `areas` nichts (neues optionales Feld bricht die App nicht).

### PR B — Die amtlichen Wahlbereichs-Grenzen als Karte

**Frage:** „Wo ist eigentlich Wahlbereich V?"

**Daten.** `scripts/wahl_geodaten.py hol` lädt beide Ebenen (`f=geojson`,
`outSR=4326`), vereinfacht mit demselben Douglas-Peucker wie die
Ortsbereiche (25 m; der Code steht in `scripts/` beim Stadtteile-Asset —
nachsehen, wo `stadtteile-oldenburg.json` erzeugt wurde, und dieselbe
Funktion nehmen) und schreibt `web/frontend/public/geo/wahlbereiche-oldenburg.json`
(Ziel < 30 KB) und `wahlbezirke-oldenburg.json` (Ziel < 100 KB; gebraucht
erst in PR C, aber in einem Lauf geholt). Properties: `nr` (1–6 bzw.
`BezirksNr`), `wb` (Wahlbereich), `name` (`Stadtbezirk`), `lokal`
(`Wahllokal_ID`). Quelle und Lizenz in den Dateikopf (`"license":
"dl-zero-de/2.0"`, `"source": "Stadt Oldenburg, openGEOdata, Stand
2024-09-20"`). **Statisches Asset, kein Cron** — Wahlbezirke ändern sich vor
einer Wahl, nicht dazwischen; vor der nächsten Wahl einmal `hol` laufen
lassen und den Diff ansehen. `tests/test_wahl_geodaten.py` hält fest: 6 und
91 Features, jede `BezirksNr` kommt in der Referenz-CSV vor, jede Fläche hat
genau einen Wahlbereich, keine zwei Wahlbezirke überlappen (Ray-Casting auf
Zentroiden reicht).

**Komponente.** `components/wahlabend/bereich-karte.tsx`: Leaflet (liegt
schon in `package.json`, Kacheln über `lib/basemap.ts` — **keine
Kachel-URL in die Komponente**, s. Wurzel-`CLAUDE.md`), die sechs Polygone
als Flächen in `--primary` getönt nach Stärke der **gewählten** Liste
(0,15–0,6 Alpha), ohne Liste einheitlich hell; Umriss 1,5 px; darin die
römische Zahl als Label (`L.divIcon`, `font-display`). Hover hebt an, Klick
setzt `?bereich=`… **nein**: Klick scrollt zur Karte dieses Wahlbereichs
(`scrollIntoView` auf `article[data-wb]`) und hebt sie kurz (`ring-2
ring-primary/40`, wie `useFrisch`). Auf dem Handy 220 px hoch, am
Schreibtisch neben der Rangzeile aus PR A (Grid `@3xl:grid-cols-[1fr_320px]`).

Einbau auf dem Reiter *Wahlbereiche* **über** den Karten, auch ohne gewählte
Liste („Tippe einen Wahlbereich" ist dann der Text). Und auf `/wahlen` nichts
— die Karte gehört zur Wahl, nicht zur Übersicht.

**Stadtkarte.** `lib/wahl-flaechen.ts` und `stadt-karte.tsx` (Ebene
„Wahlergebnis") bekommen die amtlichen Polygone statt der
Ortsbereichs-Näherung: `WahlFlaeche` je Wahlbereich, gezeichnet aus
`wahlbereiche-oldenburg.json`, die Ortsbereichs-Ebene bleibt für alles
andere. Der Satz „Grenzgebiete … ungefähr" in der Quellenzeile entfällt.
`STADTKARTE-PLAN.md` Schritt 7 nachziehen.

**Fertig, wenn:** Tim auf dem Bild sieht, wo Wahlbereich V ist; Browsertest
`14-layout` bleibt grün (Leaflet-Container hat `max-width: 100%`).

### PR C — Die 91 Wahlbezirke: Filter auf der Karte, Ergebnis je Wahlbezirk

**Frage:** „Wie hat mein Wahllokal gewählt?" — und Tims „visuelle Filterung".

**Backend.** `GET /api/wahlabend/wahlbezirke?wahl=|probe=|counted=` →
`ElectionDistrictList { districts: [ { number, name, area, counted: bool,
totals: ElectionTotals, parties: [ {slug, votes, share_pct} ] } ] }`. Die
Zahlen sind da: `votemanager.Snapshot.districts` (die `Wahlbezirke`-CSV,
133 Zeilen) — `service._fill_areas` aggregiert sie heute zu Wahlbereichen
und wirft die Einzelzeile weg. Neues `service.districts(reg, snap)` gibt sie
je Bezirk zurück; Briefwahlbezirke (`9xx`) **mit**, gekennzeichnet
`postal: true`, denn sie zählen zum Wahlbereich, haben aber keine Fläche.
Kandidaten-Stimmen je Wahlbezirk NICHT — die CSV hat sie (Spalten `D1_2_n`),
aber 91 × 383 Zahlen im Vertrag sind für die Frage zu viel; wer sie will,
schreibt PR C2 mit `?party=`-Filter.

**Frontend.** In `bereich-karte.tsx` eine zweite Stufe: Klick auf einen
Wahlbereich zoomt hinein und zeigt seine Wahlbezirke (aus
`wahlbezirke-oldenburg.json`, `wb == nr`), getönt nach Anteil der gewählten
Liste **in diesem Bezirk**; Hover-Tooltip „115 Donnerschwee · Grüne 31,2 %
· 612 von 1.988"; Klick setzt den Filter `?bezirk=115`, und die
Kandidaten-Rangliste (#1350) … **bekommt keinen Bezirks-Filter** (s. o.,
Personenstimmen je Bezirk sind nicht im Vertrag) — stattdessen zeigt die
Tafel unter der Karte das Bezirks-Ergebnis als Listen-Tafel (dieselbe
Bauform wie `ListenTafel`, nur für diesen Bezirk). Der Auszählungsstand am
Wahlabend: nicht gezählte Bezirke schraffiert (`pattern` in SVG, nicht
`opacity` — Alpha ist schon die Stärke).

**Tests.** `tests/test_wahlbezirke.py`: 133 Bezirke aus der Referenz 2026,
Summe der Bezirks-Stimmen je Liste = Wahlbereichs-Stimmen (das ist die
Zusage, die `_fill_areas` implizit gibt — jetzt explizit), Briefwahlbezirke
tragen `postal`. Vertrag neu schneiden, `api:typen`.

**Fertig, wenn:** Ein Klick auf „115" auf der Karte zeigt Donnerschwee mit
seinen Listen; Bild gegengelesen.

### PR D — Große Listen: drei je Wahlbereich, Rest aufklappen

`view.tsx::BereichKarte`: `eintrag.candidates.slice(0, 3)` sichtbar, darunter
„+ 9 weitere" als `<details>` mit `<summary>` (kein Blättern nach links —
horizontale Listen auf dem Handy sind die Ausnahme der Designsprache, und drei
Zeilen plus ein Aufklappen ist die Bauform, die `Mandate` unten schon nutzt).
**Welche drei:** nach Personenstimmen, nicht nach Listenplatz — vor der
Auszählung nach Listenplatz (die Zahlen fehlen). Wer gewählt ist, steht immer
oben, auch von Platz 9; wer knapp dran ist (`close`), gehört in die drei,
wenn Platz ist. Regel als reine Funktion `lib/wahlabend.ts::vorneDrei(kandidaten,
phase)` mit vitest daneben. Die Sitzgrenzen-Marke (`sitzgrenze`) bleibt auf
allen Balken, auch den zugeklappten. Der Zustand „aufgeklappt" je Karte in
`useState`, nicht in der URL.

**Fertig, wenn:** die SPD-Ansicht auf dem Handy von gut 70 auf 18 Zeilen
schrumpft und Tim das Bild abnickt.

### PR E — Beobachtungsliste: Kandidaturen merken, quer über alle Listen

**Frage:** „Wie stehen *meine* fünf Leute — egal aus welcher Liste?"

**Backend.** `routers/bookmarks.py`: neue Art `candidate` — Payload
`{kind: "candidate", election: slug, party, area, position}`, `target_key`
wie in §2.4, `title` = Name, `subtitle` = „SPD · Wahlbereich II · Platz 1".
Kein neues Schema. Dazu `GET /api/wahlabend/beobachtet?wahl=` (hinter
`require_active`): die gemerkten Kandidaturen des Kontos mit den aktuellen
Zeilen aus `candidates.ranking` (Rang, Stimmen, Status) — **eine** Antwort,
damit die App nicht 383 Zeilen holt, um fünf zu zeigen.

**Frontend.** In der Rangliste (#1350) je Zeile ein Stern (`follow-button.tsx`
kennt die Bauform; angemeldet: merken/entfernen, sonst der Registrier-Hinweis
aus `/wahlen`). Über der Rangliste, wenn etwas gemerkt ist: die Karte
„Beobachtet" mit den gemerkten Zeilen in derselben Bauform, immer in
Rang-Reihenfolge. Auf der Merkliste (`/merkliste`) erscheinen sie in einer
Gruppe „Wahl", mit Link auf `/wahlabend?ansicht=kandidaten`.

**Benachrichtigung — bewusst nicht in diesem PR.** „Dein Kandidat ist drin"
am Wahlabend wäre ein Meldeanlass über `notify.einreihen`, mit Nachtruhe und
Tagesgrenze, und hat am Wahlabend selbst (20–24 Uhr) einen schlechten Takt.
Wenn Tim es will: eigener PR, ein einziger Anlass „Ergebnis steht" nach
`phase == "complete"`.

**Tests.** `tests/test_bookmarks.py` erweitern (Art `candidate`, Löschen mit
Konto), `test_wahlkandidaten.py` um `beobachtet`. Browsertest in
`15-wahlabend.spec.ts` gegen gemockte Antworten wie bisher.

**Fertig, wenn:** Tim fünf Namen aus drei Listen merkt und sie oben in einer
Karte sieht — Bild gegengelesen.

## Anhang D — Was PR E noch braucht (offen)

Die Beobachtungsliste ist als Einzige nicht gebaut. Sie ist die aufwendigste
der fünf (Konto-Tabelle, zweiter Endpunkt, Stern an jeder Zeile, Auftritt auf
`/merkliste`) und die einzige, die niemandem fehlt, solange keine Wahl läuft:
Für die Ratswahl 2026 ist der Abend vorbei. Der Bauplan steht unverändert
unter „PR E"; §2.4 nennt die Tabelle, die dafür schon da ist.

## Anhang A — Was NICHT gebaut wird, und warum

- **Kandidaten-Stimmen je Wahlbezirk im Vertrag** (91 × 383): zu groß für
  die Frage; als Filter-Endpunkt (`?party=`) ein eigener kleiner PR, wenn
  jemand ihn braucht.
- **Blättern nach links** (Tims Alternative in Vorschlag 4): horizontal
  scrollende Listen sind auf dem Handy die Ausnahme; das Aufklappen ist die
  Bauform, die die Seite schon hat.
- **Push am Wahlabend** für die Beobachtungsliste: s. PR E.
- **Ein Cron für die Geodaten**: Wahlbezirke ändern sich nur zur Wahl.

## Anhang B — Reihenfolge und Zeit

A und D vor dem 27.09. (Stichwahl-Abend ist Mehrheitswahl, die Reiter
gelten dort nicht — aber der Rückblick auf die Ratswahl wird an dem Abend
oft geöffnet). B als Nächstes, C dahinter, E wenn Tim es will. Jeder PR
einzeln nach `dev`, kein Stapel (Tims Regel: nie gestackte PRs).

## Anhang C — Die Befehle hinter den Zahlen

```bash
# Feature Service der Stadt: Ebenen, Felder, Zahl der Features
B=https://services5.arcgis.com/kqBnwL0FsBhsJf2P/arcgis/rest/services/Wahlen/FeatureServer
curl -s "$B/0?f=json" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['name'],[f['name'] for f in d['fields']])"
curl -s "$B/0/query?where=1%3D1&returnCountOnly=true&f=json"     # {"count":91}
curl -s "$B/1/query?where=1%3D1&returnCountOnly=true&f=json"     # {"count":6}
curl -sL "$B/0/query?where=1%3D1&outFields=*&f=geojson&outSR=4326" -o /tmp/wahlbezirke.geojson   # 439 KB
curl -sL "$B/1/query?where=1%3D1&outFields=*&f=geojson&outSR=4326" -o /tmp/wahlbereiche.geojson  # 118 KB
# Lizenz und Stand: DCAT-Feed des Portals
curl -sL https://opengeodata-stadt-oldenburg-gis4ol.hub.arcgis.com/api/feed/dcat-us/1.1.json | python3 -c "
import json,sys;[print(d['title'],d['modified'],d['license'][:80]) for d in json.load(sys.stdin)['dataset'] if 'wahl' in d['title'].lower()]"

# Nummerierung 2026 gegen die Geodaten (im Repo-Root)
python3 - <<'EOF'
import csv,json
rows=list(csv.DictReader(open('kommunalwahl/referenz-2026/ratswahl-2026-wahlbezirke.csv',encoding='utf-8-sig'),delimiter=';'))
csv_nr={int(r['gebiet-nr']) for r in rows if r['gebiet-nr'].isdigit()}
geo={f['properties']['BezirksNr'] for f in json.load(open('/tmp/wahlbezirke.geojson'))['features']}
print(len(csv_nr), len(geo), sorted(geo-csv_nr), sorted(n for n in csv_nr-geo if n<900))   # 133 91 [] []
EOF

# Kandidaturen je Liste und Wahlbereich (web/backend)
../../.venv/bin/python -c "
from app.election import archive; import collections
n=archive.night('ratswahl-2026'); c=collections.Counter()
for a in n['areas']:
    for p in a['parties']: c[p['slug']]=max(c[p['slug']],len(p['candidates']))
print(sorted(c.items(), key=lambda x:-x[1])[:8])"
```
