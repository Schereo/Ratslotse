# Bauplan — Wahlprogramm-Vergleich in Ratslotse

**Gegenstand:** Der Datenbestand aus PR #356 (`kommunalwahl/`) wird zu einem öffentlichen
Bereich auf ratslotse.de und in der App. Ziel ist der 13.09.2026 (Ratswahl Oldenburg) —
sinnvoll live ab Ende August.

**Adressat dieses Dokuments:** die Design-/Frontend-Session, die daraus die Oberfläche baut.
Er beschreibt *was* angezeigt wird, *woher* es kommt und *wo* es technisch hängt. Die
Gestaltung selbst — Layout, Rhythmus, Komponenten-Optik — ist bewusst offen gelassen.

---

## 1. Was rein soll, was nicht

**Rein:**

- Inhaltlicher Vergleich der Listen, die ein echtes Kommunalwahlprogramm vorgelegt haben.
- Sichtbar machen, wo Listen beieinanderstehen und wo nicht.
- Jede einzelne Aussage mit Belegzitat und Link ins Originalprogramm der Partei.
- Ratslotse-Ton: kurz, verständlich, ohne Verwaltungsdeutsch.

**Raus (bewusst):**

- **Kein Selbsttest / kein Thesen-Durchklicken.** Der Lokal-O-Mat in Oldenburg macht genau
  das. Wir bauen kein zweites Werkzeug daneben und übernehmen auch keine Wahl-O-Mat-Optik.
  Die 44 Thesen bleiben eine **Vergleichsachse**, kein Fragebogen. (Ggf. später eigene Stufe.)
- Keine Empfehlung, keine Wertung, keine Rangliste „bestes Programm".
- Keine Parteilogos (Rechte, und wir brauchen sie nicht — `parteien-meta.json` hat Farben).
- Keine Verknüpfung mit dem Abstimmungsverhalten im Rat. Verglichen werden **Programme,
  nicht Politik**. Das gehört als Satz auf die Seite.

---

## 2. Was tatsächlich in den Daten steckt

Alles liegt gebündelt in `kommunalwahl/data.json` (353 KB). Die Einzeldateien darunter
(`digests/`, `positionen/`, `thesen.json`, …) sind die Quellen, aus denen `analyse.py`
diese Bündelung erzeugt — **die Oberfläche liest nur `data.json`.**

### 2.1 Die Datenlage — der wichtigste Befund

16 zugelassene Wahlvorschläge, aber nur 8 mit ausformuliertem Kommunalwahlprogramm.
`data.json → quellenart[slug].art` stuft jede Liste ein:

| Stufe | Listen | Bedeutung |
|---|---|---|
| `voll` (8) | SPD, CDU, Grüne, Linke, FDP, Bürger Bündnis, AfD, Volt | Eigenes Kommunalwahlprogramm |
| `landes` (1) | BSW | Landesweites Rahmenprogramm, nennt Oldenburg an keiner Stelle |
| `kurz` (4) | Für Oldenburg, Echt Oldenburg, DAVA, M. Stille | Nur Stichpunkte auf der Website bzw. ein Zeitungsporträt |
| `keins` (3) | Piraten, PGM, Die PARTEI | Nichts auffindbar |

Zu jeder Liste ohne Programm steht in `digests[slug].programm.hinweis` ein ausführliches
Rechercheprotokoll (was geprüft wurde, was gefunden wurde). Das ist die Belegkette für die
Aussage „hat kein Programm" — sie muss auf der Seite auffindbar, aber nicht laut sein.

### 2.2 Positionen zu den 44 Thesen

`data.json → positionen[slug].positionen[thesen_id]` = `{pos, beleg, seite}`
mit `pos` ∈ `+1` (dafür) / `0` (teils) / `−1` (dagegen) / `null` (keine Aussage).

| Liste | Positionen (von 44) | mit Belegzitat | mit Seitenzahl | Quelle |
|---|---:|---:|---:|---|
| SPD | 34 | 34 | 34 | PDF, 54 S. |
| CDU | 33 | 33 | **0** | Website |
| Volt | 33 | 33 | 33 | PDF, 71 S. |
| Grüne | 31 | 31 | 31 | PDF, 40 S. |
| Linke | 30 | 30 | 30 | PDF, 32 S. |
| BSW | 27 | 27 | 27 | PDF, 43 S. (Landesprogramm) |
| FDP | 24 | 24 | 24 | PDF, 16 S. |
| AfD | 23 | 23 | 23 | PDF, 48 S. |
| Bürger Bündnis | 19 | 19 | 17 | PDF, 11 S. |
| *alle übrigen* | 0–4 | | | keine belastbare Grundlage |

**Jede** gewertete Position trägt ein wörtliches Belegzitat. Bei PDF-Quellen zusätzlich die
Seitenzahl → Direktlink `<url>#page=N`. Die CDU hat ihr Programm nur als Website; dort führt
der Link auf die Seite, nicht auf eine Stelle (`quellen.cdu.seitenlink === false` sagt das an).

### 2.3 Was jede Liste inhaltlich sagt

`data.json → digests[slug]`:

