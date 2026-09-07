# Stadtkarte — Umbauplan „Karte als Bühne“ (Richtung A)

> **Status:** Plan, beschlossen von Tim am 07.09.2026 nach den drei
> Bühnen-Entwürfen (Artefakt „Stadtkarte: drei Bühnen“). Noch nichts davon
> gebaut. Jeder Schritt unten ist ein eigener PR nach `dev`, hinter dem
> Feature-Schalter `stadtkarte`, bis Schritt 5 den Umzug macht.

## 1. Ziel in einem Absatz

Heute gibt es zwei Karten mit zwei Vokabularen: die **Stadtkarte** im
Themen-Tab (`/council?tab=themen`, Orte und Themen über alle Jahre, nach
Zahl der Beschlüsse gewichtet) und **Mein Viertel** (`/viertel`, Vorhaben
der letzten zwei Jahre mit Stand, Planflächen, Sperrungen, Presse). Beide
beantworten „wo passiert was“, nur verschieden nah. Daraus wird **eine
Karte mit drei Zoomstufen** — Stadt → Viertel → Vorhaben — und
**Ebenen-Chips**, die sagen, was auf der Karte liegt. Die Karte füllt die
Seite, rechts läuft eine Tafel-Spalte mit, die mit dem Zoom ihren Inhalt
wechselt. „Stadtkarte“ in der Navigation zeigt auf diese Karte; „Mein
Viertel“ bleibt der persönliche Einstieg in dieselbe Karte mit
vorgewähltem Ortsbereich. Eine Komponente, zwei Eingänge.

## 2. Was es schon gibt (und was davon bleibt)

| Baustein | Datei | Bleibt? |
|---|---|---|
| Leaflet-Karte der Themen-Orte, Cluster, Klick → Thema | `web/frontend/components/council-map.tsx` | wird zur **Ebene „Themen-Orte“** der neuen Karte; Cluster-Logik bleibt |
| Themen-Tab: Ortsbereich-Filter, Wahlbereichs-Schnellauswahl, Art-Filter, Top-Themen-Karten | `web/frontend/components/council-entities.tsx` | Filter werden Unter-Chips der Ebene; Top-Themen-Karten wandern in die Tafel-Spalte der Stadt-Stufe |
| SVG-Stadtkarte mit Wärmefärbung (Auswahl, Onboarding) | `web/frontend/components/stadtteil-karte.tsx` | bleibt im Onboarding; auf der neuen Karte übernimmt Leaflet die Färbung (GeoJSON-Ebene der 31 Umrisse) |
| Viertel-Karte: Pins, Straßenlinien, Planflächen, Sperrungen, Hover, Namensschild | `web/frontend/components/viertel-karte.tsx` | wird zum **Viertel-Zeichner** der neuen Karte (gleiches Leaflet, andere Stufe) |
| Auswahl (Anzeigetafel, Suche, Standort, Highlights, Rangliste) und Tafel | `web/frontend/app/(app)/viertel/view.tsx` (849 Zeilen) | wird in Bausteine zerlegt: `ViertelTafel`, `StadtTafel`, `VorhabenDetail` — dieselben Bausteine füllen die Tafel-Spalte |
| Endpunkte | `/api/districts/projects` (öffentlich), `/api/districts/{id}/projects` (optional_user), `/api/districts/lookup` (öffentlich), `/api/council/entities-map` (**require_active**) | alle bleiben; `entities-map` s. Entscheidung 1 |
| iOS | `DistrictView.swift` (MapKit, Sheet), `CouncilMapView.swift` (MKMapView mit Cluster), Routen `.district(id)` und `councilSection .map` | Schritt 6 führt beide in eine `CityMapView` zusammen |

## 3. Zielbild

### Adresse und Zustand

```
/karte                                   Stadt-Stufe
/karte?ort=fliegerhorst                  Viertel-Stufe
/karte?ort=fliegerhorst&v=94             Vorhaben-Stufe (Detail offen)
/karte?…&ebenen=vorhaben,plaene,sperrungen
```

