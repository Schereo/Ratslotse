"""Der Haushaltsvollzug — wie das laufende Jahr gegen seinen Plan läuft.

Der Haushalts-Bereich zeigte bisher den **Plan** für das kommende Jahr und das
**Ist** aus dem Jahresabschluss, der zwei Jahre zurückliegt. Dazwischen klaffte
das laufende Jahr: Genau das, was im Rat gerade verhandelt wird.

Die Stadt berichtet darüber vierteljährlich. § 31 der Niedersächsischen
Kommunalhaushalts- und -kassenverordnung verpflichtet sie dazu, und der
Bericht heißt seit 2018 **Finanz- und Leistungsbericht** (davor
„Quartalsbericht“). Er geht an den Ausschuss für Finanzen und Beteiligungen,
zu den Stichtagen 31.03., 30.06., 30.09. und 31.12.

Was dieses Modul liest
----------------------
Aus jedem Bericht die beiden **Übersichtstabellen**, die unter „Auswertung der
Berichte zum …“ stehen:

* **1. Ergebnishaushalt** — je Teilhaushalt Erträge, Aufwendungen und Ergebnis,
  einmal als Ansatz und einmal als Prognose zum Jahresende, dazu die
  gedruckte Abweichung.
* **2. Finanzhaushalt** — dieselbe Tabelle für die Ein- und Auszahlungen der
  Investitionstätigkeit.

Beide enden auf einer gedruckten Summenzeile für die ganze Stadt. Sie ist die
Zahl, die die Schicht überhaupt erst interessant macht: „Der Plan sagt −91,5
Millionen, die Verwaltung erwartet −64,1 Millionen.“

WARUM WORTKOORDINATEN UND NICHT DER TEXTAUSZUG
-----------------------------------------------
Beides wurde gebaut und gemessen. Der pypdf-Fließtext zerreißt Zahlen an
Leerzeichen („6.003. 089“, „- 96.165.678“) — damit ließe sich noch leben. Was
ihn unbrauchbar macht, ist die **leere Zelle**: Wo ein Teilhaushalt keine
Einzahlungen plant, druckt der Bericht nichts, und im Fließtext fehlt die Zahl
einfach. Aus elf Spalten werden neun, und ab da steht jeder Betrag eine Spalte
zu weit links. Gemessen am Bestand: **128 leere Zellen in 18 der 43 Tabellen**
— eine einzige von ihnen genügt, um den Rest ihrer Zeile zu verschieben.

Mit den echten Wortkoordinaten (``pymupdf``) ist die leere Zelle genau das:
eine Spalte ohne Wort. ``pymupdf`` ist dafür Voraussetzung und bewusst KEINE
Abhängigkeit in ``requirements.txt`` — dieselbe Entscheidung wie bei den
Änderungslisten (``council/aenderungslisten.py``) und den PDF-Renderern der
OCR: Deploy und Web-Service bleiben unberührt, die Ingest-Maschine installiert
sich das Paket einmal von Hand.

VIER LESERICHTUNGEN, UND DIE RICHTIGE WIRD GESUCHT
---------------------------------------------------
Die Übersichtstabellen stehen im Querformat, und die Berichte lösen das auf
drei verschiedene Weisen: aufrecht auf einer Querformat-Seite (2023–2026),
über ``/Rotate 270`` (2018–2022) und — in drei Berichten — mit im
Inhaltsstrom gedrehtem Text auf einer aufrechten Seite. In den ersten beiden
Fällen liefert ``pymupdf`` schon Anzeigekoordinaten, im dritten nicht.

Deshalb wird die Leserichtung nicht geraten, sondern **gesucht**: Von den vier
möglichen Drehungen wird die genommen, in der die Seite ihre Tabellenmarke
(„1. Ergebnishaushalt“) und mindestens acht Datenzeilen samt Summenzeile
zeigt. Eine falsche Drehung liefert Buchstabensalat und fällt sofort durch.

ZWEI LAYOUTS, UND WELCHES GILT, WIRD GERECHNET
-----------------------------------------------
Die Tabelle hat in allen Jahrgängen elf Zahlenspalten — aber nicht dieselben.
Bis 2020 steht die Ermächtigungsübertragung an **dritter** Stelle und ist in
die Ansatz-Spalte eingerechnet („Verfügbare Mittel im Saldo“); ab 2021 steht
sie als „nachrichtlich“ **hinten** und bleibt draußen. Die Kopfzeile sagt das
zwar, aber sie ist über die Seite verstreut („Ermächti- gungsübertra- gungen“)
und in einem Bericht mit einem senkrecht gesetzten „T e n d e n z“
durchsetzt.

Also entscheidet die Rechnung. Beide Belegungen werden durchprobiert, und
genommen wird die, unter der die fünf Gleichungen jeder Zeile aufgehen:

1. Ertrag − Aufwand (− Übertragung) = Ansatz-Ergebnis
2. Prognose-Ertrag − Prognose-Aufwand = Prognose-Ergebnis
3. Abweichung Ertrag = Prognose-Ertrag − Ansatz-Ertrag
4. Abweichung Aufwand = Prognose-Aufwand − Ansatz-Aufwand (+ Übertragung)
5. Abweichung Ergebnis = Prognose-Ergebnis − Ansatz-Ergebnis

Unter der falschen Belegung geht keine einzige davon auf — die Beträge liegen
Millionen auseinander. Das ist die stärkste Probe der Schicht: Stünde ein
Betrag eine Spalte daneben, ginge sie nicht auf.

DER ANSATZ HEISST ZWEIERLEI, UND DIE ZEILE SAGT WELCHES
--------------------------------------------------------
Aus derselben Layout-Frage folgt eine Falle, die keine Rechenprobe fängt: Die
Ansatz-Spalte des Ergebnisses **enthält** bis 2020 die Ermächtigungs-
übertragungen aus dem Vorjahr und ab 2021 nicht mehr. Wer beide Jahrgänge
nebeneinanderlegt, vergleicht zwei verschiedene Größen — 2018 stünde ein
Überschuss von 5,4 Millionen statt der 8,8 Millionen des Haushaltsplans.

Deshalb trägt **jede Zeile** ihr ``plan_basis``: ``budget`` (der Ansatz) oder
``budget_plus_carryover`` (die verfügbaren Mittel). Das ist keine Technikspalte,
sondern die Bedingung dafür, dass eine Zeitreihe über den Schnitt 2020/2021
etwas bedeutet.

WAS DER BERICHT NICHT HERGIBT
------------------------------
**Kein Ist zum Stichtag.** Alle 21 gelesenen Berichte führen Ansatz, Prognose
zum Jahresende und Abweichung — keiner nennt, was bis zum Stichtag tatsächlich
gebucht war. „Zum 30. Juni“ ist der Tag, an dem die Ämter ihre Erwartung für
den 31. Dezember abgegeben haben, nicht ein Halbjahres-Ist. Eine Spalte dafür
gibt es hier deshalb nicht; sie wäre in jeder Zeile leer und in jeder Anzeige
eine Einladung zum Missverständnis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from council.herkunft import Herkunft

# --------------------------------------------------------------------------
# Proben
# --------------------------------------------------------------------------

PROBE_SPALTEN = "execution_columns"
PROBE_ZEILE = "execution_row"
PROBE_SUMME = "execution_totals"
PROBE_ZEITRAUM = "execution_period"

#: Ihre Erklärsätze stehen in ``herkunft.PROBEN`` und NICHT noch einmal hier:
#: Sie sind für Leserinnen geschrieben und reisen über die API in den
#: Beleg-Chip. Eine zweite Fassung neben der ersten driftet, und welche dann
#: gilt, entscheidet der Zufall des Aufrufwegs.

#: Was diese Schicht abdeckt — reist mit den Zahlen, nicht im Frontend.
ABGRENZUNG = (
    "Kernverwaltung der Stadt Oldenburg, dreizehn Teilhaushalte. Gegenüber "
    "stehen der beschlossene Ansatz und die Prognose der Ämter für den "
    "31. Dezember — nicht das, was bis zum Stichtag gebucht war. Die "
    "Eigenbetriebe berichten getrennt und sind hier nicht enthalten."
)

#: Der Bericht rundet und sagt es selbst: „Es kann zu geringen
#: Rundungsdifferenzen im Vergleich zu den einzelnen Übersichten der
#: Teilhaushalte kommen.“ Gemessen über 42 Tabellen sind es höchstens 3 € auf
#: der Summenzeile. Fünfzehn Euro ist damit großzügig — und immer noch fünf
#: Größenordnungen unter jedem Spaltenfehler, den diese Proben fangen sollen.
TOLERANZ_EUR = 15.0

#: Werte der Spalte ``plan_basis`` (s. Modulkopf).
BASIS_ANSATZ = "budget"
BASIS_MIT_UEBERTRAG = "budget_plus_carryover"

#: Werte der Spalte ``budget``.
ERGEBNISHAUSHALT = "result"
FINANZHAUSHALT = "cash"

#: Werte der Spalte ``kind``, je Haushalt. Der Finanzhaushalt bewegt
#: Ein- und Auszahlungen und keine Erträge — zwei Vokabulare, damit eine
#: Abfrage über beide Haushalte nicht versehentlich Äpfel addiert.
ARTEN: dict[str, tuple[str, str, str]] = {
    ERGEBNISHAUSHALT: ("revenue", "expense", "result"),
    FINANZHAUSHALT: ("inflow", "outflow", "result"),
}

#: Wie die beiden Haushalte für Leserinnen heißen — hier und nicht im
#: Frontend, damit Web und App dieselbe Auskunft geben.
HAUSHALT_NAMEN: dict[str, str] = {
    ERGEBNISHAUSHALT: "Ergebnishaushalt",
    FINANZHAUSHALT: "Finanzhaushalt (Investitionen)",
}

ART_NAMEN: dict[str, str] = {
    "revenue": "Erträge",
    "expense": "Aufwendungen",
    "inflow": "Einzahlungen",
    "outflow": "Auszahlungen",
    "result": "Ergebnis",
}

#: Was ``plan_basis`` bedeutet, in einem Satz je Wert. Er gehört an jede
#: Anzeige, die Jahrgänge nebeneinanderstellt (s. Modulkopf).
BASIS_ERKLAERT: dict[str, str] = {
    BASIS_ANSATZ:
        "Ansatz des Haushaltsplans. Die Ermächtigungsübertragungen aus dem "
        "Vorjahr stehen daneben und sind nicht eingerechnet — so berichtet "
        "die Stadt seit dem Haushaltsjahr 2021.",
    BASIS_MIT_UEBERTRAG:
        "Verfügbare Mittel: Ansatz zuzüglich der Ermächtigungsübertragungen "
        "aus dem Vorjahr. So berichtete die Stadt bis zum Haushaltsjahr 2020 "
        "— der Wert liegt deshalb unter dem Überschuss, den der Haushaltsplan "
        "selbst ausweist.",
}


class VollzugFehler(RuntimeError):
    """Ein Bericht, dessen eigene Rechnung nicht aufgeht."""


# --------------------------------------------------------------------------
# Die Felder
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Position:
    """Eine Zeile der Übersichtstabelle, aufgeteilt nach Art."""

    #: 1–13; ``0`` ist keine Teilhaushalts-Nummer, sondern die Summenzeile.
    #: Der Primärschlüssel verträgt kein NULL, deshalb eine Zahl.
    sub_budget: int
    kind: str
    #: Die gedruckte Bezeichnung („Soziales und Gesundheit“, „Summen“).
    label: str
    budgeted: float | None
    forecast: float | None
    deviation: float | None
    #: „nachrichtlich: Ermächtigungsübertragungen“ — nur an der Aufwands- bzw.
    #: Auszahlungszeile, denn genau dazu ermächtigen sie (§ 20 KomHKVO).
    carryover: float | None
    is_total: bool


@dataclass(frozen=True)
class Vollzugsbericht:
    """Eine Übersichtstabelle: ein Haushaltsjahr, ein Stichtag, ein Haushalt."""

    budget_year: int
    #: ISO-Datum des Stichtags, z. B. ``2025-06-30``.
    as_of: str
    budget: str
    plan_basis: str
    positionen: list[Position]
    probes: tuple[str, ...]
    probe_result: str

    @property
    def summe(self) -> dict[str, Position]:
        """Die Summenzeile je Art — die Zahl für die ganze Stadt."""
        return {p.kind: p for p in self.positionen if p.is_total}


# --------------------------------------------------------------------------
# PDF → Wörter → Zeilen
# --------------------------------------------------------------------------

#: Ein Wort: (linke Kante, rechte Kante, Grundlinie, Text).
Wort = tuple[float, float, float, str]

#: Die vier Leserichtungen (s. Modulkopf). Gruppiert wird später über die
#: **Grundlinie** und nicht über die Oberkante: Zellen einer Tabellenzeile
#: teilen ihre Grundlinie, ihre Oberkante aber nicht — im Bericht zum
#: 31.12.2024 stehen drei Zellen 0,2 pt höher als der Rest ihrer Zeile, und
#: eine Seitenzahl daneben zog sie über die Oberkante in eine eigene Zeile.
_RICHTUNGEN: tuple[tuple[str, object], ...] = (
    ("0", lambda x0, y0, x1, y1: (x0, x1, y1)),
    ("90", lambda x0, y0, x1, y1: (y0, y1, -x0)),
    ("180", lambda x0, y0, x1, y1: (-x1, -x0, -y0)),
    ("270", lambda x0, y0, x1, y1: (-y1, -y0, x1)),
)

#: Deutsche Zahl. „2030,0“ (Prozentspalte) hat keine Tausenderpunkte, große
#: Beträge haben sie immer — beide Formen müssen durch.
_ZAHL = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")
_NR = re.compile(r"^(0[1-9]|1[0-9])$")
_MARKE = re.compile(r"\b([12])\.\s*(Ergebnishaushalt|Finanzhaushalt)")
_STICHTAG = re.compile(
    r"Auswertung der Berichte\s+zum\s+"
    r"(\d{1,2})\s*\.\s*(\d{1,2}|[A-Za-zä]+)\s*\.?\s*(\d{4})")
#: Das Haushaltsjahr, ein zweites Mal auf derselben Seite (s. PROBE_ZEITRAUM).
_ABWEICHUNGSJAHR = re.compile(r"Plan/Ist-Abweichung\s+(\d{4})")

_MONATE = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
           "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
           "oktober": 10, "november": 11, "dezember": 12}


def _betrag(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def stichtag(text: str) -> date | None:
    """Der Stichtag aus der Überschrift — „30.06.2018“ wie „30. Juni 2025“."""
    m = _STICHTAG.search(text)
    if m is None:
        return None
    tag, monat, jahr = m.group(1), m.group(2), m.group(3)
    nummer = _MONATE.get(monat.lower()) if not monat.isdigit() else int(monat)
    if not nummer:
        return None
    try:
        return date(int(jahr), nummer, int(tag))
    except ValueError:
        return None


def _zeilen_bilden(woerter: list[Wort]) -> list[list[Wort]]:
    """Wörter → visuelle Zeilen: nach Grundlinie gruppiert, in der Zeile nach x."""
    zeilen: list[list[Wort]] = []
    for w in sorted(woerter, key=lambda w: (w[2], w[0])):
        if zeilen and abs(w[2] - zeilen[-1][0][2]) <= 2.5:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    for z in zeilen:
        z.sort(key=lambda w: w[0])
    return zeilen


def _schluessel(zeile: list[Wort]) -> tuple[int | None, list[Wort]]:
    """Die Zeilennummer und was hinter ihr steht — ``0`` für die Summenzeile.

    Der Griff auf die ersten ZWEI Wörter ist kein Spielraum, sondern die
    Seitenzahl: Sie steht am linken Rand und teilt in mehreren Berichten die
    Grundlinie mit einer Datenzeile. Wer nur das erste Wort prüft, verliert in
    jedem dieser Berichte genau einen Teilhaushalt — und der fehlt danach
    still, weil die Summenprobe ihn nicht vermisst, sondern reißt.
    """
    for i, w in enumerate(zeile[:2]):
        if _NR.match(w[3]):
            return int(w[3]), zeile[i + 1:]
        if w[3].startswith("Summe"):
            return 0, zeile[i + 1:]
    return None, zeile


def _spalten(datenzeilen: list[list[Wort]], luecke: float = 12.0) -> list[float]:
    """Die Spaltenmitten: rechte Kanten aller Zahlen, zu Gruppen gebündelt.

    Die Beträge sind rechtsbündig gesetzt, ihre rechten Kanten liegen deshalb
    auf einem Zehntel beieinander. Zwischen zwei Spalten liegen mindestens
    25 pt — die Lücke von 12 pt trennt sicher und fasst nichts zusammen, was
    getrennt gehört.
    """
    kanten = sorted(w[1] for z in datenzeilen for w in z if _ZAHL.match(w[3]))
    gruppen: list[list[float]] = []
    for k in kanten:
        if gruppen and k - gruppen[-1][-1] <= luecke:
            gruppen[-1].append(k)
        else:
            gruppen.append([k])
    return [sum(g) / len(g) for g in gruppen]


def _zuordnen(zeile: list[Wort], mitten: list[float],
              toleranz: float = 14.0) -> list[float | None]:
    """Die Beträge einer Zeile auf die Spalten legen — leere Zelle bleibt leer."""
    aus: list[float | None] = [None] * len(mitten)
    for w in zeile:
        if not _ZAHL.match(w[3]):
            continue
        i = min(range(len(mitten)), key=lambda j: abs(mitten[j] - w[1]))
        if abs(mitten[i] - w[1]) <= toleranz:
            aus[i] = _betrag(w[3])
    return aus


def seiten_woerter(pdf_bytes: bytes) -> list[list[tuple]]:
    """Je Seite die rohen Wortrahmen ``(x0, y0, x1, y1, text)``."""
    try:
        import pymupdf  # noqa: PLC0415 — bewusst optional, s. Modulkopf
    except ImportError as e:  # pragma: no cover — auf Maschinen mit Paket unerreichbar
        raise VollzugFehler(
            "pymupdf fehlt — die Spaltenzuordnung braucht Wortkoordinaten. "
            "Einmalig installieren: .venv/bin/pip install pymupdf"
        ) from e

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [[(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
                for page in doc]


# --------------------------------------------------------------------------
# Eine Tabellenseite lesen
# --------------------------------------------------------------------------

#: Die elf Spalten, zweimal belegt. Erste Belegung 2018–2020, zweite ab 2021 —
#: welche gilt, entscheidet die Rechnung (s. Modulkopf), nicht das Jahr.
_ALT = ("rev_plan", "exp_plan", "carryover", "plan_result",
        "rev_fc", "exp_fc", "fc_result",
        "dev_rev", "dev_exp", "dev_result", "pct")
_NEU = ("rev_plan", "exp_plan", "plan_result",
        "rev_fc", "exp_fc", "fc_result",
        "dev_rev", "dev_exp", "dev_result", "pct", "carryover")

_LAYOUTS = ((_ALT, BASIS_MIT_UEBERTRAG), (_NEU, BASIS_ANSATZ))


def _gleichungen(r: dict, layout: tuple[str, ...]) -> list[tuple[str, float, float]]:
    """Die nachrechenbaren Gleichungen einer Zeile: (Name, links, rechts).

    Leere Zellen nehmen ihre Gleichung mit — eine Zelle, die der Bericht nicht
    druckt, ist keine Zahl, die wir prüfen könnten.
    """
    g = r.get
    aus: list[tuple[str, float, float]] = []
    if layout is _ALT:
        if None not in (g("rev_plan"), g("exp_plan"), g("carryover"), g("plan_result")):
            aus.append(("Ansatz", g("rev_plan") - g("exp_plan") - g("carryover"),
                        g("plan_result")))
        if None not in (g("exp_fc"), g("exp_plan"), g("carryover"), g("dev_exp")):
            aus.append(("Abweichung Aufwand",
                        g("exp_fc") - g("exp_plan") - g("carryover"), g("dev_exp")))
    else:
        if None not in (g("rev_plan"), g("exp_plan"), g("plan_result")):
            aus.append(("Ansatz", g("rev_plan") - g("exp_plan"), g("plan_result")))
        if None not in (g("exp_fc"), g("exp_plan"), g("dev_exp")):
            aus.append(("Abweichung Aufwand", g("exp_fc") - g("exp_plan"), g("dev_exp")))
    if None not in (g("rev_fc"), g("exp_fc"), g("fc_result")):
        aus.append(("Prognose", g("rev_fc") - g("exp_fc"), g("fc_result")))
    if None not in (g("rev_fc"), g("rev_plan"), g("dev_rev")):
        aus.append(("Abweichung Ertrag", g("rev_fc") - g("rev_plan"), g("dev_rev")))
    if None not in (g("fc_result"), g("plan_result"), g("dev_result")):
        aus.append(("Abweichung Ergebnis", g("fc_result") - g("plan_result"),
                    g("dev_result")))
    return aus


def _layout_waehlen(roh: list[tuple[int, str, list[float | None]]]):
    """Die Spaltenbelegung, unter der die Tabelle sich selbst bestätigt.

    Gibt ``(layout, plan_basis, treffer, gegenprobe)`` zurück — ``gegenprobe``
    ist die Trefferzahl der VERWORFENEN Belegung und gehört ins Prüfprotokoll:
    Sie ist der Beleg dafür, dass die Wahl eindeutig war und nicht knapp.
    """
    bewertet = []
    for layout, basis in _LAYOUTS:
        treffer = risse = 0
        for _nr, _label, werte in roh:
            r = dict(zip(layout, werte))
            for _name, links, rechts in _gleichungen(r, layout):
                if abs(links - rechts) <= TOLERANZ_EUR:
                    treffer += 1
                else:
                    risse += 1
        bewertet.append((risse, -treffer, layout, basis, treffer))
    bewertet.sort(key=lambda b: (b[0], b[1]))
    _risse, _neg, layout, basis, treffer = bewertet[0]
    gegenprobe = bewertet[1][4]
    return layout, basis, treffer, gegenprobe


def _tabelle_lesen(zeilen: list[list[Wort]], art: str):
    """Eine Übersichtstabelle → Positionen, geprüft. Wirft bei jedem Riss."""
    daten: list[tuple[int, list[Wort]]] = []
    for z in zeilen:
        nr, rest = _schluessel(z)
        if nr is not None and sum(1 for w in rest if _ZAHL.match(w[3])) >= 6:
            daten.append((nr, rest))
    if len(daten) < 8 or not any(nr == 0 for nr, _ in daten):
        raise VollzugFehler(
            f"{art}: {len(daten)} Datenzeilen und "
            f"{'keine' if not any(nr == 0 for nr, _ in daten) else 'eine'} "
            "Summenzeile — das ist keine vollständige Übersichtstabelle.")

    mitten = _spalten([rest for _nr, rest in daten])
    if len(mitten) != len(_ALT):
        raise VollzugFehler(
            f"{art}: {len(mitten)} Zahlenspalten statt {len(_ALT)} — der "
            "Bericht führt eine Tabelle, die dieses Modul nicht kennt.")

    beschriftet = _beschriften(zeilen, daten, mitten)
    roh = [(nr, label, _zuordnen(rest, mitten))
           for (nr, rest), label in zip(daten, beschriftet)]
    layout, basis, treffer, gegenprobe = _layout_waehlen(roh)
    if treffer < 40 or gegenprobe >= treffer:
        raise VollzugFehler(
            f"{art}: Die Spaltenbelegung ist nicht entschieden "
            f"({treffer} Gleichungen gehen auf, die andere Belegung schafft "
            f"{gegenprobe}) — ohne eindeutige Belegung wird nichts gespeichert.")

    zeilenwerte = [(nr, label, dict(zip(layout, werte))) for nr, label, werte in roh]
    for nr, label, r in zeilenwerte:
        for name, links, rechts in _gleichungen(r, layout):
            if abs(links - rechts) > TOLERANZ_EUR:
                raise VollzugFehler(
                    f"{art}, Zeile {nr or 'Summen'} ({label}): {name} geht nicht "
                    f"auf — gerechnet {links:,.0f} €, gedruckt {rechts:,.0f} €.")

    summe = next(r for nr, _l, r in zeilenwerte if nr == 0)
    teile = [r for nr, _l, r in zeilenwerte if nr != 0]
    for feld in layout:
        if feld == "pct" or summe.get(feld) is None:
            continue
        gerechnet = sum(r[feld] or 0.0 for r in teile)
        if abs(gerechnet - summe[feld]) > TOLERANZ_EUR:
            raise VollzugFehler(
                f"{art}, Spalte {feld}: Die Teilhaushalte ergeben "
                f"{gerechnet:,.0f} €, die Summenzeile nennt {summe[feld]:,.0f} €.")

    ertrag, aufwand, ergebnis = ARTEN[art]
    positionen: list[Position] = []
    for nr, label, r in zeilenwerte:
        for kind, plan, prognose, abweichung, uebertrag in (
                (ertrag, r["rev_plan"], r["rev_fc"], r["dev_rev"], None),
                (aufwand, r["exp_plan"], r["exp_fc"], r["dev_exp"], r["carryover"]),
                (ergebnis, r["plan_result"], r["fc_result"], r["dev_result"], None)):
            positionen.append(Position(
                sub_budget=nr, kind=kind,
                label=label or ("Summen" if nr == 0 else f"Teilhaushalt {nr:02d}"),
                budgeted=plan, forecast=prognose, deviation=abweichung,
                carryover=uebertrag, is_total=nr == 0))

    ergebnis_probe = (
        f"{treffer} Gleichungen gehen auf (die verworfene Spaltenbelegung "
        f"schafft {gegenprobe}); die Summenzeile ist aus "
        f"{len(teile)} Teilhaushalten nachgerechnet")
    return positionen, basis, ergebnis_probe


def _beschriften(zeilen: list[list[Wort]], daten: list[tuple[int, list[Wort]]],
                 mitten: list[float]) -> list[str]:
    """Die gedruckte Bezeichnung je Datenzeile — auch wenn sie umbricht.

    „Klima, Umwelt, Mobilität, Bau, Grün, Friedhöfe“ steht auf zwei Zeilen,
    und die Beträge stehen daneben, senkrecht zentriert zwischen beiden — die
    Datenzeile trägt dann nur ihre Nummer, der Name steht darüber und darunter.

    Zugeordnet wird ein Bruchstück deshalb der NÄCHSTEN Datenzeile und nur
    ihr. Ein Band „zwischen voriger und nächster Grundlinie“ war der erste
    Versuch und ging schief: Die Bänder benachbarter Zeilen überlappen, und
    „Friedhöfe“ landete zusätzlich bei „Soziales und Gesundheit“. Zwei
    Schranken halten außerdem Kopf- und Fußzeile draußen, die auf derselben
    Seite stehen und keiner Zeile gehören: Ein Bruchstück muss näher als eine
    halbe Zeilenhöhe an seiner Zeile liegen UND innerhalb der Tabelle, also
    zwischen erster und letzter Datenzeile.
    """
    grenze = min(mitten) - 25.0
    grundlinien = [rest[0][2] if rest else 0.0 for _nr, rest in daten]
    abstaende = sorted(b - a for a, b in zip(grundlinien, grundlinien[1:]))
    hoehe = abstaende[len(abstaende) // 2] if abstaende else 16.0
    naehe = hoehe * 0.6

    #: Je Datenzeile die Bruchstücke, die ihr am nächsten liegen.
    fragmente: list[list[tuple[float, float, str]]] = [[] for _ in daten]
    for z in zeilen:
        if any(_ZAHL.match(w[3]) for w in z):
            continue
        for w in z:
            if w[1] >= grenze or _NR.match(w[3]):
                continue
            if not (grundlinien[0] - naehe <= w[2] <= grundlinien[-1] + naehe):
                continue
            i = min(range(len(daten)), key=lambda j: abs(grundlinien[j] - w[2]))
            if abs(grundlinien[i] - w[2]) <= naehe:
                fragmente[i].append((w[2], w[0], w[3]))

    aus: list[str] = []
    for i, (_nr, rest) in enumerate(daten):
        teile = list(fragmente[i])
        for w in rest:
            if _ZAHL.match(w[3]):
                break
            teile.append((w[2], w[0], w[3]))
        teile.sort()
        aus.append(" ".join(t[2] for t in teile).strip())
    return aus


# --------------------------------------------------------------------------
# Ein Bericht
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Lesung:
    """Was ein Dokument hergab — und was daran nicht aufging.

    Zwei Listen und nicht eine Ausnahme, weil ein Dokument **zwei** Einheiten
    trägt: Ergebnis- und Finanzhaushalt. Im Bericht zum 30.06.2024 weist die
    Stadt beim Teilhaushalt 13 eine Aufwands-Abweichung von −40.377 € aus,
    obwohl Ansatz und Prognose dort gleich sind — ein Fehler im Dokument, und
    zwar nur in seiner ERGEBNIS-Tabelle. Wer daran das ganze Dokument
    verwirft, verliert einen Finanzhaushalt, an dem nichts falsch ist.
    """

    berichte: list[Vollzugsbericht]
    #: Je verworfener Tabelle ein Satz im Klartext, mit der Stelle.
    risse: list[str]


def _tabellenseiten(pdf_bytes: bytes):
    """Je erkannter Tabellenseite (Art, Zeilen, Volltext) — in ihrer Richtung."""
    zeichen = buchstaben = 0
    for seite in seiten_woerter(pdf_bytes):
        if not seite:
            continue
        for w in seite:
            zeichen += len(w[4])
            buchstaben += sum(c.isalpha() for c in w[4])
        for _name, dreh in _RICHTUNGEN:
            woerter = [(*dreh(w[0], w[1], w[2], w[3]), w[4]) for w in seite]
            woerter = [(round(a, 1), round(b, 1), round(c, 1), t)
                       for a, b, c, t in woerter]
            zeilen = _zeilen_bilden(woerter)
            volltext = " ".join(" ".join(w[3] for w in z) for z in zeilen)
            marke = _MARKE.search(volltext)
            if marke is None:
                continue
            art = (ERGEBNISHAUSHALT if marke.group(2) == "Ergebnishaushalt"
                   else FINANZHAUSHALT)
            yield art, zeilen, volltext
            break
    # Der Buchstabenanteil steht am Ende, damit ein Aufrufer ohne Treffer
    # unterscheiden kann: keine Tabelle — oder gar kein lesbarer Text?
    yield "letters", buchstaben / zeichen if zeichen else 0.0, ""


def lies_vollzugsbericht(pdf_bytes: bytes) -> Lesung:
    """Die Übersichtstabellen eines Finanz- und Leistungsberichts.

    Liefert bis zu zwei Berichte (Ergebnis- und Finanzhaushalt) und je
    verworfener Tabelle einen Satz, warum. Beide Listen leer heißt „das ist
    kein stadtweiter Vollzugsbericht“ — die Fachausschuss- und
    Eigenbetriebs-Fassungen tragen dieselben Label und sollen hier still
    durchfallen, nicht lärmen.
    """
    return lies_tabellenseiten(_tabellenseiten(pdf_bytes))


def lies_tabellenseiten(seiten) -> Lesung:
    """Aus erkannten Tabellenseiten die Berichte bauen — die Naht zum PDF.

    Getrennt von :func:`lies_vollzugsbericht`, damit sich prüfen lässt, was
    hier entschieden wird (Stichtag, Haushaltsjahr, Proben), ohne ein PDF zu
    bauen: ``pymupdf`` ist bewusst keine Abhängigkeit dieses Projekts, und ein
    Test, der es braucht, liefe in der CI gar nicht erst.
    """
    gefunden: dict[str, tuple[list[Position], str, str, int | None]] = {}
    risse: list[str] = []
    anteil = 1.0
    # Der Stichtag wird von JEDER Tabellenseite eingesammelt, auch von einer,
    # deren Tabelle durchfällt: Bis 2022 trägt nur die Ergebnis-Seite die
    # Überschrift „Auswertung der Berichte zum …“, die Finanzhaushalts-Seite
    # steht ohne. Käme der Stichtag nur aus den gelesenen Tabellen, verlöre ein
    # Dokument mit kaputter Ergebnis-Tabelle seinen Finanzhaushalt gleich mit —
    # nicht wegen dessen Zahlen, sondern weil niemand mehr sagt, wann sie
    # gelten.
    tage: set[date] = set()
    for art, zeilen, volltext in seiten:
        if art == "letters":
            anteil = zeilen  # type: ignore[assignment]
            continue
        if (tag := stichtag(volltext)) is not None:
            tage.add(tag)
        if art in gefunden:
            continue
        try:
            positionen, basis, probe = _tabelle_lesen(zeilen, art)
        except VollzugFehler as fehler:
            # Keine Tabelle auf dieser Seite ist der Normalfall: Die Marke
            # steht auch über den Erläuterungen. Eine ANGEFANGENE Tabelle,
            # deren Rechnung reißt, ist es nicht — die wird gemeldet.
            if "keine vollständige Übersichtstabelle" not in str(fehler):
                risse.append(str(fehler))
            continue
        jahr = _ABWEICHUNGSJAHR.search(volltext)
        gefunden[art] = (positionen, basis, probe,
                         int(jahr.group(1)) if jahr else None)

    if not gefunden:
        if anteil < 0.5:
            risse.append(
                f"Der Textlayer trägt nur {anteil:.0%} Buchstaben — das PDF "
                "bringt keine Zeichenzuordnung mit (Glyphen-Salat). Ohne sie "
                "ist keine Spalte lesbar; hier hilft nur eine neue Fassung "
                "des Dokuments.")
        return Lesung([], risse)

    if not tage:
        return Lesung([], risse + [
            "Die Übersichtstabelle steht da, aber kein Stichtag „Auswertung "
            "der Berichte zum …“ — ohne ihn wüsste keine Zeile, wann sie gilt."])
    if len(tage) > 1:
        return Lesung([], risse + [
            "Mehrere Stichtage in einem Dokument: "
            + ", ".join(t.isoformat() for t in sorted(tage))])
    tag = next(iter(tage))

    berichte: list[Vollzugsbericht] = []
    for art, (positionen, basis, probe, jahr) in sorted(gefunden.items()):
        probes = [PROBE_SPALTEN, PROBE_ZEILE, PROBE_SUMME]
        zeitraum = ""
        if jahr is not None:
            if jahr != tag.year:
                risse.append(
                    f"{art}: Der Stichtag nennt das Haushaltsjahr {tag.year}, "
                    f"die Spaltengruppe „Plan/Ist-Abweichung“ aber {jahr}.")
                continue
            probes.append(PROBE_ZEITRAUM)
            zeitraum = f"; Haushaltsjahr {tag.year} zweimal auf der Seite genannt"
        berichte.append(Vollzugsbericht(
            budget_year=tag.year, as_of=tag.isoformat(), budget=art,
            plan_basis=basis, positionen=positionen,
            probes=tuple(probes), probe_result=probe + zeitraum))
    return Lesung(berichte, risse)


def herkunft_fuer(bericht: Vollzugsbericht, *, document_id: int | None,
                  label: str | None, url: str | None) -> Herkunft:
    """Die Herkunft: das Dokument, der Abschnitt und was nachgerechnet wurde."""
    tabelle = ("1. Ergebnishaushalt" if bericht.budget == ERGEBNISHAUSHALT
               else "2. Finanzhaushalt")
    tag = date.fromisoformat(bericht.as_of)
    return Herkunft(
        kind="ris",
        probe=list(bericht.probes),
        document_id=document_id,
        label=label or f"Finanz- und Leistungsbericht zum {bericht.as_of}",
        url=url,
        citation=f"Auswertung der Berichte zum {tag:%d.%m.%Y}, {tabelle}",
        probe_result=bericht.probe_result,
        as_of=f"Finanz- und Leistungsbericht zum {tag:%d.%m.%Y}",
    )
