# Plan: Stabilität & UX — Rundumschlag 10/2026

**Auftrag (Tim, 09.10.2026):** Nach den zwei Sicherheitsprüfungen eine
Stabilitäts- und UI/UX-Prüfung von allem, was Ratslotse heute kann — nirgends
zu lange laden, nirgends hängen bleiben, keine unklare UI, langweilige
Bildschirme lebendiger, schwer verständliche Navigation klarer. Plan schreiben
**und direkt umsetzen.**

**Wie geprüft wurde.** Stand `origin/dev` (= nächster Release), lokal mit dem
Prod-Abzug vom 01.10.2026 und allen Feature-Schaltern an (wie auf dev),
Frontend als Production-Build. Sechs parallele Prüfungen — zwei im Code
(Frontend-Stabilität, Backend-Latenz mit Messung jeder GET-Route), vier im
Browser mit Screenshots am Schreibtisch (1440 px), auf dem Telefon (375/320
px), auf dem Tablet und im Dunkelmodus, dazu Langsam- und Fehlersimulation per
`page.route`. Belegbilder liegen im Scratchpad der Sitzung; die IDs unten
(FS/BL/OE/RI/NV/HA) verweisen auf die Einzelberichte.

**Kein Befund ohne Messung.** Wo eine Zahl steht, ist sie gemessen; was nur
aus dem Code geschlossen ist, steht als „vermutet" da.

---

## 1. Was die Messung zeigt

### Stabilität — das Wichtigste zuerst

| # | Befund | Wirkung heute |
|---|---|---|
| FS-01 | Scheitert `/auth/me` beim Laden mit 5xx oder Netzfehler, schickt die App zur **Anmeldung** | trifft **jeden Deploy** (API-Neustart) |
| FS-05 | `useFetch` kennt keinen Fehler; Detailseiten machen aus 500/Funkloch „Diesen Beschluss finde ich nicht" | Sackgasse statt „Nochmal" |
| HA-01 | Haushalt: bei Backend-Fehler **dauerhaft** „… wird geladen …" auf allen Schritt-Seiten | ewiger Spinner |
| FS-02/03 | Karte und Tippspiel: Skelett für immer, wenn `/app-config` bzw. `/tipp/*` scheitert | ewiger Spinner |
| — | `lib/api.ts` ohne Zeitgrenze; Next bricht nach 30 s mit Klartext-„500" ab, im Funkloch gar nicht | 30–61 s Spinner, dann „Fehler 500" |
| FS-04/12 | Lotti: Abbruch vor dem ersten Wort → „Lotti schreibt …" für immer, übersteht sogar Neuladen; kein Stopp-Knopf | hängt |
| FS-09 | Recherche-Strom verbindet sich bei 401/403/404 alle 2 s neu, endlos | Dauer-Last, Fortschritt steht |
| FS-14 | kein `global-error.tsx`; `ChunkLoadError` nach Deploy → „Erneut versuchen" hilft nicht | weiße Seite / Sackgasse |
| BL-01 | **Schema-Migration bei jeder Anfrage** (736 SQL, 22–55 ms) — 20 gleichzeitige Anfragen 7,7 s statt 0,6 s | langsam unter Last |
| BL-02 | Jede angemeldete Anfrage schreibt mit Commit; bei Schreibsperre 5 s Wartezeit **je Anfrage**, Threadpool voll | bis 11 s |
| BL-03 | `async` Fehler-Handler schreibt synchron → Event-Loop 5,35 s blockiert | ganzer Dienst steht |
| BL-04 | `/goal/klima_2035`, `/goal/wohnungsbau` → 500 (`outcome` null nicht erlaubt) | kaputt |
| FS-17 | Drei Abrufe lesen alte deutsche Feldnamen → Personen-Marken leer, Verwaltung fehlt, Recherche-Kontingent nie sichtbar — **auch auf Prod** | still kaputt |

Einzeln ist das Backend schnell (Median aller GET-Routen 26,5 ms). Langsam
wird es durch **Parallelität**: Eine angemeldete Seite schickt 11–19 Anfragen
gleichzeitig, rund 10 davon allein aus dem Layout.

### Klarheit & Navigation

