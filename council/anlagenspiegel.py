"""Was aus Investitionen wird — der Anlagenspiegel des Jahresabschlusses.

Der Haushalts-Bereich zeigt, was die Stadt bauen wollte und was sie gebaut
hat. Was daraus **wurde**, stand nirgends: Ein Neubau ist im Jahr seiner
Fertigstellung eine Investition und danach vierzig Jahre lang Vermögen, das
sich abnutzt. Der Anlagenspiegel (Abschnitt 8.1, „gem. § 57 Abs. 2 KomHKVO")
ist die Tabelle, die beides verbindet.

Er beantwortet die Frage, die eine Investitionsliste offenlässt: **Baut die
Stadt schneller auf, als ihr Bestand verfällt?** Für 2024 lautet die Antwort
beim größten Posten nein — die Stadt schreibt darauf mehr ab, als sie zubaut.
Das ist keine Wertung, sondern die Differenz zweier Spalten derselben Zeile.

WARUM ES DIESE SCHICHT ERST SEIT 08/2026 GIBT
----------------------------------------------
Der Abschnitt steht bei **97 % des Dokuments**. Die Volltext-Grenze lag bei
400.000 Zeichen, die Jahresabschlüsse sind 478.000–709.000 lang — der
Anlagenspiegel wurde also in *jedem* Jahrgang abgeschnitten, und zwar
unbemerkt, weil alles davor vollständig war. Erst das Anheben der Grenze
(``scripts/backfill_anlagen_texte.py``) hat ihn sichtbar gemacht.

DIE TABELLE HAT DREIZEHN WERTSPALTEN, UND SIE PRÜFEN SICH GEGENSEITIG
----------------------------------------------------------------------
Je Zeile stehen drei Blöcke nebeneinander:

* **Anschaffungs- und Herstellungswerte** — Stand Vorjahr, Zugänge, Abgänge,
  Umbuchungen, Stand Jahresende (Spalten 1–5),
* **Abschreibungen** — Stand Vorjahr, Abschreibung des Jahres, Auflösungen
  für Abgänge, Zuschreibungen, Umbuchungen, Stand Jahresende (6–11),
* **Buchwerte** — am Jahresende und am Vorjahresende (12–13).

Daraus folgen drei Rechenwege, die alle drei aufgehen müssen
(:func:`probe`) — und der letzte trifft auf eine *andere* Quelle:

1. ``AHK_vorher + Zugänge + Abgänge + Umbuchungen = AHK_nachher``
2. ``Abschr_vorher + Abschreibung + Auflösungen + Zuschreibungen + Umb. = Abschr_nachher``
3. ``AHK_nachher + Abschr_nachher = Buchwert`` — und dieser Buchwert steht
   **Cent-genau in der Bilanz** (:mod:`council.bilanz`). Für 2024 geprüft:
   Immaterielles Vermögen 91.394.171,68 € hier wie dort.

Die Vorzeichen kommen aus dem Dokument, nicht von uns: Abgänge und
Abschreibungen stehen dort negativ. Deshalb wird **addiert**, wo man
subtrahieren würde — wer hier ein Minus einbaut, dreht die Probe um und
findet den Fehler nie.

WAS DIESE SCHICHT NICHT KANN
-----------------------------
Sie führt das **Infrastrukturvermögen als eine Zeile** (2.3). Die Aufteilung
auf Straßen, Brücken und Gleisanlagen steht woanders im selben Dokument, in
den Erläuterungen zum Sachvermögen — dort auch der Satz, aus dem die Zahl
ihren Namen hat: „Dem **Substanzverlust** bei den Straßen, Wegen und Plätzen
um 9,6 Millionen Euro …". Diese Untertabelle liest
:func:`parse_sachvermoegen_gruppen`.
"""
from __future__ import annotations

import re

#: Der Abschnitt, in dem die Tabelle steht.
ABSCHNITT = "8.1 Anlagenübersicht"

#: Wo die Erläuterung zum Sachvermögen ihre Untergruppen auflistet.
ABSCHNITT_GRUPPEN = "Erläuterungen zum Sachvermögen"

PROBE_AHK = "anlagen_ahk_kette"
PROBE_ABSCHREIBUNG = "anlagen_abschreibungskette"
PROBE_BUCHWERT = "assets_book_value"
PROBE_BILANZ = "anlagen_gegen_bilanz"
PROBE_UMBUCHUNG = "anlagen_umbuchungssaldo"

