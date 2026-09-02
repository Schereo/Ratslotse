# Regeln für `council/`

Scraper, Parser und der große Rats-Store. Hier stehen nur die Regeln, deren
Verletzung schon einmal Daten unsichtbar gemacht oder einen Cron zerlegt hat.
Alles Übrige: [`../CLAUDE.md`](../CLAUDE.md).

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