- **Dieselbe Seite heißt bis zu vier Namen** (NV-01): Heute = Start = Übersicht
  = Dashboard; „Themen" ist zugleich „Meine Themen" (Tab-Leiste) und ein
  Reiter der Ratsinfos (Orte/Projekte/Organisationen).
- **Zurück vom Beschluss landet in einer leeren Liste** (NV-02), aktiver
  Menüpunkt auf Detailseiten falsch (NV-03), Wahlen/Hilfe fallen aus der
  App-Hülle (NV-04).
- **Fehler sagen das Falsche**: „Die Verbindung ist abgebrochen" bei jedem
  Server-/Modellfehler (RI-04), Lotti-Fehler ohne Ausweg (RI-05), Haushalt
  „noch nicht eingelesen" statt Fehler (HA-02).
- **Nach der Wahl tun Seiten noch so, als stünde sie bevor** (OE-03/04/17): das
  Tippspiel lädt 26 Tage danach zum „Trotzdem tippen" ein (auf Prod stehen
  beide Runden auf `locked`), der Wahlvergleich zählt „0 Tage" herunter.
- Admin: „Sperren" wirkt **ohne Rückfrage** (HA-04).

### Handwerk & Lebendigkeit

- Sitzung am Telefon: TOP-Titel mit Ergebnis 32–64 px breit, ein Wort je
  Zeile (RI-01) — betrifft jede vergangene Sitzung.
- Haushalt springt beim Laden (CLS bis **1,09**, HA-03).
- `/changelog` ist 2,3 MB HTML, 172.000 px hoch (OE-01).
- „Heute" in der Sitzungspause: oben zwei leere Karten, „Zahl der Woche: 0"
  (NV-05/OE-15), obwohl die nächste Sitzung (26.10.) bekannt ist.
- Leere Flächen: Belege-Spalte auf /fragen, „Tagesordnung folgt" ×25,
  Merkliste, `/g` ohne Token (RI-15/16, NV-15, OE-16).

---

## 2. Pakete — in der Reihenfolge der Umsetzung

Jedes Paket ist ein eigener PR gegen `dev` (Fixes, die schon auf Prod wirken,
gegen `main`). UI-PRs gehen erst nach Tims Blick auf die Bilder in den Merge.

| # | Paket | Befunde | Stand |
|---|---|---|---|
| 0 | **Stille Feldnamen** (Prod-Fix) | FS-17 | #1669 → `main` |
| 1 | **Nie hängen bleiben** — Zeitgrenze + lesbare Fehler in `lib/api.ts`, `useFetch` mit `error`/`refetch`, `<AbrufFehler>`, Auth nur bei 401 abmelden, `global-error`, Chunk-Heilung, Listen/Karte/Tipp/Stichwahl, SSR-Zeitgrenzen | FS-01…08, 13, 14, 16, 20 | #1671 |
| 2 | **Backend unter Last** — Schema einmal je Prozess, Sitzungszähler ohne Warten, Fehler-Handler im Threadpool, Ziel-Seiten, Indizes, Parteien-Cache | BL-01…07 | #1670 **auf dev** |
| 3 | **Nach der Wahl** — Tippspiel endet von selbst, Countdown/Banner/Stichwahl/Verlauf, Kommunalwahl-Überlauf | OE-02, 03, 04, 17 | #1672 |
| 4 | **Navigation** — Namen vereinheitlichen, aktive Markierung, Zurück zur Sitzung, Palette vollständig, Mehr-Blatt gegliedert, Konto benannt, Abmelden-Ziel, Hilfe-Kopf | NV-01…04, 06…11, 13…15 | #1673 |
| 5 | **Ehrliche Fehler in Strömen** — Frag den Rat/Recherche/Lotti unterscheiden Netz/Server/Modell, Stopp für Lotti, „dauert länger"-Hinweis, Recherche-Backoff, `no-transform` | FS-04, 09–12, 25, RI-04, 05, 08 | #1675 |
| 6 | **Haushalt stabil** — `AbrufFehler` in allen Seiten/Sections, Fehler ≠ leer, formgleiche Skelette (CLS), `documents` einmal | HA-01…03, 06…09 | wartet auf #1671 (braucht `useFetch.error`) |
| 7 | **Telefon-Handwerk** — Sitzung mobil, RIS-Ergebnis-Anhang im Titel, Chip-Masken, `/tipp/admin` mobil | RI-01, 09, HA-05, 10 | #1676 |
| 8 | **Heute lebendig** — nächste Sitzung statt leerer Woche, Zahl der Woche ohne orange Null | NV-05, OE-15, RI-16 | #1677 |
| 9 | **Einstieg & Formulare** — Zurück im Einrichtungs-Assistenten, Tour übersteht Neuladen, Beispielantwort, Login-Wand erklärt sich, `/g` ohne Token | OE-05, 06, 08, 09, 10, 16 | #1679 |
| 10 | **Lange Seiten** — Changelog eindampfen (+ Fragmente wieder sichtbar), Thema/Ort/Beratende deckeln | OE-01, RI-10, 19 | #1678 |
| 11 | **Admin-Sicherheitsnetz** — Rückfrage vor Sperren/Rate-Limits, Emoji raus | HA-04, 13 | #1674 |