PROBEN: dict[str, str] = {
    PROBE_AHK: ("Anfangsstand, Zugänge, Abgänge und Umbuchungen ergeben "
                "zusammen den ausgewiesenen Endstand."),
    PROBE_ABSCHREIBUNG: ("Die Abschreibungsspalten ergeben zusammen den "
                         "ausgewiesenen Stand am Jahresende."),
    PROBE_BUCHWERT: ("Anschaffungswert minus aufgelaufener Abschreibung ist "
                     "der ausgewiesene Buchwert."),
    PROBE_BILANZ: ("Der Buchwert stimmt mit der Bilanzposition desselben "
                   "Jahresabschlusses überein."),
    PROBE_UMBUCHUNG: ("Was bis 2020 zwischen den Vermögensarten verschoben "
                      "wurde, hebt sich über alle Positionen auf null auf."),
}

#: Toleranz der Ketten in Euro. Die Tabelle rechnet auf den Cent; ein Cent
#: Rundung je Summand ist das Äußerste, was aus der PDF-Extraktion kommen
#: kann. Wer hier großzügiger wird, findet echte Fehler nicht mehr.
TOLERANZ = 0.05

#: Die Brücke zur Bilanz — und sie trägt **genau eine** Zeile.
#:
#: Naheliegend wären drei: Immaterielles Vermögen, Sachvermögen,
#: Finanzvermögen stehen in beiden Tabellen. Die Fußnote der Anlagenübersicht
#: sagt aber, dass zwei davon etwas anderes zählen:
#:
#:     „In der Anlagenübersicht auszuweisen sind Immaterielle
#:     Vermögensgegenstände, das Sachvermögen **ohne Vorräte und
#:     geringwertige Vermögensgegenstände** sowie das Finanzvermögen **ohne
#:     Forderungen**."
#:
#: Ein Abgleich dieser beiden gegen die Bilanz meldet also verlässlich eine
#: Differenz, die keine ist — beim ersten Versuch waren es 85 Tsd. € beim
#: Sachvermögen und 184 Mio. € beim Finanzvermögen, und beide Zahlen sind
#: korrekt. Nur das Immaterielle Vermögen kennt keine Ausnahme; dort stimmt
#: es auf den Cent (2024: 91.394.171,68 € hier wie dort).
BILANZ_ROLLE: dict[str, str] = {
    "1": "immaterielles_vermoegen",
}

_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
#: Die Spaltennummern-Zeile über der Tabelle („1 2 3 … 14"). Sie sagt, wie
#: viele Spalten dieser Jahrgang führt — die erste ist die Bezeichnung, der
#: Rest sind Werte.
_SPALTENZEILE = re.compile(r"(?m)^\s*1(?:\s+\d{1,2})+\s*$")
#: Die Einheitenzeile des Kopfes — eine Marke je Wertspalte.
_EURO_MARKE = re.compile(r"-\s*Euro\s*-")
#: Eine Gliederungsnummer am Zeilenanfang („1.", „2.3"). Der Punkt hinter der
#: einstelligen Nummer ist Pflicht — sonst fängt das Muster die Fußnoten­
#: markierungen („2)") und die Spaltennummern-Zeile („1 2 3 … 14") mit ein.
_ZEILE = re.compile(r"(?m)^\s*(\d(?:\.\d)?)\.?\s+(?=[A-ZÄÖÜa-zäöü])")


def _eur(roh: str) -> float:
    return float(roh.replace(".", "").replace(",", "."))


def _abschnitt(text: str) -> str:
    """Nur die Anlagenübersicht — ohne Inhaltsverzeichnis und ohne 8.2 ff.

    „Anlagen zum Anhang" steht zweimal im Dokument: einmal im
    Inhaltsverzeichnis (bei ~1 %) und einmal als echte Überschrift (bei
    ~97 %). Genommen wird die **letzte** — im Verzeichnis folgt der
    Überschrift eine Seitenzahl, keine Tabelle.
    """
    marken = [m.start() for m in re.finditer(r"Anlagen\s+zum\s+Anhang", text)]
    if not marken:
        marken = [m.start() for m in re.finditer(r"8\.1\s+Anlagen[üu]bersicht", text)]
    if not marken:
        return ""
    rest = text[marken[-1]:]
    ende = re.search(r"8\.2\s+Forderungs", rest)
    return rest[:ende.start()] if ende else rest


