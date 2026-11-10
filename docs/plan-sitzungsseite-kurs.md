# Plan: Sitzungsseite „Kurs der Sitzung“, Punkt-Seite und Mitlesen

Stand 10.11.2026. Anlass: Tim hat mit Claude in einer Design-Canvas die Seite
einer einzelnen Sitzung neu entworfen. Heute zeigt sie einen Kopf mit Termin
und Ort und darunter die Tagesordnung als Liste. Der Entwurf macht daraus drei
Ansichten derselben Sitzung (vorher, währenddessen, nachher), gibt jedem
Tagesordnungspunkt eine eigene Seite und stellt die Sitzung als Linie mit
Bojen dar, dem „Kurs der Sitzung“.

Dieser Plan ist so geschrieben, dass ein Agent ihn ohne weiteres Nachfragen
umsetzen kann. Er nennt je Schritt die Dateien, die Entscheidungen samt Grund
und die Stellen, an denen der Entwurf dem Bestand widerspricht. Wo etwas
**offen** ist, steht es in Abschnitt 8; dort erst Tim fragen, dann bauen.

**Arbeitsregeln** (Wurzel-`CLAUDE.md`): ein Schritt, ein Branch von `dev`, ein
PR mit `--base dev`, Squash-Merge, Changelog-Fragment in `changelog.d/`. Vor
jedem Push `python scripts/pruefe.py`. Vor dem Merge eines UI-PRs ein Bild an
Tim und sein Gegenlesen abwarten (`REZEPTE.md`, „Eine Frontend-Seite
hinzufügen“).

**Zuerst lesen:** dieser Plan, dann `docs/entwurf-sitzungsseite/README.md`,
dann die Bilder in `docs/entwurf-sitzungsseite/bilder/`. Die Quelldateien des
Entwurfs (`quellen/*.dc.html`) erst, wenn ein genaues Maß gebraucht wird.

> **Woher dieser Plan kommt.** Er wurde außerhalb des Repos geschrieben und
> lag zuerst unversioniert im Haupt-Checkout (Zweig
> `codex/texte-alltagssprache`, 710 Commits hinter `dev`). „Was heute da ist“
> ist deshalb gegen `origin/dev` gemessen, nicht gegen diesen Arbeitsbaum.
> Schritt 0 checkt Plan und Material auf einem Zweig von `dev` ein.

## 0. Kurzfassung

| Schritt | Was | Sichtbar für | Schalter |
|---|---|---|---|
| 0 | Plan und Entwurfsmaterial einchecken | niemand | – |
| 1 | Daten: Etappen, Piktogramm, „wichtig“ je Punkt an `/council/session/{ksinr}` | niemand | – |
| 2 | Baustein „Kurs der Sitzung“ (Rechnung in `lib/`, Komponente) | niemand | – |
| 3 | Sitzungsseite neu: vor und nach der Sitzung | alle | `sitzung_kurs` |
| 4 | Punkt-Seite: Kurzfassung, Vorgeschichte, Unterlagen, „Frag den Rat“ mit Kontext | alle | `punkt_seite` |
| 5 | Mitlesen während der Sitzung | alle | `mitlesen` |
| 6 | Argumente und Fraktionen auf der Punkt-Seite | alle | `punkt_argumente` |
| 7 | Notizen und Mitschrieb, auf dem Gerät verschlüsselt | Konten | eigener Plan |

Schritte 1 bis 3 gehören zusammen und sind der Kern. 4 und 5 bauen darauf auf.
6 und 7 sind eigene Vorhaben mit eigener Messung und dürfen warten.

**Nicht Teil dieses Plans:** die iOS-App (nur Rücksicht auf ihren Vertrag,
s. 3.18), die Sitzungsliste `council/view.tsx` und die Beschluss-Seite.

## 1. Das Material

Alles liegt in `docs/entwurf-sitzungsseite/`.

| Ansicht | Quelle (`quellen/`) | Bilder (`bilder/`) | Beispiel aus dem Bestand |
|---|---|---|---|
| Sitzung nach der Sitzung, Desktop | `Main.dc.html` | `nach-der-sitzung-desktop-1…4.png` | Verkehrsausschuss 08.06.2026, ksinr 4652 |
| Sitzung nach der Sitzung, Handy | `Mobil.dc.html` (bindet `Main` bei 390 px ein) | `nach-der-sitzung-handy-1…2.png` | wie oben |
| Sitzung vor der Sitzung | `VorDerSitzung.dc.html` | `vor-der-sitzung-desktop-1…3.png`, `vor-der-sitzung-handy-1…2.png` | Verkehrsausschuss 21.09.2026, ksinr 4654 |
| Mitlesen | `Mitlesen.dc.html`, `MitlesenMobil.dc.html` | `mitlesen-desktop-1…2.png`, `mitlesen-handy.png`, vier Zustandsbilder `mitlesen-*-zustand-*.png` | wie oben |
| Punkt-Seite | `Punkt.dc.html` | `punkt-desktop-1…2.png`, `punkt-handy-1…2.png` | Ö 9 „Soziales D-Ticket“, 21.09.2026 |
| Baustein Kurs | `Kurs.dc.html` | – | vier Datensätze, s. u. |
| Kurs: wenig, viel, Handy | `KursVarianten.dc.html` | `kurs-varianten.png` | Sportausschuss 07.10.2026 (ksinr 4593), Rat 31.08.2026 (ksinr 4702) |

Die Handy-Bilder zeigen eine lange Seite in Spalten nebeneinander, von links
nach rechts zu lesen. `canvas.json` hält die Notizzettel der Canvas fest; ihr
Inhalt steht vollständig in diesem Plan. Die Canvas selbst heißt „Ratslotse ·
Sitzungsseite Redesign“ und liegt privat bei Tims Claude-Artefakten; dort
lassen sich Mitlesen und Punkt-Seite durchklicken.

`Kurs.dc.html` trägt vier Datensätze in der Methode `sitzungen()`: `wenig`
(Sportausschuss 07.10.2026), `normal` (Verkehrsausschuss 21.09.2026), `viel`
(Rat 31.08.2026) und `nach` (Verkehrsausschuss 08.06.2026, mit Ergebnissen).
Sie sind die Testfälle für Schritt 2.

**Wie die `.dc.html`-Dateien zu lesen sind.** Es ist das Format der
Design-Canvas, kein Code für dieses Repo. Sie laufen nur in der Canvas (die
Laufzeit `support.js` und die Bilder unter `/_blob/…` fehlen hier).

- Fast alles ist gewöhnliches HTML mit Inline-Styles. Die Maße darin sind die
  des Entwurfs und dürfen als Vorlage dienen.
- `{{ name }}` ist ein Platzhalter, den die Klasse `Component` am Dateiende in
  `renderVals()` füllt. `<sc-if>` blendet ein, `<sc-for>` wiederholt,
  `<dc-import name="Kurs">` bindet `Kurs.dc.html` ein.
- **Die Farben sind Literale des Hellmodus.** Im Repo werden daraus Tokens
  (Anhang B). Wer ein Literal aus dem Entwurf in eine Komponente schreibt, hat
  den Dunkelmodus kaputtgemacht.
- Kopfzeile („Anmelden“, „Registrieren“), Fußzeile und der Block „Willst du
  früher davon erfahren?“ gehören zur `PublicShell` des Bestands. Sie stehen
  nur im Entwurf, damit die Seite vollständig aussieht, und werden **nicht**
  nachgebaut.

**Was im Entwurf echt ist und was gesetzt.** Sitzungen, Punkte, Vorlagen,
Ergebnisse und Beschluss-Nummern stammen aus dem Ratsbestand. Von Hand gesetzt
und damit nur Platzhalter sind: alle Lotti-Sätze, die Auswahl „wichtig“ samt
Grund, die Piktogramme, die Etappen, die „Zusagen der Verwaltung“, die
Abschnitte „Was beantragt wird“, „Was die Verwaltung sagt“ und „Was es kostet“,
sämtliche Argumente, Streitpunkte und Fraktions-Paraphrasen der Punkt-Seite,
die Antworten im Gespräch und der Presse-Link. Abschnitt 4.7 sagt je Feld, ob
es dafür schon eine Quelle gibt.

## 2. Was heute da ist (gemessen an `origin/dev`, `3e402c82`, 10.11.2026)

Zeilenangaben sind Näherungen von diesem Stand; vor der Arbeit nachsehen.

