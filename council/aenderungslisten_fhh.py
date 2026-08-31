"""Die Änderungslisten zum FINANZhaushalt — der zweite Haushalt im Verfahren.

Der Schwester-Parser zu ``council/aenderungslisten.py``. Jener liest den
Ergebnishaushalt (was die Stadt erwirtschaftet und verbraucht), dieser den
Finanzhaushalt (was tatsächlich fließt — und vor allem: was investiert wird).
Beide Listen entstehen im selben Verfahren, liegen als Anlage an derselben
Vorlage und werden im selben Ausschuss beschlossen.

WARUM EIN EIGENES MODUL. Die Bauform ist eine andere, und nicht ein bisschen:
Wo der EHH ZWEI Betragsspalten führt (Ertrag ±, Aufwand ±), führt der FHH
FÜNF — ``Soll laut Entwurf | Einzahlungen ± | Auszahlungen ± | VE ± | neues
Soll``. Den EHH-Parser darauf zu verallgemeinern hieße, einen an 1.799
Positionen bewiesenen Leser umzubauen, um einen zweiten zu sparen. Geteilt
wird stattdessen die GEOMETRIE (``zeilen_bilden``, ``band``,
``zeilen_falten`` — dort unter öffentlichem Namen), denn die ist bei beiden
dieselbe.

Die Bauform (an allen 18 FHH-Dokumenten der Jahrgänge 2019–2026 gemessen)
-------------------------------------------------------------------------
Querformat, elf Spalten, als Linienraster gezeichnet::

    Lfd.Nr | THH | Seite | Produkt | Bezeichnung | Soll laut Entwurf |
    Einzahlungen ± | Auszahlungen ± | VE ± | neues Soll | Erläuterungen

Am Ende je Planjahr eine „Zusammenstellung der Veränderungen“ mit
Verwaltungsentwurf, jeder Liste und der Endsumme.

VIER UNTERSCHIEDE ZUM EHH, alle gemessen und alle hier abgefangen:

1. **Die Positionszeile trägt ihre EIGENE Rechenprobe.** ``Soll laut
   Entwurf + Einzahlung + Auszahlung = neues Soll`` — gemessen 190 von 191
   Zeilen des Bestands. Das hat der EHH nicht, und es ist der schärfste
   Wächter über die Spaltenzuordnung, den dieses Ressort besitzt: Landete ein
   Betrag eine Spalte daneben, ginge diese Zeile nicht auf. Sie läuft
   deshalb je Zeile, nicht nur als Schlusssumme.
2. **Die Zusammenstellung hat zwei Formen.** Verwaltungslisten führen VIER
   Beträge (Ein, Aus, Saldo, VE), die Beschluss-Dateien DREI (Ein, Aus,
   Saldo) plus eine Spalte „Vorschlag von“ mit dem Urheber — derselbe
   Apparat wie beim EHH seit #838.
3. **Der Kopf der Saldo-Spalte heißt nicht überall gleich**: „Saldo“ in den
   meisten Dokumenten, „Verbesserung/Verschlechterung“ in 212802. Nur auf
   das erste zu prüfen verlöre ein ganzes Dokument — beide gelten.
4. **Ein Gedankenstrich IST ein Betrag** und heißt Null. Als Zahl gelesen
   fehlt er, und die Zeile fällt unter jede Mindestanzahl von Beträgen;
   daran verschwanden bei der ersten Messung sämtliche Beschluss-Dateien.

Warum die Spalten aus den LINIEN kommen, nicht aus den Kopfwörtern
------------------------------------------------------------------
Der EHH misst seine zwei Spalten an den Kopfwörtern „Ertrag“/„Aufwand“ und
arbeitet mit Toleranzfenstern. Bei fünf Spalten à ~54 pt trägt das nicht:
Die Fenster stießen aneinander. Der FHH zeichnet sein Raster ohnehin —
gemessen zwölf senkrechte Linien auf jeder Tabellenseite von 17 der 18
Dokumente. Verankert wird an der Erläuterungs-Spalte: Die sechs Linienkanten
links des Kopfworts „Erläuterungen“ sind die fünf Betragsspalten, die davor
ist die Bezeichnung.

Das trägt auch dort, wo die Zählung nicht stimmt: 286016 zeichnet auf den
meisten Seiten die äußeren Tabellenränder nicht mit (10 statt 12 Linien).
Die INNEREN Kanten stehen trotzdem alle — und nur die braucht dieser Aufbau.

``pymupdf`` ist Voraussetzung, aus demselben Grund wie beim EHH bewusst nicht
in ``requirements.txt``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from council.aenderungslisten import (
    Linien,
    ListenFehler,
    Wort,
    band,
    seiten_linien,
    seiten_woerter,
    zeilen_bilden,
    zeilen_falten,
)
from council.herkunft import Herkunft

# --------------------------------------------------------------- Label-Sortierung

#: Was dieses Modul liest: FHH-Änderungslisten des KERNhaushalts.
_LABEL_FHH = re.compile(r"\bFHH\b|Finanzhaushalt", re.I)
#: Was draußen bleibt — andere Haushalte, die ihre eigenen FHH-Listen führen:
#: Eigenbetrieb Gebäudewirtschaft (EGH), Bäderbetrieb (BBO),
#: Wirtschaftsförderung (WFO), die beiden Stiftungen. Ihre Labels tragen
#: „Finanzhaushalt“ mit, deshalb schlägt RAUS vor FHH.
_LABEL_RAUS = re.compile(
    r"\bEGH\b|\bBBO\b|\bWFO\b|Klävemann|Stiftung|Vermögensplan|Erfolgsplan"
    r"|Synopse", re.I)
_LABEL_VERW = re.compile(r"Verw(?:altung|\.)\s*(III|II|I|[123])\b", re.I)
_LABEL_AFB = re.compile(r"beschlossene\s+Änderungen", re.I)

_ROEMISCH = {"I": 1, "II": 2, "III": 3, "1": 1, "2": 2, "3": 3}


def liste_aus_label(label: str | None) -> str | None:
    """Anlagen-Label → Listen-Schlüssel, oder ``None`` für „gehört nicht her“.

    Dieselben Schlüssel wie beim EHH (``verwaltung_1..3``,
    ``afb_beschlossen``), damit beide Haushalte im Frontend nebeneinander
    dieselbe Sprache sprechen. Von 32 Anlagen, deren Label „Finanzhaushalt“
    oder „FHH“ trägt, bleiben so die 18 des Kernhaushalts übrig — genauso
    viele, wie es EHH-Listen gibt.
    """
    t = label or ""
    if _LABEL_RAUS.search(t) or not _LABEL_FHH.search(t):
        return None
    if _LABEL_AFB.search(t):
        return "afb_beschlossen"
    m = _LABEL_VERW.search(t)
    if m and "nderungslist" in t:
        return f"verwaltung_{_ROEMISCH[m.group(1).upper()]}"
    return None


# ------------------------------------------------------------------- Datenformen

#: Ein Betrag oder „kein Betrag“. Der Gedankenstrich der Dokumente wird zu 0,
#: eine leere Zelle zu ``None`` — das ist ein Unterschied: „ausdrücklich
#: null“ gegen „hier steht nichts“.
_ZAHL = re.compile(r"-?\d{1,3}(?:\.\d{3})*|-?\d+")
_STRICH = frozenset({"-", "–", "—"})


@dataclass
class FhhZeile:
    """Eine Position einer FHH-Änderungsliste — ein Planjahr, eine Zeile."""

    year: int
    seq: int
    sub_budget: int | None
    page_draft: str | None   # auch „neu“ — dann steht die Zeile nicht im Entwurf
    product: str | None         # Investitionscode, z. B. „I10.089904.500“
    label: str
    #: Die fünf Betragsspalten. ``None`` = Zelle leer, ``0`` = Strich.
    planned_draft: int | None
    inflow: int | None
    outflow: int | None
    commitment_authorizations: int | None
    planned_new: int | None
    explanation: str | None = None
    author: str | None = None


@dataclass
class FhhSumme:
    """Eine Zeile der Zusammenstellung: Entwurf, eine Liste oder die Endsumme."""

    year: int
    typ: str  # "entwurf" | "liste" | "endsumme"
    label: str
    inflows: int
    outflows: int
    balance: int
    #: Verpflichtungsermächtigungen — die Verwaltungslisten weisen sie aus,
    #: die Beschluss-Dateien nicht. Sie zählen NICHT in den Saldo (dieselbe
    #: Regel wie bei den Nachbewilligungen).
    commitment_authorizations: int | None = None


@dataclass
class FhhErgebnis:
    zeilen: list[FhhZeile] = field(default_factory=list)
    summen: list[FhhSumme] = field(default_factory=list)
    eigene_zeile: dict[int, str] = field(default_factory=dict)
    stand: str | None = None

    @property
    def budget_year(self) -> int:
        return min(z.year for z in self.zeilen)


# ----------------------------------------------------------- Spalten aus Linien

@dataclass(frozen=True)
class FhhSpalten:
    """Die gezeichneten Spalten einer FHH-Tabellenseite.

    ``amount`` sind die fünf Betragsspalten als (links, rechts) in
    Leserichtung: Soll laut Entwurf, Einzahlungen, Auszahlungen, VE, neues
    Soll. ``bez`` ist die Bezeichnungs-Spalte, ``erl`` die linke Kante der
    Erläuterungen.
    """

    amount: tuple[tuple[float, float], ...]
    bez: tuple[float, float]
    erl: float


#: Die Kopfwörter der fünf Betragsspalten, in Leserichtung. Geprüft wird, dass
#: jedes in SEINER Spalte steht — das ist die Selbstkontrolle des Aufbaus:
#: Verschöbe sich das Raster um eine Spalte, stünde „VE“ über „neues Soll“.
#: NICHT „Soll“: Das Wort steht in der ERSTEN und der FÜNFTEN Spalte
#: („Soll laut Entwurf“, „neues Soll“) und hätte jede Seite durchfallen
#: lassen, sobald es in der falschen geprüft wurde.
_KOPF_BETRAG = ("laut", "Ein-", "Aus-", "VE", "neues")


#: Wie stark die fünf Betragsspalten in ihrer Breite auseinanderliegen
#: dürfen. Gemessen über den Bestand: 51,8 bis 60,5 pt — die Spalten sind
#: gesetzt, nicht gerechnet, und schwanken um wenige Punkte. 15 pt Spielraum
#: liegen weit über jeder gemessenen Abweichung und weit unter dem Sprung zur
#: Erläuterungs-Spalte (137 bis 211 pt).
_SPALTEN_TOLERANZ = 15


def _spalten(zeilen: list[list[Wort]], senkrecht: list[float]) -> FhhSpalten | None:
    """Die Spalten einer Tabellenseite — oder ``None``, wenn es keine ist.

    Gesucht wird der letzte LAUF von sechs Kanten mit annähernd gleichem
    Abstand: Das sind die fünf Betragsspalten, und die Kante dahinter ist der
    Beginn der Erläuterungen. Die Kante davor öffnet die Bezeichnung.

    Warum nicht am Kopfwort „Erläuterungen“ verankern, wie zuerst gebaut:
    Weil nur die ERSTE Seite eines Blocks den Tabellenkopf wiederholt. In
    256703 tragen zehn von fünfzehn Seiten dasselbe Zwölf-Linien-Raster, aber
    keine Kopfzeile — sie galten damit als „keine Tabellenseite“, und mit
    ihnen fielen alle Auszahlungen des Jahrgangs weg.

    Der Lauf trägt auch dort, wo die Linienzahl schwankt: 286016 zeichnet die
    äußeren Tabellenränder auf den meisten Seiten nicht mit (zehn statt zwölf
    Linien). Die Breite unterscheidet die Spalten zuverlässig — die
    Erläuterungen sind zwei- bis viermal so breit wie eine Betragsspalte, die
    Bezeichnung gut doppelt.
    """
    kanten = sorted(senkrecht)
    if len(kanten) < 7:
        return None
    lauf = None
    for i in range(len(kanten) - 6, -1, -1):
        sechs = kanten[i:i + 6]
        breiten = [b - a for a, b in zip(sechs, sechs[1:])]
        if max(breiten) - min(breiten) <= _SPALTEN_TOLERANZ:
            lauf = (i, sechs)
            break
    if lauf is None:
        return None
    i, sechs = lauf
    if i == 0:
        return None                     # keine Bezeichnungs-Kante davor
    spalten = FhhSpalten(
        amount=tuple(zip(sechs[:-1], sechs[1:])),
        bez=(kanten[i - 1], sechs[0]),
        erl=sechs[-1],
    )
    return spalten if _koepfe_passen(zeilen, spalten) else None


def _koepfe_passen(zeilen: list[list[Wort]], spalten: FhhSpalten) -> bool:
    """Steht jedes Kopfwort über seiner Spalte?

    Die Selbstkontrolle des Aufbaus, und mit Absicht mild: Geprüft wird nur,
    dass jedes GEFUNDENE Kopfwort in seiner Spalte liegt. Auf Kopfwörter zu
    bestehen ginge nicht — nur die erste Seite eines Blocks trägt den Kopf,
    die Folgeseiten wiederholen bloß das Raster. Ein Kopfwort in der
    FALSCHEN Spalte lässt die Seite dagegen sofort durchfallen; genau das
    fängt ein um eine Spalte verschobenes Raster.
    """
    for zeile in zeilen[:18]:
        treffer = [(x0, x1, text) for x0, x1, _y, text in zeile
                   if text in _KOPF_BETRAG]
        # ZWEI Kopfwörter in einer Zeile machen sie zur Kopfzeile. Eines
        # allein tut das nicht: „laut" ist ein gewöhnliches deutsches Wort
        # und stand in 256703 mitten in einer Erläuterung — als Kopfwort
        # gelesen lag es weit rechts seiner Spalte, und die Seite fiel durch.
        # Mit ihr fielen drei Positionen weg, und dem Jahrgang 2023 fehlten
        # 10,8 Mio. € Auszahlungen.
        if len(treffer) < 2:
            continue
        for x0, x1, text in treffer:
            links, rechts = spalten.amount[_KOPF_BETRAG.index(text)]
            if not (links - 2 <= (x0 + x1) / 2 <= rechts + 2):
                return False
    return True


def _wert(text: str) -> int | None:
    """Zellinhalt → Betrag.

    Zwei Schreibweisen, die keine Zahl zu sein scheinen und doch eine sind:

    * Der **Gedankenstrich** ist eine ausdrückliche Null.
    * Ein Betrag in **Klammern** — „(275.900)" als neues Soll in 244466.
      Das ist hier NICHT die kaufmännische Negativ-Notation: Die Zeile
      rechnet 250.000 + 25.900 = 275.900, die Klammern heben den Wert also
      hervor, sie kehren ihn nicht um. Entschieden wird das nicht von dieser
      Funktion, sondern von der Zeilenprobe — läse man das Vorzeichen falsch,
      ginge „Soll + Ein + Aus = neues Soll" nicht auf. Ohne Klammer-Fassung
      fiel die einzige Position des Dokuments samt ihrer 25.900 € weg.
    """
    if text in _STRICH:
        return 0
    nackt = text[1:-1] if text.startswith("(") and text.endswith(")") else text
    return int(nackt.replace(".", "")) if _ZAHL.fullmatch(nackt) else None


def _zelle(zeile: list[Wort], links: float, rechts: float) -> int | None:
    """Der Betrag einer Spalte in dieser Zeile — Beträge sind rechtsbündig."""
    for x0, x1, _y, text in zeile:
        if links < x1 <= rechts + 1 and x0 >= links - 1:
            wert = _wert(text)
            if wert is not None:
                return wert
    return None


# ------------------------------------------------------------------ Positionen

def _ist_position(zeile: list[Wort], spalten: FhhSpalten | None) -> bool:
    """Positionszeilen beginnen mit Lfd. Nr. und Teilhaushalt, ganz links.

    Der Teilhaushalt steht ein- ODER zweistellig: Die meisten Dokumente
    setzen „03", 302945 setzt „8". Auf zwei Ziffern zu bestehen kostete dort
    jede einzelne Position — das Dokument kam als „andere Bauform" zurück,
    obwohl nur die führende Null fehlte.
    """
    return (spalten is not None and len(zeile) >= 3
            and re.fullmatch(r"\d{1,3}", zeile[0][3]) is not None
            and (re.fullmatch(r"\d{1,2}", zeile[1][3]) is not None
                 or zeile[1][3] == "alle")
            and zeile[0][0] < spalten.bez[0])


#: Investitionscodes des Programms: „I10.089904.500“. Sie wickeln über zwei
#: Grundlinien („I10.089904“ / „.500“), die Nachlese in
#: :func:`_fragmente_anbauen` setzt sie wieder zusammen.
_PRODUKT = re.compile(r"[IP]\d[\d.]*")


def _position_lesen(zeile: list[Wort], year: int, spalten: FhhSpalten) -> FhhZeile:
    seq = int(zeile[0][3])
    sub_budget = int(zeile[1][3]) if zeile[1][3] != "alle" else None

    page: str | None = None
    product: str | None = None
    label: list[str] = []
    bez_links, bez_rechts = spalten.bez
    for x0, x1, _y, text in zeile[2:]:
        if x0 >= spalten.amount[0][0] - 1:
            break                       # ab hier beginnen die Beträge
        if bez_links - 1 <= x0 and x1 <= bez_rechts + 1:
            label.append(text)
        elif _PRODUKT.fullmatch(text) or text.startswith("."):
            product = (product or "") + text if product else text
        elif page is None:
            page = text                # „92“, „neu“ — beides kommt vor

    # Die BETRÄGE stehen hier bewusst noch nicht: Ein Teil der Dokumente
    # setzt sie auf eigene Grundlinien neben der Positionszeile (210923: die
    # Zeile trägt nur Nummern, Code und Namen, die Spalten 340–599 sind auf
    # ihrer Grundlinie leer). Sie kommen deshalb aus dem ZEILENBAND —
    # dieselbe Geometrie, die schon Erläuterung und Urheber zuordnet.
    return FhhZeile(
        year=year, seq=seq, sub_budget=sub_budget, page_draft=page, product=product,
        label=" ".join(label),
        planned_draft=None, inflow=None, outflow=None,
        commitment_authorizations=None, planned_new=None,
    )


def _bezeichnungsfragment(zeile: list[Wort], spalten: FhhSpalten) -> str | None:
    """Der Bezeichnungs-Anteil einer Wickelzeile — oder ``None``.

    Wie beim EHH, nur mit gezeichneten Kanten statt geschätzten: Was in der
    Bezeichnungs-Spalte steht, gehört zum Namen; was links davon steht, macht
    die Zeile zu einer Nummern- oder Kopfzeile; ein Betrag in einer der fünf
    Betragsspalten macht sie zu einer verrutschten Positionszeile.
    """
    links, rechts = spalten.bez
    part = [w for w in zeile if links - 1 <= w[0] and w[1] <= rechts + 1]
    if not part:
        return None
    if any(w[1] < links - 1 for w in zeile):
        return None
    if any(_zelle([w], *spalten.amount[i]) is not None
           for w in zeile for i in range(5)):
        return None
    return " ".join(w[3] for w in part)


def _produktfragment(zeile: list[Wort], spalten: FhhSpalten) -> str | None:
    """Der abgerissene Schwanz eines Investitionscodes („.500“)."""
    bez_links = spalten.bez[0]
    part = [w for w in zeile if w[1] <= bez_links and w[3].startswith(".")
            and re.fullmatch(r"\.\d+", w[3])]
    return part[0][3] if len(part) == 1 else None


# ------------------------------------------------------------- Zusammenstellung

_ENTWURF = re.compile(r"Verw(?:altungs|\.\-)?[Ee]ntwurf", re.I)
_LISTE = re.compile(r"Änderungs?liste", re.I)
#: „Änderungen 2026“ (die meisten) oder „Veränderungen 2019“ (196998) —
#: beide Schreibweisen führen dieselbe Spaltengruppe an.
_BLOCK_JAHR = re.compile(r"(?:Ver)?[Ää]nderungen\s+(20\d\d)")
_JAHR_MARKER = _BLOCK_JAHR
_STAND = re.compile(r"Stand:\s*(\d{1,2}\.\d{1,2}\.\d{2,4})")
#: Die Saldo-Spalte heißt nicht überall gleich (s. Modulkopf).
_SALDO_KOPF = re.compile(r"Saldo|Verschlechterung")


@dataclass(frozen=True)
class SummenSpalten:
    """Die Spalten einer Zusammenstellungs-Seite, aus ihren Kopfwörtern.

    Anders als bei den Positionen gibt es hier KEIN Linienraster — die
    Zusammenstellung ist gesetzt, nicht gezeichnet. Die Beträge sind aber
    rechtsbündig unter ihren Köpfen, und das reicht: Jeder Betrag gehört zu
    dem Kopf, dessen rechte Kante seiner eigenen am nächsten liegt.

    Warum überhaupt nach Spalten und nicht einfach „die ersten drei Zahlen
    der Zeile": Weil Zeilen ohne Spaltenbezug mitgelesen würden. Die
    Überschrift „Finanzhaushalt 2019 - 2022" von 196998 ergibt mit dem
    Gedankenstrich als Null exakt drei Beträge (2019, 0, 2022) und bestand
    als Zusammenstellungs-Zeile jede Zählprüfung — bis auf ihre eigene
    Rechenprobe, an der sie den ganzen Jahrgang mitgerissen hat.
    """

    ein: float
    aus: float
    balance: float
    commitment_authorizations: float | None


#: Wie weit die rechte Kante eines Betrags von der ihres Kopfworts abweichen
#: darf. Gemessen 1–23 pt: Die Köpfe „Saldo" und „VE" sind kürzer als ihre
#: Spalte und stehen zentriert, „Einzahlungen"/„Auszahlungen" füllen sie fast.
_KOPF_TOLERANZ = 35


def _summen_spalten(zeilen: list[list[Wort]]) -> SummenSpalten | None:
    """Die Kopfwörter der Zusammenstellung → ihre rechten Kanten."""
    kanten: dict[str, float] = {}
    for zeile in zeilen[:14]:
        for _x0, x1, _y, text in zeile:
            if text == "Einzahlungen":
                kanten.setdefault("ein", x1)
            elif text == "Auszahlungen":
                kanten.setdefault("aus", x1)
            elif _SALDO_KOPF.fullmatch(text):
                kanten.setdefault("balance", x1)
            elif text == "VE":
                kanten.setdefault("commitment_authorizations", x1)
    if not {"ein", "aus", "balance"} <= kanten.keys():
        return None
    return SummenSpalten(kanten["ein"], kanten["aus"], kanten["balance"],
                         kanten.get("commitment_authorizations"))


def _summen_zellen(zeile: list[Wort], spalten: SummenSpalten,
                   ) -> tuple[dict[str, int], float, float] | None:
    """Die Beträge einer Zeile ihren Spalten zuordnen.

    Gibt ``None`` zurück, sobald etwas nicht stimmt: ein Betrag ohne Spalte,
    zwei Beträge in derselben Spalte, oder eine der drei Pflichtspalten leer.
    Das ist die Eintrittskarte — was hier durchfällt, ist keine
    Zusammenstellungs-Zeile.
    """
    felder = {"ein": spalten.ein, "aus": spalten.aus, "balance": spalten.balance}
    if spalten.commitment_authorizations is not None:
        felder["commitment_authorizations"] = spalten.commitment_authorizations
    zellen: dict[str, int] = {}
    erster = letzter = None
    for x0, x1, _y, text in zeile:
        wert = _wert(text)
        if wert is None:
            continue
        name, abstand = min(((n, abs(x1 - k)) for n, k in felder.items()),
                            key=lambda p: p[1])
        if abstand > _KOPF_TOLERANZ:
            return None
        if name in zellen:
            return None
        zellen[name] = wert
        erster = x0 if erster is None else min(erster, x0)
        letzter = x1 if letzter is None else max(letzter, x1)
    if not {"ein", "aus", "balance"} <= zellen.keys():
        return None
    return zellen, erster, letzter


def _summen_zeile(year: int, typ: str, zeile: list[Wort],
                  zellen: dict[str, int], erster: float, letzter: float) -> FhhSumme:
    """Eine Zusammenstellungs-Zeile lesen — und sofort beweisen.

    Die Zeilenprobe läuft HIER, nicht später: Eine Zeile, die ihren eigenen
    Saldo nicht trägt, ist ein Lesefehler — und dann soll das Dokument
    fallen, nicht die Zeile.
    """
    ein, aus, balance = zellen["ein"], zellen["aus"], zellen["balance"]
    if abs(ein - aus - balance) > 2:
        raise ListenFehler(
            f"Zeilenprobe {year}: {ein:,} − {aus:,} ≠ {balance:,} "
            f"in „{' '.join(w[3] for w in zeile)[:70]}“")
    # Links des ersten Betrags steht die Beschriftung, rechts des letzten der
    # Urheber („Vorschlag von" — nur die Beschluss-Dateien führen ihn).
    label = " ".join(w[3] for w in zeile if w[1] <= erster).strip()
    author = " ".join(w[3] for w in zeile if w[0] >= letzter).strip()
    return FhhSumme(year=year, typ=typ, label=(label or author or "liste"),
                    inflows=ein, outflows=aus, balance=balance,
                    commitment_authorizations=zellen.get("commitment_authorizations"))


def _block_jahr(block_jahr: int | None, aus: FhhErgebnis, typ: str) -> int:
    """Das Planjahr eines Blocks — wie beim EHH aus der Reihenfolge, wenn die
    Überschrift fehlt: Jeder Block beginnt mit seinem Verwaltungsentwurf."""
    if block_jahr is not None:
        return block_jahr
    years = sorted({z.year for z in aus.zeilen})
    entwuerfe = sum(1 for s in aus.summen if s.typ == "entwurf")
    idx = entwuerfe if typ == "entwurf" else entwuerfe - 1
    if 0 <= idx < len(years):
        return years[idx]
    raise ListenFehler("Zusammenstellungs-Block ohne erkennbares Planjahr.")


# ------------------------------------------------------------------- Der Leser

def parse_fhh_seiten(seiten: list[list[Wort]],
                     linien: list[Linien]) -> FhhErgebnis:
    """Die Seiten einer FHH-Änderungsliste → geprüfte Zeilen.

    ``linien`` ist hier PFLICHT, anders als beim EHH: Die fünf Betragsspalten
    kommen aus dem Raster, ohne das gibt es keine Zuordnung. Wirft
    :class:`ListenFehler`, sobald eine Probe nicht aufgeht.
    """
    aus = FhhErgebnis()
    if seiten and (m := _STAND.search(" ".join(w[3] for w in seiten[0]))):
        aus.stand = m.group(1)

    # Das Planjahr gilt über Seitengrenzen hinweg: Ein Block beginnt mit
    # seiner Überschrift („Änderungen 2023") und läuft über so viele Seiten,
    # wie er braucht — die Folgeseiten wiederholen das Linienraster, aber
    # nicht die Überschrift. In 256703 trug nur jede vierte Tabellenseite ein
    # Jahr; die übrigen fielen samt ihrer Positionen weg, und dem Jahrgang
    # 2023 fehlten am Ende alle 11,2 Mio. € Auszahlungen.
    #
    # Der Merker gilt AUSDRÜCKLICH NUR für Tabellenseiten. Die
    # Zusammenstellung bekommt ihr Jahr weiter aus ihrem eigenen Block
    # (:func:`_block_jahr`) — ein dokumentweiter Merker hat beim EHH schon
    # einmal alle vier Blöcke auf dasselbe Planjahr fallen lassen (303358).
    jahr_merker: int | None = None

    for nr, woerter in enumerate(seiten):
        zeilen = zeilen_bilden(woerter)
        senkrecht = linien[nr][1] if nr < len(linien) else []
        spalten = _spalten(zeilen, senkrecht)
        seitentext = " ".join(w[3] for w in woerter)
        marker = _JAHR_MARKER.search(seitentext)
        if marker:
            jahr_merker = int(marker.group(1))
        year = jahr_merker if spalten is not None else None
        # Zusammenstellungs-Seiten setzen ihre Köpfe als GANZE Wörter
        # („Einzahlungen"); die Tabellenseiten brechen sie um („Ein-" /
        # „zahlungen"). Das unterscheidet die beiden Seitenarten von selbst.
        summen_spalten = None if spalten is not None else _summen_spalten(zeilen)

        block_jahr: int | None = None
        positionen: list[tuple[float, FhhZeile]] = []
        fragmente: list[tuple[float, str]] = []
        for zeile in zeilen:
            text = " ".join(w[3] for w in zeile)
            if (b := _BLOCK_JAHR.search(text)):
                block_jahr = int(b.group(1))
            elif spalten is None and re.fullmatch(r"20\d\d", text.strip()):
                block_jahr = int(text.strip())

            if spalten is not None and year is not None:
                if _ist_position(zeile, spalten):
                    position = _position_lesen(zeile, year, spalten)
                    aus.zeilen.append(position)
                    positionen.append((zeile[0][2], position))
                    continue
                if (frag := _bezeichnungsfragment(zeile, spalten)):
                    fragmente.append((zeile[0][2], frag))
                    continue
                if (schwanz := _produktfragment(zeile, spalten)):
                    _produkt_anbauen(positionen, zeile[0][2], schwanz)
                    continue

            if summen_spalten is None:
                continue
            gelesen = _summen_zellen(zeile, summen_spalten)
            if gelesen is None:
                continue
            zellen, erster, letzter = gelesen
            links_text = " ".join(w[3] for w in zeile if w[1] <= erster).strip()
            rechts_text = " ".join(w[3] for w in zeile if w[0] >= letzter).strip()
            if _ENTWURF.search(text):
                typ = "entwurf"
            elif _LISTE.search(text):
                typ = "liste"
            elif links_text or rechts_text:
                # Eine Zeile mit eigener Beschriftung, aber ohne Stichwort:
                # die politische Liste der Beschluss-Dateien. Ihr Label steht
                # RECHTS der Beträge, in der Spalte „Vorschlag von" — nur
                # links zu suchen machte sie zur zweiten Endsumme, und die
                # Zusammenstellung meldete „1×Entwurf, 1×Liste, 2×Endsumme".
                typ = "liste"
            else:
                # Nackte Zahlenreihe ohne jede Beschriftung — die Summe unter
                # dem Block. Die Beschluss-Dateien setzen sie ohne
                # „Überschuss/Fehlbedarf" davor, anders als der EHH.
                typ = "endsumme"
            aus.summen.append(_summen_zeile(
                _block_jahr(block_jahr, aus, typ), typ, zeile, zellen, erster, letzter))

        _fragmente_anbauen(positionen, fragmente)
        if spalten is not None and nr < len(linien):
            _betraege_anbauen(positionen, zeilen, spalten, linien[nr])
            _texte_anbauen(positionen, zeilen, spalten, linien[nr])

    aus.zeilen = _doppelzeilen_falten(aus.zeilen)
    if not aus.zeilen:
        raise ListenFehler("Keine Positionszeilen gefunden — andere Bauform?")
    if not aus.summen:
        raise ListenFehler("Keine Zusammenstellung gefunden — ohne sie keine Probe.")
    _proben(aus)
    return aus


def _doppelzeilen_falten(zeilen: list[FhhZeile]) -> list[FhhZeile]:
    """Dieselbe Position, zweimal gedruckt — zu EINER zusammenziehen.

    Der Bestand führt Positionen, die über zwei Tabellenzeilen laufen: gleiche
    Lfd. Nr., gleicher Teilhaushalt, gleicher Investitionscode, gleicher Name
    — aber zwei Erläuterungsblöcke, von denen nur der erste Beträge trägt
    (210923, Position 3: „Einrichtung eines Sonderfonds …" und darunter
    „Haushaltsvermerk: …"). Als zwei Positionen gelesen zählte die zweite als
    betragslos mit, und der Datenbank-Schlüssel (Jahrgang, Liste, Jahr, Lfd.)
    hätte sie ohnehin nicht beide gehalten.

    Verschmolzen wird nur, was sich nicht widerspricht: Tragen beide Zeilen
    in derselben Spalte VERSCHIEDENE Beträge, ist das kein Umbruch, sondern
    ein Lesefehler — dann fällt das Dokument, statt sich eine Zahl
    auszusuchen.
    """
    aus: dict[tuple[int, int], FhhZeile] = {}
    for z in zeilen:
        schluessel = (z.year, z.seq)
        erste = aus.get(schluessel)
        if erste is None:
            aus[schluessel] = z
            continue
        for spaltenname in ("planned_draft", "inflow", "outflow",
                            "commitment_authorizations", "planned_new"):
            alt_wert, neu_wert = getattr(erste, spaltenname), getattr(z, spaltenname)
            if neu_wert is None:
                continue
            if alt_wert is not None and alt_wert != neu_wert:
                raise ListenFehler(
                    f"Position {z.year}/seq {z.seq} steht zweimal mit "
                    f"verschiedenem {spaltenname}: {alt_wert:,} und {neu_wert:,}.")
            setattr(erste, spaltenname, neu_wert)
        for spaltenname in ("explanation", "label", "author"):
            alt_text, neu_text = getattr(erste, spaltenname), getattr(z, spaltenname)
            if neu_text and neu_text != alt_text:
                setattr(erste, spaltenname, f"{alt_text} {neu_text}".strip()
                        if alt_text else neu_text)
    return list(aus.values())


def _produkt_anbauen(positionen: list[tuple[float, FhhZeile]], y: float,
                     schwanz: str) -> None:
    """Den abgerissenen Code-Schwanz seiner Position zuschlagen — eindeutig
    oder gar nicht (dieselbe Regel wie bei den Bezeichnungs-Fragmenten)."""
    if not positionen:
        return
    sortiert = sorted(positionen, key=lambda p: abs(p[0] - y))
    if abs(sortiert[0][0] - y) > 13:
        return
    if len(sortiert) > 1 and abs(sortiert[1][0] - y) < 2 * abs(sortiert[0][0] - y):
        return
    ziel = sortiert[0][1]
    if ziel.product and not ziel.product.endswith(schwanz):
        ziel.product += schwanz


def _fragmente_anbauen(positionen: list[tuple[float, FhhZeile]],
                       fragmente: list[tuple[float, str]]) -> None:
    """Übergelaufene Bezeichnungs-Zeilen — Regel wie beim EHH: eindeutig
    oder liegen lassen."""
    if not positionen or not fragmente:
        return
    anbau: dict[int, list[tuple[float, str]]] = {}
    for fy, ftext in fragmente:
        sortiert = sorted(positionen, key=lambda p: abs(p[0] - fy))
        if abs(sortiert[0][0] - fy) > 13:
            continue
        if len(sortiert) > 1 and abs(sortiert[1][0] - fy) < 2 * abs(sortiert[0][0] - fy):
            continue
        anbau.setdefault(id(sortiert[0][1]), []).append((fy, ftext))
    for py, position in positionen:
        teile = anbau.get(id(position))
        if not teile:
            continue
        alle = sorted(teile + [(py, position.label)])
        position.label = " ".join(t for _, t in alle if t)


#: Der Index der Spalte „neues Soll" in :attr:`FhhSpalten.amount`.
_SOLL_NEU = 4


def _betragszeilen(zeilen: list[list[Wort]], spalten: FhhSpalten,
                   boden: float) -> list[tuple[float, dict[int, int]]]:
    """Die Betragszeilen einer Seite: je Grundlinie, was in welcher Spalte steht.

    „Betragszeile" heißt: eine Grundlinie mit einem Betrag in der Spalte
    **neues Soll** und in mindestens einer weiteren. Das „neues Soll" ist der
    entscheidende Teil der Bedingung, nicht die Anzahl:

    Unter der letzten Position jedes Blocks steht dessen SUMMENZEILE, noch
    innerhalb des Tabellenrahmens (300530, Seite 4: „−34.800 | 1.018.472"
    bei y = 499, direkt unter Position 12). Sie füllt zwei bis drei Spalten
    und sah damit aus wie eine Positionszeile — als solche gezählt gab es
    eine Betragszeile mehr als Positionen, die Zuordnung über die
    Reihenfolge fiel auf ihren Notweg zurück, und der schlug die Summe der
    LETZTEN Position zu. Ergebnis: jeder Betrag doppelt.

    Eine Summenzeile trägt kein „neues Soll" — sie summiert Änderungen, sie
    schreibt keinen Ansatz fort. Jede echte Positionszeile des Bestands
    trägt es dagegen. Damit trennt eine Spalte, was eine Zählung nicht
    trennen konnte.
    """
    aus: list[tuple[float, dict[int, int]]] = []
    for zeile in zeilen:
        if zeile[0][2] >= boden:
            continue
        zellen: dict[int, int] = {}
        mehrdeutig = set()
        for w in zeile:
            for i, (links, rechts) in enumerate(spalten.amount):
                if not (links < w[1] <= rechts + 1 and w[0] >= links - 1):
                    continue
                wert = _wert(w[3])
                if wert is None:
                    continue
                if i in zellen:
                    mehrdeutig.add(i)
                zellen[i] = wert
        for i in mehrdeutig:
            zellen.pop(i, None)
        if len(zellen) >= 2 and _SOLL_NEU in zellen:
            aus.append((zeile[0][2], zellen))
    return aus


def _betraege_anbauen(positionen: list[tuple[float, FhhZeile]],
                      zeilen: list[list[Wort]], spalten: FhhSpalten,
                      linien: Linien) -> None:
    """Die fünf Betragsspalten ihren Positionen zuschlagen.

    DAS MODELL: Eine Position besitzt ihre Grundlinie und alles darunter bis
    zur nächsten Position — ihre Tabellenzeile eben. Die Beträge stehen
    irgendwo darin, und wo genau, ist Sache des Dokuments: 243618 setzt sie
    exakt auf die Grundlinie, 210923 setzt sie 44 bis 67 pt darunter (dort
    liegt jeder Betrag NÄHER an der folgenden Position als an der eigenen).
    Beide Lagen fallen in dieselbe Zeile, also braucht es keine Fallregel für
    beide — und kein Abstandsfenster, das für das eine Dokument zu eng und
    für das andere zu weit wäre.

    Drei Dinge liegen damit von selbst draußen, und jedes davon hat vorher
    einen Riss verursacht:

    * Der **Tabellenkopf** — über der ersten Position, also in keiner Zeile.
      Sein „+ / −“ über jeder Spalte ist ein Gedankenstrich und damit nach
      den Regeln dieses Moduls ein Betrag (Null); er machte jede Spalte
      mehrdeutig, in der er stand.
    * Die **Fußzeile** — unter dem Tabellenrahmen. „Seite 3“ setzt seine
      Ziffer in die Auszahlungs-Spalte: „452.200 + 3 + 425.300 ≠ 877.500“.
    * Die **Summenzeile des Blocks** — sie steht zwar noch im Rahmen und in
      der Zeile der letzten Position, trägt aber kein „neues Soll“ und wird
      schon von :func:`_betragszeilen` aussortiert.
    """
    if not positionen:
        return
    waagerecht, _senkrecht = linien
    letzte = max(py for py, _pos in positionen)
    # Die unterste waagerechte Linie ist NUR dann der Tabellenboden, wenn sie
    # unter der letzten Position liegt. Ein Teil des Bestands zeichnet den
    # unteren Rahmen gar nicht (244161: letzte Linie bei y = 158, die einzige
    # Position steht bei y = 189) — dort war „der Boden" plötzlich eine
    # Kopflinie, und ALLE Beträge lagen darunter, also draußen.
    #
    # Ohne Boden fällt die Fußzeile trotzdem nicht herein: „Seite 3" füllt
    # eine einzige Spalte und kein „neues Soll", und daran scheitert sie
    # schon in :func:`_betragszeilen`.
    boden = max(waagerecht) if waagerecht and max(waagerecht) > letzte else float("inf")

    # Doppelt gedruckte Positionen (gleiche Lfd. Nr., zwei Erläuterungs-
    # blöcke) besitzen EINE Zeile, nicht zwei.
    sortiert: list[tuple[float, FhhZeile]] = []
    for py, position in sorted(positionen, key=lambda p: p[0]):
        if sortiert and sortiert[-1][1].seq == position.seq:
            continue
        sortiert.append((py, position))

    spannen = [(py, pos, sortiert[i + 1][0] if i + 1 < len(sortiert) else boden)
               for i, (py, pos) in enumerate(sortiert)]

    for y, zellen in _betragszeilen(zeilen, spalten, boden):
        for oben, position, unten in spannen:
            if oben - 2 <= y < unten:
                (position.planned_draft, position.inflow,
                 position.outflow, position.commitment_authorizations, position.planned_new) = (
                    zellen.get(i) for i in range(5))
                break


def _texte_anbauen(positionen: list[tuple[float, FhhZeile]],
                   zeilen: list[list[Wort]], spalten: FhhSpalten,
                   linien: Linien) -> None:
    """Erläuterung und Urheber ihren Positionen zuschlagen — über die
    Zeilenbänder der waagerechten Linien, wie beim EHH."""
    waagerecht, senkrecht = linien
    if not positionen or len(waagerecht) < 2:
        return
    # Rechts der Erläuterungen kann noch eine Urheber-Spalte stehen; ihre
    # Kante ist die letzte senkrechte Linie rechts der Erläuterungs-Kante,
    # sofern dahinter nur noch der Blattrand kommt.
    rechts_davon = sorted(x for x in senkrecht if x > spalten.erl + 20)
    urheber_links = rechts_davon[0] if len(rechts_davon) == 2 else None

    erl_baender: dict[int, list[Wort]] = {}
    urh_baender: dict[int, list[Wort]] = {}
    for zeile in zeilen:
        for w in zeile:
            if w[0] < spalten.erl - 1:
                continue
            b = band(waagerecht, w[2])
            if b is None:
                continue
            ziel = (urh_baender if urheber_links is not None and w[0] >= urheber_links - 1
                    else erl_baender)
            ziel.setdefault(b, []).append(w)

    for py, position in positionen:
        b = band(waagerecht, py)
        if b is None:
            continue
        if sum(1 for qy, _ in positionen if band(waagerecht, qy) == b) > 1:
            continue
        if (woerter := sorted(erl_baender.get(b, []), key=lambda w: (w[2], w[0]))):
            position.explanation = zeilen_falten(zeilen_bilden(woerter))
        if (woerter := sorted(urh_baender.get(b, []), key=lambda w: (w[2], w[0]))):
            position.author = " ".join(
                " ".join(w[3] for w in z) for z in zeilen_bilden(woerter))


# ------------------------------------------------------------------- Die Proben

def _proben(aus: FhhErgebnis) -> None:
    """Vier Proben, und die erste hat der EHH nicht.

    1. **Zeilenprobe je Position**: Soll + Ein + Aus = neues Soll. Sie läuft
       auf jeder Zeile, die alle vier Werte trägt.
    2. **Zeilenprobe je Summenzeile**: lief schon beim Lesen.
    3. **Kettenprobe je Planjahr**: Entwurf + alle Listen = Endsumme.
    4. **Positionsprobe je Planjahr**: Die Summe der Positionen trifft genau
       eine Zusammenstellungs-Zeile.
    """
    voll = [z for z in aus.zeilen
            if None not in (z.planned_draft, z.inflow, z.outflow, z.planned_new)]
    schief = [z for z in voll
              if abs((z.planned_draft or 0) + (z.inflow or 0)
                     + (z.outflow or 0) - (z.planned_new or 0)) > 2]
    if schief:
        z = schief[0]
        raise ListenFehler(
            f"Zeilenprobe {z.year}/seq {z.seq}: {z.planned_draft:,} + "
            f"{z.inflow:,} + {z.outflow:,} ≠ {z.planned_new:,} "
            f"({len(schief)} von {len(voll)} Zeilen betroffen)")

    for year in sorted({z.year for z in aus.zeilen}):
        entwurf = [s for s in aus.summen if s.year == year and s.typ == "entwurf"]
        listen = [s for s in aus.summen if s.year == year and s.typ == "liste"]
        ende = [s for s in aus.summen if s.year == year and s.typ == "endsumme"]
        # Die Endsumme ist OPTIONAL, anders als beim EHH: Die
        # FHH-Beschluss-Dateien führen je Block nur den Entwurf und die
        # Listen und verzichten auf die Schlusszeile (303359, 230016/230178).
        # Ihre Gesamtübersicht steht stattdessen auf einer eigenen Seite.
        # Entwurf und Endsumme sind BEIDE optional, anders als beim EHH. Die
        # Beschluss-Dateien führen je Block nur die Listen: 212802 überschreibt
        # seine Seite ausdrücklich mit „Übersicht aller Änderungen“ und nennt
        # weder den Entwurf noch eine Schlusszeile — es zeigt, was geändert
        # wurde, nicht wovon aus. Nur die Listen sind Pflicht; ohne sie gibt
        # es nichts, woran sich die Positionen messen ließen.
        if len(entwurf) > 1 or len(ende) > 1 or not listen:
            raise ListenFehler(
                f"Zusammenstellung {year}: erwartet höchstens 1×Entwurf, "
                f"≥1×Liste, höchstens 1×Endsumme — gefunden "
                f"{len(entwurf)}/{len(listen)}/{len(ende)}.")

        toleranz = 2 * (len(listen) + 1)
        # Die Kette lässt sich nur prüfen, wo Entwurf UND Endsumme stehen.
        # Fehlt eines von beiden, bleiben die Listen selbst die Referenz der
        # Positionsprobe — bei den kumulierten Dateien ihre Summe („alle“).
        kette_ok = not (entwurf and ende) or all(
            abs(getattr(entwurf[0], field) + sum(getattr(s, field) for s in listen)
                - getattr(ende[0], field)) <= toleranz
            for field in ("inflows", "outflows"))

        pos_e = sum(z.inflow or 0 for z in aus.zeilen if z.year == year)
        pos_a = sum(z.outflow or 0 for z in aus.zeilen if z.year == year)
        if kette_ok:
            ziele = [(s.label, s.inflows, s.outflows) for s in listen]
            if len(listen) > 1:
                ziele.append(("alle", sum(s.inflows for s in listen),
                              sum(s.outflows for s in listen)))
        else:
            ziele = [("beschlossen",
                      ende[0].inflows - entwurf[0].inflows,
                      ende[0].outflows - entwurf[0].outflows)] if ende and entwurf else []
        treffer = [label for label, e, a in ziele
                   if abs(e - pos_e) <= toleranz and abs(a - pos_a) <= toleranz]
        if len(treffer) != 1:
            raise ListenFehler(
                f"Positionsprobe {year}: Die Positionen summieren auf "
                f"{pos_e:,} / {pos_a:,} — "
                + ("keine Zusammenstellungs-Zeile trifft das" if not treffer
                   else "mehrere Zeilen träfen das")
                + ": " + "; ".join(f"{lab}: {e:,}/{a:,}" for lab, e, a in ziele))
        aus.eigene_zeile[year] = treffer[0]


def lies_fhh_liste(pdf_bytes: bytes) -> FhhErgebnis:
    """PDF → geprüfte FHH-Änderungsliste. Wirft :class:`ListenFehler`."""
    return parse_fhh_seiten(seiten_woerter(pdf_bytes), seiten_linien(pdf_bytes))


def herkunft_fuer(label: str, url: str | None, document_id: int) -> Herkunft:
    return Herkunft(
        art="ris",
        probe=("aenderungsliste_fhh_zeilen", "aenderungsliste_summen",
               "aenderungsliste_positionen"),
        label=label,
        url=url or f"https://buergerinfo.oldenburg.de/getfile.php?id={document_id}&type=do",
        document_id=document_id,
    )