def spaltenzahl(block: str) -> int | None:
    """Wie viele **Wertspalten** dieser Jahrgang führt — aus dem Dokument.

    Bis 2020 sind es zwölf, ab 2021 dreizehn: Der Abschreibungs-Block bekam
    eine Spalte „Umbuchungen" dazu. Wer eine feste Zahl annimmt, verliert die
    andere Hälfte der Jahrgänge — beim ersten Versuch fielen 2019 und 2020
    genau so heraus, und die einzige Zeile, die durchkam, riss dann die
    Probe, weil ihre zwölf Werte auf dreizehn Felder verteilt wurden.

    Gelesen wird die Spaltennummern-Zeile („1 2 3 … 14"). Ihre erste Zahl
    gehört zur Bezeichnungsspalte, der Rest sind Werte.
    """
    m = _SPALTENZEILE.search(block)
    if m:
        return len(m.group(0).split()) - 1
    # 2017 druckt keine Spaltennummern. Der Kopf nennt seine Spalten aber ein
    # zweites Mal — als Einheitenzeile („- Euro - - Euro - …"), und die hat
    # genau eine Marke je WERT-Spalte. Zwei unabhängige Signale für dieselbe
    # Angabe; das zweite rettet den ältesten Jahrgang.
    euro = len(_EURO_MARKE.findall(block[:2500]))
    return euro if euro in (12, 13) else None


def _label(roh: str) -> str:
    """Die Bezeichnung vor der ersten Zahl — Zeilenumbrüche geheilt.

    Die PDF-Extraktion bricht mitten im Wort um („Vermögensgegenst\nände",
    „Verkehrslen-\nkungsanlagen"). Ohne Heilung stünde auf der Seite
    „Immaterielles Vermögensgegenst änd" — ein Fehler, den niemand den Daten
    zuschreiben würde, sondern uns.
    """
    erste = _BETRAG.search(roh)
    kopf = roh[:erste.start()] if erste else roh
    kopf = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", kopf)     # Trennstrich am Umbruch
    kopf = re.sub(r"(\wä|\wö|\wü|[a-zäöüß])\s*\n\s*([a-zäöüß])", r"\1\2", kopf)
    kopf = re.sub(r"\s+", " ", kopf)
    kopf = re.sub(r"\s*\d\)\s*", " ", kopf)                  # Fußnotenmarken
    return kopf.strip(" .,")


def parse_anlagenspiegel(text: str, year: int) -> list[dict]:
    """Die Zeilen der Anlagenübersicht — je Vermögensposition eine.

    Zeilen ohne Beträge (etwa „1.3 Ähnliche Rechte", die es in Oldenburg
    nicht gibt) kommen **nicht** als Nullzeile herein: Eine Position, die das
    Dokument leer lässt, ist keine mit dem Wert null.
    """
    block = _abschnitt(text)
    if not block:
        return []
    spalten = spaltenzahl(block)
    if spalten not in (12, 13):
        # Ein drittes Layout wäre eine Änderung, die jemand ansehen muss —
        # nicht etwas, das der Parser stillschweigend zurechtbiegt.
        return []

    treffer = list(_ZEILE.finditer(block))
    zeilen: list[dict] = []
    for i, m in enumerate(treffer):
        nr = m.group(1)
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(block)
        roh = block[m.end():ende]
        # Der Fußnotenverweis der Kopfzeile („Vermögen ¹)") und die
        # Spaltennummern stehen vor der ersten Zahl — deshalb wird nach der
        # Betragsliste gefiltert, nicht nach der Position im Text.
        betraege = [_eur(b) for b in _BETRAG.findall(roh)]
        if len(betraege) < spalten:
            continue
        # Die ERSTEN so vielen, wie der Jahrgang Spalten hat: Bei der letzten
        # Zeile eines Blocks hängen die Fußnotentexte hinten dran, und die
        # tragen ihrerseits Zahlen.
        w = betraege[:spalten]
        # Bis 2020 fehlt die Umbuchungs-Spalte im Abschreibungs-Block. Sie
        # wird mit 0,00 ergänzt, damit alle Jahrgänge dieselben Felder
        # tragen — die Kette rechnet sich damit unverändert.
        if spalten == 12:
            w = w[:9] + [0.0] + w[9:]
        label = _label(roh)
        zeilen.append({
            "year": year, "nr": nr, "label": label, "n_columns": spalten,
            "cost_opening": w[0], "additions": w[1], "disposals": w[2],
            "transfers": w[3], "cost_closing": w[4],
            "depreciation_opening": w[5], "depreciation": w[6], "depreciation_releases": w[7],
            "write_ups": w[8], "depreciation_transfers": w[9], "depreciation_closing": w[10],
            "book_value": w[11], "book_value_prior_year": w[12],
        })
    return zeilen


