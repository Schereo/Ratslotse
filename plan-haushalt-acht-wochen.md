# Haushalt, Runde 3 — vier Zwei-Wochen-Pläne (A–D)

*Stand 17.08.2026, nach Abschluss der Quellen-Recherche (dokumentiert in
`docs-site/src/content/docs/haushalt-quellen-recherche.md`) und der ersten
Umsetzungswelle daraus (#599–#602: Zensus-Fußnote, Finanzrechnung, Bilanz).*

## Grundsätze für alle vier Pläne

1. **Null neue Seiten.** Der Bereich hat 19 Routen — jede Zeile dieses Plans
   landet als Block, Erweiterung oder Korrektur auf einer bestehenden. Wo
   unten „Wohin" steht, ist das die Zielseite; ein Agent, der doch eine neue
   Route braucht, meldet das statt zu bauen.
2. **Jede Zahl trägt ihre Probe im Code** (`council/herkunft.py` erzwingt
   `art` und `probe`). Die Messwerte in diesem Plan stammen aus der Recherche
   und sind an den Originalquellen geprüft — trotzdem gilt: nachmessen, nicht
   glauben.
3. Die Anti-Patterns gelten weiter: keine Bewertungsfarben, keine
   Selbstvergewisserung, keine erfundenen Kennzahlen, Lücken sichtbar,
   Zitate wörtlich, Gendern mit Sternchen.
4. Alles bleibt hinterm Umgebungs-Gate (`HAUSHALT_FREI`). Der Release nach
   `main` ist Tims Entscheidung und kein Planinhalt — Plan D bereitet ihn
   nur vor.
5. Changelog als Fragment (`changelog.d/<slug>.md`), PRs gegen `dev`,
   nie gestackt.

---

## Plan A (Wochen 1–2): Was fast geschenkt ist — und was wegläuft

### Woche 1 — Lange Reihen, bevor sie verschwinden

**Zuerst der Archiv-Cron, dann die Parser.** Die Stadt führt kein
Jahrbuch-Archiv: Nur die jeweils neueste Ausgabe liegt online, das Internet
Archive hat vom Statistik-Verzeichnis null Schnappschüsse. Tabellen mit drei
Jahrgängen (1103, 0803) verlieren mit jeder Ausgabe ihr ältestes Jahr —
unwiederbringlich.

- **Archiv-Job** (`scripts/archive_statistik.py`, täglicher Cron): prüft
  `modified` in der Open-Data-`data.json` und eine feste Liste von
  Jahrbuch-PDFs, legt veränderte Dateien versioniert unter `data/archiv/` ab.
  `data/` läuft ohnehin durchs nächtliche Backup samt Off-Site-Mirror — kein
  neuer Speicherpfad. Takt in `kern/jobs.py` eintragen. (~0,5 Tage)
- **55 Jahre Ausgaben** (Jahrbuch/Open Data 1102): Die CSV laden wir seit
  Monaten — genutzt wird nur die Einwohnerspalte. Die Ausgabenspalte dazu:
  Verwaltungshaushalt 1972–2009, ordentliche Aufwendungen 2010–2025
  (2025: 850,17 Mio. €, Monate vor dem Jahresabschluss).
  **Wohin:** `/haushalt` (Übersicht) — die bestehende Zeitreihe wird zur
  langen Reihe mit **Naht 2009/2010** (Bruch-Marker wie bei `gebaut`; über
  die Naht wird keine Linie gezogen, die Quelle trennt dort selbst).
  **Proben:** PDF↔CSV-Abgleich (bekannte Ausnahme: CSV 2021 ist um
  4,66 Mio. € falsch, das PDF hat recht — der Jahresabschluss bestätigt es)
  und Abgleich gegen `council_ergebnisrechnung` Posten 20 (gemessener
  Versatz 0,03–0,04 %; als Toleranz formulieren oder Ursache einmal im
  Jahresabschluss klären). (~1 Tag)
- **Hebesätze seit 1980** (Jahrbuch 1105, neun Änderungsjahre):
  **Wohin:** Steuer-Steckbrief (`/haushalt/steuer?art=…`) als Zeitstrahl der
  Änderungsjahre (GB-11). **Pflicht-Kontext:** 2025 stieg der
  Grundsteuer-B-Hebesatz um 21 % — das Aufkommen **sank** im selben Jahr um
  4,6 %, weil die Reform die Messbeträge umstellte. Hebesatz nie ohne
  Aufkommen daneben. (~0,5 Tage)
- **Trifft die Stadt ihre Steuerschätzung?** (Jahrbuch 1103, Plan neben Ist
  je Steuerart): Gewerbesteuer 2023 +42,3 %, 2024 +52,1 %, 2025 +42,8 % —
  drei Jahre in Folge über 40 % unterschätzt, das ist ein Muster.
  Weder `council_ergebnishaushalt` noch `council_ergebnisrechnung`
  schlüsseln Steuern auf; die Plan-Seite je Steuerart haben wir nirgends.
  **Wohin:** Steuer-Steckbrief, Block „Geplant und geworden — nur diese
  Steuer". **Grenze ehrlich:** je Ausgabe nur drei Jahrgänge; die Reihe
  wächst ab jetzt über den Archiv-Job. (~1 Tag)
- **Klein:** dritte KFA-Komponente nachziehen (Zuweisungen übertragener
  Wirkungskreis, 10,58/11,16 Mio. € 2025/2026) — `council_steuerkraft`
  führt heute exakt Gemeinde+Kreis; Probe: Summe = „Finanzzuweisungen" in
  Jahrbuch 1103 (79.787 ≈ 79.785 T€). (~0,5 Tage)

### Woche 2 — Beschlossen am Plan vorbei

Der stärkste Fund der RIS-Recherche, mit der härtesten Probe im Bereich.

- **Über-/außerplanmäßige Bewilligungen** (§ 117 NKomVG) als Serie:
  zweistufige Extraktion (Titel-Regex trifft 140/151 = 92,7 %; die elf
  Lücken schließen alle über `council_vorlagen.beschlussvorschlag`).
  **Drei Fallen, alle vermessen:** Verpflichtungsermächtigungen zählen
  nicht in die Summe (48 Zeilen); Sitzungsdatum ≠ Haushaltsjahr
  (Januar-Beschlüsse gehören zum Vorjahr — naiv summiert liegt man
  20–27 % daneben); die zehn Sammelberichte tragen Schwellenwerte, keine
  Beträge.
- **Rechenschaftsbericht Kapitel 3 parsen** (2022–2024 im Bestand): die vier
  Entscheidungskanäle Rat / Oberbürgermeister / Fachdienst 200 /
  Eilentscheidung. **Probe:** Der RB nennt dieselben Fälle mit
  Vorlagen-Nummern — Abgleich lief in der Recherche auf 0,00 € (2022) und
  100 € (2023); 2024 weicht um +2,19 % ab, die Ursache wird benannt statt
  geglättet. Interne Tabellenprobe zeigt 2022 einen echten
  Dokument-Widerspruch (288 T€ zwischen Tabelle und Fließtext) — anzeigen,
  nicht reparieren.
- **Wohin:** `/haushalt/plan-ist`, Block unter „Warum es anders kam":
  26,97 → 40,24 → **57,49 Mio. €** in drei Jahren, Rats-Anteil 88 → 73 %.
  Jede Rats-Position verlinkt über die Vorlagen-Nummer auf ihre
  Beschluss-Seite. Der Satz „In acht Jahren wurde keine Nachbewilligung
  abgelehnt" steht nüchtern da — Befund, keine Wertung.
- **Spenden an die Stadt** (klein, ~0,5 Tage): 215 Beschlusszeilen, 213 mit
  Betrag, lückenlos monatlich seit 2018; Jahresserie 0,47–1,0 Mio. €.
  **Wohin:** `/haushalt/einnahmen`, kleiner Block „Auch das sind Einnahmen".
  Probe über „Auswirkungen a) Finanzen" (64/64 wo die Struktur existiert;
  ältere Jahrgänge ohne diese Struktur bleiben draußen statt ungeprüft
  drin). Die Schwellenlogik (OB bis 100 €, VA bis 2.000 €, Rat darüber)
  erklärt nebenbei, wie Zuständigkeit funktioniert.
