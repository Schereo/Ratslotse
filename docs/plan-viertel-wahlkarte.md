# Plan: Wahlergebnis auf der Stadtkarte, bis auf den Wahlbezirk

> Tims Wunsch vom 23.09.2026, sinngemäß: Wer auf „Mein Viertel“ die
> Wahlergebnisse einschaltet, soll auf der **ganzen Stadt** sehen, wie die
> Gegenden gewählt haben. Klickt man einen **Stadtteil** an, sieht man seine
> **Wahlbezirke**, jeweils **in der Farbe der Partei, die dort vorn lag**.
> Tippt man einen Wahlbezirk an, erscheint dessen **genaue Aufteilung**.
>
> Das Dokument ist ein Arbeitsplan für ein anderes Modell. Oben stehen die
> Entscheidungen, die Tim treffen muss, und die Messungen dahinter. Danach
> folgen die PRs in der Reihenfolge, in der sie gebaut werden.

## 0. Was es schon gibt

Die meisten Bausteine liegen schon im Repo. Es fehlen die Verbindung zwischen
den Bausteinen und die Färbung.

| Baustein | Wo | Stand |
|---|---|---|
| Stadtkarte mit Stufen Stadt → Ortsbereich | `app/(app)/karte/view.tsx`, `components/stadt-karte.tsx` (Leaflet) | läuft, `/viertel` leitet dorthin |
| Ebene „Wahlergebnis“ | `lib/karten-ebenen.ts` (Schalter `wahlabend`), `lib/wahl-flaechen.ts`, `components/wahl-karte.tsx` | tönt **Ortsbereiche** in `--primary` nach dem **ersten** Wahlbereich laut Ortskatalog. Die Quellenzeile sagt selbst: „ungefähr“ |
| Amtliche Umrisse | `public/geo/wahlbezirke-oldenburg.json` (91 Urnenbezirke, `nr/wb/name/lokal`), `wahlbereiche-oldenburg.json` (6), `stadtteile-oldenburg.json` (31) | kommen aus `scripts/wahl_geodaten.py` (openGEOdata, dl-zero-de/2.0) |
| Ergebnis je Wahlbezirk | `GET /api/wahlabend/wahlbezirke?wahl=<slug>` → `ElectionDistrictList` (`antworten.py:4379`) | 133 Bezirke (91 Urne + 42 Brief), je Liste Stimmen/Anteil. Dieselbe Abfrage liefert den eingefrorenen Stand jeder gelaufenen Wahl |
| Parteifarben als Fläche | `components/wahlabend/stichwahl-karte.tsx` | **einzige** Ausnahme laut DESIGNSPRACHE § 2 |
| SVG-Karte ohne Kacheln | `components/wahlabend/gebietskarte.tsx` + `lib/gebiete.ts` (hat schon `farbe(nr)`) | für /wahlabend |

## 1. Messungen (23.09.2026, Ratswahl 2026, `kommunalwahl/referenz-2026/`)

Gemessen mit shapely an den Umrissen aus `public/geo/` und an der CSV je Bezirk.
Die Skripte stehen in Anhang A.

1. **Wahlbezirke liegen nicht innerhalb der Ortsbereiche.** Bei **25 von 91**
   Urnenbezirken liegen weniger als 80 % der Fläche in einem einzigen
   Ortsbereich. Beispiele: 204 „Innenstadt“ verteilt sich zu 44 % auf Eversten,
   29 % auf die Innenstadt und 27 % aufs Dobbenviertel. 206 liegt je zur Hälfte
   im Gerichtsviertel und in Osternburg.
2. **Zwei Ortsbereiche haben keinen eigenen Bezirk:** Innenstadt und Drielake.
   In beiden überwiegt kein Bezirk flächenmäßig. Eine Zuordnung nach dem
   „Hauptbezirk“ ließe sie leer.
3. **Sechs Ortsbereiche liegen in mehreren Wahlbereichen:** Bürgerfelde,
   Donnerschwee, Drielaker-Moor, Haarentor, Osternburg und Tweelbäke. Die
   heutige Ebene färbt sie nach nur einem davon.
4. **Ein Drittel der Stimmen kam per Brief: 32,2 %** (80.650 von 250.816
   gültigen Stimmen). Die 42 Briefwahlbezirke (Nummern ab 900) haben keine
   Fläche. **Eine Karte nach Urnenbezirken zeigt also, wie im Wahllokal gewählt
   wurde, nicht das ganze Ergebnis.**
