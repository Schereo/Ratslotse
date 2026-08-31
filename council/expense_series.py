"""Was die Stadt in einem Jahr ausgegeben hat — Datensatz 1102, seit 1972.

Die längste Reihe des Haushalts-Bereichs: **54 Jahrgänge**, von 1972 bis zum
gerade abgelaufenen Jahr. Sie beantwortet die einfachste Frage, die man an
einen Haushalt stellen kann — „wie viel gibt die Stadt aus?" —, und sie
beantwortet sie über eine Zeitspanne, in der Oldenburg von 133.000 auf 176.000
Einwohner*innen gewachsen ist, zweimal die Währung gewechselt hat (D-Mark →
Euro, hier durchgängig in Euro umgerechnet von der Stadt selbst) und einmal
das ganze Rechnungswesen umgestellt hat.

Der Datensatz steht an **zwei** Stellen, und das ist der Grund, warum diese
Schicht überhaupt eine Probe hat:

* **Statistisches Jahrbuch, Tabelle 1102** (PDF, :data:`TABELLE_URL`) — führt
  2002 bis heute, mit Fußnoten, Titeln und Untertiteln.
* **Open-Data-Portal, Datensatz 1102** (zwei CSV-Dateien,
  :data:`CSV_URLS`) — führt 1972 bis heute, aber nackt: keine Untertitel,
  keine Fußnoten.

Warum die Aufwendungs-Spalte bis 08/2026 liegen blieb
------------------------------------------------------
Die neuere der beiden CSV-Dateien laden wir seit Monaten — für die
Einwohnerspalte (``council/haushalt.parse_einwohner``). Die Aufwendungs-Spalte
daneben blieb bewusst liegen, mit dieser Begründung:

    „Sie weicht vom beschlossenen Plan ab (2024: 764,7 statt 728,2 Mio.), ist
    aber nirgends als Ist oder Nachtrag gekennzeichnet — als ‚Ist' ausgewiesen
    wäre sie eine Behauptung."

Die Entscheidung war richtig und ist es nicht mehr, weil die Beschriftung
inzwischen gefunden ist — sie steht nicht im CSV, sondern im **PDF derselben
Tabelle**, als Untertitel über den beiden Blöcken:

* 1972–2009: „Ausgaben des Verwaltungshaushalts — **Anordnungssoll** —"
* 2010–2025: „Ordentliche Aufwendungen des Ergebnishaushalts —
  **Gesamtergebnisrechnung** —"

„Gesamtergebnisrechnung" ist keine Floskel, sondern der Name eines Abschnitts
im Jahresabschluss. Damit ist die Spalte das Ist, und zwar ein benanntes.

Was der gemessene Versatz von 0,03–0,05 % ist
----------------------------------------------
Gegen ``council_ergebnisrechnung`` (Posten 20, „Summe ordentliche
Aufwendungen") liegt die Statistik in jedem Jahrgang **etwas höher**, und zwar
erstaunlich gleichmäßig: 2017 +166.253 €, 2018 +236.269 €, 2019 +260.407 €,
2020 +186.548 €, 2021 +214.651 €, 2022 +267.171 €, 2023 +286.730 €, 2024
+328.936 €. Das sind 0,032 bis 0,046 Prozent — zu klein für einen Fehler, zu
groß für Rundung.

Der Jahresabschluss löst es selbst auf. Er führt die Tabelle **zweimal**:

* **3.1 Ergebnisrechnung der Kernverwaltung** — das ist, was wir parsen.
* **3.2 Gesamtergebnisrechnung** — im Rechenschaftsbericht ausgeschrieben als
  „Gesamtergebnisrechnung (Kernhaushalt und nicht rechtsfähige Stiftungen)".

Und er rechnet den Unterschied vor: „ordentliche Aufwendungen gemäß
Haushaltsplan Seite 260 728.170.348,30 **abzüglich Aufwendungen der nicht
rechtsfähigen Stiftungen** -286.683,03 → Summe ordentliche Aufwendungen
Kernhaushalt: 727.883.665,27". Für die Stiftungen (Collins, Eilers,
Francksen, Klaue, Edith Ruß, Wellmann, Winter …) legt die Stadt eigene
Jahresabschlüsse vor; aus der Rechnung der Kernverwaltung sind sie deshalb
herauszurechnen.

Damit ist der Versatz kein offener Punkt, sondern eine Abgrenzung mit Namen:
**Die Statistik zählt die Stiftungen mit, unsere Ergebnisrechnung nicht.**
Gegengeprobt an den Zahlen des Jahresabschlusses 2024 selbst: Gesamt
764.745.383,29 € → auf Tausend gerundet 764.745 T€, und genau das steht in
Tabelle 1102. Auf den Tausender genau, in jedem geprüften Jahrgang.

Die Naht 2009/2010
-------------------
Zum 1. Januar 2010 stellte die Stadt von kameraler auf doppische Buchführung
um; die Fußnote der Tabelle sagt es selbst („Einführung Neues Kommunales
Rechnungswesen (NKR) zum 01. Januar 2010"). Links davon steht das
**Anordnungssoll des Verwaltungshaushalts**, rechts die **ordentlichen
Aufwendungen der Gesamtergebnisrechnung** — zwei Begriffe aus zwei
Rechnungswesen, die nur zufällig beide „was die Stadt ausgibt" heißen.

Deshalb trägt jeder Jahrgang sein :data:`REGELWERK` mit, deshalb hat jedes
Regelwerk seine eigene :data:`ABGRENZUNG`, und deshalb zieht kein Lesepfad
eine Linie über 2009/2010. Dieselbe Regel wie bei den Ist-Investitionen
(``council/investitionen_ist.py``), aus derselben Fußnote.

Die drei Proben
----------------
1. :func:`prokopfprobe` — **die Rechnung, die in der Datei selbst steht.**
   Beide Quellen führen neben dem Betrag eine Einwohnerzahl und einen Betrag
   je Einwohner*in. Betrag ÷ Einwohnerzahl muss den ausgewiesenen Pro-Kopf-Wert
   ergeben. Gemessen: 38 von 38 Zeilen der alten CSV, 15 von 16 der neuen, 24
   von 24 im PDF.

   Sie erledigt nebenbei eine Frage, die sonst offen bliebe: Die **alte CSV
   beschriftet ihre Spalte falsch** („Ausgaben insgesamt in Euro"), tatsächlich
   sind es Tausend Euro wie überall sonst in diesem Datensatz. Die Probe geht
   nur in Tausend Euro auf — und zwar in allen 38 Zeilen. Sollte die Stadt
   eines Tages wirklich auf Euro umstellen, reißt sie in jeder Zeile um den
   Faktor 1000, und es kommt nichts herein statt des Tausendfachen.

2. :func:`zweitquellenprobe` — **PDF gegen CSV.** In den 24 Jahren, die beide
   Quellen führen, müssen sie übereinstimmen. Sie tun es 23-mal.

3. :func:`gegenprobe` — **gegen unseren eigenen Bestand.** Für die Jahre mit
   Jahresabschluss muss der Betrag zur Ergebnisrechnung desselben Jahres
   passen, mit der oben erklärten Toleranz.

Der eine Fall, in dem sich zwei amtliche Quellen widersprechen
---------------------------------------------------------------
**2021.** Das CSV nennt 613.572 T€, das PDF 608.910 T€ — 4,662 Mio. €
Unterschied. Es ist der einzige Widerspruch in 24 gemeinsamen Jahren, und er
ist auflösbar, weil beide Quellen ihre Pro-Kopf-Spalte mitbringen:

* PDF: 608.910.000 € ÷ 169.605 = 3.590,17 €, ausgewiesen 3.590 € — geht auf.
* CSV: 613.572.000 € ÷ 169.605 = 3.617,65 €, ausgewiesen 3.611 € — geht nicht
  auf. Die CSV-Zeile widerspricht also **sich selbst**.

Der Jahresabschluss 2021 entscheidet die Frage endgültig — und zeigt, was
passiert ist: Er weist als Ergebnis 608.910.073,82 € aus und in der Spalte
**daneben**, als Ansatz, 613.571.622,10 €. Der CSV-Wert ist auf den Tausender
genau der **Plan** des Jahres. In dieser einen Zeile ist die Spalte verrutscht.

Wir korrigieren das nicht still: Der PDF-Wert kommt herein, der CSV-Wert steht
als ``conflict_amount`` daneben im Bestand, und die Seite schreibt beides an.
Eine stille Korrektur wäre hier besonders verlockend und besonders falsch —
sie sähe aus wie eine saubere Reihe und wäre eine Behauptung über eine amtliche
Quelle.

Was 2025 kann, was kein Jahresabschluss kann
----------------------------------------------
Der jüngste Jahresabschluss im Ratsinformationssystem ist der von 2024; der
von 2025 wird frühestens Mitte 2026 beschlossen. Tabelle 1102 führt **2025
schon** (850.170 T€). Die Gesamtsumme des abgelaufenen Jahres steht hier also
Monate vor dem Abschluss — die einzige Stelle im Bereich, an der das so ist.
Sie trägt dort die Pro-Kopf- und die Zweitquellenprobe, aber noch nicht die
Gegenprobe gegen den Abschluss; ``probes`` je Zeile sagt das.
"""
from __future__ import annotations

