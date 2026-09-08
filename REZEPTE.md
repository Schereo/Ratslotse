# Rezepte: welche Aufgabe fasst welche Dateien an

Die [`CLAUDE.md`](CLAUDE.md) sagt, **welche Regeln** gelten. Diese Datei sagt,
**wo man anfängt** — für die Aufgaben, die hier immer wieder vorkommen.

Sie ersetzt keine der Schicht-Dateien; sie führt zu ihnen. Wenn ein Rezept und
eine `CLAUDE.md` sich widersprechen, gilt die `CLAUDE.md`.

**Vor jedem Push:** `python scripts/pruefe.py` — und nach einer NEUEN Datei
einmal die volle Suite, nicht nur `--schnell`. Der pre-push-Hook fährt nur die
schnellen Prüfungen, und `tests` steckt bewusst nicht darin.

---

## Einen API-Endpunkt hinzufügen

1. **Antwortform** in [`web/backend/app/antworten.py`](web/backend/app/antworten.py).
   Ein Handler mit `-> dict` erzeugt im Vertrag „irgendein Objekt", und daraus
   leitet kein Generator Typen ab. Die zwei Regeln dort lesen: Ein fehlender
   Pflichtschlüssel ist ein **500**, ein nicht deklariertes Feld wird **stumm
   entfernt**.
2. **Route** in `web/backend/app/routers/…`. Rechte über
   `Depends(require_permission("…"))`, nie über einen Rollennamen.
3. **Vertrag neu schneiden**: `python scripts/openapi_schnitt.py`
4. **Frontend-Typen**: `cd web/frontend && npm run api:typen`
5. **Aufrufen** nur über `web/frontend/lib/api.ts` — `api.get/post/put/del`. Ein nacktes
   `fetch("/api/…")` zeigt in der nativen App ins Nichts, und ESLint weist es ab.

**Was dich fängt:** `test_api_vertrag.py` (Antwortform), `test_frontend_zugriffe.py`
(gerufene Pfade), `test_ios_vertrag.py` (die ausgelieferte App), `pruefe.py --nur vertrag,typen`.

---

## Eine Frontend-Seite hinzufügen

1. Seite unter `web/frontend/app/(app)/…/page.tsx` — innerhalb `(app)` erbt sie
   Navigation und Anmeldung.
2. **Vor der ersten Zeile** [`web/frontend/DESIGNSPRACHE.md`](web/frontend/DESIGNSPRACHE.md)
   lesen. Abweichungen dort nachziehen, nicht danebenlegen.
3. Antworttypen aus `web/frontend/lib/vertrag.ts`, nicht abtippen.
4. Reine Logik gehört nach `web/frontend/lib/` und bekommt dort einen `*.test.ts` daneben.
5. Soll die Seite noch nicht für alle sichtbar sein: Recht (`web/frontend/lib/rechte.ts`) für
   „wer darf", Feature-Schalter (`web/frontend/lib/features.ts`) für „schon so weit?".

**Was dich fängt:** `npx tsc --noEmit`, `npx next lint`, `14-layout.spec.ts`
(die Seite darf nicht seitwärts scrollen), `npx vitest run`.

**Und:** Vor dem Merge ein Bild an Tim (`SendUserFile`) und sein Gegenlesen
abwarten. Das ist eine stehende Regel für jeden UI-PR.

---

## Eine Tabelle oder Spalte ändern

1. `CREATE TABLE` in `SCHEMA` — `council/store_schema.py` bzw. `kern/store.py`.
2. **Und** die Migration in `_migrate()` derselben Datei. Beides, immer.
3. Bei einer Umbenennung zusätzlich die Karte: `TABELLEN_UMBENANNT` bzw. die
   Spaltenlisten (`_GELD_SPALTEN` & Co.).

**Der Fehler, der hier lauert:** Wer nur das `CREATE TABLE` ändert, bekommt eine
grüne CI (dort entsteht jede Datenbank frisch) und einen `OperationalError` auf
dev und Prod, wo sie gewachsen ist. Ein Migrationspaar `("x", "x")` wirkt gar
nicht, und kein Test schlägt an — deshalb die Wächter.

**Was dich fängt:** `test_migration_bestand.py` (gegen die Schema-Auszüge von dev
UND Prod, seit 09/2026 **mit** Datenzeilen), `test_schema_gegen_migration.py`,
`test_alte_werte.py` (liest eine Oberfläche noch den alten Wert?).

---

## Einen Cron-Job hinzufügen

1. Skript in `scripts/`, `main()` gibt ein `dict` mit Kennzahlen zurück.
2. In `run_guarded` (`kern/alerts.py`) einhängen — sonst gibt es bei einem
   Absturz keine Mail und keinen Eintrag in `job_runs`.
3. **Takt in [`kern/jobs.py`](kern/jobs.py) eintragen.** Wer die crontab ändert
   und das vergisst, bekommt eine falsch anschlagende Überfällig-Ampel.