5. **Wer vorn lag (Urne, 91 Bezirke):** SPD 49, Grüne 39, AfD 2 (514 und 515,
   Grundschule Krusenbusch) und Linke 1 (205, Kulturzentrum PFL). **29 Bezirke
   sind knapp**, das heißt, der Vorsprung beträgt weniger als 3 Punkte. Die
   Karte wird überwiegend rot und grün sein. Die vier Ausreißer sind der
   eigentliche Fund und dürfen nicht untergehen.
6. **Stichwahl und erster Wahlgang der OB-Wahl** gehen über denselben
   Endpunkt (`wahl=ob-2026`, `wahl=ob-stichwahl-2026`). Die Stichwahl zählt
   133 Bezirke, die Geometrie kennt 91. Die Differenz sind wieder die
   Briefwahlbezirke.

## 2. Entscheidungen für Tim

Zu jeder Frage steht eine Empfehlung dabei. Baut das andere Modell ohne
Antwort los, gilt die Empfehlung.

**E1 – Parteifarben als Fläche (zweite Ausnahme in der Designsprache).**
Der Wunsch verlangt ausdrücklich „eingefärbt in den Parteifarben“, die
Designsprache verbietet genau das bis auf die Stichwahl-Karte.
*Empfehlung:* Die Ausnahme gilt auch hier, mit derselben Grammatik wie bei der
Stichwahl. Die Farbe zeigt, wer vorn lag. Die **Deckkraft** zeigt den
**Vorsprung auf die Zweitplatzierten**, sodass knapp umkämpfte Bezirke blass
bleiben. Ein Bezirk ohne Stimmen wird gestrichelt. Die Ausnahme gilt **nur für
diese Ebene**, nicht für Listen, Balken oder Tafeln. Dort bleibt die Parteifarbe
ein Punkt. Der CDU-Farbton #1a1a1a wird im Dunkelmodus zur Wand. Deshalb gelten
`color_dark` aus den Stammdaten und ein heller Rand.

**E2 – Was zeigt die Stadt-Stufe?** „Welche Stadtteile *oder* welche
Wahlbereiche“ ist offen.
*Empfehlung:* **Die 91 Wahlbezirke**, gefärbt, und darüber die 31
Ortsbereichsgrenzen als dünne weiße Linie zur Orientierung. Ein Ergebnis je
Ortsbereich gibt es nicht (Messung 1). Man müsste es schätzen, und eine
Schätzung in Parteifarbe wirkt wie ein amtliches Ergebnis. Die sechs
Wahlbereiche wären zu grob, weil sie nur rot oder grün zeigen und Krusenbusch
in „Süd“ verschwindet. *Alternative:* Ein Umschalter „Bezirke · Wahlbereiche“.
Er wäre nur ein Chip mehr, ist aber für den ersten Schritt nicht nötig.

**E3 – Welche Wahl?** Es gibt drei gelaufene Wahlen, die auf eine Karte passen.
*Empfehlung:* Die Vorgabe ist **Ratswahl 2026**. Drei Chips unter der Ebene
schalten um: „Ratswahl · OB 1. Wahlgang · Stichwahl“. Die Auswahl steht in der
Adresse (`?wahl=`). Bei der Stichwahl nimmt die Ebene die Farben der
Stichwahl-Karte (Prange in SPD-Rot, Rohr in Orange) aus
`stichwahl-karte.tsx::kartenfarbe`, statt eigene zu erfinden.

**E4 – Briefwahl.** *Empfehlung:* Die Briefwahl kommt nicht auf die Fläche. Die
Tafel nennt immer zusätzlich den **Wahlbereich mit Briefwahl** („im ganzen
Wahlbereich III inkl. Briefwahl: …“). Unter der Karte steht eine Zeile: „Farben
nach den Wahllokalen. Ein Drittel der Stimmen kam per Brief und hat keinen
Ort.“ So bleibt die Karte quellenehrlich, ohne sich selbst zu erklären
(DESIGNSPRACHE, Anti-Patterns).

**E5 – iOS.** *Empfehlung:* Die App kommt im selben Plan dran, als letzter PR
und erst nachdem Tim die Web-Fassung abgenommen hat. Die App hat heute
**keine** Wahl-Ebene (`grep -ri wahlergebnis ios/` ist leer).

## 3. Bauform