import re

#: Die Übersichtsseite, auf der die Stadt ihre Jahrbuch-Tabellen verlinkt. Wie
#: bei 1107/1108 trägt die Datei den Jahrgang im Namen, der Link wandert also
#: jedes Jahr — ``scripts/ingest_ausgabenreihe.py`` sucht ihn dort, statt eine
#: Adresse hochzuzählen.
JAHRBUCH_URL = ("https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/"
                "stadtverwaltung/statistik/statistisches-jahrbuch.html")
#: Stand vom 17.08.2026 und die Rückfallebene, wenn die Übersicht sich ändert.
TABELLE_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
               "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1102-2025-AZ.pdf")

#: Wie die Übersichtsseite den Link auf diese Tabelle schreibt.
LINK_MUSTER = re.compile(r'href="([^"]*/1102[^"]*\.pdf)"', re.IGNORECASE)

#: Die beiden CSV-Dateien desselben Datensatzes im Open-Data-Portal
#: (dl-de/by-2-0), je Regelwerk eine. Die zweite laden wir ohnehin schon:
#: ``council.haushalt.EINWOHNER_CSV_URL`` zeigt auf dieselbe Datei und liest
#: ihre Einwohnerspalte.
CSV_URLS: dict[str, str] = {
    "kameral": ("https://opendata.oldenburg.de/sites/default/files/"
                "1102%20Ausgaben%20des%20Verwaltungshaushaltes%201972-2009.csv"),
    "doppik": ("https://opendata.oldenburg.de/sites/default/files/"
               "1102-Ordentliche_Aufwendungen_des_Ergebnishaushaltes_seit_2010.csv"),
}

