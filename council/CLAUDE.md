# Regeln für `council/`

Scraper, Parser und der große Rats-Store. Hier stehen nur die Regeln, deren
Verletzung schon einmal Daten unsichtbar gemacht oder einen Cron zerlegt hat.
Alles Übrige: [`../CLAUDE.md`](../CLAUDE.md).

## Vorher: echte Daten holen

Parser und Auswertungen an drei erfundenen Zeilen zu prüfen, sagt nichts über
den Bestand. Ein Abzug der Ratsdaten steht in einem Befehl bereit:

```bash
python scripts/lokale_daten.py hol && python scripts/lokale_daten.py setz
```

Ohne Konten, ohne Personendaten, ohne Embeddings und Anlagen-Rohtexte — aber
mit allem, was die Auswertungen lesen. Näheres in der
Wurzel-[`CLAUDE.md`](../CLAUDE.md).

## Schema und Migration sind ZWEI Stellen

Eine frische Datenbank entsteht aus dem `SCHEMA`-Literal, eine gewachsene
(dev, Prod) ausschließlich aus `_migrate()`. **Wer nur eine der beiden
anfasst, hat einen Fehler gebaut, den kein Test sieht** — lokal und in der CI
ist die DB immer frisch.

- **Neue Spalte:** ins `SCHEMA` *und* als `ALTER TABLE … ADD COLUMN` nach
  `_migrate()`. Der Guard muss **die Spalte selbst** nennen
  (`if "impact" not in cols:`), nicht eine Nachbarspalte — sonst entsteht sie
  auf gewachsenen Datenbanken nie.
- **Index auf eine per Migration ergänzte Spalte** gehört in `_migrate()`,
  niemals ins `SCHEMA`: Das ganze Schema läuft per `executescript` **vor** der
  Migration, der Index fände seine Spalte also noch nicht.
- **Umbenennung:** Paar in die passende Liste (`_GELD_SPALTEN`,
  `_STRUKTUR_SPALTEN`, `_REST_SPALTEN`, `_FACH_SPALTEN`). **Links steht der
  ALTE Name.** Wandert er bei einem Suchen-und-Ersetzen mit, wird das Paar
  `("x", "x")` — still wirkungslos. Dagegen steht ein Wächter, verlass dich
  nicht darauf, dass er jede Form erwischt.
- **Werte umschreiben** (Daten, nicht Spaltennamen) läuft **nach** der
  Spaltenumbenennung: `_werte_umschreiben` prüft auf die Spalte und kehrt
  still zurück, wenn sie noch anders heißt.
- **Tabellenumzug** (`_tabellen_umbenennen`) läuft als einzige Migration
  **vor** dem Schema. Sonst legt `CREATE TABLE IF NOT EXISTS` die neue Tabelle
  leer an, der Zielname ist belegt, und die Daten bleiben für immer unter dem
  alten Namen liegen.

## Register, die man mitpflegen muss

| Liste | Wenn du … | sonst |
|---|---|---|
| `COUNCIL_USER_OWNED_TABLES` | eine konto-gebundene Tabelle anlegst | DSGVO-Löschlücke, roter Test |
| `HERKUNFT_TABELLEN` (`herkunft.py`) | eine Tabelle mit `herkunft_id` anlegst | ihre Belege gelten als verwaist und werden weggeräumt |
| `_DOKUMENT_QUELLEN` | eine neue Dokumentquelle einliest | der Beleg-Chip fällt auf die Startseite zurück |
| `QUELLEN` / `REIHENFOLGE` / `STELLEN` (`finanzquellen.py`) | eine Finanz-Datenart ergänzt | Erkennung und Anzeige kennen sie nicht |
| `QUERY_TYPES`, `RESEARCH_CHANNELS`, `EXTRA_REGELN` (`qa.py`) | einen Fragetyp oder Kanal ergänzt | das Modell darf ihn nicht wählen |
| `POLICY_FIELDS` (`topics.py`) | ein Themenfeld ergänzt | die Klassifikation kennt es nicht |

## Belege: keine Zahl ohne Herkunft

Jeder Finanz-Parser baut eine `Herkunft(art=…, probe=…, label=…, url=…)`.
Ohne Probe lässt sie sich gar nicht erst bauen. Der Schlüssel einer Herkunft
enthält bewusst **kein** `fetched_at` — sonst legte jeder Lauf einen neuen
Datensatz an und die Tabelle wüchse mit der Zahl der Läufe.

Mehrschrittige Ingests laufen in `transaktion(...)`. Bricht ein Cron mitten
drin ab, darf kein halber Jahrgang stehen bleiben.

## Zwei Namensräume, gleiche Wörter

`qa_antwort`, `deep_bericht` und Geschwister sind **gleichzeitig**
Prompt-Schlüssel in `kern/prompts.py`. Ein Suchen-und-Ersetzen über den
blossen String lässt `prompts.get(…)` ins Leere laufen, ohne dass ein Test
rot wird.

