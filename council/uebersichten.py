"""Die Übersichten des Haushaltsplans (Anlage 003) — wer Zuschüsse bekommt.

Anlage 003 bündelt Tabellen, die sonst nirgends stehen. Der erste und für
Leser*innen greifbarste Teil ist die **Übersicht über die Zuweisungen und
Zuschüsse an Dritte**: je Zuschuss eine Zeile mit laufender Nummer,
Teilhaushalt, Produkt, Beschreibung („Zuschuss Reparaturrat"), Betrag im
Planjahr und im Vorjahr, Erläuterung („Reparaturrat Oldenburg e.V. —
Zuschuss für Personal- und Sachkosten") und ob bar oder unbar. Rund 300
Zeilen je Plan, 2019–2026.

Vereine und Träger stehen dort mit Namen, und so zeigt sie die Seite auch
(Tims Entscheidung 24.09.2026). Privatpersonen kommen in der Übersicht nicht
vor — der kleinste Empfänger ist eine Betriebssportgruppe.

WIE GELESEN WIRD
----------------

Die Seiten sind quer gedreht (/Rotate 270), und das hilft: In den
UNGEDREHTEN Koordinaten ist jeder Zuschuss eine waagerechte Bande, die
Spalten liegen nebeneinander. Die Anker sind die Zeilen, die links eine
laufende Nummer und daneben eine zweistellige Teilhaushaltsnummer tragen; jedes
andere Wort gehört zum nächstgelegenen Anker, denn die Zellen sind senkrecht
zentriert und brechen nach oben und unten um. Die Spalten sagt der Tabellenkopf
(„Haushalt 2025 in Euro", „Erläuterungen", „bar"/„unbar") — ihre Lage wandert
zwischen den Jahrgängen, deshalb wird sie je Seite gemessen, nicht festgeschrieben.

DIE PROBE: Nach jedem Teilhaushalt steht „Summe THH 03" mit beiden
Beträgen. Die Zeilen darüber müssen sie ergeben, in beiden Spalten
(Einzelheiten und die beiden Ausnahmen der Vorlage selbst: ``pruefen``).
Gemessen 24.09.2026: 2019 und 2022–2026 ergeben auch die gedruckte
Gesamtsumme auf den Euro.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PROBE_ZUSCHUESSE = "grants_subtotals"

_BETRAG = re.compile(r"^-?\d{1,3}(?:\.\d{3})*$")
_NR = re.compile(r"^\d{1,3}$")
_THH = re.compile(r"^\d{2}$")
_KOPF = "Zuweisungen und Zuschüsse an Dritte"


@dataclass
class Zuschuss:
    lfd_nr: int
    sub_budget_no: int
    product_no: str
    product_name: str
    description: str
    amount_prior: float | None
    amount: float | None
    note: str
    cash: bool | None


@dataclass
class Lesung:
    budget_year: int | None = None
    zeilen: list[Zuschuss] = field(default_factory=list)
    summen: dict[int, tuple[float, float]] = field(default_factory=dict)
    #: Was die Probe verwirft — ein Jahrgang mit Hinweis wird nicht gespeichert.
    hinweise: list[str] = field(default_factory=list)
    #: Was an der VORLAGE auffällt, nicht an der Lesung: doppelte Nummern,
    #: übersprungene, eine Summenzeile, die ihre eigenen Zeilen nicht ergibt.
    auffaellig: list[str] = field(default_factory=list)

    @property
    def bestanden(self) -> bool:
        return bool(self.zeilen) and not self.hinweise


def _wert(t: str) -> float:
    return float(t.replace(".", ""))


def _spalten(woerter: list[tuple]) -> dict[str, float] | None:
    """Die Spaltengrenzen aus dem Tabellenkopf der Seite (x in Punkten).

    Gesucht: die beiden „Haushalt"-Köpfe (Vorjahr links, Planjahr rechts),
    „Erläuterungen", „bar", „unbar", „Beschreibung" und „Name" (des
    Produkts). Fehlt einer, ist die Seite keine Zuschuss-Seite."""
    kopf = [w for w in woerter if w[1] < _kopfende(woerter)]
    hh = sorted(w[0] for w in kopf if w[4] == "Haushalt")
    erl = [w[0] for w in kopf if w[4].startswith("Erläuterung")]
    bar = [w[0] for w in kopf if w[4] == "bar"]
    unbar = [w[0] for w in kopf if w[4] == "unbar"]
    besch = [w[0] for w in kopf if w[4] == "Beschreibung"]
    name = [w[0] for w in kopf if w[4] == "Name"]
    produkt = [w[0] for w in kopf if w[4].startswith("Produkt/")]
    # „bar"/„unbar" gibt es erst ab 2020; 2019 fehlt die Spalte.
    if len(hh) < 2 or not erl or not besch or not name or not produkt:
        return None
    rechts = max(w[2] for w in kopf)
    return {
        "produkt": produkt[0] - 12,
        "name": min(name) - 35,
        "beschreibung": besch[0] - 18,
        "vorjahr": hh[0] - 10,
        "planjahr": hh[1] - 10,
        "erlaeuterung": erl[0] - 45,
        "bar": (bar[0] + unbar[0]) / 2 - 2 if bar and unbar else float("inf"),
        "ende": unbar[0] + 30 if unbar else rechts + 200,
    }


def _kopfende(woerter: list[tuple]) -> float:
    """Die Unterkante des Tabellenkopfs: die Zeile „in Euro" unter „Haushalt".

    Nicht eine feste Höhe — das Produkt „Haushalt und Controlling" steht
    direkt darunter und sähe sonst aus wie ein dritter Spaltenkopf."""
    euro = [w[3] for w in woerter if w[4] in ("Euro", "EUR") and w[1] < 130]
    return min(euro) + 1 if euro else 0.0


def _jahr(woerter: list[tuple]) -> int | None:
    """Das Planjahr: die rechte der beiden Jahreszahlen im Kopf."""
    jahre = sorted((w[0], int(w[4])) for w in woerter
                   if w[1] < _kopfende(woerter) and re.fullmatch(r"20\d\d", w[4]))
    return jahre[-1][1] if jahre else None


def _zuordnen(ws: list[tuple], marken: list[tuple[float, bool]],
              mitte) -> dict[float, list[tuple]]:
    """Die Zeilen einer Spalte den Zuschüssen zuordnen.

    Die Zellen sind senkrecht ZENTRIERT: Eine Erläuterung mit elf Zeilen
    beginnt fünf Zeilen über ihrer Nummer. „Das nächstgelegene Anker-Wort"
    reicht deshalb nicht — die untere Hälfte einer langen Erläuterung liegt
    näher an der nächsten Nummer als an der eigenen. Stattdessen, von oben
    nach unten: Eine Zelle nimmt unter ihrer Nummer so viele Zeilen, wie sie
    darüber hatte; der Rest bis zur nächsten Nummer gehört dieser.
    Summenzeilen (``False``) sind harte Grenzen und nehmen nichts."""
    zeilen: list[list[tuple]] = []
    for w in sorted(ws, key=mitte):
        if zeilen and mitte(w) - mitte(zeilen[-1][0]) <= 3:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    aus: dict[float, list[tuple]] = {}
    oben = 0  # wie viele Zeilen der aktuellen Zelle über ihrer Nummer lagen
    i = 0
    for k, (y, ist_zuschuss) in enumerate(marken):
        naechste = marken[k + 1][0] if k + 1 < len(marken) else float("inf")
        davor: list[list[tuple]] = []
        while i < len(zeilen) and mitte(zeilen[i][0]) < y - 3:
            davor.append(zeilen[i])
            i += 1
        auf: list[list[tuple]] = []
        while i < len(zeilen) and mitte(zeilen[i][0]) <= y + 3:
            auf.append(zeilen[i])
            i += 1
        danach: list[list[tuple]] = []
        j = i
        while j < len(zeilen) and mitte(zeilen[j][0]) < naechste - 3:
            danach.append(zeilen[j])
            j += 1
        oben = len(davor)
        if not ist_zuschuss:
            continue
        # Symmetrisch um die Nummer; die letzte Zelle einer Seite nimmt den Rest.
        unten = len(danach) if k + 1 == len(marken) else oben
        if k + 1 < len(marken) and not marken[k + 1][1]:
            unten = len(danach)  # vor einer Summenzeile gehört alles dieser
        nimmt = danach[:unten]
        i += len(nimmt)
        gruppe = [w for z in davor + auf + nimmt for w in z]
        if gruppe:
            aus[y] = gruppe
    return aus


def lies_seite(woerter: list[tuple], aus: Lesung) -> bool:
    """Eine Seite lesen; ``False``, wenn sie keine Zuschuss-Seite ist.

    ``woerter`` sind pymupdf-Wörter (x0, y0, x1, y1, text, …) in den
    ungedrehten Koordinaten der Seite."""
    sp = _spalten(woerter)
    if sp is None:
        return False
    if aus.budget_year is None:
        aus.budget_year = _jahr(woerter)
    rumpf = [w for w in woerter if w[1] > _kopfende(woerter) + 1]
    mitte = lambda w: (w[1] + w[3]) / 2  # noqa: E731

    # Anker: laufende Nummer ganz links, Teilhaushalt daneben, auf einer Höhe.
    # Die Seitenzahl steht am linken Rand (x ≈ 19) und ist keine Nummer.
    lfd_x = min((w[0] for w in woerter if w[4] == "Lfd."), default=60.0)
    nummern = [w for w in rumpf if lfd_x - 12 <= w[0] <= lfd_x + 15
               and _NR.match(w[4])]
    anker: list[tuple[float, int, int]] = []
    # Die Zeilenhöhe gibt der Teilhaushalt, nicht die Nummer: 2019 steht die
    # „44" sechs Punkte über ihrer Zeile (Kinderbuchpreis), und nach der
    # Nummer allein bekäme die Zeile darunter ihren Betrag.
    thh_woerter = [w for w in rumpf if w[0] > lfd_x + 15 and w[0] < sp["produkt"]
                   and _THH.match(w[4])]
    for n in nummern:
        kandidaten = [w for w in thh_woerter if abs(mitte(w) - mitte(n)) <= 8]
        if kandidaten:
            thh = min(kandidaten, key=lambda w: abs(mitte(w) - mitte(n)))
            anker.append((mitte(thh), int(n[4]), int(thh[4])))
    # Summenzeilen „Summe THH 03" trennen die Teilhaushalte.
    summen: list[tuple[float, int, list[str]]] = []
    for w in rumpf:
        if w[4] == "Summe":
            zeile = sorted((x for x in rumpf if abs(mitte(x) - mitte(w)) <= 3), key=lambda x: x[0])
            thh = next((int(x[4]) for x in zeile if _THH.match(x[4])), None)
            betraege = [x for x in zeile if _BETRAG.match(x[4]) and x[0] >= sp["vorjahr"]]
            if thh is not None:
                summen.append((mitte(w), thh, [x[4] for x in betraege]))
                if len(betraege) == 2:
                    aus.summen[thh] = (_wert(betraege[0][4]), _wert(betraege[1][4]))
    if not anker:
        return True
    zellen: dict[float, dict[str, list[tuple]]] = {a[0]: {} for a in anker}
    je_spalte: dict[str, list[tuple]] = {}
    for w in rumpf:
        if w in nummern or any(abs(mitte(w) - s[0]) <= 3 for s in summen):
            continue
        x = w[0]
        if x >= sp["ende"]:
            continue
        spalte = ("bar" if x >= sp["bar"] - 30 and w[4] == "x" else
                  "erlaeuterung" if x >= sp["erlaeuterung"] else
                  "planjahr" if x >= sp["planjahr"] else
                  "vorjahr" if x >= sp["vorjahr"] else
                  "beschreibung" if x >= sp["beschreibung"] else
                  "name" if x >= sp["name"] else
                  "produkt" if x >= sp["produkt"] else "thh")
        je_spalte.setdefault(spalte, []).append(w)
    marken = sorted([(a[0], True) for a in anker] + [(s[0], False) for s in summen])
    for spalte, ws in je_spalte.items():
        for y, gruppe in _zuordnen(ws, marken, mitte).items():
            zellen[y][spalte] = gruppe

    def text(ws: list[tuple]) -> str:
        roh = " ".join(w[4] for w in sorted(ws, key=lambda w: (round(mitte(w) / 3), w[0])))
        # Trennstriche am Zeilenende: „Grundstücks- preise" → „Grundstückspreise";
        # „Bau- und" bleibt, weil danach ein Wort mit Kleinbuchstaben UND ein
        # „und"/„oder" stünde.
        return re.sub(r"(\w)- (?!und\b|oder\b|u\.)(?=[a-zäöüß])", r"\1", roh)

    betraege = _betraege_in_folge(anker, summen, je_spalte, mitte)
    for y, nr, thh in anker:
        z = zellen[y]
        if y in betraege:
            vor_wert, plan_wert = betraege[y]
        else:
            vor = [w for w in z.get("vorjahr", []) if _BETRAG.match(w[4])]
            plan = [w for w in z.get("planjahr", []) if _BETRAG.match(w[4])]
            vor_wert = _wert(vor[0][4]) if vor else None
            plan_wert = _wert(plan[0][4]) if plan else None
        bar = z.get("bar", [])
        aus.zeilen.append(Zuschuss(
            lfd_nr=nr, sub_budget_no=thh,
            product_no=text(z.get("produkt", [])).replace(" ", ""),
            product_name=text(z.get("name", [])),
            description=text(z.get("beschreibung", [])),
            amount_prior=vor_wert,
            amount=plan_wert,
            note=text(z.get("erlaeuterung", [])),
            cash=(bar[0][0] < sp["bar"]) if bar else None,
        ))
    return True


def _betraege_in_folge(anker, summen, je_spalte, mitte) -> dict[float, tuple]:
    """Die Beträge der Reihe nach zuordnen, wo das eindeutig geht.

    2021 stehen die Beträge im Teilhaushalt 10 zwanzig Punkte UNTER ihrer
    Nummer, näher an der nächsten Zeile als an der eigenen — jede
    Nähe-Regel verschiebt sie um eins. Die Reihenfolge verschiebt sich
    nicht: Zwischen zwei Summenzeilen hat jeder Zuschuss genau eine
    Betragszeile. Stimmt die Zahl der Betragszeilen mit der der Zuschüsse
    überein, gilt die Reihenfolge; sonst entscheidet die Nähe (s. o.).
    Ein „-" ist ein ausdrückliches Null."""
    zeilen: list[list[tuple]] = []
    for w in sorted([w for sp in ("vorjahr", "planjahr") for w in je_spalte.get(sp, [])
                     if _BETRAG.match(w[4]) or w[4] == "-"], key=mitte):
        if zeilen and mitte(w) - mitte(zeilen[-1][0]) <= 3:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    grenzen = [s[0] for s in summen] + [float("inf")]
    aus: dict[float, tuple] = {}
    unten = float("-inf")
    for g in grenzen:
        abschnitt = [a[0] for a in anker if unten < a[0] < g]
        betraege = [z for z in zeilen if unten < mitte(z[0]) < g]
        unten = g
        if not abschnitt or len(abschnitt) != len(betraege):
            continue
        for y, z in zip(abschnitt, betraege):
            werte = sorted(z, key=lambda w: w[0])
            if len(werte) != 2:
                break
            aus[y] = tuple(0.0 if w[4] == "-" else _wert(w[4]) for w in werte)
    return aus