```
Stadt-Stufe                       Ortsbereich-Stufe (z. B. Krusenbusch)
┌─────────────────────────┐       ┌─────────────────────────┐
│ 91 Bezirke in Sieger-   │ Klick │ die Bezirke, die ihn    │ Tipp auf
│ farbe, Deckkraft=Vor-   │ auf   │ berühren (≥ 5 % Fläche),│ Bezirk
│ sprung; Ortsbereichs-   │ Stadt-│ VOLLER Umriss, außerhalb│ ──────►  Tafel: „Wahlbezirk 515 ·
│ grenzen weiß darüber    │ teil  │ des Ortsbereichs blass; │          Grundschule Krusenbusch“
│ Hover: Bezirk + Stadtteil│─────►│ Ortsbereich-Umriss oben │          alle Listen, Vorsprung,
└─────────────────────────┘       └─────────────────────────┘          Beteiligung, Wahlbereich
                                                                        inkl. Brief, → /wahlabend
```

Drei Regeln gelten, die nicht offensichtlich sind:

- **Der Klick auf der Stadt-Stufe trifft den Ortsbereich, nicht den Bezirk.**
  So will es der Wunsch („Stadtteil anklicken → Wahlbezirke“), und so arbeitet
  die Stufe heute schon. Technisch fängt eine transparente Ortsbereichs-Ebene
  **über** den Bezirken die Klicks ab. Der Hinweis beim Zeigen nennt trotzdem
  den Bezirk unter dem Zeiger, dafür reicht ein Punkt-in-Polygon-Test auf den
  91 Flächen.
- **Auf der Ortsbereich-Stufe wird der Bezirk ganz gezeigt und nicht auf den
  Ortsbereich zugeschnitten.** Ein beschnittener Bezirk 204 sähe aus wie
  „Innenstadt hat so gewählt“, obwohl 71 % der Stimmen aus Eversten und dem
  Dobbenviertel kommen. Der Teil außerhalb ist blass, der Umriss des
  Ortsbereichs liegt obenauf.
- **Die Tafel nennt die Überlappung**, wenn sie klein ist: „Liegt nur zu 23 %
  in Neuenwege.“ Ab 80 % entfällt der Satz.

## 4. PRs

Jeder PR geht gegen `dev` und bekommt ein Changelog-Fragment, mit Ausnahme von
PR 1. Jeder UI-PR braucht vor dem Merge **Bilder in hell und dunkel sowie auf
dem Handy** für Tim (stehende Regel).

### PR 1 – Zuordnung Wahlbezirk ↔ Ortsbereich (Daten, kein UI)

**Dateien:** `scripts/wahl_geodaten.py` (neuer Unterbefehl `ueberlappung`),
neue Datei `kommunalwahl/geo/wahlbezirk-ortsbereiche.json`,
`tests/test_wahl_geodaten.py`.

- Das Skript schneidet jeden der 91 Bezirke mit den 31 Ortsbereichen und
  schreibt `{ "101": [{"place": "Bürgerfelde", "share": 0.97}, …], … }`.
  Anteile unter 5 % fallen weg, danach wird auf 1 normiert.
- **Ohne shapely**, denn shapely steht in keiner requirements-Datei und soll
  dort auch nicht hin. Die Fläche wird über ein **Raster mit 20 m Abstand und
  Punkt-in-Polygon** bestimmt. Das ist deterministisch und reicht bei Bezirken
  von mehreren hundert Metern völlig. Einmalig gegen shapely prüfen (Anhang A):
  Die Abweichung je Anteil muss unter 2 Punkten liegen. Die Zahl gehört in die
  PR-Beschreibung.
- Die Datei wird eingecheckt wie die Umrisse selbst. Neu gerechnet wird mit
  `hol`, also vor der nächsten Wahl.
- **Tests:** Jeder der 91 Bezirke hat mindestens einen Ortsbereich. Die Anteile
  ergeben zusammen 1 (± 0,01). **Innenstadt und Drielake** kommen je in
  mindestens einem Bezirk vor (Messung 2). 204 steht zu weniger als 50 % in der
  Innenstadt. Kein Ortsname fehlt in `stadtteile-oldenburg.json`.

### PR 2 – Backend: Karte je Wahl, gerechnet im Backend

Es gilt die Regel „Logik ins Backend“: Wer vorn lag, wie groß der Vorsprung
ist und welcher Bezirk zu welchem Ortsbereich gehört, rechnet der Server, nicht
jede Oberfläche für sich (Web und iOS).

