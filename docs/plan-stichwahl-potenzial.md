# Plan: Das Wähler*innen-Potenzial für die Stichwahl — eine Seite nur mit Link

Stand 16.09.2026. Stichwahl am 27.09.2026, Jascha Rohr gegen Ulf Prange.
Elf Tage.

## 0. Was Tim gesagt hat (15./16.09.2026)

> Wir würden gerne, dass Rohr die Stichwahl gewinnt, und dafür das
> Wähler*innen-Potenzial in Oldenburg analysieren. Wo macht es am meisten
> Sinn, Wahlkampf zu machen, an Haustüren zu gehen? Macht es eher Sinn,
> dahin zu gehen, wo Jascha sowieso gewählt worden ist — oder ist das
> verschenkte Zeit? Wo wurden die anderen OB-Kandidaten gewählt, die jetzt
> nicht mehr im Rennen sind, und sind das Personen, die man überzeugen
> kann? These: SPD-Wählende sind schwer zu überzeugen; der Fokus liegt eher
> auf Boldt (Linke) und Küßner. Butzin hat seine Unterstützung für Rohr
> angekündigt. Und ein Vergleich zur Stichwahl 2021 (auch SPD gegen Grüne).
> Umfangreich, interaktiv, auf der Website — aber nur mit Link, den man
> erraten müsste, kein Knopf. Sei kreativ.

Der Auftrag hat zwei Hälften: eine **Analyse** (die steht in §1 und §2,
gerechnet mit `scripts/stichwahl_potenzial.py`) und eine **Seite** (§3).

## 1. Gemessen — die Ausgangslage

Alle Zahlen aus den eingefrorenen Bezirksdaten (`kommunalwahl/referenz-2026/`
und die 2021er Fixtures), je Wahlbezirk, 91 an der Urne, 42 per Brief.
Rechenkern: `python scripts/stichwahl_potenzial.py`.

### 1.1 Der erste Wahlgang 2026

| | Stimmen | Anteil |
|---|---:|---:|
| Prange (SPD) | 28.075 | 33,2 % |
| **Rohr (GRÜNE, parteilos, CDU unterstützt)** | **25.850** | **30,5 %** |
| Boldt (Linke) | 10.198 | 12,1 % |
| Butzin (Einzel, unterstützt Rohr) | 6.211 | 7,3 % |
| Fröhlich (FDP) | 4.945 | 5,8 % |
| Küßner (Einzel) | 4.025 | 4,8 % |
| Wilkens (BB-OL) | 3.843 | 4,5 % |
| Stille, Castur | 1.509 | 1,8 % |

