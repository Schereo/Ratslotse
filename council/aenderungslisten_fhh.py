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

    jahr: int
    lfd: int
    thh: int | None
    seite_entwurf: str | None   # auch „neu“ — dann steht die Zeile nicht im Entwurf
    produkt: str | None         # Investitionscode, z. B. „I10.089904.500“
    bezeichnung: str
    #: Die fünf Betragsspalten. ``None`` = Zelle leer, ``0`` = Strich.
    soll_entwurf: int | None
    einzahlung: int | None
    auszahlung: int | None
    ve: int | None
    soll_neu: int | None
    erlaeuterung: str | None = None
    urheber: str | None = None


@dataclass
class FhhSumme:
    """Eine Zeile der Zusammenstellung: Entwurf, eine Liste oder die Endsumme."""

    jahr: int
    typ: str  # "entwurf" | "liste" | "endsumme"
    label: str
    einzahlungen: int
    auszahlungen: int
    saldo: int
    #: Verpflichtungsermächtigungen — die Verwaltungslisten weisen sie aus,
    #: die Beschluss-Dateien nicht. Sie zählen NICHT in den Saldo (dieselbe
    #: Regel wie bei den Nachbewilligungen).
    ve: int | None = None


@dataclass
class FhhErgebnis:
    zeilen: list[FhhZeile] = field(default_factory=list)
    summen: list[FhhSumme] = field(default_factory=list)
    eigene_zeile: dict[int, str] = field(default_factory=dict)
    stand: str | None = None

    @property
    def jahrgang(self) -> int:
        return min(z.jahr for z in self.zeilen)


# ----------------------------------------------------------- Spalten aus Linien

@dataclass(frozen=True)
class FhhSpalten:
    """Die gezeichneten Spalten einer FHH-Tabellenseite.

    ``betrag`` sind die fünf Betragsspalten als (links, rechts) in
    Leserichtung: Soll laut Entwurf, Einzahlungen, Auszahlungen, VE, neues
    Soll. ``bez`` ist die Bezeichnungs-Spalte, ``erl`` die linke Kante der
    Erläuterungen.
    """

    betrag: tuple[tuple[float, float], ...]
    bez: tuple[float, float]
    erl: float


#: Die Kopfwörter der fünf Betragsspalten, in Leserichtung. Geprüft wird, dass
#: jedes in SEINER Spalte steht — das ist die Selbstkontrolle des Aufbaus:
#: Verschöbe sich das Raster um eine Spalte, stünde „VE“ über „neues Soll“.
#: NICHT „Soll“: Das Wort steht in der ERSTEN und der FÜNFTEN Spalte
#: („Soll laut Entwurf“, „neues Soll“) und hätte jede Seite durchfallen
#: lassen, sobald es in der falschen geprüft wurde.
_KOPF_BETRAG = ("laut", "Ein-", "Aus-", "VE", "neues")


def _spalten(zeilen: list[list[Wort]], senkrecht: list[float]) -> FhhSpalten | None:
    """Die Spalten einer Tabellenseite — oder ``None``, wenn es keine ist.

    Verankert an der Erläuterungs-Spalte: Ihre linke Kante ist die letzte
    senkrechte Linie vor dem Kopfwort „Erläuterungen“, und die fünf
    Betragsspalten sind die fünf Intervalle davor. Verlangt werden also
    sieben Kanten — nicht zwölf: Die äußeren Tabellenränder fehlen in 286016
    auf den meisten Seiten, die inneren Kanten stehen dort trotzdem alle.
    """
    erl_kopf = None
    for zeile in zeilen[:18]:
        for x0, _x1, _y, text in zeile:
            if text == "Erläuterungen" and erl_kopf is None:
                erl_kopf = x0
    if erl_kopf is None:
        return None
    links = sorted(x for x in senkrecht if x < erl_kopf)
    if len(links) < 7:
        return None
    kanten = links[-6:]
    spalten = FhhSpalten(
        betrag=tuple(zip(kanten[:-1], kanten[1:])),
        bez=(links[-7], kanten[0]),
        erl=kanten[-1],
    )
    return spalten if _koepfe_passen(zeilen, spalten) else None


def _koepfe_passen(zeilen: list[list[Wort]], spalten: FhhSpalten) -> bool:
    """Steht jedes Kopfwort über seiner Spalte?

    Die Selbstkontrolle des Aufbaus. Sie ist mit Absicht mild — geprüft wird
    nur, dass jedes gefundene Kopfwort IN seiner Spalte liegt, nicht dass
    alle fünf vorhanden sind: „VE“ steht in manchen Jahrgängen nur auf der
    ersten Seite eines Blocks. Ein Kopfwort in der FALSCHEN Spalte lässt die
    Seite dagegen sofort durchfallen.
    """
    gefunden = 0
    for zeile in zeilen[:18]:
        for x0, x1, _y, text in zeile:
            if text not in _KOPF_BETRAG:
                continue
            i = _KOPF_BETRAG.index(text)
            links, rechts = spalten.betrag[i]
            mitte = (x0 + x1) / 2
            if not (links - 2 <= mitte <= rechts + 2):
                return False
            gefunden += 1
    return gefunden >= 2