**Neuer Endpunkt** `GET /api/wahlabend/karte?wahl=<slug>&place=<Ortsbereich?>`
in `routers/wahlabend.py`. Er ist öffentlich und hängt am Schalter `wahlabend`
wie seine Nachbarn. Die Antwortform kommt nach `antworten.py`:

```python
class ElectionMapDistrict(TypedDict):
    number: int
    name: str
    area: int
    counted: bool
    #: Slug der stärksten Liste bzw. Kandidatur — None, solange nicht gezählt.
    leader: str | None
    #: Vorsprung auf Platz 2 in Prozentpunkten — trägt die Deckkraft.
    margin_pct: float | None
    turnout_pct: float | None
    #: Wo der Bezirk liegt: Ortsbereiche mit Flächenanteil, größter zuerst.
    places: list[ElectionMapPlace]          # {name: str, share: float}
    #: Alle Listen, stärkste zuerst (für die Tafel; die Karte braucht nur leader).
    parties: list[ElectionDistrictParty]

class ElectionMap(TypedDict):
    election: ElectionInfo                   # Titel, Datum, Art (Liste/Person)
    #: Stammdaten der Listen/Kandidaturen: slug, short, name, color, color_dark
    contestants: list[ElectionMapContestant]
    #: Anteil der Briefwahl an allen gültigen Stimmen — für die Hinweiszeile.
    postal_share_pct: float
    districts: list[ElectionMapDistrict]     # nur Urnenbezirke (91)
    #: mit ?place=: die Wahlbereiche, die der Ortsbereich berührt, MIT Briefwahl
    areas: list[ElectionMapArea]
```

- Grundlage ist `_districts(None, None, wahl)`, also der eingefrorene Stand
  aus `archive`. Ohne `wahl` gilt die jüngste abgeschlossene Wahl. Ist gerade
  eine Wahl live, kommt der Live-Stand wie heute, und der Abruf läuft alle 60 s.
- Personenwahlen (OB) liefern in `contestants` die Kandidaturen mit den
  Kartenfarben der Stichwahl-Karte. **Die Farbzuordnung zieht vom Frontend ins
  Backend um** (`election/service.py`). `stichwahl-karte.tsx` liest sie dann
  von dort, damit es eine Fassung gibt und nicht zwei.
- `?place=` filtert auf Bezirke mit Anteil > 0 in diesem Ortsbereich. Ein
  unbekannter Name ergibt 404.
- **Vertrag neu schneiden** (`web/backend/CLAUDE.md`): `api/openapi.json`,
  `lib/api-schema.ts`, `lib/vertrag.ts`.
- **Tests** (`tests/test_wahlabend_karte.py`): Für die Ratswahl 2026 liefert
  der Endpunkt SPD 49 / Grüne 39 / AfD 2 / Linke 1 als `leader`. Bezirk 515
  hat `leader == "afd"` und `margin_pct ≈ 8,9`. `postal_share_pct ≈ 32,2`.
  Für `place=Innenstadt` kommen mindestens 3 Bezirke zurück. Für die Stichwahl
  haben alle 91 Bezirke einen `leader` aus den beiden Kandidaturen. Die
  Rauchprobe nimmt den Endpunkt mit auf (öffentlich, nichts Persönliches).

### PR 3 – Web, Stadt-Stufe

**Dateien:** `components/stadt-karte.tsx`, `app/(app)/karte/view.tsx`,
`lib/wahl-flaechen.ts` (wird zu reinen Funktionen über `ElectionMap`),
`lib/karten-ebenen.ts` (Quellenzeile), neu `components/wahl-bezirke-ebene.ts`
(der Leaflet-Layer als Funktion, damit `stadt-karte.tsx` nicht über 400
Zeilen wächst).

- Ist die Ebene an, zeichnet die Stadt-Stufe **die 91 Bezirke** aus
  `/geo/wahlbezirke-oldenburg.json` (lazy, 44 KB) in der Farbe des `leader`.
  Die Deckkraft ist `0.15 + 0.6 · min(1, margin_pct / 20)`. Bei 20 Punkten
  Vorsprung ist die Fläche satt, bei unter 3 Punkten fast leer. Die
  Ortsbereichsflächen darüber haben keine Füllung, einen weißen Rand von 1 px
  und fangen den Klick ab.
- Die bisherige Tönung der Ortsbereiche nach dem Wahlbereich
  (`wahlFlaechen`, `toenungNachStaerke`) **entfällt**. Sie war „ungefähr“ und
  wird jetzt durch das Genaue ersetzt. Die Tests dazu werden entsprechend
  angepasst.