Dasselbe gilt über die Sprachgrenze: `qa.py` und
`web/frontend/components/council-qa.tsx` wenden **dieselbe** Regel auf
Zitat-Nummern an. Änderst du sie hier, ändere sie dort mit — sonst laufen
Nummerierung und `cited` auseinander.

## Deutsche Wörter in Regexen

`\bwort\b` trifft im Deutschen fast nichts, weil Komposita die hintere
Wortgrenze verschieben. Grenze nur hinten setzen, und `\w*plan\b` niemals
öffnen — das trifft Bebauungsplan bis Stellenplan.

## Wo eine neue Abfrage hingehört

`council/store.py` trug bis 09/2026 **15.744 Zeilen in einer Klasse** mit 506
Methoden. Der Haushalt ist als erste Ecke heraus:

| Datei | Methoden | Inhalt |
|---|---|---|
| `council/store.py` | 161 | **Kern**: Beschlüsse, Vorlagen, Anlagen, Herkunft, Suche, Embeddings |
| `council/store_schema.py` | 15 | `SCHEMA`, Migration und ihre Vokabulare |
| `council/store_sitzungen.py` | 48 | Termine, Tagesordnungen, Gremien, Wochenvorschau |
| `council/store_haushalt.py` | 136 | Haushalts-Seiten, Lese- UND Schreibseite |
| `council/store_personen.py` | 31 | Ratsmitglieder, Verwaltung, Namensformen, Anwesenheit |
| `council/store_themen.py` | 31 | Entitäten, Aliasse, Steckbriefe, Verwandtschaft |
| `council/store_orte.py` | 33 | Katalog, Geocodierung, Stadtteile, Kartenpunkte |
| `council/store_wortbeitraege.py` | 21 | Wortbeiträge und Videos |
| `council/store_quiz.py` | 13 | die Quiz-Abfragen |
| `council/store_presse.py` | 10 | Pressemitteilungen und Beteiligungen |
| `council/store_fundstuecke.py` | 10 | Fundstücke, Rückblicke, Social-Text |
| `council/geld/*.py` | 24 | je eine Facette der KI-Frage |
| `council/store_helfer.py` | — | die paar Funktionen, die mehrere Ecken brauchen |

Alle landen über Mixins in derselben `CouncilStore`; an den Aufrufstellen
ändert sich nichts. `store.py` ist damit von 15.744 auf 4.786 Zeilen und von
506 auf 161 eigene Methoden geschrumpft.

`store_helfer.py` gibt es, weil ein Mixin in einer eigenen Datei nichts aus
`store.py` importieren kann — das wäre ein Ring. Was mehrere Ecken brauchen und
keiner gehört, wandert dorthin.
| `council/geld/*.py` | je eine Facette der KI-Frage, je eine Store-Methode |

**Die Wurzeln müssen BEIDE Seiten treffen.** Der erste Haushalts-Schnitt ging
nur von den Endpunkten aus — 55 `save_*`-Methoden blieben deshalb im Kern
zurück, obwohl sie nirgendwo sonst gebraucht werden. Zu den Wurzeln gehören
also die Endpunkte **und** die Ingest-Module und -Skripte der Ecke.

Der Schnitt läuft je Ecke über den **Aufrufkegel**, nicht über ein
Namensmuster: was die Endpunkte dieser Ecke am `store` aufrufen, plus was
diese Methoden ihrerseits an `self` rufen — abzüglich der allgemeinen Helfer,
die die Ecke zwar benutzt, die ihr aber nicht gehören. Bei den Orten waren das
sechs Beschluss-Helfer (`_decision_where`, `search_decisions`, …); gemessen
ruft keine der umgezogenen Methoden sie an, die Grenze läuft also wirklich
dazwischen.

Alle drei landen über Mixins in derselben `CouncilStore`, an den Aufrufstellen
ändert sich also nichts: `store.get_haushalt(...)` heißt überall weiter so.

**Neue Abfrage einer Fachecke gehört in deren Modul**, nicht in die Mitte.
`tests/test_store_groesse.py` hält die Zahl der Methoden in `CouncilStore`
fest; sie darf schrumpfen und nicht wachsen. Gehört eine Abfrage wirklich in
die Mitte, wird die Zahl dort angehoben — mit einem Satz, warum.

**Schema und Migrationen gehören der Datenbank als Ganzem**, nicht einer
Fach-Ecke. Sie liegen seit 09/2026 trotzdem in einer eigenen Datei
(`store_schema.py`) — `_migrate` allein war 2.458 Zeilen, ein Viertel des
Stores in einer Methode. Das ist keine Ecke, sondern dieselbe Sache in einer
eigenen Datei; die Reihenfolge der Schritte ist unverändert.

**Wächter, die Quelltext lesen, lesen `council/store*.py` — alle.** Vier Tests
suchten an der festen Datei `store.py`; nach dem Umzug fanden sie 39 statt 84
Migrationspaaren und waren trotzdem grün, bis der Zählwert-Test anschlug.