def _wert(text: str) -> int | None:
    """Zellinhalt → Betrag. Der Gedankenstrich ist eine ausdrückliche Null."""
    if text in _STRICH:
        return 0
    return int(text.replace(".", "")) if _ZAHL.fullmatch(text) else None


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


def _position_lesen(zeile: list[Wort], jahr: int, spalten: FhhSpalten) -> FhhZeile:
    lfd = int(zeile[0][3])
    thh = int(zeile[1][3]) if zeile[1][3] != "alle" else None

    seite: str | None = None
    produkt: str | None = None
    bezeichnung: list[str] = []
    bez_links, bez_rechts = spalten.bez
    for x0, x1, _y, text in zeile[2:]:
        if x0 >= spalten.betrag[0][0] - 1:
            break                       # ab hier beginnen die Beträge
        if bez_links - 1 <= x0 and x1 <= bez_rechts + 1:
            bezeichnung.append(text)
        elif _PRODUKT.fullmatch(text) or text.startswith("."):
            produkt = (produkt or "") + text if produkt else text
        elif seite is None:
            seite = text                # „92“, „neu“ — beides kommt vor

    # Die BETRÄGE stehen hier bewusst noch nicht: Ein Teil der Dokumente
    # setzt sie auf eigene Grundlinien neben der Positionszeile (210923: die
    # Zeile trägt nur Nummern, Code und Namen, die Spalten 340–599 sind auf
    # ihrer Grundlinie leer). Sie kommen deshalb aus dem ZEILENBAND —
    # dieselbe Geometrie, die schon Erläuterung und Urheber zuordnet.
    return FhhZeile(
        jahr=jahr, lfd=lfd, thh=thh, seite_entwurf=seite, produkt=produkt,
        bezeichnung=" ".join(bezeichnung),
        soll_entwurf=None, einzahlung=None, auszahlung=None,
        ve=None, soll_neu=None,
    )


def _bezeichnungsfragment(zeile: list[Wort], spalten: FhhSpalten) -> str | None:
    """Der Bezeichnungs-Anteil einer Wickelzeile — oder ``None``.

    Wie beim EHH, nur mit gezeichneten Kanten statt geschätzten: Was in der
    Bezeichnungs-Spalte steht, gehört zum Namen; was links davon steht, macht
    die Zeile zu einer Nummern- oder Kopfzeile; ein Betrag in einer der fünf
    Betragsspalten macht sie zu einer verrutschten Positionszeile.
    """
    links, rechts = spalten.bez
    teil = [w for w in zeile if links - 1 <= w[0] and w[1] <= rechts + 1]
    if not teil:
        return None
    if any(w[1] < links - 1 for w in zeile):
        return None
    if any(_zelle([w], *spalten.betrag[i]) is not None
           for w in zeile for i in range(5)):
        return None
    return " ".join(w[3] for w in teil)


def _produktfragment(zeile: list[Wort], spalten: FhhSpalten) -> str | None:
    """Der abgerissene Schwanz eines Investitionscodes („.500“)."""
    bez_links = spalten.bez[0]
    teil = [w for w in zeile if w[1] <= bez_links and w[3].startswith(".")
            and re.fullmatch(r"\.\d+", w[3])]
    return teil[0][3] if len(teil) == 1 else None


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
    saldo: float
    ve: float | None


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
                kanten.setdefault("saldo", x1)
            elif text == "VE":
                kanten.setdefault("ve", x1)
    if not {"ein", "aus", "saldo"} <= kanten.keys():
        return None
    return SummenSpalten(kanten["ein"], kanten["aus"], kanten["saldo"],
                         kanten.get("ve"))


def _summen_zellen(zeile: list[Wort], spalten: SummenSpalten,
                   ) -> tuple[dict[str, int], float, float] | None:
    """Die Beträge einer Zeile ihren Spalten zuordnen.

    Gibt ``None`` zurück, sobald etwas nicht stimmt: ein Betrag ohne Spalte,
    zwei Beträge in derselben Spalte, oder eine der drei Pflichtspalten leer.
    Das ist die Eintrittskarte — was hier durchfällt, ist keine
    Zusammenstellungs-Zeile.
    """
    felder = {"ein": spalten.ein, "aus": spalten.aus, "saldo": spalten.saldo}
    if spalten.ve is not None:
        felder["ve"] = spalten.ve
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
    if not {"ein", "aus", "saldo"} <= zellen.keys():
        return None
    return zellen, erster, letzter


