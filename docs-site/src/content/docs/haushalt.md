---
title: Stadtfinanzen
description: Der Haushalts-Bereich — woher die Zahlen kommen, welche redaktionell sind, und was bewusst fehlt.
---

Der Haushalt ist der sperrigste Stoff, den Ratslotse zeigt: Doppik-Vokabular,
Millionenbeträge ohne Bezugsgröße, Zuständigkeiten quer über drei staatliche
Ebenen. Der Bereich unter `/haushalt` übersetzt ihn — und macht dabei an jeder
Stelle sichtbar, welche Zahl amtlich ist, welche wir gerechnet haben und
welche schlicht fehlt.

## Die Seiten

| Route | Inhalt |
|---|---|
| `/haushalt` | Übersicht: Kernzahlen, Rücklagen-Reichweite, Geldfluss (Balken oder 100-Euro-Ansicht), Zeitreihe, Bereichskarten |
| `/haushalt/bereich?name=<slug>` | Dossier je Teilhaushalt: Brutto/Netto, Kostendeckung, Brutto-gegen-Netto-Vergleich, Entwicklung |
| `/haushalt/einnahmen` | Alle Einnahmequellen mit Spielraum-Kodierung (frei / begrenzt / kein Einfluss) |
| `/haushalt/steuer?art=<slug>` | Steckbrief je Einnahmeart: „Wer entscheidet was", Ist-Kurve, Hebesatz, Ein-Punkt-Überschlag |
| `/haushalt/produkte[?nr=<produkt_nr>]` | „Was kostet eigentlich …?" — Produktsuche mit Filtern (Amt, Spielraum); `nr` öffnet den Steckbrief |
| `/haushalt/pflicht` | Muss oder kann — Teilhaushalte nach Gestaltungsspielraum |
| `/haushalt/labor` | Was-wäre-wenn: Hebesatz-Regler und Kürzungen, jede Bewegung in Mio., € je Einwohner und Anteil an der Lücke; dauerhaft sichtbare Gegenrechnung |
| `/haushalt/pruefung` | Was das Rechnungsprüfungsamt beanstandet: alle Feststellungen der Schlussberichte im Wortlaut, mit Textziffer, Seite und Deeplink; dazu die Ketten über die Jahrgänge |
| `/haushalt/konzern` | Der Konzern Stadt: Kernverwaltung gegen Gesamtabschluss über elf Jahrgänge, Aufschlüsselung nach Aufgabenträgern, Gegenprobe gegen den Jahresabschluss |
| `/haushalt/vergleich` | Städtevergleich: Steuerkraft, Hebesätze und Steuereinnahmekraft der acht kreisfreien Städte aus der amtlichen Statistik — und die Erklärung, warum Ausgaben und Personal **nicht** verglichen werden |

Query-Parameter statt dynamischer Segmente, weil der Capacitor-Export die
Slugs zur Bauzeit nicht kennt — dieselbe Konvention wie `/council/decision?id=`.

## Woher die Daten kommen

Fast alles läuft über **einen** Endpunkt: `GET /api/council/haushalt` liefert
Planjahre, Ist-Steuern, Steuerkraft und die Einwohnerzahl in einem Aufruf.
Nur die Prüfungsfeststellungen hängen an einem eigenen
(`GET /api/council/haushalt/pruefberichte`) — sie sind eine Viertel-Megabyte
Prosa und haben auf Seiten, die sie nicht zeigen, nichts zu suchen.

| Tabelle | Inhalt | Quelle | Ingest |
|---|---|---|---|
| `council_haushalt` | Ergebnishaushalt je Teilhaushalt, 2020–2026 (**Plan**) | Beschlossene Haushaltsplan-PDFs; 2024 aus dem Open-Data-CSV | `scripts/ingest_haushalt.py` |
| `council_steuern` | Steuereinnahmen je Art seit 1998 (**Ist**) | Open-Data-Portal, Datensatz 1104 | `scripts/ingest_finanzen_opendata.py` |
| `council_steuerkraft` | Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr seit 1993 (Jahreszahl beim Einlesen korrigiert, s. u.) | Open-Data-Portal, Datensatz 1106 | dito |
| `council_einwohner` | Einwohnerzahl je Jahr seit 2010 | Open-Data-Portal, Datensatz 1102 | dito |
| `council_ergebnisrechnung` | Ansatz, Plan **und** Ergebnis je Posten — gesamt und je Teilhaushalt, 2017–2024 | Jahresabschlüsse — **Anlagen im RIS** | `scripts/ingest_finanzberichte.py` |
| `council_ergebnishaushalt` | Dieselben Posten für Jahre **ohne** Abschluss, 2019–2026 — je Zeile `art` (`ansatz` / `finanzplanung`) und `plan_jahrgang` | Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — **Anlagen im RIS** | dito |
| `council_abweichungsgruende` | Warum ein Posten vom Plan abwich (Abschnitt 6.3.1), 45 Einträge | dito | dito |
| `council_pruefbericht_quellen` | **Fundstelle** des RPA-Schlussberichts je Jahrgang (eine Zeile je Jahr) | dito | dito |
| `council_produkte` | Produktebene: was einzelne Aufgaben kosten — plus Steckbrief (Kurzbeschreibung, Auftragsgrundlage, Beeinflussbarkeit, Wirkungskreis, Zielgruppe) | Teilhaushalts-Pläne — **Anlagen im RIS** | dito |
| `council_pruefberichte` | Prüfungsfeststellungen 2017–2023, eine Zeile je Randmarke | Schlussberichte des Rechnungsprüfungsamts — **Anlagen im RIS** | `scripts/ingest_pruefberichte.py` |
| `council_konzern_posten` | Gesamtergebnisrechnung des **Konzerns** je Posten, 2014–2024 | Konsolidierte Gesamtabschlüsse — **Anlagen im RIS** | `scripts/ingest_konzernabschluss.py` |
| `council_konzern_traeger` | Dieselben Summen je Aufgabenträger (Kernverwaltung, Klinikum, Eigenbetriebe …), 2017–2024, in **TEUR** | dito | dito |

