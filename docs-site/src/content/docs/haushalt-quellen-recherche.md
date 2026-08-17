---
title: "Welche Zahlen wir (noch) nicht auswerten"
description: Ergebnis der Quellen-Recherche vom 17.08.2026 — was im Bestand liegt, was extern verfügbar ist, und was bewusst draußen bleibt.
---

Vier parallele Recherchen, alle Werte an den Originalquellen geprüft. Dieses
Dokument hält fest, **was wir nicht auswerten und warum** — damit die nächste
Runde nicht dieselben Wege noch einmal geht.

Stand des Bestands beim Schreiben: 23 Finanz-Tabellen, 899 Anlagen mit
Volltext. Was wir bereits haben, steht in [Haushalt](/docs/haushalt/).

## Die stärkste Bestätigung

Zwei Recherchen fanden unabhängig voneinander **dieselbe Zahl**: Die Bilanz
der Stadt weist zum 31.12.2024 Geldschulden von **43.690.971,71 €** aus, die
Bundesstatistik für den Kernhaushalt **43.690.972 €**. Zwei Quellen, ein Cent
Rundung. Wo zwei unabhängige Wege zur selben Zahl führen, trägt sie.

## Rang 1 — Die drei Schuldenzahlen

Warum man über Oldenburgs Schulden drei verschiedene Zahlen hört, und alle
drei stimmen — je nach Abgrenzung:

| Abgrenzung | 31.12.2024 | je Einwohner | Haben wir? |
|---|---|---|---|
| Kernhaushalt, Investitionskredite | 43,69 Mio € | 248 € | nein |
| Stadt als Rechtsträger inkl. Eigenbetriebe | 294,9 Mio € | 1.673 € | **ja** (Jahrbuch 1108) |
| Integriert inkl. Extrahaushalte + Beteiligungen | 740,33 Mio € | 4.198 € | nein |

Quelle der dritten Zahl: Statistikportal, „Integrierte Schulden der Gemeinden
und Gemeindeverbände", Blatt `NI`, ARS `034030000000`. DL-DE/BY-2.0.

**Zwingend daneben:** 431,5 der 740 Mio € (58 %) stammen aus Beteiligungen
**unter** 50 %. Der Tabellenband schreibt selbst, das erlaube „keine
Rückschlüsse auf eine mögliche Haftung". Der Satz „Oldenburg hat 740 Mio €
Schulden" wäre falsch. Und: keine Zeitreihe daraus bauen — der Berichtskreis
wechselt, die Publikation warnt davor.

## Rang 2 — Die Bilanz der Stadt

Wir zeigen Schulden und die laufende Rechnung. Die **Vermögensseite** fehlt
komplett.

Zum 31.12.2024: Eigenkapital 926,87 Mio € · Sachvermögen 605,57 Mio € ·
Rückstellungen 337,21 Mio €, davon **Pensionsrückstellungen 311,79 Mio €**
(das Siebenfache der Kreditschulden, +21 Mio €/Jahr) · Bilanzsumme
1.479,99 Mio €.

**Vier Proben, alle bestanden:** Aktiva = Passiva auf den Cent in allen acht
Jahrgängen · gedruckte Bilanzsumme als dritte Bestätigung (2017–2020) ·
Vorjahreskette über Dokumentgrenzen (63 Prüfungen, 63 Treffer) · die sieben
Kennzahlen, die die Stadt im Rechenschaftsbericht selbst rechnet, ergeben
sich exakt aus der geparsten Bilanz.

Neun Bilanzstichtage 2016–2024, lückenlos. **Layout wechselt 2021** (römische
→ arabische Ziffern, Aktiva-Block → zweispaltig verschränkt) — ein Parser
braucht beide Zweige.

**Ehrlichkeitsauflage:** Die Schulden springen 2024 von 84,4 auf 207,1 Mio €.
Das ist ein **Buchungsartefakt** (Cash-Pooling, 138,2 Mio € Bilanzverlängerung
mit Gegenposten auf der Aktivseite); das Dokument erklärt es in 6.2.3/6.2.7
selbst. Ohne diesen Text wäre die Zahl still falsch.

## Rang 3 — Die Finanzrechnung

Wir zeigen die Ergebnisrechnung. Für 2024 weist die Stadt **6,1 Mio €
Jahresüberschuss** aus — und hatte am Jahresende **22,4 Mio € weniger Geld**.
Beides steht im selben Dokument, beides stimmt. Wer nur unsere Zahl sieht,
bekommt den falschen Eindruck.

