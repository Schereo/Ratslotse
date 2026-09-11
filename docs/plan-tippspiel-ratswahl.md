# Umsetzungsplan: Tippspiel zur Ratswahl Oldenburg 2026

Stand: 11.09.2026 (Freitag), nachmittags. Die Wahl ist am **Sonntag,
13.09.2026, 8–18 Uhr**; die Auszählung beginnt um 18 Uhr, die erste
Rats-Hochrechnung wird gegen 20 Uhr erwartet. Alles hier muss bis Samstag
Abend auf Prod sein.

Dieser Plan führt **zwei Quellen** zusammen und ersetzt beide:

1. die technische Erhebung vom 11.09. (Datenlage, Votemanager-Robustheit,
   Wiederverwendbares im Repo) und
2. das Design-Artboard **„Tippspiel Kommunalwahl"** aus dem Claude-Design-
   Projekt `2e1e6508-5493-4bff-bfe9-16abab1ed05e` (Artboards `1a`–`1i`:
   Plan, drei Beamer-Screens, vier Handy-Screens, Admin).

Wo beide etwas anderes sagten, steht die Entscheidung mit Begründung in §3.
**Das Design gewinnt bei allem Sichtbaren und bei den Spielregeln** — Tim hat
es durchgesehen. **Die Erhebung gewinnt bei der Datenquelle** — das Design
wurde geschrieben, ohne dass der bestehende Wahlabend-Code bekannt war.

Der Plan ist wie [`plan-cities-phase5.md`](plan-cities-phase5.md)
geschrieben: **ohne das Gespräch dahinter ausführbar**. Jeder Abschnitt in §5
ist ein Pull Request mit Dateien, Signaturen, Tests und Fertig-Kriterium.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`web/backend/CLAUDE.md`, `web/frontend/CLAUDE.md`,
**`web/frontend/DESIGNSPRACHE.md`**, `tests/CLAUDE.md`, die Technik-Doku
`docs-site/src/content/docs/wahlabend.md` und die Modul-Docstrings von
`web/backend/app/election/service.py`, `votemanager.py`, `presentation.py`.
Dazu das Artboard selbst — es ist die Bildvorlage, dieser Text ist die
Bauanleitung.

## 0. Was Tim vorgegeben hat

Am 11.09.2026, in drei Nachrichten:

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

Und zur Zusammenführung mit dem Design:

> Alle dunklen Designs sollten umschaltbar sein in Light Mode.

Daraus die Regeln dieses Plans:

1. **Kein zweites Register.** Listen, Kurznamen, Farben, Sitze 2021 und die
   neun OB-Kandidaturen kommen aus `kommunalwahl/kandidaten.json`,
   `kommunalwahl/parteien-meta.json` und `kommunalwahl/wahl-fakten.json`
   (`ob_kandidaten`) — über `election.register.load()` bzw. eine neue,
   gleich gebaute Funktion für die OB-Kandidaturen. Nichts wird abgetippt.
2. **Kein zweiter Scraper für die Ratswahl.** Sie liegt fertig gerechnet in
   `election.service.live()` (Sitze je Liste, Hochrechnung, Phase, 89 Tests,
   gestufte Rückfälle). Neu ist nur der Abruf der **OB-Wahl** (§2.4) — nach
   dem Muster von `presentation.py`.
3. **Jede dunkle Fläche hat einen Hellmodus.** Die drei Beamer-Screens sind
   im Entwurf dunkel (`hsl(213 50% 7%)`). Sie werden **nicht** mit festen
   Farbwerten gebaut, sondern gegen die Design-Token des Repos, und tragen
   den vorhandenen `LottiThemeSwitch`. Dunkel bleibt die **Vorgabe** auf der
   Beamer-Route (ein Projektor in einem abgedunkelten Raum), umschaltbar ist
   sie trotzdem. Im Hellmodus werden die dunklen Karten zur **Anzeigetafel**,
   nicht zu schwarzen Kacheln — das ist Tims stehende Regel (§3.10).
4. **Die Punkte rechnet der Server.** Ein Rechenweg für Handy und Beamer;
   die Formel steht in Anhang A und in `prediction/scoring.py` mit Tests,
   nirgendwo sonst. (`logik-ins-backend`.)
5. **Der Abend darf an nichts sterben.** Dieselbe Regel wie in `service.py`:
   Die Seiten antworten immer, notfalls mit dem letzten Stand und einem
   Vermerk. Ein 500er um 20 Uhr ist die einzige Antwort, die niemand
   gebrauchen kann.
6. **Manuell schlägt automatisch.** Der Votemanager-Abruf ist die Bequemlich-
   keit, die Handeingabe im Admin ist die Zusage. Veröffentlichen ist ein
   eigener Schritt (Entwurf → live), damit ein Tippfehler nicht auf dem
   Beamer landet.
7. **Web zuerst, iOS nicht.** Bis Sonntag gibt es keinen App-Store-Release
   mehr. Der Vertrag wird so geschnitten, dass die App später nachziehen
   kann; gebaut wird sie in diesem Plan nicht.
8. **Nach `main`, nicht nach `dev`.** `dev` liegt sieben Commits vor `main`
   (Städtevergleich, Admin-Panel); die gehören nicht ungeplant auf Prod.
   Jeder PR dieses Plans zweigt von `origin/main` ab und geht mit
   `--base main` — wie #1150 (Wahlabend) am 06.09. Danach Rückmerge nach
   `dev`.
9. **Bild vor dem Merge.** Jeder UI-PR schickt ein Bild an Tim
   (`SendUserFile`) und wartet sein Gegenlesen ab. Stehende Regel.
10. **Feature-Schalter `tippspiel`**, nicht Umgebungs-Gate: Der Code fährt
    nach Prod, die Seiten gehen per `.env` an und nach dem Abend wieder aus
    — genau wie `wahlabend`.

## 1. Zielbild — die acht Screens des Artboards

```
 HANDY (hell)                          BEAMER (dunkel, umschaltbar hell)
 ┌──────────────────────────┐          ┌────────────────────────────────────┐
 │ 1c  Einstieg nach QR     │          │ 1b  Mitmachen                      │
 │     Name, Regeln in drei │          │     QR 560×560 + Kurzlink +        │
 │     Sätzen, „Los geht's" │          │     Countdown bis zur ersten       │
 ├──────────────────────────┤          │     Hochrechnung + Mitspielerzahl  │
 │ 1d  Tippen               │          ├────────────────────────────────────┤
 │     16 Zeilen, Stepper,  │          │ 1g  Live-Vergleich                 │
 │     Rest-Leiste zählt    │          │     Halbkreis 52 Sitze, Ist gegen  │
 │     live; OB aufklappbar │          │     Ø-Tipp je Liste, OB-Zeile      │
 ├──────────────────────────┤          ├────────────────────────────────────┤
 │ 1e  Mein Tipp            │          │ 1i  SCOREBOARD — das Herzstück     │
 │     vor 20 Uhr Bestäti-  │          │     Podium als Treppe (2/1/3),     │
 │     gung, danach Rang,   │          │     Lotti feiert auf Platz 1,      │
 │     Punkte, Tipp↔Ist     │          │     Rangliste zweispaltig, Zeilen  │
 ├──────────────────────────┤          │     wandern 900 ms, ▲▼-Chips       │
 │ 1f  Spätstarter          │          └────────────────────────────────────┘
 │     „Nachgetippt HH:MM"  │          ┌────────────────────────────────────┐
 └──────────────────────────┘          │ 1h  Admin (hell, Desktop 1280)     │
                                       │     Sitze eintragen, Quelle je     │
                                       │     Liste, Entwurf → Veröffent-    │
                                       │     lichen, Phase, Beamer-Steuerung│
                                       │     Protokoll                      │
                                       └────────────────────────────────────┘
```

Der Ablauf am Abend, wie ihn Artboard `1a` festlegt:

| Zeit | Was passiert |
|---|---|
| ab jetzt | Link und QR verteilen, Tippen offen (`1c` → `1d`). Der Tipp bleibt bis Tipp-Schluss änderbar. |
| 18:00 | Wahllokale schließen. Der Beamer zeigt `1b` mit Countdown „bis zur ersten Hochrechnung". |
| ~20:00 | **Tipp-Schluss = Moment der ersten Rats-Hochrechnung.** Gesetzt durch den Admin („Tippen schließen") oder automatisch, sobald der Votemanager die erste Sitzzahl liefert. |
| danach | Wer einsteigt, darf **weiter tippen** — sein Tipp wird als „Nachgetippt HH:MM" gekennzeichnet (`1f`). |
| 20:00–23:00 | Der Beamer wechselt alle **45 s** zwischen `1g` und `1i`; bei jedem neuen Stand springt er für 60 s auf das Scoreboard, damit die Rangwechsel zu sehen sind. |
| Endergebnis | Admin setzt „Endstand". Das Scoreboard friert ein, Platz 1 bekommt den Endstand-Kicker, auf dem Handy steht der Endrang (`1e`). |

## 2. Was gemessen ist und den Plan trägt

Alle Zahlen vom 11.09.2026, Befehle in Anhang D.

### 2.1 Die internen Daten, die schon da sind

| Quelle | Inhalt | Wer liest sie heute |
|---|---|---|
| `kommunalwahl/kandidaten.json` | 16 Wahlvorschläge in Stimmzettel-Reihenfolge (`index` 1–16, `slug`, `short`, `official`, `kind`), 383 Kandidierende je Wahlbereich | `election/register.py::load()` |
| `kommunalwahl/parteien-meta.json` | `farbe` / `farbe_dunkel` / `kurz` je Slug | `register._colors()` → `ElectionParty.color` |
| `kommunalwahl/referenz-2021/*.csv` | Ergebnis 2021 (Sitze, Anteile) | `election/reference.py` → `seats_2021` |
| `kommunalwahl/wahl-fakten.json` → `ob_kandidaten` | **9 OB-Kandidaturen** mit `name`, `beruf`, `jahrgang`, `vorgeschlagen_von` | noch niemand im Backend |
| `kommunalwahl/wahl-fakten.json` → `wahl` | `sitze: 52`, `termin`, `stichwahl_ob: 2026-09-27` | noch niemand im Backend |

Die 16 Slugs: `gruene spd cdu linke fdp afd volt piraten bsw dava stille
partei pgm buergerbuendnis echt-oldenburg fuer-oldenburg`. Genau diese trägt
ein Sitz-Tipp; die Summe ist **52**.

Die neun OB-Kandidaturen in Dateireihenfolge: Jascha Rohr (Grüne), Ulf Prange
(SPD), Heike Boldt (Linke), Sebastian Fröhlich (FDP), Ralf Butzin (Einzel),
Yakup Castur (DAVA), Byanca Küßner (Einzel), Michael Stille (Einzel), Holger
Martin Wilkens (BB-OL). Sie haben keinen Slug — PR 1 leitet ihn aus dem
Nachnamen ab (`rohr prange boldt froehlich butzin castur kuessner stille
wilkens`); ein Test hält fest, dass die neun verschieden sind.

### 2.2 Was der Wahlabend heute liefert

`GET /api/wahlabend` (`ElectionNight` in `antworten.py`) trägt alles, was das
Tippspiel für die Ratswahl braucht:

- `phase`: `before` | `counting` | `complete`;
- `parties[]` mit `slug`, `short`, `name`, `color`, `color_dark`, `seats`,
  `projected_seats`, `seats_2021`, `share_pct`;
- `progress.districts_counted` / `districts_total` (133), `areas[]` (die
  sechs Wahlbereiche — daraus der `wbLabel` „4/6 Wahlbereiche" des Designs),
  `computed_at`, `notes`, `source.ok`;
- `?probe=2021&counted=N`: die Generalprobe mit den Zahlen von 2021.
  **Damit lässt sich alles vor Sonntag mit echten Bewegungen ansehen**
  (`counted` 0 → 40 → 90 → 133 nacheinander).

`service.live()` hält das Bild im Prozess, erneuert im Hintergrund, wirft
nie. Das Tippspiel ruft **diese Funktion**, nicht den Votemanager.

### 2.3 Ist der Votemanager-Abruf robust? (Tims Frage)

Kurz: **Der Abruf stirbt an nichts, aber er vertraut der CSV mehr, als sie
verdient.** Gelesen in `votemanager.py` (Stand `main`, #1234 enthalten):

| Nr. | Befund | Zeile | Folge am Abend |
|---|---|---|---|
| a | Der Ersatzpfad über die Ergebnisdarstellung wird nur geholt, wenn die Wahlbereichs-CSV fehlt oder **ein Wahlbereich keine Personenstimmen** trägt. | `votemanager.py:265` | Solange die CSV leer bleibt, greift er. Sobald sie einmal Personenstimmen für alle sechs Bereiche trägt, nie wieder — auch wenn sie danach einfriert. |
| b | Eine JSON-Zeile ersetzt die CSV-Zeile nur, wenn sie **Personenstimmen** hat und die CSV keine. | `votemanager.py:273` | Zählt die Stadt am Sonntag nur Listensummen, trägt das JSON keine `sub_zeilen` → die JSON-Zeile wird verworfen, **die leere CSV-Zeile bleibt**. Die Wahlbereiche blieben den Abend über ohne Zahlen, obwohl die Website der Stadt sie zeigt. |
| c | Der **Auszählungsstand** wird nie verglichen. | `votemanager.py:273` | Eine veraltete, aber gefüllte CSV (40 Bezirke) gewinnt gegen ein JSON mit 120 — und sagt es nicht. |
| d | Die **Stadtzeile** wird nur ersetzt, wenn die CSV-Stadt gar nicht `counted` ist. | `votemanager.py:409` | Wie c auf Stadt-Ebene; Anteile und Sitze hängen an ihr. |
| e | Die 133 **Bezirke** kommen nie aus dem JSON (bewusst, #1234). | Docstring | Ohne lebende Bezirks-CSV gibt es keine Hochrechnung; `projected_seats` bleibt `None`. |

Ob die CSVs am Abend im Minutentakt geschrieben werden, lässt sich nicht
messen. Dafür spricht, dass sie `max-schnellmeldungen`/`anz-schnellmeldungen`
tragen (sinnlos für einen Endstand) und `Cache-Control: max-age=60` senden;
dagegen spricht Tims Erfahrung. **Der Plan macht die Frage zweimal
unerheblich:** PR 0 lässt die Ergebnisdarstellung gewinnen, sobald sie weiter
ist als die CSV (nach Auszählungsstand, nicht nach Personenstimmen) — und die
Handeingabe im Admin (`1h`) überschreibt beides. Befund **e** bleibt und ist
tragbar: Fehlt die Hochrechnung, läuft das Spiel auf dem ausgezählten Stand,
und der Admin kann die Zahlen vom Fernseher eintippen.

### 2.4 Die OB-Wahl beim Votemanager

- `daten/api/termin.json` nennt beide Wahlen samt Gebiets-Ids: OB-Wahl
  **`wahl.id 2552`**, Stadt-Gebiet **`ebene_-6360_id_10357`**; Ratswahl 913 /
  `ebene_-6361_id_10358`.
- Das Ergebnis-JSON liegt unter
  `daten/api/wahl_2552/ergebnis_ebene_-6360_id_10357_0.json` — **mit der
  vollen Gebiets-Id im Namen**; `ergebnis_10357_0.json` ist 404. Heute trägt
  es nur `zeitstempel` und `seitentitel` (247 Bytes), keine `Komponente` —
  derselbe Vor-Auszählungs-Zustand wie bei der Ratswahl.
- **Eine Open-Data-CSV für die OB-Wahl gibt es nicht** — acht Namensmuster
  probiert, alle 404, auch für 2021; der Verzeichnis-Index ist 403. Die
  OB-Wahl kommt also nur über die Ergebnisdarstellung.
- Die Form ist an **2021** gemessen
  (`20210912/…/wahl_223/ergebnis_ebene_3_id_513_0.json`, 14 KB):

  ```
  Komponente.tabelle.zeilen[]      je Kandidatur: label.labelKurz „Krogmann, SPD",
                                   label.labelLang, zahl „29.564", prozent „40,92 %", color
  Komponente.info.hinweis[]        „Alle Schnellmeldungen eingegangen!", „133 von 133 Ergebnissen"
  Komponente.info.tabelle.zeilen[] Wahlberechtigte / Wählerinnen/Wähler / ungültige / gültige Stimmen
  Komponente.wahlbeteiligung.text.prozent   53.83
  Komponente.gewaehlte_kandidaten  title „Es findet eine Stichwahl statt zwischen", items[].label
  Komponente.grafik.balken[]       dieselben Zahlen als int (wert, prozentGerundet)
  ```

  `presentation.py` kann davon schon `_reports` (den „n von 133"-Satz),
  `_totals` (die Info-Tabelle) und `parse_number` („29.564" → 29564). Neu ist
  nur die Kandidaten-Zeile. Die 2021-Datei wird **Fixture** und zugleich die
  Generalprobe der OB-Wahl.

### 2.5 Was das Design an Maßen vorgibt

Aus dem Artboard abgelesen (die Beamer-Screens sind 1920×1080, im Artboard
mit `scale(.5)` dargestellt):

| Screen | Raster | Kernmaße |
|---|---|---|
| `1b` Mitmachen | `1fr 620px`, gap 80, padding 96/120 | H1 104 px Bricolage, Countdown 64 px tabular-nums in gerahmtem Kasten, QR-Karte 560×560 weiß mit Radius 32 und 34 px Innenrand, Lotti `pose="point"` 150 px |
| `1g` Vergleich | `700px 1fr`, gap 80, padding 56/80 | Halbkreis 640×340 mit 52 Punkten à 30 px, `transition: background .6s`; „52 Sitze" 60 px; Lotti `pose="search"` 96 px in einer Karte mit dem Vergleichssatz |
| `1i` Scoreboard | Podium `1fr 1.25fr 1fr`, gap 28, `align-items:end` | **Treppe:** Platz 2 = 232 px, Platz 1 = 300 px, Platz 3 = 200 px. Platz 1 mit Verlauf, Leucht-Schatten, laufendem Glanzband (`sweep 5 s`) und Lotti `pose="celebrate"` 120 px (`bob 3 s`). Rangziffern 56/44/44 px, Namen 64/44/40 px. |
| `1i` Rangliste | **zweispaltig**, Zeilen absolut positioniert | Zeile 74 px hoch, `width: calc(50% - 14px)`, Raster `70px 1fr auto 190px`, `transition: top .9s cubic-bezier(.2,.8,.2,1), left .9s …, background .6s` |
| `1d` Tippen | Handy | Sticky Rest-Kopf mit **segmentierter Leiste** in Parteifarben (`transition: width .25s`), Zeilen mit 8-px-Dot (Inset-Ring `rgba(0,0,0,.15)`), Stepper 44×44, Zahlenfeld 46×44 in Bricolage |
| `1h` Admin | Desktop 1280, hell | Tabelle Liste / Sitze / Stimmen % / Quelle / Ø-Tipp · exakt; Phase-Leiste; Beamer-Steuerung; Protokoll |

Akzentfarbe der Live-Marke: `hsl(19 95% 60%)` (das Signal-Orange der Marke),
als 14-px-Punkt mit `pulse 1.6s infinite`.

### 2.6 Was im Repo schon liegt und wiederverwendet wird

- **`components/wahlabend/halbkreis.tsx`** — genau der Halbkreis aus `1g`,
  mit Mehrheitslinie und Hervorhebung einer Liste. Nimmt
  `parteien: WahlabendPartei[]`, `gesamt`, `feld`, `titel`. **Nicht neu
  bauen.**
- **`components/mascot.tsx`** — `Mascot` mit `pose="celebrate"` /
  `"point"` / `"search"` existiert; `mascot.jsx` im Design-Projekt ist ein
  Port davon. **Achtung, andere Schnittstelle als im Design:** die Größe
  kommt über `className` (`h-32 w-32`), nicht über `size`; statt `bob` gibt
  es `regie` (`"ruhig" | "lebhaft" | "aus"`).
- `components/confetti.tsx` (`ConfettiBurst`), `components/staffel.tsx`,
  `components/reveal.tsx`, `components/aufklapp.tsx`, `components/ui/*`.
- `lib/use-tween.ts`: `useTween(zahl, ms)` und `useFrisch(wert, ms)` — für
  gleitende Punktzahlen und das kurze Aufleuchten bewegter Zeilen.
- `components/web-theme-switch.tsx` → `LottiThemeSwitch`: der fertige
  Hell/Dunkel-Regler für Seiten ohne Konto-Hülle. **Das ist der Schalter aus
  Regel 3.**
- Takte und Kurven in `app/globals.css`: `duration-tipp/-fluss/-weg/-buehne`,
  `ease-out-strong`, `ease-in-out-strong`, `ease-back-out`; die
  Anzeigetafel-Fläche `.hh-tafel`.
- Schriften: **Bricolage Grotesque liegt als `--font-display` / `font-display`
  vor.** **IBM Plex Mono aus dem Design gibt es nicht** — dafür wird
  `font-mono` benutzt (so macht es der Wahlabend schon: `KICKER` in
  `components/wahlabend/view.tsx`). Keine neue Schrift laden.
- `components/wahlabend/view.tsx` als Vorlage für Kopf, Fuß, Polling
  (`useQuery` mit `refetchInterval`) und Countdown (`useWahlabendZeit`,
  MESZ-fest).
- Seiten außerhalb `app/(app)/` (`/wahlabend`, `/kommunalwahl`) haben keinen
  Konto-Kopf; **Query-Parameter statt dynamischer Pfadsegmente** (statischer
  Export).
- `app/ratelimit.py`: `RateLimiter(max_calls, window).check(request)` je IP.
  **Achtung Wahlparty:** 30 Leute im selben WLAN sind EINE Adresse.
- `tests/test_endpunkt_schutz.py`: jeder öffentliche Endpunkt steht mit
  Begründung in der Liste. `scripts/rauchprobe.py`: handgepflegt, das
  Tippspiel kommt dort **nicht** hinein (wie `/api/wahlabend`).
- `kern/store.py`: `SCHEMA` + `_migrate()`; `USER_OWNED_TABLES` mit Wächter.
  Die Tippspiel-Tabellen hängen an keinem Konto und tragen deshalb **keine**
  Spalte `owner_id`/`user_id`.

## 3. Wo Design und Erhebung auseinanderliefen — und was gilt

| # | Frage | Entwurf aus der Erhebung | Design-Artboard | **Es gilt** |
|---|---|---|---|---|
| 1 | Punkte je Liste | 10 / 7 / 4 / 1 / 0 | **5 / 3 / 1 / 0** (exakt, ±1, ±2), max 80 | **Design.** Steht auf drei Screens als Satz; die Kurve ist flacher und macht die 16 Listen gleichgewichtiger. |
| 2 | Null getippt, null bekommen | nicht geregelt | **zählt als exakt** | **Design.** Ohne die Regel wären die sechs kleinen Listen wertlos, und genau sie trennen die Feldmitte. |
| 3 | OB-Punkte | 5/4/3/2/1/0 je Prozentpunkt | **6 / 3 / 1** bei ±0,5 / ±1,5 / ±3 Prozentpunkten, max 54 | **Design.** |
| 4 | Routen | `/tippspiel`, `/tippspiel/tafel` | **`/tipp`, `/tipp/live`, `/tipp/admin`** | **Design.** Kürzer auf dem QR-Code und auf dem Beamer lesbar. |
| 5 | Identität | Token im `localStorage` + eigener Header | **Cookie-Token**, Doppelname → „Merle (2)" | **Design** für das Web. Der Token kommt zusätzlich im Antwortkörper, damit ein späterer nativer Client ihn als Header schicken kann. Kein Konto, keine Adresse. |
| 6 | Tipp-Schluss | fest 18:00 | **Moment der ersten Hochrechnung (~20:00)**, gesetzt vom Admin oder automatisch | **Design.** 18:00 ist nur der früheste denkbare Zeitpunkt; der Abend richtet sich nach der ersten Zahl, nicht nach der Uhr. |
| 7 | Spätstarter | dürfen nicht mehr tippen | **dürfen, werden als „Nachgetippt HH:MM" gekennzeichnet**; Schalter „mitgewertet / außer Konkurrenz" | **Design**, mit der Empfehlung des Artboards: Vorgabe **außer Konkurrenz**, sichtbar am Ende der Liste. |
| 8 | Mehrere Spiele | Spiel-Code, `?spiel=CODE` | **ein Spiel**, keine Codes | **Design.** Ein Abend, eine Runde; ein Code auf dem Beamer wäre eine Hürde mehr. Namen sind öffentlich sichtbar — das steht so im Einstieg. |
| 9 | Ergebnisquelle | nur Votemanager, automatisch | **Handeingabe Pflicht, Poller Kür**, neuer `council/wahlergebnis.py` | **Beides, aber anders geschnitten.** Der Poller wird **nicht** neu gebaut: `election.service.live()` gibt es schon, mit Rückfällen und 89 Tests. Die Handeingabe aus `1h` kommt wie entworfen und überschreibt je Liste. Das Design kannte den Wahlabend-Code nicht. |
| 10 | Dunkle Flächen | nicht behandelt | Beamer dunkel `hsl(213 50% 7%)` | **Design plus Tims Nachtrag:** gegen Token bauen, Vorgabe dunkel auf `/tipp/live`, `LottiThemeSwitch` in der Ecke. Im Hellmodus werden die dunklen Karten zur **Anzeigetafel** (`.hh-tafel`, hell `hsl(205 52% 92%)` mit Rand `hsl(206 38% 82%)`) — nie schwarze Kacheln auf heller Seite. |
| 11 | Vergleichswert je Liste | Median der Tipps | **Ø-Tipp** (Mittel aller Tipps vor Tipp-Schluss) | **Design.** |
| 12 | Rang-Animation | FLIP-Messung | **absolute Zeilen, `top`/`left` per Rang, 900 ms** | **Design.** Einfacher und ohne Messung; der Endzustand steht auch ohne JavaScript. |
| 13 | Polling | 60 s / 30 s | **30 s mit ETag** | **Design.** |
| 14 | Beamer-Umschaltung | `?tv=1`, manuell | **Automatik 45 s, Sprung auf das Scoreboard bei neuem Stand** | **Design.** |

Bewusst **nicht gebaut** (aus `1a`): Konten, Chat, Preise, Tipps auf die
Wahlbeteiligung, Tipps je Wahlbereich oder auf Personen, Push und Mail
(es gibt keinen Kanal ohne Konto), die OB-Stichwahl am 27.09.

## 4. Die Regeln als Sätze (so stehen sie auf den Screens)

- **Sitze:** „Punkte je Liste: exakt 5 · ±1 Sitz 3 · ±2 Sitze 1." Max 80.
- **OB-Bonus:** „bis 6 Punkte je Kandidatur", ±0,5 % → 6, ±1,5 % → 3,
  ±3 % → 1. Max 54. Wer nicht mittippt, bekommt 0 — **kein Abzug**.
- **Gleichstand:** kleinere Summe der Sitz-Abweichungen gewinnt, dann die
  frühere Abgabe.
- **Spätstarter:** „Nachgetippt HH:MM", außer Konkurrenz am Ende der Liste.
- **Vorbehalt** in der Fußzeile beider Beamer-Screens, wie unter der
  Wahlabend-Tafel: „Die Punkte rechnen wir; maßgeblich ist die amtliche
  Ergebnisdarstellung der Stadt."

## 5. Die Pull Requests

Reihenfolge ist Abhängigkeit: 0 → 1 → 2 → 3 → 4. **PR 0 ist unabhängig vom
Rest und sollte als Erstes gemergt werden** — er nützt dem Wahlabend auch
ohne Tippspiel. Die Reihenfolge 1 → 2 → 3 folgt dem Artboard `1a`: erst
rechnen, dann das Handy (damit verteilt werden kann), dann der Admin, dann
der Beamer.

### PR 0 — Votemanager: die Ergebnisdarstellung gewinnt, wenn sie weiter ist

**Ziel:** Befunde b, c, d aus §2.3 schließen. Danach ist es für die
Ratszahlen egal, ob die Open-Data-CSV am Abend lebt.

**Dateien:** `web/backend/app/election/votemanager.py`,
`tests/test_wahlabend_live.py`, `docs-site/src/content/docs/wahlabend.md`.

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
an (statt „nur wenn die CSV-Stadt nicht `counted` ist"). Der Hinweistext wird
allgemein: „…: Zahlen aus der Ergebnisdarstellung des Votemanagers — sie ist
weiter als die Open-Data-CSV."

**Tests** (der Fake-Server `Lage`/`Stoerung` in `test_wahlabend_live.py` legt
CSV und JSON getrennt):

- `test_json_ohne_personen_ersetzt_leere_csv` — CSV leer, JSON mit
  Listensummen ohne `sub_zeilen` → Anteile gefüllt,
  `person_votes_available == False`, Hinweis in `notes`.
- `test_json_weiter_als_csv_gewinnt` — CSV 40/22 Meldungen mit Personen,
  JSON 22/22 → Zahlen aus dem JSON.
- `test_csv_weiter_als_json_bleibt` — umgekehrt, kein Hinweis.
- `test_stadtzeile_folgt_derselben_regel`.
- Die bestehenden 89 Wahlabend-Tests bleiben grün (`-k wahlabend`).

**Fertig, wenn** die vier Tests grün sind und `/wahlabend?probe=2021&counted=60`
unverändert aussieht (die Probe läuft ohne JSON). **Zeit: 1,5 h.**

### PR 1 — Backend: Schema, Punkte, OB-Abruf, Endpunkte

**Ziel:** Alles, was rechnet und speichert. Danach lässt sich mit `curl`
tippen und der Stand als JSON lesen.

**Neu:** `web/backend/app/prediction/__init__.py`, `scoring.py` (Anhang A),
`service.py`, `web/backend/app/election/mayor.py`,
`web/backend/app/routers/tippspiel.py`, `tests/test_prediction_scoring.py`,
`tests/test_prediction_api.py`, `tests/test_prediction_mayor.py`,
`tests/fixtures/wahlabend/ob-2021.json`.

**Geändert:** `kern/store.py` (SCHEMA + Methoden), `kern/features.py`
(Schalter `tippspiel`), `web/backend/app/antworten.py`, `schemas.py`,
`main.py` (`include_router`), `ratelimit.py`,
`web/backend/requirements.txt` + `constraints.txt` (`segno`),
`tests/test_endpunkt_schutz.py`, `api/openapi.json` +
`web/frontend/lib/api-schema.ts` (neu geschnitten).

**Schema** (in `kern/store.py::SCHEMA`, englisch, kein `owner_id`):

```sql
-- Ein Spiel je Wahl; die Zeile trägt den Zustand des Abends.
CREATE TABLE IF NOT EXISTS prediction_game (
    id            INTEGER PRIMARY KEY CHECK (id = 1),   -- es gibt genau eines
    title         TEXT NOT NULL,
    phase         TEXT NOT NULL,      -- open | locked | live | final
    locked_at     TEXT,               -- Tipp-Schluss (1. Hochrechnung)
    locked_reason TEXT,               -- 'admin' | 'projection'
    late_scored   INTEGER NOT NULL DEFAULT 0,  -- Spätstarter mitgewertet?
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prediction_players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,        -- Anzeigename, Doppelte als „Merle (2)"
    token_hash  TEXT NOT NULL UNIQUE, -- sha256 des Cookie-Geheimnisses
    created_at  TEXT NOT NULL,
    late_at     TEXT,                 -- gesetzt, wenn nach locked_at getippt
    hidden_at   TEXT                  -- Moderation: NULL = sichtbar
);
CREATE TABLE IF NOT EXISTS prediction_tips (
    player_id   INTEGER PRIMARY KEY REFERENCES prediction_players(id),
    seats_json  TEXT NOT NULL,        -- {"gruene": 14, …} alle 16 Slugs, Summe 52
    mayor_json  TEXT,                 -- {"rohr": 31.5, …} oder NULL
    updated_at  TEXT NOT NULL
);
-- Der veröffentlichte Stand: je Liste eine Zeile, mit Herkunft.
CREATE TABLE IF NOT EXISTS prediction_result (
    slug        TEXT PRIMARY KEY,     -- Listen-Slug oder 'ob:<slug>'
    seats       INTEGER,              -- Sitze (Listen) — NULL bei OB-Zeilen
    pct         REAL,                 -- Prozent (OB) bzw. Stimmenanteil
    source      TEXT NOT NULL,        -- 'votemanager' | 'manuell'
    draft       INTEGER NOT NULL DEFAULT 1,   -- 1 = Entwurf, 0 = veröffentlicht
    updated_at  TEXT NOT NULL
);
-- Ein Rang je Person je veröffentlichtem Stand: Grundlage der ▲▼-Chips.
CREATE TABLE IF NOT EXISTS prediction_standings (
    stand_at    TEXT NOT NULL,
    player_id   INTEGER NOT NULL,
    rank        INTEGER NOT NULL,
    points      INTEGER NOT NULL,
    PRIMARY KEY (stand_at, player_id)
);
-- Das Protokoll aus 1h.
CREATE TABLE IF NOT EXISTS prediction_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    text       TEXT NOT NULL          -- „20:05 manuell · CDU 13 → 12 korrigiert"
);
```

**Store-Methoden** (`kern/store.py`, Stil wie die Quiz-Methoden daneben):

```python
def prediction_game(self) -> dict                      # legt die Zeile beim ersten Zugriff an
def prediction_game_set(self, **felder) -> None        # phase, locked_at, locked_reason, late_scored
def prediction_player_add(self, name: str, token_hash: str, late_at: str | None) -> dict
def prediction_player_by_token(self, token_hash: str) -> dict | None
def prediction_player_update(self, pid: int, *, name=None, hidden=None) -> None
def prediction_players(self, include_hidden: bool = False) -> list[dict]   # mit Tipp (LEFT JOIN)
def prediction_name_frei(self, name: str) -> str       # „Merle" belegt → „Merle (2)"
def prediction_tip_set(self, pid: int, seats: dict[str,int], mayor: dict[str,float] | None) -> None
def prediction_result(self, *, draft: bool | None = None) -> list[dict]
def prediction_result_set(self, rows: list[dict], *, source: str, draft: bool = True) -> None
def prediction_result_publish(self) -> int             # draft=0 für alle; gibt die Zahl zurück
def prediction_result_discard(self) -> None            # Entwurf verwerfen
def prediction_standings_record(self, stand_at: str, rows: list[tuple[int,int,int]]) -> None
def prediction_standings_previous(self, before: str) -> dict[int,int]
def prediction_log_add(self, text: str) -> None
def prediction_log(self, limit: int = 20) -> list[dict]
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
    runoff: tuple[str, ...]        # Slugs aus gewaehlte_kandidaten
    fetched_at: str | None; ok: bool; error: str | None; notes: tuple[str, ...]

def candidates() -> tuple[MayorCandidate, ...]   # aus wahl-fakten.json; @lru_cache
def slug_of(name: str) -> str                    # „Sebastian Fröhlich" → „froehlich"
def parse(payload, known) -> MayorResult | None  # None ohne Komponente
def resolve_ids(session, base) -> tuple[int, str]  # aus termin.json, Vorgabe bei Fehler
def fetch(force: bool = False) -> MayorResult    # TTL wie votemanager, letzter guter Stand, wirft nie
def probe(counted: int | None) -> MayorResult    # aus ob-2021.json
def reset() -> None
```

Zuordnung: `labelKurz` vor dem Komma → `slug_of(nachname)`; eine Zeile ohne
Treffer im Register wird als Hinweis gemeldet und **mitgezählt**, nicht
verworfen. `phase`: `before` ohne `Komponente` oder `reports_received == 0`,
`complete` bei `received == expected > 0`, sonst `counting`. Dazu
`GET /api/wahlabend/ob` (Form `MayorNight`, hinter dem Schalter `wahlabend`).

**Antwortformen** (`antworten.py`, `TypedDict`, Nullbares als `| None`):

```python
class PredictionParty(TypedDict):
    slug: str; short: str; name: str; color: str; color_dark: str; seats_2021: int | None
class PredictionMayorCandidate(TypedDict):
    slug: str; name: str; party: str
class PredictionSetup(TypedDict):            # GET /api/tipp/setup
    title: str; phase: str; seats_total: int
    locked: bool; locked_at: str | None; late_scored: bool
    player_count: int; deadline_hint: str     # „bis zur ersten Hochrechnung"
    parties: list[PredictionParty]; mayor_candidates: list[PredictionMayorCandidate]
class PredictionSeatLine(TypedDict):
    slug: str; tip: int; actual: int | None; avg_tip: float | None; points: int; exact: bool
class PredictionMayorLine(TypedDict):
    slug: str; tip: float; actual_pct: float | None; avg_tip: float | None; points: int
class PredictionScore(TypedDict):
    total: int; seat_points: int; mayor_points: int; exact_lists: int; deviation: int | None
class PredictionMine(TypedDict):
    player_id: int; name: str; late_at: str | None; scored: bool
    has_tip: bool; has_mayor_tip: bool; locked: bool
    seats: list[PredictionSeatLine]; mayor: list[PredictionMayorLine]
    score: PredictionScore | None; rank: int | None; rank_before: int | None
    phase: str; stand_label: str; source_label: str; notes: list[str]
class PredictionRow(TypedDict):
    player_id: int; name: str; late_at: str | None; scored: bool; has_tip: bool
    score: PredictionScore | None; rank: int | None; rank_before: int | None
class PredictionCompareLine(TypedDict):
    slug: str; short: str; color: str; color_dark: str
    actual: int | None; avg_tip: float | None; exact_count: int
class PredictionStand(TypedDict):             # GET /api/tipp/stand
    phase: str; stand_label: str              # „20:38"
    area_label: str                           # „4/6 Wahlbereiche"
    source_label: str                         # „votemanager" | „manuell" | „gemischt"
    seats_total: int; player_count: int; tip_count: int
    compare: list[PredictionCompareLine]
    mayor: list[PredictionMayorLine]; mayor_status: str
    rows: list[PredictionRow]                 # nach Rang, dann Name
    leader_player_id: int | None
    compare_sentence: str                     # der Satz neben Lotti in 1g
    computed_at: str; notes: list[str]
class MayorNight(TypedDict): ...
```

**Eingaben** (`schemas.py`): `PredictionJoinIn(name)` — 2–30 Zeichen,
getrimmt, ohne Zeilenumbrüche. `PredictionTipIn(seats, mayor)` — der Router
prüft gegen das Register: genau die 16 Slugs, jeder 0–52, **Summe 52**; OB:
nur bekannte Slugs, jeder 0–100 mit einer Nachkommastelle, **Summe höchstens
100**, fehlende Slugs = 0; `mayor: null` = nicht mitgetippt. Fehler als 422
mit deutschem Satz.

**Router** (`routers/tippspiel.py`; alle öffentlichen hinter
`features.an("tippspiel")` → 404 wie beim Wahlabend):

| Methode/Pfad | Schutz | Antwort |
|---|---|---|
| `GET /api/tipp/setup` | offen | `PredictionSetup` |
| `POST /api/tipp` | offen, Bremse | `PredictionMine` + `Set-Cookie: tipp_token` (HttpOnly, SameSite=Lax, 30 Tage); Body `{name, seats, mayor?}`; legt an oder aktualisiert |
| `GET /api/tipp/me` | Cookie (sonst 401) | `PredictionMine` |
| `DELETE /api/tipp/me` | Cookie | `Ok` |
| `GET /api/tipp/stand` | offen, **ETag** | `PredictionStand` |
| `GET /api/tipp/qr.png` | offen | PNG 600×600, `Cache-Control: public, max-age=3600` |
| `GET /api/tipp/admin/stand` | `require_admin` | `PredictionStand` + Entwurfszeilen |
| `PUT /api/tipp/admin/ergebnis` | `require_admin` | Entwurf setzen (je Liste `{slug, seats}` bzw. `ob:<slug>`, `source: "manuell"`) |
| `POST /api/tipp/admin/abfragen` | `require_admin` | „Jetzt abfragen": `service.live()` + `mayor.fetch(force=True)` in den Entwurf |
| `POST /api/tipp/admin/veroeffentlichen` | `require_admin` | Entwurf → live, Standings schreiben, Protokollzeile |
| `POST /api/tipp/admin/verwerfen` | `require_admin` | Entwurf verwerfen |
| `PUT /api/tipp/admin/phase` | `require_admin` | `{phase, late_scored?}` — „Tippen schließen", „Endstand setzen" |
| `PUT /api/tipp/admin/spieler/{id}` | `require_admin` | `{name?, hidden?}` |

`GET /api/tipp/stand` und `…/me` nehmen `?probe=2021&counted=N` wie
`/api/wahlabend` (Generalprobe: Ratswahl `service.probe`, OB `mayor.probe`).
`qr.png` nutzt **`segno`** (reines Python, PNG ohne Pillow:
`segno.make(url, error="m").save(buf, kind="png", scale=12, border=2)`) —
eine Zeile in `web/backend/requirements.txt`, eine Fassung in
`constraints.txt`, Ausnahme in `test_api_vertrag.py` wie `bild.png`.

**Der automatische Tipp-Schluss.** Beim Bauen des Stands gilt: Ist
`game.phase == "open"` und liefert der Wahlabend erstmals eine Zahl (ein
`projected_seats` oder `seats` > 0), setzt `service` `phase = "locked"`,
`locked_at = jetzt`, `locked_reason = "projection"` und schreibt eine
Protokollzeile. Das ist der einzige Ort, an dem das passiert — ein zweiter
Weg wäre eine zweite Wahrheit.

**Stand-Rechnung** (`prediction/service.py`):

```python
def setup(store) -> PredictionSetup
def stand(store, *, probe, counted) -> PredictionStand
def mine(store, token: str, *, probe, counted) -> PredictionMine
def _actual(store, night, mayor) -> tuple[dict[str,int|None], dict[str,float|None], str]
    # veröffentlichte Handeingabe schlägt den Wahlabend; gibt auch source_label
def _avg_tips(tips) -> dict[str, float]        # Ø-Tipp, nur Tipps vor locked_at
def _compare_sentence(compare) -> str          # „Die Runde hat die CDU im Schnitt um 2 Sitze zu stark getippt."
```

`stand()` liest `election.service.live()` (bzw. `probe`), `mayor.fetch()`,
den veröffentlichten `prediction_result` und alle sichtbaren Spieler*innen,
rechnet `scoring.score(...)`, sortiert (Anhang A), schreibt die Ränge unter
dem Stand-Zeitstempel (`INSERT OR IGNORE`) und holt `rank_before` aus dem
letzten anderen Stand. Vor dem ersten veröffentlichten Ergebnis ist `score`
`None`, `rank` `None`, Reihenfolge alphabetisch. Das fertige Ergebnis wird
20 s im Prozess gehalten, und daraus entsteht der **ETag** — 30 Handys und
der Beamer rechnen den Abend nicht 30-mal nach.

**Tests:**

- `test_prediction_scoring.py`: Anhang A Zeile für Zeile — 5/3/1/0; **0 auf 0
  zählt als exakt**; OB 6/3/1 mit den Grenzen 0,5/1,5/3,0 (auch genau auf der
  Grenze); kein Abzug ohne OB-Tipp; Gleichstand über Abweichung, dann
  Abgabezeit; Höchstwerte 80 / 54 / 134; `None`-Ergebnis → kein Score.
- `test_prediction_mayor.py`: `parse(ob-2021.json)` → 6 Kandidaturen,
  Krogmann 29.564 / 40,92, `133/133`, `phase complete`, `runoff` zwei Slugs;
  Payload ohne `Komponente` → `None`; die neun 2026er Slugs verschieden;
  unbekannter Nachname → Hinweis und mitgezählt.
- `test_prediction_api.py` (TestClient, `FEATURE_FLAGS=tippspiel`,
  `DISABLE_RATE_LIMIT=1`, `election.service` und `mayor.fetch` auf `probe(60)`
  gepatcht): Tipp mit Summe 51 → 422; Tipp OK → Cookie gesetzt, `me.seats`
  16 Zeilen; zweiter „Merle" → Name „Merle (2)"; nach `phase=locked` neuer
  Tipp → `late_at` gesetzt und `scored False`; Entwurf setzen ändert den
  öffentlichen Stand **nicht**, Veröffentlichen schon; `rank_before` nach
  dem zweiten veröffentlichten Stand gesetzt; ausgeblendete Person fehlt;
  Schalter aus → 404; ohne Cookie 401; Admin-Routen ohne Admin 403; ETag
  liefert beim zweiten Abruf 304; `qr.png` ist ein PNG.
- `test_endpunkt_schutz.py`: die sechs offenen Routen mit Begründung.
- **Der Schalter `tippspiel` kommt erst in PR 2 in die Registry** — sonst
  wird `tests/test_features.py` rot, das je Schalter eine
  `useFeature("…")`-Stelle im Frontend verlangt. PR 1 patcht `FEATURES` in
  seinen Tests.

**Fertig, wenn** `python scripts/pruefe.py --schnell` grün ist und der
Ablauf aus Anhang D.3 gegen `scripts/dev.py start` durchläuft. **Zeit: 6 h.**

### PR 2 — Handy: Einstieg, Tippen, Mein Tipp (`1c`–`1f`)

**Ziel:** Vom QR-Scan zum abgegebenen Tipp in unter einer Minute. Danach kann
verteilt werden — das ist der Grund, warum dieser PR vor dem Beamer kommt.

**Neu:** `app/tipp/layout.tsx` (wie `app/wahlabend/layout.tsx`: außerhalb
`(app)`, Metadata, `bg-background`), `app/tipp/page.tsx` (Suspense),
`components/tipp/view.tsx` (die Weiche: kein Cookie → `1c` bzw. nach
Tipp-Schluss `1f`; Cookie und offen → `1d`; Cookie und `locked` → `1e`),
`components/tipp/einstieg.tsx`, `components/tipp/tippen.tsx`,
`components/tipp/ob-tipp.tsx`, `components/tipp/mein-tipp.tsx`,
`lib/tipp.ts` + `lib/tipp.test.ts`, `changelog.d/tippspiel.md`.

**Geändert:** `kern/features.py` (Schalter `tippspiel`, `fertig_wenn`: „Der
Wahlabend ist vorbei und das Scoreboard ein Rückblick"),
`tests/e2e/14-layout.spec.ts` (`OFFEN` um `/tipp` erweitern).

**`lib/tipp.ts`** (reine Logik, mit Test):

```ts
export function startverteilung(parties, total = 52): Record<string, number>
  // Hare/Niemeyer über seats_2021 auf 52 — der Ausgangspunkt des Formulars
export function rest(tipp: Record<string, number>, total = 52): number
export function restText(r: number): string          // „Noch 3 Sitze" | „2 zu viel" | „52 von 52 — passt"
export function restTon(r: number): "warn" | "ok"    // Farbe der Rest-Anzeige
export function segmente(tipp, parties): {slug; farbe; w: string}[]  // die Leiste aus 1d
export function obRest(tipp: Record<string, number>): number         // 100 − Summe
export function rangDelta(rank, rankBefore): {richtung: "auf"|"ab"|"gleich"|"neu"; um: number}
export function punkteText(n: number): string                        // „12 Punkte" / „1 Punkt"
export type Setup = ApiAntwort<"/tipp/setup">; export type Meins = ApiAntwort<"/tipp/me">;
```

**`1c` Einstieg** (`einstieg.tsx`): Kicker „Ratswahl Oldenburg · 13.09.2026",
Überschrift „Wer tippt den Rat am besten?" in `font-display`, der Zweisatz
aus dem Artboard, ein Namensfeld mit der Unterzeile „Öffentlich sichtbar im
Raum. Kein Konto, keine E-Mail.", Primärknopf „Los geht's — tippen". Darunter
die drei Merksätze als Zeilen: „bis ~20 Uhr · Tippen bis zur ersten
Hochrechnung, änderbar", „5 · 3 · 1 Punkte je Liste: exakt, ±1, ±2 Sitze",
„OB-Bonus bis 6 Punkte je Kandidatur".

**`1d` Tippen** (`tippen.tsx`): **Sticky Kopf** mit „Sitze im Rat", dem
Rest-Text rechts in `font-mono` (Farbe nach `restTon`) und der **segmentierten
Leiste** (8 px hoch, Radius 99 px, Segmente in Parteifarben, `transition:
width .25s`). Darunter 16 Zeilen: 8-px-Dot mit Inset-Ring, Kurzname,
Unterzeile (2021er Sitze), Stepper −/+ 44×44 und Zahlenfeld 46×44 in
`font-display`. Aufklappbarer OB-Block („Optional · bis 6 Bonuspunkte je
Kandidatur") mit neun Prozentfeldern und eigener Rest-Anzeige auf 100. Der
Absende-Knopf ist gesperrt, solange der Rest nicht 0 ist, und sagt warum.
Fußzeile: „Änderbar bis zur ersten Hochrechnung (ca. 20 Uhr)."

**`1e` Mein Tipp** (`mein-tipp.tsx`): vor dem ersten Ergebnis die
Bestätigung; danach der Kopf mit Rang („3 von 24"), ▲▼-Chip, Punktzahl groß
(`useTween`) und der Zeile „Sitze 61 · OB-Bonus 12 · 9 Listen exakt".
Darunter die Tabelle Tipp / Ist / Pkt je Liste, und der Satz über die Listen
ohne Sitz („6 Listen ohne Sitz: … — du hattest alle bei 0: je 5 Punkte").
Links „Rangliste" und „OB-Tipp ansehen". Polling alle 30 s, sobald
`phase !== "open"`.

**`1f` Spätstarter**: Kopf mit Warn-Tint (`#fffbeb`), „Die erste Hochrechnung
ist schon da.", der Satz mit dem Tipp-Schluss, das Muster-Etikett
„Nachgetippt HH:MM" und die Erklärung „Fair für alle, die vor 20 Uhr geraten
haben." Zwei Wege: „Trotzdem tippen" und „Nur zuschauen — zur Rangliste".

**Tests:** `lib/tipp.test.ts` (Startverteilung summiert 52; `rest`/`restText`
an den Grenzen; `segmente` summieren auf 100 %; `rangDelta` mit `null`);
`npx tsc --noEmit`; `npx next lint`. Bild an Tim: `1c`, `1d` mit Rest 0,
`1e` mit `?probe=2021&counted=90`.

**Fertig, wenn** ein fremdes Handy über den QR-Link auf dev in unter einer
Minute einen gültigen Tipp abgibt. **Zeit: 5 h.**

### PR 3 — Admin: Ergebnisse, Phase, Beamer (`1h`)

**Ziel:** Tim steuert den Abend ohne Konsole — und kann die Zahlen notfalls
vom Fernseher abtippen.

**Neu:** `app/tipp/admin/page.tsx` (im Admin-Gate, Recht `admin`),
`components/tipp/admin.tsx`, `components/tipp/admin-tabelle.tsx`.
**Geändert:** `app/(app)/admin/page.tsx` (ein Abschnitt „Tippspiel" mit dem
Weg dorthin und dem QR-Bild zum Ausdrucken).

Aufbau nach Artboard `1h`, hell, Desktop 1280:

1. **Kopf**: „Live-Seite verbunden · N Anzeigen", „N Tipps · N nachgetippt".
2. **Ratswahl · Sitze**: Tabelle Liste / Sitze / Stimmen % / Quelle / Ø-Tipp ·
   exakt. Die Sitz-Zelle ist ein Zahlenfeld; wer tippt, setzt die Quelle der
   Zeile auf „manuell". Darüber die Zeile „votemanager · zuletzt 20:38 ·
   nächste Abfrage in 41 s" mit dem Knopf **„Jetzt abfragen"**. Unten die
   Summenzeile („52 von 52") und die zwei Knöpfe **„Entwurf verwerfen"** und
   **„Veröffentlichen → Live"** (primär).
3. **OB-Wahl · Prozent**: neun Felder, Summenzeile, Quelle. Dazu der feste
   Satz „Stichwahl 27.09. ist kein Teil des Tippspiels."
4. **Phase**: Zeitleiste mit Haken — „Tippen offen bis HH:MM", „Tipp-Schluss
   HH:MM · automatisch (1. Hochrechnung)", „Live · Hochrechnungen 4/6",
   „Endergebnis" mit dem Knopf „Endstand setzen". Die Rückfrage steht
   **inline**, kein Dialog (so das Artboard).
5. **Beamer**: Automatik 45 s · Vergleich · Rangliste, plus der Hinweis „Bei
   neuem Stand springt der Beamer für 60 s auf die Rangliste."
6. **Protokoll**: die letzten Zeilen aus `prediction_log`.

**Der Entwurf ist die ganze Idee dieses Screens.** Nichts, was hier getippt
oder abgefragt wird, erscheint auf dem Beamer, bevor „Veröffentlichen"
gedrückt ist. Ein Tippfehler bleibt damit im Admin.

**Tests:** `test_prediction_api.py` um die Admin-Fälle (Entwurf ändert den
öffentlichen Stand nicht; Veröffentlichen schreibt Standings und Protokoll;
„Jetzt abfragen" füllt den Entwurf aus der Probe). Bild an Tim.
**Zeit: 4 h.**

### PR 4 — Beamer: Mitmachen, Vergleich, Scoreboard (`1b`, `1g`, `1i`)

**Ziel:** Das Herzstück. Ein Beamer im Raum, 30 Namen, und man sieht auf
fünf Meter, wer vorn liegt und wer eben drei Plätze gestiegen ist.

**Neu:** `app/tipp/live/page.tsx`, `components/tipp/live.tsx` (Rahmen,
Polling, Ansichts-Automatik, Theme), `components/tipp/beamer-mitmachen.tsx`,
`components/tipp/beamer-vergleich.tsx`, `components/tipp/scoreboard.tsx`,
`components/tipp/podium.tsx`, `tests/e2e/16-tippspiel.spec.ts` +
`tests/e2e/fixtures/tipp-stand-*.json`. **Geändert:** `14-layout.spec.ts`.

**Route und Ansichten.** `/tipp/live?ansicht=qr|vergleich|rangliste`; ohne
Parameter gilt die **Automatik**: vor dem ersten Ergebnis `qr`, danach
Wechsel alle 45 s zwischen `vergleich` und `rangliste`, und bei einem neuen
`computed_at` ein Sprung für 60 s auf `rangliste`. Der Wechsel blendet nur
(`opacity` über `--takt-buehne`), er schiebt nichts.

**Hell und dunkel (Regel 3).** Die Seite setzt beim ersten Aufruf das dunkle
Theme (Beamer), merkt sich aber die Wahl des Geräts wie überall sonst; oben
rechts steht der `LottiThemeSwitch`. Gebaut wird gegen Token, nicht gegen
Farbwerte:

| Design (dunkel) | Token | Hellmodus |
|---|---|---|
| Seite `hsl(213 50% 7%)` | `bg-background` | `hsl(204 45% 97.5%)` |
| Karte `hsl(212 42% 11%)` | die **Anzeigetafel** `.hh-tafel` | `hsl(205 52% 92%)`, Rand `hsl(206 38% 82%)` |
| Rand `hsl(211 36% 17%)` | `border-border` | wie Tafel-Rand |
| Text `hsl(204 40% 96%)` | `text-foreground` | `hsl(212 55% 11%)` |
| Sekundärtext `hsl(208 22% 65%)` | `text-muted-foreground` | wie gehabt |
| Platz-1-Verlauf `hsl(205 92% 34%) → 24%` | `from-primary to-primary` mit Abdunklung | bleibt — Primärfläche ist in beiden Themes erlaubt, weiße Schrift darauf |
| Live-Punkt `hsl(19 95% 60%)` | die Akzentfarbe | bleibt |

**Keine schwarze Kachel im Hellen.** Das ist Tims stehende Regel (Memo
„Anzeigetafel-Tönung, nie Tiefsee im Hellen"); der Entwurf ist im Hellmodus
als Tafel zu lesen, nicht nachzufragen.

**`1b` Mitmachen**: Raster `1fr 620px`. Links Marke, Kicker „Tippspiel",
H1 104 px, der Zweisatz, der gerahmte Countdown („Tippen noch · MM:SS · bis
zur ersten Hochrechnung") und Lotti `pose="point"` mit „N Mitspielende haben
schon getippt." Rechts die QR-Karte 560×560 (weiß **in beiden Themes** — ein
QR-Code wird nicht invertiert) mit `qr.png` und darunter der Kurzlink
`ratslotse.de/tipp`.

**`1g` Vergleich**: Raster `700px 1fr`. Links der **`Halbkreis`** aus
`components/wahlabend/halbkreis.tsx` mit dem veröffentlichten Stand, darunter
„52 Sitze", darunter die Tafel mit Lotti `pose="search"` und dem
`compare_sentence` vom Server, dazu „Ø-Tipp = Mittel aller N Tipps vor
Tipp-Schluss." Rechts die Tabelle Liste / Ist ▮ / Ø-Tipp ◇ / Exakt, darunter
die Zeile „Ohne Sitz laut Hochrechnung: …" und der OB-Block.

**`1i` Scoreboard**: Kopf mit Live-Punkt (`pulse`), Wahlbereichs-Label und
Stand. Dann das **Podium als Treppe**: Raster `1fr 1.25fr 1fr`, `align-items:
end`, Höhen 232 / 300 / 200. Platz 1 mit Verlauf, Leucht-Schatten, laufendem
Glanzband und **Lotti `pose="celebrate"`** (120 px, ruhig schwebend). Bei
einem Führungswechsel läuft einmal `ConfettiBurst` — nicht beim ersten
Rendern und höchstens einmal je Minute; bei `phase === "final"` noch einmal,
und der Kicker über Platz 1 sagt „Endstand".

Darunter die **zweispaltige Rangliste**: Zeilen absolut positioniert, `width:
calc(50% - 14px)`, Höhe 74 px, Raster `70px 1fr auto 190px`, `left`/`top` aus
dem Rang gerechnet:

```ts
// Rang 4 … n, zweispaltig: links die obere Hälfte, rechts die untere.
const proSpalte = Math.ceil(rows.length / 2);
const i = index % proSpalte, spalte = Math.floor(index / proSpalte);
const style = { top: `${i * 82}px`, left: spalte === 0 ? "0" : "calc(50% + 14px)" };
```

`transition: top .9s cubic-bezier(.2,.8,.2,1), left .9s …, background .6s`.
Eine Zeile, die gestiegen ist, leuchtet 1,6 s (`useFrisch` auf `−rank`). Der
▲▼-Chip trägt die Differenz zum vorherigen Stand und **verblasst nach 20 s**
(`transition: opacity .6s`). Spätstarter tragen das Etikett „Nachgetippt
HH:MM" und stehen bei `late_scored = false` am Ende der Liste. Fußzeile: die
Punkteregel in einem Satz plus `ratslotse.de/tipp`.

**`prefers-reduced-motion`**: kein Wandern, kein Glanzband, kein Konfetti —
die Zeilen stehen sofort an der neuen Stelle. Der Endzustand kommt aus
`top`/`left`, nicht aus einer Animation; er steht also auch ohne Bewegung.

**Tests:** `16-tippspiel.spec.ts` mockt `/api/app-config` und
`/api/tipp/stand` mit **drei** Fixtures nacheinander (`open`, `live` Stand A,
`live` Stand B mit vertauschten Rängen) und prüft: vor dem ersten Ergebnis
die QR-Ansicht; Podium ab dem ersten Stand; nach dem Wechsel steht Name X vor
Name Y in der DOM-Reihenfolge und sein Chip sagt „+2"; ohne Schalter der
Hinweis; kein seitliches Scrollen; **beide Themes** (Klasse `dark` gesetzt
und entfernt) ohne dunkle Kachel im Hellen. Bilder an Tim: Scoreboard dunkel,
Scoreboard hell, Vergleich, Mitmachen — alle auf 1920×1080.

**Fertig, wenn** auf dev die Folge `?probe=2021&counted=0 → 40 → 90 → 133`
Rangwechsel gleitend zeigt und Tim beide Themes abgenickt hat.
**Zeit: 6 h.**

### PR 5 — Betrieb: Doku, Generalprobe, Schalter

**Doku:** `docs-site/src/content/docs/tippspiel.md` (Zweck, Identität ohne
Konto, Punkte aus Anhang A, Ablauf, Grenzen, Runbook — Muster
`wahlabend.md`), Sidebar-Eintrag in `docs-site/astro.config.mjs` nach
`wahlabend`; Absatz in `wahlabend.md` zur OB-Wahl (`/api/wahlabend/ob`).

**Schalter auf Prod:** `FEATURE_FLAGS=wahlabend,tippspiel` in der `.env` von
tk-nwz (Sicherung `.env.bak-<datum>` wie am 07.09.),
`sudo systemctl restart nwz-web-api`. Auf dev gilt `*`.

**Generalprobe** (Anhang D.4) am Samstag nach dem Deploy auf dev **und**
Prod. **Zeit: 2 h.**

## 6. Zeitplan

| Wann | Was |
|---|---|
| Fr 11.09. nachmittags | PR 0 und PR 1 parallel anfangen (verschiedene Dateien) |
| Fr abends | PR 2 — danach kann der Link verteilt werden |
| Sa vormittags | PR 3 (Admin) — die Zusage für den Abend |
| Sa nachmittags | PR 4 (Beamer), Bilder an Tim |
| Sa abends | PR 5, Schalter auf Prod, Generalprobe, Rückmerge `main → dev` |
| So bis 19:45 | QR liegt aus, Gäste tippen |
| So ab 20:00 | Anhang E |

Zusammen rund **24 Stunden** Bauzeit. Fällt etwas weg, dann in dieser
Reihenfolge: Ansichts-Automatik auf dem Beamer (dann von Hand über
`?ansicht=`), Ø-Tipp-Spalte in `1g`, OB-Generalprobe, Umbenennen im Admin.
**Nicht** wegfallen dürfen: die Handeingabe (PR 3) und PR 0 — sie sind die
beiden Antworten auf „was, wenn der Votemanager nicht liefert".

## Anhang A — Die Punkte

Alle Werte ganze Zahlen, berechnet in `prediction/scoring.py`:

```python
def seat_points(tip: int, actual: int | None) -> int:
    """5 exakt · 3 bei ±1 · 1 bei ±2 · sonst 0.

    `actual is None` (noch keine Zahl) → 0. Und: 0 getippt auf 0 erhalten
    IST exakt — ohne diese Regel wären die sechs kleinen Listen wertlos,
    und genau sie trennen die Feldmitte."""

def mayor_points(tip_pct: float, actual_pct: float | None) -> int:
    """6 bei ≤0,5 · 3 bei ≤1,5 · 1 bei ≤3,0 Prozentpunkten · sonst 0.
    Die Grenze gehört zur besseren Stufe (genau 1,5 → 3 Punkte)."""

def score(tip_seats, tip_mayor, actual_seats, actual_mayor) -> PredictionScore:
    """total = seat_points + mayor_points; exact_lists zählt die exakten
    Listen; deviation = Σ|Δ Sitze| (None, solange es keine Zahlen gibt).
    Ohne OB-Tipp sind die Bonuspunkte 0 — kein Abzug."""

def order(rows) -> list:
    """total absteigend, deviation aufsteigend, updated_at aufsteigend, name.
    Spätstarter mit `late_at` und `late_scored = False` stehen hinter allen
    gewerteten Zeilen, untereinander nach derselben Regel."""
```

Höchstwerte: Sitze **80** (16 × 5), OB **54** (9 × 6), zusammen **134**. Ränge
sind dicht (1, 2, 3 …); über einen echten Gleichstand entscheidet erst die
Abweichung, dann wer früher fertig war.

## Anhang B — Vertrag und Verhalten am Rand

- Alle Tippspiel-Antworten tragen `notes: list[str]`; die Vermerke des
  Wahlabends (`NOTE_REDUCED`, `NOTE_STALE`, `NOTE_EMPTY`) werden
  durchgereicht, dazu eigene: „OB-Ergebnis gerade nicht abrufbar — Stand von
  19:40 Uhr", „Zahlen von Hand eingetragen".
- `stand()` wirft nie: Fällt `mayor.fetch()`, bleibt `mayor_status` auf
  „noch keine Zahlen" und die OB-Punkte sind 0 mit Vermerk; fällt der Store,
  kommt der letzte Stand aus dem Cache mit `NOTE_STALE`.
- **Standings nur bei neuem Stand.** Geschrieben wird unter dem Zeitstempel
  der Veröffentlichung, `INSERT OR IGNORE` — so bleibt `rank_before` ein
  echter Vorgängerstand und nicht „vor 20 Sekunden".
- **Der ETag** ist der Hash aus `computed_at` + Spielerzahl + Phase. Der
  Beamer fragt alle 30 s und bekommt meist 304.
- Der Vertrag ist so geschnitten, dass die iOS-App später dieselben Formen
  nachbauen kann; `scripts/ios_vertrag.py --ausgeliefert` bleibt leer.

## Anhang C — Was aus dem Design NICHT eins zu eins übernommen wird

| Im Artboard | Im Code | Warum |
|---|---|---|
| `IBM Plex Mono` für Kicker und Zeitstempel | `font-mono` (Systemschrift) | Die Schrift liegt im Repo nicht; eine vierte Schriftfamilie für Kicker zu laden kostet mehr, als sie bringt. Der Wahlabend macht es schon so. |
| `<Mascot size={120} bob />` | `<Mascot pose="celebrate" className="h-[120px] w-[120px]" />` | Die echte Komponente nimmt die Größe über `className` und kennt `bob` nicht; die Ruhe-Bewegung steuert `regie`. |
| Feste Farbwerte `hsl(213 50% 7%)` u. a. | Token (`bg-background`, `.hh-tafel`, `text-muted-foreground`) | Regel 3: Ohne Token gibt es keinen Hellmodus. |
| Neuer Poller `council/wahlergebnis.py` | `election.service.live()` | Gibt es schon, mit Rückfällen und 89 Tests. Ein zweiter Abruf wäre eine zweite Wahrheit. |
| Halbkreis als eigene Punktwolke | `components/wahlabend/halbkreis.tsx` | Dieselbe Grafik ist gebaut, samt Mehrheitslinie und Hervorhebung. |
| `{{ }}`-Platzhalter, `sc-for`, `x-import` | React, `lib/vertrag.ts`-Typen | Das Artboard ist eine Bildvorlage, keine Laufzeit. |

## Anhang D — Befehle und Messungen

**D.1 Register und OB-Kandidaturen**

```bash
python3 -c "import json;d=json.load(open('kommunalwahl/kandidaten.json'));print([(l['index'],l['slug']) for l in d['lists']])"
python3 -c "import json;print(json.load(open('kommunalwahl/wahl-fakten.json'))['ob_kandidaten'])"
```

**D.2 Votemanager, OB-Wahl (gemessen 11.09.2026)**

```bash
V=https://votemanager.kdo.de/20260913/03403000
curl -s $V/daten/api/termin.json                    # wahl.id 2552, ebene_-6360_id_10357
curl -s $V/daten/api/wahl_2552/ergebnis_ebene_-6360_id_10357_0.json
curl -s https://votemanager.kdo.de/20210912/03403000/api/praesentation/wahl_223/ergebnis_ebene_3_id_513_0.json \
  > tests/fixtures/wahlabend/ob-2021.json           # die Fixture, 14 KB
for u in Oberbuergermeisterwahl OB-Wahl Buergermeisterwahl; do
  curl -s -o /dev/null -w "$u %{http_code}\n" "$V/daten/opendata/Open-Data-03403000-$u-Stadt.csv"
done                                                 # alle 404 — kein OB-CSV
```

**D.3 Durchstich nach PR 1**

```bash
B=http://127.0.0.1:8600     # Port aus scripts/dev.py start
curl -s $B/api/tipp/setup | python3 -m json.tool | head -20
curl -s -c /tmp/c -X POST $B/api/tipp -H 'Content-Type: application/json' -d @tipp.json
curl -s -b /tmp/c "$B/api/tipp/me?probe=2021&counted=60" | python3 -m json.tool | head -30
curl -s "$B/api/tipp/stand?probe=2021&counted=90" | python3 -c "import json,sys;s=json.load(sys.stdin);print(s['phase'],s['stand_label'],[(r['name'],r['rank'],r['score'] and r['score']['total']) for r in s['rows']])"
```

**D.4 Generalprobe nach dem Deploy**

```bash
B=https://ratslotse.de
curl -s $B/api/app-config | python3 -c "import json,sys;print(json.load(sys.stdin)['features'])"
curl -s -o /tmp/qr.png -w "%{content_type}\n" $B/api/tipp/qr.png
# Danach im Browser: /tipp von einem fremden Handy, /tipp/live auf dem Beamer
# (beide Themes durchschalten), /tipp/admin → „Jetzt abfragen" → veröffentlichen.
```

## Anhang E — Runbook Sonntag, 13.09.2026

1. **Vormittags:** `curl -s https://ratslotse.de/api/app-config` nennt
   `tippspiel` und `wahlabend`. `/tipp/live` auf dem Beamer öffnen, Theme
   wählen, QR-Ansicht steht, Countdown läuft.
2. **Bis 19:45:** Gäste tippen. Wer den Rest nicht auf 0 bekommt, sieht die
   gelbe Leiste — der Tipp ist dann nicht gespeichert.
3. **Um 20:00, wenn die erste Hochrechnung kommt:** Der Tipp-Schluss setzt
   sich selbst. Kommt keine Zahl, im Admin „Tippen schließen" drücken.
4. **Die CSV-Frage:**
   ```bash
   V=https://votemanager.kdo.de/20260913/03403000
   curl -s $V/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbereiche.csv | cut -d';' -f5-7 | head -8
   curl -s https://ratslotse.de/api/wahlabend | python3 -c "import json,sys;n=json.load(sys.stdin);print(n['phase'],n['progress'],n['source'],n['notes'])"
   ```
   Steht in `notes` „Zahlen aus der Ergebnisdarstellung", greift PR 0.
   Kommt gar nichts, obwohl die Website der Stadt Zahlen zeigt: **Zahlen im
   Admin eintragen und veröffentlichen.** Dafür ist der Screen da.
5. **Je neuem Stand:** „Jetzt abfragen" → Zahlen prüfen → „Veröffentlichen".
   Der Beamer springt von selbst auf das Scoreboard.
6. **Wenn ein Name stört:** Admin → Spieler → ausblenden. Wirkt beim
   nächsten Stand.
7. **Nach dem Endergebnis:** „Endstand setzen". Screenshot des Scoreboards
   für Tim. Der Schalter bleibt an, bis der Wahlausschuss das amtliche
   Ergebnis festgestellt hat; dann `FEATURE_FLAGS` ohne `tippspiel` und
   `wahlabend`, Neustart.