| Baustein | Wo | Für den Plan wichtig |
|---|---|---|
| Sitzungsseite | `web/frontend/app/(app)/council/sitzung/view.tsx` (197 Z.), `page.tsx` | Öffentlich (`OEFFENTLICHE_PFADE`), holt `/council/session/{ksinr}`. Kopf-Karte nach `DESIGNSPRACHE.md` § 6 „Kopf einer einzelnen Sitzung“, Aktionsleiste Kalender, Merken, Teilen, Ratsinfo. Auf breiten Schirmen (`useWeit`) zweite Spalte mit `BeschlussVorschau` (`docs/plan-breite-schirme.md`, PR 5) |
| Tagesordnung | `web/frontend/components/tagesordnung.tsx` (647 Z.) | `AgendaRow`, `AenderungenSection`, `DringlichkeitsBlock`, `AttendanceSection`, `CalendarButton`, `LiveChip`, `ergebnisseJeTop`, `useTopSprung`, `useTopsAusLink`, `topKey`, `videoKey`, `topDomId`. **Dieselben Zeilen trägt die Sitzungsliste** (`council/view.tsx`), „damit die beiden Orte nicht auseinanderlaufen“ |
| Antwort der Sitzung | `web/backend/app/routers/council.py` (~Z. 2033), Form `SessionDetail` in `antworten.py` (~Z. 2748) | `agenda_items`, `decisions`, `attendance`, `has_protocol`, `video_results`, `url`, `agenda_changes`, optional `live_state` |
| Ein Punkt | `AgendaItemRow` in `antworten.py` (~Z. 91), aus `CouncilStore.agenda_items` | `item_number`, `title`, `template_number`, `kvonr`, `is_public`, `anlagen`, `summary`, `social_text`, `dringlich`. Dieselbe Methode bedient die Merkliste |
| Texte je Punkt | Tabellen `agenda_item_summaries`, `agenda_item_social` | `summary` entsteht nur aus dem Titel, `social_text` kennt Vorlage und Anlagen und ist der bessere Text, wo es ihn gibt |
| Überschriften und Gruppen | `council/store_sitzungen.py::_ueberschriften`, `_eltern_nummer` | Erkennt Oberpunkte ohne Vorlage und trennt **Vorhaben** („Ö 11 Bauleitplanung …“) von **Rubriken** („Anträge der Fraktionen …“). Grundlage der Etappen |
| Wichtigkeit vor der Sitzung | `_punkte_bewerten`, `_bewertete_punkte`, `_punkt_export`, `sitzungs_highlights`, `agenda_wichtigkeit` (Tabelle `agenda_item_impact`, Tragweite 0–100) | Eine Bewertung für alle Abnehmer. `_punkt_export` liefert u. a. `titel_kurz`, `applicants`, `wichtig`, `wichtig_grund`, `wichtig_quelle`, `kind`, `behandlung`, `vorgeschichte`, `gruppe_nr`, `gruppe_titel`, `gruppe_stationen`, `top`. Nur für kommende Sitzungen bewertet |
| Wiederkehr | `_wiederkehr`, `agenda_since_decisions` | Wie oft eine Formulierung schon auf einer Tagesordnung stand; Stationen einer Vorlage nach ihrem jüngsten Beschluss |
| Satz zur Sitzung | Tabelle `committee_summaries` (`get_cached_summary`, `save_summary`) | Zusammenfassung je Sitzung und Tagesordnungs-Stand; leer heißt „nur Routine“. Ob der Text für den Seitenkopf taugt, ist nicht geprüft |
| Live-Fenster | `web/frontend/lib/live.ts`, `council/live.py`, Feld `live_until` | „Live“ = Startzeit erreicht, Ende noch nicht. Aus Kalenderdaten gerechnet |
| **Live-Stand** | `council/livetracker.py`, Tabellen `council_live_state`, `council_live_events`, Feld `live_state` (`LiveState` in `antworten.py`) | **Nur Ratssitzungen** (O1 überträgt nur den Rat). Aus dem Transkript des Streams, alle 30 Sekunden: `item_number`, `item_title`, `block_start`, `phase`, `speaker`, `party`, `since`, `as_of`, `finished`. Im Web: `components/live-banner.tsx`, in der Sitzungsliste über `liveItemKeys`, `liveSpeakerText`, `liveStateFresh`, `LIVE_REFRESH_MS` |
| Vorläufige Ergebnisse | `components/video-result.tsx`, Feld `video_results` | Aus der O1-Übertragung gelesen, gestrichelt gerahmt, verschwinden, sobald das Protokoll da ist |
| Frag den Rat | `POST /council/ask` (~Z. 5401), `AskBody` (~Z. 5061), `components/council-qa.tsx` (3.735 Z.) | `AskBody` trägt `question`, `history` (max. 4), `conversation_id`, `previous_answer`, `from_suggestion` und **`screen: ScreenContext`** mit `route`, `heading`, `element_title`, `element_text`, `selection` und `refs` (`decision_id`, `ksinr`, `slug`, `place_id`, `year`, `area`). Es gibt einen Sitzungs-Fragetyp, der die ganze Sitzung in den Kontext legt |
| Lotti | `components/lotti.tsx`, `mascot.tsx`, `POST /council/explain` | Erklärt, was auf dem Bildschirm steht. Regeln in `DESIGNSPRACHE.md` § 1, § 5, § 8 |
| Akte | `council/matters.py::akte_von`, `docs/plan-akte.md` | Stationen eines Vorgangs über Jahre. Quelle für die Vorgeschichte |
| Wortbeiträge | Tabelle `council_speeches` | Quelle für Argumente und Fraktionen (Schritt 6) |
| Merken und Folgen | `BookmarkButton` (Arten `session`, `agenda_item`, `decision`), `POST/DELETE /council/template/{kvonr}/follow` | Bleibt, wie es ist |
| Gremien | `web/frontend/lib/committees.ts` | `shortCommittee`, `committeeIcon`, `committeeExplains` |
| Schalter | `kern/features.py`, `useFeature("…")`, `tests/test_features.py` | Kein Schalter ohne Nutzung, keine Nutzung ohne Schalter |
| Tests | `npx vitest run` (reine Logik in `lib/`), Browsertests in `web/frontend/tests/e2e/` (`03-oeffentlich`, `04-council`, `14-layout`, `17-lesbarkeit`), `pytest tests/` | Komponenten werden nicht per JSX-Test geprüft, sondern im Browser |
| iOS | `ios/Packages/RatslotseFeatures/…/CouncilViews.swift`, `LiveStateText.swift`, `RatslotseAPI/…/Models.swift` | Decodiert `SessionDetail` von Hand. Neue Felder nur optional und zusätzlich |
| Notizen | – | Gibt es nicht |

## 3. Wo der Entwurf dem Bestand widerspricht

Der Entwurf entstand gegen einen alten Stand und ohne Blick in
`DESIGNSPRACHE.md` von `dev`. Diese Punkte sind die eigentliche Arbeit der
Übergabe. „Entschieden“ heißt: so bauen. „Offen“ verweist auf Abschnitt 8.

**3.1 Lotti-Sprechblase.** Der Entwurf lässt Lotti im Kopf die Sitzung
zusammenfassen, erklärt mit ihr den nichtöffentlichen Teil und begrüßt im
Mitlesen. `DESIGNSPRACHE.md` § 1 sagt: Lotti ist Erklärerin, „nie Autorin einer
Ratsauskunft“; § 8 verbietet jede Sprechblase außerhalb der Anstupser-Grenzen.
Der Satz im Kopf ist eine Ratsauskunft. **Offen (8.1).** Bis zur Antwort: der
Satz steht als gewöhnlicher Absatz in `text-lese` mit KI-Funke und dem Hinweis
„Automatisch zusammengefasst“, ohne Figur. Die beiden reinen Erklärungen
(nichtöffentlich, Mitlesen) bekommen die Form, die der Bestand für Lottis
Erklärungen schon hat; welche Komponente das ist, vor Schritt 3 nachsehen.

**3.2 Tafel außerhalb des Haushalts.** Der Kopf steht auf der Anzeigetafel
(`.hh-tafel`, hell `hsl(205 52% 92%)`, Rand `hsl(206 38% 82%)`). § 4 beschreibt
sie als Fläche für „die eine Zahl“ im Haushalt. **Entschieden:** Der
Sitzungskopf nutzt `.hh-tafel` unverändert, weil die Klasse Hintergrund, Rand
und die Tokens `--card`, `--border`, `--muted-foreground`, `--primary`,
`--signal` je Theme schon richtig setzt. § 4 bekommt im selben PR einen Satz,
dass die Tafel auch den Kurs einer Sitzung trägt. Die Bänder der Etappen sind
`--card` mit Deckkraft, keine eigene Farbe.

**3.3 Kopf einer einzelnen Sitzung.** § 6 beschreibt den heutigen Kopf
(Kicker „Sitzung“, Kurzname, Termin und Ort, Aktionsleiste). Der Entwurf
ersetzt ihn. **Entschieden:** § 6 wird im PR von Schritt 3 neu geschrieben.
Erhalten bleiben: Kurzname als einzige Hauptüberschrift, amtlicher Name
darunter bei Abweichung, Aktionen mit mindestens 44 px, Rücknavigation
oberhalb.

**3.4 Signal-Orange.** Der Entwurf rechnet mit `hsl(19 92% 50%)`. Seit 10/2026
gilt `hsl(19 92% 42%)` (Kontrast). **Entschieden:** immer das Token. Orange
bleibt Marker: die Umrandung des aktiven Punkts und zwei 8-px-Punkte („Jetzt
dran“, „Mitlesen“), nie eine Fläche.

**3.5 Dunkelmodus.** Fehlt im Entwurf. **Entschieden:** Abnahme in beiden
Themes (Anhang B). Die Ergebnisfarben der Bojen kommen aus der Farbgrammatik
der Beschlüsse (`OUTCOME_DOT_CLS` in `components/decision-ui.tsx`), nicht aus
den Hex-Werten des Entwurfs.

**3.6 Was der Entwurf weglässt und bleiben muss.** Der Entwurf kennt diese
Teile der heutigen Seite nicht. Keiner davon entfällt.