**Prange liegt 2.225 Stimmen vorn.** 29.222 Stimmen gingen an Kandidaturen,
die nicht mehr antreten (ohne Stille/Castur, die die Bezirksdatei unter
„Sonstige" führt). Dazu **37.430 CDU-Zweitstimmen** der Ratswahl — die CDU
hat keine eigene OB-Kandidatur und unterstützt Rohr. Und **76.873
Nichtwählende** an der Urne (Wahlberechtigte minus Wählende; die Briefwahl
führt keine Wahlberechtigten).

### 1.2 Die Briefwahl ist Rohrs bessere Hälfte

| Rohr-Anteil der beiden | 2026 |
|---|---:|
| an der Urne | 46,3 % |
| per Brief | **51,1 %** |

Ein Drittel der Stimmen kam per Brief. 2021 dasselbe Bild: Fuhrhop lag in
der Stichwahl per Brief bei 50,1 %, an der Urne bei 44,2 %. **Wer Rohr
wählen will, soll es per Brief tun** — das ist die billigste Stimme des
Wahlkampfs, und sie geht nicht am Sonntag im Regen verloren.

### 1.3 Wo die Umworbenen wohnen — und wo nicht

Korrelation je Bezirk zwischen dem Anteil einer Kandidatur und dem
Rohr-Anteil (erster Wahlgang):

| Wählende von … | r | heißt |
|---|---:|---|
| Boldt (Linke) | +0,11 | **überall**, ohne Muster |
| Küßner | −0,43 | eher dort, wo Rohr schwach ist |
| Butzin | **−0,71** | fast nur dort, wo Rohr schwach ist |
| CDU (Ratswahl) | −0,21 | eher außen |
| Grüne (Ratswahl) | +0,76 | das ist Rohrs Basis |
| AfD (Ratswahl) | −0,71 | der Gegenpol |

Das beantwortet Tims Kernfrage anders, als sie gestellt war: **Hochburg oder
Diaspora ist kein Entweder-oder, weil dort zwei verschiedene Dinge zu tun
sind.** In den Hochburgen (Nadorst Süd, Innenstadt, Wechloy, Bürgerfelde,
Donnerschwee — Rohr 53 bis 58 % der beiden) wohnt seine Basis, die am
Wahltag kommen muss. In der Diaspora (Bümmerstede, Kreyenbrück,
Alexanderfeld, Krusenbusch, Tweelbäke — Rohr 35 bis 43 %) wohnen Butzin,
Küßner und die CDU, also die, die man überzeugen kann. Die Linke wohnt
überall.

### 1.4 Ertrag je Tür

Mit den Vorgabe-Annahmen (§2.1) je 1.000 Wahlberechtigte, Urnenbezirke;
„Rohr" ist sein Anteil an den Stimmen der beiden:

| Bezirk | Ort | WB | netto je 1.000 | Rohr |
|---|---|---|---:|---:|
| 307 BBS Haarentor | Wechloy | III | 45,8 | 58 % |
| 203 Kulturzentrum PFL | Innenstadt | II | 45,2 | 53 % |
| 308 FF Haarentor | Wechloy | III | 44,3 | 55 % |
| 109 Friseurmeisterschule | Nadorst Süd | I | 44,0 | 65 % |
| 208 Oberschule Osternburg | Osternburg | II | 43,4 | 48 % |
| 106 Neues Gymnasium | Nadorst Süd | I | 42,4 | 54 % |
| … | | | | |
| 501 Caritas Begegnungsstätte | Bümmerstede | V | 16,5 | 33 % |
| 411 GS Nadorst | Ohmstede | IV | 16,4 | 51 % |

Der Ertrag streut um den Faktor drei. Gebündelt nach Stadtbezirken liegen
**Eversten (+558), Nadorst Süd (+385), Innenstadt (+368), Osternburg (+240)**
vorn — Eversten, weil es groß ist (13 Bezirke, 11.000 Nichtwählende), die
anderen, weil dort Linke- und Rohr-Wählende dicht beieinander wohnen.

### 1.5 Was 2021 lehrt — und was nicht

Krogmann (SPD) gegen Fuhrhop (Grüne), 58 : 42 im ersten, 54 : 46 im zweiten
Wahlgang. **Die Stichwahl am 26.09.2021 fiel auf den Tag der
Bundestagswahl:** 12 % MEHR Wählende als im ersten Wahlgang, Fuhrhop wuchs um
den Faktor 1,71, Krogmann um 1,47. Eine Stimmen-Wanderung lässt sich daraus
**nicht** schätzen — die ökologische Regression liefert Übertragungsquoten
über 1, das ist Rauschen aus der Beteiligung. 2026 gibt es keine
Bundestagswahl; die Beteiligung wird FALLEN, nicht steigen. Drei Lehren
bleiben trotzdem:

1. **Fuhrhop wuchs in ihren schwächsten Bezirken am stärksten** (× 2,2 im
   schwächsten Fünftel gegen × 1,55 in den Hochburgen). Wo eine
   Grünen-Kandidatur im ersten Wahlgang schwach war, ist der Zuwachs im
   zweiten prozentual am größten — dort wählte im ersten Wahlgang noch
   jemand anderes.
2. **Die Briefwahl war ihre bessere Hälfte** (50 % gegen 44 %). Siehe §1.2.
3. **Die Hochburgen hielten, aber sie trugen den Sieg nicht:** Ein
   Grünen-Kandidat gewinnt eine Stichwahl in Oldenburg nicht mit den
   Bezirken, die er schon hat. 2021 fehlten am Ende 6.544 Stimmen.

### 1.6 Was Rohr braucht

2.225 Stimmen netto. Mit den Vorgabe-Annahmen (Linke 55/15, Küßner 45/15,
Butzin 40/20, FDP 20/35, BB-OL 15/30, CDU netto 0) ergibt das Modell
**+5.211 netto → Rohr gewinnt mit rund 3.000**. Das ist keine Prognose, das
ist der Hebel: **Die Stichwahl entscheidet sich bei Linke, Butzin und
Küßner** — 20.434 Stimmen. Kommen davon netto 11 Prozentpunkte mehr zu Rohr
als zu Prange, ist der Rückstand aufgeholt. Alles, was die CDU-Empfehlung
darüber hinaus bringt, ist Vorsprung. Und: **Jede Stimme der eigenen Basis,
die zu Hause bleibt, muss doppelt ersetzt werden.**

## 2. Das Modell — ehrlich über seine Grenzen

### 2.1 Die Rechnung je Bezirk

Für jede ausgeschiedene Kandidatur zwei Regler: Anteil ihrer Stimmen zu
Rohr, Anteil zu Prange; der Rest bleibt zu Hause. Dazu die CDU-Zweitstimmen
der Ratswahl mit eigenem Reglerpaar. Netto je Bezirk = Σ Stimmen × (zu Rohr −
zu Prange). Ertrag je Tür = netto ÷ Wahlberechtigte. Die Vorgaben sind Tims
Einschätzung in Zahlen, nicht gemessen:

| | zu Rohr | zu Prange | warum |
|---|---:|---:|---|
| Boldt (Linke) | 55 | 15 | „inhaltlich am nächsten" |
| Küßner | 45 | 15 | dito, Einzelvorschlag |
| Butzin | 40 | 20 | hat Rohr unterstützt; wohnt außen |
| Fröhlich (FDP) | 20 | 35 | bürgerlich, CDU-Empfehlung zieht |
| Wilkens (BB-OL) | 15 | 30 | |
| CDU (Ratswahl) | 25 | 25 | die unsicherste Größe — netto 0 |

### 2.2 Was das Modell NICHT kann

- **Wer wen gewählt hat.** Eine Bezirksstatistik zeigt, WO Stimmen liegen,
  nicht, wie sie wandern. Die Regler sind Annahmen; die Seite sagt das.
- **Beteiligung.** Ohne Bundestagswahl fällt sie. Wer im ersten Wahlgang
  Boldt wählte und am 27.09. zu Hause bleibt, ist für beide verloren — das
  ist der „Rest" der Regler. Ein Beteiligungs-Regler je Lager (Basis Rohr,
  Basis Prange, Umworbene) macht das sichtbar.