### Unterwegs gefunden (nicht im Prüfauftrag, aber behoben)

- **Changelog-Fragmente erschienen nie** auf ratslotse.de/changelog: Die Seite
  las `category:`, die Fragmente tragen `kategorie:` (#1678, mit Wächter).
- **Admin-Sperren ohne Rückfrage** wurde beim Prüfen tatsächlich ausgelöst
  (lokal, sofort zurückgenommen) — genau der Fall, gegen den #1674 baut.
- **Das Tippspiel steht auf Prod in beiden Runden noch auf `locked`** — ohne
  Endstand. #1672 setzt ihn künftig selbst; bis zum Release lässt er sich im
  Admin-Panel setzen.

## 3. Bewusst nicht in diesem Lauf

- **Tab-Leiste umbelegen** (NV-06: „Suche" statt „Themen"). Die Belegung ist
  eine frühere Entscheidung von Tim (Themen-Zähler als Rückkehr-Anlass). Die
  Prüfung hält „Suche nur über Mehr" für die größte mobile Hürde — **Tims
  Entscheidung**, nicht in den PRs.
- **Ein Bootstrap-Endpunkt fürs Layout** (BL-13, ~10 Anfragen je Seite in
  einer). Nach BL-01/02 ist der Druck deutlich kleiner; erst nachmessen.
- **Mehrere uvicorn-Worker / async SSE** (BL-10). Braucht vorher eine Klärung
  des Zustands im Speicher (Rate-Limiter, Recherche-Registry, Wahl-Caches).
- **Wahlabend-Sperre über Netzabrufe** (BL-09) — erst vor der nächsten Wahl.
- **Deploy in ein eigenes Verzeichnis** (FS-15, alte Chunks behalten) —
  vermutet, braucht Messung auf dem Server; Paket 1 fängt die Folge im Client.
- **Beschluss ↔ Sitzung ↔ Person verlinken, Tippfehler-Vorschläge,
  Belege-Spalte auf /fragen** (RI-06/07/15) — Gestaltungsarbeit, gehört in eine
  Design-Runde.

- **Kleinere P2-Befunde**, die keinem Paket zugeschlagen sind: Rate-Limit mit
  Wartezeit (OE-11), Wegwerf-Adresse mit Grund (OE-12, Sicherheitsentscheidung),
  Touch-Ziele unter 44 px an TOP-Knöpfen und Admin-Filtern (RI-11, HA-12),
  Lotti-Knopf verdeckt rechte Werte (RI-18, HA-07), Karten-Chips mobil
  (RI-12), Admin-Ortskandidaten zuklappen (HA-11), Quellen-Check-Pfad
  `quelle`↔`source` (BL-11), Themen-Limit je IP statt Konto.

## 4. Woran man merkt, dass es wirkt

- Eine Seite bleibt nie länger als 20 s im Ladezustand; danach steht ein Satz
  und ein „Nochmal" (Paket 1, Tests in `lib/api.test.ts`).
- Ein Deploy wirft niemanden mehr zur Anmeldung (Paket 1).
- 20 gleichzeitige Anfragen < 1 s lokal (Paket 2; vorher 7,7 s).
- Haushalt CLS < 0,1 auf allen Seiten (Paket 6).
- Keine Seite scrollt bei 320 px seitwärts (`14-layout.spec.ts`).
