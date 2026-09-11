# Umsetzungsplan: Tippspiel zur Ratswahl Oldenburg 2026

Stand: 11.09.2026 (Freitag), mittags. Die Wahl ist am **Sonntag, 13.09.2026,
8–18 Uhr**; die Auszählung beginnt um 18 Uhr. Alles hier muss bis Samstag
Abend auf Prod sein, damit am Sonntag getippt und ab 18 Uhr verglichen werden
kann. Der Plan ist wie [`plan-cities-phase5.md`](plan-cities-phase5.md)
geschrieben: **ohne das Gespräch dahinter ausführbar**. Jeder Abschnitt in §4
ist ein Pull Request mit Dateien, Signaturen, Tests, Zeitbedarf und
Fertig-Kriterium. Was gemessen ist, steht mit Zahl in §2 und mit Befehl in
Anhang C.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`web/backend/CLAUDE.md`, `web/frontend/CLAUDE.md`,
**`web/frontend/DESIGNSPRACHE.md`** (Farben, Bewegung, Anti-Patterns — die
Tafel steht und fällt damit), `tests/CLAUDE.md`, die Technik-Doku
`docs-site/src/content/docs/wahlabend.md` und die Modul-Docstrings von
`web/backend/app/election/service.py`, `votemanager.py`, `presentation.py`.
Das Tippspiel ist ein **Aufsatz auf den Wahlabend**: Es baut keinen zweiten
Abruf der Ratswahl und keine zweite Sitzverteilung, es liest
`service.live()` und legt Tipps daneben.

## 0. Was Tim vorgegeben hat

Am 11.09.2026:

> Tippspiel zur Kommunalwahl in Oldenburg: tippen, welche Parteien wie viele
> Plätze im Stadtrat bekommen; ein öffentlicher Endpunkt, wo man sich per
> QR-Code anmeldet, seinen Namen eingibt und dann einfach tippen kann;
> zusätzlich optional, wer von den OB-Kandidaten wie viel Prozent bekommt;
> eine schöne, übersichtliche Live-Seite, wo am Wahlabend die ausgezählten
> Stimmen gegen den Tipp verglichen werden; ein Scoreboard, wo alle
> aufgelistet sind — das Scoreboard ist das Herzstück, soll besonders cool
> aussehen, die ersten Plätze celebrieren, und man soll Rangwechsel mit
> Animationen gut sehen können.

> Bitte nutz unsere internen Daten, die durch die Kommunalwahlseite bereits
> erfasst werden — dann brauchen wir nur einen Scraper für den Votemanager.

> Check nochmal, ob unser Votemanager-Abruf robust ist; ich glaube nicht,
> dass die Open-Data-CSV live am Abend aktualisiert wird.

Daraus die Regeln dieses Plans:

1. **Kein zweites Register.** Listen, Kurznamen, Farben, Sitze 2021 und die
   OB-Kandidaten kommen aus `kommunalwahl/kandidaten.json`,
   `kommunalwahl/parteien-meta.json` und `kommunalwahl/wahl-fakten.json`
   (`ob_kandidaten`) — über `election.register.load()` bzw. eine neue,
   gleich gebaute Funktion für die OB-Kandidaten. Nichts wird abgetippt.
2. **Ein neuer Abruf, nicht zwei.** Die Ratswahl liefert `service.live()`
   fertig (Sitze je Liste, Hochrechnung, Phase). Neu ist nur der Abruf der
   **OB-Wahl** aus der Ergebnisdarstellung des Votemanagers (§2.3) — nach dem
   Muster von `presentation.py`.
3. **Ohne Konto.** Wer den QR-Code scannt, gibt einen Namen ein und tippt.
   Kein Registrieren, keine Adresse, kein Passwort. Die Identität ist ein
   Geheimnis im Browser (§3.1).
4. **Die Punkte rechnet der Server** — `logik-ins-backend`: Web zeigt, Server
   entscheidet. Die Formel steht in Anhang A und in `prediction/scoring.py`
   mit Tests, nirgendwo sonst.
5. **Der Abend darf an nichts sterben.** Dieselbe Regel wie in
   `service.py`: Die Tafel antwortet immer, notfalls mit dem letzten Stand
   und einem Vermerk. Ein 500er um 19 Uhr ist die einzige Antwort, die
   niemand gebrauchen kann.
6. **Web zuerst, iOS nicht.** Bis Sonntag gibt es keinen App-Store-Release
   mehr (Review dauert Tage). Der Vertrag wird so geschnitten, dass die App
   später nachziehen kann; gebaut wird sie in diesem Plan nicht.
7. **Nach `main`, nicht nach `dev`.** `dev` liegt sieben Commits vor `main`
   (Städtevergleich, Admin-Panel); die gehören nicht ungeplant auf Prod. Jeder
   PR dieses Plans zweigt von `origin/main` ab und geht mit `--base main` —
   wie #1150 (Wahlabend) am 06.09. Danach Rückmerge nach `dev`.
8. **Bild vor dem Merge.** Jeder UI-PR (2, 3, 4) schickt ein Bild an Tim
   (`SendUserFile`) und wartet sein Gegenlesen ab. Stehende Regel.
9. **Designsprache ist Gesetz, auch für die Feier.** Keine
   Parteifarben-Flächen (nur 8-px-Dots und 9-px-Tags), keine Emoji im
   UI-Text, Bewegung nur über `transform`/`opacity`, die vier Takte aus
   `globals.css`, `prefers-reduced-motion` respektiert. „Cool" heißt hier:
   Typografie, Podium, gleitende Zahlen, ein Konfetti-Regen aus
   `components/confetti.tsx` — nicht Neon.
10. **Feature-Schalter `tippspiel`**, nicht Umgebungs-Gate: Der Code fährt
    nach Prod, die Seite geht per `.env` an und nach dem amtlichen
    Endergebnis wieder aus — genau wie `wahlabend`.

## 1. Zielbild

```
  ┌────────────────────────────────┐ ┌────────────────────────────────┐
  │ A  MITMACHEN  /tippspiel       │ │ B  MEIN TIPP LIVE  /tippspiel  │
  │    ?spiel=CODE (aus dem QR)    │ │    ab So 18 Uhr: je Liste Tipp │
  │    Name → 16 Listen auf 52     │ │    · Stand · Punkte, OB-Zeile, │
  │    Sitze verteilen (Start:     │ │    mein Rang und die Bewegung  │
  │    Ergebnis 2021), optional    │ │    seit dem letzten Stand      │
  │    OB-Prozente; Autosave bis   │ │    (PR 2)                      │
  │    So 18:00 (PR 2)             │ │                                │
  └────────────────────────────────┘ └────────────────────────────────┘
  ┌────────────────────────────────┐ ┌────────────────────────────────┐
  │ C  TAFEL  /tippspiel/tafel     │ │ D  BETRIEB                     │
  │    Podium 1–3, Rangliste mit   │ │    Admin legt das Spiel an,    │
  │    gleitenden Zeilen (FLIP),   │ │    QR-Ecke zum Ausdrucken,     │
  │    ▲▼ seit letztem Stand,      │ │    Namen ausblenden/umbenennen │
  │    Punkte tween, Konfetti bei  │ │    Generalprobe ?probe=2021,   │
  │    Führungswechsel, TV-Modus   │ │    Runbook für Sonntag         │
  │    mit QR-Ecke vor 18 Uhr      │ │    (PR 4)                      │
  │    (PR 3)                      │ │                                │
  └────────────────────────────────┘ └────────────────────────────────┘
  ┌───────────────────────────────────────────────────────────────────┐
  │ 0  UNTERBAU: PR 0 macht den Votemanager-Abruf unabhängig davon,   │
  │    ob die Open-Data-CSV am Abend lebt (§2.4). PR 1 legt Schema,   │
  │    Punkte, OB-Abruf und Endpunkte.                                │
  └───────────────────────────────────────────────────────────────────┘
```

## 2. Was gemessen ist und den Plan trägt

Alle Zahlen vom 11.09.2026, Befehle in Anhang C.

### 2.1 Die internen Daten, die schon da sind

| Quelle | Inhalt | Wer liest sie heute |
|---|---|---|
| `kommunalwahl/kandidaten.json` | 16 Wahlvorschläge in Stimmzettel-Reihenfolge (`index` 1–16, `slug`, `short`, `official`, `kind`), 383 Kandidierende je Wahlbereich | `election/register.py::load()` → `Register.parties` |
| `kommunalwahl/parteien-meta.json` | `farbe` / `farbe_dunkel` / `kurz` je Slug | `register._colors()` → `ElectionParty.color` |
| `kommunalwahl/referenz-2021/*.csv` | Ergebnis 2021 (Sitze, Anteile) | `election/reference.py` → `seats_2021`, `share_2021_pct` |
| `kommunalwahl/wahl-fakten.json` → `ob_kandidaten` | **9 OB-Kandidat*innen** mit `name`, `beruf`, `jahrgang`, `vorgeschlagen_von` | noch niemand im Backend |
| `kommunalwahl/wahl-fakten.json` → `wahl` | `sitze: 52`, `termin`, `stichwahl_ob: 2026-09-27` | noch niemand im Backend |