| Bestand | Platz in der neuen Seite |
|---|---|
| „Zurück zu den Sitzungen“ (nur angemeldet) | oberhalb der Tafel, wie heute |
| Merken (`BookmarkButton`) | Aktionen im Kopf, zwischen Kalender und Teilen. Der Entwurf zeigt nur zwei bzw. drei Knöpfe |
| Ratsinfo-Link, Protokoll-Link | Aktionen im Kopf, extern und gestrichelt wie im Bestand |
| `LiveChip` | neben dem Titel; solange die Sitzung läuft, führt daneben „Mitlesen“ |
| `AenderungenSection` (nur kommende Sitzungen) | zwischen Kopf und Liste, vor „Leinen los“ |
| `VideoResultsNotice` und Video-Chips | Hinweis über der Liste; Bojen ohne Protokoll-Ergebnis, aber mit Video-Ergebnis: Ring in der Ergebnisfarbe **gestrichelt** |
| `DringlichkeitsBlock` | vor der ersten Etappe; im Kurs eine eigene Etappe „Dringlich“ direkt nach „Zum Start“ |
| `AttendanceSection` | unter der Liste, wie heute |
| Sprung zum geteilten Punkt (`?top=`, `useTopSprung`, `flash`) | bleibt; dieselben DOM-Kennungen (`topDomId`) an den neuen Karten, der Kurs springt dorthin |
| `BeschlussVorschau` auf breiten Schirmen | s. 3.7 |
| `AbrufFehler`, `notFound()`, „Für diese Sitzung liegt noch keine Tagesordnung vor“ | unverändert; ohne Tagesordnung gibt es keinen Kurs |
| Einladung zum Konto am Fuß | Sache der `PublicShell`, nicht der Seite |

**3.7 Rechte Spalte.** Der Entwurf stellt rechts „Ort und Zeit“, „Quellen“ und
„Wie es weitergeht“ neben die Liste. Auf breiten Schirmen steht dort heute die
`BeschlussVorschau`. **Entschieden:** Die rechte Spalte des Entwurfs gilt bis
zur Breite, ab der `useWeit` greift. Darüber, und nur wenn es Beschlüsse gibt,
hat die `BeschlussVorschau` Vorrang und die drei Karten rücken unter die Liste.
„Ort und Zeit“ wiederholt den Kopf nicht wörtlich: Die Karte trägt die volle
Adresse, die im Kicker fehlt.

**3.8 Live.** Im Entwurf steht: „Ratslotse weiß nicht, wo die Sitzung gerade
ist.“ Das stimmt für Ausschüsse. Für den Rat gibt es `live_state`.
**Entschieden:** Mitlesen folgt im Rat der Übertragung und sagt das dazu; in
Ausschüssen klickt man selbst. Einzelheiten in 4.5.

**3.9 Punkt-Seite und Beschluss-Seite.** Nach dem Protokoll hat ein Punkt
einen Beschluss mit eigener Seite (`/council/decision`). **Entschieden:** Die
Punkt-Seite gibt es für Punkte ohne Protokoll-Beschluss. Hat der Punkt einen,
führt jeder Verweis zur Beschluss-Seite; ein alter Link auf die Punkt-Seite
zeigt oben einen Hinweis mit Link dorthin, statt umzuleiten (der Inhalt bleibt
lesbar, niemand landet woanders als erwartet). So entstehen nicht zwei Seiten,
die dasselbe verschieden erzählen.

**3.10 Kontext für „Frag den Rat“.** Der Entwurf nimmt an, dass `/ask` keinen
Kontext kennt. Es gibt `screen`. **Entschieden:** Die Punkt-Seite schickt
`screen` mit `route`, `heading` (Titel des Punkts), bei „Dazu fragen“
zusätzlich `element_title` und `element_text` des Bausteins, dazu
`refs.ksinr`. `ExplainRefs` bekommt ein optionales `item_number`
(`str | None`, max. 20 Zeichen), damit der Punkt eindeutig ist. Optional und
am Ende, weil die ausgelieferte App das Feld nicht schickt.

**3.11 Paraphrasen.** § 1: „Paraphrasen kursiv ohne Anführungszeichen“. Der
Entwurf setzt sie gerade. **Entschieden:** kursiv. Wörtliche Zitate aus
Vorlagen, die der Entwurf noch in Anführungszeichen zeigt, werden zu
Paraphrasen.

**3.12 Presse.** Der Entwurf zeigt einen einzelnen NWZ-Artikel mit Titel und
Seite. Der Bestand verlinkt nur die NWZonline-Suche zum Thema
(`components/nwz-link.tsx`). **Entschieden:** Die Punkt-Seite nutzt
`nwz-link.tsx`. Einzelne Artikel sind nicht Teil dieses Plans.

**3.13 Zählung der Ergebnisse.** Die Zeile „7 Angenommen · 4 Zur Kenntnis · …“
zählt Ergebnisse von Punkten. Das ist keine Stimm- oder Abstimmungsgrafik
(§ 8) und bleibt Text mit Punkt in der Ergebnisfarbe, kein Balken.

**3.14 Zwei Listen.** `AgendaRow` trägt Sitzungsliste und Sitzungsseite.
**Entschieden:** Die neue Seite bekommt eigene Karten-Komponenten
(`components/sitzung/…`). Alles, was rechnet (`ergebnisseJeTop`, `topKey`,
`videoKey`, `topDomId`, `kurzfassung`), wird weiter aus `tagesordnung.tsx`
importiert, nicht kopiert. Die Sitzungsliste bleibt bei `AgendaRow`.

**3.15 Adressen.** Das Web wird auch statisch exportiert; Seiten lesen ihre
Kennung aus der Query, nicht aus dem Pfad. **Entschieden:**
`/council/punkt?ksinr=…&top=…` und `/council/sitzung/mitlesen?ksinr=…`, `top`
im selben Format wie heute beim geteilten Punkt. Beide in
`OEFFENTLICHE_PFADE` (`lib/public-routes.ts`, Test daneben), Hilfsfunktionen in
`lib/routes.ts`, `generateMetadata` nach dem Muster von `sitzung/page.tsx`
(erst `istExport()`, dann `searchParams`).

**3.16 „Zusagen der Verwaltung“.** Die Karte im Entwurf ist aus Protokollen
von Hand zusammengetragen. Eine Quelle dafür gibt es nicht. **Entschieden:**
nicht bauen. Der Platz bleibt leer, bis die Akte Protokollnotizen als
Stationen liefert.

**3.17 Mitschrieb.** Im Mitlesen kann man je Punkt festhalten, was passiert
ist. Tim hat das noch nicht bestätigt. **Offen (8.3).** Bis dahin gehört es
nicht in Schritt 5.

**3.18 iOS.** Die App aus dem Store decodiert `SessionDetail`. Ein
umbenanntes oder entferntes Feld bricht sie. **Entschieden:** nur zusätzliche,
optionale Felder; vor jedem Backend-PR `python3 scripts/ios_vertrag.py
--ausgeliefert`.

## 4. Zielbild

### 4.1 Baustein „Kurs der Sitzung“

Eine Linie vom Anker (Beginn) bis zum Schloss (nichtöffentlich). Jede Boje ist
ein Punkt, jedes helle Band eine Etappe. Die lauffähige Rechnung steht in
`quellen/Kurs.dc.html`, Methode `rechne()`; Anhang C gibt sie als Regel wieder.

**Eingabe.** `start` („17:00“), Liste der Etappen. Je Etappe `name`, `mittel`
(optional), `kurz`, `gesperrt`, bei gesperrt `nr` („N 13–15“) und `anzahl`,
sonst `punkte`. Je Punkt `nr`, `titel`, `kurz`, `piktogramm`, `wichtig`,
`vertagt`, `ergebnis`, `vorlaeufig`, `href`. Dazu `aktiv` (Nummer oder leer),
`onWaehle` (optional) und `dichte` (`auto`, `komfortabel`, `kompakt`).

**Zellen.** Eine Zelle für den Start, dann je Etappe ihre Punkte oder eine
Schloss-Zelle. Eine Etappe mit nur einer Zelle bekommt eine Leerzelle dazu,
damit ihr Name Platz hat (bei der letzten Etappe davor, sonst dahinter).

**Zeilen.** Kein seitliches Scrollen. Gemessen wird die Breite des Bausteins
(`ResizeObserver`), nicht die des Fensters.

1. Nutzbar = Breite − 36 px (je 18 px Rand), mindestens 120.
2. Spalten = ⌊nutzbar ÷ 60⌋, mindestens 3.
3. Bräuchte das mehr als zwei Zeilen, gilt **kompakt**: Spalten = ⌊nutzbar ÷ 30⌋.
4. Zeilen = ⌈Zellen ÷ Spalten⌉, danach Spalten = ⌈Zellen ÷ Zeilen⌉, damit die
   Zeilen gleich lang werden.
5. Jede zweite Zeile läuft von rechts nach links (`flex-direction:
   row-reverse`). **Im DOM bleibt die Reihenfolge 1, 2, 3**, damit Tab-Folge
   und Vorlesen stimmen.
6. Die Kehre sitzt im Rand neben dem Zeilenende: 18 px breit, 2 px Linie,
   Radius 14, von der Linienhöhe der einen Zeile zur nächsten.

**Maße.**

| | komfortabel | kompakt |
|---|---|---|
| Zeilenhöhe | 20 Kopf + 44 Knoten + 22 Fuß (40 mit Kurztitel) | 18 + 30 + 18 |
| Abstand der Zeilen | 8 | 8 |
| Boje | 30 px Kreis, Piktogramm 15 | Punkt 10 px mit 2 px Ring, kein Link |
| Wichtige Boje | 40 px gefüllt, Piktogramm 18, Schein 4 px | 26 px, Piktogramm 14, Schein 3 px |
| Trefferfläche | 44 × 44 um jede Boje | nur wichtige und die aktive |
| Nummer unter der Boje | immer, mit „Ö“ | ohne „Ö“; nur am Etappenanfang, an wichtigen, an der aktiven, am Schloss |
| Kurztitel unter der Nummer | nur einzeilig und ab 104 px Zellenbreite | nie |
| Etappenname | voller Name mit Anzahl, sonst Name, sonst `mittel`, sonst `kurz` (je nachdem, was in Zellen × Breite passt) | `kurz` |

