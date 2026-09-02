# Regeln für `kern/`

Geteilte Infrastruktur: Konten-Store, Benachrichtigungen, LLM-Client, Prompts,
Cron-Rahmen. Was hier bricht, bricht überall. Allgemeines:
[`../CLAUDE.md`](../CLAUDE.md).

## Benachrichtigungen gehen NUR über `notify.einreihen`

`store.enqueue_notification` direkt aufzurufen umgeht auf einen Schlag den
Aus-Schalter des Kontos, die Nachtruhe und die Tagesgrenze. Für einen neuen
Meldeanlass gehören vier Dinge zusammen:

1. Konstante `N…` **und** Eintrag in `NOTIFY_DEFAULTS` — fehlt er, gilt der
   Anlass als gewünscht und geht ungefragt raus.
2. Eintrag in `NOTIFY_LABELS`, sonst fehlt der Schalter in den Einstellungen.
3. `url` ist Pflicht und muss ein **App-Pfad** sein (`/…`). Eine externe
   Ratsinfo-Adresse lässt den Tap wortlos nichts tun.
4. Optional `NOTIFY_PARENT` (Unteroption) und `TERMINGEBUNDEN` (eigener
   Tagestopf).

Eine leere Empfängerliste heißt: Es ist **nichts** rausgegangen. `sent_at`
darf dann nicht gesetzt werden, sonst verschwindet eine Meldung bei einem
Zustell-Ausfall lautlos für immer.

## LLM-Aufrufe

- Immer über `llm.chat_complete` / `chat_stream`, nie ein eigener Client. Dort
  hängen Auth, Retry, das DSGVO-Provider-Routing und die Kostenzählung.
- `_feature="…"` mitgeben. Ohne den Wert gibt es kein Kostentracking, und ein
  Name ohne Gegenstück im Admin-Frontend macht einen Test rot.
- **Neues Modell heißt: Eintrag in `MODEL_PARAMS`.** Bei Reasoning-Modellen
  ohne Token-Floor kommt die Antwort sporadisch leer zurück
  (`finish_reason='length'`), und zwar ohne Fehler.
- Ein Inhaltsfilter-Treffer überspringt **einen Datensatz**, nicht den Lauf.

## Prompts sind Code

Sie stehen in `prompts.py::DEFAULTS` und werden über `prompts.get(key)` bzw.
`prompts.render(key, **kwargs)` geholt. Geschweifte Klammern, die wörtlich
gemeint sind (JSON-Beispiele), gehören als `{{` und `}}` verdoppelt.

Ein DB-Override ist ein stiller Killer für jede Umbenennung: Das Modell
liefert weiter den alten Namen, die Extraktion bleibt leer, es gibt keinen
Fehler. Vor einem Umbau also prüfen, ob Overrides existieren.

## Cron-Jobs

Jedes Skript läuft über `alerts.run_guarded("<key>", main)`. Ohne den Rahmen
gibt es keinen Alarm, keinen Traceback und keinen `job_runs`-Eintrag — der Job
kann monatelang stumm tot sein. Der Key muss **exakt** dem Eintrag in
`jobs.py::JOBS` entsprechen; dort stehen auch `schedule` und `max_age_h`. Wer
die crontab auf dem Server ändert, zieht sie hier nach, sonst schlägt die
Überfällig-Ampel falsch an.

`main()` gibt ein `dict` zurück — es landet als Kennzahlen in `job_runs` und im
Admin-Panel. Eine Kennzahl, die dauerhaft 0 ist, ist ein Ausfall und kein
Zustand.

## Schema und Migration

Dieselbe Regel wie in [`../council/CLAUDE.md`](../council/CLAUDE.md): Spalte
ins `SCHEMA` **und** nach `_migrate()`, Guard nennt die Spalte selbst (ein
AST-Wächter erzwingt das hier), Umbenennung zuerst, Werte danach. Eine neue
konto-gebundene Tabelle gehört in `USER_OWNED_TABLES`.
