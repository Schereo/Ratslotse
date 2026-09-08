# Plan: Sehen, was Nutzer*innen tun — und sie zurückholen

Stand 08.09.2026. Grundlage ist die Prod-Auswertung vom selben Tag
(27 Konten, 9 echte Neuanmeldungen seit 25.08., 169 Fragen, 48 Themen).
Ihre Kernbefunde, auf die dieser Plan antwortet:

| Befund | Zahl |
|---|---|
| Anonyme Besucher sind unsichtbar — kein Zugriffslog, keine Analytik | 0 Datenpunkte |
| Neue Konten ohne Thema **und** ohne Gremium (kein Anlass, sie je anzusprechen) | 5 von 9 |
| Neue Konten, die an einem zweiten Tag wiederkamen | 4 von 9 · nach 7 Tagen: 1 · heute: 0 |
| Antworten, die mit „keine Auskunft" enden | 11 von 124 (9 %) |
| Suchbegriffe in der Beschluss-Suche seit dem 03.09. | 0 |
| Fragen, die nicht gespeichert wurden (alter App-Build ohne `conversation_id`) | 45 von 169 (27 %) |
| Daumen-Bewertungen in drei Monaten | 5 |

**Ein Vorbehalt, der die Reihenfolge bestimmt:** Der Einrichtungs-Assistent
läuft im Browser erst seit dem 02.09. (#950, Tour-Einladung #1061 am 03.09.).
Sechs der neun Neuen haben sich davor registriert und ihn nie gesehen; von den
drei danach haben ihn zwei gemacht. Ob der Assistent „übersprungen" wird,
wissen wir also noch nicht — und genau deshalb steht das Messen vor dem Bauen.

## Grundsätze

- **Kein Dritter.** Keine Analytik-Dienste, kein Cookie, keine IP, kein
  User-Agent, keine Sitzungsaufzeichnung. Dasselbe Muster wie
  `web/frontend/lib/fehler-melden.ts` → `POST /api/client-errors`: an die
  eigene Domäne, in die eigene Tabelle, vorher gar nicht erst erhoben, was
  der Server maskieren müsste. Ein Wächter-Test hält die Feldliste fest.
- **Aufrufe zählen, nicht Menschen verfolgen.** Ohne Kennung gibt es keine
  „eindeutigen Besucher"; wir zählen Aufrufe je Tag/Seite/Client und nennen
  sie auch so. Eine Sitzung ist ein Tab (`sessionStorage`-Marke, verschwindet
  mit dem Tab).
- **Logik ins Backend, Web und iOS featuregleich.** Jeder Zähler und jede
  Rückmeldung entsteht im Server; die Clients zeigen nur an.
- **Jeder Anlass geht durch `notify.einreihen`.** Nichts, was Leute zurückholt,
  umgeht Aus-Schalter, Nachtruhe und Tagesgrenze. Kein Newsletter.
- **Jede Maßnahme nennt vorher die Zahl, an der man ihre Wirkung abliest.**

## Die vier Kennzahlen

Sie kommen aus Daten, die heute schon vorliegen (`web_users`,
`user_activity`, `topics`, `committee_subscriptions`, `qa_conversation_turns`)
und brauchen nur eine Auswertung — deshalb Teil von PR 1.

| Kennzahl | Definition | Stand 08.09. |
|---|---|---|
| **Haken-Quote** | Anteil neuer Konten mit ≥ 1 Thema oder Gremium binnen 24 h | 4 von 9 |
| **Tag-2 / Tag-7 / Tag-30** | Anteil neuer Konten mit Aktivität an einem weiteren Tag im Fenster | 4/9 · 1/9 · 0/9 |
| **Sackgassen-Quote** | Anteil Antworten ohne Quelle | 9 % |
| **Fragen je aktivem Konto und Woche** | Median über Konten mit Aktivität in der Woche | nicht erhoben |

## Teil A — Messen

### PR 1 · Trichter und Kohorten im Admin-Panel

Reine Auswertung vorhandener Tabellen. Neue Ansicht *Statistik → Kohorten*:
je Registrierungswoche die Stufen registriert → bestätigt → Einrichtung
begonnen → fertig → erster Haken → erste Frage → Tag 2 → Tag 7 → Tag 30,
dazu die vier Kennzahlen als Verlauf. Betreiber- und Testkonten (Rolle
`admin`, Domänen aus einer Liste in `.env`) werden ausgeschlossen —
sonst ist die Statistik das eigene Klicken (Tim: 15.209 von 23.888 Zugriffen).

- Dateien: `kern/store.py` (Abfragen), `web/backend/app/routers/admin.py`,
  `antworten.py` (Antwortform), Vertrag neu schneiden, `lib/vertrag.ts`,
  Admin-Seite. Wächter: `pruefe.py --nur vertrag,typen`.
- Aufwand: M. Wirkung: jede weitere Maßnahme wird damit erst ablesbar.

### PR 2 · Aufrufe der öffentlichen Seiten

`POST /api/page-views` nach dem Muster von `client-errors` (offen, immer 200,
gebremst): Pfad als Muster (`/council/decision/{n}`), Client, `angemeldet`
ja/nein, Sitzungs-Erstaufruf ja/nein. Tabelle `page_views(day, path_pattern,
client, logged_in, count, sessions)` — kein Referrer, keine Query, keine
Kennung. Die Frontend-Seite ist ein `OnboardingTracker`-artiger Hook in der
Hülle, der bei Routenwechsel feuert; iOS sendet dasselbe je Screen.

Anzeige im Admin: Aufrufe je Tag, die zehn meistgesehenen Seitenmuster,
Anteil angemeldet/anonym, App/Web. Damit ist „viele neue Besucher" erstmals
eine Zahl — und die Frage, welche Tabs die Leute überhaupt aufmachen, für
Anonyme und Angemeldete beantwortet.

- Dateien: `kern/store.py` (Tabelle + Migration + Register),
  `web/backend/app/routers/feedback.py` (neben `client_errors_router`),
  `web/frontend/lib/aufrufe-melden.ts`, `app/(app)/layout.tsx` und
  `app/layout.tsx`, `ios/…/AppModel.swift`, Wächter-Test nach Vorbild
  `tests/test_fehlersammler.py` (Feldliste), Datenschutzerklärung prüfen
  (aggregiert, ohne Personenbezug — vermutlich ein Satz).
- Optional daneben: 7-Tage-rotierendes Caddy-Zugriffslog auf tk-edge-vm,
  nur für Betriebsdiagnose (Bots, 404-Wellen), nie für Produktzahlen. Root
  über tk-host, Caddyfile-Block je vhost. Nicht Teil des Repos.
- Aufwand: M.

### PR 3 · Ereignisse, die heute stumm sind

`record_activity` bekommt weitere `feature`-Werte, alle serverseitig an der
Stelle, an der das Ereignis ohnehin verarbeitet wird:

| feature | wo |
|---|---|
| `topic_created`, `topic_hits_opened` | `routers/council.py` Themen-Endpunkte |
| `bookmark`, `share`, `template_follow` | die jeweiligen Endpunkte |
| `ai_question_chip` statt `ai_question`, wenn die Frage wörtlich ein Vorschlagstext ist | `ask`-Endpunkt (Vergleich gegen die Chip-Liste, die der Server ohnehin liefert) |
| `ai_answer_empty` | `ask`, wenn `cited` leer ist — die Sackgassen-Quote |
| `from_mail` | Frontend-Hülle, wenn `?zeig=` im Aufruf steht (die Deep-Links der Mails) |
| `wizard_skipped` je Schritt | `/onboarding/setup` |

Dazu im Admin die vorhandene Funktions-Tabelle um die neuen Spalten. Der
Test `tests/test_backend_api.py` (Design 20a) hält die erlaubten Werte fest.

- Aufwand: S–M.

### PR 4 · Antworten ohne Quelle sichtbar machen

Eine Liste im Admin: die Fragen der letzten 30 Tage, deren Antwort keine
Quelle hatte — nur für Konten mit eingeschaltetem Speichern (die Frage liegt
dann ohnehin in `qa_conversation_turns`); für alle anderen nur der Zähler.
Daneben die Retrieval-Probe als Knopf: dieselbe Frage heute noch einmal nur
durch `hybrid_search` (kein Modell, keine Kosten) — zeigt, ob eine Lücke
inzwischen zu ist, wie bei „Giftmüll" und „Ausfallbürgschaft".

- Aufwand: S.

### Nachzug · App-Build 19 im Store

Der ausgelieferte Build schickt weder `X-Client` noch `conversation_id`;
seine Fragen fehlen in jeder Auswertung und die Leute haben keine
Gesprächsliste. Kein Code nötig — der nächste Store-Build hat beides.
Beim Release-Schnitt `scripts/ios_vertrag.py --ausgeliefert` und danach
prüfen, dass `client=ios` in `user_activity` ankommt.

## Teil B — Halten

### PR 5 · Der erste Haken

Die Einrichtung endet heute mit „Fertig", auch wenn nichts eingerichtet
wurde. Drei Änderungen, alle im bestehenden Assistenten
(`onboarding-flow.tsx`, iOS-Pendant, Server-Regel in `/onboarding/setup`):

1. **Themen zuerst.** Schritt 1 wird die Themenwahl mit den Stadtthemen-Chips
   (#1059) — drei Tipps, fertig. Gremien und Stadtteil rücken dahinter.
2. **Überspringen bleibt, wird aber zur Nebenwahl.** Kein Zwang (Tims
   Grundsatz), aber der Weg ohne Thema ist ein kleiner Textlink, nicht der
   Hauptknopf — und der Server merkt sich `wizard_skipped`.
3. **Aus der ersten Frage ein Thema machen.** Unter jeder Antwort: „Dieses
   Thema verfolgen" — ein Tipp legt aus der Frage ein Thema an
   (`topic_auto_description` gibt es schon) und zeigt sofort „n Beschlüsse,
   davon m in 6 Monaten". Das ist die kürzeste Brücke von „ich habe etwas
   gefragt" zu „das Produkt meldet sich bei mir".

Zahl: Haken-Quote. Ziel: aus 4 von 9 wird die Mehrheit.

- Aufwand: M (Web + iOS).

### PR 6 · Die Erinnerung erreicht auch die, die nie angefangen haben

`scripts/remind_setup.py` schreibt nur ab Schritt 1. Zweiter Anlass, gleiche
Zurückhaltung (eine Mail je Konto, nie wieder): Konten, die seit 48 h
bestätigt sind und **weder Thema noch Gremium** haben. Der Text nennt drei
Stadtthemen als Knöpfe, die direkt ein Thema anlegen (`?zeig=`-Deep-Link).

Zahl: Tag-7-Rückkehr der Konten, die die Mail bekamen.

- Dateien: `scripts/remind_setup.py`, `kern/store.py` (Abfrage),
  `kern/jobs.py` unverändert (gleicher Job). Aufwand: S.

### PR 7 · „Keine Auskunft" wird ein Angebot

Wenn `cited` leer bleibt, weiß der Server in dem Moment mehr, als die Antwort
sagt: die verworfenen Kandidaten liegen vor. Der `ask`-Endpunkt liefert dann
zusätzlich `alternativen`: die drei bestbewerteten verworfenen Titel als
Chips („Meintest du: Sachstand ehemalige Schießanlage Fliegerhorst?") und —
wenn ein Wort der Frage im Glossar oder in den Entitäten-Aliassen steht —
die amtliche Bezeichnung dazu. Die Clients zeigen die Chips unter der
Antwort; ein Tipp stellt die Frage neu.

Dazu genau dort, und nur dort, die Frage „Hat das geholfen?" mit Daumen —
die vorhandene Tabelle `council_qa_feedback` reicht, es fehlt nur der Anlass.

Zahl: Sackgassen-Quote, und der Anteil Sackgassen, nach denen eine zweite
Frage folgt.

- Dateien: `routers/council.py` (`ask`), `council/embeddings.py`
  (verworfene Kandidaten zurückgeben), `antworten.py`, SSE-Vertrag
  (`done`-Ereignis um `alternativen`), Web `fragen`-Komponenten, iOS
  `SSEClient.swift`. Validierung: die Stadion-Fragen dürfen nicht schlechter
  werden (Tims Regel). Aufwand: M.

### PR 8 · Themen bekommen beim Anlegen eine Rückmeldung

`council.topic_intel.treffer` rechnet das Ergebnis im Bearbeiten-Blatt
schon vorab aus. Zwei Regeln obendrauf, im Server:

- **Leer:** 0 Treffer → „Zu diesem Thema gibt es in Ratsbeschlüssen bisher
  nichts. Anlegen lohnt sich, wenn du auf Künftiges wartest — sonst probier
  eine andere Formulierung." (Der Fall „Oberbürgermeisterkandidaten" seit
  dem 13.06.)
- **Mehrfach:** mehr als ein bekannter Ort/Stadtteil im Namen →
  „Das sind 7 Stadtteile. Als 7 Themen bekommst du je Stadtteil eine eigene
  Meldung — aufteilen?" mit einem Knopf, der es tut. (Der Fall
  „Bürgerfelde Nord, Dietrichsfeld, …")

Und einmal im Monat im Themen-Abgleich (#1129): Themen, die seit 90 Tagen
keinen Treffer haben, bekommen in der Karte den Hinweis „ruht seit …".

- Dateien: `council/topic_intel.py`, Themen-Endpunkte, Web + iOS
  Bearbeiten-Blatt. Aufwand: S–M.

### PR 9 · Mailmenge vor dem Abonnieren zeigen

Vier Konten haben binnen 15 Sekunden alle 16 Ausschüsse abonniert; zwei
davon bekamen je ~20 Tagesordnungs-Mails und kamen nie wieder. Der Knopf
„alle" bleibt, aber neben der Auswahl steht live, was sie bedeutet: „≈ n
Meldungen im Monat" — aus den Sitzungsterminen der letzten 12 Monate
gerechnet (`council_scheduled_sessions`, im Server). Ab einer Schwelle ein
ruhiger Hinweis, keine Sperre.

- Aufwand: S.

### Zur Diskussion · Ein Anlass für Konten ohne Abo

Wer nichts abonniert hat, hört nie wieder von Ratslotse. Ein möglicher
Anlass, der kein Newsletter ist: das „Fundstück des Tages" (`council_daily_finds`,
gibt es schon) als **wöchentliche** Karte per Push/Mail, ausschließlich für
Konten ohne Thema und Gremium, abbestellbar mit einem Tipp, über
`notify.einreihen` mit eigener Art (`n7_fundstueck`). Das braucht Tims
Entscheidung — es ist die einzige Maßnahme hier, die Leute anspricht, die
nicht ausdrücklich darum gebeten haben.

## Reihenfolge

| # | PR | Aufwand | Zahl, an der man es sieht |
|---|---|---|---|
| 1 | Trichter & Kohorten im Admin | M | alles Weitere |
| 2 | Aufrufe der öffentlichen Seiten | M | Aufrufe/Tag, Seiten, App/Web |
| 3 | Stumme Ereignisse | S–M | Chip-Anteil, Sackgassen, `from_mail` |
| 5 | Der erste Haken | M | Haken-Quote |
| 6 | Erinnerung an Nie-Begonnene | S | Tag-7 der Angeschriebenen |
| 7 | „Keine Auskunft" als Angebot | M | Sackgassen-Quote, Folgefrage |
| 8 | Themen-Rückmeldung | S–M | leere Themen, Mehrfach-Themen |
| 9 | Mailmenge vor dem Abo | S | Abos je Konto, Rückkehr |
| 4 | Antworten ohne Quelle im Admin | S | — (Werkzeug) |

1–3 zuerst und **vier Wochen laufen lassen**, bevor 5–9 gebaut werden: Der
Assistent im Web ist sechs Tage alt, die Zähler ebenso. Was danach immer noch
bei 0 Suchbegriffen und 4 von 9 Haken steht, ist ein Befund; was heute so
aussieht, kann noch der Zeitpunkt sein.

Jeder PR: ein Zweig von `dev`, ein Changelog-Fragment, `pruefe.py` vor dem
Push, Bild vor dem Merge bei UI.