def probe(row: dict) -> tuple[list[str], list[str]]:
    """Welche Ketten dieser Zeile aufgehen — und welche reißen.

    Liefert (bestanden, risse). Gerechnet wird mit **Addition**: Abgänge und
    Abschreibungen stehen im Dokument bereits negativ.
    """
    bestanden: list[str] = []
    risse: list[str] = []

    def pruefe(name: str, ist: float, soll: float, was: str) -> None:
        if abs(ist - soll) <= TOLERANZ:
            bestanden.append(name)
        else:
            risse.append(f"{row['nr']} {row['label'][:28]}: {was} "
                         f"{ist:,.2f} gegen {soll:,.2f} ({abs(ist - soll):,.2f} €)")

    pruefe(PROBE_AHK,
           row["cost_opening"] + row["additions"] + row["disposals"] + row["transfers"],
           row["cost_closing"], "Anschaffungswerte")
    # Bis 2020 fehlt dem Abschreibungs-Block die Umbuchungs-Spalte. Die Kette
    # KANN dort nicht schließen, wo in dem Jahr etwas zwischen den
    # Vermögensarten verschoben wurde — das ist eine Eigenschaft der Vorlage,
    # kein Fehler. Sie als Riss zu melden hieße, dem Dokument einen Defekt
    # anzuhängen, den es nicht hat; sie stillschweigend glattzurechnen wäre
    # schlimmer. Stattdessen wird der Rest als `umbuchung_abgeleitet`
    # ausgewiesen und über den Jahrgang geprüft (`umbuchungsprobe`).
    if row.get("n_columns") == 13:
        pruefe(PROBE_ABSCHREIBUNG,
               (row["depreciation_opening"] + row["depreciation"] + row["depreciation_releases"]
                + row["write_ups"] + row["depreciation_transfers"]),
               row["depreciation_closing"], "Abschreibungen")
    pruefe(PROBE_BUCHWERT, row["cost_closing"] + row["depreciation_closing"],
           row["book_value"], "Buchwert")
    return bestanden, risse


def gegen_bilanz(zeilen: list[dict], bilanz_posten: list[dict]) -> list[str]:
    """Die Gegenprobe an einer anderen Quelle: Buchwert = Bilanzposition.

    Nur für die drei Hauptzeilen (:data:`BILANZ_ROLLE`); die Untergliederung
    des Anlagenspiegels ist feiner als die Bilanz. Fehlt eine Bilanzposition,
    ist das kein Riss — dann gibt es die Gegenprobe für dieses Jahr eben
    nicht, und das darf die Anzeige sagen.
    """
    nach_rolle = {p["role"]: p.get("value") for p in bilanz_posten}
    risse: list[str] = []
    for z in zeilen:
        role = BILANZ_ROLLE.get(z["nr"])
        if not role:
            continue
        bilanz = nach_rolle.get(role)
        if bilanz is None:
            continue
        if abs(z["book_value"] - bilanz) > TOLERANZ:
            risse.append(f"{z['nr']} {z['label'][:28]}: Anlagenspiegel "
                         f"{z['book_value']:,.2f} gegen Bilanz {bilanz:,.2f}")
    return risse


#: Eine Untergruppe des Sachvermögens: Label, Wert des Jahres, Vorjahreswert.
#: Der Label-Teil darf ZEILENUMBRÜCHE enthalten: Im PDF steht
#: „Straßen, Wege, Plätze, Verkehrslen-\nkungsanlagen", und ein Muster ohne
#: `\n` überspringt ausgerechnet die Zeile, um die es geht. Ausgeschlossen
#: bleibt das €-Zeichen — daran endet der vorige Eintrag.
_GRUPPE = re.compile(
    r"([A-ZÄÖÜ][^€]{3,80}?)\s*(-?\d{1,3}(?:\.\d{3})*,\d{2})\s*€\s*"
    r"(-?\d{1,3}(?:\.\d{3})*,\d{2})\s*€")