Passt alles in eine Zeile, ist sie höchstens Spalten × 150 + 36 px breit.

**Zustände.**

| Zustand | Darstellung |
|---|---|
| vor der Sitzung | Boje weiß mit feinem Rand; wichtig groß und primär gefüllt |
| schon einmal vertagt | gelber Punkt (11 px) oben rechts an der Boje. Im Entwurf nur an wichtigen Bojen gezeichnet; gemeint ist jede |
| nach der Sitzung | Ring in der Ergebnisfarbe; wichtige Boje in der dunklen Ergebnisfarbe gefüllt |
| vorläufig (Video) | wie Ergebnis, Ring gestrichelt |
| aktiv (Mitlesen) | Umrandung 3 px Signal mit 2 px Abstand; Linie bis dorthin voll primär; frühere Bojen 55 % Deckkraft; Nummer fett |
| nichtöffentlich | eine Schloss-Boje mit gestricheltem Rand, davor gestrichelte Linie, darunter „N 13–15“ |

Die Deckkraft der früheren Bojen ist die eine Stelle, an der gedimmt wird. Sie
trifft Zeichen, keinen Text, den jemand lesen muss (§ 3 „Weniger wichtig heißt
nicht schlechter lesbar“); die Nummern darunter bleiben deckend.

**Bedienung.** Ohne `onWaehle` ist jede Boje ein Link zur Karte des Punkts
(`#…` mit `topDomId`). Mit `onWaehle` ruft sie den Rückruf mit der Nummer.
`title` und `aria-label` tragen Nummer, Titel und, wenn bekannt, das Ergebnis
in Worten. Der Baustein hat eine Beschriftung („Kurs der Sitzung, 17 Punkte in
5 Etappen“); die aktive Boje trägt `aria-current="step"`.

**Wo der Code hingehört.** Die Rechnung nach `web/frontend/lib/kurs.ts` mit
`lib/kurs.test.ts`: reine Funktion von (Etappen, Breite, Dichte, aktiv) auf
Zeilen und Zellen. Die Komponente `components/sitzung/kurs.tsx` misst und
zeichnet nur. Testfälle aus dem Entwurf (Zellen samt Start und Leerzellen):

| Datensatz | Zellen | Breite | Ergebnis |
|---|---:|---:|---|
| `wenig` | 9 | 1.174 | eine Zeile, komfortabel, mit Kurztitel |
| `normal` | 16 | 1.176 | eine Zeile, komfortabel, ohne Kurztitel |
| `nach` | 21 | 1.176 | zwei Zeilen zu 11 Spalten, komfortabel |
| `viel` | 29 | 1.174 | zwei Zeilen zu 15 Spalten, komfortabel |
| `wenig` | 9 | 320 | eine Zeile, kompakt |
| `normal` | 16 | 320 | zwei Zeilen zu 8 Spalten, kompakt |
| `viel` | 29 | 320 | vier Zeilen zu 8 Spalten, kompakt |

### 4.2 Sitzungsseite vor der Sitzung

Bild: `vor-der-sitzung-desktop-1…3.png`. Von oben nach unten:

1. **Tafel.** Kicker in Mono (nah am Termin „Morgen“ oder „Heute“, sonst der
   Wochentag; Datum, Uhrzeit, Ort), Kurzname als `h1`, Aktionen (3.6),
   darunter der Satz zur Sitzung (3.1).
2. **Kurs der Sitzung** in der Tafel, rechts im Kicker „17 öffentlich · 5
   nichtöffentlich“, darunter ein Satz Legende.
3. **Wichtig in dieser Sitzung**, noch in der Tafel: bis zu drei Karten, je
   Piktogramm, Nummer, Art, ein Satz, eine Zeile Grund, „Zum Punkt“. Rechts im
   Kicker „3 von 9“ (gezeigte von inhaltlichen Punkten). Auf dem Handy seitlich
   zu wischen, mit den Blätter-Regeln aus § 6.
4. **Tagesordnung.** Links eine senkrechte Linie mit denselben Zeichen wie im
   Kurs, rechts die Karten.
   - „Leinen los · Beginn 17:00 Uhr“ als Kopfzeile der Linie.
   - Je Etappe ein Band: Kicker „Etappe 2 von 5“, Name in Bricolage 18, rechts
     Bereich und Anzahl („Ö 5 – Ö 10 · 6 Punkte“).
   - Formalien als eine aufklappbare Karte („5 Punkte zeigen“).
   - Je Punkt eine Karte: links die Nummer groß (Bricolage 26, „Ö“ in Muted,
     Zahl in Text, 78 px Spalte), rechts Art, Vorlage, Titel, Kurzfassung,
     Kenn-Chips („Kosten etwa 15.000 Euro“, „Vorgeschichte 3 Stationen“,
     „Unterlagen 5 Pläne“), Pfeil rechts. Die ganze Karte ist der Link zur
     Punkt-Seite.
   - Wichtige Punkte: Rand primär/45, Ring, Nummer primär, dazu „Wichtig:“ mit
     Grund; auf der Linie die große Boje.
   - Gleichartige Formalakte hintereinander (im Beispiel drei Widmungen)
     teilen sich eine Karte mit einer Erklärzeile und schlanken Zeilen. Die
     Regel dafür ist `formalakt_deckel` aus `council/impact.py`: was dort als
     Formalakt gilt und direkt aufeinander folgt, wird zusammengelegt.
   - Unter 480 px Kartenbreite rutscht die Nummer über den Text. Lange Wörter
     trennen (`hyphens: auto`, `hyphenate-limit-chars: 14 5 5`,
     `overflow-wrap: anywhere`).
   - Nichtöffentlich: gestrichelte Karte mit Bereich und Anzahl und dem Satz
     „Das Ratsinfo sperrt hier auch die Überschriften. Mehr als die Zahl der
     Punkte ist nicht öffentlich.“
5. **Rechts** (3.7): „Ort und Zeit“, „Wie es weitergeht“ (Sitzung, Protokoll
   „kommt meist erst einige Wochen später“, Ergebnisse), „Quellen“.

### 4.3 Sitzungsseite nach der Sitzung

Bild: `nach-der-sitzung-desktop-1…4.png`. Derselbe Aufbau, mit diesen
Unterschieden:

- Kurs und Linie tragen die Ergebnisfarben. Unter dem Kurs steht die Zählung
  als Legende („7 Angenommen · 4 Zur Kenntnis · 1 Vertagt · 1 Erledigt · 1 Kein
  Beschluss“) und ein Satz, wie viele Punkte ein Ergebnis hatten.
- Jede Karte beginnt mit Ergebnis und Abstimmung („Angenommen · einstimmig“).
- Wichtige Punkte sind ausgeklappt: Kurzfassung, „Der Weg dieser Vorlage“
  (Stationen als Chips, die aktuelle hervorgehoben), „Zum Beschluss“.
- Vertagte Punkte zeigen „Wie es weitergeht“, wenn der Punkt auf einer
  späteren Tagesordnung steht, mit Link zu dieser Sitzung.
- Anträge zeigen, wer sie gestellt hat (Fraktion mit Parteipunkt, sonst Name
  und Rolle), und verlinken „Zum Beschluss“ und den Antrag im Ratsinfo.

**Dazwischen** liegt ein Zustand, den der Entwurf nicht zeichnet: Die Sitzung
ist vorbei, das Protokoll fehlt. Dann gilt der Aufbau „vor der Sitzung“ mit
dem Satz „Die Sitzung war am …. Ergebnisse stehen hier, sobald das Protokoll
vorliegt.“ Gibt es Video-Ergebnisse, erscheinen sie an Kurs und Karten in der
vorläufigen Form (4.1), mit `VideoResultsNotice` darüber.

| Zustand | Bedingung | Ansicht |
|---|---|---|
| vorher | `session_date` heute oder später, nicht live | 4.2 |
| läuft | `isLiveNow(data)` | 4.2, dazu `LiveChip` und „Mitlesen“ als Primäraktion |
| vorbei, ohne Protokoll | Datum vergangen, `has_protocol` falsch | 4.2 mit dem Satz oben, Video-Ergebnisse vorläufig |
| vorbei, mit Protokoll | `has_protocol` wahr | 4.3 |

### 4.4 Punkt-Seite

Bild: `punkt-desktop-1…2.png`.

- Zurück zur Sitzung, Kicker (Nummer, Art, Vorlage, „Morgen im
  Verkehrsausschuss“), Titel, Chips (Politikfeld, „Im Rat seit 2018 · 5
  Sitzungen“), rechts Merken, Drucken, Teilen als stille Icons.
- „Das Wichtigste in Kürze“: Kurzfassung in `text-lese`, darunter der feste
  Hinweis „Automatische Kurzfassung. Verbindlich sind die Unterlagen im
  Ratsinfo.“ Form und Figur nach 3.1.
- Reiter mit Anzahl: **Argumente**, **Fraktionen**, **Vorgeschichte**,
  **Unterlagen**. Ein Reiter ohne Inhalt erscheint nicht. Gibt es nur einen,
  entfallen die Reiter.
- **Vorgeschichte:** Stationen mit Datum, Gremium, Ergebnis, Titel, einem Satz
  und Link zum Beschluss; die anstehende Sitzung als letzte Station.
- **Unterlagen:** Vorlage, Anträge, Protokolle, extern markiert.
- **Argumente** (Schritt 6): „Worüber gestritten wird“ mit Zählung („7 dafür ·
  9 dagegen oder mit Bedenken“), darunter Streitpunkte als Karten mit Frage,
  zwei Spalten „Dafür“ und „Dagegen“, je Aussage Urheber und Fundstelle, am
  Fuß „Dazu fragen“. Danach „Weitere Argumente“. Feste Hinweise: „Ratslotse
  ergänzt keine eigenen Argumente.“ und „Argumente sind Aussagen der
  Beteiligten, keine geprüften Tatsachen.“
