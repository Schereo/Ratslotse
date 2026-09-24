"""Die Budgetberichte der Fachausschüsse — Investitionen je Maßnahme mit
Prognose und Begründung (Plan Haushalt-Datenquellen, PR 8b).

Jugendhilfeausschuss (Teilhaushalt 11) und Schulausschuss (Teilhaushalt 12)
bekommen seit 2017 viermal im Jahr einen „Finanz- und Leistungsbericht" zum
Quartalsstichtag. Ab 2018/2019 steht darin eine Tabelle der Investitionen je
Maßnahme (I10-Nummer): Ansatz, Prognose zum Jahresende, Abweichung — und
darunter, in den Worten der Verwaltung, warum („Der Erweiterungsbau der
Krippe ist fertiggestellt …"). Der Haushaltsvollzug (``council_budget_execution``)
kennt nur Summen je Teilhaushalt; das hier ist die Ebene darunter.

DREI TABELLENFORMEN (gemessen 24.09.2026 an 30 Berichten, s. Plan):

* ``verfuegbar`` (2018–2021): Ansatz · Ermächtigungsübertragung · verfügbare
  Mittel · Prognose · Abweichung · Prozent.
* ``nachrichtlich`` (2021–2026): Ansatz · Prognose · Abweichung · Prozent ·
  nachrichtlich Ermächtigung aus Vorjahren · Abweichung plus Ermächtigung.
* ``kurz`` (Schulausschuss 2021 und 2023, kleines Seitenformat): Plan ·
  Prognose, Zahlen ohne Tausenderpunkt.

WIE GELESEN WIRD: über Wortrahmen. Die Spalte „E/A" findet sich am Kopfwort,
die Betragsspalten an ihren rechten Rändern (Zahlen stehen rechtsbündig), die
Maßnahmen-Nummern stehen links und oft über zwei Zeilen („I10.170073.525 bis
I10.170073.525.001") — sie gehören zur nächstgelegenen Betragszeile.
Fließtextzeilen zwischen zwei Maßnahmen sind die Erläuterung der oberen.

DIE PROBE: Die Zeile „Auszahlungen für Investitionen" der Teilfinanzrechnung
nennt Ansatz und Prognose des ganzen Teilhaushalts; die Maßnahmen ergeben
sie, auf den Euro — je Richtung, als Beträge: Manche Berichte drucken
Einzahlungen mit Minus, die Summenzeile nicht (20/0493). Fehlt die Zeile,
ist der Bericht ungeprüft und wird nicht gespeichert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PROBE_BUDGETBERICHT = "budget_report_measures_sum"

_ZAHL = re.compile(r"^-?\d{1,3}(?:\.\d{3})+(?:,\d+)?$|^-?\d+(?:,\d+)?$")
#: Sieben Ziffern kommen vor: „I10.1702721.510.002" (21/0648) ist ein Tippfehler
#: im Dokument und wird so übernommen, wie es dort steht.
_I10 = re.compile(r"I10\.\d{6,7}(?:\.\d{3})*\.?")
_THH = re.compile(r"THH\s*0?(\d{1,2})\b|Teilhaushalt\s+0?(\d{1,2})\b")

#: Spaltenfolge je Tabellenform — die Felder, die gespeichert werden.
FORMEN = {
    "verfuegbar": ("planned", "carryover", "available", "forecast", "deviation", "deviation_pct"),
    "nachrichtlich": ("planned", "forecast", "deviation", "deviation_pct", "carryover", "deviation_total"),
    "kurz": ("planned", "forecast"),
}


class BerichtFehler(ValueError):
    """Die Tabelle lässt sich nicht so lesen, dass die Probe besteht."""


@dataclass
class Massnahme:
    nr: str                         # erste I10-Nummer der Zeile
    nr_bis: str | None              # letzte, wo die Zeile einen Bereich nennt
    name: str
    kind: str                       # A = Auszahlung, E = Einzahlung
    planned: float | None
    forecast: float | None
    carryover: float | None = None  # Ermächtigung aus Vorjahren
    note: str = ""                  # Erläuterung im Wortlaut


@dataclass
class Bericht:
    sub_budget_no: int | None = None
    as_of: str | None = None        # Stichtag, ISO
    form: str | None = None
    massnahmen: list[Massnahme] = field(default_factory=list)
    summe: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    hinweise: list[str] = field(default_factory=list)
    gerundet: list[str] = field(default_factory=list)   # Summenzeile des Dokuments gerundet

    @property
    def budget_year(self) -> int | None:
        return int(self.as_of[:4]) if self.as_of else None

    def pruefen(self) -> bool:
        """Die Maßnahmen gegen die Zeile der Teilfinanzrechnung, je Richtung."""
        if not self.massnahmen:
            self.hinweise.append("keine Maßnahme gelesen")
            return False
        ok = True
        for kind in sorted({m.kind for m in self.massnahmen}):
            if kind not in self.summe:
                self.hinweise.append(f"keine Summenzeile für {kind}")
                ok = False
                continue
            plan, prog = self.summe[kind]
            ms = [m for m in self.massnahmen if m.kind == kind]
            for feld, soll in (("planned", plan), ("forecast", prog)):
                ist = sum(getattr(m, feld) or 0 for m in ms)
                if soll is not None and abs(ist - soll) <= 1:
                    continue
                if soll is not None and abs(ist - soll) <= 0.001 * soll:
                    # Die Summenzeile des Dokuments ist gerundet (26/0596:
                    # 2.320.000 statt 2.319.506 — auch seine Abweichungs-
                    # spalte rechnet damit). Die Maßnahmen sind vollständig.
                    def de(x: float) -> str:
                        return f"{x:,.0f}".replace(",", ".")
                    self.gerundet.append(f"{kind} {feld}: Summenzeile {de(soll)} €, Maßnahmen {de(ist)} €")
                    continue
                self.hinweise.append(f"{kind} {feld}: Maßnahmen {ist:,.0f} ≠ Summenzeile {soll}")
                ok = False
        return ok


def _zahl(s: str, kurz: bool = False) -> float | None:
    """„1.715.500" / „-164,2" — im Kleinformat „7711.2" mit Dezimalpunkt."""
    if kurz:
        return float(s) if re.fullmatch(r"-?\d+(?:\.\d+)?", s) else None
    if not _ZAHL.match(s):
        return None
    return float(s.replace(".", "").replace(",", "."))