Die Slugs der Listen: `gruene spd cdu linke fdp afd volt piraten bsw dava
stille partei pgm buergerbuendnis echt-oldenburg fuer-oldenburg`. Genau diese
16 Schlüssel trägt ein Sitz-Tipp; die Summe ist **52**.

Die OB-Kandidat*innen (Reihenfolge wie in der Datei): Jascha Rohr (Grüne),
Ulf Prange (SPD), Heike Boldt (Linke), Sebastian Fröhlich (FDP), Ralf Butzin
(Einzel), Yakup Castur (DAVA), Byanca Küßner (Einzel), Michael Stille
(Einzel), Holger Martin Wilkens (BB-OL). Sie haben keinen Slug — PR 1 leitet
ihn aus dem Nachnamen ab (`rohr prange boldt froehlich butzin castur kuessner
stille wilkens`); `test_prediction_mayor.py` hält fest, dass die neun Slugs
verschieden sind.

### 2.2 Was der Wahlabend heute liefert

`GET /api/wahlabend` (`ElectionNight` in `antworten.py`) trägt alles, was das
Tippspiel für die Ratswahl braucht:

- `phase`: `before` | `counting` | `complete`.
- `parties[]` mit `slug`, `short`, `name`, `color`, `color_dark`, `seats`
  (ausgezählter Stand), `projected_seats` (Hochrechnung, `None` ohne
  Bezirksdatei), `seats_2021`, `share_pct`.
- `progress.districts_counted` / `districts_total` (133), `computed_at`,
  `notes` (Menschentext der Rückfallstufen), `source.ok`.
- `?probe=2021&counted=N`: die Generalprobe — Zahlen von 2021 im Register von
  2026. **Damit lässt sich die Tafel vor Sonntag mit echten Bewegungen
  ansehen** (counted 0 → 40 → 90 → 133 nacheinander).

`service.live()` hält das Bild im Prozess, erneuert im Hintergrund, wirft
nie. Das Tippspiel ruft **diese Funktion**, nicht den Votemanager.

### 2.3 Die OB-Wahl beim Votemanager

Gemessen gegen `votemanager.kdo.de` (Anhang C.2):

- `20260913/03403000/daten/api/termin.json` nennt beide Wahlen samt
  Gebiets-Ids: OB-Wahl **`wahl.id 2552`**, Stadt-Gebiet
  **`ebene_-6360_id_10357`**; Ratswahl 913 / `ebene_-6361_id_10358`.
- Das Ergebnis-JSON liegt unter
  `daten/api/wahl_2552/ergebnis_ebene_-6360_id_10357_0.json` — **mit der
  vollen Gebiets-Id im Namen**, nicht nur der Zahl (`ergebnis_10357_0.json`
  ist 404). Heute trägt es nur `zeitstempel` und `seitentitel` (247 Bytes),
  keine `Komponente` — derselbe Vor-Auszählungs-Zustand wie bei der Ratswahl.
- **Eine Open-Data-CSV für die OB-Wahl gibt es nicht** — acht Namensmuster
  probiert (Anhang C.2), alle 404, auch für 2021; der Verzeichnis-Index ist
  403. Die Ratswahl-CSVs heißen `…-Stadtratswahl-{Stadt,Wahlbereiche,
  Wahlbezirk}.csv`; ein OB-Gegenstück ist nicht auffindbar. **Die OB-Wahl
  kommt also nur über die Ergebnisdarstellung** (das JSON, das die Website
  selbst lädt).
