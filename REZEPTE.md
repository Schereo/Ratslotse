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
Die zwei Dinge, die man dabei vergisst:

1. `python3 scripts/ios_vertrag.py --ausgeliefert` — bricht die App im Store?
2. Nach einem Fix auf `main`: zurück nach `dev` mergen.

---

## Wenn ein Wächter anschlägt

Er nennt in der Meldung den Befehl, der das Problem behebt. Falls nicht, ist das
ein Fehler im Wächter und gehört behoben — „assert False" kostet die nächste
Person eine halbe Stunde.

**Ein roter Wächter ist fast nie zu streng.** Die Regeln hier stehen alle wegen
eines Ausfalls, den sie einmal nicht verhindert haben; die Kommentare nennen ihn.
Lies ihn, bevor du die Ausnahmeliste erweiterst.