#: Das erste Jahr des neuen Rechnungswesens — die Naht. Steht als Fußnote 1
#: unter der Tabelle: „Einführung Neues Kommunales Rechnungswesen (NKR) zum
#: 01. Januar 2010."
NAHT_AB = 2010

#: Die beiden Rechnungswesen. Schlüssel → wie es auf der Seite heißt.
#: Wortgleich zu ``council/investitionen_ist.REGELWERK``: Es ist dieselbe
#: Umstellung, aus derselben Fußnote derselben Quelle.
REGELWERK: dict[str, str] = {
    "kameral": "Kamerales Rechnungswesen (bis 2009)",
    "doppik": "Doppisches Rechnungswesen (ab 2010)",
}

#: Wie die Quelle ihre beiden Blöcke ÜBERSCHREIBT — der Name der Größe.
TITEL: dict[str, str] = {
    "kameral": "Ausgaben des Verwaltungshaushalts",
    "doppik": "Ordentliche Aufwendungen des Ergebnishaushalts",
}

#: Was jeweils gezählt wird — der Satz, der neben der Zahl stehen kann. Beide
#: stammen aus dem Untertitel der Tabelle; der Zusatz erklärt ihn.
#:
#: Ohne diese Sätze wäre die Reihe eine Kurve über zwei verschiedene Größen.
#: „Anordnungssoll" ist der kamerale Begriff für das, was angeordnet wurde
#: (nicht für das, was tatsächlich floss — das hieße Kassen-Ist);
#: „Gesamtergebnisrechnung" ist der Abschnitt des Jahresabschlusses, der
#: Kernhaushalt und Stiftungen zusammen ausweist.
ABGRENZUNG: dict[str, str] = {
    "kameral": ("Gezählt wird das Anordnungssoll des Verwaltungshaushalts — "
                "was im Haushaltsjahr zur Zahlung angeordnet wurde. "
                "Investitionen liefen kameral im Vermögenshaushalt und stehen "
                "nicht darin."),
    "doppik": ("Gezählt werden die ordentlichen Aufwendungen der "
               "Gesamtergebnisrechnung — was das Jahr verbraucht hat, "
               "Kernhaushalt und nicht rechtsfähige Stiftungen zusammen. "
               "Investitionen zählen extra; von einem Neubau steht hier nur "
               "die Abschreibung des Jahres."),
}