- Die Form ist an **2021** gemessen
  (`20210912/03403000/api/praesentation/wahl_223/ergebnis_ebene_3_id_513_0.json`,
  14 KB, `file_version 21.9.8`; 2026 meldet `26.08.03`):

  ```
  Komponente.tabelle.zeilen[]      je Kandidat*in: label.labelKurz „Krogmann, SPD",
                                   label.labelLang „Jürgen Krogmann, Sozial…",
                                   zahl „29.564", prozent „40,92 %", color
  Komponente.info.hinweis[]        „Alle Schnellmeldungen eingegangen!",
                                   „133 von 133 Ergebnissen"   ← Auszählungsstand
  Komponente.info.tabelle.zeilen[] Wahlberechtigte / Wählerinnen/Wähler /
                                   ungültige Stimmen / gültige Stimmen (zahl, prozent)
  Komponente.wahlbeteiligung.text.prozent   53.83
  Komponente.gewaehlte_kandidaten  title „Es findet eine Stichwahl statt zwischen",
                                   items[].label „Krogmann, Jürgen (SPD)"
  Komponente.grafik.balken[]       dieselben Zahlen als int (wert, prozentGerundet)
  ```

  `presentation.py` kann davon schon `_reports` (der „n von 133"-Satz),
  `_totals` (die Info-Tabelle) und `parse_number` („29.564" → 29564). Neu zu
  schreiben ist nur die Kandidaten-Zeile: `labelKurz` vor dem Komma ist der
  Nachname, dahinter die Partei; `zahl` und `prozent` als Text. Die 2021-Datei
  wird **Fixture** (`tests/fixtures/wahlabend/ob-2021.json`) und
  zugleich die Generalprobe der OB-Wahl.

### 2.4 Ist der Votemanager-Abruf robust? (Tims Frage)

Kurz: **Der Abruf stirbt an nichts, aber er vertraut der CSV mehr, als sie
verdient.** Gelesen in `votemanager.py` (Stand main, #1234 enthalten):

| Nr. | Befund | Zeile | Folge am Abend |
|---|---|---|---|
| a | Der Ersatzpfad (JSON) wird nur geholt, wenn die Wahlbereichs-CSV fehlt oder **ein Wahlbereich keine Personenstimmen** trägt (`_needs_presentation`). | `votemanager.py:265` | Solange die CSV leer bleibt, wird das JSON geholt — gut. Sobald sie einmal Personenstimmen für alle sechs Bereiche hat, nie wieder — auch wenn sie danach einfriert. |
| b | Eine JSON-Zeile ersetzt die CSV-Zeile nur, wenn sie **Personenstimmen** hat und die CSV keine (`_better`). | `votemanager.py:273` | Zählt die Stadt am Sonntag nur Listensummen (die Personenstimmen kommen nach 2021er Praxis eventuell erst Montag), trägt das JSON keine `sub_zeilen` → `_candidates` gibt `None` → **die JSON-Zeile wird verworfen, die leere CSV-Zeile bleibt.** Die Wahlbereiche blieben dann den ganzen Abend ohne Zahlen, obwohl die Website sie zeigt. |
| c | Ist die CSV **veraltet, aber nicht leer** (etwa ein einmaliger Export von 40 Bezirken mit Personenstimmen), gewinnt sie gegen ein JSON mit 120 Bezirken — `_better` vergleicht keinen Auszählungsstand. | `votemanager.py:273` | Die Seite zeigt den alten Stand und sagt es nicht. |
| d | Die **Stadtzeile** wird nur ersetzt, wenn die CSV-Stadt gar nicht `counted` ist. | `votemanager.py:409` | Gleiches Problem wie c auf Stadt-Ebene: Stimmenanteile und Sitze Stufe 1 hängen an ihr. |
| e | Die 133 **Bezirke** kommen nie aus dem JSON (bewusst, #1234). | `votemanager.py` Docstring | Ohne lebende Bezirks-CSV gibt es keine Hochrechnung — `projected_seats` bleibt `None`. Das ist dokumentiert und für das Tippspiel tragbar (§3.4). |

Was sich **nicht** messen lässt: ob die Open-Data-CSVs am Abend im
Minutentakt geschrieben werden. Dafür spricht, dass sie die Spalten
`max-schnellmeldungen`/`anz-schnellmeldungen` tragen (sinnlos für einen
Endstand) und `Cache-Control: max-age=60` senden; dagegen spricht Tims
Erfahrung. Der Plan macht die Frage **unerheblich**: PR 0 lässt die
Ergebnisdarstellung gewinnen, sobald sie weiter ist als die CSV — nach
Auszählungsstand, nicht nach Personenstimmen. Das JSON ist die Quelle der
Website der Stadt; wenn dort etwas steht, steht es auch bei uns.

### 2.5 Was im Frontend schon liegt

- `lib/use-tween.ts`: `useTween(zahl, ms)` (gleitende Zahl, 300 ms,
  reduced-motion-fest) und `useFrisch(wert, ms)` (kurzes Aufleuchten nach
  einem Anstieg). Beides für Punkte und Rangzahlen.
- `components/confetti.tsx`: `ConfettiBurst({onDone})`, Markenfarben,
  3,2 s, ohne Dependency. Für Führungswechsel und `complete`.
- `components/staffel.tsx` (`STAFFEL`, `staffelStil(i)`, gedeckelt bei
  sechs), `components/reveal.tsx`, `components/gleit-marker.tsx` (das
  Muster „eine Fläche fährt von Ziel zu Ziel", Messen per
  `getBoundingClientRect`).
- Takte und Kurven in `app/globals.css`: `duration-tipp/-fluss/-weg/-buehne`,
  `ease-out-strong`, `ease-in-out-strong`, `ease-back-out`.
- **Keine Animationsbibliothek** (kein framer-motion, kein auto-animate).
  Die Rangwechsel werden von Hand als FLIP gebaut (§4 PR 3) — 40 Zeilen,
  nur `transform`, wie es die Designsprache verlangt.
- `components/wahlabend/view.tsx` als Vorlage für Kopf, Fuß, Polling
  (`useQuery` mit `refetchInterval`), Countdown (`useWahlabendZeit` aus
  `components/wahlabend-hinweis.tsx`, MESZ-fest).
- Seiten außerhalb `app/(app)/` (`/wahlabend`, `/kommunalwahl`) haben keinen
  Konto-Kopf; Query-Parameter statt dynamischer Segmente (statischer
  Export). `/tippspiel?spiel=CODE`, nicht `/tippspiel/CODE`.
- `lib/api.ts`: `api.get(path)` nimmt **keine Header** entgegen. PR 2
  ergänzt einen optionalen zweiten Parameter `{ headers }` (die Funktion
  `request` spreadet `options.headers` bereits) — der Teilnehmer-Token geht
  als `X-Prediction-Token`, nie in die URL.

### 2.6 Was im Backend schon liegt

- `kern/features.py`: Registry mit `fertig_wenn`; `tests/test_features.py`
  verlangt je Schalter eine `useFeature("…")`-Stelle im Frontend.
- `app/ratelimit.py`: `RateLimiter(max_calls, window_seconds).check(request)`
  je IP. **Achtung Wahlparty:** 30 Leute im selben WLAN sind EINE Adresse.
  Die Bremsen des Tippspiels müssen das aushalten (§3.6).
- `tests/test_endpunkt_schutz.py`: jeder öffentliche Endpunkt steht mit
  Begründung in der Liste (Muster: `("get", "/api/wahlabend")`, Z. 113).
- `scripts/rauchprobe.py`: Proben sind handgepflegt (`PROBEN`), nur
  Endpunkte ohne Pfad-Parameter; die Tippspiel-Routen tragen einen Code und
  kommen deshalb **nicht** hinein — das gilt schon für `/api/wahlabend`.
- `kern/store.py`: `SCHEMA` (`CREATE TABLE IF NOT EXISTS`, läuft bei jedem
  Öffnen) + `_migrate()`; `USER_OWNED_TABLES` mit Wächter gegen jede
  Tabelle, die an einem Konto hängt. Die Tippspiel-Tabellen hängen an
  keinem Konto (§3.1) und tragen deshalb **keine** Spalte `owner_id` /
  `user_id`. `test_migration_bestand.py` migriert die Schema-Auszüge von
  dev und Prod mit zwei Zeilen je Tabelle — neue Tabellen aus `SCHEMA`
  brauchen keinen Migrationsschritt, neue Spalten an alten Tabellen schon
  (hier: keine).
- `data/ratslotse.sqlite` kommt **nie** auf ein Notebook
  (`scripts/lokale_daten.py` holt nur die Ratsdatenbank). Die Tippspiel-
  Tabellen liegen dort — Namen von Gästen bleiben auf dem Server.

## 3. Entscheidungen

### 3.1 Identität ohne Konto

Beitritt legt eine Zeile in `prediction_players` an und gibt dem Browser ein
**Geheimnis** (32 Hex-Zeichen aus `secrets.token_hex(16)`) zurück, das nur
als SHA-256 in der Datenbank steht (`token_hash`). Der Browser bewahrt es in
`localStorage["tippspiel.token.<code>"]` und schickt es als Header
`X-Prediction-Token`. Verliert jemand den Browser, ist der Tipp weg — dann
tritt die Person mit anderem Namen neu ein; der Admin blendet die Leiche aus
(§3.5). Kein Passwort-Reset, keine Mail. Das ist die Abwägung: ein Abend,
eine Party, keine Konten.

Namen sind je Spiel **eindeutig ohne Groß/Klein** (`UNIQUE(game_id, name
COLLATE NOCASE)`), 2–30 Zeichen, getrimmt, ohne Zeilenumbrüche. Ein
belegter Name gibt 409 mit dem Rat „nimm z. B. ‚Anna K.'". Kein
Wortfilter — die Runde ist Tims Umfeld; gegen den Ausreißer gibt es die
Moderation.

### 3.2 Spiel und Code

Ein **Spiel** hat einen sechsstelligen Code ohne verwechselbare Zeichen
(`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`), angelegt vom Admin. Der QR-Code trägt
`https://ratslotse.de/tippspiel?spiel=CODE`. Es kann mehrere Spiele geben
(Tims Wahlparty, eine zweite Runde im Büro) — die Kosten sind eine Spalte,
und ohne Code stünde jede Tafel mit Namen offen im Netz. Ohne `?spiel=` sagt
`/tippspiel`: „Du brauchst den Link aus dem QR-Code." Es gibt bewusst keinen
Einstieg von der Landing Page.

### 3.3 Sperre

Tipps lassen sich ändern bis **Sonntag 18:00 MESZ** — dieselbe Konstante
wie der Beginn des Wahlabends (`votemanager.ELECTION_NIGHT_START`, im
Frontend `useWahlabendZeit`). Der Server prüft die Uhrzeit, das Frontend
zeigt den Countdown. Beitritt nach 18 Uhr ist erlaubt (man kann zuschauen),
Tippen nicht: 409 „Die Tippabgabe ist seit 18 Uhr geschlossen." Ein Spiel
kann der Admin zusätzlich schließen (`closed_at`).

### 3.4 Wogegen live verglichen wird

- **Sitze:** in Phase `counting` gegen `projected_seats` (Hochrechnung),
  wenn vorhanden, sonst gegen `seats`; in `complete` gegen `seats`. Die
  Tafel nennt die Basis („Hochrechnung nach 61 von 133 Bezirken" /
  „ausgezählter Stand" / „Endergebnis"). Ohne lebende Bezirks-CSV (§2.4 e)
  gibt es keine Hochrechnung; dann läuft die Tafel auf `seats` — die springen
  stärker, das ist am Abend ehrlich und genau die Bewegung, die Tim sehen will.
- **OB:** gegen die Prozente aus dem OB-JSON, wie sie stehen (Teilstand).
- **Vor 18 Uhr** (Phase `before`) gibt es keine Punkte; die Tafel zeigt die
  Teilnehmer*innen alphabetisch mit „hat getippt / tippt noch", dazu die
  **Konsens-Zeile** je Liste (Median der Tipps) — das ist der Inhalt, den die
  Tafel vor der Auszählung tragen kann, und er macht neugierig.

### 3.5 Moderation und Löschung

Admin (Recht `admin`) kann je Teilnehmer*in **ausblenden** (`hidden_at`,
Tafel und Zähler lassen die Zeile weg, der Tipp bleibt) und **umbenennen**.
Ein*e Teilnehmer*in kann sich selbst löschen (`DELETE …/me`, Token). Nach dem
amtlichen Endergebnis: Schalter aus; die Tabellen bleiben als Rückblick bis
zum Jahresende, dann `DELETE` per Migration (Eintrag in `fertig_wenn`).

### 3.6 Bremsen

| Endpunkt | Bremse | Warum so weit |
|---|---|---|
| `POST …/players` | 60 je IP / 10 min | Wahlparty hinter einer Adresse; 500 Zeilen je Spiel als harte Kappe |
| `PUT …/me/tips` | 240 je IP / 10 min | Autosave beim Tippen, viele Geräte hinter einem NAT |
| `GET …/board`, `…/me` | keine eigene; Antworten kommen aus dem Prozess-Cache (60 s) | wie `/api/wahlabend` |

`DISABLE_RATE_LIMIT=1` gilt in Tests wie überall.

### 3.7 Was bewusst NICHT gebaut wird

- Kein iOS (Regel 6). Der Vertrag ist so geschnitten, dass die App später
  dieselben Endpunkte spricht.
- Keine Tipps je **Wahlbereich** oder auf Personen — 16 Zahlen und 9
  Prozente reichen für einen Abend; mehr tippt niemand am Handy.
- Keine Push-/Mail-Benachrichtigung — kein Konto, kein Kanal.
- Kein Wortfilter für Namen, keine Captchas.
- Keine Karte, kein Verlauf je Person über den Abend (die Standings-Tabelle
  legt ihn zwar ab — die Ansicht ist Kür nach dem Sonntag).

## 4. Die Pull Requests

Reihenfolge ist Abhängigkeit: 0 → 1 → 2 → 3 → 4. PR 0 ist unabhängig vom
Rest und sollte **als Erstes** gemergt werden — er nützt dem Wahlabend auch
ohne Tippspiel.

### PR 0 — Votemanager: die Ergebnisdarstellung gewinnt, wenn sie weiter ist

**Ziel:** Befunde b, c, d aus §2.4 schließen. Danach ist es egal, ob die
Open-Data-CSV am Abend lebt.

**Dateien:** `web/backend/app/election/votemanager.py`,
`tests/test_wahlabend_live.py`, `docs-site/src/content/docs/wahlabend.md`
(Absatz „Wenn die CSV nicht liefert").

**Änderungen:**

```python
def _needs_presentation(areas: list[AreaRow] | None) -> bool:
    """Das JSON lohnt, solange irgendein Wahlbereich in der CSV nicht fertig
    ausgezählt ist — nicht nur, solange Personenstimmen fehlen."""
    if not areas:
        return True
    return any(not _has_persons(r) or r.reports_received < r.reports_expected
               or r.reports_expected == 0 for r in areas)

def _better(csv_row: AreaRow | None, json_row: AreaRow) -> bool:
    """Die JSON-Zeile ersetzt die CSV-Zeile, wenn sie WEITER ist: mehr
    Schnellmeldungen, oder gleich viele mit Personenstimmen, die der CSV
    fehlen, oder überhaupt Zahlen, wo die CSV keine hat."""
    if csv_row is None or not csv_row.counted:
        return json_row.counted
    if json_row.reports_received > csv_row.reports_received:
        return True
    return (json_row.reports_received == csv_row.reports_received
            and _has_persons(json_row) and not _has_persons(csv_row))
```

`_merge_presentation` wendet dieselbe `_better`-Regel auf die **Stadtzeile**
an (statt „nur wenn CSV-Stadt nicht counted"). Der Hinweistext wird
allgemein: „…: Zahlen aus der Ergebnisdarstellung des Votemanagers — sie ist
weiter als die Open-Data-CSV." Kosten: bis zu acht kleine JSON-Abrufe je
Minute, solange nicht alles ausgezählt ist; beim Votemanager cachen sie
ohnehin 60 s.

**Tests** (der Fake-Server `Lage`/`Stoerung` in `test_wahlabend_live.py`
kann CSV und JSON getrennt legen):

- `test_json_ohne_personen_ersetzt_leere_csv`: CSV alle Bereiche leer, JSON
  mit Listensummen ohne `sub_zeilen` → `areas[*].parties[*].votes` gefüllt,
  `person_votes_available == False`, Hinweis in `notes`.
- `test_json_weiter_als_csv_gewinnt`: CSV 40/22 Meldungen mit Personen,
  JSON 22/22 → Anteile aus dem JSON.
- `test_csv_weiter_als_json_bleibt`: umgekehrt → CSV bleibt, kein Hinweis.
- `test_stadtzeile_folgt_derselben_regel`.
- Bestehende 89 Wahlabend-Tests bleiben grün (`-k wahlabend`).

**Zeit:** 1,5 h. **Fertig, wenn** die vier Tests grün sind und
`/wahlabend?probe=2021&counted=60` unverändert aussieht (die Probe läuft
ohne JSON).

### PR 1 — Backend: Schema, Punkte, OB-Abruf, Endpunkte

**Ziel:** Alles, was rechnet und speichert. Danach lässt sich mit `curl`
beitreten, tippen und die Tafel als JSON lesen.

**Dateien (neu):**

- `web/backend/app/prediction/__init__.py`
- `web/backend/app/prediction/scoring.py` — reine Funktionen (Anhang A)
- `web/backend/app/prediction/service.py` — Tafel und „meins" aus
  `election.service.live()/probe()`, `election.mayor`, Store
- `web/backend/app/election/mayor.py` — OB-Wahl aus der Ergebnisdarstellung
- `web/backend/app/routers/tippspiel.py` — öffentlicher Router + Admin-Router
- `tests/test_prediction_scoring.py`, `tests/test_prediction_api.py`,
  `tests/test_prediction_mayor.py`, `tests/fixtures/wahlabend/ob-2021.json`

**Dateien (geändert):** `kern/store.py` (SCHEMA + Methoden),
`kern/features.py` (Schalter `tippspiel`), `web/backend/app/antworten.py`
(Formen), `web/backend/app/schemas.py` (Eingaben), `web/backend/app/main.py`
(`include_router` ×2), `web/backend/app/ratelimit.py` (zwei Bremsen),
`web/backend/requirements.txt` + `constraints.txt` (`segno`, s. u.),
`tests/test_endpunkt_schutz.py` (Ausnahmen), `api/openapi.json` +
`web/frontend/lib/api-schema.ts` (neu geschnitten).

**Schema** (in `kern/store.py::SCHEMA`, englisch, kein `owner_id`):

```sql
CREATE TABLE IF NOT EXISTS prediction_games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,     -- 6 Zeichen, Alphabet ohne 0/O/1/I
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    closed_at   TEXT                      -- NULL = offen (Admin kann schließen)
);
CREATE TABLE IF NOT EXISTS prediction_players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL REFERENCES prediction_games(id),
    name        TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,     -- sha256(hex) des Browser-Geheimnisses
    created_at  TEXT NOT NULL,
    hidden_at   TEXT,                     -- Moderation: NULL = sichtbar
    UNIQUE (game_id, name COLLATE NOCASE)
);
CREATE TABLE IF NOT EXISTS prediction_tips (
    player_id   INTEGER PRIMARY KEY REFERENCES prediction_players(id),
    seats_json  TEXT NOT NULL,            -- {"gruene": 14, …} alle 16 Slugs, Summe 52
    mayor_json  TEXT,                     -- {"rohr": 31.5, …} oder NULL (nicht getippt)
    updated_at  TEXT NOT NULL
);
-- Ein Rang je Person je Stand des Abends: Grundlage von rank_before (▲▼)
CREATE TABLE IF NOT EXISTS prediction_standings (
    game_id     INTEGER NOT NULL,
    computed_at TEXT NOT NULL,            -- ElectionNight.computed_at
    player_id   INTEGER NOT NULL,
    rank        INTEGER NOT NULL,
    points      INTEGER NOT NULL,
    PRIMARY KEY (game_id, computed_at, player_id)
);
```

`prediction_games.created_at` statt einer `created_by`-Spalte: Das Spiel
gehört niemandem, das Anlegen ist eine Admin-Handlung und steht im Log.
(Sollte der Wächter `test_delete_web_user_covers_every_user_table` eine der
Tabellen für nutzerbezogen halten, ist das ein Fehlalarm über den Spaltennamen
— dann nicht die Tabelle in `USER_OWNED_TABLES`, sondern den Namen ändern.)

**Store-Methoden** (`kern/store.py`, Rückgaben als `dict`/`sqlite3.Row` wie
die Quiz-Methoden daneben):

```python
def prediction_game_create(self, code: str, title: str) -> dict
def prediction_game(self, code: str) -> dict | None
def prediction_games(self) -> list[dict]                          # Admin
def prediction_player_add(self, game_id: int, name: str, token_hash: str) -> dict   # sqlite3.IntegrityError → Router: 409
def prediction_player_by_token(self, game_id: int, token_hash: str) -> dict | None
def prediction_player_update(self, player_id: int, *, name: str | None = None, hidden: bool | None = None) -> None
def prediction_player_delete(self, player_id: int) -> None        # Tipp + Standings mit
def prediction_players(self, game_id: int, include_hidden: bool = False) -> list[dict]   # mit Tipp (LEFT JOIN)
def prediction_tip_set(self, player_id: int, seats: dict[str, int], mayor: dict[str, float] | None) -> None
def prediction_standings_record(self, game_id: int, computed_at: str, rows: list[tuple[int, int, int]]) -> None  # INSERT OR IGNORE
def prediction_standings_previous(self, game_id: int, before: str) -> dict[int, int]   # player_id → rank des letzten Stands VOR `before`
```

**OB-Abruf** (`election/mayor.py`, Muster `presentation.py`):

```python
@dataclass(frozen=True)
class MayorCandidate:
    slug: str; name: str; party: str; votes: int | None; share_pct: float | None

@dataclass(frozen=True)
class MayorResult:
    phase: str                     # before | counting | complete
    reports_expected: int; reports_received: int
    turnout_pct: float | None; valid_votes: int | None
    candidates: tuple[MayorCandidate, ...]
    runoff: tuple[str, ...]        # Slugs aus gewaehlte_kandidaten, leer ohne Stichwahl-Satz
    fetched_at: str | None; ok: bool; error: str | None

def candidates() -> tuple[MayorCandidate, ...]      # aus wahl-fakten.json, votes None; @lru_cache
def slug_of(name: str) -> str                        # „Sebastian Fröhlich" → „froehlich"; „Küßner" → „kuessner"
def parse(payload: object, known: tuple[MayorCandidate, ...]) -> MayorResult | None   # None ohne Komponente
def resolve_ids(session, base) -> tuple[int, str]    # aus termin.json: (2552, "ebene_-6360_id_10357"); Vorgabe bei Fehler
def fetch(force: bool = False) -> MayorResult        # TTL votemanager.ttl_seconds(), letzter guter Stand, wirft nie
def probe(counted: int | None) -> MayorResult        # ob-2021.json, Zeilen nach Position auf die 2026er Namen gelegt, Stimmen × counted/133
def reset() -> None
```

Zuordnung: `labelKurz` vor dem Komma → `slug_of(nachname)`; eine Zeile ohne
Treffer im Register wird als `notes`-Hinweis gemeldet und **mitgezählt**,
nicht verworfen (Muster „CSV-Spalten ohne Register-Eintrag zählen mit").
`phase`: `before` ohne `Komponente` oder `reports_received == 0`,
`complete` bei `received == expected > 0`, sonst `counting`. Der
Ratswahl-Router bekommt zusätzlich `GET /api/wahlabend/ob` (Form
`MayorNight`, hinter `wahlabend`) — die Wahlabend-Seite kann die OB-Zeile
später zeigen, das Tippspiel braucht sie heute.

**Antwortformen** (`antworten.py`, `TypedDict`, nullbar als `| None`):

```python
class PredictionParty(TypedDict):
    slug: str; short: str; name: str; color: str; color_dark: str; seats_2021: int | None
class PredictionMayorCandidate(TypedDict):
    slug: str; name: str; party: str
class PredictionGame(TypedDict):
    code: str; title: str; seats_total: int; deadline: str        # ISO, 2026-09-13T16:00:00+00:00
    locked: bool; closed: bool; player_count: int
    parties: list[PredictionParty]; mayor_candidates: list[PredictionMayorCandidate]
class PredictionJoin(TypedDict):
    player_id: int; name: str; token: str
class PredictionSeatLine(TypedDict):
    slug: str; tip: int; actual: int | None; points: int
class PredictionMayorLine(TypedDict):
    slug: str; tip: float; actual_pct: float | None; points: int
class PredictionScore(TypedDict):
    total: int; seat_points: int; mayor_points: int; bonus_points: int; deviation: int | None
class PredictionMine(TypedDict):
    player_id: int; name: str; locked: bool; has_tip: bool; has_mayor_tip: bool
    seats: list[PredictionSeatLine]; mayor: list[PredictionMayorLine]
    score: PredictionScore | None; rank: int | None; rank_before: int | None
    basis: str; phase: str; computed_at: str; notes: list[str]
class PredictionBoardRow(TypedDict):
    player_id: int; name: str; has_tip: bool; has_mayor_tip: bool
    score: PredictionScore | None; rank: int | None; rank_before: int | None
class PredictionConsensus(TypedDict):
    slug: str; median_tip: int | None; actual: int | None
class PredictionBoard(TypedDict):
    code: str; title: str; phase: str            # before | counting | complete
    basis: str                                   # none | seats | projected_seats
    districts_counted: int; districts_total: int
    mayor_phase: str; mayor_reports_received: int; mayor_reports_expected: int
    computed_at: str; deadline: str; locked: bool
    rows: list[PredictionBoardRow]               # sortiert nach Rang, dann Name
    consensus: list[PredictionConsensus]
    leader_player_id: int | None
    notes: list[str]
class MayorNight(TypedDict): …                   # MayorResult 1:1, candidates mit votes/share_pct
```

**Eingaben** (`schemas.py`, pydantic): `PredictionJoinIn(name: str,
min_length=2, max_length=30)` mit Validator (trim, kein `\n`);
`PredictionTipIn(seats: dict[str, int], mayor: dict[str, float] | None)` —
der Router prüft gegen das Register: genau die 16 Slugs, jeder 0–52, Summe
52; OB: nur bekannte Slugs, jeder 0–100 mit einer Nachkommastelle, Summe
zwischen 99,5 und 100,5, fehlende Slugs = 0; `mayor: null` = nicht getippt.
Fehler als 422 mit deutschem Satz (der Wrapper zeigt `detail`).

**Router** (`routers/tippspiel.py`; alle öffentlichen hinter
`features.an("tippspiel")` → 404 wie beim Wahlabend):

| Methode/Pfad | Schutz | Antwort |
|---|---|---|
| `GET /api/tippspiel/{code}` | offen | `PredictionGame` |
| `POST /api/tippspiel/{code}/players` | offen, Bremse | `PredictionJoin` (201); 409 Name belegt; 409 Spiel geschlossen; 409 „voll" ab 500 |
| `GET /api/tippspiel/{code}/me` | Header `X-Prediction-Token` (sonst 401) | `PredictionMine` |
| `PUT /api/tippspiel/{code}/me/tips` | Token, Bremse | `PredictionMine`; 409 nach 18 Uhr |
| `DELETE /api/tippspiel/{code}/me` | Token | `Ok` |
| `GET /api/tippspiel/{code}/board` | offen | `PredictionBoard` |
| `GET /api/tippspiel/{code}/qr.png` | offen | PNG 600×600, `Cache-Control: public, max-age=3600` |
| `GET /api/admin/tippspiel` | `require_admin` | `list[PredictionGame]` |
| `POST /api/admin/tippspiel` | `require_admin` | `PredictionGame` (Body `{title}`) |
| `PUT /api/admin/tippspiel/{code}` | `require_admin` | `PredictionGame` (Body `{closed: bool}`) |
| `PUT /api/admin/tippspiel/{code}/players/{player_id}` | `require_admin` | `Ok` (Body `{name?, hidden?}`) |

`GET …/me` und `…/board` nehmen `?probe=2021&counted=N` wie
`/api/wahlabend` (Generalprobe: Ratswahl `service.probe`, OB
`mayor.probe`). `qr.png` nutzt **`segno`** (reines Python, schreibt PNG ohne
Pillow; `segno.make(url, error="m").save(buf, kind="png", scale=12,
border=2)`) — eine Zeile in `web/backend/requirements.txt`, eine Fassung in
`constraints.txt` (aktuell 1.6.x), Ausnahme in `test_api_vertrag.py` wie
`bild.png`. Der PNG-Endpunkt ist Bequemlichkeit; der Link steht daneben.

**Tafel-Rechnung** (`prediction/service.py`):

```python
def board(code: str, *, probe: str | None, counted: int | None, store: Store) -> PredictionBoard
def mine(code: str, token: str, *, probe, counted, store) -> PredictionMine
def _basis(night: ElectionNight) -> tuple[str, dict[str, int | None]]   # none|seats|projected_seats → slug → Sitze
def _mayor_actual(result: MayorResult) -> dict[str, float | None]
```

`board()` liest `election.service.live()` (bzw. `probe`), `mayor.fetch()`,
alle sichtbaren Spieler*innen mit Tipp, rechnet je Person
`scoring.score(...)`, sortiert (Anhang A), schreibt die Ränge in
`prediction_standings` unter `night["computed_at"]` (nur wenn dieser Stand
noch nicht abgelegt ist — `INSERT OR IGNORE`) und holt `rank_before` aus
dem letzten anderen Stand. Vor 18 Uhr (`phase == "before"` **und** Uhrzeit
vor Deadline) ist `score None`, `rank None`, Reihenfolge alphabetisch.
Cache: das fertige Board 20 s je Code im Prozess (`threading.Lock`), damit
30 Handys und der Fernseher nicht 30-mal rechnen. Zwei Spiele gleichzeitig
sind zwei Einträge.

**Tests:**

- `test_prediction_scoring.py`: Anhang A Zeile für Zeile (exakt 10 / ±1 7 /
  ±2 4 / ±3 1 / ±4 0; OB 5/4/…/0; Bonus; Sortierung mit Gleichstand und
  Zeitstempel; `deviation`; `None`-Sitze → 0 Punkte, `basis none` → kein
  Score).
- `test_prediction_mayor.py`: `parse(ob-2021.json)` → 6 Kandidaten, Krogmann
  29.564 / 40,92, `reports 133/133`, `phase complete`, `runoff` zwei Slugs;
  Payload ohne `Komponente` → `None`; `slug_of` für alle neun 2026er Namen
  verschieden; unbekannter Nachname → Hinweis + mitgezählt.
- `test_prediction_api.py` (TestClient, `FEATURE_FLAGS=tippspiel`,
  `DISABLE_RATE_LIMIT=1`, `election.service` auf `probe(60)` gepatcht,
  `mayor.fetch` auf `probe(60)`): Beitritt → Token; doppelter Name 409;
  Tipp mit Summe 51 → 422; Tipp OK → `me.seats` 16 Zeilen; nach
  gepatchter Uhr 18:01 → 409; Board sortiert, `rank_before` nach zweitem
  Stand gesetzt; ausgeblendete Person fehlt im Board; Schalter aus → 404;
  ohne Token 401; Admin-Routen ohne Admin 403; `qr.png` ist ein PNG.
- `test_endpunkt_schutz.py`: die sieben offenen Routen mit Begründung
  („Tippspiel: ohne Konto, Identität ist der Token; hinter Schalter").
- `test_features.py` verlangt eine `useFeature("tippspiel")`-Stelle — die
  kommt in PR 2; **PR 1 legt den Schalter deshalb noch nicht in die
  Registry**, sondern PR 2 (sonst rot). Der Router prüft bis dahin
  `features.an("tippspiel")`, was ohne Registry-Eintrag „aus" ergibt — für
  die Tests wird `FEATURES` gepatcht.

**Zeit:** 5 h. **Fertig, wenn** `python scripts/pruefe.py --schnell` grün
ist (Vertrag geschnitten, Typen erzeugt), die drei Testdateien grün sind
und dieser Ablauf gegen `scripts/dev.py start` klappt:

```bash
B=http://127.0.0.1:8600   # Port aus dev.py; Admin-Cookie aus dem Login
curl -s -X POST $B/api/admin/tippspiel -H 'Content-Type: application/json' -b cookies -d '{"title":"Wahlparty"}'
curl -s -X POST $B/api/tippspiel/CODE/players -H 'Content-Type: application/json' -d '{"name":"Anna"}'
curl -s -X PUT  $B/api/tippspiel/CODE/me/tips -H "X-Prediction-Token: …" -H 'Content-Type: application/json' -d @tipp.json
curl -s "$B/api/tippspiel/CODE/board?probe=2021&counted=60" | python3 -m json.tool | head -40
```

### PR 2 — Frontend: Mitmachen und „Mein Tipp gegen den Stand"

**Ziel:** Vom QR-Scan zum abgegebenen Tipp in unter einer Minute am Handy;
ab 18 Uhr dieselbe Seite als persönlicher Live-Vergleich.

**Dateien (neu):** `web/frontend/app/tippspiel/layout.tsx` (wie
`app/wahlabend/layout.tsx`: außerhalb `(app)`, Metadata, `bg-background`),
`app/tippspiel/page.tsx` (Suspense + `<TippspielView />`),
`components/tippspiel/view.tsx` (Weiche: kein Code → Hinweis; kein Token →
Beitritt; Token → Formular oder Vergleich), `components/tippspiel/beitritt.tsx`,
`components/tippspiel/sitz-verteiler.tsx`, `components/tippspiel/ob-tipp.tsx`,
`components/tippspiel/mein-vergleich.tsx`, `lib/tippspiel.ts` +
`lib/tippspiel.test.ts`, `changelog.d/tippspiel.md` (`hinzugefuegt`).

**Dateien (geändert):** `lib/api.ts` (optionale Header), `kern/features.py`
(Schalter `tippspiel` mit `fertig_wenn`: „Das amtliche Endergebnis steht;
danach ist die Tafel ein Rückblick"), `tests/e2e/14-layout.spec.ts`
(`OFFEN` um `/tippspiel` erweitern — ohne Code zeigt die Seite den
Hinweis, das reicht der Layout-Probe).

**`lib/api.ts`:**

```ts
type Extra = { headers?: Record<string, string> };
get:  <T>(path: string, extra?: Extra) => request<T>(path, extra),
put:  <T>(path: string, body?: unknown, extra?: Extra) => request<T>(path, { method: "PUT", body: …, ...extra }),
del:  <T>(path: string, body?: unknown, extra?: Extra) => …
```

`request` spreadet `options.headers` schon (Z. 69); die drei Signaturen
bleiben für alle Aufrufer abwärtskompatibel.

**`lib/tippspiel.ts`** (reine Logik, mit Test):

```ts
export const TOKEN_KEY = (code: string) => `tippspiel.token.${code}`;
export function tokenLesen(code): string | null      // try/catch um localStorage
export function tokenMerken(code, token): void
export function startverteilung(parties: {slug; seats_2021: number|null}[], total = 52): Record<string, number>
  // Hare/Niemeyer über seats_2021 auf 52 — der Ausgangspunkt des Formulars; Listen ohne 2021er Sitz: 0
export function sitzeRest(tipp: Record<string, number>, total = 52): number
export function prozentRest(tipp: Record<string, number>): number     // 100 − Summe, eine Nachkommastelle
export function rangDelta(rank, rankBefore): { richtung: "auf" | "ab" | "gleich" | "neu"; um: number }
export function punkteText(n): string                                  // „12 Punkte", „1 Punkt"
export type Spiel = ApiAntwort<"/tippspiel/{code}">; export type Meins = …; export type Tafel = …
```

**Beitritt** (`beitritt.tsx`): Titel des Spiels, ein Feld „Wie heißt du?"
(`components/ui/input`), Knopf „Mitmachen". 409 → Fehlertext unter dem Feld,
Feld behält den Wert. Erfolg → Token merken, Formular. Vor der ersten Zeile
`DESIGNSPRACHE.md` §5 (Bausteine) lesen — Karte, Kicker, Primärknopf.

**Sitz-Verteiler** (`sitz-verteiler.tsx`): 16 Zeilen, je Zeile 8-px-Dot in
der Parteifarbe, Kurzname, 2021-Sitze klein („2021: 12"), Stepper −/+
(44-px-Ziele) und ein Zahlenfeld; oben eine **Rest-Leiste**: „Noch 3 Sitze zu
verteilen" / „2 Sitze zu viel" / „52 von 52 — passt", als Tint (Warnung gelb,
Erfolg grün, §2 Semantik). Speichern per Autosave (debounce 800 ms) **nur bei
Rest 0**; sonst Hinweis. Start: `startverteilung(...)`, sobald ein Tipp vom
Server kommt, der. `useTween` an der Summe. Reihenfolge = Stimmzettel
(Register-Index), nicht nach Größe.

**OB-Tipp** (`ob-tipp.tsx`): aufklappbar („OB-Wahl mittippen — bis zu 45
Bonuspunkte", `components/aufklapp.tsx`), 9 Zeilen mit Name, Partei als
9-px-Tag, Prozentfeld (Schritt 0,5), Rest-Leiste zu 100. „Nicht mittippen"
setzt `mayor: null`.

**Mein Vergleich** (`mein-vergleich.tsx`, ab `locked`): Kopf mit
Rang (groß, `font-display`, `useTween`), Punkte, ▲▼-Chip aus
`rangDelta`, Basis-Satz („Hochrechnung nach 61 von 133 Bezirken"); darunter
je Liste: Dot, Kurzname, Tipp → Stand, Punkte als Tint-Pille (10 grün, 7/4
neutral, 1/0 leise); OB-Block analog mit Prozent. Polling `refetchInterval:
60_000` nur bei `phase !== "before"` (Muster `wahlabend/view.tsx`), Countdown
davor. Ein Link „Zur Tafel" → `/tippspiel/tafel?spiel=CODE`. Fußzeile:
„Die Punkte rechnen wir; maßgeblich ist die amtliche Ergebnisdarstellung
der Stadt." (derselbe Vorbehalt wie unter der Wahlabend-Tafel).

**Tests:** `lib/tippspiel.test.ts` (Startverteilung summiert 52 und
reproduziert die 50 Sitze von 2021 proportional; Rest-Rechner; rangDelta
mit `null`); `npx tsc --noEmit`; `npx next lint`; Bild an Tim: Beitritt,
Formular mit Rest 0, Vergleich mit `?probe=2021&counted=60`.

**Zeit:** 4 h. **Fertig, wenn** ein fremdes Handy per QR-Link (dev) in
unter einer Minute einen gültigen Tipp abgibt und die Seite nach
`?probe=2021&counted=90` Punkte zeigt — und Tim das Bild abgenickt hat.

### PR 3 — Die Tafel

**Ziel:** Das Herzstück. Ein Fernseher im Wohnzimmer, 30 Namen, und man
sieht auf drei Meter, wer gerade vorn liegt und wer eben drei Plätze
gestiegen ist.

**Dateien (neu):** `app/tippspiel/tafel/page.tsx`,
`components/tippspiel/tafel.tsx` (Rahmen, Polling, Modus),
`components/tippspiel/podium.tsx`, `components/tippspiel/rangliste.tsx`,
`components/tippspiel/flip.ts` (der FLIP-Hook), `components/tippspiel/
konsens.tsx`, `components/tippspiel/qr-ecke.tsx`; `tests/e2e/16-tippspiel.spec.ts`
+ `tests/e2e/fixtures/tippspiel-board-*.json`; `14-layout.spec.ts` um
`/tippspiel/tafel`.

**Aufbau der Seite** (`/tippspiel/tafel?spiel=CODE`, optional `&tv=1`):

1. **Kopf**: Titel des Spiels, Phase als Kicker („Auszählung läuft ·
   Hochrechnung nach 61/133 Bezirken · Stand 19:42 Uhr"), vor 18 Uhr der
   Countdown. Im TV-Modus ohne Ratslotse-Kopf, `max-w-none`, Schriftgrößen
   über `clamp()`.
2. **Podium** (ab Phase `counting`): drei Karten, Mitte höher (Platz 1),
   links 2, rechts 3 — nur `transform: translateY` unterscheidet die Höhen.
   Große Rangziffer in `font-display`, Name, Punkte mit `useTween`, ▲▼-Chip.
   Flächen: Karte (`bg-card`) mit Primär-Tint für Platz 1 (`bg-primary/10`,
   Rahmen `primary/20` — keine Gold-Farbe, die es in der Designsprache nicht
   gibt). Wechselt `leader_player_id`, läuft einmal `ConfettiBurst` (nicht
   beim ersten Rendern, nicht öfter als alle 60 s). Bei `phase ===
   "complete"` noch einmal, und der Kicker sagt „Endergebnis".
3. **Rangliste**: alle weiteren Zeilen (`rangliste.tsx`), je Zeile Rang,
   Name, Punkte (tween), Aufschlüsselung klein (Sitze · OB · Bonus), ▲▼-Chip
   „+3" / „−1" mit `lucide-react` `ArrowUp`/`ArrowDown` (kein Emoji), Chip
   in Semantik-Tints (auf grün, ab neutral-grau; nichts Rotes — verlieren
   ist hier kein Fehler). Personen ohne Tipp am Ende, ausgegraut, „kein
   Tipp". Eine Zeile, die gerade gestiegen ist, leuchtet 1,6 s
   (`useFrisch` auf `−rank`).
4. **FLIP** (`flip.ts`): der Hook nimmt eine `Map<player_id,
   HTMLElement>`; `useLayoutEffect` misst vor dem Commit die alten `top`
   (aus dem letzten Render, in einem `useRef` gehalten), nach dem Commit die
   neuen; für jede Zeile mit Differenz `dy`: `style.transform =
   translateY(dy)`, `transition = none`, dann im nächsten Frame
   `transition = transform var(--takt-buehne) var(--ease-in-out-strong)`,
   `transform = ""`. Neue Zeilen kommen mit `fade-up`, gelöschte werden
   nicht animiert (sie sind einfach weg). `prefers-reduced-motion` → kein
   Transform. Nur `transform`, kein `top`/`height` — Designsprache §7.
5. **Konsens** (`konsens.tsx`, vor und während der Auszählung): eine
   Zeile je Liste: Dot, Kurzname, Median-Tipp → Stand, als schmale
   Balken-Paare in `bg-muted`/`bg-primary` (keine Parteifarben-Flächen,
   Dot reicht). Zeigt, wie die Runde tippt, und ist der Inhalt vor 18 Uhr.
6. **QR-Ecke** (`qr-ecke.tsx`): unten links, `qr.png` + Kurzlink
   `ratslotse.de/tippspiel?spiel=CODE`, „Mitmachen bis 18 Uhr". Ab `locked`
   verschwindet sie (opacity → 0).
7. **TV-Modus**: mehr als 12 Zeilen → Seiten, die alle 20 s wechseln
   (Podium bleibt stehen; nur die Liste blendet, `opacity` über
   `--takt-buehne`). `?tv=1` blendet Kopf und Fußleiste aus und setzt den
   Bildschirmschoner-Hinweis nicht — das macht der Fernseher.

**Polling:** `useQuery(["tippspiel","board",code,probe,counted], …,
{ refetchInterval: phase === "before" ? 60_000 : 30_000, placeholderData:
keepPreviousData })` — die alte Liste bleibt stehen, bis die neue da ist
(§7 „Was schon dasteht, bleibt beim Nachladen stehen").

**Tests:** `16-tippspiel.spec.ts` mockt `/api/app-config` (Schalter an) und
`/api/tippspiel/CODE/board` mit **drei** Fixtures nacheinander
(`before`, `counting` Stand A, `counting` Stand B mit vertauschten Rängen);
prüft: Podium erscheint erst ab `counting`; nach dem Wechsel steht Name X
über Name Y (DOM-Reihenfolge), sein Chip sagt „+2"; Konfetti-Element
existiert nach Führungswechsel; ohne Schalter zeigt die Seite den Hinweis;
kein seitliches Scrollen (14-layout). Fixtures erzeugt aus
`prediction.service.board(probe=2021, counted=40/90)` mit drei
Test-Spieler*innen (Anhang C.4). Bild(er) an Tim: Podium mit Konfetti,
Liste mit ▲▼, TV-Modus auf 1920×1080 (`resize_window`).

**Zeit:** 5 h (FLIP + Podium 3 h, Konsens/QR/TV 2 h). Wird es knapp:
TV-Seitenwechsel und Konsens sind Kür, Podium + FLIP + Chips sind Pflicht.
**Fertig, wenn** auf dev die Folge `?probe=2021&counted=0 → 40 → 90 →
133` (vier Reloads) Rangwechsel gleitend zeigt, kein Layout-Sprung außer
dem Podium-Eintritt, und Tim das Bild abgenickt hat.

### PR 4 — Betrieb: Admin, Doku, Einstiege, Generalprobe

**Ziel:** Tim legt Samstag das Spiel an, druckt den QR-Code, und Sonntag
läuft es ohne Konsole.

**Admin-Panel** (`app/(app)/admin/page.tsx` — ein weiterer Abschnitt neben
*Neuigkeiten*): Liste der Spiele (Code, Titel, Teilnehmer, offen/zu), „Neues
Spiel" (Titel), je Spiel: Link zur Tafel, Link `/tippspiel?spiel=`,
QR-Bild groß (zum Ausdrucken, `qr.png`), Teilnehmerliste mit „ausblenden"
/ „umbenennen" (Inline-Feld, `PUT …/players/{id}`), „Spiel schließen". Kein
Löschen von Spielen (Rückblick).

**Doku:** `docs-site/src/content/docs/tippspiel.md` (Zweck, Identität ohne
Konto, Punkte aus Anhang A, Betrieb am Sonntag, Grenzen — Muster
`wahlabend.md`), Sidebar-Eintrag in `docs-site/astro.config.mjs` nach
`wahlabend`; Absatz in `wahlabend.md` zur OB-Wahl (`/api/wahlabend/ob`).

**Einstiege:** `components/wahlabend-hinweis.tsx`: kein Link (§3.2 — ohne
Code gibt es nichts zu zeigen). Stattdessen auf `/tippspiel` ohne Code der
Satz mit dem Hinweis. Der Admin-Abschnitt ist der Einstieg für Tim.

**Generalprobe** (Anhang C.5, am Samstag nach dem Deploy auf dev **und**
Prod): Spiel anlegen, drei Tipps von drei Geräten, Tafel mit
`?probe=2021&counted=40` dann `90`, `me` mit Probe, `qr.png` gescannt.

**Schalter auf Prod:** `FEATURE_FLAGS=wahlabend,tippspiel` in der `.env`
von tk-nwz (Sicherung wie am 07.09.: `.env.bak-<datum>`), `sudo systemctl
restart nwz-web-api`. Auf dev gilt `*`.

**Runbook Sonntag:** Anhang D — als Abschnitt in `tippspiel.md`, damit es
am Abend jemand außer dem Modell lesen kann.

**Tests:** `tests/test_prediction_api.py` um Admin-Fälle (anlegen,
schließen, ausblenden → Board ohne die Zeile); Doku-Build (`npm --prefix
docs-site run build`) grün.

**Zeit:** 3 h. **Fertig, wenn** Tim im Admin-Panel ein Spiel angelegt,
den QR-Code gescannt und auf dem Handy getippt hat.

## 5. Zeitplan

| Wann | Was | Wer merged |
|---|---|---|
| Fr 11.09. nachmittags | PR 0 (Votemanager), PR 1 (Backend) parallel anfangen — sie berühren verschiedene Dateien | `merge_wenn_gruen.py`, `--base main` |
| Fr abends / Sa früh | PR 2 (Mitmachen) | nach Tims Bild |
| Sa vormittags | PR 3 (Tafel) | nach Tims Bild |
| Sa nachmittags | PR 4 (Admin, Doku), Schalter auf Prod, Generalprobe auf Prod mit `?probe=2021` | Tim |
| Sa abends | Rückmerge `main → dev` (`git merge origin/main`, s. CLAUDE.md) | — |
| So bis 17 Uhr | QR-Code liegt aus, Gäste tippen; Anhang D Punkt 1–3 | — |
| So 18:05 | Anhang D Punkt 4 (CSV gegen JSON prüfen) | — |

Zusammen rund **18 Stunden** Bauzeit, davon 9 im Frontend. Fällt etwas weg,
dann in dieser Reihenfolge: TV-Seitenwechsel, Konsens-Zeile, OB-Probe
(dann OB erst live ohne Generalprobe), Admin-Umbenennen (dann per SQL).

## Anhang A — Die Punkte

Alle Werte ganze Zahlen; berechnet in `prediction/scoring.py`:

```python
def seat_points(tip: int, actual: int | None) -> int      # None → 0
    # |Δ| 0 → 10, 1 → 7, 2 → 4, 3 → 1, ≥4 → 0
def mayor_points(tip_pct: float, actual_pct: float | None) -> int
    # |Δ| in Prozentpunkten, gerundet: 0 → 5, 1 → 4, 2 → 3, 3 → 2, 4 → 1, ≥5 → 0
def bonus_points(tip: dict[str, int], actual: dict[str, int | None]) -> int
    # +10 stärkste Liste richtig (bei Gleichstand: eine davon)
    # +10 die drei stärksten in richtiger Reihenfolge
def score(tip_seats, tip_mayor, actual_seats, actual_mayor) -> PredictionScore
    # total = seat + mayor + bonus; deviation = Σ|Δ Sitze| (None ohne Zahlen)
def order(rows) -> list[rows]   # total desc, deviation asc, tips updated_at asc, name
```

Höchstwerte: Sitze 160 (16 × 10), OB 45 (9 × 5), Bonus 20 — zusammen 225.
Wer die OB-Wahl nicht tippt, hat dort 0; das ist die Bedeutung von
„optional, aber Bonus". Ränge sind **dicht** (1, 2, 2, 4 gibt es nicht —
1, 2, 3 nach der Sortierung; Gleichstand entscheidet die Abweichung, dann
wer früher fertig war). Solange `basis == "none"` (nichts ausgezählt), gibt
es keinen Score.

Warum diese Kurve: Ein Sitz daneben ist am Wahlabend ein guter Tipp und soll
sich lohnen (7 von 10); ab vier Sitzen ist es geraten. Bei den Prozenten sind
die kleinen Kandidaturen mit 0–2 % für alle leicht — deshalb nur 5 Punkte je
Kandidat*in, damit die OB-Wahl nicht die Ratswahl übertönt.

## Anhang B — Vertrag und Verhalten am Rand

- Alle Tippspiel-Antworten tragen `notes: list[str]`; die Vermerke des
  Wahlabends (`NOTE_REDUCED`, `NOTE_STALE`, `NOTE_EMPTY`) werden
  durchgereicht, dazu eigene: „OB-Ergebnis gerade nicht abrufbar — Stand von
  19:40 Uhr", „Ohne Bezirksdatei keine Hochrechnung; Punkte nach
  ausgezähltem Stand".
- `board()` wirft nie: Fällt `mayor.fetch()`, bleibt `mayor_phase ==
  "before"` und die OB-Punkte sind 0 mit Vermerk; fällt der Store (readonly
  bei voller Platte), kommt der letzte Board-Cache mit `NOTE_STALE`.
- `computed_at` der Tafel = `computed_at` des Wahlabends; **nur** bei einem
  neuen Wert werden Standings geschrieben — so bleibt `rank_before` ein
  echter Vorgänger-Stand und nicht „vor 20 Sekunden".
- Die Deadline ist eine Konstante des Servers (`ELECTION_NIGHT_START`), im
  Vertrag als ISO-String; das Frontend rechnet **nicht** selbst, es
  vergleicht nur gegen `locked`.
- Der Vertrag ist so geschnitten, dass die iOS-App ihn später mit
  denselben sechs Formen nachbauen kann; `python3 scripts/ios_vertrag.py
  --ausgeliefert` bleibt leer, weil die App keinen dieser Endpunkte kennt.

## Anhang C — Befehle und Messungen

### C.1 Register und OB-Kandidaten

```bash
python3 -c "import json;d=json.load(open('kommunalwahl/kandidaten.json'));print([(l['index'],l['slug']) for l in d['lists']])"
python3 -c "import json;print(json.load(open('kommunalwahl/wahl-fakten.json'))['ob_kandidaten'])"
```

### C.2 Votemanager, OB-Wahl (gemessen 11.09.2026)

```bash
V=https://votemanager.kdo.de/20260913/03403000
curl -s $V/daten/api/termin.json                     # wahl.id 2552, gebiet ebene_-6360_id_10357
curl -s $V/daten/api/wahl_2552/ergebnis_ebene_-6360_id_10357_0.json   # vor der Auszählung: nur Zeitstempel
curl -s https://votemanager.kdo.de/20210912/03403000/api/praesentation/wahl_223/ergebnis_ebene_3_id_513_0.json \
  > tests/fixtures/wahlabend/ob-2021.json            # die Fixture (14 KB)
# kein Open-Data-CSV für die OB-Wahl:
for u in Oberbuergermeisterwahl OB-Wahl Buergermeisterwahl; do
  curl -s -o /dev/null -w "$u %{http_code}\n" "$V/daten/opendata/Open-Data-03403000-$u-Stadt.csv"; done   # alle 404
```

### C.3 Ratswahl-Stand in der Probe

```bash
cd web/backend && ../../.venv/bin/python -c "
from app.election import service; n = service.probe(60)
print(n['phase'], n['progress'], [(p['slug'], p['seats'], p['projected_seats']) for p in n['parties']])"
```

### C.4 Board-Fixtures für den Browsertest

```bash
cd web/backend && FEATURE_FLAGS=tippspiel ../../.venv/bin/python -c "
import json; from app.prediction import service
# vorher: Spiel 'TEST01' mit drei Spieler*innen und Tipps in einer Wegwerf-DB (RATSLOTSE_DB=/tmp/t.sqlite)
for c in (0, 40, 90):
    open(f'../frontend/tests/e2e/fixtures/tippspiel-board-{c}.json','w').write(
        json.dumps(service.board('TEST01', probe='2021', counted=c, store=STORE), ensure_ascii=False))"
```

### C.5 Generalprobe nach dem Deploy

```bash
B=https://ratslotse.de
curl -s "$B/api/tippspiel/CODE" | python3 -m json.tool | head -20                       # locked false, 16 parties, 9 mayor_candidates
curl -s "$B/api/tippspiel/CODE/board?probe=2021&counted=90" | python3 -c "import json,sys;b=json.load(sys.stdin);print(b['phase'],b['basis'],[(r['name'],r['rank'],r['score'] and r['score']['total']) for r in b['rows']])"
curl -s -o /tmp/qr.png -w "%{content_type}\n" "$B/api/tippspiel/CODE/qr.png"
```

## Anhang D — Runbook Sonntag, 13.09.2026

1. **Vormittags:** `curl -s https://ratslotse.de/api/app-config` nennt
   `tippspiel` und `wahlabend`. Tafel im TV-Modus öffnen
   (`/tippspiel/tafel?spiel=CODE&tv=1`), QR-Ecke sichtbar, Countdown läuft.
2. **Bis 17:45:** Gäste tippen. Wer keinen Rest 0 hinbekommt, sieht die
   gelbe Leiste — der Tipp ist dann nicht gespeichert (`has_tip false` in
   der Tafel: „tippt noch").
3. **17:55:** Letzter Blick auf `…/board`: alle `has_tip true`, die es sein
   sollen. Ab 18:00 sagt `locked true`.
4. **18:05 — die CSV-Frage:** 
   ```bash
   V=https://votemanager.kdo.de/20260913/03403000
   curl -s $V/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbereiche.csv | cut -d';' -f5-7 | head -8   # anz-schnellmeldungen
   curl -s "https://ratslotse.de/api/wahlabend" | python3 -c "import json,sys;n=json.load(sys.stdin);print(n['phase'],n['progress'],n['source'],n['notes'])"
   ```
   Steht in `notes` „Zahlen aus der Ergebnisdarstellung", greift PR 0 —
   alles gut. Steht dort nichts und `districts_counted` bleibt bei 0,
   obwohl die Website der Stadt Zahlen zeigt: `journalctl -u nwz-web-api
   -n 200 | grep -i wahlabend` — die Hinweise nennen die Datei.
5. **Alle 20 Minuten:** Tafel zeigt `computed_at` der letzten fünf
   Minuten; der Chip ▲▼ bewegt sich. Sonst `notes` lesen — stale heißt „der
   Abruf klemmt", nicht „die Tafel ist kaputt".
6. **Wenn ein Name stört:** Admin-Panel → Tippspiel → ausblenden. Wirkt
   beim nächsten Stand (≤ 30 s).
7. **Nach dem Endergebnis** (`phase complete`, Konfetti): Screenshot der
   Tafel für Tim (`SendUserFile`). Schalter bleibt an, bis der
   Wahlausschuss das amtliche Ergebnis festgestellt hat; dann
   `FEATURE_FLAGS=` ohne `tippspiel`, `wahlabend`, Neustart.
