---
title: "Feature: Tippspiel"
description: Das Tippspiel zur Ratswahl 2026 — Beitritt ohne Konto, Sitze und OB-Prozente tippen, Live-Vergleich und Beamer-Scoreboard am Wahlabend.
---

Zur Ratswahl am 13.09.2026 gibt es ein Tippspiel: Gäste tippen, wie viele
Sitze jede Liste bekommt und wer Oberbürgermeister\*in wird, und sehen am
Wahlabend live, wie ihr Tipp gegen die Hochrechnung abschneidet. Kein Konto,
kein Passwort — ein Name reicht, per QR-Code vom Handy.

:::note[Hinter dem Feature-Schalter `tippspiel`]
Die **öffentlichen** Routen (`POST /api/tipp`, `GET /api/tipp/me`,
`GET /api/tipp/stand`, `GET /api/tipp/setup`) hängen am Schalter `tippspiel`
aus [`kern/features.py`](https://github.com/Schereo/Ratslotse/blob/main/kern/features.py) —
ohne ihn antworten sie mit 404, genau wie beim Wahlabend. Die **Admin**-Routen
unter `/api/tipp/admin/…` hängen **nicht** daran: Tim soll das Spiel
vorbereiten — Ergebnisse eintragen, die Teilnehmerliste ansehen — bevor es
öffentlich geht. Dort sitzt stattdessen die gewöhnliche Rechteprüfung
(`require_admin`).
:::

## Identität ohne Konto

Wer mitspielt, bekommt keine Zeile in `web_users` — die Identität **ist** ein
Cookie. `POST /api/tipp` ohne gültigen `tipp_token`-Cookie ist ein Beitritt
(`name` Pflicht, 2–30 Zeichen, serverseitig getrimmt und auf Mehrfach-
Leerzeichen geprüft); mit gültigem Cookie aktualisiert derselbe Endpunkt nur
den Tipp, `name` wird dann ignoriert — umbenennen kann nur der Admin
(`PUT /api/tipp/admin/spieler/{id}`). Der Cookie:

| Eigenschaft | Wert |
|---|---|
| Name | `tipp_token` |
| Haltbarkeit | 30 Tage |
| Attribute | `HttpOnly`, `SameSite=Lax` |
| Gespeichert | nur der SHA-256-Hash, nie der Klartext |

`GET /api/tipp/me` beantwortet „bin ich schon dabei, und was habe ich
getippt" — ohne Cookie oder mit einem unbekannten Hash antwortet er **401**,
und das ist hier kein Fehlerfall, sondern die erwartete Antwort für
Erstbesuchende (das Frontend fängt genau diesen Code ab, statt ihn als Netz-
oder Serverfehler zu behandeln).

## Das Spiel

Ein Tipp besteht aus zwei Teilen, beide optional für sich:

- **Sitze je Liste** — eine Zahl 0…52 für jede der 16 Listen; die Summe muss
  genau 52 ergeben, sonst lehnt der Server den Tipp ab (400).
- **OB-Prozente** — eine Zahl 0…100 für jede der neun Kandidaturen, ohne
  Summenzwang (die Stichwahl am 27.09. ist bewusst **kein** Teil des
  Tippspiels — bis dahin ist der Wahlabend vorbei).

**Der Tipp-Schluss setzt sich selbst.** Sobald die erste echte Hochrechnung
eintrifft (`_check_auto_lock`, ausgelöst durch jeden `GET /api/tipp/stand`,
solange die Phase noch `open` ist), springt das Spiel automatisch auf
`locked` — niemand muss um 20 Uhr im Admin auf einen Knopf drücken. Bleibt die
Hochrechnung aus, tut es der Admin von Hand („Tippen jetzt schließen").

**Ein später Beitritt zählt „außer Konkurrenz".** Wer erst nach dem
Tipp-Schluss beitritt, bekommt das Etikett „nachgetippt" und taucht auf der
öffentlichen Tafel unten an, solange `late_scored` beim Spiel aus ist (Default) —
niemand soll mit dem Wissen der ersten Hochrechnung noch die Bestenliste
anführen können.

## Die Punkte

Berechnet in `web/backend/app/prediction/scoring.py`, ganze Zahlen:

| Abweichung | Sitz-Punkte | OB-Punkte (Prozentpunkte) |
|---|---:|---|
| exakt | 5 | 6 (≤ 0,5 Pp.) |
| ±1 | 3 | 3 (≤ 1,5 Pp.) |
| ±2 | 1 | 1 (≤ 3,0 Pp.) |
| mehr | 0 | 0 |

Höchstwerte: Sitze 16 × 5 = **80**, OB 9 × 6 = **54**, zusammen **134**. Ohne
OB-Tipp gibt es dafür schlicht null Punkte, keinen Abzug. **0 getippt auf 0
erhalten ist exakt** — ohne diese Regel wären die sechs Kleinstlisten
wertlos, und genau sie trennen die Feldmitte.

Ränge sind dicht (1, 2, 3, …). Bei Punktgleichstand entscheidet zuerst die
Summe der absoluten Sitz-Abweichungen (`deviation`, kleiner gewinnt), dann wer
seinen Tipp zuerst abgegeben hat. Ein echter Gleichstand — beides identisch —
wird nicht ausgelost, sondern nach Eingabereihenfolge entschieden;
`prediction_standings_previous` hält je Stand fest, wer wo
stand, damit die ▲▼-Chips auf dem Beamer den **vorherigen** Rang kennen.

## Mehrere Runden

Seit dem 12.09.2026 kann das Tippspiel **mehrere Runden** haben — ein Kreis,
der unter sich tippen will, bekommt seine eigene. Die Runden stehen als
Registry in `web/backend/app/prediction/rounds.py` (Slug, Titel, gelistet
ja/nein); eine neue Runde ist ein Fünf-Zeilen-PR. Die **Hauptrunde**
(`ratswahl`) hat keinen Parameter: `/tipp`, `/tipp/live` und `/api/tipp/…`
bleiben, wie sie sind. Jede andere Runde hängt an `?runde=<slug>` (Seiten)
bzw. `?round=<slug>` (API); ein unbekannter Slug ist 404.

| getrennt je Runde | geteilt |
|---|---|
| Spieler*innen, Tipps, Doppelnamen-Zähler | der Wahlabend (Hochrechnung, Auto-Lock aus derselben Quelle) |
| Ergebnisse (Entwurf und veröffentlicht), Ränge, Protokoll | Listen, OB-Kandidaturen, Punkteregeln |
| Phase (offen/Tippfrist/Endstand) | der Feature-Schalter `tippspiel` |
| der Cookie: `tipp_token` bzw. `tipp_token_<slug>` | die Admin-Seite |

Eine Runde mit `listed = False` erscheint **nirgends** — nicht auf „Heute",
nicht in der Beamer-Fußzeile der Hauptrunde, in keiner Sitemap. Ihr Link ist
ihr Zugang; der QR-Code ihres Beamers (`/api/tipp/qr.png?round=<slug>`)
zeigt auf `/tipp?runde=<slug>`. Der **Admin** unter `/tipp/admin` verwaltet
alle Runden über einen Umschalter im Kopf — auch eine Runde ohne eigene
Adminperson bekommt so ihre Ergebnisse, notfalls von Hand.

In der Datenbank trägt jede Runde eine Zeile in `prediction_game` (`slug`),
die übrigen Tabellen ihr `game_id`. Der Bestand von vorher (ein Spiel mit
`CHECK (id = 1)`) wird beim Start zur Hauptrunde migriert
(`Store._migrate_tippspiel_runden`, geprüft in
`tests/test_prediction_runden.py`).

## Woher der Vergleich kommt

**Grundlage ist der Wahlabend.** `GET /api/tipp/stand` liest denselben
Auszählungsstand wie `/wahlabend` (`election.service.live()`, in der
Generalprobe `?probe=2021&counted=N`) und die OB-Prozente aus
`election.mayor.fetch()`. Je Liste zählt die **Hochrechnung**, sobald es
eine gibt, sonst der ausgezählte Stand — der Beamer folgt dem Votemanager
also von selbst, ohne dass am Abend jemand klickt.

**Darüber liegt je Liste die veröffentlichte Handeingabe.** Der Admin trägt
Zahlen ein (`PUT /api/tipp/admin/ergebnis`) oder holt sie per „Jetzt
abfragen" (`POST /api/tipp/admin/abfragen`). Beides landet zunächst nur im
**Entwurf** (`prediction_result`, Spalten ohne `published_`) — ein
Tippfehler beim Eintragen erscheint nirgends öffentlich. Erst
`POST /api/tipp/admin/veroeffentlichen` schreibt die `published_`-Spalten;
`POST …/verwerfen` nimmt den Entwurf zurück auf den zuletzt veröffentlichten
Stand. Wirkung je Zeile:

| Veröffentlichte Zeile | Wirkung |
|---|---|
| von Hand (`manuell`) | **schlägt den Wahlabend** für genau diese Liste bzw. Kandidatur — die Zusage |
| aus „Jetzt abfragen" (`votemanager`) | friert nichts ein; zählt nur, wenn der Wahlabend für die Liste gerade keine Zahl nennt — der Rückfall |

`source_label` sagt, was gerade gilt: `votemanager`, `manuell`, `gemischt`
oder leer (noch kein Ergebnis). Die OB-Prozente zählen erst, wenn dort etwas
ausgezählt ist (`phase != before`).

**Ein Stand ist ein Ist, nicht ein Abruf.** Die Ränge liegen unter einem
Stand-Zeitstempel in `prediction_standings`, und `rank_before` ist der Rang
im letzten *anderen* Stand. Der Zeitstempel wechselt nur, wenn sich die
verglichenen Zahlen ändern; er ist zugleich der ETag. Die Generalprobe
schreibt nichts in die Datenbank — kein Tipp-Schluss, keine Ränge — und
hält ihren vorherigen Rang im Prozess.

## Der Beamer (`/tipp/live`)

Die eine Seite, die am Wahlabend die meiste Zeit auf dem Bildschirm steht:

1. **Vor dem ersten Ergebnis** — der QR-Code zum Beitreten, ein Zähler „N
   Mitspielende haben schon getippt", der Server-Text zum Tipp-Schluss
   (`deadline_hint` — bewusst kein tickender Countdown: Der Server nennt
   keine feste Uhrzeit, solange sie nicht feststeht).
2. **Danach automatisch** abwechselnd (alle 45 s) zwei Ansichten:
   - **Vergleich** — Halbkreis mit dem veröffentlichten Sitzstand, Tabelle
     Liste/Ist/Ø-Tipp/Exakt, OB-Prozente, der vom Server erzeugte Satz
     (`compare_sentence`, z. B. „Die Runde hat die CDU im Schnitt um 2 Sitze
     zu stark getippt").
   - **Scoreboard** — Podium für die ersten drei, darunter die Rangliste mit
     ▲▼-Chip je Rangänderung. Ein frischer Auszählungsstand
     (`computed_at` wechselt) springt für 60 Sekunden auf die Rangliste, ein
     Führungswechsel oder der Endstand lässt einmal Konfetti laufen.
3. `?ansicht=qr|vergleich|rangliste` erzwingt eine Ansicht — genau die URL,
   die der „Beamer in diesem Modus öffnen"-Knopf im Admin benutzt.

Die Seite startet beim allerersten Besuch **dunkel** (fürs abgedunkelte
Zimmer), merkt sich danach aber dieselbe Geräte-Wahl wie überall sonst in der
App — kein zweites, seiteneigenes Theme-System. Gebaut ist sie gegen
Design-Token, nicht gegen Farbwerte: Der Seiten-Hintergrund ist das
gewöhnliche `bg-background`, nur die hervorgehobene Tafel je Screen trägt
zusätzlich `.hh-tafel` (dieselbe Klasse wie beim Haushalt).

## Grenzen

- **Kein Konto heißt kein Gerätewechsel.** Der Tipp hängt am Cookie; wer den
  Browser wechselt oder Cookies löscht, verliert seinen Zugang zum eigenen
  Tipp (nicht den Tipp selbst — der Admin sieht und kann ihn weiter zuordnen,
  s. u.).
- **Die Stichwahl (27.09.) ist kein Teil des Tippspiels.** Sie liegt zeitlich
  nach dem Wahlabend, für den das Spiel gebaut ist.
- **Der Admin kann jeden Tipp sehen, niemand sonst.** Es gibt keine
  „Tipps der anderen ansehen"-Funktion vor Tipp-Schluss — das wäre gegen den
  Sinn eines Tipps.
- **Ausblenden statt Löschen.** `PUT /api/tipp/admin/spieler/{id}` mit
  `hidden: true` nimmt eine Person von der öffentlichen Tafel, ihr Tipp
  bleibt in der Datenbank (Nachvollziehbarkeit, falls ein Ausblenden ein
  Versehen war).

## Runbook Wahlsonntag (13.09.2026)

**Vorher, auf `dev` oder `feature`:** `FEATURE_FLAGS=*` steht dort ohnehin;
`/tipp` und `/tipp/live` durchspielen, `/tipp/admin` einen Testlauf machen
(Ergebnis eintragen, veröffentlichen, Spieler ausblenden). Die Generalprobe
`?probe=2021&counted=0` → `40` → `90` → `133` auf `/api/tipp/stand` bzw. der
entsprechenden Wahlabend-Seite (die Tippspiel-Zahlen selbst brauchen echte
Tipps in der Datenbank, s. u.) prüft, ob ein neuer Stand sauber gleitend
ankommt.

**Sonntag, vor 18 Uhr auf Prod:**

```bash
FEATURE_FLAGS=wahlabend,tippspiel
```

in der `.env` setzen (Sicherung als `.env.bak-<datum>`, wie am 07.09.2026),
dann `sudo systemctl restart nwz-web-api`. `curl -s
https://ratslotse.de/api/app-config` muss danach beide Namen nennen.
`/tipp/live` auf dem Beamer öffnen, Theme wählen, QR-Ansicht steht.

**Bis zur ersten Hochrechnung:** Gäste tippen über den QR-Code. Eine Summe,
die nicht auf 52 aufgeht, meldet sich im Frontend, bevor der Tipp abgeschickt
wird.

**Um 20 Uhr, wenn die erste Hochrechnung kommt:** Der Tipp-Schluss setzt sich
selbst (s. o.). Kommt aus irgendeinem Grund keine Zahl, im Admin „Tippen
jetzt schließen" drücken.

**Je neuem Auszählungsstand:** Im Admin „Jetzt abfragen" → Zahlen prüfen →
„Veröffentlichen". Der Beamer springt von selbst für eine Minute auf das
Scoreboard.

**Stört ein Name:** Admin → Teilnehmer → „Ausblenden". Wirkt ab dem nächsten
veröffentlichten Stand.

**Nach dem Endergebnis:** Phase auf „Endergebnis" setzen, Screenshot des
Scoreboards für alle, die nicht da waren. Der Schalter bleibt an, bis der
Wahlausschuss das amtliche Ergebnis festgestellt hat — danach `tippspiel` aus
`FEATURE_FLAGS`, Neustart; dieselbe Regel wie beim Schalter `wahlabend`, s.
[`kern/features.py`](https://github.com/Schereo/Ratslotse/blob/main/kern/features.py).

## Dateien

| Pfad | Inhalt |
|---|---|
| `web/backend/app/prediction/scoring.py` | Punkteformel, Rang- und Sortierregel |
| `web/backend/app/prediction/service.py` | Zusammensetzen von Stand/Mein-Tipp, Auto-Tipp-Schluss |
| `web/backend/app/election/mayor.py` | Die neun OB-Kandidaturen und ihr Auszählungsstand |
| `web/backend/app/routers/tippspiel.py` | Alle `/api/tipp/…`-Endpunkte, öffentlich und Admin |
| `web/backend/app/antworten.py` | Antwortformen `Prediction…` (Teil des API-Vertrags) |
| `kern/store.py` | Schema und Zugriffe (`prediction_…`-Tabellen) |
| `web/frontend/app/tipp/` | Beitritt/Tippen/Mein-Tipp (Handy) |
| `web/frontend/app/tipp/admin/` | Verwaltung: Ergebnisse, Phase, Teilnehmer |
| `web/frontend/app/tipp/live/` | Der Beamer |
| `web/frontend/components/tipp/` | Alle Bausteine der drei Flächen oben |
| `tests/test_prediction_scoring.py` | Punkteformel, Rangregel |
| `tests/test_prediction_mayor.py` | OB-Wahl: Slugs, Parsing der Ergebnisdarstellung |
| `tests/test_prediction_api.py` | Endpunkte: Beitritt, Tippen, Admin, Auto-Tipp-Schluss |
| `web/frontend/tests/e2e/16-tippspiel.spec.ts` | Beitritt, Tippen, Mein Tipp (Handy) |
| `web/frontend/tests/e2e/17-tippspiel-live.spec.ts` | Der Beamer: Automatik, Führungswechsel, Themes |