- **`council/money.py`-Hygiene:** Stückpreise im Fließtext („1,00 € für das
  Tagesticket", „6,00 € Parkgebühr") landen heute als Beschlussbetrag;
  Sammelbericht-Schwellen (50.000) ebenso; bei 31,8 % der Texte mit
  mehreren Beträgen gewinnt blind der größte (Deckungsvorschlags-Falle).
  Muster nachschärfen, Tests, Wirkung am Bestand messen.

---

## Plan B (Wochen 3–4): Vermögen und Verpflichtungen zu Ende erzählen

### Woche 3 — Was hinter der Bilanz steckt

- **`MAX_TEXT` anheben** (`scripts/backfill_anlagen_texte.py`, heute
  400.000): kappt alle acht Jahresabschlüsse exakt an der Grenze —
  abgeschnitten ist ausgerechnet Abschnitt 8 „Anlagen zum Anhang"
  (Anlagen-, Forderungs-, Schulden-, Rückstellungsübersicht). Erst klären,
  warum das Limit existiert (DB-Größe? FTS?), dann anheben — notfalls nur
  für die Finanz-Muster der Registry. Backfill `--nur-finanz` erneut,
  Zugewinn messen. **Vorher Sichtung:** Das Layout von Abschnitt 8 ist
  ungeprüft; Abbruchkriterium definieren, bevor ein Parser entsteht.