- `charakter` — 60–100 Wörter Fließtext: Tonlage und Grundhaltung des Programms
- `kernpunkte` — je 7 Bullets: die zentralen Forderungen
- `besonderes` — 6–8 Bullets: was in diesem Programm auffällt und in keinem anderen steht
  (Grüne: „Interspecies Councils"; usw.) — **das ist der unterhaltsamste Teil des Bestands**
- `themen[<feld>]` — `{positionen: string[], seiten: number[], praegnanz: 0–3}` je Themenfeld;
  53–94 konkrete Forderungs-Bullets pro Liste, verteilt über 12 Themenfelder
- `programm` — Titel, URL, Format, Seitenzahl, Beschlussstand, Hinweise

### 2.4 Ähnlichkeit

`data.json → paare["a|b"]` = `{wert: 0–100, n, themen: {<feld>: {wert, n}}}`.
Für die 8 Voll-Listen ergibt das 28 Paare (mit BSW: 36). Alle haben `n ≥ 16` — die
`min_n = 5`-Schranke greift im Vergleichsset **nirgends**, sie bleibt aber als Regel gültig.

Spannweite: `cdu|fdp` 90 % (n=21) bis `linke|afd` 22 % (n=18).

### 2.5 Streitigkeit je These

`data.json → thesen_stat[]` = These + `{n, dafuer, teils, dagegen, streit: 0–1}`.

⚠️ **`streit` ist ohne n-Schranke unbrauchbar für eine Top-Liste.** Die streitigste These nach
Rohwert ist B3 mit `streit = 1.00` bei **n = 2** — zwei Listen, eine dafür, eine dagegen. Für
die Anzeige gilt: **n ≥ 5** (siehe §7.1).

Nach dieser Regel sind die echten Konfliktlinien:
Fliegerhorststraße (M1) · Stadion-Finanzierung (C1) · Aufnahme Geflüchteter (I4) ·
Klimavorgaben vs. Wirtschaftlichkeit (K4) — und die Baumschutzsatzung (K2, n=4, knapp drunter).

Und — mindestens so interessant — die **Einigkeit**: Gewaltschutz/Frauenhäuser (S3, 6 von 6
dafür), Housing First (S1, 5/6), Sportförderung (C2, 7/9), Bürokratieabbau (V1, 6/8).

### 2.6 Rahmendaten

`data.json → fakten`: Termin, 52 Sitze (von 50 erhöht), 383 Kandidierende, 16 Wahlvorschläge,
6 Wahlbereiche, Dreistimmenwahlrecht (kumulieren/panaschieren, ab 16, EU-Bürger:innen),
9 OB-Kandidaturen, Bürgerentscheid Baumschutz vom 22.02.2026 mit vollem Ergebnis.

---

## 3. Entscheidungen, die vor dem Bauen feststehen

**E1 — Verglichen werden 9 Listen: die 8 mit `art: voll`, plus BSW.**
BSW hat 27 belegte Positionen mit Seitenzahlen — die wegzuwerfen wäre Verschwendung. Aber das
Programm ist ein Landesrahmen, der Oldenburg **an keiner einzigen Stelle** erwähnt
(nachgeprüft), und 7 der 27 Positionen leiten sich ausdrücklich aus Forderungen an „alle
Kommunen" oder an das Land ab — K3 sogar aus der Kritik an einer Landesvorgabe. Also: **BSW ist
überall dabei, trägt die Markierung aber an jeder einzelnen Position**, nicht nur auf der
Parteikarte. Kein stiller Mitläufer.
*Umschaltbar an einer Stelle:* die Vergleichsmenge wird einmal als Konstante bestimmt
(`art === "voll" || slug === "bsw"`), nicht in jeder Komponente neu — wer BSW herausnimmt,
behält 8 Listen und 28 Paare. Begründung und Belegstellen: [`pruefbericht.md`](pruefbericht.md) §5.

**E2 — Die 7 übrigen Listen kommen vor, aber nicht im Vergleich.**
Der Nutzer-Wunsch war ein Satz am Anfang. Es sind aber drei verschiedene Sachverhalte, und die
gehören auseinandergehalten:

> *Sieben der 16 Wahlvorschläge treten ohne vergleichbares Programm an: **Piraten**, **PGM**
> und **Die PARTEI** haben keines veröffentlicht. **Für Oldenburg**, **Echt Oldenburg**,
> **DAVA** und **Michael Stille** haben nur wenige Stichpunkte bzw. ein Zeitungsporträt
> vorgelegt. Sie stehen in diesem Vergleich deshalb nicht — was sie sagen, steht trotzdem
> hier.*

Jede dieser Listen bekommt eine eigene kleine Karte mit dem, was es gibt (Kandidatenzahl,
Fundstelle, ggf. `kernpunkte`) und einem aufklappbaren „Was wir geprüft haben" aus
`programm.hinweis`. **Nicht** wegblenden — das wäre die unfairste Variante.

**E3 — Primärer Link geht immer aufs Original der Partei.** `quellen[slug].url` (+ `#page=N`).
Die archivierte Kopie ist ein *zusätzlicher* Link, klar als Archiv beschriftet, mit Stand und
SHA256-Prüfsumme.

**E4 — Neutralität ist eine Bauvorgabe, nicht eine Haltung.** Alle 9 Listen bekommen
identische Bauteile in identischer Reihenfolge, gleich viel Platz, gleiche Sortierung
(`fakten.wahlvorschlaege`-Reihenfolge = Kandidatenzahl absteigend, wie in `reihenfolge`). Keine
Liste bekommt einen einordnenden Zusatz, den eine andere nicht bekommt. Wo eine Position
kontrovers ist, steht das Belegzitat da — mehr nicht.

**E5 — Parteifarben nur als Datenmarke.** `meta[slug].farbe` / `.farbe_dunkel` für Chips,
Balken, Matrixzeilen. Flächen, Buttons und Navigation bleiben Ratslotse (Hafenblau/Signal).
Neun Parteifarben plus Marke plus Ampel ist sonst ein Jahrmarkt.

**E6 — Die Ampel ist eine eigene Skala und nie Dekoration.** Zustimmung / teils / Ablehnung /
keine Aussage bekommen **je eine eigene Glyphe** zusätzlich zur Farbe. Ohne das ist die
gesamte Positionsdarstellung für farbfehlsichtige Leser:innen wertlos — und das ist bei einer
Positionsmatrix nicht ein Detail, sondern der ganze Inhalt.

**E7 — Keine aggregierte Ampel-Bilanz je Partei.** Sieben Thesen (K4, B3, C1, F3, I2, W4, O4)
sind bewusst umgedreht formuliert: Zustimmung zeigt dort in die entgegengesetzte Richtung wie
bei ihren Nachbarthesen. Dieselbe Partei steht bei K1 auf Grün und bei K4 auf Rot — beides
korrekt. Ein „7× dafür, 3× dagegen"-Streifen oder ein Zustimmungsbalken je Liste wäre
**inhaltlich falsch**. Die Glyphe ist nur zusammen mit dem Thesentext lesbar.

**E8 — Die Belege heißen „Beleg", nicht „Zitat".** Rund ein Sechstel der Belege ist grammatisch
an den Satzbau angepasst oder zieht zwei Fundstellen zusammen (Prüfung: kein einziger ist
erfunden, aber auch nicht durchweg wörtlich). Anführungszeichen und das Wort „Zitat" würden
eine Wörtlichkeit versprechen, die wir nicht einlösen — „Beleg" oder „Fundstelle" ist ehrlich
und genauso stark.

---

## 4. Informationsarchitektur

Fünf Routen, 24 statisch vorgerenderte Seiten, alle **öffentlich ohne Konto**.

```
/kommunalwahl                    Überblick / Einstieg
/kommunalwahl/thema/[thema]      12 Seiten — ein Themenfeld quer über alle Listen
/kommunalwahl/liste/[liste]      9 Seiten — ein Programm im Profil
/kommunalwahl/naehe              Ähnlichkeit aller Paare
/kommunalwahl/methodik           Rechenweg, Grenzen, Quellenverzeichnis
```

### 4.1 `/kommunalwahl` — Überblick

Die Seite, die geteilt wird. Sie muss allein stehen können.

1. **Kopf** — „Ratswahl Oldenburg · 13. September 2026", Tage-bis-zur-Wahl, Kennzahlenband
   aus `fakten.wahl`: 52 Sitze · 383 Kandidierende · 16 Wahlvorschläge · 3 Stimmen · ab 16.
2. **„Du hast drei Stimmen"** — ein Lotti-Kasten, der Kumulieren und Panaschieren in zwei
   Sätzen erklärt (`fakten.wahl.wahlrecht.hinweis` als Rohstoff, nicht als Text). Das ist der
   Ratslotse-Beitrag, den kein anderes Angebot in Oldenburg leistet.
3. **Datenlage** — der Satz aus E2 plus ein Balken „8 von 16 Listen mit Programm". Aufklappbar:
   die sieben Karten der nicht verglichenen Listen.
4. **„Darüber streiten sie"** — 5 Karten aus `thesen_stat`, gefiltert `n ≥ 5`, nach `streit`
   absteigend. Je Karte: These in Alltagssprache, ein Verteilungsbalken dafür/teils/dagegen,
   die Listen-Chips in den drei Lagern. Aufklappbar → Belegzitate.
5. **„Darüber sind sie sich einig"** — 3 Karten, dieselbe Mechanik, `n ≥ 6` nach `streit`
   aufsteigend. Bewusst gleich prominent: Wahlberichterstattung zeigt nur Konflikt.
6. **12 Themenfelder** als Kacheln → `/kommunalwahl/thema/…`, sortiert nach `themen_rang`
   (⚠️ neu zu berechnen, §7.2), mit „x von 9 Listen äußern sich".
7. **9 Listen** als Kacheln → `/kommunalwahl/liste/…`, mit Farbe, Kurzname, Kandidatenzahl,
   Programmumfang, Ein-Satz-Charakterisierung (⚠️ zu erzeugen, §7.3).
8. **„Wer steht wem nahe?"** — Teaser: die drei ähnlichsten und die drei fernsten Paare →
   `/kommunalwahl/naehe`.
9. **Fuß** — Stand des Bestands, Link Methodik, Hinweis „Programme, nicht Politik".

### 4.2 `/kommunalwahl/thema/[thema]` — ein Themenfeld

Für jemanden, der eine Frage hat („Was passiert mit dem Wohnraum?"). 12 Seiten.

1. **Kopf** — Themenname (`themen[key].label`), Ein-Absatz-Einführung (⚠️ zu erzeugen, §7.3),
   „x von 9 Listen mit eigenem Kapitel".
2. **Die Streitfragen** — die 3–5 Thesen dieses Feldes als **Positionsmatrix**: Zeile = These,
   Spalte = Liste, Zelle = Ampelglyphe. Zelle antippen → Sheet mit dem vollen Belegzitat,
   Seitenzahl und Link ins Programm. Auf schmalen Screens kippt die Matrix in Listenform
   (These als Überschrift, drei Lager als Chip-Reihen).
3. **Was die Listen konkret fordern** — je Liste ein aufklappbarer Block mit
   `digests[slug].themen[feld].positionen` (die 3–11 Forderungs-Bullets), dem Prägnanzpunkt
   (0–3) und den Seitenzahlen als Sprungziele ins Original. **Das ist inhaltlich das Wertvollste
   im ganzen Bestand** und darf nicht unter der Matrix verschwinden.
4. **Weiter** — Nachbarthemen, zurück zum Überblick.

### 4.3 `/kommunalwahl/liste/[liste]` — ein Programm im Profil

9 Seiten, alle identisch aufgebaut (E4).

1. **Kopf** — Kurzname + amtliche Bezeichnung, Farbmarke, Typ (Partei / Wählergruppe),
   Kandidatenzahl, Wahlbereiche. Bei BSW die Landesprogramm-Markierung (E1).
2. **Die Quelle** — prominent, nicht im Fuß: Programmtitel, Format, Seitenzahl, Beschlussstand,
   **Knopf „Programm öffnen"** → Original-URL, daneben „Archivierte Fassung (Stand 07.08.2026)"
   → §5.4. Auffälligkeiten aus `programm.hinweis` (z. B. das Grünen-Deckblatt, das
   versehentlich „2021" trägt) gehören sichtbar hierher.
3. **Wofür dieses Programm steht** — `charakter`, gesetzt als Fließtext.
4. **Die sieben Kernpunkte** — `kernpunkte`.
5. **„Fällt auf"** — `besonderes`. Eigene Optik, das ist der Teil mit Wiedererkennungswert.
6. **Positionen nach Themenfeld** — 12 Blöcke aus `digests[slug].themen`, mit Prägnanzpunkt,
   Bullets und Seiten-Sprungzielen. Themenfelder mit `praegnanz: 0` werden als „keine Aussage"
   ausgewiesen, nicht weggelassen.
7. **Steht am nächsten bei / am weitesten weg von** — je 3 Listen aus `paare`, mit Prozent und n.
8. **Alle 44 Thesen** — kompakte Liste, Ampelglyphe + These + Belegzitat aufklappbar.

### 4.4 `/kommunalwahl/naehe` — Ähnlichkeit

1. **Erklärung zuerst**, dann Zahlen. Zwei Sätze: wie gerechnet wird, was `n` bedeutet, und
   der Satz „Ein hoher Wert heißt: zu den Thesen, zu denen sich **beide** äußern, stimmen sie
   oft überein — nicht, dass die Programme gleich sind."
2. **Matrix 9 × 9** — Zelle = Prozent + Ampel, `n` immer daneben oder im Tooltip. Eigener
   horizontaler Scroll-Container, der Body scrollt nie quer. Auf Mobil: Liste statt Raster,
   nach Wert sortierbar.
3. **Paar-Detail** (Sheet oder eigene Ankersektion) — Gesamtwert, `n`, und die Thesen, die den
   Wert treiben: **volle Übereinstimmung** und **klarer Dissens** je als namentliche Liste,
   beides mit Beleg. Dazu die dritte Gruppe: Thesen, zu denen sich **beide nur unbestimmt**
   äußern — die zählen in der Formel als volle Übereinstimmung und heben den Wert um bis zu
   14 Punkte (§7.6).
   ⚠️ **Keine 12 Themen-Ampeln je Paar.** 199 der 432 Zellen wären nicht belastbar: 81 haben
   gar keinen gemeinsamen Vergleichspunkt, 118 genau einen. Eine „Wohnen: 0 %"-Ampel auf einer
   einzigen These ist Rauschen mit Prozentzeichen.
4. **Grenzen** — direkt darunter, nicht auf einer anderen Seite: Programmumfang verzerrt
   (Auskunftsdichte reicht von 19 bis 34 der 44 Thesen, `n` je Paar von 12 bis 29),
   Thesenauswahl ist eine Entscheidung, Schweigen ist keine Position.

### 4.5 `/kommunalwahl/methodik` — Rechenweg und Quellen

Die Vertrauensseite. Rechenweg mit Formel, die vier Einschränkungen aus `README.md`,
Thesenkatalog vollständig (44 Thesen mit Themenzuordnung und `hinweis`), und das
**Quellenverzeichnis**: je Liste URL, Abrufdatum, Format, Größe, SHA256 aus
`quellen/manifest.json` — mit dem Einzeiler zum Nachprüfen.

---

## 5. Technische Anbindung

### 5.1 Die Daten kommen zur Bauzeit, nicht über eine API

`data.json` ist unveränderlich zwischen zwei Deploys. Es gibt nichts zu servieren.
**Vorbild ist `app/changelog/page.tsx`**, das `CHANGELOG.md` aus dem Repo-Wurzelverzeichnis
zur Bauzeit liest. Kein Backend-Endpunkt, keine Tabelle, kein Cache, keine Rate-Limits,
keine CORS-Frage, kein Ladezustand.

Neu: `web/frontend/lib/kommunalwahl.ts`

- `import "server-only"` obenan — die Datei darf nie versehentlich in einen Client-Bundle geraten.
- liest `../../kommunalwahl/data.json` einmal, memoisiert
- exportiert **enge, typisierte Schnitte** statt des ganzen Baums:
  `vergleichsListen()`, `nichtVerglichen()`, `themenfeld(key)`, `profil(slug)`, `paar(a,b)`,
  `streitThesen(minN)`, `einigkeitThesen(minN)`, `quelle(slug)`
- Typen nach `web/frontend/lib/kommunalwahl-types.ts` (nicht in `lib/types.ts` — das ist die
  API-Vertragsdatei und hat mit diesem Bestand nichts zu tun)

### 5.2 Server-Komponenten schneiden, Client-Komponenten kriegen nur ihre Scheibe

Die Seiten sind **Server Components**. Nur das wirklich Interaktive ist `"use client"`:
Positionsmatrix, Paar-Detail-Sheet, die Aufklapper. Diese bekommen exakt die Daten als Props,
die sie brauchen — was ein Client-Component sieht, landet im RSC-Payload und damit im
Download. `digests` allein sind 188 KB roh; die dürfen nie als Ganzes über die Grenze.

Richtwert: Die 9-Listen-Teilmenge ist 257 KB roh / 75 KB gzip. Über 24 Seiten verteilt und
serverseitig geschnitten bleibt jede Seite deutlich darunter.

### 5.3 Routen als echte Pfadsegmente — bewusst anders als der `(app)`-Bereich

`lib/routes.ts` erklärt, warum die Ratsinfo-Seiten Query-Parameter statt Pfadsegmente nutzen:
Die IDs kommen aus der API und lassen sich zur Bauzeit nicht aufzählen, also würde ein
dynamisches Segment den statischen Export (`MOBILE=1`) sprengen.

**Hier gilt das nicht.** Die Mengen sind fix und zur Bauzeit bekannt: 12 Themenfelder,
9 Listen. `generateStaticParams()` zählt sie auf, Next rendert 24 Seiten vor, der Export
läuft durch. Dafür gibt es lesbare, teilbare URLs (`/kommunalwahl/thema/wohnen`) und jede
Seite trägt nur ihre eigenen Daten.

⚠️ Was weiterhin gilt: **`searchParams` nicht anfassen.** Jeder Zugriff darauf macht die Route
dynamisch und bricht den Export. Filter- und Auswahlzustände gehören in Client-State, nicht
in die Adresszeile (oder per `history.replaceState` nach dem Mount, ohne `useSearchParams`).

### 5.4 Die archivierten PDFs — nicht nach `public/`

42 MB PDFs (AfD 19 MB, BSW 17 MB — beide bildlastig gescannt). In `web/frontend/public/`
würden sie in den statischen Export wandern und damit **in das iOS- und Android-App-Bundle**.
Das ist keine Option.

Stattdessen ein einziger neuer Backend-Endpunkt:

```
GET /api/kommunalwahl/programm/{slug}.pdf   →  FileResponse aus kommunalwahl/programme/
```

- neue Datei `web/backend/app/routers/kommunalwahl.py`, ~30 Zeilen, in `main.py` eingehängt
- **Slug gegen eine Whitelist** aus `quellen/manifest.json` prüfen, nie gegen das Dateisystem —
  sonst ist es ein Pfad-Traversal-Loch
- öffentlich, kein Login (die Seite ist es auch)
- `Content-Disposition: inline`, langes `Cache-Control` (die Dateien ändern sich nie)

Der Deploy-`rsync` hat keinen Ausschluss für `kommunalwahl/` — die Dateien landen also
ohnehin schon auf dem Server. Einmalig 42 MB Erstübertragung, danach inkrementell nichts.

### 5.5 Hülle, Navigation, Auffindbarkeit

- Die Seiten liegen **außerhalb** von `app/(app)/`, also unter `app/kommunalwahl/` — damit
  greift der Auth-Gate in `app/(app)/layout.tsx` gar nicht erst. `lib/public-routes.ts` muss
  nicht angefasst werden. Präzedenz: `/changelog`, `/impressum`.
- Eigenes `app/kommunalwahl/layout.tsx` auf Basis von `PublicShell` — Marke, Rücksprung,
  am Ende die Einladung ins Konto. Angemeldete Nutzer:innen sollen aber nicht ihre Navigation
  verlieren: eine schmale Rückleiste „← Zurück zu Ratslotse" reicht.
- **Einstiege:** Sidebar-Punkt (`components/nav.tsx`, befristet bis 13.09.), Karte auf dem
  Dashboard, Eintrag in der Command-Palette, Banner auf `app/page.tsx` (Landing).
- `app/sitemap.ts`: alle 24 URLs ergänzen (statisch aufzählbar).
- `app/robots.ts`: `/kommunalwahl` ist erlaubt — nichts zu tun, aber prüfen, dass kein
  bestehendes `disallow` greift.
- `generateMetadata` je Route, statisch (kein `searchParams`!). Ein eigenes
  `opengraph-image.png` für den Bereich — der Link wird geteilt werden.

### 5.6 Nach der Wahl

Am 14.09. ist der Vergleich ein Archiv. Ein zur Bauzeit ausgewerteter Datumsvergleich setzt
einen Kopfstreifen: „Die Wahl ist vorbei. Diese Seite dokumentiert den Stand vor dem
13.09.2026." Sidebar-Punkt und Landing-Banner verschwinden dann. Das kostet jetzt zehn Zeilen
und erspart später eine Panik-Änderung.

---

## 6. Bauteile

Katalog für die Design-Session. Namen sind Vorschläge.

| Bauteil | Aufgabe | Datenherkunft | Zustände, die es können muss |
|---|---|---|---|
| `ListenChip` | Liste als Marke: Farbpunkt + Kurzname | `meta[slug]`, `fakten.wahlvorschlaege` | mit/ohne Link, aktiv, BSW-Markierung |
| `PositionsGlyph` | eine Position als Ampel **+ Glyphe** | `positionen[..].pos` | dafür / teils / dagegen / keine Aussage |
| `ThesenKarte` | eine These mit Lagerverteilung | `thesen_stat[i]`, `positionen` | zu, aufgeklappt mit Belegen; „zu dünn" (n<5) |
| `PositionsMatrix` | Thesen × Listen | `thesen`, `positionen` | breit (Raster) / schmal (Listen), Zelle → Sheet |
| `Beleg` | Fundstelle + Seite + Link ins Original (**nicht** „Zitat", s. E8) | `positionen[..]`, `quellen[slug]` | mit Seitenlink / ohne (CDU) / Archivlink |
| `QuellenKarte` | Programm-Steckbrief | `digests[slug].programm`, `quellen[slug]` | PDF / Web; mit/ohne Beschlussstand; Hinweis |
| `ThemenBlock` | Forderungen einer Liste zu einem Feld | `digests[slug].themen[feld]` | Prägnanz 0–3; leer = „keine Aussage" |
| `AehnlichkeitsMatrix` | 9 × 9 Paarwerte | `paare` | Raster / Mobilliste, Zelle → Detail |
| `PaarDetail` | ein Paar aufgeschlüsselt | `paare[a\|b]`, `positionen` | Themen-Ampeln, Einigkeit, Dissens |
| `DatenlageBanner` | 8 von 16, mit Erklärung | `quellenart` | zu / aufgeklappt |
| `OhneProgrammKarte` | eine nicht verglichene Liste | `digests[slug]`, `quellenart` | `keins` / `kurz` — verschiedene Texte |
| `WahlFakten` | Kennzahlenband | `fakten.wahl` | — |
| `DreiStimmenErklaerer` | Lotti erklärt das Wahlrecht | `fakten.wahl.wahlrecht` | — |
| `StandHinweis` | Stand + Vor/Nach-Wahl-Zustand | `thesen.stand`, Bauzeit-Datum | vor / nach dem 13.09. |

---

## 7. Vorarbeiten an den Daten

Fünf Punkte. **7.1 und 7.2 sind Korrekturen** und müssen vor dem Frontend passieren;
**7.3 ist der Unterschied zwischen „Datensatz angezeigt" und „Ratslotse".**

### 7.1 `streit` braucht eine n-Schranke ⚠️

Ungefiltert steht B3 (n = 2) an der Spitze der Streitliste. Jede Anzeige, die nach `streit`
sortiert, filtert vorher `n ≥ 5`. Am besten in `analyse.py` gleich ein Feld `belastbar: bool`
mitschreiben, statt die Regel in jeder Komponente zu wiederholen.

### 7.2 `themen_rang` **und `thesen_stat`** zählen die falsche Menge ⚠️

`themen_rang.erwaehnt: 12` heißt „12 von 16 Listen" — gezählt über alle Digests, auch über die,
die gar kein Programm haben. Dasselbe gilt für **`thesen_stat`**: M5 steht dort mit `n = 10`,
obwohl nur 9 Listen verglichen werden. Damit sind `n`, `dafuer`, `teils`, `dagegen` und
`streit` durchgehend über die falsche Grundmenge gerechnet — und genau diese Zahlen tragen die
Blöcke „Darüber streiten sie" und „Darüber sind sie sich einig". `analyse.py` anpassen,
`data.json` neu erzeugen.

### 7.2b Sieben Einstufungen korrigieren ⚠️

Die inhaltliche Prüfung hat sieben Positionen gefunden, die nicht tragen — Einzelbelege in
[`pruefbericht.md`](pruefbericht.md) §2. Der folgenreichste: **Grüne und Bürger Bündnis
vertreten zur Stadionfinanzierung praktisch dieselbe Position** (anteilig, gedeckelt, mit
verbindlicher privater Beteiligung), stehen aber auf `−1` und `+1` — den beiden Extremen. C1
ist zugleich einer der fünf Top-Streitpunkte und stünde damit falsch auf der Startseite.

| | Änderung |
|---|---|
| C1 Grüne | `−1 → 0` |
| W3 BSW | `+1 → 0` (gleiche Substanz wie SPD, die 0 hat) |
| M3 Volt | `−1 → null` (Beleg spricht über Stellplätze, nicht über Gebühren) |
| I4 CDU | `−1 → null` (Schluss, den der Text nicht hergibt) |
| P2 SPD | `+1 → 0` (nennt keines der drei geforderten Rechte) |
| C3 SPD | `+1 → 0` (Grenzfall: Rückschau + „bei Bedarf") |
| B1/W3 BSW | angleichen (gleiche „alle Kommunen"-Bauform, verschieden bewertet) |

Dazu: BB-OL M4 und P2 brauchen die fehlende Seitenzahl 11, und im SPD-`besonderes` gehört
„erstmals seit über 30 Jahren" gestrichen (steht nicht im Programm).

**Nach diesen Änderungen ändern sich Paarwerte und Streitwerte** — `analyse.py` neu laufen
lassen, dann `pruef_struktur.py` (§10) erneut.

### 7.2c Zwei Thesen brauchen einen Hinweis, sonst führen sie in die Irre ⚠️

- **W1** („Oldenburg soll … eine zusätzliche städtische Wohnungsbaugesellschaft gründen") ist
  überholt: Der Stadtrat hat die Gründung **2025 beschlossen** — das BB-OL schreibt das
  wörtlich, die SPD reklamiert die Initiative für sich, die Grünen sprechen von „der neuen"
  Gesellschaft. Offen ist „ausbauen oder zurückdrehen", nicht „gründen oder nicht".
- **B2** (Kita-Gebühren): nur 2 von 9 Listen äußern sich, und die Gegenprobe zeigt, dass die
  anderen sieben wirklich schweigen — vermutlich, weil der Kindergartenbeitrag ab 3 Jahren in
  Niedersachsen landesrechtlich beitragsfrei ist. **Rechtslage prüfen und als Hinweis
  ergänzen**, sonst liest sich das Schweigen als Desinteresse.

### 7.3 Die Alltagssprache fehlt — der größte Posten

Der Bestand ist durchgängig in Programm- und Verwaltungssprache. Ratslotse übersetzt sonst
(„Lotti erklärt's einfach"). Vier Texttranchen, alle über `nwz/llm.py` mit einem Prompt in
`nwz/prompts.py` (damit sie im Admin live nachjustierbar sind):

| Was | Menge | Warum |
|---|---|---|
| „Worum geht's?" je These | **32** (12 der 44 haben schon einen `hinweis`) | Ein Satz: was diese These für Oldenburg konkret bedeutet |
| Einführung je Themenfeld | **12** | Ein Absatz Einstieg auf der Themenseite |
| Ein-Satz-Charakterisierung je Liste | **9** | `charakter` ist 60–100 Wörter — für Kacheln braucht es 12–15 |
| „Kein Programm"-Einzeiler | **7** | `programm.hinweis` sind 150–250 Wörter Rechercheprotokoll |

Ergebnis als eigene Datei `kommunalwahl/klartext.json`, von `analyse.py` in `data.json`
gemischt. **Redaktionell gegenlesen** — bei Wahlinhalten ist eine schiefe Paraphrase
schlimmer als gar keine.

### 7.4 Aktualität bis zum 13.09.

Der Bestand ist ein Schnappschuss vom 07.08.2026. Fünf Wochen bis zur Wahl — Programme können
nachgereicht oder geändert werden (Echt Oldenburg kündigt sein Programm sogar ausdrücklich
an). Nötig: ein sichtbarer Stand auf jeder Seite und ein dokumentierter Auffrischungs-Weg
(`analyse.py` neu laufen lassen → PR → Deploy). Ein Cron-Job lohnt für fünf Wochen nicht.

### 7.6 Beidseitiges „teils/teils" hebt die Ähnlichkeit ⚠️

Haben zwei Listen zur selben These beide `0`, zählt das als **volle Übereinstimmung**
(`1 − |0−0|/2 = 1`). Zwei Listen, die beide vage bleiben, gelten also als einig. Grüne–FDP
fällt von 38 % auf 23 %, wenn man diese Thesen herausnimmt; CDU–Volt von 50 auf 38.
11 % aller gewerteten Vergleiche sind solche Paarungen.

Das ist kein Fehler, sondern liegt in der Wahl-O-Mat-Formel — aber es gehört auf die
Methodikseite und als dritte Gruppe ins Paar-Detail (§4.4.3).

Gegenprobe zur Beruhigung: Lässt man jede einzelne These einmal weg, bewegt sich der Paarwert
im Median um 3,4 Punkte, maximal 6,4. **Kein Wert hängt an einer einzelnen These.**

### 7.5 Kleinkram

- `paare` und `abdeckung` enthalten alle 16 Listen — die Oberfläche filtert auf die 9.
- `thesen_stat` für `I3` hat `streit: null` — nur eine Liste (FDP) äußert sich, die These
  vergleicht also nichts. 43 der 44 Thesen tragen tatsächlich einen Vergleich; fünf weitere
  (B1, B2, B3, O2, D2, S2) beruhen auf zwei oder drei Positionen.
- Bürgerentscheid Baumschutz: `ja + nein = 37 242`, Beteiligung `37 295` — die Differenz sind
  **53 ungültige Stimmen**. Die Prozentwerte sind korrekt auf die gültigen Stimmen gerechnet,
  aber ohne diese Zeile gehen die Zahlen für Leser:innen nicht auf.
- Die Volltexte sind schmutzig extrahiert (Wörter mitten getrennt: `Aug|enhöhe`,
  `part eipolitisches`, `Kita - und`). Für seitengenaue Links reicht das; für Volltextsuche
  oder Textstellen-Anker auf der Seite taugen sie nicht.
- 42 MB Partei-PDFs liegen in einem öffentlichen Repo. Vertretbar als Belegarchiv, solange
  der primäre Link zum Original der Partei geht und die Kopien als Archiv gekennzeichnet sind.
  Kurze Belegzitate sind vom Zitatrecht gedeckt; das gilt nicht automatisch für eine
  Vollkopie. Falls das unangenehm wird: PDFs aus dem Repo nehmen, Manifest mit den Prüfsummen
  behalten — die Belegkette hängt an den Hashes, nicht an den Dateien.

---

## 8. Fallen

- **`searchParams` in einer Server-Komponente bricht den App-Build** (`MOBILE=1`). Siehe die
  Kommentare in `lib/share-metadata.ts` und `lib/public-routes.ts` — dieses Repo hat sich
  daran schon einmal die Finger verbrannt.
- **PDFs nie nach `public/`** — sonst wächst das App-Bundle um 42 MB (§5.4).
- **`data.json` nie an eine Client-Komponente durchreichen** — 353 KB im RSC-Payload (§5.2).
- **Sortierung nach `streit` ohne n-Filter** produziert Unsinn (§7.1).
- **Die Ampel braucht Glyphen**, nicht nur Farbe (E6).
- **Keine Zustimmungs-Bilanz je Partei** — sieben Thesen sind umgedreht formuliert, eine Summe
  daraus ist falsch (E7).
- **Keine Themen-Ampeln im Paar-Detail** — 46 % der Zellen sind nicht belastbar (§4.4.3).
- **Belege nicht als „Zitat" auszeichnen** (E8).
- **Kein Wahl-O-Mat-Look.** Der Lokal-O-Mat ist ein anderes Angebot, und die Seite darf nicht
  aussehen, als konkurriere sie damit (§1).
- **Breite Tabellen brauchen ihren eigenen `overflow-x: auto`.** Der Body scrollt nie quer.

---

## 9. Reihenfolge

| Stufe | Inhalt | Ergebnis |
|---|---|---|
| **0** | §7.1, §7.2, §7.2b, §7.2c in `analyse.py`/den Positionsdateien, `data.json` neu | Zahlen und Einstufungen stimmen |
| **1** | `lib/kommunalwahl.ts` + Typen + Route-Gerüst + `/kommunalwahl` | Überblick steht, teilbar |
| **2** | `/kommunalwahl/thema/[thema]` + `/liste/[liste]` | 21 Inhaltsseiten |
| **3** | `/kommunalwahl/naehe` + `/methodik` + Backend-PDF-Endpunkt | vollständig, belegt |
| **4** | §7.3 Klartext-Tranchen einmischen | Ratslotse-Ton |
| **5** | Einstiege (Nav, Dashboard, Landing, Sitemap, OG-Bild) | auffindbar |

CHANGELOG-Eintrag unter `## [Unreleased]` ist Pflicht (Repo-Regel), Doku-Seite in
`docs-site/` beschreibt Bestand und Methode.

## 10. Prüfliste vor dem Merge

- [ ] `pruefe.py`, `pruef_struktur.py` und `pruef_zitate.py` laufen grün und hängen in `tests/`
      — die drei haben die Prüfung von 2026-08-07 getragen (Struktur, alle 1 560 abgeleiteten
      Zahlen, jedes Belegzitat gegen den Programmtext) und sichern jede Datenauffrischung genauso ab
- [ ] Test friert die Vergleichsmenge ein: eine Datenauffrischung darf nicht still ändern,
      wer verglichen wird
- [ ] Die sieben Korrekturen aus §7.2b sind drin und `data.json` ist neu erzeugt
- [ ] `MOBILE=1 npm run build:mobile` läuft durch, Bundle-Zuwachs gemessen
- [ ] Backend im echten 3.12-venv: `import app.main` + pytest (stehende Repo-Regel)
- [ ] Jede angezeigte Position führt per Klick zur belegenden Stelle im Original
- [ ] Positionsmatrix ohne Farbwahrnehmung lesbar
- [ ] Alle 9 Listen: gleiche Bauteile, gleiche Reihenfolge, gleicher Platz
- [ ] Die sieben nicht verglichenen Listen sind auffindbar und erklärt