:::note[Zwei Tabellen zu denselben Berichten]
`council_pruefbericht_quellen` hält die **Fundstelle** des Schlussberichts
(eine Zeile je Jahrgang, für den Verweis „geprüft → Schlussbericht"),
`council_pruefberichte` die **einzelnen Feststellungen** daraus (eine Zeile je
Randmarke). Zwei Ebenen, zwei Tabellen — die Namen halten sie auseinander.
:::

Alle Ingests sind idempotent. Die vier Schichten aus dem **Ratsinformations-
system** zieht seit 08/2026 ein Cron von allein nach (siehe unten); die
Ingest-Skripte bleiben der Weg von Hand, wenn ein verbesserter Parser über den
**Bestand** laufen soll. Die Plan- und Open-Data-Schichten (`council_haushalt`,
`council_steuern`, `council_steuerkraft`, `council_einwohner`) kommen per
Download von oldenburg.de und bleiben Handarbeit.

## Herkunft: woher jede einzelne Zahl stammt

Jede Zeile der neun Tabellen oben trägt eine `herkunft_id`. Sie zeigt auf
**`council_herkunft`** — einen Datensatz je Dokument-und-Abschnitt mit:

| Feld | Was drinsteht | Beispiel |
|---|---|---|
| `art` | `ris` · `opendata` · `stadt` | `ris` |
| `dokument_id` | `council_anlagen.document_id` — der **stabile Anker** | `280863` |
| `label` / `url` | wie das Dokument heißt und wo es liegt | „Jahresabschluss 2024 …" |
| `fundstelle` | wo **im** Dokument gelesen wurde | „Abschnitt 6.3.1 — Erläuterungen …" |
| `seite` | Seitenzahl, wo das Dokument eine trägt | `161` |
| `probe` | die bestandene(n) Rechenprobe(n) | `strukturprobe,vorjahreskette` |
| `probe_ergebnis` | ihr Messwert | „0.00 % Abweichung zur Gesamtrechnung" |
| `stand` | Stichtag des **Inhalts**, nicht des Abrufs | „Jahresabschluss 2024" |
| `fetched_at` | zuletzt bestätigt (wandert nur vorwärts) | |

Warum eine eigene Tabelle statt Spalten je Zieltabelle — die Begründung steht
ausführlich im Modulkopf von `council/herkunft.py`, kurz:

1. **Eine Zieltabelle trägt Zeilen aus mehreren Dokumenten.** Bei den
   Beteiligungen ist das der Normalfall: dieselbe Kennzahl im
   Konzernabschluss, im Einzelabschluss der Gesellschaft und im
   Beteiligungsbericht, mit verschiedenen Stichtagen und
   Konsolidierungsstufen. Verschiedene Dokumente heißen automatisch
   verschiedene Herkunfts-Datensätze — ohne dass eine Tabelle dafür etwas
   wissen muss.
2. **Ein neues Herkunftsfeld darf nicht neun `ALTER TABLE` kosten.**
3. **Wiederholung.** Ein Jahresabschluss-Jahrgang schreibt rund 200 Zeilen aus
   demselben Abschnitt hinter derselben Probe.

Die alten Spalten (`quelle_label`, `quelle_url`, `source_url`) **bleiben** und
werden weiter aus derselben Angabe gefüllt. Sie zu entfernen hieße, neun
Tabellen neu zu schreiben, darunter vier, deren Inhalt nur über einen Download
von oldenburg.de wiederzubeschaffen wäre — kosmetischer Gewinn, echtes Risiko.

`GET /api/council/haushalt` liefert die Datensätze als `herkunft`, nach ID
nachschlagbar, samt eines Erklärsatzes je Probe für die Oberfläche.

:::note[Was der Altbestand mitbringt — und was nicht]
Das Nachrüsten übernimmt aus den alten Feldern Label und URL und löst über die
URL zusätzlich die `document_id` in `council_anlagen` auf. **Fundstelle und
Probe bleiben leer bzw. tragen `unbekannt`:** Der Altbestand hält nicht fest,
an welchem Abschnitt er gelesen wurde und welche Probe er bestanden hat. Das
zu erfinden — „steht schon meistens in Abschnitt 6.3.1" — wäre genau die Sorte
Angabe, die diese Umstellung abschaffen soll. Der nächste Einlese-Lauf trägt
beides nach, weil er den Jahrgang ohnehin ersetzt; `herkunft_aufraeumen()`
räumt die abgelösten Datensätze weg.
:::

### Was ein neuer Parser tun muss

Drei Schritte, mehr nicht:

1. **Eine `Herkunft` bauen.** `art` und `probe` sind Pflicht — eine Herkunft
   ohne Probe lässt sich nicht konstruieren (`ValueError`). Trägt die Quelle
   wirklich keine Rechenprobe, ist das ausdrücklich zu sagen:
   `probe=herkunft.UNGEPRUEFT`. Dazu mindestens ein Verweis (`dokument_id`
   oder `url`), und so viel von `fundstelle`, `seite`, `probe_ergebnis`,
   `stand`, wie das Dokument hergibt. Leer ist erlaubt, geraten nicht.
2. **Sie an die `save_*`-Methode geben** — sie steht dort, wo früher
   `label, url` bzw. `source_url` standen. Der Store trägt sie ein
   (`merke_herkunft`, idempotent über einen Fingerabdruck der Inhaltsfelder)
   und verknüpft die Zeilen.
3. **Die Zieltabelle in `herkunft.HERKUNFT_TABELLEN` eintragen.** Damit
   bekommt sie ihre `herkunft_id`-Spalte beim nächsten Öffnen, wird beim
   Nachrüsten mitversorgt, und `store.herkunft_luecken()` meldet ab sofort
   jede Zeile darin, die ohne Herkunft geschrieben wurde. Die Ingest-Skripte
   geben das nach jedem Lauf aus; leer ist der Sollzustand.

Eine **neue Rechenprobe** braucht einen Eintrag in `herkunft.PROBEN` — Name
plus einen Satz für Leserinnen, denn der Satz landet über die API im Beleg und
beantwortet dort „warum soll ich das glauben?". Ein unbekannter Probenname
fliegt beim Bauen der `Herkunft` auf, nicht erst in der Datenbank.

:::tip[Herkunft ist dokumentweit — was je Zeile schwankt, bleibt je Zeile]
Die Prüfungsfeststellungen führen ihre **Textziffer** und ihre **Seite**
selbst; das ist ihre Fundstelle, und sie ist für jede Feststellung eine
andere. Die Herkunft beschreibt das Dokument und den Abschnitt, aus dem ein
Lauf gelesen hat — nicht die Zeile darin. Wer beides vermischt, bekommt so
viele Herkunfts-Datensätze wie Datenzeilen und hat nichts gewonnen.
:::

:::tip[Eine Einheit wird einmal versorgt — und zwar vom ersten Dokument]
Dieselbe Zeile kann in **zwei** Anlagen stehen: Sechs (Jahrgang,
Teilhaushalt)-Paare hängen an zwei Vorlagen — dieselbe PDF-Datei, ein zweites
Mal unter einem anderen Tagesordnungspunkt hochgeladen. Da die `save_*`-
Methoden bei gleichem Schlüssel die ganze Zeile ersetzen, gewinnt sonst das
zuletzt gelesene Dokument, und welches das ist, entscheidet die Sortierung der
Kandidaten. Das ist keine Kosmetik: Es steht danach in der Zeile, und
„TOP 5 - Anlage III - THH 08“ sagt außerhalb seiner Sitzung nichts.

`lies_teilhaushalte` überspringt deshalb, was schon versorgt ist; maßgeblich
ist das Dokument mit der **kleinsten `document_id`** — die getfile-Nummer des
Ratsinformationssystems steigt mit jedem Upload, das erste Dokument ist also
die Anlage der Haushaltsvorlage selbst. Weichen die Zahlen des zweiten
Dokuments ab, wird **gemeldet statt überschrieben**: Ein Nachtragshaushalt,
der einen Ansatz wirklich ändert, ist eine Entscheidung für einen Menschen,
nicht für einen unbeaufsichtigten Lauf.
:::

:::caution[Plan ist nicht Ist]
`council_haushalt` enthält **Planwerte** (was der Rat beschlossen hat),
`council_steuern` **Ist-Werte** (was tatsächlich geflossen ist). Die beiden
dürfen nie in einem Satz vermischt werden — im Frontend stehen sie in
getrennten Bausteinen, und die Prompt-Bausteine der KI-Frage
(`_haushalt_block`, `_steuern_block`) sagen dem Modell ausdrücklich, was sie
sind.
:::

## Der Bereich hält sich selbst aktuell

Fünf Datenschichten, jede einmal von Hand eingelesen — ohne Cron veraltet der
ganze Bereich still, sobald niemand mehr daran denkt. `check_finanzdaten.py`
(alle zwei Wochen) nimmt das ab.

**Bestandsgesteuert, nicht kalendergesteuert.** Der Job fragt nicht „ist es
September?", sondern *„welche Einheit fehlt mir, und liegt inzwischen ein
Dokument dafür vor?"*. Ein Job, der im September nach dem Jahresabschluss
sucht, bricht in dem Jahr, in dem die Stadt später dran ist. So ist der Takt
egal: Verspätungen, Nachtragshaushalte und nachgereichte Prüfberichte sind
automatisch abgedeckt, und der Job darf beliebig oft laufen.

:::danger[Einheit, nicht Jahrgang]
Die kleinste Einheit ist **nicht** der Jahrgang, sondern das Dokument
beziehungsweise die Ebene: Ein Produkt-Jahrgang verteilt sich auf rund neun
Teilhaushalts-Anlagen, ein Jahresabschluss auf zwei Ebenen (Gesamtrechnung und
Teil-Ergebnisrechnungen). **„Jahr ist da" heißt nicht „Jahr ist vollständig".**

Und die Teile kommen nicht gleichzeitig. `check_protocols.py` legt eine Anlage
zunächst ohne Volltext an (`n_pages = 0`, `status = 'listed'`); den Text holt
`backfill_anlagen_texte.py` später und in Tranchen. Zwischen zwei Läufen liegt
also regelmäßig ein Jahrgang, von dem die Hälfte lesbar ist — kein Sonderfall,
sondern Normalbetrieb. Ein Bestand je Jahrgang sperrt ihn nach dem ersten
Dokument und verliert die übrigen acht **dauerhaft**, ohne dass etwas auffällt:
Das Jahr steht in der Tabelle, ist also nicht überfällig, und keine Meldung
schlägt an.

Deshalb führt `council/finanzquellen.py` den Bestand als Menge von Einheiten —
Tupel, deren erstes Element immer der Jahrgang ist:

| Datenart | Einheit | Beispiel |
|---|---|---|
| Jahresabschluss | Ebene | `(2024, "gesamt")`, `(2024, "teilhaushalte")` |
| Teilhaushalts-Pläne | Teilhaushalt | `(2024, 7)` |
| Schlussbericht, Prüfungsfeststellungen, Haushaltsplan | der Jahrgang selbst | `(2024,)` |

Den Schlüssel eines Teilhaushalts-Plans liefern Textkopf und Label zusammen:
der Jahrgang aus der ersten Ansatzspalte, die Nummer aus `THH\s*0*(\d+)` im
Label. Gegen alle 79 Teilhaushalts-Anlagen des Bestands geprüft — das Paar
trifft immer genau das, was `parse_teilergebnishaushalt` am Ende vergibt.
:::

Aus acht Jahrgängen Sitzungsdaten (`council_sessions.session_date` über
`council_agenda_items`) ergibt sich der Rhythmus der Stadt:

| Was | Wann im Rat | Ausnahmen |
|---|---|---|
| Jahresabschluss + RPA-Schlussbericht + Rechenschaftsbericht | **Anfang September** | 1× August |
| Haushaltsplan mit Gesamtergebnishaushalt und Teilhaushalten | **Anfang Oktober** | 1× November |

Der Monat steuert **nicht** die Suche, sondern nur die Meldung: Bleibt ein
Jahrgang länger als vier Wochen über seinen üblichen Monat hinaus aus, geht ein
Hinweis an `ALERT_EMAIL` — kein Fehler, sondern die Frage, ob die Stadt spät
dran ist oder ein Erkennungsmuster nicht mehr greift. Die Mail unterscheidet
beides: Liegt ein passendes Dokument vor und wird trotzdem nichts übernommen,
steht das ausdrücklich drin. Gemeldet wird nur, wenn sich die Liste gegenüber
dem letzten Lauf geändert hat (Vergleich über `job_runs`) — alle vierzehn Tage
dieselbe Mail wäre eine, die niemand mehr liest.

:::note[Woher der Jahrgang kommt]
`council_anlagen.fetched_at` trägt bei **allen** Finanzdokumenten den
10.08.2026 — den Tag des Volltext-Backfills. Als Veröffentlichungsdatum ist das
Feld wertlos. Der Jahrgang kommt deshalb aus dem Dokument selbst: aus dem Label
(Jahresabschluss), dem Textanfang (Prüfberichte) oder der ersten Ansatzspalte
im Tabellenkopf (Teilhaushalts-Pläne).

Bei den Teilhaushalts-Plänen ist das nicht dasselbe wie die Jahreszahl im
Dateinamen: „2024 007 IVw THH01" ist der Haushaltsplan **2024**, seine erste
Ansatzspalte trägt **2023** — und genau die übernimmt der Parser (alles danach
ist mittelfristige Finanzplanung). Wer hier das Label läse, suchte einen
Jahrgang, den die Tabelle nie zurückgibt.
:::

### Drei Regeln, die ihn unbeaufsichtigt tragen

1. **Er lädt nichts herunter.** Die Anlagen kommen über `check_protocols.py`
   ins System; der Job liest nur aus, was schon in `council_anlagen` liegt.
   Zwei Wege zu denselben Daten wären einer zu viel. Deshalb deckt er
   `council_haushalt` und die Open-Data-Schichten **nicht** ab — ihr Ausbleiben
   meldet er trotzdem, damit `ingest_haushalt.py` nicht vergessen wird.
2. **Er senkt keine Prüfschwelle.** Summenprobe, Strukturprobe, Vorjahres-Kette
   und die Rechenprobe der Erläuterungen gelten unverändert. Was sie reißt,
   kommt nicht in die Datenbank, wird gezählt und gemeldet. Ein unbeaufsichtigter
   Lauf ist der Grund, warum es diese Proben gibt — nicht der Anlass, sie zu
   lockern.
3. **Er ergänzt nur, was fehlt — Einheit für Einheit.** Eine vorhandene Einheit
   wird nicht angefasst. Zweimal hintereinander laufen ändert beim zweiten Mal
   keine einzige Zeile.

Und was ein Jahrgang bekommt, bekommt er in **einer** Transaktion
(`store.transaktion()`, verschachtelbar). Ohne die Klammer braucht ein
Jahresabschluss 1 + n + 1 Transaktionen — Gesamtrechnung, je Teilhaushalt eine,
Erläuterungen. Ein Abbruch dazwischen ließe den Jahrgang halb in der Datenbank,
und halb sieht für den nächsten Lauf aus wie fertig.

:::danger[Ein leeres Ergebnis ersetzt nie einen gefüllten Bestand]
Alle Speicherwege ersetzen einen Jahrgang: Sie löschen ihn und schreiben ihn
neu. Solange ein Mensch danebensteht, ist das richtig. Alle zwei Wochen
unbeaufsichtigt kippt die Rechnung — ändert die Stadt ihr Tabellenlayout,
liefert ein Parser irgendwann null oder halb so viele Zeilen, und wer das
speichert, tauscht einen gefüllten Bestand gegen ein kaputtes Ergebnis. Bemerkt
würde es erst, wenn die Seite leer ist.

`finanzquellen.bestandsschutz()` steht vor jedem ersetzenden Schreibvorgang:
**0 Zeilen ersetzen nie etwas**, weniger als 80 % des bisherigen Standes auch
nicht — beides wird gemeldet statt stillschweigend vollzogen. Verglichen wird
auf der Ebene, die ein Dokument abdeckt: bei den Produkten je Teilhaushalt,
nicht je Jahr, sonst sähe jedes einzelne THH-Dokument wie ein Einbruch aus.
Anlass war ein Beinahe-Unfall am 16.08.2026, bei dem ein Übertragungsskript
257 Prüfungsfeststellungen gelöscht hätte, weil die Quelltabelle leer war.

Das ist die Gegenrichtung zu den Pflicht-Proben: Die halten falsche Daten
draußen, diese Regel hält richtige drin.

**Der Schutz gilt dem unbeaufsichtigten Weg, nicht dem bewussten Handgriff.**
Wer einen verbesserten Parser über den Bestand zieht, will einen kleineren
Jahrgang oft genau so — ein früherer Lauf war zu großzügig. Ein Schutz, der das
blockiert, macht den einzigen Weg unbenutzbar, auf dem sich ein Parser-Fehler je
korrigieren ließe. Die Ingest-Skripte haben dafür `--auch-schrumpfen`: Der
Schrumpf wird deutlich gemeldet und dann vollzogen. Ein **leeres** Ergebnis
bleibt auch damit tabu — null Zeilen sind nie eine Absicht.
:::

### Eine Quelle für die Erkennung

Woran ein Dokument erkannt wird — Label-Muster, Mindestseitenzahl, Ausschlüsse,
Parser, Zieltabelle, erwarteter Monat — steht in **`council/finanzquellen.py`**,
je Datenart einmal. Die Ingest-Skripte und der Cron benutzen dieselbe
Definition; auf die Frage „ist das ein Jahresabschluss?" gibt es sonst zwei
Antworten, und eine davon veraltet still.

| Datenart | Erkennung | Zieltabelle | Erwartet |
|---|---|---|---|
| Jahresabschluss | Label `%Jahresabschluss%`, > 100 Seiten, **ohne** `%Rechenschaft%` / `%Schlussbericht%` | `council_ergebnisrechnung` (+ `council_abweichungsgruende`) | September, Jahrgang + 1 |
| Schlussbericht des RPA (Fundstelle) | Label `%chlussbericht%` **oder** Text beginnt mit `Schlussbericht`; entschieden am Textanfang | `council_pruefbericht_quellen` | September, Jahrgang + 1 |
| Prüfungsfeststellungen | Text `%Rechnungsprüfungsamtes%`, > 30 Seiten; entschieden am Textanfang | `council_pruefberichte` | September, Jahrgang + 1 |
| Teilhaushalts-Pläne | Label `%THH%`, > 40 Seiten | `council_produkte` | Oktober, Jahrgang + 0 |
| Gesamtergebnishaushalt | Label `%Gesamtergebnishaushalt%`, > 10 Seiten; Jahrgang aus dem **Tabellenkopf** (vier der acht Dokumente tragen keine Jahreszahl im Label) | `council_ergebnishaushalt` | Oktober, Jahrgang − 1 |
| Haushaltsplan | *(kein Anlagen-Muster — Download)* | `council_haushalt` | Oktober, Jahrgang − 1 |

### Der Datenstand ist sichtbar

`GET /api/council/haushalt/datenstand` liefert diese Matrix live aus dem
Bestand; der Block **„Bis wann die Zahlen reichen"** am Fuß von `/haushalt`
(`components/haushalt/datenstand.tsx`) zeigt sie.

Das ist kein Entwickler-Feature. Auf `/haushalt` steht der Plan für 2026, auf
`/haushalt/plan-ist` die Abrechnung für 2024, auf `/haushalt/pruefung`
Feststellungen bis 2023 — die Frage „warum steht hier 2024 und nicht 2025?"
müsste sonst auf neun Seiten einzeln beantwortet werden. Die Ursache ist immer
dieselbe und liegt bei der Stadt. Wo ein Jahrgang erwartet wird, aber noch
fehlt, steht das ausdrücklich da: *„Der Jahrgang 2025 wird üblicherweise im
September 2026 vorgelegt."* Das Wort „fehlt" kommt nicht vor — was die Stadt
noch nicht veröffentlicht hat, fehlt uns nicht.

**Ein halber Jahrgang gibt sich zu erkennen.** Sonst stünde er in derselben
Jahresspanne wie ein vollständiger und sähe aus wie einer: *„Für 2023 haben wir
6 von 9 Teilhaushalten."* / *„Für 2024 fehlt noch die Aufteilung auf die
einzelnen Bereiche."* Der Maßstab ist der bestbelegte Jahrgang desselben
Bestands — mehr wissen wir nicht, und weniger zu behaupten wäre falsche
Bescheidenheit.

Auch die Fußzeile verspricht nur, was sie halten kann. „Wir tragen neue
Jahrgänge automatisch nach" galt pauschal für die ganze Liste — deren erste und
prominenteste Zeile aber der Haushaltsplan ist, den der Cron gar nicht anfasst.
Jetzt nennt sie die Schichten, die **nicht** automatisch nachkommen, beim
Namen, und zieht die Liste aus den Daten: `automatisch === false`.

## Die redaktionelle Schicht

Drei Dinge liefert keine Datenquelle. Sie stehen als gepflegte Konstanten im
Frontend, damit sie überprüfbar bleiben:

- **`lib/haushalt-steuern.ts`** — je Einnahmeart: die Stufen „Wer entscheidet
  was", Spielraum-Einstufung, Rechenbeispiel, Lotti-Erklärung.
- **`lib/haushalt-pflicht.ts`** — Einordnung der Teilhaushalte in Pflicht /
  Pflicht mit Spielraum / überwiegend freiwillig. Eine Einschätzung auf Ebene
  ganzer Teilhaushalte; die Seite sagt das auch.
- **`lib/haushalt-quellen.ts`** — Fundstellen, Datenstände und Lizenzen.

## Quellen-System

Jede Zahl trägt einen Beleg-Chip, am Seitenende steht das Verzeichnis mit
Dokument, Fundstelle, Stand, Lizenz und Direktlink. Die Nummerierung läuft
**seitenweise** über `<Quellenkontext>` — global gezählt trüge eine Seite mit
zwei Quellen die Nummern 2 und 4.

Werte, die wir selbst bilden (Anteile, Differenzen, Rücklagen-Reichweite,
Pro-Kopf-Angaben, Ein-Punkt-Überschlag), sind an Ort und Stelle als
*„unsere Rechnung, keine amtliche Kennzahl"* gekennzeichnet.

`lib/haushalt-quellen.ts` fasst die Quelle einer ganzen **Seite** in einem
Absatz zusammen. Je einzelner Datenzeile weiß es die Datenbank genauer:
`council_herkunft` (siehe [oben](#herkunft-woher-jede-einzelne-zahl-stammt))
führt Fundstelle, Probe und Anker je Dokument-und-Abschnitt.

## Jahresabschlüsse und Produktebene aus dem eigenen Bestand

Beide Dokumenttypen mussten nirgends beschafft werden: Sie hängen als Anlagen
an Ratsvorlagen und liegen mit Volltext in `council_anlagen`.

**Jahresabschluss** (300+ Seiten je Jahrgang) → die Ergebnisrechnung der
Kernverwaltung führt **Ansatz und Ergebnis nebeneinander**. Damit gibt es
„geplant gegen tatsächlich" und die Aufschlüsselung der Erträge nach Arten
(Steuern, Zuwendungen, Entgelte, Kostenerstattungen). Eingelesen sind alle
acht Jahrgänge **2017–2024**, je mit zwölf Teilhaushalten.

Dass 2017, 2018 und 2020 lange fehlten, lag nie am Text, sondern an drei
verschiedenen Spaltenlayouts: 2017 steht das Ergebnis **vor** dem Ansatz,
2018 hat elf Spalten mit sechs möglichen Leerfeldern, 2019–2024 tragen eine
meist leere Nachtragsspalte. `_spalten_zuordnen()` liest die Anordnung
deshalb aus dem **Tabellenkopf** statt aus einer festen Reihenfolge. Zwei
Kleinigkeiten kamen dazu: 2017 schreibt die Summenzeilen als „12.= Summe"
ohne Leerzeichen, und im Abschluss 2022 fällt bei THH09 ein Zeilenumbruch
mitten in die Überschrift („A. Teil\n-Ergebnisrechnung THH09") — ohne ihn im
Muster fand der Parser dort nur die Fortsetzungsseite und verwarf über die
Summenprobe die ganze Teilhaushalts-Ebene.

:::danger[„Plan" heißt nicht in jedem Jahrgang dasselbe]
Die Ergebnisrechnung vergleicht das Ist mit dem Wert, den das Dokument selbst
als Bezug führt — und der wechselt:

| Jahrgang | Bezugsgröße (`plan_art`) |
|---|---|
| 2018 | Gesamtermächtigung (Ansatz + Nachtrag + Übertragungen) |
| 2020 | Ansatz einschließlich Nachtragshaushalt |
| alle übrigen | nackter Haushaltsansatz |

Bei den Ausgaben 2020 sind das **27,2 Mio. € Unterschied** — also der
Unterschied zwischen „21,5 Mio. weniger ausgegeben als geplant" und
„5,7 Mio. mehr". Beide Werte stehen in derselben Zeile, deshalb speichert der
Parser beide: `ansatz` den ursprünglichen Haushaltsansatz, `plan` die
Bezugsgröße der Abweichung, `plan_art` welche davon. Die Oberfläche schreibt
die Bezugsgröße an (Kasten „Was ‚geplant' in diesem Jahr heißt", Fußnote in
der Mehrjahres-Kurve). Eine Kurve, die 2018 die Gesamtermächtigung und 2021
den nackten Ansatz gegen das Ist stellt, ohne das zu sagen, wäre still
falsch — und still falsch ist hier der schlechteste Ausgang.

Bestätigt wird die Zuordnung aus dem Dokument selbst: Die Prozentsätze in
Abschnitt 6.3.1 rechnen 2018 gegen die Gesamtermächtigung (3 von 3 Posten,
gegen den Ansatz nur 1 von 3) und 2020 gegen Ansatz + Nachtrag (4 von 4).
:::

### Das „Warum" zu den Abweichungen

Abschnitt **6.3.1** des Jahresabschlusses begründet jede Abweichung ab 20 %
gegenüber dem Plan, je Posten und in den Worten der Verwaltung — etwa, dass
die Mehrerträge 2024 „nahezu auf den Bereich der Gewerbesteuer" entfallen und
„unter anderem aus einem Einmaleffekt" stammen. Der Abschnitt existiert in
allen acht Jahrgängen (45 Posten, ~37.000 Zeichen).

Die Eintrittskarte ist hart: Die Überschrift nennt die Abweichung **doppelt**,
als Betrag und als Prozentsatz („+75,1 Millionen Euro, +24,82 %"). Beides muss
zu der Zeile passen, die der Tabellen-Parser für denselben Posten gelesen hat
(`pruefe_abweichungsgruende`) — damit prüft sich das Dokument an einer zweiten
Stelle selbst. 45 von 45 bestehen; was nicht passt, wird verworfen statt
angezeigt. Angezeigt wird der Wortlaut, nicht eine Zusammenfassung: nur
Silbentrennung am Zeilenende und eingestreute Seitenfüße („JA 161") werden
entfernt.

**Schlussberichte des Rechnungsprüfungsamts** werden nur **verlinkt**, nicht
ausgewertet — sie sagen selbst, dass die Plan-Ist-Abweichungen „im Anhang und
im Rechenschaftsbericht erläutert" werden. Erkannt werden sie an der
Eingangsformel, nicht am Label („Schlussbericht JA 2017" ist der Bericht zum
Eigenbetrieb Gebäudewirtschaft, weitere Treffer betreffen Stiftungen). Achtung:
Der Volltext ist umbrochen, ein `LIKE` auf die Formel findet **nichts** —
`pruefbericht_aus_anlage()` normalisiert vorher. Der Jahrgang **2024** ist ein
kaputter Textextrakt (Glyphen-Indizes statt Zeichen, Buchstabenanteil 0,00
gegen 0,71–0,76 bei den übrigen); er wird als `lesbar = 0` gespeichert und auf
der Seite so benannt, statt überspielt zu werden.

**Teilhaushalts-Pläne** (THH01–13) → die Produktebene: was einzelne Aufgaben
kosten, mit Produktnummer und zuständigem Amt (2023 etwa
„Kindertagesbetreuung" mit 71,1 Mio. € Aufwand und 58,6 Mio. €
Zuschussbedarf). Die Abdeckung ist unvollständig — für 2023 erklären die
gefundenen Produkte rund 82 % der geplanten Aufwendungen. Der Endpunkt
liefert diese Quote als `abdeckung_prozent` mit, damit die Oberfläche die
Liste nicht als Vollbild ausgeben kann.

## Der Produkt-Steckbrief

Zu jedem Produkt führen die Pläne einen Steckbrief: **Kurzbeschreibung**
(was die Aufgabe umfasst), **Auftragsgrundlage** (die Gesetze, Satzungen und
Verträge dahinter), **Grad der Beeinflussbarkeit**, **Wirkungskreis** und
**Zielgruppe**. Das beantwortet die häufigste Bürgerfrage zum Haushalt — „was
kostet eigentlich das Stadtarchiv?" — und belegt die Pflicht/Kür-Einordnung,
die auf `/haushalt/pflicht` bisher nur geschätzt ist.

Der Bestand (377 Produkte, 2018–2023): Auftragsgrundlage und Wirkungskreis
tragen 100 %, Kurzbeschreibung, Beeinflussbarkeit und Zielgruppe je 98,4 %.
Die sechs Lücken sind echt — „Personalzuweisung an das Jobcenter" führt den
Plan ohne Beschreibungstext. Der Lauf von `ingest_finanzberichte.py` weist
die Quote je Feld aus, die Seite nennt sie ebenfalls.

:::caution[Die Label stehen NACH ihrem Inhalt]
Im PDF sitzt „Kurzbeschreibung:" als Spaltenüberschrift **links neben** dem
Absatz. Die Textextraktion schiebt sie dahinter, die Reihenfolge im Text ist
also: Absatz — `Kurzbeschreibung:` — Rechtsgrundlagen-Absatz —
`Auftragsgrundlage:`. Wer vorwärts liest, bekommt jedes Feld um eines
verschoben; die Kurzbeschreibung wäre dann das Gesetz. Kurze Werte passen im
PDF neben ihr Label und stehen deshalb **dahinter** („Grad der
Beeinflussbarkeit: mittel"). `_STECKBRIEF_FELDER` markiert beide Fälle
ausdrücklich, statt sie zu erraten.

Zwei Folgefehler, die dabei auffielen und je einen eigenen Schutz haben:
- **Jede Leistung trägt einen eigenen Steckbrief.** Ein Produkt zerfällt in
  Leistungen (`P10.111023.001`) mit denselben Feldern. Der Produktblock wird
  deshalb vor der ersten Leistungs-Überschrift abgeschnitten.
- **Die Grunddaten-Tabelle steht mitten drin.** Ihr Label steht ausnahmsweise
  vor ihrem Inhalt, die Tabelle liegt also zwischen `Wirkungskreis:` und
  `Zielgruppe(n):` — ungefiltert stand eine Zahlenwüste („Einheit · Ist 2021 ·
  Plan 2022 …") als Zielgruppe auf der Seite. Übernommen wird nur der
  zusammenhängende Fließtext-Block unmittelbar vor dem Label.
:::

`beeinflussbarkeit` ist normalisiert (`niedrig` / `mittel` / `hoch`; die Pläne
schreiben mal „niedrig", mal „gering", mal groß). Der Wortlaut bleibt in
`beeinflussbarkeit_roh` erhalten — Mischformen wie „niedrig/mittel bei
Gesundheitsförderung und Prävention" bekommen **keine** Stufe zugewiesen,
weil jede Wahl eine Behauptung wäre; die Seite zeigt dann den Rohwert.

Gesucht und gefiltert wird **serverseitig** (`q`, `amt`, `spielraum` am
Endpunkt): Mit dem Steckbrief trägt jede Zeile mehrere hundert Zeichen
Fließtext. `nr` holt zusätzlich ein einzelnes Produkt, damit der Steckbrief
auch dann lädt, wenn ein Filter es aus der Liste nähme. `facetten` liefert
Ämter und Spielraum-Stufen mit Anzahl sowie die Abdeckung je Feld.

Verwaltungsdeutsch wird nicht ungefiltert durchgereicht: „übertragender
Wirkungskreis", „Grad der Beeinflussbarkeit" und „Produkt" stehen im Glossar
(`lib/glossary.ts`), die drei Stufen werden in `SPIELRAUM_TEXT` zu Sätzen
übersetzt. Eingefärbt wird nichts — ein teures Produkt ist keine schlechte
Note, und „kaum Spielraum" kein Missstand.

## Planjahre: „Ansatz" heißt fünfmal etwas anderes

`council_ergebnisrechnung` kann die Einnahmearten nur für **abgeschlossene**
Jahre zeigen — 2025 und 2026 haben keinen Jahresabschluss. Die Zahlen stehen
aber längst im Haushaltsplan selbst: Anlage 005, der *Gesamtergebnishaushalt*,
führt dieselben Posten 01–24 auf 16 bis 18 Seiten. Acht Dokumente decken die
Planjahre 2019–2026 ab (`council/ergebnishaushalt.py`).

Der Tabellenkopf sieht harmlos aus und ist die eigentliche Gefahr:

```
Ergebnis 2024 | Ansatz 2025 | Ansatz 2026 | Ansatz 2027 | Ansatz 2028 | Ansatz 2029
```

Fünfmal „Ansatz" — beschlossen ist genau **eins** davon (hier 2026). 2027–2029
sind mittelfristige Finanzplanung nach § 8 NKomVG, 2025 ist der
*fortgeschriebene* Vorjahresansatz. Gespeichert wird deshalb nur, was sich
belegen lässt, und jede Zeile sagt, was sie ist:

| Spalte | Was sie ist | Wird gespeichert? |
|---|---|---|
| 1 — `Ergebnis JJJJ` | Ist des Vorvorjahres, **Gesamtebene** (mit den nicht rechtsfähigen Stiftungen) | nein — Gegenprobe |
| 2 — `Ansatz JJJJ+1` | fortgeschriebener Vorjahresansatz | nein (s. u.) |
| 3 — `Ansatz JJJJ+2` | **beschlossener Haushaltsansatz** | ja, `art='ansatz'` |
| 4–6 | mittelfristige Finanzplanung | ja, `art='finanzplanung'` |

**Warum Spalte 2 draußen bleibt:** Sie widerspricht dem, was der Plan des
Vorjahres für dasselbe Jahr beschlossen hat — über sieben Jahrgangspaare
stimmen nur 7 bis 11 von 23 Posten überein (Nachträge, Umschichtungen). Zwei
Zeilen für dasselbe Jahr mit verschiedenen Beträgen und keine Regel, welche
gilt: das wäre eine Lücke, die aussieht wie ein Bestand.

**Warum `plan_jahrgang` im Schlüssel steht:** Dasselbe Jahr kommt in mehreren
Plänen vor — 2027 ist im Haushalt 2026 die erste Finanzplanungsstufe und im
Haushalt 2027 der Ansatz. Und die Finanzplanung wird jedes Jahr neu
geschrieben: Zwischen zwei aufeinanderfolgenden Plänen stimmen für dasselbe
Finanzplanungsjahr **0 bis 2 von 23** Posten überein. Ohne `plan_jahrgang`
überschriebe der jüngste Plan stumm den älteren.

:::caution[Es ist der Entwurf, nicht der Beschluss]
Anlage 005 hängt an der Vorlage, mit der die Verwaltung den Haushalt
**einbringt**; vier der acht Dokumente sagen das im Titel („Haushalt 2026
Verwaltungsentwurf"). Über die sechs Jahre mit Jahresabschluss liegt der
Ansatz dieser Tabelle bei den ordentlichen Erträgen 0,7 bis 13,1 Mio. €
**unter** dem Ansatz, den der Abschluss desselben Jahres als Bezugsgröße
führt — deutlich mehr, als die Stiftungen erklären. Jede Zeile trägt deshalb
`stand = "Haushaltsplan JJJJ, Anlage 005 — Stand der Einbringung"`. Wer die
Zahl zeigt, zeigt den Vorschlag der Verwaltung und sollte das anschreiben.
:::

:::caution[Was diese Schicht **nicht** liefert]
Eine Aufteilung nach Teilhaushalten. Der Jahresabschluss führt sie in
Abschnitt 5 („Teil-Ergebnisrechnung THH01…"), der Gesamtergebnishaushalt
nicht: In allen acht Dokumenten kommt „THH" kein einziges Mal vor. Für ein
Bild, das Herkunft und Verwendung gegenüberstellt, liefert sie also nur die
Herkunftsseite. `council_produkte` deckt nur 8 bis 10 der 13 Teilhaushalte ab
(17–36 % unter der Summenzeile), `council_haushalt` ist vollständig, aber eine
andere Gliederung (2026: 812,9 statt 788,6 Mio. € Erträge). Beides ist
brauchbar — aber nur, wenn die Seite den Unterschied benennt.
:::

## Vier Prüfungen, und keine davon ist optional

Aus PDF-Text extrahierte Tabellen verschmelzen Zahlen („355.188334.704") und
kleben Seitenzahlen an Werte. Ein Jahrgang kommt deshalb nur in die Datenbank,
wenn er **alle** folgenden Proben besteht:

| Probe | Was sie prüft | Wo |
|---|---|---|
| **Zeilenprobe** | `Abweichung = Ergebnis − Plan`, wobei als Plan nur zugelassen ist, was der Tabellenkopf als Spalte nennt | `_spalten_zuordnen` |
| **Summenprobe** | Die zwölf Teilhaushalte ergeben die Gesamtrechnung — in **Plan und Ist**, Zeilen 12 und 20 | `summenprobe` |
| **Strukturprobe** | `12 − 20 = 21` innerhalb der Tabelle, in Plan und Ist | `strukturprobe` |
| **Vorjahres-Kette** | Das Ist eines Jahres taucht im Folgejahrgang als Vorjahresspalte wieder auf | `vorjahreskette` |

Stand heute: Summenprobe 0,0000 % in allen acht Jahrgängen, Strukturprobe 8/8,
Vorjahres-Kette 14/14 Glieder.

Für die Planjahre (`council/ergebnishaushalt.py`) gelten zwei eigene, und beide
sind Pflicht:

| Probe | Was sie prüft | Wo |
|---|---|---|
| **Summenzeilen** | `01–11 = 12`, `13–19 = 20` und `12 − 20 = 21` — in **allen sechs** Jahresspalten, also achtzehnmal je Dokument | `summenprobe` |
| **Planspalte** | Die hervorgehobene Planjahr-Spalte steht in jeder Zeile ein zweites Mal am Zeilenende und zeigt auf dieselbe Spalte wie der Kopf | `planspaltenprobe` |

Die zweite trägt die Trennlinie zwischen Ansatz und Finanzplanung: Ohne sie
wäre „dritte Spalte = beschlossener Ansatz" eine Reihenfolgeannahme. Stand
heute in 8/8 Dokumenten aufgegangen, 23 von 23 Zeilen je Dokument.

**Gegenprobe, keine Probe:** Die Ist-Spalte des Vorvorjahres lässt sich gegen
`council_ergebnisrechnung` halten — aber sie ist die *Gesamt*ebene (mit den
nicht rechtsfähigen Stiftungen), der gespeicherte Abschluss die
Kernverwaltung. Deckungsgleich sind 6 bis 8 von 23 Posten, der größte Abstand
liegt bei 0,075 % der Ertragssumme. Gegen die *Gesamt*ergebnisrechnung
desselben Abschlusses trifft sie dagegen auf den Cent: **184 von 184 Posten in
allen acht Jahrgängen**. Der Lauf misst den Abstand und meldet ihn ab 0,5 % —
verwerfen darf er deswegen nichts, sonst flöge irgendwann ein richtiger
Jahrgang wegen einer anderen Konsolidierungsstufe raus.

**Welche Probe eine gespeicherte Zeile bestanden hat, steht seit 08/2026 an
der Zeile** — über ihre `herkunft_id` in `council_herkunft.probe`, mitsamt dem
Messwert (`probe_ergebnis`, etwa „0.00 % Abweichung zur Gesamtrechnung"). Bis
dahin lief die Probe zwar, aber nur das Lauf-Protokoll wusste davon, und das
ist nach dem Lauf weg. Jede Probe hier braucht deshalb einen Eintrag in
`herkunft.PROBEN` — Name plus einen Satz für Leserinnen.

Zwei Details, die teuer erkauft sind:

- Die Summenprobe prüfte früher nur den Ansatz. Das genügt nicht — ein
  Fehlgriff, der zufällig denselben Ansatz trägt, käme durch. Sie prüft
  deshalb **Plan und Ist**. (Im Abschluss 2022 wurde THH09 einmal mit 0,1
  statt 26,8 Mio. € gelesen; erst die Summe machte es sichtbar.)
- Gesucht wird das **letzte** passende Fenster in der Zahlenfolge einer Zeile,
  denn der Kopf ordnet von rechts: Abweichung, davor Ergebnis, davor die
  Bezugsgröße. Damit dabei nicht die Zeile *unter* Posten 24 mitgelesen wird —
  „Jahresergebnis" trägt keine Nummer und rutscht in dieselbe Zeile —, wird die
  Zeile vorher an diesem Wort abgeschnitten. Ohne den Schnitt ergäbe sich für
  Posten 24 ein zweites, in sich stimmiges Tripel (2024: 34,6 + −28,5 = 6,1).

:::caution[Vorzeichen nur auf den Cent reparieren]
Fehlt im Dokument ein Minuszeichen, darf der Parser es ergänzen — aber nur,
wenn der Betrag **exakt** passt (1 Cent Toleranz statt 1 Euro) und alle drei
Werte des Tripels von null verschieden sind. Ohne die zweite Bedingung erfüllt
jedes „X | 0,00 | X" diese Probe: Im Abschluss 2018 hätte das für THH11 ein
Ist von 0,00 € eingetragen, richtig sind 105,0 Mio. €. Der Fall wird gezählt
und geloggt (`vorzeichen_repariert`); in den acht Jahresabschlüssen tritt er
derzeit **null**-mal auf.
:::

Ein Nebenertrag: Die Ansätze aus den Jahresabschlüssen bestätigen die Werte,
die wir aus den Plan-PDFs lesen. `council_haushalt` minus der Zeile „nicht
rechtsfähige Stiftungen" trifft den **ursprünglichen** Ansatz auf den Cent —
2020 also 588.539.108,34 € (vor Nachtrag), nicht die 591,3 Mio. € des
fortgeschriebenen Plans. Genau dafür gibt es die beiden Felder.

## Die Prüfung: was das Rechnungsprüfungsamt beanstandet

Der Jahresabschluss ist die Abrechnung — der **Schlussbericht des
Rechnungsprüfungsamts** ist die einzige regelmäßige, förmliche Kontrolle
davon durch eine Stelle, die dem Rat berichtet und nicht der
Verwaltungsspitze. Auch er hängt als PDF an einer Ratsvorlage und wird dort
nie wieder gelesen.

Greifbar ist er, weil er seine Befunde mit **Randmarken** auszeichnet und
deren Bedeutung selbst in den Vorbemerkungen erklärt: `B` Beanstandung,
`WB` Wiederholte Beanstandung, `H` Hinweis, `K` Korrektur/Klärung. Für
2017–2023 stehen so **257 Feststellungen** im Bestand — 166 Hinweise,
42 Beanstandungen, 37 wiederholte, 12 Korrekturen.

Jede trägt Jahr, Textziffer, Seite und einen Deeplink auf das Quelldokument.
Die Marken werden auf der Seite **erklärt, nicht bewertet**, und zwar mit dem
Wortlaut aus der Legende des jeweiligen Jahrgangs — die ändert sich (der
Bericht 2023 führt kein `K` mehr). Bewertungsfarben gibt es keine: Rot für
„Beanstandung" machte aus einer Aufbereitung eine Anklage, mit einem Mittel,
das dem Bericht selbst fremd ist.

:::note[Der Konsistenz-Check statt einer Rechenprobe]
Prosa lässt sich nicht nachrechnen — das Dokument liefert aber eine eigene
Klammer, und `council/pruefberichte.py` macht sie zum Pflicht-Gate:

1. Es muss eine Legende geben, und **nur die dort erklärten Marken** zählen.
2. Jede Marke muss unter einer **Textziffer aus dem Inhaltsverzeichnis**
   stehen (das Verzeichnis überschreibt seine erste Spalte selbst mit
   „Textziffer").
3. Der Textblock endet an der nächsten Marke oder der nächsten
   Abschnittsüberschrift — nie „so viele Zeichen".

Was die Klammer nicht erfüllt, wird verworfen und **gezählt**. Der Ingest
weist die Zahl je Jahrgang aus; sie ist derzeit 0 und bleibt es, solange das
Dokumentformat hält. Steigt sie, hat sich etwas geändert — dann gehört ein
Blick in den Bericht, keine gelockerte Regel.
:::

Zwei Fallen, die dabei teuer waren und als Test festgehalten sind:

- **Die Legende schreibt die Marken genau wie der Fließtext** (` B  Beanstandung`).
  Wer vor dem Berichtsanfang zu zählen beginnt, zählt für 2019–2023 jede Marke
  einmal zu oft.
- **Am Berichtsende steht der Name der Amtsleitung in gesperrter Schrift**
  („K R U P K E"). Mit nur einem Leerzeichen hinter der Marke ginge er als
  `K`-Marke durch. Deshalb verlangt das Muster **zwei** Leerzeichen — den
  Abstand der Randspalte.

**Zuordnung und Dedup.** Welcher Bericht zu welchem Jahresabschluss gehört,
entscheidet der **Textanfang**, nicht das Label: „Schlussbericht JA 2017"
(`document_id` 192039) ist der Bericht zum Eigenbetrieb Gebäudewirtschaft,
und jedes Jahr kommen die formgleichen Berichte zu Klävemann-Stiftung, VOSS,
AWB und EGH dazu. Der Titel steht im Extrakt über vier Zeilen — ein
`LIKE 'Schlussbericht des …'` in SQL findet deshalb **keinen einzigen**
Bericht; erst nach Whitespace-Normalisierung greift der Vergleich.

**Die Ketten.** Eine „wiederholte Beanstandung" sagt von selbst, dass ein
Mangel schon einmal dastand — sie sagt nur nicht, seit wann. Über den
Abschnittstitel (ohne Klammerzusätze, weil „Internes Kontrollsystem (IKS)" ab
2020 nur noch „Internes Kontrollsystem" heißt) finden dieselben Sachen über
die Jahrgänge zusammen. Die Textziffer taugt dafür **nicht**, sie verschiebt
sich. Längste Kette: **Plan-Ist-Vergleich**, in allen sieben geprüften Jahren
als `WB` ausgewiesen — zuletzt mit dem Satz „Dies widerspricht dem Grundsatz
der Haushaltswahrheit". Deshalb steht der Hinweis auf die Prüfung auch auf
`/haushalt/plan-ist`, im Wortlaut und mit Link.

**Was daneben steht.** Der Absatz, der im Bericht direkt auf eine Marke
folgt, wird als `folgeabsatz` getrennt geführt und getrennt angezeigt. Dort
steht oft die Gegenseite („Die Verwaltung hat hierzu erklärt, dass eine
entsprechende Umsetzung bis 31.12.2024 erfolgen soll."). Getrennt, weil sonst
als Beanstandung gälte, was der Bericht gar nicht so gemeint hat — 97 der 257
Feststellungen haben einen, 23 davon mit Bezug auf die Verwaltung.

Eine **regelmäßige** Rückmeldung der Verwaltung gibt es nicht: Im ganzen
Bestand liegen dazu drei Dokumente — die „Nacharbeiten-Übersicht" zum
Prüfbericht 2020 (`council_anlagen` 243109, Vorlage 21/0944) und je eine
Stellungnahme des Oberbürgermeisters zu den Berichten 2019 und 2021. Die
Nacharbeiten-Übersicht war beim Bau die beste Gegenprobe: Sie nennt zu jeder
Feststellung Ziffer **und** Seite, und beide stimmen mit dem Geparsten
überein (3.1.1 → Seite 18, 3.1.3 → 20, 3.2 → 22).

## Woran das Labor seine Zahlen misst

Ein Regler, der eine Zahl verändert, sagt nichts darüber, ob das viel ist.
Deshalb hängt an jeder Bewegung ein Bezug, und alle drei kommen aus Daten:

- **Anteil an der Lücke** — der Balken im Ergebnis füllt sich, Einnahmen und
  Kürzungen getrennt eingefärbt.
- **Euro je Einwohner** — Bezugsgröße ist `council_einwohner` (jüngstes Jahr).
- **Der Beispielbetrieb am Hebesatz** — 100.000 € Gewerbeertrag × Messzahl
  3,5 % (§ 11 GewStG) × Hebesatz. Dieselbe Rechnung wie im Steuer-Steckbrief,
  damit beide Seiten dieselbe Zahl nennen.
- **Vergleichsgrößen aus der Produktebene** — „ungefähr so viel, wie
  *Kulturgutvermittlung* im ganzen Jahr kostet". Verglichen wird nur
  **innerhalb desselben Teilhaushalts**: Eine Kultur-Kürzung neben eine
  Sozialleistung zu stellen legt nahe, man könne die stattdessen streichen.
  Wo für einen Bereich keine Produkte vorliegen, entfällt der Vergleich.
- **„Wie verlässlich ist der Plan?"** — der Ansatz gegen das Ergebnis aus den
  Jahresabschlüssen. In allen fünf eingelesenen Jahren fiel das Ergebnis
  besser aus als geplant (zwischen +2,9 und +38,1 Mio. €). Der Block sagt
  ausdrücklich dazu, dass das Minus damit nicht unecht wird — ein Plan preist
  Vorsicht ein.

:::caution[Produktzahlen sind Vergleich, nicht Rechengrundlage]
Die Simulation rechnet mit dem aktuellen Planjahr, die Produktebene stammt aus
dem jüngsten auslesbaren Teilhaushaltsplan (2023). Beides zu verrechnen ergäbe
eine Zahl, die in keinem Dokument steht. Die Produkte stehen deshalb nur
daneben — als Größenordnung, nie als Summand.
:::

## Der Konzern Stadt: was der Kernhaushalt nicht zeigt

Alles bisher Beschriebene ist die **Kernverwaltung**. Das ist nicht die ganze
Stadt: Klinikum, Verkehr und Wasser, Abfallwirtschaftsbetrieb, Bäderbetrieb,
Weser-Ems Halle und der Eigenbetrieb Gebäudewirtschaft führen eigene Bücher
und tauchen im Haushalt bestenfalls als Zuschusszeile auf. 2024 stehen
799,1 Mio. € Kernverwaltung gegen 1.241,5 Mio. € Konzern — der Haushalts-
Bereich zeigte bis dahin rund **64 %** dessen, was die Stadt bewegt.

Die Quelle ist der **konsolidierte Gesamtabschluss** nach § 128 NKomVG, genauer
der Prüfbericht, den das Rechnungsprüfungsamt dazu vorlegt (`council_anlagen`,
zwölf Jahrgänge 2013–2024). Parser: `council/konzernabschluss.py`.

**Die Labels dieser Reihe sind wertlos.** Der Gesamtabschluss 2016 heißt im
Bürgerinfo schlicht „Anlage", 2013 ebenso; „Prüfbericht GA 2021" trifft nur
drei von zwölf. Erkannt wird deshalb am **Textanfang** — und zwar erst nach
dem Glätten des Zeilenumbruchs, denn im Rohtext steht der Titel über fünf
Zeilen verteilt. Ein `raw_text LIKE 'Bericht über die Prüfung des
konsolidierten Gesamtabschlusses zum 31.12.2016%'` fände **nichts**.

### Zwei Tabellen, sechs Proben

| Abschnitt | Tabelle | Proben |
|---|---|---|
| 3.2 Gesamtergebnisrechnung | `council_konzern_posten` | `Erträge − Aufwendungen = ordentliches Ergebnis`; dasselbe für die außerordentlichen Posten; beide zusammen = Gesamtjahresergebnis |
| 4.1.1 Trägeraufstellung | `council_konzern_traeger` | je Zeile `Jahr − Vorjahr = Veränderung`; Träger + Konsolidierung = ausgewiesene Summe; diese Summe = Summenposten aus 3.2 |

Dazu die **Vorjahres-Kette** über Dokumentgrenzen: 39 von 39 Gliedern schließen.
Sie ist bewusst **kein** Ausschlussgrund, sondern eine Meldung — sie prüft zwei
Jahrgänge gegeneinander, und wer bei Streit beide wegwirft, verliert einen
guten wegen eines schlechten.

Stand heute: **11 von 12 Jahrgängen** gespeichert (2014–2024), 289 Posten,
135 Trägerzeilen.

### Drei Fallen, an denen ein naiver Parser scheitert

- **Die Postennummern wechseln.** Bis 2018 ist Posten 15 die Summe der
  ordentlichen Erträge, ab 2019 ist es Posten 13. Wer weiter 15 liest, bekommt
  ab 2019 „Versorgungsaufwendungen" — 8,4 Mio. statt 1,14 Mrd., und keine
  Zeile im Log. Gespeichert wird deshalb eine **Rolle**
  (`ertraege_summe`, `zinsaufwand`, …), erkannt an der Beschriftung; die
  Nummer steht nur noch als Fundstelle daneben.
- **Die Vorjahresspalte ist nicht immer in Euro.** 2014–2016 führt der
  Tabellenkopf `EUR EUR TEUR`. Wer das übersieht, liest einen Konzern, der
  über Nacht auf ein Tausendstel schrumpft. Die Einheit kommt aus dem Kopf.
- **2019 hat keine Zeilenumbrüche.** Der Extrakt setzt die ganze Tabelle in
  eine Zeile, und die nächste Postennummer klebt am Vorjahreswert
  (`269.835.099,832. Zuwendungen`). Auflösbar, weil ein deutscher Betrag immer
  genau zwei Nachkommastellen hat — mehr macht `entzerren()` nicht, und die
  drei Proben entscheiden anschließend wie bei jedem anderen Jahrgang.

Dazu kommt eine Eigenheit, die keine Falle, sondern eine Grenze ist: In den
Jahrgängen bis 2017 stehen **Leerzeichen mitten in Beträgen**
(`105.667.339, 23`, `160.026.568 ,55`). Solche Zeilen fallen weg, statt eine
geratene Zahl zu liefern — der erste *saubere* Betrag einer Zeile ist sonst
nicht mehr der des Haushaltsjahres, sondern der des Vorjahres. Die
Beschriftung darf deshalb keine Ziffernfolge enthalten; tut sie es, ist die
Zeile zerschossen.

### Die Gegenprobe — die stärkste Bestätigung im ganzen Bereich

Der Gesamtabschluss führt die Kernverwaltung als eigene Trägerzeile. Diese
Zeile muss den Ist-Wert wiedergeben, den `council_ergebnisrechnung` aus einem
**anderen** Dokument eines **anderen** Jahres trägt. Sie tut es in **10 von 10**
vergleichbaren Fällen (5 Jahrgänge × Erträge und Aufwendungen), jeweils auf
die Rundung eines Tausend genau — 2024 etwa 799.057 TEUR gegen
799.057.202,86 €. Zwei getrennt eingelesene Quellen, dieselbe Zahl; die Seite
zeigt den Abgleich offen.

### Was der Gesamtabschluss nicht hergibt

- **Die Liste der einbezogenen Gesellschaften.** In den jüngeren Jahrgängen ist
  der Konsolidierungskreis eine **Grafik ohne Textebene** („Aus der
  nachfolgenden Grafik ist ersichtlich, welche Aufgabenträger …") — dieselbe
  Sackgasse wie bei der Schuldenübersicht. Wer dazugehört, sagt stattdessen die
  Trägeraufstellung, und die trägt Zahlen. Beteiligungsquoten stehen nirgends.
- **Der Schuldenstand.** Die Gesamtschuldenübersicht ist Pflichtanlage, aber
  ihre Seiten tragen im PDF keinen Text. Ohne OCR ist dort nichts zu holen, und
  ein aus Diagrammbeschriftungen zusammengerechneter Schuldenstand wäre still
  falsch.
- **Der Jahrgang 2013** (`document_id` 188333): 74 Seiten, aber nur 38.000
  Zeichen Volltext — die Tabellenseiten kommen ohne Textebene. Keine der drei
  Proben ist überhaupt rechenbar, der Jahrgang fällt durch.
- **Die Aufwendungsseite der Trägeraufstellung 2018.** Ihre Konsolidierungs-
  zeile (−80.462 TEUR) passt nicht zur eigenen Summenzeile; der Bericht des
  Folgejahres führt für dasselbe Jahr −80.398. Die Spaltenprobe schlägt mit
  64 TEUR an, die Aufstellung wird verworfen — die Ertragsseite desselben
  Jahrgangs und seine Postentabelle bleiben. **Das ist der Gate im Betrieb**,
  nicht die Theorie dazu.

:::caution[Ein Gesamtabschluss ist kein Haushalt]
Er wird rund zwei Jahre später aufgestellt, folgt handelsrechtlichen Regeln und
ist mit den Planzahlen auf `/haushalt` **nicht verrechenbar** — auch nicht
durch Subtraktion. Die API liefert deshalb keine gemischten Summen, sondern
beide Reihen getrennt, und die Seite sagt es in einem eigenen Block statt im
Kleingedruckten.
:::

## Städtevergleich: was sich vergleichen lässt — und was nicht

`/haushalt/vergleich` ist aus einer Absage entstanden. Der Entwurf sah einen
breiten Städtevergleich vor (Ausgaben, Personal, Schulden je Einwohner). Der
wurde **nicht** gebaut, und zwar nicht wegen fehlender Daten: Ein Vergleich
von Kernhaushalten misst zuerst, wie weit eine Stadt ausgelagert hat.

Oldenburgs Kernhaushalt zeigt rund **64 %** dessen, was der Konzern bewegt;
Osnabrücks knapp **48 %**, weil dort die Stadtwerke dazugehören. Dieselbe
Kennzahl, dieselbe Stadt, dasselbe Jahr — Kern gegen Konzern — unterscheidet
sich bei der Pro-Kopf-Verschuldung um **Faktor 2,53** (2024) und **6,04**
(2023). Wer eine Kernhaushaltszahl aus Stadt A gegen eine Konzernzahl aus
Stadt B stellt, kennt nicht einmal die Größenordnung des Fehlers.

:::note[Die beste Quelle zum Fallstrick liegt im eigenen Bestand]
Die Stadt Oldenburg hat genau diesen Vergleich 2018 auf Antrag der
FDP-Fraktion angestellt (Vorlage **18/0911**, `kvonr` 17170) — sieben Städte,
neun Jahrgänge — und ihn im selben Dokument entwertet: *„Die heterogenen
Strukturen der verschiedenen Städte lassen einen aussagefähigen Vergleich in
dem Sinne nicht zu, dass eine niedrigere Quote ‚besser' als eine höhere Quote
ist."* Danach listet sie je Stadt auf, was im Kernhaushalt steckt und was
nicht. Antrag: `document_id` **196000**, Antwort: **196525**.

Dieselbe Warnung kommt vom Nds. Innenministerium (Runderlass 13.12.2017) und
vom Statistischen Bundesamt. Die Seite zitiert die Verwaltung wörtlich und
verlinkt den Vorgang in unserem Bestand — die Vorlage wurde als Bericht **zur
Kenntnis genommen**, es gibt also einen `council_decisions`-Eintrag. Aufgelöst
wird er über die **Vorlagennummer**, nicht über die gespeicherte id: Die
Nummer ist auf jeder Kopie der Datenbank dieselbe.
:::

### Was trotzdem trägt

Robust gegen die Auslagerungsfrage ist, was die Stadt als Hoheitsträger
festlegt oder was das Land für alle gleich berechnet — es wandert nicht mit,
wenn ein Aufgabenblock in einen Eigenbetrieb zieht:

| Reihe | Kennzahlen | Quelle |
|---|---|---|
| `steuerkraft` | Steuerkraftmesszahl (TEUR), Einwohnerzahl | LSN, Kommunaler Finanzausgleich, Blatt `ST_KR_MESS_VGL` |
| `realsteuern` | Hebesätze Grundsteuer A/B und Gewerbesteuer, Ist-Aufkommen je Einwohner, Steuereinnahmekraft je Einwohner | LSN, Realsteuervergleich, Blätter `2_1` und `5_1` |

Die Steuerkraftmesszahl rechnet § 11 NFAG mit **Nivellierungshebesätzen**, also
für alle Gemeinden mit denselben fiktiven Sätzen; sie misst die Steuerbasis,
nicht die Hebesatzpolitik. Und Steuern erhebt nie ein Eigenbetrieb — der
Auslagerungseffekt existiert hier schlicht nicht.

**Die Steuerkraft je Einwohnerin wird nicht gespeichert.** Das Landesamt weist
sie nicht aus; die Division ist unsere und steht auf der Seite als solche
gekennzeichnet. Gespeichert werden Messzahl und Einwohnerzahl getrennt, sonst
ließe sich später nicht mehr unterscheiden, was amtlich ist und was gerechnet.

### Drei Proben, und eine davon prüft zwei Dokumente gegeneinander

- **`lsn_zweijahresueberlappung`** — Jede KFA-Ausgabe nennt zwei Ausgleichsjahre
  nebeneinander. Das ältere muss die Hauptspalte der Vorjahresausgabe
  wiederholen, **für jede der 403 Gemeinden**. Das ist die stärkste Probe des
  Bereichs: Sie prüft nicht eine Rechnung innerhalb eines Dokuments, sondern
  zwei Veröffentlichungen gegeneinander. Gemessen: 403 von 403 identisch.
- **`lsn_hebesatzprobe`** — `Grundbetrag × Hebesatz = Ist-Aufkommen`, die
  Definition einer Realsteuer. Bei der Gewerbesteuer zusätzlich
  `brutto − Umlage = netto`.
- **`lsn_dreijahresmittel`** — Der ausgewiesene Dreijahresdurchschnitt ist das
  Mittel der drei Jahreswerte, und geteilt durch die mitgelieferte
  durchschnittliche Einwohnerzahl ergibt er den Pro-Kopf-Wert der Zeile.

:::caution[Die Toleranz folgt der Rundung, nicht dem Gefühl]
Das LSN rundet Grundbetrag und Ist-Aufkommen auf volle Tausend Euro. Ein
Rundungsfehler von ±0,5 T€ im Grundbetrag wird mit dem Hebesatz
multipliziert — bei 500 % sind das ±2,5 T€. Eine feste Prozentschranke
verwürfe deshalb ausgerechnet die **Grundsteuer A**, deren Beträge so klein
sind (13–44 T€), dass die Rundung dort 1–3 % ausmacht. Die Schranke ist
darum `0,5 × Hebesatz/100 + 0,5`.

Und die Gewerbesteuer wird gegen **brutto** geprüft, nicht gegen netto: Die
erste Fassung prüfte gegen netto und verwarf alle acht Städte — die
Abweichung war jedes Mal auf die Tausend Euro genau die Gewerbesteuerumlage.
:::

### Drei Fallen im Dateiformat

1. **Der Städtename ist nicht stabil.** KFA 2025 schreibt `Oldenburg (Oldb),
   Stadt`, KFA 2026 `Oldenburg (Oldenburg), Stadt`; `Bad Zwischenahn` bekommt
   zwischendurch ein `*`. Verbunden wird über die **Schlüsselnummer**.
2. **Die Schlüsselnummer hat zwei Schreibweisen** — sechsstellig im
   Finanzausgleich (`403000`), dreistellig im Realsteuervergleich (`403`).
   `schluessel_normalisieren()` gleicht das an; ohne sie fänden die beiden
   Reihen einander nie, und der Fehler wäre still.
3. **Die Spaltenposition ist keine Zusage.** Gelesen wird über den
   ausgeschriebenen Tabellenkopf, den das LSN als Vorlesehilfe für
   Screenreader mitliefert — und **wo** er steht, sagt die Datei in ihren
   ersten Zeilen selbst („Der Tabellenkopf für Vorlesehilfen befindet sich in
   Zeile 14"). Fehlt der Hinweis, bricht der Parser ab, statt zu raten.

### Kein neues Paket, kein Cron

XLSX ist ein ZIP mit XML darin; `council/staedtevergleich.py` liest beides mit
der Standardbibliothek. Ein Extra-Paket nur für einen jährlichen Ingest käme in
`requirements.txt` und damit auf den Server — dieselbe Überlegung, aus der
`fastembed` draußen steht. Eine Dokumenttyp-Deklaration lehnt der Leser ab
(eine echte Tabellenmappe hat keine), womit die Entity-Expansion-Lücke der
Standardbibliothek zu ist.

Beide Quellen erscheinen **einmal jährlich**, deshalb kein Cron. Die
Download-Adressen des LSN tragen undurchsichtige Nummern (`/download/227086`),
die sich nicht hochzählen lassen; sie stehen auf der Übersichtsseite und
werden beim jährlichen Lauf mitgegeben:

```bash
python scripts/ingest_staedtevergleich.py \
  --kfa <KFA N, Datei oder Adresse> \
  --kfa-vorjahr <KFA N−1> \
  --realsteuer <Realsteuervergleich>
```

Der Lauf **schreibt nichts**, wenn die Zwei-Jahres-Überlappung scheitert; eine
einzelne Stadt, deren Hebesatzprobe nicht aufgeht, fällt mit Begründung heraus,
ohne den Jahrgang mitzunehmen.

:::danger[Nicht mit `council_steuerkraft` mischen]
Beide Tabellen führen Steuerkraftmesszahlen, und sie sind **nicht** dasselbe.
Unser Open-Data-Datensatz 1106 trägt dieselben Beträge wie das LSN, aber unter
einer um **ein Jahr verschobenen** Beschriftung: Was das LSN „KFA 2026" nennt,
heißt dort „Ausgleichsjahr 2025" (drei Wertepaare geprüft, zwei unabhängige
Wege). Welche Angabe stimmt, ist offen und wird bei der Statistikstelle der
Stadt geklärt.

Bis dahin liegen die LSN-Werte in einer **eigenen Tabelle**
(`council_staedtevergleich`) mit der Jahresangabe des Landesamts, und kein
Lesepfad legt die beiden Reihen zusammen. Sie zu mischen hieße, zwei Jahre
gegeneinander zu plotten, die nicht dasselbe meinen. Die Seite nennt den
offenen Punkt in ihrem Grenzen-Block — `/haushalt/steuer` zeigt dieselben
Beträge unter der anderen Beschriftung.
:::

## Was bewusst fehlt

Der Bereich zeigt lieber eine Lücke als eine Schätzung:

- **Produktebene 2024 und 2025** — die Teilhaushalts-Pläne liegen als Anlage
  vor, aber ihr Tabellenlayout hat sich geändert: Zwischen „21. ordentliches
  Ergebnis" und den Zahlen stehen jetzt zwei Beschriftungszeilen
  („Jahresüberschuss(+) / Jahresfehlbetrag (-)"), und die Prüfsumme
  *Erträge − Aufwendungen = Ergebnis* greift ins Leere. Der Bestand bleibt
  deshalb bei 2023 stehen. Genau dieser Fall ist der Grund für den Hinweis aus
  `check_finanzdaten.py`: „Dokument liegt vor, wird aber nicht übernommen".
- **Der Schlussbericht 2024** — sein PDF bringt keine Zeichenzuordnung mit,
  der Volltext besteht aus Glyphen-Nummern (`/12 /8 /6 □ /13 …`) und läuft in
  die 400.000-Zeichen-Kappung. Eine zweite Kopie gibt es nicht; ein neuer
  Versuch bräuchte OCR. Der Jahrgang scheitert schon an der
  Textanfang-Erkennung, ganz ohne Sonderfall — und die Seite sagt das, statt
  es zu überspielen.
- **Vollständige Produktebene** — für einige Teilhaushalte fehlen auslesbare
  Dokumente; die Abdeckung schwankt je Jahr zwischen 63 % und 82 %.
- Der Open-Data-Datensatz 1102 enthält abweichende Aufwendungen (2024: 764,7
  statt 728,2 Mio. €), ist aber weder als Ist noch als Nachtrag
  gekennzeichnet; genutzt wird daraus nur die Einwohnerspalte.
- **Grundsteuer A und B getrennt** — das Portal führt sie in einer Spalte.
  Deshalb eine gemeinsame Karte und im Labor kein Grundsteuer-Regler.
- **Gebühren und Beiträge** — in keinem der Datensätze enthalten.
- **Hebesatz-Zeitreihe** — die Sätze der Vorjahre liegen im Realsteuervergleich
  (Blatt 1) nur nach Größenklassen vor, nicht je Stadt; und über die
  Grundsteuerreform 2025 hinweg wären sie ohnehin nicht vergleichbar. Der
  Städtevergleich selbst steht seit 08/2026 unter `/haushalt/vergleich`.
- **Verschuldung pro Einwohner im Städtevergleich** — Anlage 2 der
  Gesamtabschlüsse führt sie über acht Jahrgänge samt Osnabrück, Braunschweig
  und Hannover, und die Vorjahres-Kette schließt dort 4/4. Nicht gebaut, weil
  die Vergleichsstädte **nicht aktuell** sind (Braunschweig 2016 gegen
  Oldenburg 2024, vom Dokument selbst markiert) — eine Grafik ohne Jahr an
  jedem Balken wäre still falsch, und das gehört sorgfältig gemacht statt
  nebenbei.

## Befunde aus dem Datenabgleich

Beim Abgleich der Entwürfe mit den echten Zahlen fielen Annahmen durch, die
plausibel klangen:

- **Die Finanzkrise 2009 ist in Oldenburg nicht sichtbar.** Die Gewerbesteuer
  stieg 2009 von 58,9 auf 61,9 Mio. €. Die realen Einbrüche liegen 2000
  (−8,5) und 2003 (−7,8); Corona 2020 kostete nur 3,8 Mio. Die Ist-Kurve
  berechnet ihre Marker deshalb aus den Daten, statt Geschichte zu deuten.
- **Der Finanzausgleich dämpft, aber nicht mit festem Faktor.** Ausgleichs-
  jahr 2024 → 2025 stieg die Steuerkraft um 45,9 Mio. €, während die
  Zuweisungen um 30,4 Mio. fielen; 2025 → 2026 stiegen beide. Der Effekt ist
  systematisch real, seine Höhe hängt am Landestopf — das Labor beziffert ihn
  deshalb nicht, sondern benennt ihn mit den echten Jahreszahlen daneben.
- **Stiftungsvermögen ist keine freiwillige Leistung.** Es ist zweckgebunden
  und wird treuhänderisch verwaltet; als kürzbar geführt hätte das Labor eine
  Handlungsmöglichkeit behauptet, die es nicht gibt.
- **Bestätigt:** Alle überwiegend freiwilligen Bereiche zusammen kosten
  47,1 Mio. € — das geplante Defizit beträgt 71,1 Mio. Kürzen allein schließt
  es rechnerisch nicht.

### Der Datensatz 1106 ist um ein Jahr verschoben

Der einzige Fall bisher, in dem wir eine Quelle **korrigieren** statt sie zu
übernehmen — und der einzige, der eine so lange Begründung verdient.

Der Open-Data-Datensatz 1106 („Steuerkraftmesszahlen und Schlüsselzuweisungen")
führt seine Spalte als `Ausgleichsjahr`, beschriftet die Zeilen aber um ein
Jahr zu früh. Geprüft am 16.08.2026, an drei unabhängigen Strängen:

1. **Das Landesamt für Statistik Niedersachsen (LSN)** — die Stelle, die den
   Begriff definiert und die Zahlen liefert. Seine KFA-Tabellen (Blatt
   `ST_KR_MESS_VGL`, Schlüssel-Nr. 403000) tragen dieselben Beträge auf den
   Euro genau, nur ein Jahr später: **12 von 12** Steuerkraftmesszahlen aus
   den Jahrgängen KFA 2016–2026 decken sich mit der CSV-Zeile `Jahr−1`,
   **keine einzige** mit der gleichnamigen. Für die Schlüsselzuweisungen
   (Blatt `9a`) gilt dasselbe; die Ausreißer sind durchweg vorläufige Stände,
   die das LSN später selbst korrigiert hat.
2. **Die Bücher der Stadt** — und das entscheidet die Frage, weil es kein
   Beschriftungs-, sondern ein Kassenfakt ist. Der Haushaltsplan 2026 weist
   als **Ist 2024** 99.569.132 € Schlüsselzuweisungen aus (Konten 31111000 +
   31112000), der Haushaltsplan 2025 als **Ist 2023** 100.319.768 € — beide
   stehen in der CSV eine Zeile zu früh. Der Jahresabschluss 2024 nennt im
   Fließtext „rund 109,5 Millionen Euro" und trifft damit den LSN-Nettobetrag
   des Ausgleichsjahrs 2024.
3. **Die Metadaten widersprechen sich selbst.** Die Spalte heißt
   „Ausgleichsjahr", die Datensatzbeschreibung spricht von „für jedes
   Haushaltsjahr". Der Widerspruch ist im Portal nicht aufgelöst.

**Was wir daraus machen:** `haushalt.parse_steuerkraft` rückt jede Jahreszahl
um eins nach vorn; `council_steuerkraft.jahr` ist damit das Ausgleichsjahr,
wie es die Tabelle ohnehin immer behauptet hat. Die beiden Pro-Kopf-Spalten
des Datensatzes bleiben liegen — die Stadt rechnet sie gegen die
Einwohnerzahl ihrer eigenen, verschobenen Jahresangabe (16 von 16 Mal von
2010 bis 2025 nachgerechnet), nach dem Rücken stünde eine
Ausgleichsjahr-Zahl über einem Nenner aus dem Vorjahr.

**Was offen bleibt:** Direkt belegt ist der Versatz für die CSV-Jahre
2015–2025; weiter zurück stellt das LSN nichts mehr online. Dass die Reihe
durchgehend derselben Konvention folgt, zeigt die Pro-Kopf-Probe oben auch
für die Jahre davor — ein Bruch mitten in der Reihe müsste sich dort zeigen
und tut es nicht. Gemeldet werden sollte der Befund trotzdem: Ansprechpartner
laut Katalog ist die Statistikstelle der Stadt Oldenburg.