#: Die Quelle rechnet in Tausend Euro, gespeichert wird wie überall im Bereich
#: in Euro. Die alte CSV BEHAUPTET Euro („Ausgaben insgesamt in Euro") und
#: meint Tausend Euro — bewiesen von der Pro-Kopf-Probe (s. Modulkopf).
TAUSEND = 1000

#: Toleranz der Pro-Kopf-Probe in Euro. Die Quelle rundet ihren Pro-Kopf-Betrag
#: auf volle Euro; schon deshalb ist der letzte Euro nicht zu halten. Dieselbe
#: Toleranz wie in ``council/schulden.prokopfprobe``.
PROKOPF_TOLERANZ = 1.0

#: Toleranz der Gegenprobe gegen ``council_ergebnisrechnung``, als Anteil.
#: Gemessen sind 0,032–0,046 % — die Aufwendungen der nicht rechtsfähigen
#: Stiftungen, die die Statistik mitzählt und die Ergebnisrechnung der
#: Kernverwaltung nicht (s. Modulkopf). 0,1 % lässt Raum, ohne einen
#: Spaltenrutsch wie 2021 (0,80 %) durchzuwinken.
GEGENPROBE_TOLERANZ = 0.001

#: Wie weit die Statistik UNTER der Kernverwaltung liegen darf: eine halbe
#: Tausenderstelle, also die Rundung der Quelle. Alles darunter hieße, die
#: Stiftungen hätten negative Aufwendungen — dann stimmt die Annahme nicht,
#: und der Jahrgang soll fallen statt still durchzugehen.
GEGENPROBE_UNTERGRENZE = -TAUSEND / 2

#: Die drei Proben, in einem Halbsatz — für den Messwert der Herkunft
#: (``probe_result``), der auf der Seite im Beleg landet. Die vollständigen
#: Erklärsätze für Leser*innen stehen in ``council/herkunft.PROBEN``; hier
#: braucht es die Kurzform, weil der Messwert alle bestandenen Proben einer
#: Gruppe hintereinander nennt.
PROBEN_KURZ: dict[str, str] = {
    "ausgabenreihe_prokopf": "Pro-Kopf-Rechnung der Quelle",
    "ausgabenreihe_zweitquelle": "Jahrbuch gegen Open-Data-Portal",
    "ausgabenreihe_jahresabschluss": "Abgleich mit dem Jahresabschluss",
}

#: Eine Datenzeile beginnt mit der Jahreszahl.
_ZEILE = re.compile(r"^((?:19|20)\d\d)\s+(\S.*)$")

#: Ein Tabellenfeld des PDFs: deutsche Tausendergruppen, dahinter höchstens
#: eine Fußnotenziffer oder das ``r`` für „revidiert" (2023 trägt es am
#: Pro-Kopf-Wert). Die Dreiergruppen sind der Trick — ``\.\d{3}`` lässt eine
#: fünfte Ziffer gar nicht erst zur Zahl gehören, sodass aus ``3.9171`` nicht
#: 39.171 wird. Wortgleich gedacht zu ``council/schulden._ZELLE``.
_ZELLE = re.compile(r"^(\d{1,3}(?:\.\d{3})*)([1-9]|r)?$")

#: Die Titel der beiden Blöcke im PDF. Die Jahresspanne endet mit einer
#: optionalen Ziffer: Im Textextrakt klebt die Fußnotenmarke an der Jahreszahl
#: (``2010 bis 20251``). Fünfstellige Jahre gibt es nicht, die Ziffer ist also
#: eindeutig die Marke.
#:
#: Der zweite Titel trägt die Tabellennummer NICHT — im PDF steht „1102" nur
#: über dem ersten Block, der zweite beginnt gleich mit seiner Überschrift.
_TITEL: dict[str, re.Pattern] = {
    "kameral": re.compile(
        r"1102\s+Ausgaben des Verwaltungshaushalts\s+"
        r"((?:19|20)\d\d)\s+bis\s+((?:19|20)\d\d)\d?"),
    "doppik": re.compile(
        r"Ordentliche Aufwendungen des Ergebnishaushalts\s+"
        r"((?:19|20)\d\d)\s+bis\s+((?:19|20)\d\d)\d?"),
}

#: Woran der Volltext in seine beiden Blöcke zerfällt.
_SCHNITT = "Ordentliche Aufwendungen des Ergebnishaushalts"