- Beim Zeigen erscheint ein Hinweis mit Bezirksnummer, Name, Ortsbereich und
  den ersten drei Listen als Punkt mit Prozent. Das HTML folgt dem Muster von
  `hinweisHtml`.
- Die **Wahl-Chips** (E3) sitzen am Ebenen-Chip „Wahlergebnis“, nur solange
  die Ebene an ist. Die Adresse dazu ist `?wahl=ratswahl-2026`.
- Die **Legende** in der Tafel-Spalte ersetzt `WahlKarte` auf der
  Stadt-Stufe: je Farbe „vorn in N Bezirken“ (SPD 49, Grüne 39, …), dazu die
  Deckkraft-Leiste „knapp ↔ deutlich“ und die Briefwahl-Zeile (E4).
- **Browsertest** (`web/frontend/e2e/`): Ebene an → 91 Pfade mit
  `data-bezirk`. Klick auf Krusenbusch → Ortsbereich-Stufe. Chip „Stichwahl“
  → andere Farben, Adresse trägt `wahl=`.

### PR 4 – Web, Ortsbereich-Stufe und Bezirks-Tafel

**Dateien:** `components/stadt-karte.tsx`, `app/(app)/karte/view.tsx`, neu
`components/wahl-bezirk-tafel.tsx`.

- Die Ortsbereich-Stufe mit der Ebene holt
  `/api/wahlabend/karte?wahl=…&place=<Name>`. Sie zeichnet die Bezirke dieses
  Ortsbereichs in voller Form (s. § 3). Außerhalb des Ortsbereichs wird
  gedimmt. Dafür reicht eine Maske, also ein Polygon „Stadt minus
  Ortsbereich“ mit Loch, halb deckend darübergelegt. Jeder Bezirk trägt seine
  Nummer als Label, das ist bei der Menge gut lesbar (nach Hauptfläche
  höchstens 13 je Ortsbereich, mit der 5-%-Schwelle ein paar mehr, vorher
  zählen).
- Ein Tipp auf einen Bezirk bringt die **Bezirks-Tafel**: Titel „Wahlbezirk
  515 · Grundschule Krusenbusch“, darunter **alle** Listen als Zahlentabelle
  (Bauform-Pflicht, s. Notiz „Zahlentabellen-Bauform“) mit Punkt, Kurzname,
  Balken, Prozent und Stimmen. Dazu kommen Vorsprung, Wahlbeteiligung, der
  Überlappungssatz aus § 3 und der Wahlbereich **mit** Briefwahl zum Vergleich.
  Unten stehen zwei Links: „Diese Liste in allen Bezirken“ (`/wahlabend`
  Rangliste mit `party=`) und „Zum Wahlabend“. Der gewählte Bezirk steht in
  der Adresse (`&bezirk=515`), damit die Tafel sich teilen lässt.