def pruefen(aus: Lesung) -> None:
    """Die Probe: je Teilhaushalt ergeben die Zeilen die gedruckte Summe.

    Die laufende Nummer ist KEINE Probe: Die Stadt vergibt sie selbst
    doppelt (2026: 54, 56, 58, 60 und 62 je zweimal) und überspringt welche
    (2025: 43 und 44) — beides steht so im Dokument und gehört in
    ``auffaellig``.

    Eine Summenzeile darf abweichen, wenn ihre Zeilen vollständig sind (jede
    mit Betrag in beiden Spalten): 2020 und 2021 steht unter Teilhaushalt 8
    „Summe 5.000", die drei Zeilen darüber ergeben 17.800 — und die
    Gesamtsumme des Dokuments weicht um genau diese 12.800 € ab. Das ist ein
    Fehler der Vorlage, keiner der Lesung. Fehlt dagegen ein Betrag, ist die
    Abweichung unsere, und der Jahrgang wird verworfen."""
    nummern = sorted(z.lfd_nr for z in aus.zeilen)
    doppelt = sorted({n for n in nummern if nummern.count(n) > 1})
    fehlt = sorted(set(range(1, max(nummern) + 1)) - set(nummern)) if nummern else []
    if doppelt:
        aus.auffaellig.append(f"laufende Nummer doppelt vergeben: {doppelt}")
    if fehlt:
        aus.auffaellig.append(f"laufende Nummer übersprungen: {fehlt}")
    for thh, (vor, plan) in sorted(aus.summen.items()):
        zeilen = [z for z in aus.zeilen if z.sub_budget_no == thh]
        s_vor = sum(z.amount_prior or 0 for z in zeilen)
        s_plan = sum(z.amount or 0 for z in zeilen)
        if abs(s_vor - vor) <= 1 and abs(s_plan - plan) <= 1:
            continue
        satz = (f"THH {thh:02d}: Zeilen {s_vor:,.0f} / {s_plan:,.0f} €, "
                f"Summenzeile {vor:,.0f} / {plan:,.0f} €")
        vollstaendig = all(z.amount_prior is not None and z.amount is not None for z in zeilen)
        if vollstaendig:
            aus.auffaellig.append(f"{satz} — die Summenzeile der Vorlage weicht ab")
        else:
            aus.hinweise.append(satz)
    ohne = sorted({z.sub_budget_no for z in aus.zeilen} - set(aus.summen))
    if ohne:
        aus.hinweise.append(f"ohne Summenzeile: THH {ohne}")


