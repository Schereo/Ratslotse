# Regeln für `tests/`

Die Suite ist in diesem Repo nicht nur Regressionsschutz, sondern das
Werkzeug, mit dem Konventionen durchgesetzt werden. Allgemeines:
[`../CLAUDE.md`](../CLAUDE.md).

## Wächter statt Bitten im Review

Wenn eine Regel wichtig genug ist, dass ihr Bruch etwas kaputt macht, gehört
sie als Test hierher und nicht in eine Prosa-Zeile, die niemand liest. Das
Muster steht in `test_api_vertrag.py`: eine ausdrückliche Ausnahmeliste, ein
Test, der die Liste gegen die Wirklichkeit hält, und ein zweiter, der meldet,
wenn ein Eintrag überflüssig geworden ist.

**Eine Ausnahmeliste, die nur wächst, ist kaputt.** Deshalb prüft jeder
Wächter beide Richtungen: Fehlt etwas, und steht etwas drin, das es nicht mehr
braucht.

Die Fehlermeldung nennt den Befehl, der das Problem behebt. Ein Wächter, der
nur „assert False" sagt, kostet die nächste Person eine halbe Stunde.

## Die Suite fasst nichts Echtes an

`conftest.py` erzwingt leere Schlüssel für Mail und LLM und schaltet das Lesen
der `.env` global ab. Der Grund ist gemessen: Ein Test, der einen Schlüssel per
`monkeypatch` entfernte, machte Platz, und der nächste Modul-Import füllte ihn
aus der Entwickler-`.env` mit einem echten Wert nach — die Suite verschickte
lokal echte Mail.

Wer einen Test schreibt, der eine Modellantwort braucht, mockt sie. Ein Test,
der nur mit Netz grün ist, ist kein Test.

## Datenbank-Tests laufen gegen eine frische DB — das ist die Lücke

Lokal und in der CI entsteht jede Datenbank aus dem Schema. Auf dev und Prod
entsteht sie aus der Migration. **Ein Test, der nur die frische DB anfasst,
sieht Migrationsfehler nie.** Genau daran hing die Mehrzahl der Fixes im
Sommer 2026.

Wer eine Migration schreibt, prüft sie deshalb gegen einen **gewachsenen**
Stand: eine Datenbank im alten Schema anlegen, migrieren, und Spalte für
Spalte mit einer frisch angelegten vergleichen. Und zweimal migrieren — eine
Migration, die beim zweiten Lauf stolpert, bricht den nächsten Deploy.

`test_migration_bestand.py` tut das automatisch, gegen die eingecheckten
Schema-Auszüge von dev **und** Prod — und seit 09/2026 auch mit **zwei Zeilen
je Tabelle**. Der Unterschied ist gemessen: Auf dem leeren Auszug fasst kein
einziger Migrationsschritt eine Zeile an, mit Inhalt sind es drei. Alles
Inhaltsabhängige — eine Werte-Migration auf einem schon vergebenen Zielwert,
ein `NOT NULL` ohne Vorgabewert, ein Umzug, der auf zwei gefüllte Tabellen
trifft — war vorher unerreichbar. Zwei Zeilen und nicht eine, weil ein
doppelter Zielwert sonst gar nicht entstehen kann.

## Echte Daten, wo sie fehlen

Die Suite läuft absichtlich gegen leere Datenbanken — das hält sie schnell und
unabhängig. Für alles, was erst an Menge auffällt (Paginierung, lange Titel,
Sonderfälle im Bestand), gibt es den Abzug: `python scripts/lokale_daten.py
hol && setz` holt die Ratsdaten von dev, `python scripts/saat_konten.py` legt
erfundene Konten dazu. Beides steht in der Wurzel-`CLAUDE.md`.

Ein Test, der eine echte Datenbank braucht, hängt an einer **eigenen**
Umgebungsvariable (`RATSLOTSE_MESS_DB`), nicht an `COUNCIL_DB` — die zeigt im
Testlauf immer auf eine leere Wegwerf-Datei, eine Bedingung darauf übersprang
nie und riss den Lauf um. `test_testpfade.py` hält das fest.

## Die Suite läuft parallel — kein Modul redet über den Prozess

Der Lauf fährt `pytest -n auto` (in der CI und in `scripts/pruefe.py`); jeder
xdist-Arbeiter ist ein eigener Prozess und importiert eine **andere** Teilmenge
der Module in anderer Reihenfolge. Alles, was zwei Testmodule über eine
Prozessvariable verabreden, wird damit zum Zufall.

Bis 09/2026 taten sie genau das: Jedes Backend-Testmodul setzte beim Import
`os.environ.setdefault("COUNCIL_DB", …)` auf ein eigenes tempfile-Verzeichnis.
`setdefault` heißt „nimm, was schon da ist" — seriell entschied die feste
Import-Reihenfolge, parallel entschied der Zufall, und ein Modul schrieb seine
Zeilen in eine andere Datei, als die App las.

Deshalb setzt **`conftest.py`** diese Werte, einmal je Prozess:
`RATSLOTSE_DB`, `COUNCIL_DB`, `WAHLABEND_HISTORY_FILE`, `WEB_JWT_SECRET`,
`WEB_ADMIN_EMAIL`, `COOKIE_SECURE`, `DISABLE_RATE_LIMIT`. Ein Testmodul setzt
sie nicht mehr — `test_testpfade.py` meldet jede neue Zuweisung.

Braucht ein Test einen anderen Wert, nimmt er `monkeypatch.setenv` (wird nach
dem Test zurückgenommen). Braucht er eine eigene Datenbank, legt er sie unter
`tmp_path` an und hängt sie über `app.dependency_overrides` ein — nicht über
die Umgebung: `web/backend/app/main.py` ruft `get_settings()` schon beim
Import, und `get_settings` ist `lru_cache`. Wer die Variable danach umsetzt,
ändert nur seine eigene Sicht, nicht die der App.

## Kein Test gegen die eigene Fixture

Wenn beide Seiten einer Schnittstelle ihre Testdaten selbst schreiben, prüfen
sie nur, dass sie sich selbst verstehen. Ein vergessenes Feld ließ so beide
Frontends „0 Tagesordnungspunkte" anzeigen, bei grüner Suite auf beiden
Seiten. Antwortformen also gegen den Vertrag prüfen, nicht gegen eine Kopie.