- Die Auswahl eines Bezirks stellt die anderen blass, nach derselben Regel wie
  bei den Vorhaben (Tims Befund bei #1144).
- Auf dem Handy ist die Tafel das vorhandene Bottom-Sheet, keine neue Bauform.
- **Browsertest:** `/karte?ort=Krusenbusch&ebenen=wahlergebnis&wahl=ratswahl-2026`
  → Tipp auf 515 → Tafel nennt „AfD“ zuerst, „Stimmen“-Spalte mit 16 Zeilen.

### PR 5 – Designsprache und Doku

- DESIGNSPRACHE § 2 „Parteifarben“ bekommt eine **zweite Ausnahme**: die
  Wahl-Ebene der Stadtkarte, mit der Regel „Farbe = wer vorn, Deckkraft =
  Vorsprung, nie in Tafeln“ und dem Bild. Auch die Anti-Pattern-Zeile (§ 712)
  wird nachgezogen.
- `STADTKARTE-PLAN.md` Schritt 7 wird auf die neue Bauform nachgezogen, die
  Doku-Seite in `docs-site/` zur Stadtkarte ebenso.
- Dieser PR kann mit PR 3 zusammengehen, wenn der klein bleibt.

### PR 6 – iOS (erst nach Tims Abnahme der Web-Fassung)

**Dateien:** `ios/…/DistrictView.swift` und die Stadt-Karte der App,
Modelle handgeschrieben (`ios/CLAUDE.md`), XcodeGen-Nachzug bei neuen Dateien.

- Es gibt dieselbe Ebene als Umschalter. Die Bezirke sind `MapPolygon` in
  `leader`-Farbe mit derselben Deckkraftformel. Ein Tipp öffnet das Sheet mit
  derselben Tabelle. Die Daten kommen ausschließlich vom Endpunkt aus PR 2, die
  App rechnet nichts selbst.
- Die Geometrie bringt die App mit (Bundle) oder holt sie von
  `/geo/wahlbezirke-oldenburg.json`. Das entscheidet das andere Modell nach der
  Größe im Bundle.
- `python3 scripts/ios_vertrag.py` prüft den neuen Vertrag. Alle neuen Felder
  sind optional dekodiert.

## 5. Fertig, wenn

- Auf dev zeigt `/karte` mit der Ebene „Wahlergebnis“ die 91 Bezirke in
  Siegerfarbe. Krusenbusch sticht blau heraus, die Innenstadt ist nicht leer.
- Klick auf einen Stadtteil → seine Bezirke. Tipp auf einen Bezirk → die volle
  Aufteilung, teilbar über die Adresse.
- Umschalten auf OB-Wahl und Stichwahl funktioniert ohne Neuladen.
- Die Briefwahl ist genannt, aber nicht auf die Karte gerechnet.
- Tim hat die Bilder (hell/dunkel/Handy) vor jedem UI-Merge gesehen.
- **Kosten:** keine Modellaufrufe, keine neuen Crons, kein neuer Abruf fremder
  Server. Die Geometrie liegt schon im Repo.

## Anhang A – Messskripte

```python
# Überlappung Wahlbezirk × Ortsbereich (Referenz für PR 1; shapely nur lokal)
import json
from shapely.geometry import shape
bz = json.load(open("web/frontend/public/geo/wahlbezirke-oldenburg.json"))["features"]
st = json.load(open("web/frontend/public/geo/stadtteile-oldenburg.json"))["features"]
S = [(f["properties"]["name"], shape(f["geometry"]).buffer(0)) for f in st]
for f in bz:
    g = shape(f["geometry"]).buffer(0)
    ov = sorted(((s.intersection(g).area / g.area, n) for n, s in S), reverse=True)
    if ov[0][0] < 0.8:
        print(f["properties"]["nr"], [(round(a, 2), n) for a, n in ov[:3]])
```

```python
# Sieger je Urnenbezirk und Briefwahlanteil (Ratswahl 2026)
# Spalten D<n>_4 = Stimmen der Liste n in Stimmzettel-Reihenfolge
# (kommunalwahl/kandidaten.json → lists), D = gültige Stimmen.
import csv
r = list(csv.DictReader(open("kommunalwahl/referenz-2026/ratswahl-2026-wahlbezirke.csv"), delimiter=";"))
```

## Anhang B – Befunde, die nicht in diesen Plan gehören

- Die heutige Ebene fragt `/wahlabend` ohne `wahl=`. Ohne
  `WAHLABEND_ELECTION` ist das die **jüngste** Wahl, seit dem 20.09. also
  vermutlich die Stichwahl. Die Tönung nach der „stärksten Liste im
  Wahlbereich“ ist aber für Listenwahlen gebaut. Auf dev und Prod prüfen, was
  die Ebene gerade zeigt. Mit PR 3 ist die Frage ohnehin erledigt.

## Anhang C – Umsetzung (23.09.2026)

Tim hat die Empfehlungen E1–E5 am 23.09. angenommen („passt alles").

- **PR 1 + 2** zusammen als #1511: Die Überlappung wird auf einem 20-m-Raster
  gerechnet, die größte Abweichung gegen shapely beträgt 0,79 Punkte. Dazu
  kommt `GET /api/wahlabend/karte`. Nachgemessen: SPD **48** statt 49, weil
  Bezirk 400 ein Gleichstand ist (Grüne und SPD je 361 Stimmen). Die Karte
  strichelt ihn und zählt ihn in `ties`.
- **PR 3–5** zusammen, weil die Stadt- und die Viertel-Stufe dieselbe Abfrage
  teilen. Die Antwort kennt je Bezirk seine Ortsbereiche, deshalb braucht die
  Viertel-Stufe kein zweites `?place=`. Der Parameter bleibt für die App.
  Die Legende steht mit eingeschalteter Ebene oben in der Tafel.
- **Abweichung:** `stichwahl-karte.tsx` behält seine Farbregel. Vier Tage vor
  der Stichwahl wird die Seite nicht angefasst. Das Backend rechnet dieselbe
  Regel (`district_map.RUNOFF_SECOND`).
