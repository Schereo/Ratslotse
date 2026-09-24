# Plan: Acht Haushaltsquellen, die wir haben oder frei bekommen

> Tims Auftrag vom 24.09.2026: Nach der Fehlerprüfung (#1523–#1535) einen Plan
> schreiben, wie die Quellen 1–8 aus der Vorschlagsliste geholt und eingebunden
> werden. Die neuen Blickwinkel 9–11 stehen in
> [`plan-haushalt-blickwinkel.md`](plan-haushalt-blickwinkel.md).
>
> Das Dokument ist ein Arbeitsplan für ein anderes Modell. Oben stehen die
> Messungen und die Entscheidungen für Tim, danach die PRs in Bau-Reihenfolge.
> Jeder PR geht nach `dev`, bringt seinen Parser, seine Probe, seinen
> Ops-Lauf und ein Changelog-Fragment mit.

## 0. Was es schon gibt

| Baustein | Wo | Für diesen Plan |
|---|---|---|
| Quellen-Registry | `council/finanzquellen.py` (`Finanzquelle`, `Erkennung`, `bestandsschutz`) | Jede neue Schicht bekommt dort einen Eintrag, sonst sieht sie weder der Cron noch der Datenstand |
| Cron | `scripts/check_finanzdaten.py` (Prod, sonntags 6:00) | liest neue Einheiten nach, sobald ein Dokument im Bestand liegt |
| Ops-Lauf | `.github/workflows/ops-finanzdaten-ingest.yml` (`umgebung=prod`) | jeder neue Ingest gehört in dessen Skriptliste |
| Planjahre-Parser | `council/income_budget.py` (Anlage 005, Gesamtergebnishaushalt) | Vorlage für Anlage 006 |
| Wirtschaftsplan-Leser | `scripts/ingest_wirtschaftsplaene.py` („Aus dem Erfolgsplan der Anlage“, bisher nur AWB) | wird für BBGO/BBO/Hafen erweitert |
| Gesellschafts-Kennzahlen | `council_company_indicators` (Beteiligungsbericht; 14 Gesellschaften; `bilanzsumme`, `jahresergebnis`, `eigenkapitalquote` bis 2024) | bekommt eine zweite Herkunft |
| Städtevergleich | `council_city_comparison`, `scripts/haushalt_vergleich.py` | wird um Kassen-, Schulden- und Personalstatistik ergänzt |
| Herkunft/Beleg | `council/herkunft.py`, `lib/haushalt-quellen.ts` | jede Zahl mit Dokument, Fundstelle, bestandener Probe |

## 1. Messungen (24.09.2026, Prod-Abzug)

| # | Quelle | Im Bestand | Umfang |
|---|---|---|---|
| 1 | Jahresabschlüsse der Gesellschaften (Bilanz, GuV, Lagebericht als je eigene Anlage) | Vorlagen „…: Jahresabschluss 20xx“ | 4 je Jahr 2018–2021, 5 (2022/23), **7 für 2024 und 2025** (VWG, OTM, VHS, WEH ×2, Stadion ×2). Bilanz und GuV je 1–2 Seiten, Textebene `ok` |
| 2 | Gesamtfinanzhaushalt, Anlage 006 | 8 Anlagen, 2019–2026 | je 4 Seiten; Kopf „Ergebnis 2024 · Ansatz 2025 … Ansatz 2029“, Posten 01–40 wie im Muster |
| 3a | Vorbericht, Anlage 001 | 8 Verwaltungsentwürfe 2019–2026 (+ Dubletten) | 79–98 Seiten; Kapitel 2.1.1 Fehlbeträge, 2.2 Steuerarten, 2.4.1.3 Personalaufwand, 2.4.2.x je Teilhaushalt, 3.2 Investitionen |
| 3b | Übersichten, Anlage 003 | 8 Stück 2019–2026 | 42–46 Seiten: **Zuweisungen und Zuschüsse an Dritte** (je Produkt, Empfänger/Zweck, zwei Jahre), Stand der Schulden, Verpflichtungsermächtigungen, Produktgruppen |
| 4 | Wirtschaftsplan-Anlagen BBGO, BBO, Hafen | ~25 Anlagen 2019–2026 | 2–12 Seiten; im Bestand steht bisher nur das Jahresergebnis aus dem Beschlusstext |
| 5 | Budgetberichte der Fachausschüsse | 67 Vorlagen | Jugendhilfeausschuss 25, Schulausschuss 13, dazu THH07-Finanzberichte; ob sie eine gemeinsame Tabelle führen, ist **nicht gemessen** |
| 6 | Open Data „Haushaltsplan der Stadt Oldenburg“ | 2022–2025 eingelesen (`INVESTITIONEN_CSV_URLS`) | **2020 und 2021 fehlen.** Gliederung ist der Teilhaushalt, nicht das Konto. 2021 ist *eine* CSV mit zwei Blöcken (Ergebnishaushalt, Finanzhaushalt), ab 2022 je eine Datei |
| 7 | LSN-Online | Steuerkraft (nur 2026), Realsteuern 2023–2025, Gewerbesteuer 2017–2021 | Kassenstatistik, Schulden je Einwohner, Personalstand fehlen ganz |
| 8 | Regionaldatenbank Deutschland (GENESIS) | nichts | Statistiken 71517 (Kassenergebnisse, vierteljährlich), 71327 (Schulden), 74111 (Personalstand); Web-API braucht ein kostenloses Konto |

## 2. Entscheidungen

**Tim hat am 24.09.2026 entschieden: alle fünf Empfehlungen gelten.** Zu
Punkt 2 ausdrücklich: Vereine und Träger namentlich, Privatpersonen nicht.
Zu Punkt 4: Konto bei der Regionaldatenbank (nicht Destatis-GENESIS). Die
Oberfläche dort (GENESIS 5.0.4) zeigt keinen Token an; Zugang deshalb über
`REGIONALSTATISTIK_USER` + `REGIONALSTATISTIK_PASSWORD` in der `.env`, ein
`REGIONALSTATISTIK_TOKEN` hat Vorrang, falls es ihn gibt (Header `username`
= Token, ohne Passwort).

1. **Gesellschaften: zwei Herkünfte in einer Reihe?** Beteiligungsbericht und
   RIS-Abschluss nennen für dasselbe Jahr dieselbe Zahl, der Bericht aber zwei
   Jahre später. *Empfehlung:* eine Reihe, je Wert die jüngste Quelle; weichen
   beide ab, gewinnt der Abschluss und die Abweichung steht im Beleg.
2. **Zuschüsse an Dritte: mit Namen?** Die Übersicht nennt Vereine und Träger
   namentlich. Das ist öffentlich und beschlossen, aber für die Seite neu.
   *Empfehlung:* Namen von Organisationen zeigen, keine Personen (natürliche
   Personen kommen dort praktisch nicht vor; falls doch, maskieren).
3. **Vorbericht: Zahlen oder auch Text?** *Empfehlung:* drei Tabellen als
   Zahlen, die Abschnitte je Teilhaushalt als Wortlaut für die Bereichsseite und
   die KI-Frage, nie zusammengefasst.
4. **Regionaldatenbank-Konto.** Die API der Regionaldatenbank
   (regionalstatistik.de, REST/JSON, nur POST) verlangt seit 05/2025 ein
   kostenloses Konto; Zugang über Kennung + Passwort
   (`REGIONALSTATISTIK_USER`/`REGIONALSTATISTIK_PASSWORD`) oder, falls
   vorhanden, einen persönlichen Token (`REGIONALSTATISTIK_TOKEN`). Beide
   gehen als HTTP-Header, die Parameter als `application/x-www-form-urlencoded`
   im POST-Body (Anwenderdokumentation Webservice/API 5.0, 06.05.2025, § 2.1.3). *Empfehlung:* Tim legt das Konto
   an; bis dahin baut PR 7 auf den LSN-Downloads.
5. **Budgetberichte der Fachausschüsse (PR 8).** *Empfehlung:* erst messen, nur
   bauen, wenn mindestens drei Jahrgänge dieselbe Tabelle führen.

## 3. Reihenfolge

Phase A liest, was schon im Bestand liegt (kein Download, kein Konto), Phase B
holt von außen. Innerhalb der Phasen nach Nutzen je Aufwand.

| PR | Quelle | Aufwand | Ergebnis auf der Seite |
|---|---|---|---|
| 1 | Gesamtfinanzhaushalt (006) | S | `/investitionen`: geplante Investitionen bis 2029 neben dem Ist |
| 2 | Gesellschafts-Jahresabschlüsse | M | `/konzern`: Gesellschaften ein Jahr aktueller (2025) |
| 3 | Übersichten (003) | M | `/einnahmen` und Bereichsseite: wer Zuschüsse bekommt; `/schulden`: geplanter Schuldenstand, Verpflichtungsermächtigungen |
| 4 | Wirtschaftsplan-Anlagen BBGO/BBO/Hafen | S | `/konzern` Betriebe: Erträge und Aufwendungen statt nur Ergebnis |
| 5 | Vorbericht (001) | M | `/einnahmen` Steuerarten-Prognose, `/personal` Personalaufwand, Bereichsseite „Was die Verwaltung schreibt“ |
| 6 | Open Data 2020/2021 | S | `/investitionen` Reihe ab 2020 |
| 7 | LSN / Regionaldatenbank | M–L | `/vergleich`: Kassenlage, Schulden, Personal der acht kreisfreien Städte |
| 8 | Budgetberichte der Fachausschüsse | ? | erst Messung (s. Entscheidung 5) |

(Die Nummern der PRs folgen der Bau-Reihenfolge, nicht der Nummer der Quelle in
der Vorschlagsliste.)

## 4. Die PRs

### PR 1 — Gesamtfinanzhaushalt (Anlage 006)

- **Parser** `council/finance_budget.py` nach dem Muster von
  `income_budget.py`: Kopfspalten „Ergebnis JJJJ · Ansatz …“ (sechs Spalten),
  Posten 01–40 mit Muster-Nummer. Beschlossen ist nur die dritte Spalte, die
  Finanzplanung wird getrennt gespeichert (wie `financial_plan` in
  `council_income_budget`).
- **Probe:** 09 = Σ01–08, 16 = Σ10–15, 17 = 09 − 16, dasselbe für Investitions-
  und Finanzierungstätigkeit. Die Ergebnis-Spalte (Ist des Vorvorjahres) gegen
  `council_cash_flow_statement` desselben Jahres; Abweichungen > 1 € melden,
  nicht speichern.
- **Tabelle** `council_finance_budget(plan_budget_year, year, kind, nr, label,
  amount, is_total, herkunft_id, fetched_at)`; Migration in
  `council/store_schema.py`, Registry-Eintrag `finanzhaushalt` (label_muster
  `%Gesamtfinanzhaushalt%`).
- **API** Feld `finance_budget` in `/api/council/budget/investments`
  (`antworten.py`), Vertrag neu schneiden.
- **Seite** `section-investitionsplan.tsx`: gestrichelte Planreihe 2026–2029
  hinter den Ist-Balken; Satz „geplant, nicht beschlossen“ für die
  Finanzplanungsjahre.
- **Tests** Fixture aus Dok. 297442 (gekürzt, wörtlich), Summenprobe, Riss bei
  verstellter Zahl.
- **Fertig, wenn** 8 Jahrgänge ohne Riss im Ops-Lauf stehen und die Seite 2029
  zeigt.

### PR 2 — Jahresabschlüsse der Gesellschaften aus dem RIS

- **Erkennung** Vorlagen „<Gesellschaft>: Jahresabschluss JJJJ“, Anlagen mit
  Label `%Bilanz%` / `%GuV%` / `%Gewinn- und Verlust%`. Zuordnung zur
  Gesellschaft über den Vorlagentitel und die Schlüssel aus
  `council_companies` (nicht über das Label: „2 Bilanz“ bei OTM).
- **Parser** `council/gesellschaft_abschluss.py`: aus der Bilanz Bilanzsumme,
  Eigenkapital, Verbindlichkeiten; aus der GuV Umsatzerlöse, Jahresergebnis.
  HGB-Gliederung, Vorjahresspalte mitlesen.
- **Probe** Aktiva = Passiva; Jahresergebnis in GuV = Jahresergebnis in der
  Bilanz; Vorjahresspalte gegen das gespeicherte Vorjahr. Gegenprobe gegen
  `council_company_indicators` aus dem Beteiligungsbericht für 2022–2024.
- **Speichern** in `council_company_indicators` mit neuer Spalte `source`
  (`beteiligungsbericht` | `jahresabschluss`), `report_year` = Abschlussjahr.
  Entscheidung 1 regelt, welche Zahl die Seite zeigt.
- **Seite** `section-gesellschaften.tsx`, `beteiligung-steckbrief.tsx`: Reihe
  bis 2025; Beleg zeigt auf die Vorlage.
- **Tests** Fixture VWG 2025 (Dok. 308012/308013).
- **Fertig, wenn** alle 7 Gesellschaften 2025 mit bestandener Bilanzprobe
  stehen.

### PR 3 — Übersichten (Anlage 003)

Drei Teile, je ein Parser in `council/uebersichten.py`:

- **Zuschüsse an Dritte** → `council_grants(budget_year, lfd_nr, sub_budget_no,
  product_no, product_name, purpose, recipient, amount_prior, amount, cash)`.
  Probe: Summe je Teilhaushalt, soweit gedruckt; sonst Anzahl Zeilen gegen
  laufende Nummer (lückenlos).
- **Stand der Schulden** → neue Planreihe neben `council_debt`.
- **Verpflichtungsermächtigungen** → `council_commitments(budget_year,
  sub_budget_no, amount, due_year)`; Probe gegen § 3 der Haushaltssatzung
  (`council_budget_bylaw`).
- **Seite** Bereichsseite `/haushalt/bereich`: Liste „Wer aus diesem Bereich
  Zuschüsse bekommt“ (sortiert nach Betrag, suchbar); `/schulden`: geplanter
  Stand und VE. KI-Frage: Facette `grants` („Wie viel Geld bekommt der
  Kulturverein X?“).
- **Fertig, wenn** 8 Jahrgänge Zuschüsse ohne Lücke in der laufenden Nummer.

### PR 4 — Wirtschaftsplan-Anlagen BBGO, BBO, Hafen

- `scripts/ingest_wirtschaftsplaene.py` liest den Erfolgsplan heute nur für
  den Abfallbetrieb. Die Leserfunktion wird je Betrieb parametrisiert
  (Postennamen des Erfolgsplans unterscheiden sich; BBGO ist eine GmbH mit
  HGB-GuV).
- **Probe** Erträge − Aufwendungen = Ergebnis; Ergebnis = Kernzahl aus dem
  Beschlusstext (die heute schon „belegt“ ist).
- **Seite** `section-betriebe.tsx`: Erträge/Aufwendungen je Betrieb; der Kasten
  „Was hier fehlt“ schrumpft entsprechend (Text rechnen, nicht schreiben).
- **Fertig, wenn** BBGO und BBO 2020–2026 mit Erträgen stehen; Hafen 2019/2020.

### PR 5 — Vorbericht (Anlage 001)

- **Zahlen** aus drei Kapiteln: 2.1.1 Fehlbeträge/Überschüsse und Rücklage,
  2.2 Steuerarten (Plan + Finanzplanung, ergänzt `council_tax_plan`), 2.4.1.3
  gesamtstädtische Personalaufwendungen. Probe: Summen gegen
  `council_income_budget` desselben Plans.
- **Wortlaut** der Abschnitte 2.4.2.x je Teilhaushalt →
  `council_budget_notes(budget_year, sub_budget_no, section, text)`. Nur
  Wortlaut, keine Zusammenfassung (Regel wie `<Warum>`).
- **Seite** Bereichsseite: aufklappbar „Was die Verwaltung zu diesem Bereich
  schreibt“; `/einnahmen`: Steuerart-Prognose bis 2029; `/personal`:
  Personalaufwand.
- **Fertig, wenn** 2019–2026 die drei Tabellen mit Probe und 13 Abschnitte je
  Jahr stehen.

### PR 6 — Open Data 2020 und 2021

- `council/haushalt.py`: `INVESTITIONEN_CSV_URLS` um 2020/2021 erweitern. 2021
  hat EINE Datei mit zwei Blöcken („Ergebnishaushalt - Haushaltssoll“,
  „Finanzhaushalt, Investitionen - Haushaltssoll“), die Zahlen teils mit
  Tausenderpunkt; der Leser muss den Block wählen.
- **Probe** Summe der Teilhaushalte = Zeile „Finanzhaushalt
  Gesamtinvestitionen“ (dieselbe Probe wie 2022–2025).
- **Fertig, wenn** `council_investments` 2020–2025 trägt.

### PR 7 — Städtevergleich aus LSN und Regionaldatenbank

- **Quellen** LSN-Online-Downloads (heute schon für Steuerkraft/Realsteuern)
  und, sobald das Konto da ist, die API der Regionaldatenbank `regionalstatistik.de`
  (Statistiken 71517, 71327, 74111) für die acht kreisfreien Städte
  Niedersachsens.
- **Kennzahlen** Kassenergebnis je Quartal (Einzahlungen, Auszahlungen,
  Liquiditätskredite), Schulden je Einwohner, Personal je 1.000 Einwohner,
  Steuerkraft der Vorjahre.
- **Speichern** in `council_city_comparison` (neue `indicator`-Werte), je
  Wert Stand und Tabellencode im Beleg.
- **Probe** Oldenburgs Wert gegen die eigene Quelle, wo es eine gibt
  (Schulden gegen `council_debt`, Liquidität gegen `council_liquidity`).
- **Seite** `/vergleich`: neuer Block „Kassenlage im Quartal“.
- **Fertig, wenn** vier Quartale und zwei Jahre Schulden für alle acht Städte
  stehen.

### PR 8 — Budgetberichte der Fachausschüsse (nur nach Messung)

Erst ein Messskript (`scripts/messe_budgetberichte.py`): je Vorlage Anlagen,
Tabellenkopf, ob „Budget“-Zeilen je Produkt geführt werden. Ergebnis als
Tabelle in diesen Plan nachtragen. Gebaut wird nur bei mindestens drei
gleichen Jahrgängen (Entscheidung 5).

**Gemessen am 24.09.2026** (`python scripts/messe_budgetberichte.py --markdown`,
39 Anlagen zu 38 Vorlagen):

| Vorlage | Gremium | THH | Stichtag | Seiten | Text | Ergebnisrechnung | Finanzrechnung | Maßnahmen | Produkte | Prognose | Maßnahmen-Nr. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 18/0030 | Jugendhilfeausschuss | 11 | 31.12.2017 | 7 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 18/0123 | Schulausschuss | 12 | 31.12.2017 | 3 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 18/0528 | Jugendhilfeausschuss | 11 | 30.06.2018 | 7 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 18/0561 | Schulausschuss | 12 | 30.06.2018 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 19 |
| 18/0689 | Jugendhilfeausschuss | 11 | 30.09.2018 | 8 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 18/0762 | Schulausschuss | 12 | 30.09.2018 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 20 |
| 19/0009 | Jugendhilfeausschuss | 11 | 31.12.2018 | 8 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 19/0152 | Schulausschuss | 12 | 31.12.2018 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 18 |
| 19/0596 | – | 11 | 30.06.2019 | 7 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 19/0633 | Schulausschuss | 12 | 30.06.2019 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 18 |
| 19/0759 | Jugendhilfeausschuss | 11 | 30.09.2019 | 7 | ja | ✓ | ✓ | – | ✓ | ✓ | 0 |
| 19/0817 | Schulausschuss | 12 | 30.09.2019 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 18 |
| 20/0004 | Jugendhilfeausschuss | 11 | 31.12.2019 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 8 |
| 20/0014 | Jugendhilfeausschuss | 11 | 30.06.2020 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 8 |
| 20/0158 | Schulausschuss | 12 | 31.12.2019 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 18 |
| 20/0493 | Schulausschuss | 12 | 30.06.2020 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 15 |
| 20/0664 | Schulausschuss | 12 | 30.09.2020 | 3 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 15 |
| 20/0733 | Jugendhilfeausschuss | 11 | 30.09.2020 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 8 |
| 21/0179 | Jugendhilfeausschuss | 11 | 31.12.2020 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 8 |
| 21/0638 | Schulausschuss | 12 | 30.06.2021 | 11 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 16 |
| 21/0648 | Jugendhilfeausschuss | 11 | 30.06.2021 | 6 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 4 |
| 21/0874 | Jugendhilfeausschuss | 11 | 30.09.2021 | 5 | ja | ✓ | – | – | ✓ | ✓ | 0 |
| 22/0177 | Jugendhilfeausschuss | 11 | 31.12.2021 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 4 |
| 22/0618 | Jugendhilfeausschuss | 11 | 30.06.2022 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 22/0798 | Jugendhilfeausschuss | 11 | 30.09.2022 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 22/0831 | Ausschuss für Stadtgrün, Umw | 9 | 30.09.2022 | 5 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 55 |
| 23/0055 | Jugendhilfeausschuss | 11 | 31.12.2022 | 6 | ja | ✓ | – | – | ✓ | ✓ | 0 |
| 23/0155 | Schulausschuss | 12 | 31.12.2022 | 10 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 16 |
| 23/0535 | Schulausschuss | 12 | 30.06.2023 | 2 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 17 |
| 23/0682 | Jugendhilfeausschuss | 11 | 30.06.2023 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 7 |
| 23/0808 | Schulausschuss | 12 | 30.09.2023 | 2 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 18 |
| 23/0832 | Jugendhilfeausschuss | 11 | 30.09.2024 | 8 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 7 |
| 24/0445 | Jugendhilfeausschuss | 11 | 30.06.2024 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 24/0737 | Jugendhilfeausschuss | 11 | 30.09.2024 | 1 | ja | – | ✓ | ✓ | – | ✓ | 6 |
| 24/0737 | Jugendhilfeausschuss | 11 | 30.09.2024 | 7 | ja | ✓ | – | – | ✓ | ✓ | 0 |
| 25/0045 | Jugendhilfeausschuss | 11 | 31.12.2024 | 8 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 25/0549 | Jugendhilfeausschuss | 11 | 30.06.2025 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 15 |
| 25/0752 | Jugendhilfeausschuss | 11 | 30.09.2025 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 15 |
| 26/0009 | Jugendhilfeausschuss | 11 | 31.12.2025 | 7 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 15 |
| 26/0596 | – | 11 | 30.06.2026 | 6 | ja | ✓ | ✓ | ✓ | ✓ | ✓ | 12 |

**Befund:** Zwei Reihen tragen dieselbe Tabelle über viele Jahrgänge —
**Jugendhilfeausschuss (THH 11)** 2017–2026 und **Schulausschuss (THH 12)**
2017–2023: Teilergebnis- und Teilfinanzrechnung mit Prognose, ab 2019/2020
zusätzlich die Investitionen je Maßnahme (I10-Nummer) mit Ansatz, Prognose,
Abweichung und einem Erläuterungstext je Maßnahme („Der Erweiterungsbau der
Krippe ist fertiggestellt …“). Die Schwelle aus Entscheidung 5 ist damit
deutlich überschritten. Neu gegenüber dem Haushaltsvollzug
(`council_budget_execution`, nur Summen je Teilhaushalt) ist die
**Maßnahmen-Ebene mit Begründung**. Der Stadtgrün-Ausschuss (THH 09) hat nur
einen Bericht (2022) und bleibt draußen. Bau als PR 8b: Maßnahmen je Stichtag
mit Prognose und Erläuterung, Probe Summe der Maßnahmen gegen die Zeile
„Auszahlungen für Investitionen“ der Teilfinanzrechnung.

## 5. Für jeden PR

- Registry-Eintrag in `finanzquellen.py`, sonst fehlt die Schicht im
  Datenstand.
- Ops-Lauf `ops-finanzdaten-ingest.yml` um den Ingest ergänzen, nach dem Merge
  einmal `umgebung=prod`.
- Fixtures wörtlich aus echten Dokumenten, Dokumentnummer daneben.
- Bild vor dem Merge an Tim (UI-Anteil), Changelog-Fragment.
- Seiten mit Prod-Abzug rendern (`lokale_daten.py hol --von prod`), auf
  „fehlt“-Sätze prüfen, die nicht mehr stimmen.

## Anhang A — Messbefehle

```bash
sqlite3 data/council.sqlite "select document_id,label,n_pages from council_attachments where label like '%Gesamtfinanzhaushalt%'"
sqlite3 data/council.sqlite "select template_number,title from council_templates where title like '%Jahresabschluss 2025%'"
sqlite3 data/council.sqlite "select document_id,label,n_pages from council_attachments where label like '%bersichten%'"
curl -s "https://opendata.oldenburg.de/sites/default/files/1101%20Haushaltsplan%20der%20Stadt%20Oldenburg%202021.csv" | iconv -f latin1 -t utf-8 | head -40
```
