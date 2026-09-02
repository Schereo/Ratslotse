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

## Echte Daten, wo sie fehlen

Die Suite läuft absichtlich gegen leere Datenbanken — das hält sie schnell und
unabhängig. Für alles, was erst an Menge auffällt (Paginierung, lange Titel,
Sonderfälle im Bestand), gibt es den Abzug: `python scripts/lokale_daten.py
hol && setz` holt die Ratsdaten von dev, `python scripts/saat_konten.py` legt
erfundene Konten dazu. Beides steht in der Wurzel-`CLAUDE.md`.

Ein Test, der eine echte Datenbank braucht, hängt an einer **eigenen**
Umgebungsvariable, nicht an `COUNCIL_DB` — die setzen drei Testmodule beim
Import selbst, eine Bedingung darauf übersprang nie und riss den Lauf um.

## Kein Test gegen die eigene Fixture

Wenn beide Seiten einer Schnittstelle ihre Testdaten selbst schreiben, prüfen
sie nur, dass sie sich selbst verstehen. Ein vergessenes Feld ließ so beide
Frontends „0 Tagesordnungspunkte" anzeigen, bei grüner Suite auf beiden
Seiten. Antwortformen also gegen den Vertrag prüfen, nicht gegen eine Kopie.