- **Nichtwählende.** 76.873 an der Urne. Sie zu mobilisieren ist die größte
  und unwägbarste Reserve; das Modell zählt sie nur, es rechnet nicht mit
  ihnen.

## 3. Die Seite

**Adresse:** `/stichwahl/potenzial/<token>` — der Token steht in der `.env`
(`WAHLKAMPF_TOKEN`, lang und zufällig), die Seite liefert ohne ihn `notFound()`,
der Daten-Endpunkt `GET /api/wahlabend/stichwahl/potenzial?token=…` ohne ihn
404. Kein Link in der Navigation, `robots: noindex`, nicht in der Sitemap,
nicht in der Rauchprobe (die kennt den Token nicht). Das ist kein Schutz
gegen Angriff, sondern gegen Zufall — Tim: „den Link müsste erstmal jemand
erraten". Alle Daten darauf sind öffentliche Wahlergebnisse.

**Logik im Backend** (`web/backend/app/election/potential.py`, die Rechnung
aus `scripts/stichwahl_potenzial.py` als Modul): Der Endpunkt nimmt die
Regler als Query-Parameter und liefert je Bezirk Basis, Pool, Netto, Ertrag,
Strategie-Einstufung; dazu die Stadt-Summe, den Saldo gegen 2.225 und die
Stadtbezirks-Bündel. Die Seite rechnet nichts.