- **Fraktionen** (Schritt 6): je Fraktion ihre Wortmeldungen als Paraphrasen
  mit Person, Gremium und Datum. Fester Hinweis: „Paraphrasen, keine
  wörtlichen Zitate. Eine einzelne Wortmeldung ist nicht immer die Linie der
  ganzen Fraktion.“ Abstimmungen nur als Satz aus dem Protokoll.
- **Rechts: „Frag den Rat · zu diesem Punkt“.** Dieselbe Oberfläche wie das
  Ratsgespräch (Nutzer-Bubble rechts, nummerierte Quellen, Fußzeile,
  „Gründlich recherchieren“), mit `screen` nach 3.10. Kopfzeile „An Bord · 6
  Unterlagen“ nennt, was zum Punkt vorliegt. Startzustand mit bis zu vier
  Vorschlägen. „Dazu fragen“ an einem Streitpunkt setzt einen Bezug-Chip über
  die Frage und hebt die Karte hervor. `council-qa.tsx` hat 3.735 Zeilen:
  nichts kopieren, sondern den Turn-Aufbau wiederverwenden; wenn er sich nicht
  herauslösen lässt, ist das Herauslösen ein eigener PR vor Schritt 4.
- „Auf einen Blick“ (Art, Vorlage, Antragsteller, Kosten, nächster Schritt)
  und, mit Schritt 7, „Meine Notiz“.

### 4.5 Mitlesen

Bild: `mitlesen-desktop-1…2.png`, `mitlesen-handy.png`, Zustandsbilder.

- Tafel: Kicker „Heute · …“, Titel mit Marke „Mitlesen“, rechts „Ganze
  Tagesordnung“ zurück zur Sitzungsseite.
- Kurs mit `aktiv` und `onWaehle`, rechts im Kicker „Etappe 2 von 5 ·
  Beschlüsse und Berichte“ und „Boje 7 von 13“ (Formalien und der
  nichtöffentliche Teil zählen je als eine).
- Darunter „Zurück“ (52 × 52, nur Pfeil, `aria-label` „Zurück zu Ö 8 ·
  Kreyenstraße“) und „Weiter“ mit dem Ziel als zweiter Zeile. Am Anfang fehlt
  „Zurück“, am Ende „Weiter“.
- Karte „Jetzt dran“: Nummer groß (Bricolage 40), Art, „Wichtig:“ mit Grund,
  Vorlage, Titel, Antragsteller, Kurzfassung, Kenn-Chips, dann die Abschnitte
  der Punkt-Seite untereinander (ohne Reiter), ein Link „Eigene Seite zu
  diesem Punkt“, am Fuß noch einmal Zurück und Weiter.
- Rechts: „Frag den Rat zu Ö 9“ (zwei Vorschläge, Eingabe), „Als Nächstes“
  (die nächsten drei, antippbar), Link zur Sitzung im Ratsinfo. „Mein
  Mitschrieb“ nur nach 8.3.
- Letzter Schritt „Nichtöffentlicher Teil“: Erklärung, kein „Weiter“.

**Woher der aktive Punkt kommt.**

| Sitzung | Verhalten | Satz auf der Seite |
|---|---|---|
| Ausschuss (keine Übertragung) | man klickt selbst | „Ratslotse weiß nicht, wo die Sitzung gerade ist. Du gibst den Takt vor.“ |
| Rat, `live_state` frisch (`liveStateFresh`) | die Seite folgt der Übertragung, neu geladen im Takt `LIVE_REFRESH_MS` | „Folgt der Übertragung, Stand vor N Min.“ (`liveAgoText`) |
| Rat, man blättert selbst weg | Folgen pausiert; ein Knopf „Zur Übertragung: Ö 9“ holt zurück | wie oben, dazu der Knopf |
| Rat, Stand veraltet oder `finished` | wie Ausschuss bzw. „Die Sitzung ist vorbei.“ | – |

Meldet `live_state` einen Block (`block_start`), gilt der letzte Punkt des
Blocks als aktiv; die Zuordnung zu den Zellen macht `liveItemKeys`. Die
Formalien-Boje ist aktiv, sobald einer ihrer Punkte läuft.

**Speichern.** Aktiver Punkt und „folgt“ je Sitzung im `localStorage`
(Schlüssel mit ksinr), ohne Konto. Für Tests `lib/__testhilfen/speicher.ts`,
auch den gesperrten Fall.

**Handy.** In der kompakten Ansicht sind die kleinen Punkte nicht antippbar;
dort führen „Weiter“, „Zurück“ und „Als Nächstes“. Die Leiste mit Zurück und
Weiter klebt am unteren Rand (`position: sticky`). Beim Wechsel scrollt die
Seite an den Anfang der Karte und setzt den Fokus auf ihren Titel; bei
`prefers-reduced-motion` ohne Gleiten.

### 4.6 Feste Texte

Aus dem Entwurf übernehmen, wo nicht anders vermerkt. Du-Form, kurze Sätze,
kein Emoji (`DESIGNSPRACHE.md` § 1 und § 8).

| Ort | Text |
|---|---|
| Legende vorher | Jede Boje ist ein Punkt der Tagesordnung, jedes helle Band eine Etappe der Sitzung. Die großen Bojen sind die wichtigen. Der gelbe Punkt heißt: stand schon einmal hier und wurde vertagt. |
| Legende nachher | Die Farbe der Boje zeigt das Ergebnis; 14 von 20 öffentlichen Punkten hatten eines. |
| Hinweis Liste vorher | Kurzfassungen sind automatisch aus Vorlagen und Anträgen erstellt. Verbindlich sind die Unterlagen im Ratsinfo. |
| Hinweis Liste nachher | Kurzfassungen sind automatisch erstellt. Verbindlich ist das Protokoll. |
| Kopf der Linie | Leinen los · Beginn 17:00 Uhr |
| Etappen-Namen | Zum Start · Beschlüsse und Berichte · Anträge · Zum Schluss · Nichtöffentlicher Teil |
| Etappen kurz | Start · Beschlüsse · Anträge · Schluss |
| Formalien | Formalien · 5 Punkte zeigen |
| Anfragen | Fragen der Mitglieder an die Verwaltung. Ein Beschluss kommt dabei nicht heraus. |
| Einwohnerfragen | Hier können Einwohner*innen dem Ausschuss Fragen stellen. |
| Widmung | Mit einer Widmung wird eine Straße oder ein Weg offiziell zur öffentlichen Straße. |
| Nichtöffentlich, Erklärung | Nichtöffentlich berät ein Ausschuss, wenn das öffentliche Wohl oder berechtigte Interessen Einzelner es verlangen, zum Beispiel bei Grundstücken, Personal oder Verträgen. |
| Mitlesen, Knöpfe | Zurück · Weiter · Ganze Tagesordnung · Als Nächstes · Jetzt dran |
| Fußzeile im Gespräch | wie im Ratsgespräch, mit „zu diesem Punkt“ |

Zahlen in diesen Sätzen werden gerechnet. Ergibt eine Zählung null, entfällt
der Satzteil.

### 4.7 Daten: was es gibt und was fehlt

| Angabe | Für | Quelle heute | Zu tun |
|---|---|---|---|
| Nummer, Titel, Vorlage, öffentlich, Anlagen | alles | `agenda_items` | – |
| Kurztitel | Kurs, Mitlesen | `_titel_zerlegen` → `titel_kurz` | an die Sitzungsantwort reichen |
| Antragsteller | Karten | `_titel_zerlegen` → `applicants`, `group_applicants` | reichen |
| Art (Entscheidung, Bericht, Antrag …) | Karten | `behandlung`, `kind` aus der Beratungsfolge | reichen; Wortlaut für die Anzeige festlegen |
| Kurzfassung | Karten, Punkt | `social_text`, sonst `summary` | Reihenfolge wie im Store |
| Etappen | Kurs, Liste | `_ueberschriften`, `_eltern_nummer` | neue Funktion (Schritt 1) |
| Piktogramm | Kurs, Linie, Karten | – | neu (Schritt 1, Anhang A) |
| wichtig, Grund | Kurs, Karten | vorher: `sitzungs_highlights` / `agenda_wichtigkeit`; nachher: Wichtigkeit der Beschlüsse (`ImportanceBreakdown`) | reichen; dieselbe Auswahl wie die Sitzungsliste |
| schon vertagt (Zahl) | gelber Punkt | – | neu; Quelle messen (Schritt 1) |
| Ergebnis, Abstimmung | nachher | `decisions`, `ergebnisseJeTop` | – |
| vorläufiges Ergebnis | nachher | `video_results` | – |
| Weg der Vorlage | nachher, Punkt | Beratungsfolge (im Web `VorlageStop`) | wiederverwenden |
| Satz zur Sitzung | Kopf | vorher evtl. `committee_summaries`; nachher – | prüfen bzw. aus Zählungen bauen (Schritt 3) |
| Nächste Sitzung des Gremiums | rechts | `naechste_sitzung_je_gremium` | reichen |
| Vorgeschichte über Jahre | Punkt | `akte_von`, `agenda_since_decisions` | neuer Endpunkt (Schritt 4) |
| Kosten als Chip | Karten, Punkt | – | nur zeigen, wenn eine Quelle sie strukturiert liefert; sonst weglassen |
| „Was beantragt wird“, „Was die Verwaltung sagt“ | Punkt, Mitlesen | – | neu, mit Messung (Schritt 6) |
| Argumente, Streitpunkte, Fraktionen | Punkt | Rohstoff: `council_speeches`, Vorlagen, Anträge | neu, mit Messung (Schritt 6) |
| Zusagen der Verwaltung | – | – | nicht bauen (3.16) |
| Notiz, Mitschrieb | Punkt, Mitlesen | – | Schritt 7 |