4. Meldungen an Nutzer NUR über `notify.einreihen` — alles andere umgeht
   Aus-Schalter, Nachtruhe und Tagesgrenze zugleich.

**Was dich fängt:** `tests/test_jobs.py`. Achtung: `Callable[..., dict]`
prüft **nichts**, und ein Trockenlauf beweist nie den scharfen Lauf.

---

## Einen Prompt ändern

Nur in [`kern/prompts.py`](kern/prompts.py) — als Code, im Diff sichtbar. Es gibt
seit 08/2026 bewusst keine Möglichkeit mehr, ihn im Admin-UI zu überschreiben.

**Aufpassen:** Der Prompt schreibt dem Modell JSON-Schlüssel vor, die der Parser
wieder einliest. Wer einen Schlüssel umbenennt, benennt ihn an beiden Stellen um.

---

## Eine Rolle oder ein Recht hinzufügen

Ein Eintrag in [`kern/roles.py`](kern/roles.py) — mehr nicht. Geprüft wird immer
gegen ein **Recht**, nie gegen einen Rollennamen: Backend
`Depends(require_permission("…"))`, Web `web/frontend/lib/rechte.ts`, App `User.can(_:)`.

Eine neue Rolle wirkt damit ohne Frontend-Release und ohne Store-Update.

**Was dich fängt:** `test_rollen.py` — auch die Frage, ob jede Route mit dem
Recht wirklich das Recht verlangt.

---

## Etwas ausliefern, das noch nicht an sein soll

* **Nur auf dev sichtbar?** `process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev"`,
  sonst `notFound()`.
* **Auf Prod ausliefern, aber einzeln schaltbar?** Ein Eintrag in
  [`kern/features.py`](kern/features.py), `FEATURE_FLAGS` in der `.env`, im
  Frontend `useFeature("…")`.

Ein Schalter sagt „schon so weit?", ein Recht sagt „wer darf?". Verwechsle sie
nicht: Ein Schalter schützt nichts, das Backend setzt ihn nicht durch.

**Was dich fängt:** `test_features.py` — ein Name, den die Registry nicht kennt,
ist **dauerhaft aus** und sieht aus wie „noch nicht angeschaltet".

---

## Einen Release fahren

Der einzige Ablauf, der von Hand geht und **nicht** gesquasht wird. Er steht
vollständig in [`CLAUDE.md`](CLAUDE.md) unter „Deployment & Branch-Modell".
Die drei Dinge, die man dabei vergisst:

