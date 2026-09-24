"""Der Vorbericht des Haushaltsplans (Anlage 001) — was die Verwaltung zu
jedem Bereich schreibt.

Jeder Haushaltsplan beginnt mit einem Vorbericht von 80 bis 100 Seiten. Zwei
Kapitel gehen Teilhaushalt für Teilhaushalt durch:

* **2.4.2.x** — der Ergebnishaushalt des Teilhaushalts: Was ihn prägt, wo
  Aufwand steigt oder sinkt, und warum („Die Personalaufwendungen im
  Teilhaushalt 06 steigen … um rund 1,0 Millionen Euro").
* **3.2.2.x** — seine Investitionen.

Das ist die Begründung, die im Zahlenwerk nicht steht, in den Worten der
Verwaltung. Die Seite zeigt sie **als Wortlaut**, nie zusammengefasst
(dieselbe Regel wie ``<Warum>``): Eine Zusammenfassung wäre ein Text, den
niemand beschlossen hat.

WIE GELESEN WIRD
----------------

Über die Textblöcke des PDFs — ein Block ist ein Absatz. Ein Abschnitt reicht
von seiner Überschrift („2.4.2.6 Teilhaushalt 06: Kultur, Museen, Sport")
bis zur nächsten Überschrift. Dazwischen stehen Diagramme, deren
Beschriftungen als eigene Blöcke erscheinen (lauter Zahlen, „Ordentliche
Erträge", „Entwicklung der … in Millionen Euro"); sie fliegen heraus. Übrig
bleiben Absätze mit Sätzen.

DIE PROBE ist eine Vollständigkeitsprobe: Das Inhaltsverzeichnis nennt die
Teilhaushalte; jeder genannte muss im Text einen Abschnitt mit mindestens
einem Satz haben.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PROBE_VORBERICHT = "budget_notes_sections"

#: Die beiden Kapitel je Teilhaushalt.
KAPITEL = {"2.4.2": "result", "3.2.2": "investments"}

#: Die Überschrift eines Abschnitts. Ab 2025 steht die Kapitelnummer davor
#: („2.4.2.6 Teilhaushalt 06: …"), 2019 dahinter („… Sport 2.4.2.6"), 2020–2024
#: gar nicht — dann sagt die REIHENFOLGE das Kapitel: Das erste Vorkommen eines
#: Teilhaushalts im Text ist der Ergebnishaushalt, das zweite die Investitionen.
_UEBERSCHRIFT = re.compile(
    r"^\s*(?:(2\.4\.2|3\.2\.2)\.\d{1,2}\.?\s+)?Teilhaushalt\s+(\d{1,2})\s*[:\-–]\s*"
    r"(.+?)(?:\s+(2\.4\.2|3\.2\.2)\.\d{1,2})?\s*$", re.I)
#: Jede andere nummerierte Überschrift beendet einen Abschnitt („3 Gesamtfinanz…").
_ANDERE = re.compile(r"^\s*\d(?:\.\d){0,3}\.?\s+[A-ZÄÖÜ]")
_ZAHL = re.compile(r"^[\s\d.,%€+\-–()]*$")
_GRAFIK = re.compile(r"\(Grafik\s*\d+\)|^\s*Grafik\s*\d+|^\s*Tabelle\s*\d+", re.I)


@dataclass
class Abschnitt:
    kind: str                 # result | investments
    sub_budget_no: int
    title: str
    text: str                 # Absätze, getrennt durch Leerzeile
    page: int                 # erste Seite (1-basiert)


@dataclass
class VorberichtLesung:
    budget_year: int | None = None
    abschnitte: list[Abschnitt] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    im_inhalt: set[tuple[str, int]] = field(default_factory=set)

    @property
    def bestanden(self) -> bool:
        return bool(self.abschnitte) and not self.hinweise


def _ist_absatz(text: str) -> bool:
    """Ein Block, der Satz ist — kein Zahlenblock, keine Diagrammbeschriftung."""
    t = " ".join(text.split())
    if not t or _ZAHL.match(t) or _GRAFIK.search(t):
        return False
    # Diagrammbeschriftungen: kurz und ohne Satzzeichen am Ende.
    if len(t) < 90 and not re.search(r"[.:;!?)]$", t):
        return False
    # Ein Block aus lauter Zahlen mit ein paar Wörtern (Tabellenzeile).
    woerter = t.split()
    zahlen = sum(1 for w in woerter if re.fullmatch(r"[\d.,%+\-–]+", w))
    return zahlen < len(woerter) * 0.5


def _glatt(text: str) -> str:
    """Zeilenumbrüche im Absatz auflösen, Silbentrennung zusammenziehen."""
    t = re.sub(r"(\w)-\n(?=[a-zäöüß])", r"\1", text)
    return " ".join(t.split())


def lies(bloecke_je_seite: list[list[str]]) -> VorberichtLesung:
    """``bloecke_je_seite``: je Seite die Textblöcke in Lesereihenfolge."""
    aus = VorberichtLesung()
    aktuell: Abschnitt | None = None
    absaetze: list[str] = []

    def abschliessen() -> None:
        nonlocal aktuell, absaetze
        if aktuell is not None:
            aktuell.text = "\n\n".join(absaetze)
            aus.abschnitte.append(aktuell)
        aktuell, absaetze = None, []

    vorkommen: dict[int, int] = {}
    inhalt_nr: dict[int, int] = {}
    for nr, bloecke in enumerate(bloecke_je_seite, 1):
        for block in bloecke:
            erste = block.strip().split("\n")[0] if block.strip() else ""
            flach = " ".join(block.split())
            m = _UEBERSCHRIFT.match(flach) if len(flach) < 130 else None
            if m:
                thh = int(m.group(2))
                kapitel = m.group(1) or m.group(4)
                if nr <= 6:
                    # Das Inhaltsverzeichnis: merken, welche Abschnitte es nennt.
                    inhalt_nr[thh] = inhalt_nr.get(thh, 0) + 1
                    aus.im_inhalt.add((KAPITEL[kapitel] if kapitel else
                                       ("result" if inhalt_nr[thh] == 1 else "investments"), thh))
                    continue
                vorkommen[thh] = vorkommen.get(thh, 0) + 1
                kind = (KAPITEL[kapitel] if kapitel else
                        "result" if vorkommen[thh] == 1 else "investments")
                abschliessen()
                aktuell = Abschnitt(kind=kind, sub_budget_no=thh,
                                    title=m.group(3).strip(), text="", page=nr)
                continue
            if aktuell is None:
                if aus.budget_year is None:
                    j = re.search(r"Haushalt(?:splan|sjahr)?\s+(20\d\d)", block)
                    if j:
                        aus.budget_year = int(j.group(1))
                continue
            if _ANDERE.match(erste) and not _ZAHL.match(erste):
                abschliessen()
                continue
            if _ist_absatz(block):
                neu = _glatt(block)
                # Ein Absatz, den ein Seitenumbruch zerschnitten hat: Der
                # vorige endet ohne Satzzeichen („… und für die Sporthalle am"),
                # oder mit Trennstrich („Ausgleichsleistun-").
                if absaetze and absaetze[-1].endswith("-") and neu[:1].islower():
                    absaetze[-1] = absaetze[-1][:-1] + neu
                elif absaetze and not re.search(r"[.:;!?)“\"]$", absaetze[-1]):
                    absaetze[-1] = f"{absaetze[-1]} {neu}"
                else:
                    absaetze.append(neu)
    abschliessen()
    # Doppelte Abschnitte (Inhaltsverzeichnis über mehrere Seiten): der mit Text gilt.
    gesehen: dict[tuple[str, int], Abschnitt] = {}
    for a in aus.abschnitte:
        k = (a.kind, a.sub_budget_no)
        if k not in gesehen or len(a.text) > len(gesehen[k].text):
            gesehen[k] = a
    aus.abschnitte = [a for a in gesehen.values() if a.text]
    fehlt = sorted(aus.im_inhalt - set(gesehen))
    leer = sorted(k for k, a in gesehen.items() if not a.text)
    if fehlt:
        aus.hinweise.append(f"im Inhaltsverzeichnis, aber ohne Abschnitt: {fehlt}")
    if leer:
        aus.hinweise.append(f"Abschnitt ohne Absatz: {leer}")
    return aus


def bloecke_aus_pdf(pdf: bytes) -> list[list[str]]:
    import pymupdf  # noqa: PLC0415 — bewusst optional
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return [[b[4] for b in page.get_text("blocks") if b[6] == 0] for page in doc]
