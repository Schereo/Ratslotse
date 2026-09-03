# Regeln für `scripts/`

Cron-Jobs und Ops-Werkzeuge. Siehe auch [`README.md`](README.md) und
[`../CLAUDE.md`](../CLAUDE.md).

## Ein neuer Job ist erst fertig, wenn er registriert ist

1. Entrypoint über `run_guarded("<key>", main)` aus `kern/alerts.py`. Ohne ihn
   läuft der Job unbeobachtet: kein Alarm an `ALERT_EMAIL`, kein Eintrag in
   `job_runs`, kein Traceback.
2. Eintrag in `kern/jobs.py::JOBS` mit demselben Key, dazu `label`,
   `description`, `schedule`, `max_age_h`. Ein Job ohne Registry-Eintrag (und
   umgekehrt) macht `tests/test_jobs.py` rot.
3. Der Zeitplan selbst steht in der crontab auf dem Server, nicht im Repo —
   `schedule` in `jobs.py` ist die Kopie, gegen die die Überfällig-Ampel
   rechnet. Beide auseinanderlaufen zu lassen ist der häufigste Fehler.

`main()` gibt ein `dict` mit Kennzahlen zurück. Wähle Zahlen, die auffallen,
wenn der Job zwar läuft, aber nichts mehr findet.

## Läufe müssen wiederholbar sein

Ein Ops-Skript wird im Zweifel zweimal gestartet. Schreibende Läufe gehören
in eine Transaktion und müssen idempotent sein; ein zweiter Lauf darf keine
Dubletten anlegen und keine Korrektur zurückdrehen.

Wer massenhaft schreibt, baut zuerst den Trockenlauf. Der Ops-Default in
diesem Repo ist Bericht, nicht Ausführung — wer das umdreht, sagt es im
Namen des Schalters.

## Nicht in `data/` greifen, ohne den Store zu fragen

Direkte `sqlite3.connect`-Aufrufe gibt es nur an wenigen, begründeten Stellen.
Neue gehören nicht dazu: Über den Store laufen Schema, Migration und
Transaktionsverhalten mit.

## Was auf dem Server anders ist

Die Datenbanken heißen dort anders, als man denkt, und `data/` wird beim
Deploy **nicht** überschrieben. Ein Skript, das die falsche Datei öffnet,
legt sie stillschweigend neu an und meldet dann null Treffer statt eines
Fehlers. Pfade also aus der Konfiguration nehmen, nie hart schreiben.