- **Anlagenspiegel parsen:** Zugänge, Abgänge, Abschreibungen je
  Vermögenskategorie. **Probe:** Anfangsstand + Zugänge − Abgänge − AfA =
  Endstand, und Endstand = Bilanzposition. **Wohin:** `/haushalt/gebaut` —
  der fehlende Schluss der Geschichte: „Aus Investitionen wird Vermögen —
  und es schrumpft trotzdem." Dort auch der **Substanzverlust am
  Straßennetz** (das Wort ist das der Stadt): Straßen, Wege, Plätze
  210,9 → 133,3 Mio. € Buchwert 2016–2024, rund −9,6 Mio. €/Jahr.
  Untertabelle fehlt 2019/2020 (LueckenFeld); die Gesamtsumme
  Infrastrukturvermögen steht in allen acht Jahrgängen in der Bilanz.
  Kategoriegrenzen verschieben sich mindestens einmal (Umgliederung 2021)
  — jahrgangsabhängiger Zeilensatz, sonst reißt die Probe zu Recht.
- **Die Bewegung hinter dem Schuldenstand** (klein): Rechenschaftsbericht
  2.2.1 — Kreditaufnahme 2024: 0,00 €, Tilgung 2,89 Mio. €, Kettenprobe
  über drei Berichte geht auf, Endstände decken sich mit
  `council_schulden.kreditmarkt`. **Wohin:** `/haushalt/schulden`, zwei
  Zeilen im Bestand-Kopf („aufgenommen / getilgt"). Die dort genannte
  „Zinsersparnis" ist eine Gegenrechnung der Stadt — als Selbstauskunft
  kennzeichnen oder weglassen.

### Woche 4 — Die Schulden-Seite wird vollständig

- **Bürgschaften:** Bestand aus Anhang 6.2.10 (2024: **220,3 Mio. €** — das
  Fünffache der Geldschulden von 43,7 Mio. €; 2022 erklärt den Sprung:
  135,9 Mio. € für das Klinikum). Zwei Darreichungsformen: 2019/2020 exakte
  Tabellenwerte, ab 2021 gerundeter Fließtext — die gemischte Reihe sagt
  das dazu. Daneben der **Zeitstrahl der Bürgschafts-Beschlüsse** (25
  Vorlagen 2019–2026, alle angenommen): wann der Rat wofür gebürgt hat.
  **Niemals selbst addieren** — Verlängerungen und Anpassungen ersetzen
  einander; nur der Anhangs-Bestand ist eine addierbare Zahl. Abgrenzung
  zur Bilanzposition 3.7 (1,3 Mio. € = erwarteter Ausfall, nicht das
  Volumen) ausdrücklich.
- **Die dritte Schuldenzahl:** integrierte Schulden 740,33 Mio. € =
  4.198 €/Kopf (Statistikportal, 31.12.2024). Jetzt baubar, weil die eigene
  Bilanz danebensteht — der Kernhaushalt-Wert stimmt Cent-genau mit ihr
  überein (43.690.972). **Pflichttexte:** 58 % stammen aus Beteiligungen
  unter 50 %, die Quelle verbietet Haftungs-Rückschlüsse; **keine
  Zeitreihe** (Berichtskreis wechselt, die Publikation warnt selbst);
  Matching über ARS, nie über den Namen. Die Quelldatei wandert jährlich —
  in den Archiv-Job aufnehmen.
- **Seiten-Gliederung `/haushalt/schulden` ordnen:** Mit Bilanz (#602),
  Bürgschaften und dritter Zahl wird die Seite lang. Reihenfolge: Bestand →
  Zinsen → Kurve → Sprünge → Wer schuldet was → Bilanz → Bürgschaften →
  „Die dritte Zahl" → Grenzen. Bei 375 px nachmessen; was kippt, kommt
  hinter einen Auslöser (H4-A: nie ersatzlos).
- **Rechenschaftsberichte 2017–2021 nachladen** (Dokumente 192336, 205649,
  219465, 238770, 250437 — liegen als Anlage, `raw_text` leer) und die
  **Kennzahlenübersicht** parsen: 13 Kennzahlen, **die Rechenvorschrift der
  Stadt steht daneben gedruckt** — damit ist „keine erfundene Kennzahl"
  per Konstruktion erfüllt. 2018–2024 lückenlos, nach Backfill bis ~2013.
  `bericht_jahr` gehört in den Schlüssel (die Steuerquote 2021 wurde
  nachträglich revidiert — die Probe hat das gefunden). Namenskollision
  beachten: „Verschuldung je Einwohner" heißt hier 1.226 €, in
  `council_schulden` 1.673 € — verschiedene Abgrenzung, eigenes Label.
  **Wohin (Vorschlag, Alternativen erlaubt):** kompakte Leiste auf
  `/haushalt` „Die Stadt in ihren eigenen Kennzahlen" — fünf ausgewählte,
  alle als aufklappbare Tabelle. Kreuzprobe: sieben davon müssen sich exakt
  aus unserer geparsten Bilanz ergeben (heute 7/7).

---

## Plan C (Wochen 5–6): Schneller, klarer, zugänglicher — null neue Daten

### Woche 5 — Die Payload-Diät

Gemessen (roh, Dev-Bestand): `/council/haushalt` **1,64 MB** ·
`/haushalt/streit` 481 KB · `investitionsprogramm` 942 KB ·
`beteiligungen` 367 KB · `pruefberichte` 276 KB. Die Übersicht lädt also
mehr als manche Apps insgesamt — und mehrere Seiten holen den ganzen
Brocken für eine Handvoll Felder.

- **Endpoint aufteilen:** `haushalt_uebersicht` in konsumentenscharfe
  Teil-Antworten (oder `?felder=`-Auswahl); jede Seite holt nur, was sie
  rendert. API-Verträge über Tests absichern, Frontend-Libs nachziehen.
- **Wortlaute nachladen statt vorladen:** Bei `streit` und `pruefberichte`
  die vollen Texte erst beim Aufklappen holen (Query-Parameter,
  static-export-tauglich). Wortlaut-Politik bleibt unberührt — es ändert
  sich nur, *wann* der Text reist, nicht *ob*.
- **Transport:** Cache-Header/ETag für die Haushalts-Endpoints (Daten
  ändern sich höchstens täglich); prüfen, was Caddy an Kompression
  tatsächlich ausliefert.
- **Bundle:** schwere Grafik-Komponenten unterhalb der Falte per
  `next/dynamic` (Vorbild: Quiz in #584 — +7 statt +60 kB).
- **Vorher/Nachher messen** und in den PR schreiben: Transfergröße und
  Zeit bis zum ersten Inhalt je Seite; Ziel Übersicht < 350 KB Transfer.

### Woche 6 — Verstehen und Feinschliff

- **Glossar +12 Begriffe** (Bilanz, Nettoposition, Rückstellung,
  Pensionsrückstellung, Finanzrechnung, Ermächtigung, über-/außerplanmäßig,
  Bürgschaft, Hebesatz, Steuerkraftmesszahl, Schlüsselzuweisung,
  Anlagenspiegel) in `lib/glossary.ts`, und `GlossaryText` in den neuen
  Blöcken aus Plan A/B verdrahten — die Begriffe stehen dort gehäuft.
- **Anschlussstellen-Pass:** Verweis-Karten zwischen den Blöcken, die
  inhaltlich aufeinander zeigen (plan-ist-Kassensicht ↔ schulden-Bilanz ↔
  gebaut-Anlagenspiegel ↔ konzern), in der bestehenden Karten-Grammatik.
- **Interaktions-Konsistenz:** Jahr-Wahl überall als Scrollband (nie
  Dropdown), Datenstand-Zeile auf jeder Seite, Fundstellen-Muster der
  neuen Blöcke an die bestehenden angleichen.
- **Barrierefreiheits-Durchgang:** Tastatur (Ableseleiste, Aufklapper,
  Umschalter), `aria-label` mit Werten an jeder neuen Grafik, Fokus-Ringe,
  Kontrast im Dunkeln. Messrunde 375 px über alle 19 Seiten
  (`scrollWidth === innerWidth`), Lesebreiten-Nachzügler (76ch-Regel).
- **Copy-Durchgang** über die neuen Blöcke: Sternchen-Gendern, Lotti-Regeln
  (max. drei Sätze, keine Bewertung), „Woher diese Zahlen kommen"-Ton.
- Optional, wenn billig: „Link kopieren" an den großen Karten
  (Anker existieren durch die Blockstruktur ohnehin).

---

## Plan D (Wochen 7–8): Belastbar machen — KI, Quiz, Betrieb, Prod-Reife

### Woche 7 — Die neuen Zahlen arbeiten lassen

- **KI-Frage:** `geld_kontext` lernt Bilanz (Pensionen!), Kassensicht,
  Nachbewilligungen und Bürgschaften; FTS über `council_bilanz_erlaeuterungen`
  und die RB-Kapitel. **Messung statt Gefühl:** 15 Haushalts-Goldfragen
  (u. a. „Wie viel Schulden hat Oldenburg wirklich?" — erwartet die
  Abgrenzungs-Antwort, nicht eine Zahl; dazu die Stadion-Kostenfrage gemäß
  stehender Validierungs-Direktive), Trefferquote vorher/nachher in den PR.
- **Quiz:** drei deterministische Fragen aus den neuen Beständen
  („Was ist die größte Verpflichtung der Stadt — Kredite oder Pensionen?",
  „Hatte die Stadt 2024 am Jahresende mehr oder weniger Geld in der
  Kasse?", „Seit wann ist der Gewerbesteuer-Hebesatz unverändert?").
  `content_hash`-Disziplin wie in #584: neue Schlüssel für neue Fragen,
  nie einen Slot umdeuten. Danach `ingest_haushalt.py` auf dev.
- **Die Wette: Fraktions-Änderungslisten.** Der größte ungehobene Fund —
  „wer wollte was streichen, um wie viel" — scheitert bisher daran, dass
  die Anlagen-PDFs nie geladen wurden. **Timebox 2 Tage:** Ladetest der
  neun Kandidaten (196997/98, 210921–23, 227863–69). Haben sie eine
  Textebene → Parser, Verknüpfung mit den 171 vorhandenen
  `subvote`-Zeilen (Urheber + Ergebnis existieren schon!), Block auf
  `/haushalt/streit`. Sind es Scans → dokumentieren, OCR-Entscheidung an
  Tim, Zeit in W8-Puffer.
- **Datenfehler melden:** Entwürfe für die Statistikstelle formulieren
  (1102-CSV 2021 um 4,66 Mio. € daneben; Braunschweiger Wert in Oldenburgs
  Zeile der LSN-Datei „Kommunale Finanzen 2024"; Erinnerung an den
  1106-Jahresversatz). Versand ist Tims Sache.

### Woche 8 — Betrieb und Release-Vorbereitung

- **Cron-Hygiene:** `kern/jobs.py`-Takte für alle Finanz-Jobs (inkl.
  Archiv-Job aus W1), Admin-Ampel prüfen, und den Audit-Fund endlich
  ausräumen: der Haushalts-Cron gehört auf die **Dev**-Crontab, nicht auf
  Prod — Standort klären und bereinigen. Alert-Pfad einmal echt testen.
- **Tote-Links-Lauf:** oldenburg.de hat seine Statistik-URLs umgestellt
  (alte Pfade 404). Skript über alle externen Links des Bereichs
  (Quellen-URLs, „Dokument öffnen"), Bericht, Fixes.
- **Letzte Messrunde:** Transfer/Ladezeit nach Plan C nachmessen,
  375/744/1024 in hell und dunkel, Fehlerzustände (API weg, leerer
  Bestand) auf jeder Seite einmal provozieren.
- **Release-Dossier für Tims Go** (ausdrücklich ohne Ausführung): was auf
  Prod sichtbar würde, bekannte Grenzen je Seite, Restrisiken, und die
  Checkliste — Release-PR `dev` → `main` als **Merge-Commit**,
  Versionsschnitt mit `changelog_schnitt.py`, Prod-Ingests in Reihenfolge,
  TestFlight-Kopplung.
- **Puffer** für Funde aus W1–W7 — erfahrungsgemäß die am besten
  investierte Zeit der Runde.

---

## Reservebank (bewusst nicht eingeplant, mit Grund)

- **Jugendhilfe 0818 / Sozialhilfe 0803** (Jahrbuch): starke Bürgerfragen,
  aber 0818 liest Werte aus Diagramm-Beschriftungen (fragil), 0803 mischt
  Kostenträger (SGB-II-Block ist keine Stadtausgabe — Doppelzählungsfalle).
  Erst wenn der Archiv-Job zwei, drei Ausgaben gesammelt hat.
- **LSN „Kommunale Finanzen"-Quoten:** in der 2024er-Datei steht ein
  Braunschweiger Wert in Oldenburgs Zeile — nur mit Plausibilisierung, und
  die Deckungsquote ist Finanzrechnungs-, nicht Ergebnislogik.
- **GENESIS/regionalstatistik-Zeitreihen** (71327, 71717): sauberster
  externer Kanal, braucht aber ein (kostenloses) Konto → Tims Entscheidung.
- **Konzernbilanz + Kapitalflussrechnung** (Gesamtabschluss 2014–2024):
  lohnend, aber eigener Kontenrahmen und wechselnder Konsolidierungskreis.
- **Zuwendungen an Dritte** (koordinatenbasierter Parser, ~6 Tage) und
  **B-Plan-Planzeichnungen als Bild** — beide unverändert gültig, beide
  größer als ein Wochenslot.

## Entscheidungen, die nur du treffen kannst

1. **GENESIS-Konto** anlegen (kostenlos, öffnet 71327/71717-Zeitreihen)?
2. **Statistikstellen-Mails** abschicken (Entwürfe kommen aus W7)?
3. **Personen-Verdachtsfälle:** Georg Heß / Hans-Georg Heß zusammenführen?
   Masurkewitz/Musurkewitz als Tippfehler heilen?
4. **Release-Zeitpunkt** — Plan D endet mit dem Dossier, nicht mit dem Merge.