2024: Saldo laufende Verwaltungstätigkeit +58,30 Mio € · Investitionstätigkeit
−80,68 Mio € · Fehlbetrag −22,38 Mio € · Auszahlungen für Investitionen
96,37 Mio € (dazu 58,77 Mio € Ermächtigungen aus Vorjahren — die Antwort auf
„warum wird das Geplante nicht gebaut?").

**Bester Aufwand-Nutzen-Schnitt im ganzen Bericht:** Die Finanzrechnung hat
dieselbe Tabellengrammatik wie die Ergebnisrechnung, die
`council/finanzberichte.py` schon parst. Belegt: `_posten_aus_block()`
**unverändert** darauf angesetzt → 30 Posten, 7/7 Proben für 2021, 2022, 2024.
2017–2020 fallen durch (anderer Tabellenkopf).

**Die stärkste Probe überhaupt:** Posten 41 „Endbestand an Zahlungsmitteln" =
Bilanzposition „Liquide Mittel", exakt in allen acht Jahrgängen. Bilanz und
Finanzrechnung tragen sich gegenseitig.

## Rang 4 — Ausgaben, die nicht im Haushalt standen

Zwei Recherchen fanden das unabhängig. Über- und außerplanmäßige
Bewilligungen nach § 117 NKomVG:

| Jahr | insgesamt | davon Rat |
|---|---|---|
| 2022 | 26,97 Mio € | 23,83 Mio € (88 %) |
| 2023 | 40,24 Mio € | 33,87 Mio € (84 %) |
| 2024 | **57,49 Mio €** | 42,17 Mio € (**73 %**) |

Die Summe hat sich in drei Jahren mehr als verdoppelt, der Anteil mit
Ratsbeschluss ist gefallen. Wer nur die Ratsbeschlüsse zeigt, zeigt eine
schrumpfende Teilmenge, als wäre sie das Ganze.

**Die Probe ist die härteste im Bereich:** Der Rechenschaftsbericht nennt
dieselben Fälle **mit Vorlagennummern**, also mit direktem Join-Schlüssel.
Abgleich: 2022 Abweichung **0,00 €**, 2023 **100 €**, 2024 +2,19 %.
Fallzahlen exakt in allen drei Jahren.

**Fallen:** Verpflichtungsermächtigungen gehören nicht in die Summe (der
Bericht zählt sie separat) · Sitzungsdatum ≠ Haushaltsjahr (Januar-Beschlüsse
zählen zum Vorjahr; naiv summiert liegt man 20–27 % daneben) · die
Sammelberichte tragen Schwellenwerte, keine Beträge.

**Nebenbefund:** In acht Jahren wurde **keine einzige** Nachbewilligung
abgelehnt — 128 angenommen im Rat, 128 im Ausschuss, 0 abgelehnt.

## Rang 5 — Fast geschenkt: 54 Jahre Ausgaben *(umgesetzt)*

**Erledigt.** Die Reihe steht seit 08/2026 auf `/haushalt`; Technik und Proben
in [Haushalt](/docs/haushalt/#die-lange-ausgabenreihe-datensatz-1102-seit-1972).
Was die Recherche gefunden hatte und was die Umsetzung daraus gemacht hat:

- Der **Versatz von 0,03–0,05 %** gegen `council_ergebnisrechnung` war keine
  Unschärfe, sondern eine Abgrenzung: Die Statistik zählt die
  *Gesamtergebnisrechnung* (Kernhaushalt **und** nicht rechtsfähige
  Stiftungen), unser Parser die *Ergebnisrechnung der Kernverwaltung*. Der
  Rechenschaftsbericht rechnet die Differenz selbst vor. Gegen die
  Gesamtergebnisrechnung stimmt die Statistik auf den Tausender genau.
- Der **2021er-Widerspruch** ist schärfer als gedacht: 613.571.622,10 € ist auf
  den Tausender genau der **Ansatz** des Jahres — in der Tabelle des
  Jahresabschlusses die Spalte links vom Ergebnis. Im CSV ist dort eine Spalte
  verrutscht. Auflösen lässt sich das ohne den Jahresabschluss, weil die
  CSV-Zeile ihre eigene Pro-Kopf-Rechnung nicht erfüllt.
- **2025** liefert die Reihe wie erwartet — Monate vor dem Jahresabschluss.

## Rang 6 — Trifft die Stadt ihre Steuerschätzung?

Jahrbuch 1103 stellt je Steuerart Plan neben Ist:

| Gewerbesteuer | Plan | Ist | |
|---|---|---|---|
| 2023 | 124,2 Mio € | 176,8 Mio € | **+42,3 %** |
| 2024 | 133,4 Mio € | 202,9 Mio € | **+52,1 %** |
| 2025 | 155,5 Mio € | 222,1 Mio € | **+42,8 %** |

Drei Jahre über 40 % Unterschätzung ist ein Muster, keine Schwankung. Weder
`council_ergebnishaushalt` noch `council_ergebnisrechnung` schlüsseln Steuern
auf — die Plan-Seite je Steuerart haben wir nirgends.

## Weitere Funde

- **Bürgschaften 220,3 Mio €** (31.12.2024), das Fünffache der eigenen
  Geldschulden. Jahresabschluss 6.2.10. Zwei Darreichungsformen: 2019/2020
  exakte Tabellenwerte, ab 2021 nur gerundeter Fließtext. Die Bilanzposition
  „Rückstellungen für drohende Verpflichtungen aus Bürgschaften"
  (1,3 Mio €) ist **etwas anderes** — der erwartete Ausfall, nicht das
  Volumen.
- **Substanzverlust am Straßennetz** — das Wort ist das der Stadt. Straßen,
  Wege, Plätze: 210,9 (2016) → 133,3 Mio € (2024) Buchwert, rund −9,6 Mio €
  pro Jahr. Die Aufschlüsselung fehlt für 2019/2020; die Gesamtsumme steht in
  allen acht Jahrgängen in der Bilanz.
- **Kennzahlenübersicht der Stadt** (Rechenschaftsbericht) — 13 Kennzahlen
  **mit der Rechenvorschrift der Stadt daneben**, damit ist die Regel „keine
  selbst behaupteten Ziele" zwangsläufig erfüllt. 2018–2024 lückenlos.
- **Konzernbilanz + Kapitalflussrechnung** — 11 Jahrgänge 2014–2024. Wir
  parsen aus diesen Dokumenten heute nur die Gesamtergebnisrechnung.
- **Hebesätze seit 1980** (Jahrbuch 1105), nur die neun Änderungsjahre.
  Falle: „+21 % Grundsteuer B 2025" allein wäre irreführend — das Aufkommen
  **sank** im selben Jahr um 4,6 %, weil die Reform die Messbeträge umstellte.
- **Spenden an die Stadt** — 215 Beschlusszeilen, 213 mit Betrag, lückenlos
  monatlich seit 2018. 2025: 788.669 €. Die Spendernamen stehen nur in der
  Anlage.
- **Zensus 2022:** Oldenburg **172.759** — und damit einer der wenigen
  Gewinner (+0,84 %), während Niedersachsen 2,11 % verlor. Wirkung auf
  Pro-Kopf-Werte: −0,83 %.
- **Finanzausgleich:** 452 €/Einwohner, **drittniedrigste** Zuweisung in
  Niedersachsen — weil Oldenburg die dritthöchste Umlagekraft hat. Erklärt in
  einem Satz, warum ein steuerstarker Nachbar weniger bekommt.

## Ein Fund, der nichts kostet

„Schulden je Einwohner" (zeigen wir bereits) enthält **zwei künstliche
Sprünge**, weil der Nenner revidiert wurde:

- 2011→2012: Einwohnerzahl −4.371 (Zensus 2011), Pro-Kopf springt 996 → 1.121 €
- 2022→2023: Einwohnerzahl +4.079 (Zensus 2022), Pro-Kopf **sinkt** 1.652 →
  1.616 € — obwohl die Schulden von 281,5 auf 281,9 Mio € **stiegen**

2023 sieht nach Entspannung aus, ohne dass sich etwas entspannt hat. Kostet
eine Fußnote.

## Zwei Hebel vor jedem Parser

1. **`MAX_TEXT` = 400.000 Zeichen** (`scripts/backfill_anlagen_texte.py`)
   kappt alle acht Jahresabschlüsse. Abgeschnitten wird ausgerechnet
   Abschnitt 8 „Anlagen zum Anhang" — Anlagen-, Forderungs-, **Schulden-** und
   **Rückstellungsübersicht**.
2. **Fünf Rechenschaftsberichte (2017–2021)** liegen als Anlage vor, wurden
   aber nie geladen (`status='listed'`, leerer `raw_text`): Dokumente 192336,
   205649, 219465, 238770, 250437. Ein Backfill verlängert die
   Kennzahlenreihe bis etwa 2013.

## Geprüft und verworfen

**Quellen ohne Oldenburg-Bezug** — jeweils an der Quelle geprüft, nicht
vermutet:

- **Deutsche Bundesbank**: Der Dataflow `BBGFS1` hat **keine
  Regionaldimension**. Bund/Länder/Gemeinden als Ebenen, nicht als
  Einzelkörperschaften. Kein Weg zu Oldenburg.
- **Destatis Fachserie 14/5**: „Oldenburg" kommt auf 260 Seiten **null mal**
  vor; die Reihe endet mit Berichtsjahr 2021.
- **KfW-Kommunalpanel**: nur Größenklassen, „Niedersachsen" null Treffer.
  Anonymisierte Kämmerei-Befragung, Einzelkommunen methodisch ausgeschlossen.
- **KGSt-Vergleichsdatenbank**: selbst mit Mitgliedschaft anonymisiert.
- **Bertelsmann Kommunaler Finanzreport**: Oldenburg auf 122 Seiten kein
  einziges Mal.
- **haushaltssteuerung.de**: rechtlich gesperrt — Impressum verbietet
  Nachnutzung ohne Genehmigung.
- **offenerhaushalt.de**: eingestellt.

**Aus dem eigenen Bestand nicht zu holen:**

- **Haushaltsanträge der Fraktionen mit Beträgen** — die beste Frage
  überhaupt („wer wollte was streichen, um wie viel"). Die Anträge existieren
  als 171 `subvote`-Zeilen mit Urheber und Ergebnis, die **Beträge** stehen
  nur in Anlagen-PDFs, die **nie geladen** wurden (`status='listed'`,
  `LENGTH(raw_text)=0`). Kandidaten: 196997/196998 (HH 2019), 210921–210923
  (HH 2020), 227863–227869 (HH 2021). Trägt ein Ladetest, ist das der größte
  ungehobene Fund.
- **Vergaben**: 40 Beschlusszeilen, fast alle Fehltreffer („Vergabe von
  Kindergartenplätzen"). Echte Auftragsvergaben laufen nicht über öffentliche
  Ratsbeschlüsse.
- **Grundstückspreise**: 131 Zeilen, nur 17 mit Betrag — der Preis steht im
  nichtöffentlichen Teil.
- **Beträge aus Wortbeiträgen**: LLM-referierte Zusammenfassungen, keine
  Wortlaute. Zur Illustration: ein Beitrag zur Stadionfinanzierung extrahiert
  als 453.000.000 €.
- **Rückstellung „unterlassene Instandhaltung"** (0,5 Mio €) klingt nach
  Sanierungsstau, erfasst aber nur rechtlich nachzuholende Instandhaltung.
  Als Sanierungsstau gezeigt wäre sie um Größenordnungen irreführend.

## Zwei Stabilitätswarnungen

1. **Es gibt kein Jahrbuch-Archiv.** Nur die jeweils neueste Ausgabe liegt
   online, das Internet Archive hat vom Statistik-Verzeichnis **null**
   Schnappschüsse. Tabellen mit nur drei Jahrgängen (1103, 0803) verlieren
   jedes Jahr ihr ältestes unwiederbringlich.

   **Erledigt seit 17.08.2026:** `scripts/archive_statistik.py` sichert die
   Quellen täglich versioniert unter `data/archiv/` (447 Dateien, 77 MB im
   Erstlauf) — siehe [Betrieb](/docs/betrieb/#statistik-archiv-archive_statistikpy).
   Ab jetzt wächst die Reihe, statt zu schrumpfen.
2. **Zwei Datenfehler in amtlichen Quellen gefunden:** im 1102-CSV steht für
   2021 der Ansatz statt des Ergebnisses (s. o.), und in der LSN-Datei
   „Kommunale Finanzen 2024" steht ein Braunschweiger Wert in Oldenburgs
   Zeile. Externe Quellen brauchen Plausibilisierung wie unsere eigenen.

## Lizenzlage

Unproblematisch: 89 von 91 Open-Data-Sätzen DL-DE/BY-2.0 (Wohngeld sogar
DL-DE/Zero), Statistikportal DL-DE/BY-2.0, Wegweiser Kommune CC0, LSN mit
ausdrücklicher Weiterverbreitungserlaubnis. Die Namensnennung nach
dl-de/by-2-0 verlangt drei Teile: Bereitsteller, Lizenzvermerk mit Link,
Datensatz-URI.

Nicht geklärt und deshalb nur verlinken statt spiegeln: Prüfungsmitteilungen
der Landesbehörde und der LRH-Kommunalbericht.