def de_zahl(zahl: float, nachkomma: int = 0, vorzeichen: bool = False) -> str:
    """Eine Zahl in deutscher Schreibweise — für Gründe und Beleg-Messwerte.

    Wortgleich zu ``council/investitionen_ist.de_zahl`` und aus demselben
    Grund kein ``.replace`` auf dem fertigen Satz: Das verwandelte auch ein
    Dezimalkomma in einen Punkt."""
    text = f"{zahl:{'+' if vorzeichen else ''},.{nachkomma}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def regelwerk_von(year: int) -> str:
    """Unter welchem Rechnungswesen ein Jahrgang gezählt wurde.

    Aus der Jahreszahl und nicht aus der Datei, in der die Zeile stand: Der
    Schnitt ist ein Datum (1. Januar 2010) und keine Dateieigenschaft. Dass
    beide Quellen ihn genauso ziehen, prüft :func:`lies` — eine Zeile, die im
    falschen Block steht, kommt nicht herein."""
    return "doppik" if year >= NAHT_AB else "kameral"


def _zelle(field: str) -> tuple[float | None, str]:
    """Ein PDF-Tabellenfeld → (Zahl, Marke). ``(None, "")``, wenn es keine ist.

    Ohne Tausenderpunkt gilt das Feld ungeteilt: ``891`` sind 891 und nicht 89
    mit Fußnote 1."""
    field = field.strip()
    if "." not in field:
        return (float(field), "") if field.isdigit() else (None, "")
    m = _ZELLE.match(field)
    if not m:
        return (None, "")
    return float(m.group(1).replace(".", "")), m.group(2) or ""


def erkenne(text: str) -> dict[str, tuple[int, int]]:
    """Welche Blöcke stecken im PDF-Text — und welche Spanne kündigt jeder an?

    Rückgabe ``{accounting_system: (von, bis)}``, leer wenn keiner gefunden wurde. Die
    Spannen kommen aus den Titeln und nicht aus den gelesenen Zeilen: Damit
    sind sie Angaben des Dokuments, gegen die sich prüfen lässt, ob alle
    angekündigten Jahrgänge auch angekommen sind (:func:`lies` tut das).

    **Die Spanne des PDFs ist nicht die der Reihe.** Das PDF beginnt 2002, die
    CSV 1972 — die dreißig Jahre davor stehen nur dort."""
    flach = re.sub(r"\s+", " ", text or "")
    gefunden: dict[str, tuple[int, int]] = {}
    for accounting_system, muster in _TITEL.items():
        m = muster.search(flach)
        if m:
            gefunden[accounting_system] = (int(m.group(1)), int(m.group(2)))
    return gefunden


def parse_pdf(text: str) -> list[dict]:
    """Die Datenzeilen des PDFs → ``{year, population, amount, per_capita,
    revised, quelle}``, Beträge in Euro.

    Beide Blöcke stehen auf derselben Seite untereinander; getrennt wird am
    Titel des zweiten. Der Schnitt ist hier weniger kritisch als bei 1107,
    weil beide Blöcke dieselbe Spaltenzahl haben — er entscheidet aber, welche
    Zeile zu welchem Titel gehört, und das prüft :func:`lies` gegen
    :func:`regelwerk_von`."""
    zeilen: list[dict] = []
    for roh in (text or "").splitlines():
        m = _ZEILE.match(roh.strip())
        if not m:
            continue
        felder = [_zelle(f) for f in m.group(2).split()]
        # Drei Wertspalten: Einwohner, Betrag (Tausend Euro), je Einwohner.
        if len(felder) != 3 or any(w is None for w, _ in felder):
            continue
        (ew, _), (amount, _), (kopf, mark) = felder
        zeilen.append({
            "year": int(m.group(1)), "population": int(ew or 0),
            "amount": (amount or 0.0) * TAUSEND, "per_capita": kopf,
            "revised": mark == "r", "quelle": "pdf",
        })
    return zeilen


def parse_csv(csv_text: str) -> list[dict]:
    """Eine der beiden CSV-Dateien → dieselbe Zeilenform wie :func:`parse_pdf`.

    Vier Spalten, Semikolon getrennt, ohne Tausenderzeichen: Haushaltsjahr,
    Einwohner am 31.12. des Vorjahres, Betrag, Betrag je Einwohner*in.

    **Der Spaltenkopf wird nicht gelesen.** Die ältere Datei beschriftet ihre
    Beträge „in Euro" und meint Tausend Euro (s. Modulkopf); ein Parser, der
    dem Kopf glaubt, läse dort das Tausendstel. Die Einheit steht deshalb als
    :data:`TAUSEND` fest, und die Pro-Kopf-Probe entscheidet, ob das stimmt."""
    zeilen: list[dict] = []
    for line in (csv_text or "").splitlines()[1:]:
        c = [x.strip() for x in line.split(";")]
        if len(c) < 4 or not c[0].isdigit():
            continue
        if not (c[1].isdigit() and c[2].isdigit() and c[3].isdigit()):
            continue
        zeilen.append({
            "year": int(c[0]), "population": int(c[1]),
            "amount": float(c[2]) * TAUSEND, "per_capita": float(c[3]),
            "revised": False, "quelle": "csv",
        })
    return zeilen


