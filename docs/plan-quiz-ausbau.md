# Umsetzungsplan: das Quiz ausbauen — Joker, Blitzrunde, Karte, Duell, Aktuelles

Stand: 23.09.2026, nachts. Vorausgegangen ist das Brainstorm vom selben Abend
und die ersten drei Schritte daraus:

| PR | Inhalt | Stand |
|---|---|---|
| [#1513](https://github.com/Schereo/Ratslotse/pull/1513) Q1 | Richter (`appeal`), Dubletten, Ratspolitik-Deckel, `sweep_quiz.py` | gemergt nach `dev` |
| [#1518](https://github.com/Schereo/Ratslotse/pull/1518) Q2 | „Angenommen oder abgelehnt?", „Wofür mehr?" (`format`) | wartet auf Tims Bild-OK |
| [#1519](https://github.com/Schereo/Ratslotse/pull/1519) Q3 | „X % der anderen lagen richtig", Stadtkarte | wartet auf Tims Bild-OK |

Dieser Plan nimmt **alle übrigen Punkte** des Brainstorms auf und legt sie in
eine Reihenfolge. Er ist wie seine Vorgänger geschrieben: je PR Dateien,
Schnittstelle, Tests, Fertig-Kriterium; jede Zahl gemessen am Abzug von dev
(23.09.2026), Anhang C nennt die Befehle.

Wer das umsetzt, liest vorher: Wurzel-`CLAUDE.md`, `council/CLAUDE.md`
(Schema **und** Migration), `web/backend/CLAUDE.md`, `web/frontend/CLAUDE.md`,
`DESIGNSPRACHE.md` (§2 Farben, §6 Interaktion, §7 Bewegung, §8 Anti-Patterns)
und die Docstrings von `council/quiz.py`, `council/quiz_formats.py`,
`web/backend/app/routers/quiz.py`, `components/quiz-play.tsx`.

## 0. Was Tim gesagt hat (23.09.2026)

> Viele der Fragen sind vielleicht ein bisschen langweilig. Das UI ist nicht
> so engaging. Vielleicht können wir noch mehrere verschiedene Fragen mit dazu
> nehmen. […] Schreibe nach der Umsetzung von PR 1 einen Plan für alle
> Schritte und setze diese danach um.

## 1. Gemessen — was wir haben und was nicht

| Frage | Befund | Folge |
|---|---|---|
| Wie viele Fragen haben einen Tipp (`hint`)? | 109 von 777 (14 %) | Ein „Tipp-Joker" wäre meist leer → **50:50** ist der Joker, der Tipp bleibt, wo er da ist |
| Gibt es Orte mit Koordinaten **und** Gewicht? | 413 verortete Orte, **56 mit ≥ 10 Beschlüssen**, 402 mit Geometrie (Linie/Fläche) | Das Pin-Quiz „Wo liegt das?" trägt, ohne Fotos |
| Fotos (Commons) an Fragen? | 28 | Foto nur als Beigabe, nie als Voraussetzung |
| Abstimmungen je Fraktion? | `council_decision_votes`: **1 Zeile** | „Wer stimmte dagegen?" geht **nicht** → Anhang A |
| `vote` knapp/einstimmig? | 3.147 einstimmig, 1.362 mehrheitlich; `no_votes` bei 1.929 | „Einstimmig oder nicht?" wäre zu 70 % „einstimmig" → Anhang A |
| Aktuelle Beschlüsse im Abzug? | letzte Sitzung **17.08.2026** (Sommerpause), 34 mit Gesprächswert ≥ 55 im Juni | „Diese Woche im Rat" wäre heute leer → **„Aus den letzten Sitzungen"** (die jüngsten N Sitzungstage, nicht 7 Tage) |
| Heim-Viertel der Konten? | `web_users` hat keins; „Mein Viertel" ist eine Seite, kein Kontofeld | Stadtteil-Rangliste „Eversten gegen Nadorst" hat keine Grundlage → Anhang A; stattdessen **Viertel-Wissen aller** (anonym, aggregiert) auf der Stadtkarte |
| Wahlergebnisse je Bezirk? | nur live vom Votemanager, die OB-Stichwahl ist am **27.09.2026** | Wahlfragen **erst nach der Stichwahl**, und nur zur Ratswahl (Parteien, keine Kandidierenden im Wahlkampf) → Q12 |
| Kann die ausgelieferte App neue `qtype`? | Sie kennt `mc` und `estimate`; alles andere rendert sie als Multiple Choice | Eine Reihenfolge-Frage (`order`) darf die App **nicht** bekommen → Filter über `X-Client` |

## 2. Die Reihenfolge — und warum

1. **Q4 Joker (50:50)** zuerst: klein, rein serverseitig bewertet, und macht
   jede bestehende Frage fairer.
2. **Q5 Tagesergebnis teilen**: der billigste Weg, dass jemand anderes vom
   Quiz erfährt.
3. **Q6 Blitzrunde**: nutzt die schnellen Zwei-Antwort-Formen aus Q2.
4. **Q7 „Wo liegt das?"**: die stärkste neue Spielform, deterministisch.
5. **Q8 Reihenfolge**: vier Haushaltsposten nach Größe sortieren — aus den
   Produkten von Q2, ohne Modell.
6. **Q9 Duell**: braucht die Runden-Mechanik, die dann steht.
7. **Q10 Aus den letzten Sitzungen**: LLM-Fragen zu den jüngsten Beschlüssen,
   mit dem Richter aus Q1.
8. **Q11 Viertel-Wissen aller** auf der Stadtkarte (setzt Q3 voraus).
9. **Q12 Wahlfragen zur Ratswahl** — gebaut jetzt, **sichtbar erst ab dem
   28.09.2026** (Tag nach der Stichwahl).

**Kein PR hängt an einem offenen.** Q4–Q10 und Q12 zweigen von `dev` ab; wo
sie `quiz-play.tsx` anfassen, kollidieren sie mit #1518/#1519 höchstens in
Nachbarzeilen — beim Rebase beide Seiten behalten. Q11 baut auf der Stadtkarte
auf und kommt deshalb als zweiter Commit in #1519 (noch offen), nicht als
gestapelter PR.

**Bilder vor dem Merge.** Jeder PR mit Oberfläche geht mit Screenshots an Tim
(Schreibtisch + Handy, echte Daten) und wird erst nach seinem OK gemergt.
Reine Backend-PRs merged `scripts/merge_wenn_gruen.py`.

## 3. Die Pull Requests

### Q4 — Joker: 50:50

**Backend** `web/backend/app/routers/quiz.py`
- `POST /api/quiz/joker` `{question_id}` → `{remove: [int, int]}` — zwei
  falsche Indizes, **deterministisch je Frage und Konto** (Seed aus beiden), damit
  ein zweiter Aufruf nicht zwei andere streicht. 400 bei `estimate` und bei
  Fragen mit weniger als vier Antworten.
- Die Runde merkt sich den Joker nicht im Client: `POST /answer` nimmt
  `joker: bool`; mit Joker gibt es **die Hälfte der Punkte (aufgerundet)**.
  Antwortform `QuizResult` unverändert, `QuizAnswerIn.joker` neu (Vorgabe
  `false`, die App schickt es nie).
- Ein Joker je Runde ist eine Anzeige-Regel (Web zählt), keine Sicherheits-
  frage: Mehr Joker kosten Punkte, nicht Wahrheit.

**Web** `components/quiz-play.tsx`: Knopf „50:50" neben „Tipp anzeigen",
einmal je Runde; gestrichene Antworten werden `opacity-40` und `disabled`,
nicht entfernt (die Liste springt sonst). Punktezeile: „Richtig! +1 (mit Joker)".

**Tests** `tests/test_backend_api.py`: gleiche Streichung beim zweiten Aufruf,
nie die richtige, halbe Punkte, 400 bei Schätzfragen.
**Fertig, wenn** ein Joker in der Runde sichtbar zwei falsche dimmt und die
Punkte halbiert.

### Q5 — Tagesergebnis teilen

**Backend**: `POST /api/quiz/daily/complete` nimmt zusätzlich
`results: list[bool]` (je Frage richtig/falsch, höchstens fünf) und liefert
`share_text` zurück:

```
Ratslotse-Quiz 23.09.
🟩🟥🟩🟩🟩  4 von 5
ratslotse.de/quiz
```

Der Text entsteht **im Backend** (eine Regel für Web und App). Die Emoji
stehen im **geteilten Text**, nicht im UI — §8 verbietet Emoji im UI-Text.

**Web**: Auf dem Ergebnis-Schirm der Tages-Challenge „Ergebnis teilen" —
`navigator.share` wo vorhanden, sonst in die Zwischenablage mit Toast. Das
Raster erscheint im UI als farbige Kästchen (Tints aus §2), nicht als Emoji.

**Tests**: Formtest für `share_text`; ohne `results` bleibt die alte Antwort.

### Q6 — Blitzrunde

60 Sekunden, so viele Fragen wie möglich. Zieht **nur schnelle Fragen**:
`format IN ('verdict','compare')` und leichte MC-Fragen mit kurzen Optionen.

**Backend**
- `GET /api/quiz/blitz-round?n=30` → `QuizRound` (bevorzugt reizvolle,
  gemischt; ohne Lösung).
- Tabelle `quiz_blitz` in `ratslotse.sqlite` (`owner_id`, `day`, `correct`,
  `answered`, `finished_at`) — **konto-gebunden: in die Löschliste**
  (`kern/store.py`, Paar `("quiz_blitz", "owner_id")`).
- `POST /api/quiz/blitz/complete` `{correct, answered}` → `{best, today_best}`.
  Die Einzelantworten laufen wie immer über `/answer` (Punkte, Statistik);
  der Abschluss bucht nur die Bestmarke. Plausibilität: `answered ≤ 40`,
  `correct ≤ answered`.

**Web**: Kachel „Blitzrunde" auf der Startseite. Eigener Spielschirm (Timer-
Leiste oben, schrumpft über `transform: scaleX`, keine animierte Breite, §7),
nach jeder Antwort **sofort** die nächste Frage (Feedback als 300-ms-Tönung
der Kachel), Combo-Zähler („3 in Folge") als reine Anzeige. Am Ende: richtige,
Bestmarke, „Nochmal".

**Tests**: Runde enthält nur schnelle Formen, Bestmarke steigt nur.

### Q7 — „Wo liegt das?"

Ein Ort mit Namen, man setzt einen Pin; Punkte nach Entfernung zur
**Geometrie** (auf der Linie/in der Fläche = 0 m).

**Backend**
- `council/quiz_pins.py`: Kandidaten aus `council_entities` (Art `place`,
  ≥ 10 Beschlüsse, Geometrie vorhanden) — gemessen **56**. Entfernung
  Punkt↔Linie/Polygon in Metern mit einer lokalen äquirektangulären
  Projektion (Oldenburg ist klein genug; kein shapely, das steht nicht in den
  Requirements).
- `GET /api/quiz/pin-round?n=5` → `{questions: [{slug, name, kind_label}]}`
- `POST /api/quiz/pin-answer` `{slug, lat, lon}` → `{distance_m, points,
  geojson, label}`. Punkte: ≤ 150 m → 3, ≤ 500 m → 2, ≤ 1.500 m → 1, sonst 0.
  Gebucht wie das Karten-Quiz (`question_id = 0`, `area_type = 'district'`,
  Ortsbereich über `geo.ortsbereich_for`), damit es auf die Stadtkarte zählt.

**Web** `components/quiz-pin-play.tsx`: Karte (Basiskarte über
`lib/basemap.ts`), ein Tipp setzt den Pin, „Hier ist es" löst auf: die
Geometrie erscheint, eine gestrichelte Linie verbindet Pin und nächsten Punkt,
Entfernung in Worten („380 m daneben"). Kachel „Wo liegt das?" auf der
Startseite.

**Tests** `tests/test_quiz_pins.py`: Punkt auf Linie = 0, bekannter Abstand
auf ±5 %, Punkt in Fläche = 0, Punktestufen.

### Q8 — Reihenfolge: vier Posten nach Größe

`qtype = 'order'`: vier Haushaltsprodukte aus `quiz_formats.PRODUCTS`, „Sortiere
von den höchsten zu den niedrigsten geplanten Ausgaben". Nur Vierer, in denen
benachbarte Posten mindestens 1,3-fach auseinanderliegen (sonst Münzwurf).

**Backend**
- `quiz_formats.order_questions(store)`: bis zu 12 Vierer, stabile Schlüssel,
  `options` = die vier Namen in gemischter Reihenfolge, Lösung als
  `answer_order` (neue Spalte? **nein** — `correct_index` bleibt 0,
  die Lösung steht im `chart`-JSON, das ohnehin die vier Beträge trägt).
- `POST /answer` nimmt `order: list[int]`; Punkte: alle vier richtig → 3,
  Kendall-Abstand 1 → 2, 2 → 1, sonst 0. „Richtig" = alle vier.
- **Die App bekommt keine `order`-Fragen**: `pick_quiz_questions` und
  `daily_quiz_questions` nehmen `formats` entgegen; der Router lässt `order`
  nur zu, wenn `X-Client` fehlt (Web). Test dafür.

**Web**: vier Karten, per Tipp nacheinander nummerieren (1–4), „Zurücksetzen";
kein Drag & Drop (auf dem Telefon unzuverlässig). Auflösung: die richtige
Reihenfolge mit Beträgen.

### Q9 — Duell

**Backend**
- Tabelle `quiz_duels` in `ratslotse.sqlite`: `code` (10 Zeichen, zufällig),
  `owner_id`, `question_ids` (JSON), `owner_correct`, `created_at` —
  **konto-gebunden: in die Löschliste.** Gegenspieler in `quiz_duel_players`
  (`code`, `owner_id`, `correct`, `finished_at`), ebenfalls in die Liste.
- `POST /api/quiz/duel` `{question_ids, correct}` → `{code}` (nach einer
  normalen Runde, höchstens 10 Fragen, alle aktiv).
- `GET /api/quiz/duel/{code}` → Runde (ohne Lösung) + `owner_name`
  (Anzeigename) + `owner_correct` + ob ich schon gespielt habe.
- `POST /api/quiz/duel/{code}/complete` `{correct}` → Vergleich.
- Ein Duell verfällt nach 14 Tagen (404).

**Web**: Nach einer Runde „Duell starten" → Link `ratslotse.de/quiz?duell=…`
teilen. Der Link öffnet die Runde; am Ende „Du 7 · Tim 6". Ohne Konto: die
Anmeldeseite mit Rücksprung (das Quiz braucht ein Konto).

### Q10 — Aus den letzten Sitzungen

Ein Gebiet `("topic", "aktuell")` mit Label „Aus den letzten Sitzungen":
LLM-Fragen (bestehende Pipeline samt Verify **und Richter**) zu den Beschlüssen
der **jüngsten fünf Sitzungstage** mit Gesprächswert ≥ 55.

- `scripts/generate_quiz.py`: zusätzliches Gebiet; Quelle = `council_facts`
  über die jüngsten Beschlüsse (neuer Parameter `recent_days`).
- Fragen älter als 45 Tage (nach Sitzungsdatum des Quellbeschlusses) mustert
  der Wochenlauf aus (`sweep_quiz.py --stale-aktuell`), damit „aktuell" wahr
  bleibt.
- Kosten: gemessen ≈ 0,5 ct je gespeicherter Frage (Q1); 8 je Woche ≈ 4 ct.
- Web: Kachel „Aus den letzten Sitzungen" nur, wenn das Gebiet Fragen hat.

### Q11 — Viertel-Wissen aller (nach #1519)

Auf der Stadtkarte ein Umschalter „Du / Alle": „Alle" tönt jeden Ortsbereich
nach der Trefferquote aller Mitspielenden bei seinen Fragen. **Anonym und
aggregiert**, erst ab 20 Antworten je Ortsbereich (darunter grau). Neues Feld
`districts_all` in `/quiz/stats`, gerechnet aus `quiz_answers` ohne Konto-
bezug, 10 Minuten zwischengespeichert.

### Q12 — Wahlfragen zur Ratswahl (sichtbar ab 28.09.2026)

„Wo holten die Grünen 2026 mehr: Innenstadt oder Kreyenbrück?" als
`format='compare'` aus den Ratswahl-Ergebnissen je Gebiet. Keine Fragen zu
Kandidierenden. Gebaut wird jetzt; die Fragen bleiben unsichtbar, bis der
Build-Lauf am oder nach dem 28.09. sie freigibt (Stichwahl am 27.09.: keine
Wahl-Spielerei im Wahlkampf). Die Messung (welche Ergebnisse je Gebiet liegen
wo vor?) steht am Anfang des PRs.

## Anhang A — Was NICHT gebaut wird, und warum

- **„Wer stimmte dagegen?"** — `council_decision_votes` hat eine Zeile.
- **„Einstimmig oder nicht?"** — 70 % einstimmig; man gewänne mit Raten.
- **Stadtteil-Rangliste der Bewohner*innen** — es gibt kein Heim-Viertel am
  Konto; es dafür einzuführen, wäre ein Personendatum für ein Spiel.
- **„Frage der Woche" in der Mail** — eine neue Mail-Art gehört Tim, nicht
  einem Quiz-Plan (Mails laufen über `notify.einreihen`, Nachtruhe, Grenzen).
  Wenn gewünscht: eigener PR hinter einem Schalter.
- **Zitat-Fragen aus Wortbeiträgen** („Wer sagte …?") — heikel für eine
  neutrale Seite und im Wahlkampf erst recht.

## Anhang B — Zeit

Q4–Q6 je ein halber Tag, Q7 ein Tag, Q8 ein halber, Q9 ein Tag, Q10 ein
halber, Q11 ein halber. Q12 nach Messung.

## Anhang C — Die Befehle hinter den Zahlen

```bash
# Tipp-Abdeckung und Fotos
sqlite3 data/council.sqlite "select count(*), sum(hint is not null), sum(image_url is not null) from council_quiz_questions where status='active'"
# Orte fürs Pin-Quiz
sqlite3 data/council.sqlite "select count(*), sum(e.n>=10), sum(m.geojson is not null) from council_entities e join council_entity_meta m using(slug) where m.lat is not null and e.kind='place'"
# Abstimmungen je Fraktion
sqlite3 data/council.sqlite "select count(*) from council_decision_votes"
# einstimmig / mehrheitlich
sqlite3 data/council.sqlite "select vote, count(*) from council_decisions where outcome in ('accepted','rejected') group by 1"
# jüngste Sitzung im Abzug
sqlite3 data/council.sqlite "select max(session_date) from council_sessions join council_decisions using(ksinr)"
```
