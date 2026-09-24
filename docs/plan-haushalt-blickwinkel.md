# Plan: Drei neue Blickwinkel auf den Haushalt

> Tims Auftrag vom 24.09.2026, zweiter Teil: die Vorschläge 9–11 als eigener
> Plan. Anders als die acht Quellen in
> [`plan-haushalt-datenquellen.md`](plan-haushalt-datenquellen.md) liegt hier
> nichts im Bestand. Jede Quelle ist neu und beantwortet eine Frage, die der
> Haushalts-Bereich heute nicht stellt:
>
> - **Woher kommt Geld von außen?** (Fördermittel von EU, Bund, Land)
> - **Darf die Stadt das überhaupt?** (Genehmigung durch die Kommunalaufsicht)
> - **Wie steht Oldenburg im Bund da?** (Vergleich über Niedersachsen hinaus)
>
> Arbeitsplan für ein anderes Modell; Entscheidungen für Tim oben.

## 0. Anknüpfungspunkte im Repo

| Baustein | Wo | Rolle hier |
|---|---|---|
| Einnahmen-Seite mit Karten nach Spielraum | `app/(app)/haushalt/einnahmen`, `lib/haushalt-taxes.ts` (`STEUERARTEN`) | Fördermittel werden eine weitere Karte |
| Haushaltssatzung (Entwürfe) | `council_budget_bylaw`, `scripts/ingest_haushaltssatzung.py` | Die Ingest-Ausgabe sagt selbst: „Alle sind Verwaltungsentwürfe — die beschlossene Fassung steht im Amtsblatt“ |
| Haushalts-Zeitleiste | `/haushalt/mitreden#termine`, `/api/council/budget/journey` | bekommt die Schritte „genehmigt“ und „in Kraft“ |
| Städtevergleich | `council_city_comparison`, `/haushalt/vergleich` | Bundesvergleich als zweite Ebene |
| Herkunft, Beleg, Datenstand | `council/herkunft.py`, `council/finanzquellen.py` | unverändert Pflicht |

## 1. Was die Quellen hergeben (recherchiert 24.09.2026)