## 5. Umsetzung in Schritten

### Schritt 0: einchecken

Zweig von `dev`. `docs/plan-sitzungsseite-kurs.md` und
`docs/entwurf-sitzungsseite/` aus dem Haupt-Checkout übernehmen und einchecken.
Kein Changelog-Fragment nötig, wenn `pruefe.py` für reine Doku keines verlangt;
sonst eine Zeile. Im selben PR nichts anderes.

### Schritt 1: Daten

**Ziel:** `/council/session/{ksinr}` liefert alles für Kurs und Karten.

1. **Form.** In `antworten.py` ein neuer Block an `SessionDetail`:
   `kurs: NotRequired[SessionKurs]` mit `start`, `etappen` (je `name`,
   `mittel`, `kurz`, `gesperrt`, `nr`, `anzahl`, `punkte` als Liste von
   Nummern) und `punkte` (je Nummer `titel_kurz`, `art`, `piktogramm`,
   `wichtig`, `wichtig_grund`, `vertagt`, `formalie`). Ein eigener Block statt
   neuer Felder an `AgendaItemRow`, weil dieselbe Zeile die Merkliste bedient
   und dort nichts davon gebraucht wird. `NotRequired`, weil die App im Store
   das Feld nicht kennt.
2. **Etappen** als eine Funktion im Store neben `_ueberschriften`, mit Tests
   gegen echte Tagesordnungen (mindestens ksinr 4652, 4654, 4593, 4702):
   - „Zum Start“: Formalien (Beschlussfähigkeit, Tagesordnung, Protokolle samt
     Unterpunkten, als **eine** Zelle „Ö 1–3“), Mitteilungen,
     Einwohnerfragestunde: alles vor dem ersten inhaltlichen Punkt.
   - Ein Oberpunkt ohne Vorlage mit Unterpunkten eröffnet eine Etappe mit
     seinem Namen; die Unterpunkte sind die Zellen. Im Rat sind das die
     Abschnitte je Fachausschuss; für `kurz` und `mittel` `shortCommittee`
     bzw. eine kleine feste Tabelle.
   - Inhaltliche Punkte ohne Oberpunkt hintereinander: „Beschlüsse und
     Berichte“.
   - „Anfragen und Anregungen“ und Gleichartiges am Ende: „Zum Schluss“.
   - Alles Nichtöffentliche: eine gesperrte Etappe mit Bereich und der
     **gezählten** Anzahl (im Beispiel „N 17–20 · 5 Punkte“, weil es
     Unterpunkte gibt).
   - Dringliche Punkte: eigene Etappe „Dringlich“ nach „Zum Start“.
   - Eine Tagesordnung, auf die keine Regel passt, ergibt eine einzige Etappe
     „Tagesordnung“. Lieber schlicht als falsch gegliedert.
3. **Piktogramm.** Feste Liste (Anhang A). Erst Regeln über Titel, Art und
   Politikfeld, als reine Funktion mit Tabelle und Test. Dann messen: Anteil
   der letzten 300 öffentlichen inhaltlichen Punkte mit einem Treffer, der
   nicht der Rückfall ist. Liegt er unter 70 %, kommt der Schlüssel aus dem
   Lauf, der schon die Tragweite bewertet (`agenda_item_impact`): neue Spalte
   mit Migration (`council/store_schema.py`, `SCHEMA` **und** `_migrate`),
   Schlüssel im Prompt (`kern/prompts.py`) und im Parser. Das Modell wählt nur
   aus der Liste; alles andere wird verworfen. Rückfall immer nach Art.
4. **wichtig.** Vor der Sitzung dieselbe Auswahl wie `sitzungs_highlights`,
   mit höchstens drei je Sitzung; nach der Sitzung die drei wichtigsten
   Beschlüsse nach der bestehenden Wichtigkeit. Kein neues Maß: Derselbe Punkt
   darf in Liste und Seite nicht verschieden wichtig heißen. `wichtig_grund`
   wie geliefert; fehlt er, gibt es keine Zeile „Wichtig:“.
5. **vertagt.** Erst messen, welche Quelle trägt: frühere Beschlüsse mit
   Ergebnis „vertagt“ zur selben Vorlage, `agenda_since_decisions`, die Akte.
   Für Anträge ohne Vorlage gibt es womöglich keine sichere Zuordnung. Wo sie
   fehlt, steht `0`. Ein geratener gelber Punkt ist schlimmer als keiner.
6. Vertrag neu schneiden (`python scripts/openapi_schnitt.py`), Typen
   (`cd web/frontend && npm run api:typen`), `ios_vertrag.py --ausgeliefert`.

**Fängt:** `test_api_vertrag.py`, `test_ios_vertrag.py`,
`test_migration_bestand.py`, `test_schema_gegen_migration.py`.

**Umgesetzt (10.11.2026), mit diesen Abweichungen vom Text oben:**

- **Englische Namen.** Der Block heißt `course` (`SessionCourse` in
  `antworten.py`): `start`, `public_count`, `closed_count`,
  `substantive_count`, `stages` (je `kind`, `name`, `name_medium`,
  `name_short`, `subtitle`, `range`, `count`, `cells` mit `label`, `title`,
  `items`) und `items` je Nummer (`short_title`, `type`, `type_label`, `icon`,
  `applicant`, `important`, `important_reason`, `postponed`, `formality`,
  `formal_act`, `group`). Die Bojen (`cells`) und die Bereiche kommen fertig
  vom Server, damit die App die Formalien-Zelle und „Ö 5 – Ö 10" nicht
  nachbauen muss.