def _summen_zeile(jahr: int, typ: str, zeile: list[Wort],
                  zellen: dict[str, int], erster: float, letzter: float) -> FhhSumme:
    """Eine Zusammenstellungs-Zeile lesen — und sofort beweisen.

    Die Zeilenprobe läuft HIER, nicht später: Eine Zeile, die ihren eigenen
    Saldo nicht trägt, ist ein Lesefehler — und dann soll das Dokument
    fallen, nicht die Zeile.
    """
    ein, aus, saldo = zellen["ein"], zellen["aus"], zellen["saldo"]
    if abs(ein - aus - saldo) > 2:
        raise ListenFehler(
            f"Zeilenprobe {jahr}: {ein:,} − {aus:,} ≠ {saldo:,} "
            f"in „{' '.join(w[3] for w in zeile)[:70]}“")
    # Links des ersten Betrags steht die Beschriftung, rechts des letzten der
    # Urheber („Vorschlag von" — nur die Beschluss-Dateien führen ihn).
    label = " ".join(w[3] for w in zeile if w[1] <= erster).strip()
    urheber = " ".join(w[3] for w in zeile if w[0] >= letzter).strip()
    return FhhSumme(jahr=jahr, typ=typ, label=(label or urheber or "liste"),
                    einzahlungen=ein, auszahlungen=aus, saldo=saldo,
                    ve=zellen.get("ve"))