| # | Quelle | Form | Was drinsteht | Lizenz/Zugang |
|---|---|---|---|---|
| 9a | [Liste der Vorhaben EFRE/ESF+ Niedersachsen](https://www.europa-fuer-niedersachsen.niedersachsen.de/startseite/regionen_und_foerderung/efre_und_esf/liste-der-vorhaben-152610.html) | XLSX, halbjährlich | Begünstigter, Vorhaben, förderfähige Ausgaben, EU-Beitrag. Oldenburg z. B. „Resiliente Innenstädte“, 4,2 Mio. € bis 2027 | EU-Pflichtveröffentlichung, frei |
| 9b | [Förderkatalog des Bundes](https://foerderportal.bund.de/foekat/jsp/DefaultAction.do?actionMode=hilfeschnellsuche) | Web-Suche, Export | Zuwendungsempfänger, Thema, Summe, Laufzeit, Ressort | frei; deckt vor allem Projektförderung ab, **nicht** Städtebauförderung über das Land |
| 9c | RIS selbst | Vorlagen „Förder…“, „Zuwendungsbescheid“ | eigene Anträge und Bescheide | im Bestand, 12 Vorlagen |
| 10a | [Amtsblatt der Stadt Oldenburg](https://www.oldenburg.de/startseite/buergerservice/bekanntmachungen/amtsblatt.html) | PDF je Ausgabe | beschlossene Haushaltssatzung, Genehmigungsvermerk des Innenministeriums | frei |
| 10b | [Pressemitteilung „Haushalt 2026: Ministerium gibt grünes Licht“](https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/stadtverwaltung/finanzen/haushalt-2026/haushalt-2026-ministerium-gibt-gruenes-licht.html) | HTML | laut Suchauszug: Satzung genehmigt, im Amtsblatt am 17.04.2026, in Kraft am 29.04.2026; Wirtschaftspläne EGH und Bäder am 16.06.2026 genehmigt | frei |
| 10c | RIS 26/0389 | Antrag Bündnis 90/Die Grünen „Kommunalaufsicht: Kredite noch nicht genehmigt“ (Finanzausschuss 06.05.2026) | der politische Streit um die Genehmigung | seit #1523 im Bestand |
| 11 | [Wegweiser Kommune](https://www.wegweiser-kommune.de/kommunen/oldenburg-oldenburg) (Bertelsmann) | Datenportal, Zeitreihen ab 2006 | Finanzindikatoren je Kommune (Steuereinnahmen, Kassenkredite, Schulden je Einwohner) | **CC0**, laut [Nutzungsbedingungen](https://www.wegweiser-kommune.de/nutzungsbedingungen) |

## 2. Entscheidungen für Tim

1. **Förderungen: nur die Stadt oder auch ihre Gesellschaften?** VWG, EGH und
   Klinikum bekommen eigene Mittel. *Empfehlung:* Stadt und die Gesellschaften
   aus `council_companies`, getrennt ausgewiesen, nie addiert (dieselbe Regel
   wie beim Konzern).
2. **Förderungen: eingehend oder auch ausgehend?** Die Zuschüsse der Stadt an
   Dritte kommen mit PR 3 des ersten Plans. *Empfehlung:* hier nur eingehend.
   Eine Seite „Geld rein, Geld raus“ erst, wenn beide Reihen stehen.
3. **Genehmigung: wie tief?** Die Verfügung des Ministeriums selbst liegt
   nicht öffentlich vor, nur ihr Vermerk im Amtsblatt und die Pressemitteilung.
   *Empfehlung:* Datum, genehmigte Kreditsumme, Auflagen, soweit gedruckt;
   keine Spekulation über den Inhalt der Verfügung.
4. **Bundesvergleich: gegen wen?** *Empfehlung:* kreisfreie Städte zwischen
   100.000 und 250.000 Einwohnern (rund 40 Städte), dazu Niedersachsens acht
   als eigene Farbe. Kein Ranking, nur Lage und Spannweite (Regel aus
   `/vergleich`: „bewusst fehlt“).
5. **Wegweiser Kommune vs. Regionaldatenbank** (PR 7 im ersten Plan) messen
   teils dasselbe. *Empfehlung:* Regionaldatenbank für die amtlichen Rohwerte,
   Wegweiser nur für Kennzahlen, die dort schon methodisch sauber bereinigt
   sind (z. B. Kassenkredite je Einwohner); Doppelungen nicht zeigen.

## 3. Reihenfolge

| PR | Blickwinkel | Aufwand | Ergebnis |
|---|---|---|---|
| B1 | Genehmigung und beschlossene Satzung (10) | S–M | Zeitleiste: beschlossen → genehmigt → in Kraft; Satzungszahlen in beschlossener Fassung |
| B2 | Fördermittel von außen (9) | M | `/einnahmen`: Karte „Fördermittel von EU und Bund“, Liste der Vorhaben |
| B3 | Bundesvergleich (11) | M | `/vergleich`: Oldenburg in der Spannweite vergleichbarer Städte |

B1 zuerst: klein, schließt eine bekannte Lücke (nur Entwürfe im Bestand) und
hat einen aktuellen Anlass (26/0389).

## 4. Die PRs

### PR B1 — Beschlossene Satzung und Genehmigung

- **Abruf** `scripts/check_amtsblatt.py`: Übersicht der Amtsblatt-Ausgaben
  (oldenburg.de), je Ausgabe das PDF; höflich (≥ 1 s Abstand, Regel
  „Fremde RIS höflich abfragen“). Nur Ausgaben, deren Inhaltsverzeichnis
  „Haushaltssatzung“ oder „Wirtschaftsplan“ nennt.
- **Parser** `council/amtsblatt.py`: die Satzung mit demselben Leser wie
  `ingest_haushaltssatzung.py` (§ 1–§ 6), dazu der Genehmigungsvermerk
  („… mit Verfügung vom … genehmigt“), Datum der Bekanntmachung, Datum des
  Inkrafttretens, genehmigter Gesamtbetrag der Kredite, Auflagen (Wortlaut).
- **Speichern** `council_budget_bylaw` bekommt `stage`
  (`draft` | `published`) und `approved_on`, `published_on`, `in_force_on`,
  `approval_note`. Die Entwurfszeile bleibt stehen; die Seite zeigt beide,
  wenn sie abweichen.
- **Probe** Kreditermächtigung und Liquiditätskredit der veröffentlichten
  Fassung gegen den Entwurf: jede Abweichung wird ausgewiesen, nicht
  überschrieben. Summe § 1 gegen `council_budget` (beschlossener Plan).
- **Seite** `/mitreden#termine`: zwei neue Stationen „genehmigt“ und „in
  Kraft“; `/schulden`: Rahmen „genehmigte Kredite“ neben dem Entwurf. Die
  Vorlage 26/0389 erscheint als Debattenpunkt an der Station „genehmigt“.
- **Cron** in `check_finanzdaten` als Quelle `amtsblatt` (monatlich reicht).
- **Fertig, wenn** 2019–2026 je Jahr Satzung, Genehmigungs- und
  Inkrafttretens-Datum stehen, und die Datenstand-Zeile „Alle sind
  Verwaltungsentwürfe“ verschwindet.

### PR B2 — Fördermittel von außen

- **Quellen**
  1. EFRE/ESF+ „Liste der Vorhaben“ (XLSX, halbjährlich): filtern auf
     Begünstigte, die zur Stadt oder einer Gesellschaft aus
     `council_companies` gehören (Namensliste kuratiert, nicht unscharf
     abgleichen).
  2. Förderkatalog des Bundes: Suche „Stadt Oldenburg“ und die Namen der
     Gesellschaften, Export; Abruf höflich und selten (monatlich).
  3. RIS: Vorlagen „Förderantrag“/„Zuwendungsbescheid“ als Verweis am
     Vorhaben, wo Titel und Summe übereinstimmen.
- **Tabelle** `council_grants_received(source, source_id, recipient,
  recipient_key, title, program, funder, amount_eligible, amount_granted,
  start, end, herkunft_id)`.
- **Probe** je Quelle: Summenzeile der Datei, wo es eine gibt; Dubletten
  zwischen EU- und Bundesliste nach Titel + Zeitraum ausschließen.
- **Seite** `/einnahmen`: Karte „Fördermittel von außen“ (Spielraum-Stufe:
  „begrenzt“ — man muss sich bewerben), darunter die Vorhaben als Liste mit
  Geber, Summe, Laufzeit. KI-Frage: Facette `foerdermittel`.
- **Grenzen offen sagen** Städtebauförderung und Landesprogramme stehen in
  keiner der Listen vollständig. Die Karte nennt, was sie nicht zeigt.
- **Fertig, wenn** beide Listen eingelesen sind und jede Zeile einen Beleg
  hat.

### PR B3 — Oldenburg im Bundesvergleich

- **Quelle** Wegweiser Kommune (CC0): Finanzindikatoren je Kommune als
  Zeitreihe. Erst messen, ob es einen Massen-Download gibt (Datenportal
  `/daten`); sonst je Kommune abrufen, gedrosselt.
- **Vergleichsgruppe** nach Entscheidung 4, als Liste im Code
  (`council/vergleichsgruppe.py`), mit Einwohnerzahl und Stand.
- **Speichern** `council_city_comparison` mit `scope = 'bund'`, Indikator,
  Jahr, Wert, Quelle.
- **Probe** Oldenburgs Werte gegen die eigenen Reihen
  (`council_debt`, `council_taxes`), Toleranz aus der Methodik des Portals;
  bei Abweichung erscheint der Wert nicht.
- **Seite** `/vergleich`: je Kennzahl ein Streifen mit Spannweite, Median und
  Oldenburg als Punkt; Niedersachsens Städte hervorgehoben. Kein Rang, keine
  Bewertungsfarbe.
- **Fertig, wenn** drei Kennzahlen über fünf Jahre für die ganze
  Vergleichsgruppe stehen.

## 5. Risiken

| Risiko | Gegenmittel |
|---|---|
| Förderlisten nennen Begünstigte uneinheitlich | kuratierte Namensliste statt Fuzzy-Match; unzugeordnete Zeilen zählen und melden |
| Amtsblatt-Seite ändert ihr Layout | Abruf über das PDF-Inhaltsverzeichnis, nicht über HTML-Klassen; Alarm, wenn eine erwartete Satzung ausbleibt |
| Bundesvergleich lädt zum Ranking ein | Darstellung ohne Rang, Methodik-Hinweis wie auf `/vergleich` |
| Doppelte Kennzahlen aus Wegweiser und Regionaldatenbank | Entscheidung 5, eine Quelle je Kennzahl |