- **Nur Rubriken eröffnen eine Etappe** („Anträge …", die Ausschuss-Abschnitte
  im Rat). Eine Überschrift, die ein Vorhaben benennt („Bauleitplanung
  Meerweg"), bleibt in „Beschlüsse und Berichte"; ihre Punkte tragen `group`.
  Der Bauausschuss vom 27.08.2026 (ksinr 4607) hätte sonst elf Etappen mit je
  zwei Bojen bekommen.
- **Piktogramm ohne Modell** (81 %, s. Anhang A).
- **vertagt:** Zusatz „zurückgestellt/abgesetzt" im Titel eines früheren
  Punkts oder ein vertagter Beschluss, nur im selben Gremium; zugeordnet über
  die Vorlage, Anträge ohne Vorlage nur bei wörtlich gleichem, datiertem
  Titel. Gemessen: 23 von 664 Punkten seit Mai 2026. Die Akte ist nicht
  Quelle.
- **wichtig nach der Sitzung** mit derselben Schwelle wie vorher
  (`WICHTIG_MINDEST`).

### Schritt 2: Baustein Kurs

`lib/kurs.ts` mit Tests (Fälle in 4.1), `components/sitzung/kurs.tsx`,
Piktogramm-Zuordnung als Tabelle (Anhang A) in `lib/`. Noch nirgends
eingebunden. Bild an Tim: die vier Datensätze in beiden Themes, 320 px und
1.240 px.

**Umgesetzt (10.11.2026)** unter englischen Namen: `lib/course.ts` (Rechnung,
`courseInput` vom Vertrag zur Eingabe) mit `lib/course.test.ts`,
`lib/course-icons.ts` (Anhang A; `tests/test_course.py` hält ihn gegen Server
und Plan) und `components/session/course.tsx`. Die Ergebnisfarben der Bojen
stehen als `OUTCOME_RING_CLS`/`OUTCOME_FILL_CLS`/`OUTCOME_GLOW_CLS` neben
`OUTCOME_DOT_CLS` in `components/decision-ui.tsx`. Eine neutrale Boje trägt
den Rand `primary/35` statt `--border`: Auf der dunklen Tafel liegt `--border`
einen Punkt neben `--card`, die Boje verschwand im Band.

### Schritt 3: Sitzungsseite

Schalter `sitzung_kurs` (`kern/features.py`, `useFeature`). Aus: Seite wie
heute. An: neue Seite.

1. Zustand der Sitzung als reine Funktion in `lib/` mit Test (Tabelle in 4.3).
2. Kopf auf `.hh-tafel` mit Kurs, Aktionen und Satz.
3. „Wichtig in dieser Sitzung“.
4. Liste mit Linie, Etappen-Bändern und Karten; alles aus 3.6 an seinem Platz.
5. Rechte Spalte nach 3.7.
6. Satz zur Sitzung. Nachher aus Zählungen gebaut, ohne Modell: wie viele
   Beschlussvorlagen angenommen, welche wichtigen (mit `titel_kurz`), was
   vertagt. Vorher: prüfen, ob `committee_summaries` taugt (Ton, Länge, leer
   bei Routine). Wenn nicht: ein gerechneter Satz („17 öffentliche Punkte,
   darunter 3 Anträge. 2 standen schon einmal auf der Tagesordnung.“).
7. `DESIGNSPRACHE.md` § 4 und § 6 nachziehen (3.2, 3.3).

**Browsertests:** in `04-council.spec.ts` oder daneben: Seite lädt mit und
ohne Protokoll, Boje führt zur Karte, geteilter Punkt wird hervorgehoben, kein
seitliches Scrollen bei 320 px (`14-layout`), Lauf gegen die leere
Ratsdatenbank (`web/frontend/CLAUDE.md`). `17-lesbarkeit` beachten.

**Umgesetzt (10.11.2026):** Schalter `sitzung-kurs` (Bindestrich wie alle
Schalter), Seite in `components/session/session-page.tsx`, Rechnung in
`lib/session-page.ts` (Zustand, Kicker, Zählung, Formalakt-Gruppen; Tests
daneben), Browsertest `tests/e2e/28-sitzung-kurs.spec.ts` mit zwei echten
Antworten als Fixture. Das Backend liefert dazu am `course`-Block: den
gerechneten **Satz** (`summary`; `committee_summaries` taugt nicht, es ist
Mail-HTML), die **nächste Sitzung** des Gremiums (`next_session`) und je
Punkt den **Weg der Vorlage** mit Ergebnis je Station (`journey`) und, wo er
hier vertagt wurde, die **nächste Tagesordnung**, auf der er wieder steht
(`next_on_agenda`). Der Satz zählt nur, was das Protokoll sagt — dieselbe
Grundlage wie die Farben im Kurs. Nach dem Protokoll ersetzt die Kurzfassung
des Beschlusses den ankündigenden Kartentext („Der Ausschuss berät …").
Der geteilte Punkt bleibt `ring-primary` wie auf der alten Seite; Orange
gehört der aktiven Boje beim Mitlesen.

**Abnahme:** ksinr 4654 (vorher) und 4652 (nachher) sehen aus wie die Bilder,
abzüglich 3.1 bis 3.7; dazu eine Ratssitzung mit vielen Punkten (4702), eine
Sitzung ohne Tagesordnung, eine mit Video-Ergebnissen, eine mit dringlichem
Punkt. Hell und dunkel, 320, 390, 768, 1.360 und breit. Doppelte
Schriftgröße.

### Schritt 4: Punkt-Seite

Schalter `punkt_seite`. Solange er aus ist, führen die Karten wie heute zum
Beschluss oder klappen auf.

1. Endpunkt `GET /council/session/{ksinr}/item` mit `nr` als Query, öffentlich
   wie die Sitzung (in `tests/test_endpunkt_schutz.py` eintragen). Form
   `PunktDetail`: Felder des Punkts, `kurs`-Angaben, `vorgeschichte`
   (Stationen), `unterlagen`, `beschluss_id` (wenn es einen gibt, s. 3.9),
   Nachbarn für Zurück und Weiter.
2. Vorgeschichte: Beratungsfolge der Vorlage, frühere Beschlüsse, über die
   Akte verbundene Stationen; die anstehende Sitzung als letzte. Ohne Vorlage
   und ohne Akte: keine Vorgeschichte.
3. Seite `app/(app)/council/punkt/` (`page.tsx`, `view.tsx`, `loading.tsx`),
   Reiter Vorgeschichte und Unterlagen.
4. „Frag den Rat“ mit `screen` (3.10). Für Gäste: prüfen, was `/ask` heute
   ohne Konto tut, und dasselbe Verhalten zeigen wie an anderer Stelle.
5. Messen, ob der Kontext wirkt: zehn Fragen der Art „Und was kostet das?“ auf
   drei Punkt-Seiten, mit und ohne `refs.item_number`.

**Umgesetzt (10.11.2026):** Endpunkt `GET /council/session/{ksinr}/item?nr=`
(Form `SessionItemDetail`, öffentlich, nichtöffentliche Punkte 404), Seite
`app/(app)/council/punkt/`, Schalter `punkt-seite`, Link-Vorschau `punkt`
(Schlüssel `ksinr|Nummer`). Vorgeschichte: mit Vorlage ihr Weg durch die
Gremien, ohne Vorlage die früheren Auftritte desselben datierten Antrags im
selben Gremium — die Akte ist (noch) nicht Quelle. **„Frag den Rat“ ohne
Kopie von `council-qa.tsx`:** Die Box auf der Punkt-Seite reicht die Frage
mit `ksinr` und `top` an `/fragen` weiter; das Ratsgespräch schickt den Punkt
als `screen.refs` (`item_number` neu an `ExplainRefs`) und zeigt ihn als
abwählbaren Bezug-Chip über dem Eingabefeld. Der Server schlägt den Punkt
nach: Mit Beschluss ist der Beschluss der Gegenstand, ohne nennt
`qa.gegenstand_regel` den Punkt mit Sitzung und Vorlage. Ohne Konto führt die
Frage wie jeder Frage-Chip zur Anmeldung und danach zurück.

**Messung aus 5. (10.11.2026, `eval/run_punkt_bezug.py`):** Zehn Fragen ohne
Gegenstand im Wortlaut auf drei Punkt-Seiten (D-Ticket 4654 Ö 9 ohne
Beschluss, Junkerstraße 4650 Ö 10.3 vertagt, VBN-Tarif 4702 Ö 8.1 mit
Beschluss), je mit und ohne Bezug, über die echte `/ask`-Strecke. **Die
Kostenprobe deckte einen Fehler auf:** Auch MIT Bezug kam „Und was kostet
das?“ dreimal von drei als Rückfrage („kann ich nicht einordnen“,
`results/punkt_bezug/20261110-1740.json`) — die Frage-Analyse löst Rückbezüge
nur aus dem Gesprächsverlauf auf, und auf einer Punkt-Seite gibt es keinen.
Behoben: Der Gegenstand der Seite geht der Analyse als erste Runde voraus
(`qa.seiten_gegenstand`), und `qa.rueckfrage_noetig` fragt nicht zurück, wenn
die Seite einen Gegenstand hat. Danach (`20261110-1811.json`, 0,19 $):

| | beim Punkt |
|---|---:|
| mit Bezug (Wortprobe) | 27/30 |
| mit Bezug (von Hand) | 28/30 |
| ohne Bezug | 0/30 (27 Rückfragen, 3 Antworten zu fremden Themen) |

Die zwei Fehlgriffe von Hand: Beim VBN-Tarif antworten „Worum geht es dabei?“
und „Wer ist dafür?“ zum Prüfauftrag Sozialticket, der im selben Beschluss
steht, statt zur Tariferhöhung. Die drei fremden Antworten ohne Bezug kommen
über „in einfachen Worten“: Das gilt als Wunsch nach Vereinfachung und umgeht
die Rückfrage — mit Bezug ist das kein Problem mehr.

### Schritt 5: Mitlesen

Schalter `mitlesen`. Seite `app/(app)/council/sitzung/mitlesen/`. Inhalte je
Punkt aus dem Endpunkt von Schritt 4. Der Zustand (aktiv, folgt, Quelle) als
reine Funktion in `lib/mitlesen.ts` mit Tests für jede Zeile der Tabelle in
4.5, auch „16:29 gegen 16:30“. Einstieg: Knopf „Mitlesen“ im Kopf der
Sitzungsseite, als Primäraktion nur, solange die Sitzung läuft; am Tag der
Sitzung davor als Sekundäraktion, sonst gar nicht. Browsertest: Weiter und
Zurück, Boje wählen, Neuladen behält den Punkt.

**Umgesetzt (10.11.2026):** Schalter `mitlesen`, Seite
`app/(app)/council/sitzung/mitlesen/`, Rechnung in `lib/mitlesen.ts`
(Schritte = Bojen, Zustand nach der Tabelle in 4.5, Speichern je Sitzung im
`localStorage`; Tests für jede Zeile samt „16:29 gegen 16:30“ und gesperrtem
Speicher). Die Abschnitte der Punkt-Seite (Vorgeschichte, Unterlagen, „Frag
den Rat“) stehen dafür in `components/session/item-sections.tsx` und werden
auf beiden Seiten benutzt. Browsertest `30-mitlesen`. Im Rat lädt die Seite
den Stand alle `LIVE_REFRESH_MS` neu. „Mein Mitschrieb“ fehlt wie verabredet
(8.3).

### Schritt 6: Argumente und Fraktionen

Eigenes Vorhaben. Vor dem ersten Code ein kurzer Plan in `docs/` mit:
Rohstoff (`council_speeches`, Vorlagen, Anträge), Form der Ablage, Prompt in
`kern/prompts.py`, und vor allem der **Messung**: zwanzig Punkte von Hand
gelesen, je Argument geprüft, ob es in der Quelle steht, wem es gehört und ob
die Paraphrase stimmt. Regeln, die schon feststehen:

- Jede Aussage hat Urheber, Gremium oder Dokument, Datum und Fundstelle. Ohne
  Fundstelle keine Aussage.
- Keine eigenen Argumente, keine Gewichtung, keine Empfehlung.
- Fraktion nur, wenn das Protokoll sie nennt. Sonst „Fraktion im Protokoll
  nicht genannt“.
- Kein Stimmverhalten als Grafik; Abstimmungen nur als Satz aus dem Protokoll.
- Unter einer Mindestmenge (Vorschlag: zwei Seiten mit je zwei Aussagen)
  erscheint der Reiter nicht.

### Schritt 7: Notizen und Mitschrieb

Eigener Plan vor dem Bau. Was feststeht: Notizen werden auf dem Gerät
verschlüsselt, der Server speichert nur den verschlüsselten Text. Der
Schlüssel entsteht auf dem Gerät und wird mit einer eigenen Notiz-Passphrase
(und einem Wiederherstellungscode) verpackt; das Anmeldepasswort taugt dafür
nicht, weil es an den Server geht und Apple-Konten keines haben. Folgen, die
der Plan aussprechen muss: Wer Passphrase und Code verliert, verliert die
Notizen; der Server kann nicht in ihnen suchen; „Frag den Rat“ kennt sie nicht;
im Web liefert der Server den Code, der verschlüsselt, das Versprechen ist
dort schwächer als in der App.

## 6. Abnahme, für jeden UI-Schritt

- [ ] `python scripts/pruefe.py` grün
- [ ] Hell und dunkel, 320 / 390 / 768 / 1.360 / breit, doppelte Schriftgröße
- [ ] Kein seitliches Scrollen; lange Titel („Anschluss der oldenburgischen,
      verkehrsrechtlichen Ausnahmegenehmigung …“) brechen sauber
- [ ] Tastatur: Tab-Folge im Kurs 1, 2, 3; sichtbarer Fokus; 44 px
- [ ] Jede Zahl gerechnet, jede Quelle verlinkt, Externes gestrichelt
- [ ] Kein Literal aus dem Entwurf als Farbe im Code
- [ ] Nichts aus 3.6 fehlt
- [ ] `DESIGNSPRACHE.md` nachgezogen, wo der Schritt sie ändert
- [ ] Bild an Tim, Gegenlesen abgewartet

## 7. Was bewusst anders ist als im Entwurf

Wer Bild und Ergebnis vergleicht, findet diese Unterschiede. Sie sind gewollt:
Lotti-Sprechblasen (3.1), Orange dunkler (3.4), Merken im Kopf (3.6),
Vorschau statt rechter Spalte auf breiten Schirmen (3.7), Mitlesen folgt im Rat
der Übertragung (3.8), Paraphrasen kursiv (3.11), kein einzelner Presse-Link
(3.12), keine „Zusagen der Verwaltung“ (3.16), Mitschrieb erst nach Antwort
(3.17), gelber Punkt an jeder vertagten Boje (4.1), Kopf und Fuß aus der
`PublicShell`.

## 8. Offene Fragen an Tim

1. **Lotti im Kopf.** Soll Lotti die Sitzung in einer Sprechblase
   zusammenfassen dürfen? Das bräuchte eine Ausnahme in § 1 und § 8. Sonst
   bleibt der Satz ohne Figur (3.1).
2. **Rechte Spalte gegen Vorschau** auf breiten Schirmen: Vorrang für die
   `BeschlussVorschau` wie in 3.7 vorgeschlagen?
3. **Mitschrieb.** Bleibt die Idee, im Mitlesen selbst festzuhalten, was
   passiert ist? Wenn ja: erst mit Schritt 7 oder vorher nur im Browser
   gespeichert und unverschlüsselt?
4. ~~**Wie viele „wichtig“ je Sitzung?**~~ Entschieden 10.11.2026: höchstens
   drei (`KURS_WICHTIG_MAX`); die Sitzungsliste bleibt bei zwei.
5. **Punkt-Seite nach dem Protokoll.** Hinweis mit Link zur Beschluss-Seite
   wie in 3.9, oder sollen beide Seiten zusammenwachsen?

## Anhang A: Piktogramme

Lucide, Strich 2, eine Liste für Boje, Linie und Karte. Die Schlüssel sind
englisch (Tims Regel 30.08.2026: Bezeichner und Werte der API auf Englisch)
und stehen genau so in `council/course.py::ICONS`; `tests/test_course.py`
hält diese Tabelle und den Code gleich.

| Schlüssel | Lucide | Wofür |
|---|---|---|
| `formalities` | `list-checks` | Beschlussfähigkeit, Tagesordnung, Protokoll |
| `citizen_question` | `message-circle-question` | Einwohnerfragestunde |
| `inquiries` | `messages-square` | Anfragen und Anregungen |
| `announcement` | `megaphone` | Mitteilungen |
| `sign` | `signpost` | Widmung, Straßenname, Verkehrsführung |
| `bike` | `bike` | Radverkehr |
| `bus` | `bus` | Bus, VWG |
| `ticket` | `ticket` | Tarife, Tickets |
| `speed` | `gauge` | Geschwindigkeit, Messung |
| `route` | `route` | Straßennetz, Brücken, Bahnübergänge |
| `parking` | `square-parking` | Parken |
| `closure` | `ban` | Sperrung, Einziehung, Veränderungssperre |
| `building` | `building-2` | Bauvorhaben, Innenentwicklung |
| `housing` | `house` | Wohnen |
| `plan` | `map` | Bebauungsplan, Flächennutzungsplan |
| `greenery` | `leaf` | Bäume, Stadtgrün |
| `water` | `droplets` | Regen, Hitze, Entwässerung |
| `energy` | `wind` | Energie, Wind |
| `waste` | `trash-2` | Abfall |
| `money` | `euro` | Haushalt, Steuern, Gebühren |
| `environment` | `flask-conical` | Belastungen, Gutachten |
| `renovation` | `wrench` | Sanierung, Handwerk, Pflaster |
| `personnel` | `user-plus` | Besetzungen, Mitglieder |
| `statute` | `file-text` | Satzungen, Rückfall für Entscheidungen |
| `airfield` | `plane` | Fliegerhorst |
| `school` | `graduation-cap` | Schulen |
| `daycare` | `baby` | Kitas, Kindertagespflege |
| `sport` | `trophy` | Sport, Bäder |
| `culture` | `drama` | Kultur, Museen, Gedenken |
| `social` | `heart-handshake` | Soziales, Jugend, Teilhabe, Integration |
| `report` | `clipboard-list` | Rückfall für Berichte |
| `motion` | `file-pen` | Rückfall für Anträge |

Dazu fest: Anker (`anchor`) für den Beginn, Schloss (`lock`) für
nichtöffentlich. Die Liste darf wachsen, aber nur hier und in der Tabelle im
Code zugleich. Für die Etappen des Rats gibt es `committeeIcon`.

**Gemessen (Schritt 1, 10.11.2026):** Die Titel-Regeln treffen bei den letzten
300 öffentlichen inhaltlichen Punkten 81 % (Ziel ≥ 70 %), ein Modell-Schlüssel
war deshalb nicht nötig. Ohne Treffer greift nach der Sitzung das Politikfeld
des Beschlusses, sonst der Rückfall nach Art (`statute`, `report`, `motion`).

## Anhang B: Farben des Entwurfs und ihre Tokens

Die Namen der Klassen vor Gebrauch in `tailwind.config.ts` und
`app/globals.css` nachsehen.

| Im Entwurf | Bedeutung | Im Repo |
|---|---|---|
| `hsl(204, 45%, 97.5%)` | Seite | `bg-background` |
| `hsl(0, 0%, 100%)` | Karte | `bg-card` |
| `hsl(212, 55%, 11%)` | Text | `text-foreground` |
| `hsl(207, 18%, 38.5%)` | Sekundär | `text-muted-foreground`, nie mit `/60` |
| `hsl(208, 32%, 89%)`, `hsl(208, 30%, 85%)` | Rahmen, Eingabe | `border-border`, `border-input` |
| `hsl(206, 40%, 94%)`, `hsl(206, 42%, 94%)` | Tonfläche, Chip | `bg-muted`, `bg-secondary` |
| `hsl(205, 92%, 34%)` | Primär | `primary` |
| `hsl(19, 92%, 50%)` | Signal | `signal` (jetzt 42 %) |
| `hsl(205, 52%, 92%)`, `hsl(206, 38%, 82%)` | Tafel, ihr Rand | `.hh-tafel` |
| `hsla(0, 0%, 100%, 0.62)` / `0.3` | Etappen-Band, gesperrt | `--card` mit Deckkraft auf der Tafel |
| `#22c55e` `#3b82f6` `#f59e0b` `#ef4444`, Grau | Ergebnis-Ring | `OUTCOME_DOT_CLS` |
| `#15803d` `#1d4ed8` `#b45309` `#b91c1c` | wichtige Boje gefüllt | dunkle Stufe derselben Grammatik; Kontrast des weißen Zeichens messen |
| Bricolage Grotesque | Titel, Nummern | `font-display`, nie im Fließtext |
| Mono 11 px, Versalien, 0,07 em | Kicker | `font-mono text-meta uppercase tracking-[0.06em]` |
| 17 / 27 px | Kurzfassung | `text-lese` |
| 13–14 px Hinweise | Hinweise | `text-hinweis`, Metadaten `text-meta`, Quellentitel `text-quelle` |

## Anhang C: Die Rechnung des Kurses

```
zellen = [Start] + je Etappe (Punkte | [Schloss]), Etappen mit < 2 Zellen + Leerzelle
nutz    = max(120, breite − 36)
passen  = (min) => max(3, floor(nutz / min))
spalten = passen(60)
kompakt = dichte == "kompakt" || (dichte == "auto" && ceil(n / spalten) > 2)
wenn kompakt: spalten = passen(30)
zeilen  = max(1, ceil(n / spalten))
spalten = ceil(n / zeilen)
zellenBreite = nutz / spalten
mitKurztitel = !kompakt && zeilen == 1 && zellenBreite >= 104

Zeile r läuft rückwärts, wenn r ungerade ist (nur optisch).
Linie vor Zelle i:  keine (i == 0) | voll (aktiv gesetzt und i <= aktiv)
                    | gestrichelt (i > letzte öffentliche) | normal
Linie nach Zelle i: keine (i == n−1) | voll (i < aktiv)
                    | gestrichelt (i >= letzte öffentliche) | normal
Kehre am Zeilenende: Linie wie „nach“ der letzten Zelle der Zeile.

Etappenname steht am ersten Stück der Etappe, das in einer Zeile mindestens
zwei Zellen hat, sonst am ersten Stück. Platz = Zellen × zellenBreite − 20
(kompakt − 12). Ein Text passt, wenn Zeichen × 7,1 <= Platz.
```

Die letzte Schätzung (7,1 px je Zeichen) ist die des Entwurfs für Mono 10,5 px
in Versalien. Im Repo gegen die echte Schrift prüfen oder messen.