def prokopfprobe(zeile: dict) -> tuple[bool, float | None]:
    """Betrag ÷ Einwohnerzahl = der ausgewiesene Pro-Kopf-Betrag?

    Die Rechnung steht in der Datei selbst — beide Quellen führen alle drei
    Zahlen nebeneinander. Rückgabe ``(bestanden, gerechneter Wert)``.

    Diese Probe ist die einzige, die **jede** Zeile der Reihe trägt: Das PDF
    beginnt erst 2002, der Jahresabschluss erst 2017, die dreißig Jahre davor
    hängen allein an ihr. Sie ist zugleich die einzige, die eine falsche
    Einheit aufdecken kann."""
    ew, kopf = zeile.get("population"), zeile.get("per_capita")
    if not ew or kopf is None or zeile.get("amount") is None:
        return False, None
    gerechnet = zeile["amount"] / ew
    return abs(gerechnet - kopf) <= PROKOPF_TOLERANZ, gerechnet


def zweitquellenprobe(a: dict, b: dict) -> tuple[bool, float]:
    """Sagen PDF und CSV für dieses Jahr denselben Betrag?

    Rückgabe ``(bestanden, Differenz in Euro)``. Ohne Toleranz: Beide Quellen
    runden auf volle Tausend, und in 23 von 24 gemeinsamen Jahren stimmen sie
    auf den Euro überein. Eine Toleranz würde nur den einen Jahrgang
    durchwinken, für den sie gedacht wäre — und der liegt mit 4,66 Mio. €
    ohnehin weit jenseits jeder Rundung."""
    difference = (a.get("amount") or 0.0) - (b.get("amount") or 0.0)
    return difference == 0.0, difference


def gegenprobe(amount: float, kernverwaltung: float | None) -> tuple[bool | None, float | None]:
    """Passt der Betrag zur Ergebnisrechnung desselben Jahres?

    ``kernverwaltung`` ist Posten 20 („Summe ordentliche Aufwendungen") der
    Gesamtrechnung aus ``council_ergebnisrechnung`` — also die **Kernverwaltung
    ohne** die nicht rechtsfähigen Stiftungen. Die Statistik zählt sie mit;
    deshalb liegt sie systematisch etwas höher, und deshalb hat diese Probe
    eine Toleranz statt eines Gleichheitszeichens (Begründung im Modulkopf).

    Rückgabe ``(bestanden, Abweichung als Anteil)`` — ``(None, None)``, wenn
    für den Jahrgang kein Jahresabschluss vorliegt. Das ist vor 2017 der
    Normalfall und für 2025 der eigentliche Reiz der Reihe, kein Mangel."""
    if not kernverwaltung:
        return None, None
    anteil = (amount - kernverwaltung) / kernverwaltung
    return GEGENPROBE_UNTERGRENZE / kernverwaltung <= anteil <= GEGENPROBE_TOLERANZ, anteil


def _wähle(kandidaten: list[dict]) -> tuple[dict | None, dict | None, str]:
    """Aus den Kandidaten eines Jahres den einen Wert machen.

    Rückgabe ``(gewählt, verworfener Kandidat, Grund)``. Die Pro-Kopf-Probe
    entscheidet — sie ist die einzige, die beide Quellen unabhängig
    voneinander mitbringen. Wo beide sie bestehen und trotzdem
    auseinanderliegen, wird **nichts** gewählt: Dann widersprechen sich zwei
    in sich stimmige amtliche Angaben, und wir haben nichts, womit wir das
    entscheiden könnten."""
    bestanden = [k for k in kandidaten if prokopfprobe(k)[0]]
    if not bestanden:
        return None, None, "keine Quelle besteht die Pro-Kopf-Probe"
    if len({k["amount"] for k in kandidaten}) == 1:
        # Einig. Das PDF gewinnt als Fundstelle, weil es die Untertitel und
        # Fußnoten trägt — der Betrag ist ohnehin derselbe. Gewählt wird nur
        # aus den Zeilen, die ihre eigene Rechnung bestanden haben.
        pdf = next((k for k in bestanden if k["quelle"] == "pdf"), None)
        return pdf or bestanden[0], None, ""
    if len(bestanden) == 1:
        gewaehlt = bestanden[0]
        anderer = next(k for k in kandidaten if k is not gewaehlt)
        return gewaehlt, anderer, ""
    return None, None, ("beide Quellen bestehen ihre Pro-Kopf-Probe und nennen "
                        "trotzdem verschiedene Beträge")