def _block_jahr(block_jahr: int | None, aus: FhhErgebnis, typ: str) -> int:
    """Das Planjahr eines Blocks — wie beim EHH aus der Reihenfolge, wenn die
    Überschrift fehlt: Jeder Block beginnt mit seinem Verwaltungsentwurf."""
    if block_jahr is not None:
        return block_jahr
    jahre = sorted({z.jahr for z in aus.zeilen})
    entwuerfe = sum(1 for s in aus.summen if s.typ == "entwurf")
    idx = entwuerfe if typ == "entwurf" else entwuerfe - 1
    if 0 <= idx < len(jahre):
        return jahre[idx]
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

    for nr, woerter in enumerate(seiten):
        zeilen = zeilen_bilden(woerter)
        senkrecht = linien[nr][1] if nr < len(linien) else []
        spalten = _spalten(zeilen, senkrecht)
        seitentext = " ".join(w[3] for w in woerter)
        marker = _JAHR_MARKER.search(seitentext)
        jahr = int(marker.group(1)) if marker else None
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

            if spalten is not None and jahr is not None:
                if _ist_position(zeile, spalten):
                    position = _position_lesen(zeile, jahr, spalten)
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
            if _ENTWURF.search(text):
                typ = "entwurf"
            elif _LISTE.search(text):
                typ = "liste"
            elif " ".join(w[3] for w in zeile if w[1] <= erster).strip():
                # Eine Zeile mit eigener Beschriftung, aber ohne Stichwort:
                # die politische Liste der Beschluss-Dateien.
                typ = "liste"
            else:
                # Nackte Zahlenreihe ohne Beschriftung — die Summe unter dem
                # Block. Die Beschluss-Dateien setzen sie ohne „Überschuss/
                # Fehlbedarf" davor, anders als der EHH.
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
        schluessel = (z.jahr, z.lfd)
        erste = aus.get(schluessel)
        if erste is None:
            aus[schluessel] = z
            continue
        for feld in ("soll_entwurf", "einzahlung", "auszahlung", "ve", "soll_neu"):
            alt_wert, neu_wert = getattr(erste, feld), getattr(z, feld)
            if neu_wert is None:
                continue
            if alt_wert is not None and alt_wert != neu_wert:
                raise ListenFehler(
                    f"Position {z.jahr}/lfd {z.lfd} steht zweimal mit "
                    f"verschiedenem {feld}: {alt_wert:,} und {neu_wert:,}.")
            setattr(erste, feld, neu_wert)
        for feld in ("erlaeuterung", "bezeichnung", "urheber"):
            alt_text, neu_text = getattr(erste, feld), getattr(z, feld)
            if neu_text and neu_text != alt_text:
                setattr(erste, feld, f"{alt_text} {neu_text}".strip()
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
    if ziel.produkt and not ziel.produkt.endswith(schwanz):
        ziel.produkt += schwanz


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
        alle = sorted(teile + [(py, position.bezeichnung)])
        position.bezeichnung = " ".join(t for _, t in alle if t)


#: Der Index der Spalte „neues Soll" in :attr:`FhhSpalten.betrag`.
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
            for i, (links, rechts) in enumerate(spalten.betrag):
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
    boden = max(waagerecht) if waagerecht else float("inf")

    # Doppelt gedruckte Positionen (gleiche Lfd. Nr., zwei Erläuterungs-
    # blöcke) besitzen EINE Zeile, nicht zwei.
    sortiert: list[tuple[float, FhhZeile]] = []
    for py, position in sorted(positionen, key=lambda p: p[0]):
        if sortiert and sortiert[-1][1].lfd == position.lfd:
            continue
        sortiert.append((py, position))

    spannen = [(py, pos, sortiert[i + 1][0] if i + 1 < len(sortiert) else boden)
               for i, (py, pos) in enumerate(sortiert)]

    for y, zellen in _betragszeilen(zeilen, spalten, boden):
        for oben, position, unten in spannen:
            if oben - 2 <= y < unten:
                (position.soll_entwurf, position.einzahlung,
                 position.auszahlung, position.ve, position.soll_neu) = (
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
            position.erlaeuterung = zeilen_falten(zeilen_bilden(woerter))
        if (woerter := sorted(urh_baender.get(b, []), key=lambda w: (w[2], w[0]))):
            position.urheber = " ".join(
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
            if None not in (z.soll_entwurf, z.einzahlung, z.auszahlung, z.soll_neu)]
    schief = [z for z in voll
              if abs((z.soll_entwurf or 0) + (z.einzahlung or 0)
                     + (z.auszahlung or 0) - (z.soll_neu or 0)) > 2]
    if schief:
        z = schief[0]
        raise ListenFehler(
            f"Zeilenprobe {z.jahr}/lfd {z.lfd}: {z.soll_entwurf:,} + "
            f"{z.einzahlung:,} + {z.auszahlung:,} ≠ {z.soll_neu:,} "
            f"({len(schief)} von {len(voll)} Zeilen betroffen)")

    for jahr in sorted({z.jahr for z in aus.zeilen}):
        entwurf = [s for s in aus.summen if s.jahr == jahr and s.typ == "entwurf"]
        listen = [s for s in aus.summen if s.jahr == jahr and s.typ == "liste"]
        ende = [s for s in aus.summen if s.jahr == jahr and s.typ == "endsumme"]
        if len(entwurf) != 1 or len(ende) != 1 or not listen:
            raise ListenFehler(
                f"Zusammenstellung {jahr}: erwartet 1×Entwurf, ≥1×Liste, "
                f"1×Endsumme — gefunden {len(entwurf)}/{len(listen)}/{len(ende)}.")

        toleranz = 2 * (len(listen) + 1)
        kette_ok = all(
            abs(getattr(entwurf[0], feld) + sum(getattr(s, feld) for s in listen)
                - getattr(ende[0], feld)) <= toleranz
            for feld in ("einzahlungen", "auszahlungen"))

        pos_e = sum(z.einzahlung or 0 for z in aus.zeilen if z.jahr == jahr)
        pos_a = sum(z.auszahlung or 0 for z in aus.zeilen if z.jahr == jahr)
        if kette_ok:
            ziele = [(s.label, s.einzahlungen, s.auszahlungen) for s in listen]
            if len(listen) > 1:
                ziele.append(("alle", sum(s.einzahlungen for s in listen),
                              sum(s.auszahlungen for s in listen)))
        else:
            ziele = [("beschlossen",
                      ende[0].einzahlungen - entwurf[0].einzahlungen,
                      ende[0].auszahlungen - entwurf[0].auszahlungen)]
        treffer = [label for label, e, a in ziele
                   if abs(e - pos_e) <= toleranz and abs(a - pos_a) <= toleranz]
        if len(treffer) != 1:
            raise ListenFehler(
                f"Positionsprobe {jahr}: Die Positionen summieren auf "
                f"{pos_e:,} / {pos_a:,} — "
                + ("keine Zusammenstellungs-Zeile trifft das" if not treffer
                   else "mehrere Zeilen träfen das")
                + ": " + "; ".join(f"{lab}: {e:,}/{a:,}" for lab, e, a in ziele))
        aus.eigene_zeile[jahr] = treffer[0]


def lies_fhh_liste(pdf_bytes: bytes) -> FhhErgebnis:
    """PDF → geprüfte FHH-Änderungsliste. Wirft :class:`ListenFehler`."""
    return parse_fhh_seiten(seiten_woerter(pdf_bytes), seiten_linien(pdf_bytes))


def herkunft_fuer(label: str, url: str | None, dokument_id: int) -> Herkunft:
    return Herkunft(
        art="ris",
        probe=("aenderungsliste_fhh_zeilen", "aenderungsliste_summen",
               "aenderungsliste_positionen"),
        label=label,
        url=url or f"https://buergerinfo.oldenburg.de/getfile.php?id={dokument_id}&type=do",
        dokument_id=dokument_id,
    )
