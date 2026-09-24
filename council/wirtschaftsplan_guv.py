"""Wirtschaftspläne in GuV-Form — Bäderbetriebsgesellschaft (BBGO) und
Bäderbetrieb (BBO).

``council/wirtschaftsplan_tabelle.py`` liest Erfolgspläne, die ihre Summen
selbst ausweisen („Summe Erträge", „Summe Aufwendungen"). Die Bäder tun das
nicht: Ihr Wirtschaftsplan ist eine betriebswirtschaftliche Übersicht,
Zeile für Zeile — Umsatzerlöse, Gesamtleistung, Materialaufwand, Rohertrag,
Personal, Raum/Energie …, Gesamtkosten, Operatives Ergebnis, Zinsen,
Neutrale Erträge, Jahresüberschuss/-fehlbetrag —, je Zeile sieben Spalten
(Ist, Hochrechnung, Plan des Vorjahres, Plan und drei Jahre Vorausschau),
bei der BBGO zwischen jeder Spalte noch ein Anteil in Prozent.

WIE GELESEN WIRD
----------------

Die Zeilen kommen aus den Wortrahmen des PDFs
(``eigenbetriebe_abschluss.text_aus_wortrahmen``). Gelesen wird die erste
Tabelle, die mit „Umsatzerlöse" beginnt, bis zur Zeile
„Jahresüberschuss / -fehlbetrag". Zwischensummen (Gesamtleistung, Rohertrag,
Gesamtkosten, Operatives Ergebnis) und „davon"-Zeilen zählen nicht; die
übrigen Zeilen sind die Posten. Posten mit „Erlöse"/„Erträge" im Namen stehen
auf der Ertragsseite, alle anderen auf der Aufwandsseite — jeweils mit ihrem
Vorzeichen, sodass ein positiver Aufwandsposten (eine Gutschrift) die
Aufwendungen mindert, statt als Ertrag zu erscheinen.

DIE PROBE: In JEDER Spalte ergeben die Posten den ausgewiesenen
Jahresüberschuss. Das sind sieben Proben je Plan; die gespeicherte Zahl ist
nur die Spalte des Planjahres. Dazu die Kernzahl aus dem Beschlusstext
(``wirtschaftsplan_kernzahl``), die schon im Bestand steht: Das Ergebnis der
Tabelle muss sie treffen.

Der Bäderbetrieb (BBO) weist immer 0 € aus — er gleicht den Fehlbetrag
seiner Tochter über „Neutrale Erträge" aus und reicht ihn als „Abschreibungen
Finanzanlagen" weiter. Das ist die Konstruktion, kein Lesefehler; die
Erträge und Aufwendungen sagen trotzdem, wie groß der Betrieb ist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from council.herkunft import Herkunft

PROBE_GUV = "business_plan_guv_columns"

#: Zeilen, die Zwischensummen sind oder Teile eines Postens darüber.
_ZWISCHEN = re.compile(
    r"^(?:Gesamtleistung|Rohertrag|Gesamtkosten|Operatives Ergebnis|Kostenarten|"
    r"Gesamtergebnis|Neutrales Ergebnis|Ergebnis vor|Summe|-->|davon|Jahresüberschuss)", re.I)
#: Posten auf der Ertragsseite.
_ERGEBNIS = re.compile(r"^Jahres(?:überschuss|fehlbetrag|verlust|ergebnis)", re.I)
_ERTRAG = re.compile(r"Umsatzerl|Ertr[äa]g|Bestandsver|Aktivierte", re.I)
_BETRAG = re.compile(r"^-?\d{1,3}(?:\.\d{3})*$")
_PROZENT = re.compile(r"^-?\d{1,3},\d$")      # „-61,2" — eine Nachkommastelle
_CENT = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")  # „-21.776,46"
_JAHR = re.compile(r"^20\d\d$")
TOLERANZ_EUR = 2.0


class GuvFehler(ValueError):
    """Die Tabelle ist da, aber sie geht nicht auf."""


@dataclass
class GuvLesung:
    jahre: list[int] = field(default_factory=list)
    spalte: int = 0
    revenues: float | None = None
    expenses: float | None = None
    result: float | None = None
    proben: int = 0
    #: Spalten außer der des Planjahres, deren Posten den ausgewiesenen
    #: Jahresüberschuss NICHT ergeben — ein Rechenfehler der Vorlage in einer
    #: Vorausschau-Spalte (BBGO 2026, Spalte 2027: „Operatives Ergebnis" um
    #: 1 Mio. € daneben). Vermerkt, nicht verworfen.
    abweichend: list[str] = field(default_factory=list)
    posten: list[tuple[str, float]] = field(default_factory=list)
    #: Welche Zeilen die Tabelle belegt (Index der ersten und letzten).
    zeilen_von: int = 0
    zeilen_bis: int = 0


Wort = tuple[float, float, str]          # linke Kante, rechte Kante, Text
Zeile = list[Wort]


def zeilen_aus_pdf(pdf: bytes, gekippt: bool = False) -> list[Zeile]:
    """Die Zeilen aller Seiten, je Wort mit linker und rechter Kante.

    Die Spalten stehen rechtsbündig; eine leere Zelle lässt in der Zeile
    eine Lücke, die ein reiner Text nicht zeigt („Bestandsveränderungen
    0 0,0 5.000 0,1 0 0,0 0 0,0" — vier Zellen von acht). Über die rechte
    Kante findet jeder Betrag seine Spalte trotzdem."""
    import pymupdf  # noqa: PLC0415 — bewusst optional wie in eigenbetriebe_abschluss
    aus: list[Zeile] = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            dreh = page.rotation_matrix
            hoehe = page.rect.height
            if gekippt:
                # Text läuft senkrecht auf einer hochkant gesetzten Seite (BBGO
                # 2023): x = Seitenhöhe − y, y = x stellt die Tabelle wieder hin.
                woerter = sorted((round(float(w[2]), 1), hoehe - float(w[3]),
                                  hoehe - float(w[1]), str(w[4]))
                                 for w in page.get_text("words"))
            else:
                woerter = sorted(
                    (round(r.y1, 1), r.x0, r.x1, w[4])
                    for w in page.get_text("words")
                    for r in (pymupdf.Rect(w[:4]) * dreh,))
            seite: list[tuple[float, Zeile]] = []
            for y, x0, x1, t in woerter:
                if seite and abs(y - seite[-1][0]) <= 2.5:
                    seite[-1][1].append((x0, x1, t))
                else:
                    seite.append((y, [(x0, x1, t)]))
            aus.extend(sorted(z) for _y, z in seite)
    return aus


def _betrag(t: str) -> float | None:
    if _BETRAG.match(t):
        return float(t.replace(".", ""))
    if _CENT.match(t):
        return float(t.replace(".", "").replace(",", "."))
    return None


def lies_guv(zeilen: list[Zeile], budget_year: int,
             ergebnis_soll: float | None = None) -> GuvLesung:
    """Die erste GuV-Tabelle eines Wirtschaftsplans; wirft ``GuvFehler``,
    wenn die Spalte des Planjahres nicht aufgeht."""
    def label_von(z: Zeile) -> str:
        teile: list[str] = []
        for _x0, _x1, t in z:
            if _betrag(t) is not None or _PROZENT.match(t):
                break
            if t not in ("EUR", "€"):
                teile.append(t)
        # „1. Umsatzerlöse", „7. Jahresverlust" — die HGB-Gliederung des Hafens.
        return re.sub(r"^\d{1,2}\.\s*", "", " ".join(teile))

    def betraege(z: Zeile) -> list[tuple[float, float]]:
        """(rechte Kante, Betrag) — ohne Prozentspalten."""
        return [(x1, b) for _x0, x1, t in z
                if not _PROZENT.match(t) and (b := _betrag(t)) is not None]

    start = next((i for i, z in enumerate(zeilen)
                  if label_von(z).startswith("Umsatzerlöse") and len(betraege(z)) >= 4), None)
    if start is None:
        raise GuvFehler("keine Tabelle, die mit „Umsatzerlöse“ beginnt")
    # Die Spalten: die rechten Kanten der Beträge in der Umsatzerlöse-Zeile.
    kanten = [x1 for x1, _b in betraege(zeilen[start])]
    # Ihre Jahre: die Jahreszahl im Kopf DARÜBER, gefunden über die Lage —
    # der Kopf läuft über mehrere Zeilen („Plan 2024 Plan 2025 …" in der
    # einen, „rechnung 2023 Plan 2024 …" in der nächsten), und welche Zeile
    # welche Spalte beschriftet, sagt nur die x-Position.
    jahre: list[int] = []
    for k in kanten:
        treffer = [(abs(x1 - k), -i, int(t))
                   for i, z in enumerate(zeilen[max(0, start - 8):start])
                   for _x0, x1, t in z if _JAHR.match(t) and abs(x1 - k) <= 22]
        if not treffer:
            break
        jahre.append(min(treffer)[2])
    if len(jahre) < 4:
        # Mittig gesetzte Köpfe (BBO 2019–2021) treffen keine rechte Kante;
        # dann gilt die unterste Kopfzeile mit genug Jahreszahlen, der Reihe nach.
        for z in reversed(zeilen[max(0, start - 8):start]):
            js = [int(t) for _a, _b, t in z if _JAHR.match(t)]
            if len(js) >= min(4, len(kanten)):
                jahre = js[:len(kanten)]
                break
    n = len(jahre)
    kanten = kanten[:n]
    if n < 4:
        raise GuvFehler(f"Tabellenkopf: nur {n} Spalten mit Jahreszahl")
    if budget_year not in jahre:
        raise GuvFehler(f"das Planjahr {budget_year} steht nicht im Kopf {jahre}")
    aus = GuvLesung(jahre=jahre, spalte=jahre.index(budget_year))
    ergebnis: list[float] | None = None
    ertrag = [0.0] * n
    aufwand = [0.0] * n
    aus.zeilen_von = start
    for nr, z in enumerate(zeilen[start:start + 90], start):
        aus.zeilen_bis = nr
        label = label_von(z)
        if not label or label.startswith("#"):
            continue
        werte = [0.0] * n
        for x1, b in betraege(z):
            i = min(range(n), key=lambda k: abs(kanten[k] - x1))
            if abs(kanten[i] - x1) <= 12:
                werte[i] = b
        if _ERGEBNIS.match(label):
            ergebnis = werte
            break
        if _ZWISCHEN.match(label):
            continue
        aus.posten.append((label, werte[aus.spalte]))
        ziel = ertrag if _ERTRAG.search(label) else aufwand
        for i, w in enumerate(werte):
            ziel[i] += w
    if ergebnis is None:
        raise GuvFehler("keine Zeile „Jahresüberschuss / -fehlbetrag“")
    # Zwei Vorzeichen-Konventionen: die Bäder schreiben Aufwand negativ
    # (Ergebnis = Summe aller Posten), der Hafen nach HGB positiv (Ergebnis =
    # Erträge − Aufwendungen). Welche gilt, entscheidet die Spalte des
    # Planjahres — und dann gilt sie für alle Spalten.
    # Steht das Planjahr mehrfach im Kopf (eine Anpassung führt den
    # ursprünglichen und den angepassten Plan nebeneinander), entscheidet der
    # Beschlusstext: Es gilt die Spalte, deren Ergebnis er nennt.
    if ergebnis_soll is not None:
        kandidaten = [i for i, j in enumerate(aus.jahre) if j == budget_year
                      and abs(ergebnis[i] - ergebnis_soll) <= TOLERANZ_EUR]
        if kandidaten:
            aus.spalte = kandidaten[0]
    s0 = aus.spalte
    if abs(ertrag[s0] + aufwand[s0] - ergebnis[s0]) > TOLERANZ_EUR \
            and abs(ertrag[s0] - aufwand[s0] - ergebnis[s0]) <= TOLERANZ_EUR:
        aufwand = [-a for a in aufwand]
    for i in range(n):
        if abs(ertrag[i] + aufwand[i] - ergebnis[i]) <= TOLERANZ_EUR:
            aus.proben += 1
            continue
        satz = (f"Spalte {aus.jahre[i]}: Posten ergeben {ertrag[i] + aufwand[i]:,.0f} €, "
                f"ausgewiesen {ergebnis[i]:,.0f} €")
        if i == aus.spalte:
            raise GuvFehler(satz)
        aus.abweichend.append(satz)
    s = aus.spalte
    aus.revenues, aus.expenses, aus.result = ertrag[s], -aufwand[s], ergebnis[s]
    return aus


def lies_guv_pdf(pdf: bytes, budget_year: int,
                 ergebnis_soll: float | None = None) -> GuvLesung:
    """Wie ``lies_guv``, direkt aus dem PDF — erst aufrecht, dann gekippt."""
    try:
        return lies_guv(zeilen_aus_pdf(pdf), budget_year, ergebnis_soll)
    except GuvFehler as aufrecht:
        try:
            return lies_guv(zeilen_aus_pdf(pdf, gekippt=True), budget_year, ergebnis_soll)
        except GuvFehler:
            raise aufrecht from None


def herkunft_fuer(lesung: GuvLesung, *, label: str, jahr: int, url: str | None,
                  document_id: int | None, kernzahl_geprueft: bool) -> Herkunft:
    """Die Herkunft einer aus der GuV-Übersicht ergänzten Zeile: die Anlage."""
    from council.wirtschaftsplan_kernzahl import PROBE_KERNZAHL  # noqa: PLC0415
    ergebnis = f"{lesung.proben} von {len(lesung.jahre)} Spalten gehen auf"
    if lesung.abweichend:
        ergebnis += "; an der Vorlage auffällig: " + "; ".join(lesung.abweichend)
    return Herkunft(
        kind="ris",
        probe=[PROBE_GUV, PROBE_KERNZAHL] if kernzahl_geprueft else [PROBE_GUV],
        document_id=document_id, url=url, label=label,
        citation="Ergebnisplanung des Wirtschaftsplans (Spalte des Planjahres)",
        probe_result=ergebnis,
        as_of=f"Wirtschaftsplan {jahr}",
    )