def lies(seiten: list[list[list[tuple]]]) -> Lesung:
    """Alle Seiten eines Dokuments; die Zuschuss-Übersicht ist ein Block.

    Je Seite kommen zwei Fassungen der Wörter (``woerter_aus_pdf``): so, wie
    sie im PDF stehen, und in Leserichtung gedreht. Welche die Tabelle
    waagerecht zeigt, hängt am Jahrgang — 2026 liegen die Wörter ungedreht
    richtig, 2025 erst gedreht. Es gilt die erste, in der der Kopf steht."""
    aus = Lesung()
    angefangen = False
    for fassungen in seiten:
        if any(lies_seite(woerter, aus) for woerter in fassungen):
            angefangen = True
        elif angefangen:
            break
    pruefen(aus)
    return aus


def woerter_aus_pdf(pdf: bytes) -> list[list[list[tuple]]]:
    """Je Seite die Wörter zweimal: ungedreht und in Leserichtung gedreht."""
    import pymupdf  # noqa: PLC0415
    aus = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            roh = [tuple(w[:5]) for w in page.get_text("words")]
            dreh = page.rotation_matrix
            gedreht = []
            for w in roh:
                r = pymupdf.Rect(w[:4]) * dreh
                gedreht.append((r.x0, r.y0, r.x1, r.y1, w[4]))
            # 2022, 2024, 2025: Seite ungedreht, der Text läuft senkrecht von
            # unten nach oben — die Tabelle liegt quer zur Seite. Gekippt
            # (x = Seitenhöhe − y, y = x) steht sie wieder waagerecht.
            hoehe = page.rect.height
            gekippt = [(hoehe - w[3], w[0], hoehe - w[1], w[2], w[4]) for w in roh]
            aus.append([roh, gedreht, gekippt])
    return aus
