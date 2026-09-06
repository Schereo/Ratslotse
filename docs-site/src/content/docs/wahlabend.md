---
title: "Feature: Wahlabend"
description: Die Ratswahl am 13.09.2026 live — Open-Data-CSVs des Votemanagers, Sitzzuteilung nach NKWG, Hochrechnung, Generalprobe und Betrieb am Wahlsonntag.
---

Am 13. September 2026 wird der Rat der Stadt Oldenburg gewählt. Die Seite
`/wahlabend` zeigt an diesem Abend den Auszählungsstand, die Sitze je Liste und
Wahlbereich und — sobald die Personenstimmen vorliegen — wer nach dem
Niedersächsischen Kommunalwahlgesetz gerade im Rat wäre. Die Zahlen sind die
amtlichen Open-Data-Dateien der Stadt; gerechnet wird bei uns.

Der Bereich ist der ungewöhnlichste im ganzen Projekt: **keine Datenbank, kein
Cron, kein LLM.** Er liest drei CSV-Dateien, rechnet und antwortet.

:::note[Hinter dem Feature-Schalter `wahlabend`]
Der Endpunkt und die Seite hängen am Schalter `wahlabend` aus
[`kern/features.py`](https://github.com/Schereo/Ratslotse/blob/main/kern/features.py).
Ohne ihn antwortet `GET /api/wahlabend` mit 404, und die Seite zeigt einen
Hinweis statt Zahlen. Nicht am Umgebungs-Gate — die Seite soll am Wahlabend
auf Prod laufen und danach ohne Deploy wieder dunkel werden können.
:::

## Woher die Zahlen kommen

Die Stadt betreibt zur Wahl einen **Votemanager** (KDO) mit einer
Ergebnispräsentation und einem Open-Data-Bereich. Drei Dateien tragen alles,
was wir brauchen; sie haben denselben Kopf und unterscheiden sich nur im
Zuschnitt des Gebiets:

| Datei | Zeilen |
|---|---|
| `…-Stadtratswahl-Stadt.csv` | eine — die ganze Stadt |
| `…-Stadtratswahl-Wahlbereiche.csv` | sechs — die Wahlbereiche I bis VI |
| `…-Stadtratswahl-Wahlbezirk.csv` | 133 — die einzelnen Wahlbezirke (Briefwahlbezirke tragen 9xx) |

Basis ist `https://votemanager.kdo.de/20260913/03403000` mit der Präsentation
unter `/praesentation/` (Wahl-ID 913, Stadtratswahl) und den CSVs unter
`/daten/opendata/`. Der Votemanager schickt **kein CORS**: Der Browser darf die
Dateien nicht selbst holen, also holt das Backend sie und liefert ein fertiges
Bild aus. Das ist ohnehin die richtige Arbeitsteilung — die Sitzzuteilung
gehört nicht in den Browser.

### Das Spaltenschema

Je Wahlvorschlag `n` stehen in jeder Zeile vier Größen. Das Schema hat sich
zwischen 2021 und 2026 geändert; `votemanager.parse` erkennt am Kopf, welches
vorliegt, und liest beide:

| Bedeutung | 2026 | 2021 |
|---|---|---|
| Listenstimmen | `D<n>_1` | `D<n>_liste` |
| Summe der Personenstimmen | `D<n>_3` | `D<n>_summe_kandidaten` |
| Gesamt (Liste + Personen) | `D<n>_4` | `D<n>_summe_liste_kandidaten` |
| Stimmen für Listenplatz `k` | `D<n>_2_<k>` | `D<n>_<k>` |

Davor stehen `A` (Wahlberechtigte), `B` (Wähler\*innen), `C1`/`C2` (ungültige
und gültige Stimmzettel), `D` (gültige Stimmen) sowie
`max-schnellmeldungen` / `anz-schnellmeldungen` als Auszählungsstand des
Gebiets. Ein Einzelwahlvorschlag hat nur `D<n>_4`.

:::caution[Leer heißt „liegt noch nicht vor", nicht null]
Genau daran hängt die halbe Anzeige. `_int()` liefert für ein leeres Feld
`None`, und `None` reist bis in die Antwort durch: `votes: null` heißt „noch
nicht ausgezählt", `votes: 0` heißt „null Stimmen". Wer die beiden Fälle
zusammenwirft, zeigt um 20 Uhr eine Partei mit null Stimmen an, die nur noch
nicht gemeldet hat.
:::

### Wahlbezirk → Wahlbereich

Die CSV der Wahlbezirke sagt nicht, zu welchem Wahlbereich ein Bezirk gehört.
Die Nummer sagt es: Urnenbezirke tragen den Wahlbereich als **Hunderter**
(101…115 = I, 400…416 = IV), Briefwahlbezirke als **Zehner hinter der 9**
(910…916 = I, 960…966 = VI). `area_of_district()` setzt das um; gemessen ist
die Regel an allen 133 Bezirken von 2021 — die Summen je Wahlbereich ergeben
dort genau die Wahlbereichs-Zeilen (`tests/test_wahlabend.py`).

### Abruf und Cache

`votemanager.fetch()` hält ein Ergebnis 60 Sekunden — so lange cacht auch der
Votemanager selbst, häufiger zu fragen bringt nichts. Scheitert der Abruf,
bleibt der **letzte gute Stand** stehen und bekommt einen Fehlervermerk:
`source.ok = false` und `source.error` reisen mit in die Antwort, die Zahlen
bleiben die alten. Gab es noch nie einen guten Stand, ist die Antwort leer,
aber wohlgeformt — Phase `before`, sechs Wahlbereiche, keine Sitze.

## Das Kandidatenregister

Die CSVs kennen nur Spaltennummern und Listenplätze, keine Namen. Die stehen in
der **amtlichen Bekanntmachung der zugelassenen Wahlvorschläge** (Wahlausschuss,
23.07.2026). `kommunalwahl/kandidaten.py` liest das PDF und schreibt
`kommunalwahl/kandidaten.json`: je Wahlbereich und Wahlvorschlag die
Bewerber\*innen mit Listenplatz, Name, Beruf, Jahrgang und Wohnort — 16
Wahlvorschläge, 383 Bewerber\*innen, 52 zu vergebende Sitze.

Gelesen wird über die **Koordinaten**, nicht über den Text: Die Textfassung
setzt Name und Beruf in eine Zeile, und wo das eine aufhört, steht dort
nirgends. Im PDF stehen die Felder in Spalten, und `visitor_text` von pypdf
liefert zu jedem Textstück seine Position — die Spaltenkanten stehen als
Konstanten oben in `kandidaten.py`.

:::note[Die Reihenfolge ist der Stimmzettel]
Die Wahlvorschläge stehen in der Bekanntmachung in der Reihenfolge des
Stimmzettels, und das ist zugleich die Reihenfolge der Spalten `D1 … D16` in
den CSVs. Das Register braucht deshalb keine Zuordnungstabelle — der Index
einer Liste **ist** ihre Spaltennummer. Geprüft wird es trotzdem: Die
Höchstzahl an Bewerber\*innen je Liste muss Spalte für Spalte mit den
CSV-Köpfen übereinstimmen.
:::

Die Farben je Liste kommen aus `kommunalwahl/parteien-meta.json`; eine Liste
ohne Eintrag bekommt einen neutralen Grauton. `register.load()` ist
`lru_cache`-gehalten — die Datei wird einmal je Prozess gelesen.

## Die Sitzzuteilung (NKWG §§ 36, 37)

`election/seats.py` rechnet **dreimal Hare/Niemeyer**, in dieser Reihenfolge:

1. **Die Sitze des Rates auf die Wahlvorschläge** nach ihren Gesamtstimmen im
   ganzen Wahlgebiet (§ 37 Abs. 2 i. V. m. § 36 Abs. 2 und 3).
2. **Die Sitze jeder Partei auf ihre Wahlbereichslisten** nach den dort
   erzielten Stimmen (§ 37 Abs. 3). Es gibt **keine feste Sitzzahl je
   Wahlbereich** — wo eine Partei stark ist, holt sie dort mehr Sitze.
3. **Die Sitze einer Wahlbereichsliste auf Liste und Personen**, im Verhältnis
   Listenstimmen zu Personenstimmen (§ 36 Abs. 4). Personensitze gehen nach
   höchster Stimmenzahl (Abs. 5), Listensitze nach Listenreihenfolge an die
   noch nicht Gewählten (Abs. 6).

Dazu zwei Sonderfälle, die selten sind und trotzdem vorkommen: Bekommt eine
Liste mehr Sitze, als sie Bewerber\*innen hat, wandern die überzähligen zu den
stimmenstärksten nicht gewählten Bewerber\*innen **derselben Partei in anderen
Wahlbereichen** (§ 37 Abs. 5, in der Antwort als `kind: "transfer"`). Ein
Einzelwahlvorschlag hat keine anderen Wahlbereiche — sein zweiter Sitz bliebe
unbesetzt (§ 36 Abs. 7) und steht dann als Hinweis in `notes`.

:::note[Ganze Zahlen, kein Gleitkomma]
Der Bruchteil von `v·s/T` ist `(v·s) mod T`, und zwei Bruchteile mit demselben
Nenner vergleicht man als Reste. Die ganze Rechnung läuft damit in `int` —
keine Rundungsfrage, kein „0,49999999". Wo der letzte vergebene und der erste
nicht vergebene Rest **gleich** sind, hätte das Los entschieden; dort gewinnt
bei uns die Eingabereihenfolge, und der Fall wird als Menschentext in `notes`
ausgewiesen statt stillschweigend entschieden.
:::

**Verifiziert gegen das amtliche Ergebnis der Ratswahl 2021**: alle 50 Mandate,
einschließlich der Unterscheidung „direkt" gegen „über die Liste"
(`tests/test_wahlabend.py`). Das ist der einzige belastbare Beweis, den es vor
dem Wahlabend gibt — dieselben Eingaben, dasselbe Ergebnis wie der
Wahlausschuss.

### Abstände: „Wie viele Stimmen fehlen?"

Die Zuteilung ist schnell genug, um sie oft zu wiederholen — und genau das tut
der Bereich, um die interessantere Frage zu beantworten:

- `votes_to_seat` je Kandidatur — die kleinste Zahl zusätzlicher
  Personenstimmen, mit der diese Person einen Sitz hätte, alles andere
  unverändert. Binärsuche über die vollständige Zuteilung, Suchgrenze
  30.000 Stimmen; `0` heißt „schon drin", `null` „außer Reichweite".
- `votes_to_next_seat` / `votes_to_lose_seat` je Liste — dasselbe auf Stufe 1,
  gedacht als Listenstimmen im stärksten Wahlbereich der Liste, Suchgrenze
  80.000.

Diese Abstände sind der Grund, warum das Zusammensetzen einer Antwort rund zwei
Sekunden dauert — und damit der Grund für den Cache im nächsten Abschnitt.

## Die Hochrechnung

Kein Modell mit Anspruch, sondern das, was man am Wahlabend im Kopf tut: Für
jeden **noch offenen** Wahlbezirk sein Ergebnis von 2021 nehmen und mit dem
Trend skalieren, den die schon ausgezählten Bezirke **desselben Wahlbereichs**
für diese Liste zeigen (`Stimmen 2026 / Stimmen 2021` über die ausgezählten
Bezirke).

Das geht nur, weil die Wahlbezirke 2026 genauso geschnitten und nummeriert sind
wie 2021 — gleiche Zahl, gleiche Wahllokale. Die Referenz liegt als drei CSVs
von 2021 im Repo (`kommunalwahl/referenz-2021/`, altes Spaltenschema) und wird
über `ratswahl-2021.json` auf die Listenindizes von 2026 umgeschlüsselt; Listen
ohne Nachfolger 2026 fallen dabei weg.

Die Randfälle:

- **Eine Liste ohne 2021er Vergleich** (BSW, PGM, …) bekommt ihren bisherigen
  Stimmenanteil auf die geschätzten gültigen Stimmen der offenen Bezirke.
- **Im Wahlbereich noch nichts ausgezählt** → es gilt der stadtweite Trend.
- **Stadtweit noch nichts ausgezählt** → es gibt keine Hochrechnung.
- **Ein ausgezählter Bezirk ohne Gegenstück von 2021** wird gezählt und als
  Hinweis in `notes` genannt — kein Fehler, nur eine Lücke in der Basis.

Aus den hochgerechneten Stimmen läuft dieselbe Zuteilung noch einmal; ihr
Ergebnis steht getrennt in `projected_seats` und `projected_mandates`. Die
Seite hält beides auseinander: „drin" ist ausgezählt, „Hochrechnung: drin" ist
gerechnet, und wo sich beide widersprechen, sagt sie das („drin · direkt ·
Hochrechnung: raus").

:::caution[Eine Faustregel, kein Modell]
Die Hochrechnung kennt keine Briefwahl-Eigenheiten, keine Kandidatenwirkung und
keine Wahlbeteiligungs-Prognose. Sie ist gegen sich selbst geprüft — mit den
2021er Zahlen als Wahrheit trifft sie das Endergebnis von 2021 —, was nur
heißt, dass die Mechanik stimmt, nicht dass die Vorhersage taugt. Amtlich ist
allein, was der Wahlausschuss feststellt.
:::

## Der Endpunkt

`GET /api/wahlabend` — öffentlich (die Zahlen sind es auch), ohne Konto, hinter
dem Feature-Schalter. Zwei Query-Parameter:

| Parameter | Wirkung |
|---|---|
| `probe=2021` | Generalprobe: die Zahlen von 2021 im Register von 2026 |
| `counted=N` | nur für die Generalprobe — nur die ersten `N` Wahlbezirke gelten als ausgezählt (0…500) |

Die Antwortform ist `ElectionNight` in `web/backend/app/antworten.py` und damit
Teil des API-Vertrags; das Frontend leitet seine Typen daraus ab
(`lib/wahlabend.ts`). Die tragenden Felder:

| Feld | Inhalt |
|---|---|
| `dataset` | `live` oder `probe` |
| `phase` | `before` (nichts ausgezählt) · `counting` · `complete` |
| `person_votes_available` | ob irgendwo schon Personenstimmen vorliegen |
| `source` | `fetched_at`, `last_modified` (Stand beim Votemanager), `ok`, `error` |
| `progress` | Schnellmeldungen erwartet und eingegangen |
| `parties` | je Liste: Stimmen, Anteil, Sitze, Hochrechnung, 2021er Vergleich, Abstände |
| `areas` | je Wahlbereich: Stand, Summen und je Liste ihre Bewerber\*innen mit Personenstimmen |
| `mandates` / `projected_mandates` | wer einen Sitz hat, mit `kind`: `direct` · `list` · `transfer` · `unknown` |
| `notes` | Menschentext: Losfälle, unbesetzte Sitze, fehlende Personenstimmen |

### Zwei Cache-Stufen

Weil das Zusammensetzen rund zwei Sekunden dauert, wird das fertige Bild
gehalten und nach Ablauf **im Hintergrund** erneuert, während die alte Antwort
weiter ausgeliefert wird (Stale-while-revalidate). Darunter liegt der
60-Sekunden-Cache des CSV-Abrufs. Die Generalprobe wird je `counted`-Wert genau
einmal gerechnet und dann behalten — ihre Zahlen ändern sich ja nicht.

Beide Caches leben im Prozess: Ein Neustart des Dienstes setzt sie zurück, ein
zweiter Worker hätte seine eigenen.

## Die Seite `/wahlabend`

Die Seite liegt wie `/kommunalwahl` und `/changelog` **außerhalb** von
`app/(app)/` — kein Konto-Gate, eigener Kopf. Alles Gerechnete kommt fertig vom
Backend; `lib/wahlabend.ts` enthält nur Anzeige-Logik (Formate, Sortierung, der
Status einer Kandidatur in Worten).

Der Aufbau folgt der Reihenfolge, in der man am Wahlabend fragt: Wie weit ist
die Auszählung (Anzeigetafel) → wie stehen die Listen (Tafel mit Balken,
Vergleich zu 2021, Sitzband) → und dann für **eine** gewählte Liste: wer ist in
welchem Wahlbereich drin, wer ist knapp dran. Die gewählte Liste steht in der
URL (`?liste=<slug>`) und im `localStorage`, überlebt also das Neuladen.

Abgefragt wird einmal je Minute (`refetchInterval`), passend zum Cache des
Votemanagers. Drei Zustände ohne Zahlen sind ausdrücklich gestaltet: Schalter
aus, Abruf gescheitert, Phase `before` vor der ersten Meldung.

## Was am Wahlsonntag noch offen ist

**Ob die Personenstimmen mit ausgezählt werden oder zunächst nur die Summen je
Liste**, ist vorab nicht sicher zu sagen. Bei der Kommunalwahl wird jede Stimme
einer Person gegeben; das aufzuschlüsseln ist der aufwendige Teil der
Auszählung, und die Schnellmeldung kann sich zunächst auf die Summen je Liste
beschränken.

Der Bereich muss das nicht wissen — er erkennt es am CSV: Liegen weder
Listenstimmen noch Stimmen je Listenplatz vor, setzt `person_votes_available`
auf `false`. Dann liefert die Seite **Sitze je Liste und Wahlbereich, aber
keine Namen**: Die Mandate tragen `kind: "unknown"`, und in `notes` steht der
Satz dazu. Kommen die Personenstimmen später, füllen sich Namen und Abstände
von selbst — ohne Deploy, ohne Umschalten.

## Am Wahlabend

**1. Den Schalter setzen.** In der `.env` auf dem Server, dann den Dienst neu
starten:

```bash
FEATURE_FLAGS=wahlabend
```

Der Schalter kommt über `/api/app-config` auch im Frontend an — ein Neubau ist
dafür nicht nötig, ein Neustart des Backends schon.

**2. Die Generalprobe ansehen.** Vor dem Ernstfall dieselbe Seite mit echten
Zahlen, nur eben denen von 2021:

```
/wahlabend?probe=2021&counted=60     # 60 der 133 Wahlbezirke ausgezählt
/wahlabend?probe=2021                # alles ausgezählt: das Endergebnis 2021
```

`counted` zählt die Bezirke in der Reihenfolge der CSV, nicht in der, in der
sie am Wahlabend melden würden — es geht um die **Phase**, nicht um eine
Simulation des Abends. Mit einem mittleren Wert lässt sich prüfen, was die
Hochrechnung tut; mit dem vollen Lauf, ob die Zuteilung das amtliche Ergebnis
trifft.

**3. Was bei einem Netzfehler passiert.** Die Seite zeigt **den letzten guten
Stand mit Fehlervermerk** — nicht eine leere Seite und nicht Nullen. Der
Zeitstempel im Kopf ist der des Standes, nicht der des Aufrufs, die Anzeige
altert also sichtbar. Erst wenn der Dienst seit dem Start noch nie erfolgreich
abgerufen hat, gibt es nichts zu zeigen.

**4. Der Takt.** Drei 60-Sekunden-Stufen liegen hintereinander: der Cache des
Votemanagers, unser Bild, die Abfrage im Browser. Ein frisch gemeldeter
Wahlbezirk braucht entsprechend ein paar Minuten bis auf den Schirm — das ist
so gewollt und steht der Anzeige nicht im Weg, weil sie ihren eigenen Stand
ausweist.

**5. Den Votemanager-Pfad übersteuern.** Falls die Stadt eine andere Adresse
oder Wahl-ID benutzt als erwartet, muss dafür kein Code geändert werden:

```bash
WAHLABEND_VOTEMANAGER_URL=https://votemanager.kdo.de/<datum>/<gemeinde>
```

Darunter werden `/praesentation/` und die drei Dateien unter
`/daten/opendata/` angehängt. Nach der Änderung den Dienst neu starten (die
Caches liegen im Prozess).

**6. Danach.** Steht das amtliche Endergebnis fest (Wahlausschuss,
voraussichtlich in der Woche nach dem 13.09.2026), ist die Seite ein Rückblick
und braucht den Schalter nicht mehr — er kann aus der `.env` und samt seinem
Registry-Eintrag aus dem Code. Genau das steht als `fertig_wenn` in
`kern/features.py`.

## Dateien

| Pfad | Inhalt |
|---|---|
| `web/backend/app/election/votemanager.py` | Abruf und Parser der drei CSVs, beide Spaltenschemata, 60-s-Cache, Nummernregel Bezirk → Bereich |
| `web/backend/app/election/register.py` | Kandidatenregister aus `kandidaten.json` + Farben |
| `web/backend/app/election/seats.py` | Hare/Niemeyer und die Zuteilung nach §§ 36, 37 NKWG, dazu die Abstandsrechnungen |
| `web/backend/app/election/reference.py` | Die Ratswahl 2021 als Vergleich und Basis der Hochrechnung |
| `web/backend/app/election/projection.py` | Die Hochrechnung der offenen Wahlbezirke |
| `web/backend/app/election/service.py` | Zusammensetzen der Antwort, Generalprobe, Stale-while-revalidate |
| `web/backend/app/routers/wahlabend.py` | `GET /api/wahlabend` hinter dem Feature-Schalter |
| `web/backend/app/antworten.py` | Antwortform `ElectionNight` (Teil des API-Vertrags) |
| `web/frontend/app/wahlabend/` | Die Seite, außerhalb des Konto-Gates |
| `web/frontend/components/wahlabend/view.tsx` | Anzeigetafel, Listen-Tafel, Sitzband, Wahlbereiche, Mandate |
| `web/frontend/lib/wahlabend.ts` | Formate, Sortierung, Status einer Kandidatur in Worten |
| `kommunalwahl/kandidaten.py` | Erzeugt `kandidaten.json` aus der amtlichen Bekanntmachung (pypdf, Koordinaten) |
| `kommunalwahl/kandidaten.json` | 16 Wahlvorschläge, 383 Bewerber\*innen, 6 Wahlbereiche, 52 Sitze |
| `kommunalwahl/referenz-2021/` | Die drei Open-Data-CSVs von 2021 und die amtliche Sitzverteilung |
| `tests/test_wahlabend.py` | Zuteilung gegen 2021, Register gegen die CSV-Köpfe, Parser, Hochrechnung, Endpunkt |

## Was die Tests halten

Der Bereich hat keine Datenbank, an der man etwas nachsehen könnte — die Tests
sind deshalb die Dokumentation der Rechnung:

- **Hare/Niemeyer** gegen das Rechenbeispiel „Musterstadt" aus dem Erklärblatt
  des Wahlamts Braunschweig, dazu Losfall und Mehrheitsklausel.
- **Die Zuteilung reproduziert das amtliche Ergebnis 2021** — alle 50 Mandate
  mit ihrer Art.
- **Überhang wandert** in andere Wahlbereiche (§ 37 Abs. 5).
- **Ohne Personenstimmen gibt es Sitze, aber keine Namen.**
- **Das Register passt zu den CSV-Spalten 2026**, und die eingecheckte
  `kandidaten.json` ist der Stand des Skripts (`--pruefen`), nicht von Hand
  nachbearbeitet.
- **Die Nummernregel** trifft alle 133 Wahlbezirke.
- **Die Hochrechnung** trifft das Endergebnis, wenn die Referenz die Wahrheit
  ist — und liefert nichts, wenn noch nichts ausgezählt ist.
- **Der Endpunkt** ist ohne Schalter ein 404 und übersteht einen Netzfehler.