### Vier Ansichten, eine Frage

1. **„Was Rohr braucht"** — oben, immer sichtbar: ein Balken von −2.225 bis
   zum Saldo der aktuellen Regler. Darunter die Regler (je Kandidatur
   zwei Schieber, CDU, Beteiligung je Lager). Jede Änderung färbt Karte und
   Listen neu. Mit einer Zeile Ehrlichkeit: „Annahmen, keine Messung."
2. **Die Karte** — die 91 Urnenbezirke, Tönung wählbar: *Ertrag je Tür*,
   *Rohr-Anteil*, *Umworbene absolut*, *CDU-Anteil*, *Nichtwählende*.
   Antippen: Bezirkstafel mit allen neun Kandidaturen, CDU-Ratswahl,
   Nichtwählenden, Ertrag — und der **Strategie-Einstufung**:
   - **Halten** (Rohr ≥ 50 % der beiden): Basis mobilisieren, Briefwahl.
   - **Überzeugen** (Pool groß, Rohr < 45 %): Linke/Küßner/Butzin ansprechen.
   - **Beides** (Rohr stark UND Pool groß): Nadorst Süd, Innenstadt, Wechloy.
   - **Liegenlassen** (Ertrag unter 20 je 1.000): Bümmerstede, Ohmstede.
3. **Die Einsatzliste** — Stadtbezirke gebündelt (Eversten, Nadorst Süd, …),
   sortierbar nach Netto oder Ertrag, aufklappbar zu den Bezirken mit
   Wahllokal-Namen. Je Stadtbezirk: „X Türen, Y Stimmen netto, Z
   Nichtwählende". Mit **Haken „übernommen von …"** (lokal im Browser
   gespeichert, kein Konto), damit ein Team sich die Stadt aufteilen kann.
   Druckansicht.
4. **2021 gegen 2026** — die drei Lehren aus §1.5 als Bild: Fuhrhops
   Zuwachs nach Fünfteln, Briefwahl-Anteile beider Jahre, und die
   Bezirke, in denen sie am meisten dazugewann, auf der Karte.

Dazu ein **Briefwahl-Block** mit dem einen Argument aus §1.2 und dem Termin,
bis wann Briefwahl beantragt werden kann (steht auf oldenburg.de; im Plan
nachzutragen).

### Was NICHT gebaut wird

- Keine Prognose, wer gewinnt. Die Seite sagt „bei diesen Annahmen".
- Keine Personendaten, keine Adressen, keine Haushalte — nur Bezirke.
- Kein Login. Der Token ist die ganze Zugangsregel.

## 4. Die Pull Requests

| PR | Inhalt | Größe |
|---|---|---|
| **P1** | `potential.py` (Modell aus dem Skript), Vertrag, Endpunkt mit Token-Gate, Tests (Saldo 2.225, Linearität, Token) | mittel |
| **P2** | Seite: Regler, Balken, Karte (Gebietskarte mit `farbe`-Hook), Bezirkstafel, Einsatzliste, Druck | groß |
| **P3** | 2021-gegen-2026-Ansicht | klein |

P1 vor allem anderen — die Zahlen sind das, was das Team braucht; die Karte
ist Komfort. Alles vor dem **20.09.**, damit eine Woche Wahlkampf damit läuft.

## Anhang — Befehle

```bash
python scripts/stichwahl_potenzial.py                      # der Bericht mit Vorgaben
python scripts/stichwahl_potenzial.py --boldt 70 10 --cdu 40 20   # andere Annahmen
python scripts/stichwahl_potenzial.py --json /tmp/potenzial.json  # je Bezirk
```