`/viertel` und `/viertel?id=…&v=…` bleiben als **Einstiege** stehen (Mails,
Share-Links, iOS-Deep-Links, Dashboard) und führen nach dem Umzug auf die
neue Adresse — als **temporäre** Weiterleitung, nie permanent (permanente
Redirects kleben im Browser, s. Notiz Haushalts-Labor). Der Kartenzustand
(Ebenen, Ausschnitt) lebt in der URL und in `sessionStorage` (wie heute
`ratslotse:themen-karte-view`), damit „zurück“ den Ausschnitt behält.

### Layout

- **Desktop (Container ≥ 900 px):** Karte links, `flex: 1`, volle Höhe unter
  dem Kopf; rechts feste **Tafel-Spalte 420 px** (weiß, eigener Scroll).
  Ebenen-Chips oben links **auf** der Karte, Zoom-Knöpfe oben rechts,
  Brotkrumen unten links („Oldenburg › Fliegerhorst · Stadt zeigen“),
  Mini-Stadtkarte unten rechts (SVG aus `stadtteil-karte.tsx`, 200 px).
- **Mobil:** Karte 45 vh oben, darunter die Tafel als Seite; Detail als
  Bottom-Sheet (der heutige `Sheet` aus `viertel/view.tsx`). Keine zweite
  Fassung, dieselben Bausteine.