1. `python3 scripts/ios_vertrag.py --ausgeliefert` — bricht die App im Store?
2. Nach einem Fix auf `main`: zurück nach `dev` mergen.
3. **Bei einer Minor-Version: die Karte „Neu bei Ratslotse"** — ein `Release(…)`
   in [`kern/releases.py`](kern/releases.py), in denselben Commit wie der
   Versionsschnitt. Entwurf aus den Fragmenten:
   `scripts/changelog_schnitt.py x.y.0 --highlights`. Höchstens vier Highlights,
   jedes mit einem Ziel in der App, **nur große Features** — Fixes stehen im
   Changelog. Verschickt wird später von Hand im Admin-Panel unter
   *Neuigkeiten*; ein Patch-Release bekommt gar keinen Eintrag.

   **Dazu je Highlight ein Bild** (oder ein kurzer Clip) nach
   `web/frontend/public/neuigkeiten/<version>/`, **immer in der hellen
   Fassung** (Tims Entscheidung 07.09.2026 — eine zweite für den Dunkelmodus
   wäre doppelte Arbeit je Ausgabe, und ein Bild in einem gerahmten Kasten
   liest sich ohnehin als Abbildung), alle im **16:9-Rahmen** — die Bühne blättert sonst durch verschieden hohe Kästen.
   Aufgenommen wird die laufende lokale App mit echten Daten (Playwright über
   das installierte Chrome, `deviceScaleFactor: 2`, Ausschnitt um das Element
   herum auf 16:9 erweitert; Bilder als WebP ≤ 1600 px, Clips als stummes
   h264-MP4 mit Standbild). **Zeiger und Klick müssen im Clip sichtbar sein** —
   Playwright zeichnet den Mauszeiger nicht mit, die Aufnahme malt ihn sich per
   `addInitScript` selbst an die echten Mausereignisse. Entweder **alle**
   Highlights einer Ausgabe haben ein Bild oder keins — sonst hat die Bühne ein
   Loch, und `test_releases.py` meldet es.

   **Für die App dieselben Bilder aus der App** (`media_ios`, Tims Wunsch
   07.09.2026): Wer auf dem iPhone liest, soll das iPhone sehen. Aufgenommen im
   Simulator gegen das lokale Backend, **ganzes Telefon, nichts
   beschnitten** — ein zurechtgeschnittener Bildschirm sieht nicht mehr nach
   iPhone aus:

   ```bash
   xcodebuild -project ios/Ratslotse.xcodeproj -scheme Ratslotse \
     -destination 'platform=iOS Simulator,id=<UDID>' -derivedDataPath <scratch> build
   xcrun simctl install <UDID> <scratch>/Build/Products/Debug-iphonesimulator/Ratslotse.app
   SIMCTL_CHILD_RATSLOTSE_API_BASE_URL=http://127.0.0.1:<port> \
   SIMCTL_CHILD_RATSLOTSE_DEBUG_ACCESS_TOKEN=<Token> \
     xcrun simctl launch <UDID> de.ratslotse.dev
   xcrun simctl io <UDID> screenshot bild.png
   ```

   Vier Dinge, die dabei Zeit kosten:

   * `RATSLOTSE_DEBUG_ROUTE` ist ein **Deep-Link**, kein App-Screen: `/abos`
     landet im Web-View. Native Screens werden getippt.
   * **Auf Hell stellen geht nur über Mehr → Konto → Erscheinungsbild**,
     `simctl ui appearance` wirkt auf die App nicht.
   * Ein Start aus Safari lässt „◀ Safari" in der Statusleiste stehen; vor der
     Aufnahme Safari beenden und `simctl status_bar … override` setzen.
   * Für die Live-Karte braucht es eine laufende Sitzung: `council_sessions`
     auf heute ziehen und eine Zeile in `council_live_state` legen —
     **hinterher zurückdrehen**.

   **Die App-Aufnahmen sind hochkant und ungeschnitten** (`aspect` =
   Bildschirmmaß, Tims Vorgabe 07.09.2026): Ein Telefon-Bildschirm in einem
   16:9-Kasten stünde als schmaler Streifen zwischen zwei leeren Flächen, und
   ein oben und unten beschnittener sieht nicht mehr nach iPhone aus. Die Bühne
   baut ihren Rahmen aus dem Feld, alle Medien einer Ausgabe teilen sich eines.

   **Was der Simulator NICHT kann:** Im Teilen-Blatt steht dort nur
   „Erinnerungen" — kein Messenger meldet sich als Ziel an (Messages ist
   installiert, bietet im Simulator aber keine Teilen-Erweiterung). Wer den
   Weg „an jemanden schicken" zeigen will, filmt diese Sekunden auf einem
   echten iPhone.

   Für einen App-Clip: `xcrun simctl io <UDID> recordVideo`, danach **erst auf
   feste 30 fps normalisieren** (`-vf fps=30`) — die Zeitangaben der
   Simulator-Aufnahme passen nicht zu ihren Bildern, ein Schnitt auf dem Rohfilm
   landet daneben. Nach dem Tipp großzügig weiterlaufen lassen (25 s), die
   Aufnahme hinkt der Eingabe deutlich hinterher. Den **Fingertipp** malt
   hinterher ffmpeg: eine gefüllte Scheibe plus fünf wachsende Ringe an der
   Tippstelle — iOS zeichnet keinen Zeiger auf, und ohne Markierung springt das
   Teilen-Blatt aus dem Nichts auf.

   Auch hier alles oder nichts: Fehlt einem Highlight die App-Fassung, bekommt
   die App für die ganze Ausgabe die Web-Bilder. Und ein Feature, das es in der
   App gar nicht gibt (2.2.0: das Glossar), bekommt `only="web"` — angekündigt
   wird nur, was man auf dem eigenen Gerät auch findet.

---

## Einen Fehler nachsehen, den ein Nutzer gemeldet hat

| Schritt | Datei |
|---|---|
| Liste ansehen | Admin-Panel → *Fehler* (`GET /api/admin/errors`) |
| Woher er kommt | Spalte *Herkunft*: `server` = unbehandelte Ausnahme, `browser` = gemeldet vom Frontend |
| Was gespeichert wird | `kern/fehler.py` — und `tests/test_fehlersammler.py` für das, was nicht |
| Erledigt | Haken in der Zeile (`POST /api/admin/errors/{id}/resolve`); taucht er wieder auf, springt er zurück auf offen |

**Was dich fängt:** `tests/test_fehlersammler.py` (was gespeichert wird und
was nicht, Gruppierung, „nur die erste Meldung"),
`tests/test_endpunkt_schutz.py` (der offene Endpunkt steht mit Begründung in
`OEFFENTLICH`), `web/frontend/lib/fehler-melden.test.ts` (keine Query, kein
Cookie, Deckel je Seite).

## Wenn ein Wächter anschlägt

Er nennt in der Meldung den Befehl, der das Problem behebt. Falls nicht, ist das
ein Fehler im Wächter und gehört behoben — „assert False" kostet die nächste
Person eine halbe Stunde.

**Ein roter Wächter ist fast nie zu streng.** Die Regeln hier stehen alle wegen
eines Ausfalls, den sie einmal nicht verhindert haben; die Kommentare nennen ihn.
Lies ihn, bevor du die Ausnahmeliste erweiterst.