def _zeilen(woerter: list[tuple]) -> list[list[tuple]]:
    """Wörter zu Zeilen (Mittellinie ± 3 pt), jede Zeile von links nach rechts.

    Zwei Wörter, die sich waagerecht überdecken, stehen nie auf derselben
    Zeile — auch wenn ihre Mittellinien keine 3 pt auseinander liegen
    (23/0808: „2023" als Ende eines Namens direkt über dem nächsten)."""
    aus: list[list[tuple]] = []
    for w in sorted(woerter, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        mitte = (w[1] + w[3]) / 2
        if (aus and abs((aus[-1][0][1] + aus[-1][0][3]) / 2 - mitte) <= 3
                and not any(x[0] < w[2] - 1 and w[0] < x[2] - 1 for x in aus[-1])):
            aus[-1].append(w)
        else:
            aus.append([w])
    return [sorted(z, key=lambda w: w[0]) for z in aus]


def _spalten(raender: list[float], abstand: float = 12) -> list[float]:
    """Rechte Ränder zu Spalten bündeln — je Spalte der größte Rand."""
    aus: list[list[float]] = []
    for r in sorted(raender):
        if aus and r - aus[-1][-1] <= abstand:
            aus[-1].append(r)
        else:
            aus.append([r])
    return [max(g) for g in aus]


def stichtag(*texte: str) -> str | None:
    """Der Stichtag aus Titel und Anlagenname („… zum 30.06.2025"), ISO.

    Nicht aus dem Berichtstext: Dort steht zuerst „Prognose zum 31.12.",
    der Spaltenkopf — und der ist fast nie der Stichtag."""
    for t in texte:
        if m := re.search(r"(\d{2})\.(\d{2})\.(20\d\d)", t or ""):
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def lies_seiten(seiten: list[list[tuple]], seitentext: str = "", as_of: str | None = None) -> Bericht:
    """``seiten``: alle Seiten des Berichts als Wortrahmen (pymupdf ``words``),
    ``as_of``: der Stichtag (s. :func:`stichtag`)."""
    b = Bericht(as_of=as_of)
    t = " ".join(seitentext.split())
    if m := _THH.search(t):
        b.sub_budget_no = int(m.group(1) or m.group(2))
    if "nachrichtlich" in t:
        b.form = "nachrichtlich"
    elif "Verfügbare" in t or "Verfügbar" in t:
        b.form = "verfuegbar"
    else:
        b.form = "kurz"
    felder = FORMEN[b.form]

    kurz = b.form == "kurz"
    # (seite, y, zeile, ea_x, name_x) je Zeile ab dem ersten Tabellenkopf
    alle_zeilen: list[tuple[int, float, list[tuple], float, float]] = []
    datenzeilen: list[tuple[int, float, str, list, list[tuple], float, float]] = []
    summen_zeilen: list[tuple[str, list]] = []
    ea_x: float | None = None
    name_x: float | None = None
    offene_summe: str | None = None   # Beschriftung ohne Beträge — sie stehen darunter
    for s, woerter in enumerate(seiten):
        # Der Kopf steht nicht auf jeder Seite (Kleinformat: nur auf der
        # ersten); die Spalten gelten weiter, bis ein neuer Kopf kommt.
        ea = [w for w in woerter if w[4] in ("E/A*", "E/", "E/A")]
        if ea:
            kopf_x: float = min(w[0] for w in ea)
            ea_x = kopf_x
            # Die Spalte „Bezeichnung": das Kopfwort steht zentriert darüber,
            # die Namen beginnen weiter links — also der kleinere Wert aus
            # Kopfwort und der Stelle, an der nach einer Maßnahmen-Nummer das
            # erste Wort steht.
            kandidaten = [w[0] for w in woerter if w[4] == "Bezeichnung" and w[0] < kopf_x]
            for z in _zeilen(woerter):
                rest = [w for w in z[1:] if w[4] != "bis"]
                if _I10.match(z[0][4]) and rest and rest[0][0] < kopf_x - 2 and not _I10.match(rest[0][4]):
                    kandidaten.append(rest[0][0])
            name_x = min(kandidaten) if kandidaten else name_x
        for z in _zeilen(woerter):
            y = (z[0][1] + z[0][3]) / 2
            betraege = [(w[0] if kurz else w[2], _zahl(w[4], kurz)) for w in z
                        if _zahl(w[4], kurz) is not None and (ea_x is None or w[0] > ea_x + 8)]
            # Die Summenzeile der Teilfinanzrechnung: ohne E/A-Kennzeichen,
            # in älteren Berichten mit den Beträgen eine Zeile tiefer.
            kopf = " ".join(w[4] for w in z[:3])
            # Im Kleinformat bricht die Beschriftung um („Auszahlungen für" /
            # „Investitionen"): dann nur mit Beträgen und ohne weiteren Text.
            woerter_ohne_zahl = [w for w in z if _zahl(w[4], kurz) is None]
            m = re.match(r"(Aus|Ein)zahlungen für Investitionen", kopf)
            if not m and len(woerter_ohne_zahl) == 2 and len(betraege) >= 2:
                m = re.match(r"(Aus|Ein)zahlungen für$", " ".join(w[4] for w in woerter_ohne_zahl))
            if m:
                art = "A" if m.group(1) == "Aus" else "E"
                if len(betraege) >= 2:
                    summen_zeilen.append((art, betraege))
                else:
                    offene_summe = art
                continue
            if offene_summe and len(betraege) >= 2 and len(betraege) == len(z):
                summen_zeilen.append((offene_summe, betraege))
                offene_summe = None
                continue
            offene_summe = None
            if ea_x is None:
                continue
            alle_zeilen.append((s, y, z, ea_x, name_x if name_x is not None else ea_x))
            marke = [w for w in z if w[4] in ("A", "E") and abs(w[0] - ea_x) < 20]
            if marke and betraege:
                datenzeilen.append((s, y, marke[0][4], betraege, z, ea_x,
                                    name_x if name_x is not None else ea_x))
    if not datenzeilen:
        raise BerichtFehler("keine Betragszeile mit E/A-Kennzeichen")
    raender = _spalten([r for d in datenzeilen for r, _ in d[3]])
    if len(raender) != len(felder):
        raise BerichtFehler(f"{len(raender)} Betragsspalten statt {len(felder)} ({b.form})")

    def werte(zahlen: list[tuple[float, float | None]]) -> dict:
        aus: dict = {}
        for rand, wert in zahlen:
            i = min(range(len(raender)), key=lambda k: abs(raender[k] - rand))
            aus[felder[i]] = wert
        return aus

    for art, betraege in summen_zeilen:
        if art not in b.summe:   # die erste Tabelle zählt; spätere Wiederholungen nicht
            v = werte(betraege)
            b.summe[art] = tuple(abs(x) if x is not None else None   # type: ignore[assignment]
                                 for x in (v.get("planned"), v.get("forecast")))

    def ist_prosa(z: list[tuple], ea: float, nx: float | None = None) -> bool:
        if kurz and nx is not None:
            # Im Kleinformat steht die Erläuterung in der schmalen linken
            # Spalte, unter der Nummer — nie rechts der E/A-Spalte.
            return (z[0][0] < nx - 20 and not _I10.match(z[0][4])
                    and not any(w[4] in ("A", "E") and abs(w[0] - ea) < 20 for w in z))
        return len(z) >= 5 and any(w[0] > ea + 10 and _zahl(w[4], kurz) is None for w in z)

    # Die letzte Zeile eines Absatzes ist kurz und damit kein Fließtext nach
    # der Regel oben — endet sie mit Punkt und steht direkt unter Fließtext,
    # gehört sie trotzdem zur Erläuterung, nicht zum nächsten Namen
    # (21/0648: „Maßnahme Dedestr.").
    satzende: set[tuple[int, float]] = set()
    for (s1, y1, z1, e1, n1), (s2, y2, z2, _, _) in zip(alle_zeilen, alle_zeilen[1:]):
        if s1 == s2 and 0 < y2 - y1 <= 16 and ist_prosa(z1, e1, n1) and z2[-1][4].endswith("."):
            satzende.add((s2, y2))

    massnahme_zeilen = []
    for s, y, kind, zahlen, z, ea, nx in datenzeilen:
        nachbarn = [d[1] for d in datenzeilen if d[0] == s]
        # Zeilen um diese Betragszeile, die näher an ihr liegen als an jeder
        # anderen — dort stehen Nummern (links) und Bezeichnung (Spalte
        # „Bezeichnung"), oft über und unter der Betragszeile verteilt.
        # Im Kleinformat beginnt der Name auf der Betragszeile und läuft nach
        # unten weiter; darüber steht das Ende des vorigen.
        umfeld = [(zy, zz) for zs, zy, zz, _, _ in alle_zeilen
                  if zs == s and abs(zy - y) <= (60 if kurz else 26) and not ist_prosa(zz, ea, nx)
                  and (zs, zy) not in satzende
                  and (not kurz or zy >= y - 2)
                  # Gleich weit von zwei Betragszeilen: Die Bezeichnung steht
                  # über ihrer Zeile (23/0808), also gilt die untere.
                  and (min(nachbarn, key=lambda n: (round(abs(n - zy), 1), -n)) == y if not kurz
                       else max([n for n in nachbarn if n <= zy + 2], default=y) == y)]
        nummern = [n for _, zz in umfeld for w in zz if w[0] < nx - 2 for n in _I10.findall(w[4])]
        # Namen nur aus Zeilen, die in der Spalte „Bezeichnung" oder mit einer
        # Nummer beginnen — ein kurzes Satzende der Erläuterung darüber
        # („Anspruch genommen.") beginnt am linken Rand und gehört nicht dazu.
        name = " ".join(w[4] for _, zz in sorted(umfeld, key=lambda u: u[0])
                        if zz[0][0] >= nx - 2 or _I10.match(zz[0][4]) or zz[0][4] == "bis"
                        or zz is z
                        for w in zz if nx - 2 <= w[0] < ea - 2 and w[4] != "bis")
        if not nummern and not name:
            continue
        # Beträge je Richtung sind nie negativ; manche Berichte drucken
        # Einzahlungen trotzdem mit Minus (20/0493: „-2.655.000" beim
        # Digitalpakt), die Summenzeile rechnet mit dem Betrag.
        v = {k: (abs(x) if k in ("planned", "forecast", "carryover") and x is not None else x)
             for k, x in werte(zahlen).items()}
        m = Massnahme(nr=nummern[0] if nummern else "", nr_bis=nummern[-1] if len(nummern) > 1 else None,
                      name=" ".join(name.split()), kind=kind,
                      planned=v.get("planned"), forecast=v.get("forecast"),
                      carryover=v.get("carryover"))
        # Manche Berichte führen dieselbe Tabelle zweimal (26/0009: einmal
        # als Übersicht, einmal mit Erläuterungen) — gezählt wird sie einmal.
        schluessel = (m.nr, m.nr_bis, m.name, m.kind, m.planned, m.forecast)
        if any((x.nr, x.nr_bis, x.name, x.kind, x.planned, x.forecast) == schluessel
               for x in b.massnahmen):
            continue
        massnahme_zeilen.append((s, max([y] + [u[0] for u in umfeld]), m))
        b.massnahmen.append(m)

    # Erläuterungen: Fließtextzeilen unter einer Maßnahme bis zur nächsten.
    for i, (s, y, m) in enumerate(massnahme_zeilen):
        ende = massnahme_zeilen[i + 1] if i + 1 < len(massnahme_zeilen) else None
        saetze = []
        for zs, zy, z, ea_x, nx in alle_zeilen:
            if (zs, zy) <= (s, y + 4):
                continue
            if ende and (zs > ende[0] or (zs == ende[0] and zy >= ende[1] - 14)):
                break
            if any(_I10.fullmatch(w[4]) for w in z[:1]):
                continue
            if ist_prosa(z, ea_x, nx):
                saetze.append(" ".join(w[4] for w in z))
            elif saetze:
                break
        text = re.sub(r"(\w)- (?=[a-zäöüß])", r"\1", " ".join(saetze))
        m.note = " ".join(text.split())
    return b


def woerter_aus_pdf(pdf: bytes) -> tuple[list[list[tuple]], str]:
    """Alle Seiten als Wortrahmen und der Text des ganzen Berichts."""
    import pymupdf  # noqa: PLC0415 — bewusst optional
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        text = "\n".join(str(p.get_text()) for p in doc)
        seiten = [[tuple(w) for w in p.get_text("words")] for p in doc]
    return seiten, text