- Wurzel trägt `@container` (die Seiten-Layouts deklarieren keinen; ohne die
  Klasse griffen die Spalten-Varianten nie — Falle aus #1145).

### Drei Stufen

| Stufe | Karte | Tafel-Spalte |
|---|---|---|
| **Stadt** | 31 Umrisse als GeoJSON-Ebene, Füllung nach Zahl der Vorhaben (Wurzel-Skala wie heute), Hover hebt den Ortsbereich, Klick zoomt hinein; Themen-Orte als Cluster, wenn die Ebene an ist | Anzeigetafel (Stadtzahl, Stände), Suche + Standort, „Gerade in der Stadt“, Rangliste — 1:1 die heutige Auswahl, nur schmaler |
| **Viertel** | `fitBounds` auf den Ortsbereich; Pins, Linien, Planflächen, Sperrungen, Hover, Namensschild — 1:1 `viertel-karte.tsx` | Kopf (Name, Zahlen, Stand-Chips), Demnächst im Rat, Gesperrt und im Bau, Vorhaben-Liste, Investitionsprogramm, Aktuelles von der Stadt, Nebenan — 1:1 die heutige Tafel |
| **Vorhaben** | Pin groß, Ring, Schild; Karte fährt hin | `VorhabenDetail` mit Zurück-Pfeil zur Viertel-Tafel |

### Ebenen-Registry

`web/frontend/lib/karten-ebenen.ts` — **eine** Liste, aus der Chips, Legende,
Zeichner und Zähler kommen:

| id | Label | Farbe | Quelle | Stufen | Öffentlich |
|---|---|---|---|---|---|
| `vorhaben` | Vorhaben | Stand-Farben (`STAND_FARBE`) | `/districts/projects`, `/districts/{id}/projects` | Stadt (Wärme), Viertel (Pins) | ja |
| `plaene` | Bebauungspläne | Stand-Farbe, durchgezogen/gestrichelt | `locations[kind=bplan]` der Tafel | Viertel | ja |
| `sperrungen` | Sperrungen | `#b45309` | `closures` der Tafel | Viertel | ja |
| `themen-orte` | Themen-Orte | `KIND_COLOR` (Ort, Organisation, Projekt, Beschlussort) | `/council/entities-map` | Stadt, Viertel | heute nein (Entscheidung 1) |
| `beteiligungen` | Beteiligungen | Signal-Orange | `participations` + Plan-Umringe (Ebene 19 des Geoportals) | Viertel | ja |
| `presse` | Aktuelles | — (Liste, keine Geometrie) | `press` der Tafel | Viertel (nur Tafel) | ja |

Ein Chip trägt Farbe, Label und Zähler; aus ist er hohl. Ohne Zugriff
(Themen-Orte ohne Konto) zeigt er ein Schloss und führt zur Anmeldung.
Stand der Chips: URL-Parameter `ebenen`, sonst `localStorage`, Vorgabe
`vorhaben,plaene,sperrungen`.

## 4. Schritte — je ein PR

| # | PR | Inhalt | Prüfstein |
|---|---|---|---|
| 1 | **Karten-Bühne** | Schalter `stadtkarte` in `kern/features.py` (`fertig_wenn`: „/karte ist die Stadtkarte in der Navigation“). Route `app/(app)/karte/` (Gate: Schalter, sonst `notFound()`). `components/stadt-karte.tsx`: **ein** Leaflet mit Stufen-Zustand; Stadt-Stufe zeichnet die Umrisse gefärbt, Klick → Viertel-Stufe (`fitBounds`); Viertel-Stufe ruft den Zeichner aus `viertel-karte.tsx` (Funktion extrahieren, Komponente bleibt für `/viertel`). `viertel/view.tsx` in Bausteine zerlegen — `/viertel` verhält sich danach **unverändert** (E2E `03-oeffentlich` grün). Tafel-Spalte + mobiles Layout. URL-Zustand `ort`, `v`. | Fliegerhorst-Tafel sieht in `/karte?ort=fliegerhorst` aus wie in `/viertel?id=fliegerhorst`; Klick auf einen Ortsbereich auf der Stadt-Stufe zoomt hinein |
| 2 | **Ebenen-Chips** | Registry + Chips + Legende; Vorhaben, Pläne, Sperrungen ein-/ausschaltbar mit Zähler; `ebenen` in URL/`localStorage`; Zeichner lesen die Registry. Attribution je Ebene (Geoportal-Zeile nur, wenn eine Stadt-Ebene liegt). | Sperrungen aus → Linien weg, Karte „Gesperrt und im Bau“ bleibt |
| 3 | **Themen-Orte als Ebene** | `council-map.tsx` → Zeichner der Ebene (Cluster-Plugin nach Leaflet laden, Falle im Kopf der Datei). Art-Filter als Unter-Chips, Wahlbereichs-Schnellauswahl bleibt in der Stadt-Tafel. Top-Themen-Karten in die Stadt-Tafel unter die Highlights. Auf der Viertel-Stufe nur die Punkte im Ortsbereich (`ortsbereichFor` läuft heute schon im Client). | Themen-Tab und `/karte` zeigen dieselben Punkte für denselben Filter |
| 4 | **Beteiligungen als Fläche** | `plan_nrs` der Beteiligungen → Umringe (`bplan_outlines_by_keys`, Ebene 19 hat die laufenden Verfahren), Chip mit Frist, Popover mit Link zur Beteiligung. Backend: `participations` bekommt `geometry`. | Bloherfelde/Osternburg-Beteiligungen liegen als Fläche |
| 5 | **Umzug** | Navigation „Stadtkarte“ → `/karte`; Themen-Tab zeigt nur noch die Liste + Link „Auf der Karte“ (oder leitet weiter); `/viertel` → `/karte?ort=` (temporär); Dashboard-Karte, Mail-Deep-Links (`?zeig=`), Share-Links, `viertelHref()` auf die neue Adresse; Schalter raus; E2E `03-oeffentlich`, `04-council` nachziehen; Changelog. | Kein Link im Repo zeigt mehr auf `/council?tab=themen` als Karte |
| 6 | **iOS** | `CityMapView`: MapKit-Karte mit Stufen (Region der Stadt ↔ Ortsbereich), Ebenen als Chips über der Karte, Tafel als Sheet mit Detents (`DistrictView` liefert die Bausteine), Themen-Orte aus `CouncilMapView` als Ebene mit Cluster. Routen `.district(id)` und `councilSection .map` zeigen auf dieselbe View. Kein `APP_MIN_BUILD`: alles additiv, die alte App läuft weiter. | Simulator: Stadt → Fliegerhorst → Vorhaben in einer View; `ios_vertrag.py --ausgeliefert` leer |

Reihenfolge ist Pflicht: 1 vor 2 vor 3; 4 ist unabhängig ab 2; 5 erst,
wenn 1–4 auf dev gegengelesen sind; 6 kann parallel zu 3–5 laufen, sobald
der Vertrag aus 4 steht. Aufwand grob: 1 ist der größte (Zerlegung von
`view.tsx` + neue Bühne), 2 und 4 klein, 3 mittel, 5 mittel (viele
Berührpunkte), 6 groß.

## 5. Entscheidungen, die Tim treffen muss

1. **`/api/council/entities-map` öffentlich machen?** Heute `require_active`
   (mit `record_activity` für die Admin-Statistik). Die Daten sind amtliche
   Orte und Themen — Empfehlung: öffentlich, `record_activity` nur bei
   Konto; sonst trägt der Chip ein Schloss und die Karte ist ohne Konto
   halb leer.
2. **Zeitraum.** Richtung A hat bewusst keinen Zeitraum-Chip; Vorhaben sind
   „zwei Jahre“, Themen-Orte „alle Jahre“. Bleibt das so, steht der
   Zeitraum als Zähl-/Zeitraum-Angabe im Kicker (Designsprache: ehrliche
   Mengen), nicht als Schalter.
3. **Wahlbereichs-Schnellauswahl** behalten? Ja bis zur Kommunalwahl am
   13.09.2026 (der Wahl-Agent baut ein Dashboard — abstimmen, ob die Karte
   später eine Ebene „Wahlergebnis“ bekommt).
4. **Mobil:** Karte 45 vh + Tafel darunter (Empfehlung, gleiche Bausteine)
   oder Vollbild-Karte mit Sheet-Griff wie in der App.
5. **Menü:** „Mein Viertel“ bleibt als eigener Eintrag (persönlicher
   Einstieg, vorgewählter Stadtteil) neben „Stadtkarte“, oder nur noch
   „Stadtkarte“ mit dem eigenen Stadtteil als erstem Knopf in der Tafel.

## 6. Fallen, die schon bekannt sind

- **Zwei Leaflet-Karten auf einer Seite** gehen nicht gut (`_leaflet_id`,
  StrictMode-Doppelmount — s. Kopf von `council-map.tsx`). Die neue Bühne
  hat genau **eine** Karte; die Mini-Stadtkarte unten rechts ist SVG.
- **Cluster-Plugin nach Leaflet laden** (`leaflet.markercluster` erweitert
  das Browser-Singleton), sonst fehlt `markerClusterGroup`.
- **Nicht alles auf einmal laden.** 137 Vorhaben sind klein, 660 Planflächen
  (Median 3 KB) nicht. Stadt-Stufe holt nur Zähler und Punkte, die
  Viertel-Stufe die Geometrien des einen Ortsbereichs — so wie heute.
- **`@container` an der Wurzel**, sonst greift keine Spalten-Variante.
- **Keine permanenten Redirects** für `/viertel` → `/karte`.
- **Der Schalter ist eine Schuld** (`fertig_wenn` pflegen; `tests/test_features.py`
  meldet einen Schalter, den niemand liest).
- **Browsertests** brauchen zwei Server; `03-oeffentlich` prüft `/viertel`
  ohne Konto — `/karte` kommt dazu, sobald der Schalter fällt.
- **CARTO-Key** bleibt in `lib/basemap.ts`; keine Kachel-URL in die neue
  Komponente.

## 7. Was NICHT Teil des Plans ist

Der Live-Datenlauf (Register, Geoportal-Spiegel, Presse-Orte) bleibt, wie
er ist. Benachrichtigungen „Neu in deinem Viertel“ sind ein eigenes
Vorhaben. Die Wahlkarte ist ein eigenes Vorhaben des Wahl-Agenten; die
Ebenen-Registry ist so gebaut, dass sie eine Ebene „Wahlergebnis“ später
aufnimmt.