def parse_sachvermoegen_gruppen(text: str, year: int) -> list[dict]:
    """Die Untergliederung des Infrastrukturvermögens — Straßen, Brücken, …

    Der Anlagenspiegel führt Infrastrukturvermögen als **eine** Zeile. Die
    Aufteilung steht in den Erläuterungen, und dort steht auch der Satz, der
    ihr ihren Namen gibt: „Dem **Substanzverlust** bei den Straßen, Wegen und
    Plätzen um 9,6 Millionen Euro …". Das Wort ist das der Stadt, nicht
    unseres.

    Die Reihenfolge der beiden Beträge ist **Vorjahr, dann Jahr** — im
    Dokument steht die Vergleichsspalte links. Wer sie dreht, macht aus einem
    Verlust einen Zuwachs.
    """
    # ANKER STRUKTURELL, NICHT AM WORT. Die erste Fassung suchte
    # „Substanzverlust" — das Wort steht aber nur im Abschluss 2024, und die
    # Untertabelle gab es schon 2021. Wer am Wort ankert, verliert drei
    # Jahrgänge und merkt es nicht. „Gleisanlagen" ist eine Zeile DER Tabelle
    # und damit da, wo die Tabelle ist.
    m = (re.search(r"Gleisanlagen", text) or re.search(r"Substanzverlust", text))
    if not m:
        return []
    # Der Block beginnt etwas vor der Ankerzeile (sie ist nicht die erste) und
    # reicht über die Aufzählung hinaus.
    fenster = text[max(0, m.start() - 900): m.start() + 2600]
    gruppen: list[dict] = []
    for g in _GRUPPE.finditer(fenster):
        label = re.sub(r"\s+", " ", g.group(1)).strip(" .,–-")
        # Silbentrennung der PDF-Extraktion auflösen („Verkehrslen- kungsanlagen").
        label = re.sub(r"(\w)-\s+(\w)", r"\1\2", label)
        if len(label) < 4:
            continue
        gruppen.append({
            "year": year, "group_name": label,
            "book_value_prior_year": _eur(g.group(2)),
            "book_value": _eur(g.group(3)),
        })
    return gruppen


def umbuchung_abgeleitet(row: dict) -> float:
    """Was die Abschreibungskette nicht erklärt — bei zwölf Spalten.

    Bis 2020 zeigt die Vorlage im Abschreibungs-Block keine Umbuchungen. Was
    zwischen den Vermögensarten verschoben wurde, steht dort nur als
    Differenz zwischen der Spaltensumme und dem ausgewiesenen Endstand.
    Ab 2021 gibt es die Spalte, und der Rest ist null.
    """
    chain = (row["depreciation_opening"] + row["depreciation"] + row["depreciation_releases"]
             + row["write_ups"] + row["depreciation_transfers"])
    return row["depreciation_closing"] - chain


def umbuchungsprobe(zeilen: list[dict]) -> tuple[float, list[str]]:
    """Verschiebungen sind Verschiebungen — sie müssen sich aufheben.

    Die Probe für die Jahrgänge ohne Umbuchungs-Spalte: Was einer
    Vermögensart fehlt, muss einer anderen zugewachsen sein. Gerechnet über
    die **Hauptzeilen** (1, 2, 3), damit Ober- und Untergliederung nicht
    doppelt zählen.

    Geht der Saldo auf, ist bewiesen, dass die Differenzen Umbuchungen sind
    und keine Lücken — 2019 verschoben sich 396.635,53 € vom
    Infrastrukturvermögen zu den Bauten auf fremden Grundstücken, 2020
    54.639,18 € vom Sachvermögen zum Immateriellen. Beide Male: Saldo 0,00 €.
    """
    haupt = [z for z in zeilen if "." not in z["nr"]]
    balance = sum(umbuchung_abgeleitet(z) for z in haupt)
    if abs(balance) <= TOLERANZ:
        return balance, []
    return balance, [f"Umbuchungen heben sich nicht auf: {balance:,.2f} € bleiben übrig"]