def lies(csv_kameral: str, csv_doppik: str, pdf_text: str | None = None,
         income_statement: dict[int, float] | None = None) -> dict:
    """Die ganze Reihe einlesen und jeden Jahrgang durch seine Proben schicken.

    ``income_statement`` ist ``{year: Posten 20 der Gesamtrechnung in Euro}``
    aus ``council_ergebnisrechnung`` — ohne diese Abbildung läuft alles
    andere, nur ohne die dritte Probe.

    Rückgabe:

    ``zeilen``
        Die übernommenen Jahrgänge, aufsteigend. Jeder trägt ``accounting_system``,
        ``quelle`` (welche Datei den Betrag geliefert hat), die Namen seiner
        bestandenen ``probes`` und — wo die Quellen sich widersprachen —
        ``conflict_amount``/``conflict_source``.
    ``verworfen``
        Jahrgänge, die keine tragfähige Probe bestanden haben, mit ``grund``.
        Sie stehen nirgends in der Datenbank.
    ``konflikte``
        Die aufgelösten Widersprüche zwischen PDF und CSV, mit gemessener
        Differenz — die Auskunft, die die Seite anschreibt.
    ``spannen``
        Was die PDF-Titel ankündigen (leer ohne PDF).
    ``fehlende_jahrgaenge``
        Was aus den angekündigten Spannen fehlt, je Regelwerk — und dazu die
        Löcher in der CSV-Reihe selbst.
    ``probes``
        Was gerechnet wurde, in Zahlen — Grundlage des Beleg-Messwerts.
    """
    income_statement = income_statement or {}
    spannen = erkenne(pdf_text or "")

    # Je Jahr sammeln, was die Quellen sagen. Eine Zeile, die im falschen
    # Block steht (kamerale Datei mit einem Jahr ab 2010), fliegt hier raus:
    # Dann hat die Stadt ihren Schnitt verschoben, und das ist eine Nachricht
    # und keine Zeile, die man einfach umsortiert.
    #
    # Je Jahr höchstens EINE Zeile aus jeder Quelle: Steht ein Jahrgang zweimal
    # in derselben Datei, ist die Datei kaputt, und der Jahrgang fällt — sonst
    # entschiede die Lesereihenfolge, welche der beiden Zahlen gilt.
    kandidaten: dict[int, dict[str, dict]] = {}
    verworfen: list[dict] = []
    for erwartet, roh in (("kameral", parse_csv(csv_kameral)),
                          ("doppik", parse_csv(csv_doppik)),
                          (None, parse_pdf(pdf_text or ""))):
        for z in roh:
            if erwartet and regelwerk_von(z["year"]) != erwartet:
                verworfen.append({
                    "year": z["year"],
                    "grund": f"steht in der Datei für das {erwartet}e "
                             f"Rechnungswesen, gehört nach dem "
                             f"Umstellungsdatum aber ins "
                             f"{regelwerk_von(z['year'])}e"})
                continue
            je_quelle = kandidaten.setdefault(z["year"], {})
            if z["quelle"] in je_quelle:
                verworfen.append({
                    "year": z["year"],
                    "grund": f"steht in derselben Quelle ({z['quelle']}) "
                             f"mehr als einmal"})
                je_quelle[z["quelle"]] = {"doppelt": True}
                continue
            je_quelle[z["quelle"]] = z

    zeilen: list[dict] = []
    konflikte: list[dict] = []
    zaehler = {"prokopf_bestanden": 0, "prokopf_gerissen": 0,
               "zweitquelle_bestanden": 0, "zweitquelle_gerissen": 0,
               "gegenprobe_bestanden": 0, "gegenprobe_gerissen": 0,
               "ohne_jahresabschluss": 0}

    for year in sorted(kandidaten):
        je_quelle = kandidaten[year]
        if any(k.get("doppelt") for k in je_quelle.values()):
            continue  # Grund steht schon in `verworfen`.
        kand = [je_quelle[q] for q in ("pdf", "csv") if q in je_quelle]
        for k in kand:
            zaehler["prokopf_bestanden" if prokopfprobe(k)[0]
                    else "prokopf_gerissen"] += 1
        gewaehlt, konflikt, grund = _wähle(kand)
        if gewaehlt is None:
            verworfen.append({"year": year, "grund": grund})
            continue

        probes = ["ausgabenreihe_prokopf"]
        if len(kand) == 2:
            ok, _ = zweitquellenprobe(kand[0], kand[1])
            zaehler["zweitquelle_bestanden" if ok else "zweitquelle_gerissen"] += 1
            if ok:
                probes.append("ausgabenreihe_zweitquelle")

        g_ok, anteil = gegenprobe(gewaehlt["amount"], income_statement.get(year))
        if g_ok is None:
            zaehler["ohne_jahresabschluss"] += 1
        else:
            zaehler["gegenprobe_bestanden" if g_ok else "gegenprobe_gerissen"] += 1
            if not g_ok:
                # Der Jahrgang hat einen Jahresabschluss, und der widerspricht.
                # Dann gilt der Abschluss: Er ist das geprüfte Dokument, die
                # Statistik die Nacherzählung.
                verworfen.append({
                    "year": year,
                    "grund": f"weicht um {de_zahl(anteil * 100, 3, True)} % von "
                             f"der Ergebnisrechnung des Jahresabschlusses ab "
                             f"(erlaubt sind "
                             f"{de_zahl(GEGENPROBE_TOLERANZ * 100, 1)} % für die "
                             f"nicht rechtsfähigen Stiftungen)"})
                continue
            probes.append("ausgabenreihe_jahresabschluss")

        zeile = {
            "year": year, "accounting_system": regelwerk_von(year),
            "amount": gewaehlt["amount"], "quelle": gewaehlt["quelle"],
            "revised": bool(gewaehlt.get("revised")),
            "conflict_amount": konflikt["amount"] if konflikt else None,
            "conflict_source": konflikt["quelle"] if konflikt else None,
            "probes": probes,
        }
        zeilen.append(zeile)
        if konflikt:
            konflikte.append({
                "year": year, "gewaehlt": gewaehlt["quelle"],
                "amount": gewaehlt["amount"],
                "verworfen": konflikt["quelle"],
                "conflict_amount": konflikt["amount"],
                "difference": konflikt["amount"] - gewaehlt["amount"],
            })

    da = {z["year"] for z in zeilen}
    luecken: dict[str, list[int]] = {}
    for accounting_system, (von, bis) in spannen.items():
        fehlt = [j for j in range(von, bis + 1) if j not in da]
        if fehlt:
            luecken[accounting_system] = fehlt
    # Und die Löcher in der Reihe selbst — die CSV kündigt keine Spanne an,
    # ihre Vollständigkeit misst sich deshalb an ihrem eigenen Anfang und Ende.
    if zeilen:
        innen = [j for j in range(zeilen[0]["year"], zeilen[-1]["year"] + 1)
                 if j not in da]
        for j in innen:
            luecken.setdefault(regelwerk_von(j), [])
            if j not in luecken[regelwerk_von(j)]:
                luecken[regelwerk_von(j)].append(j)
        for v in luecken.values():
            v.sort()

    verworfen.sort(key=lambda v: v["year"])
    return {
        "zeilen": zeilen,
        "verworfen": verworfen,
        "konflikte": konflikte,
        "spannen": spannen,
        "fehlende_jahrgaenge": luecken,
        "probes": zaehler,
    }


def probennachweis(result: dict) -> str:
    """Der Messwert für die Herkunft — „was ist wirklich gelaufen?".

    Steht später im Beleg auf der Seite; deshalb Zahlen und keine Adjektive."""
    p = result["probes"]
    teile = [f"Pro-Kopf-Probe {p['prokopf_bestanden']} von "
             f"{p['prokopf_bestanden'] + p['prokopf_gerissen']} gelesenen Zeilen"]
    zwei = p["zweitquelle_bestanden"] + p["zweitquelle_gerissen"]
    if zwei:
        teile.append(f"PDF gegen CSV {p['zweitquelle_bestanden']} von {zwei} "
                     f"gemeinsamen Jahren")
    gegen = p["gegenprobe_bestanden"] + p["gegenprobe_gerissen"]
    if gegen:
        teile.append(f"Gegenprobe gegen die Jahresabschlüsse "
                     f"{p['gegenprobe_bestanden']} von {gegen}")
    if p["ohne_jahresabschluss"]:
        teile.append(f"{p['ohne_jahresabschluss']} Jahrgänge ohne "
                     f"Jahresabschluss zum Gegenprüfen")
    return "; ".join(teile)
