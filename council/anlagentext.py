"""PDF-Text lesen — und entscheiden, wann er als gelesen gilt.

Zwei Wege laden Anlagen-PDFs: der Backfill (``scripts/backfill_anlagen_texte
.py``, Tausende am Stück) und der MCP-Server (``council/mcp_tools.py``, eine
auf Zuruf eines Agenten). Beide müssen dasselbe Urteil fällen — sonst gilt
dieselbe Anlage je nach Weg als „gelesen“ oder als Scan. Die Schwellen
standen bis 10/2026 im Skript und sind deshalb hierher gezogen; das Skript
importiert sie.

**Welcher Extraktor (seit 10/2026: PyMuPDF, mit pypdf als Rückfall).**
pypdf setzte Leerzeichen mitten ins Wort — „de r“, „Arbei tsverträge“,
„R atsherr“, „S eite“. Das PDF ist daran unschuldig: Ghostscript (PDF24,
damit kommen die Fraktionsanträge) und andere Erzeuger teilen jede Zeile in
zwei ``TJ``-Blöcke und springen dazwischen per ``Td`` an die exakte Position,
oft mitten im Wort. pypdfs ``crlf_space_check`` hält den Sprung für einen
Wortabstand, weil seine Breitenschätzung die Blocksatz-Abstände der
``TJ``-Felder nicht mitzählt. Umgekehrt klebt pypdf Wörter zusammen, wo zwei
Spalten nebeneinanderstehen („Ausnahmesiehe“ in Bebauungsplan-Legenden).

Gemessen an 120 Dokumenten der Prod-Daten (17.10.2026; 25 Protokolle,
40 Vorlagen, 40 Anlagen, 15 Haushalts-Anlagen), je „pypdf → PyMuPDF“:

==================  ===========  ==============================================
Art                 Wortrisse    nachgelagert
==================  ===========  ==============================================
Protokolle          519 → 0      TOP-Schnitt 201/211 → 201/211, Redner-Anker
                                 756 → 781, Seitenzahl gleich
Vorlagen            46 → 0       Ernte (Finanzen, Klima, Amt, Vorschlag)
                                 identisch, Auszug 159.132 → 159.040 Zeichen
Anlagen             147 → 0      Zahlen 1.012 → 1.020 (987 gemeinsam)
Haushalt            209 → 0      Zahlen 25.786 → 25.823 (25.770 gemeinsam)
==================  ===========  ==============================================

(„Wortrisse“: von Hand geprüft, wo die beiden auseinandergehen; die
Gegenrichtung — PyMuPDF trennt, pypdf hat es am Stück — waren durchweg
pypdf-Klebungen.) Dazu ist PyMuPDF 4- bis 30-mal schneller. Wo die
Zeichenzahl abweicht, sind es Grafiken und Pläne, in denen pypdf
Beschriftungen doppelt ausgibt („2026 2026“, „jeje“).

**Haushalts-Anlagen bleiben bei pypdf.** Rund zwanzig Schichten des
Haushalts-Bereichs lesen den GESPEICHERTEN Anlagentext mit Regexen, die auf
pypdfs Zeilenbild abgestimmt sind (``council/stellenplan.py``: „klebt pypdf
die ersten beiden Nummern zusammen“). Dort zählt nicht Lesbarkeit, sondern
dass jede Zahl unter ihrem Jahr landet — und ein neuer Zeilenumbruch kippt
das, ohne dass ein Test es sieht. ``extraktor_fuer`` entscheidet am Label,
mit denselben Mustern, die die Finanz-Registry zum Erkennen benutzt.

**PyMuPDF ist optional.** Es steht in ``constraints.txt``, aber in keiner
Requirements-Datei (AGPL; auf dem Server von Hand installiert). Fehlt es,
liest ``pdf_seiten`` mit pypdf weiter und sagt das einmal im Log — ein
Dienst ohne die Bibliothek fällt also nicht aus, er liest nur schlechter.
"""
from __future__ import annotations

import io
import logging
import re
from functools import lru_cache

import pypdf

from council.kontaktdaten import entfernen

logger = logging.getLogger("council.anlagentext")

#: Steuerzeichen, die ein PDF ohne Zeichenzuordnung liefert (PyMuPDF gibt die
#: Glyph-Nummern als ``\x00\x01…`` heraus, pypdf als „/0 /1“). Sie haben in
#: der Datenbank nichts zu suchen; die Buchstaben-Schwelle unten erklärt so ein
#: Dokument ohnehin zum Scan.
_STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

PYMUPDF = "pymupdf"
PYPDF = "pypdf"

# ---- Ligaturen -----------------------------------------------------------------
#
# Word legt beim PDF-Export aus Calibri eigene Glyphen für „ti", „ft", „tt"
# und „tf" an — und schreibt in die Zuordnungstabelle der Schrift Buchstaben
# aus Latin Extended-B: „städƟschen", „WirtschaŌsplan", „MiƩel", „enƞällt".
# Jeder Leser gibt das so heraus, die Datei ist schuld. Gemessen auf dev
# (23.11.2026): 20 von 6.779 Anlagen, darunter alle Quartalsberichte der
# Beteiligungen seit 2021 — mit 192-mal „WirtschaŌsplan" und 143-mal
# „städƟschen". Die Folgen: Die Volltextsuche findet „Wirtschaftsplan" dort
# nicht, und ein Modell, das beim Zitieren das Wort richtig schreibt, verliert
# den Beleg.
#
# Eine andere Schrift im selben Bericht ordnet dieselben Glyphen Ziffern und
# Satzzeichen zu: „durchschni0liche", „Wirtscha)splan", „vermi<elt". Das zeigte die
# Punkt-Seite des Quartalsberichts 30.09.2026 im Zitat (Tim, 23.11.2026). Hier
# entscheidet nicht das Zeichen, sondern das Wort — „(teil)funktion",
# „Benzo(a)pyren" und „und/oder" sind richtig. Ersetzt wird deshalb nur, wenn genau eine
# Ligatur ein Wortstück ergibt, das im selben Dokument richtig geschrieben
# steht.
#
# Nicht zu retten sind Glyphen, die gar kein Zeichen tragen („bestägt",
# „Staon"): Dort fehlt jeder Hinweis, wo etwas fehlt. Damit ein richtig
# abgeschriebenes Zitat trotzdem belegt bleibt, vergleicht
# ``council/evidence.py::locate`` im zweiten Versuch ohne Ligatur-Paare.

#: Falsch zugeordnete Ligaturen — eindeutig, sobald ein Kleinbuchstabe daneben steht.
_FALSCHE_LIGATUREN = {"Ɵ": "ti", "Ō": "ft", "Ʃ": "tt", "ƞ": "tf"}
#: Echte Ligaturzeichen (Unicode-Block „Alphabetic Presentation Forms").
_ECHTE_LIGATUREN = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
_KLEIN = "a-zäöüß"
_FALSCH_RE = re.compile(f"(?<=[{_KLEIN}])[ƟŌƩƞ]|[ƟŌƩƞ](?=[{_KLEIN}])")
#: Ein Wort mit Ziffer, Klammer, Schrägstrich oder Spitzklammer zwischen zwei
#: Kleinbuchstaben — jede Schrift wählt ein anderes Zeichen: „durchschni0liche",
#: „Wirtscha)splan", „Wirtscha/splan", „überschri9en", „vermi<elt" (Quartals-
#: berichte 2024–2026). Aber nicht in einer Adresse: Im Bestand wurde sonst aus
#: „….niedersachsen.de/niedersaechsischer…" ein „definiedersaechsischer…"
#: (Trockenlauf über dev, 23.11.2026).
_PLATZHALTER = "0123456789)/<>]|"
_PLATZHALTER_RE = re.compile(f"(?<![\\w./:@-])[A-Za-zÄÖÜäöüß]*[{_KLEIN}][{re.escape(_PLATZHALTER)}][{_KLEIN}]++(?![/@]|\\.\\w)")
_LIGATUR_KANDIDATEN = ("tt", "ft", "ti", "tf", "fi", "fl", "ff", "ffi", "ffl")
#: So viele Buchstaben links und rechts der Lücke muss das Dokument richtig
#: geschrieben tragen — genug, dass „chnittlic" nur zu „durchschnittlich" passt.
_UMFELD_LINKS, _UMFELD_RECHTS = 4, 3


def ligaturen_reparieren(seiten: list[str]) -> list[str]:
    """Ligaturen auflösen, Seite für Seite — die Seitengrenzen bleiben, wo sie
    sind; die Aufrufer rechnen die Offsets erst danach."""
    seiten = [_FALSCH_RE.sub(lambda m: _FALSCHE_LIGATUREN[m.group(0)], s).translate(_ECHTE_LIGATUREN)
              for s in seiten]
    if not any(_PLATZHALTER_RE.search(s) for s in seiten):
        return seiten
    klein = "\n".join(seiten).lower()

    def ersetzen(m: re.Match) -> str:
        wort = m.group(0)
        i = next(k for k, ch in enumerate(wort) if ch in _PLATZHALTER)
        links = wort[max(0, i - _UMFELD_LINKS):i].lower()
        rechts = wort[i + 1:i + 1 + _UMFELD_RECHTS].lower()
        if len(links) < 3 or len(rechts) < 2:
            return wort
        passend = [e for e in _LIGATUR_KANDIDATEN if f"{links}{e}{rechts}" in klein]
        if len(passend) != 1:   # keins oder mehrdeutig: lieber stehen lassen
            return wort
        return wort[:i] + passend[0] + wort[i + 1:]

    return [_PLATZHALTER_RE.sub(ersetzen, s) for s in seiten]


def gespeicherten_text_reparieren(text: str, offsets: list[int] | None) -> tuple[str, list[int] | None]:
    """Ligaturen in einem schon gespeicherten Text auflösen — Seite für Seite,
    mit den neuen Seitenanfängen (``council_documents.page_offsets``): Aus
    „Ɵ" werden zwei Zeichen, jede folgende Seite rückt also nach hinten."""
    if not offsets:
        return ligaturen_reparieren([text])[0], offsets
    grenzen = [0, *offsets, len(text)]
    stuecke = ligaturen_reparieren([text[grenzen[i]:grenzen[i + 1]] for i in range(len(grenzen) - 1)])
    neu: list[int] = []
    pos = len(stuecke[0])   # was vor der ersten Seite steht (meist nichts)
    for s in stuecke[1:]:
        neu.append(pos)
        pos += len(s)
    return "".join(stuecke), neu


def pdf_seiten(daten: bytes, extraktor: str = PYMUPDF) -> list[str]:
    """Der Text eines PDF, Seite für Seite, Ligaturen aufgelöst.

    Seiten enden ohne Zeilenumbruch, wie bei pypdf — die Aufrufer verbinden
    mit ``"\n"`` und rechnen daraus Seiten-Offsets
    (``protocols.page_offsets``). Ein zusätzlicher Umbruch je Seite hieße eine
    Leerzeile an jeder Seitengrenze, und die gilt jedem Absatzschnitt als
    Absatzende."""
    if extraktor == PYMUPDF:
        try:
            import pymupdf  # noqa: PLC0415 — optional, s. Modulkopf
        except ImportError:
            _ohne_pymupdf()
        else:
            with pymupdf.open(stream=daten, filetype="pdf") as dok:
                return ligaturen_reparieren(
                    [_STEUERZEICHEN.sub("", str(s.get_text())).rstrip("\n") for s in dok])
    leser = pypdf.PdfReader(io.BytesIO(daten))
    return ligaturen_reparieren([_STEUERZEICHEN.sub("", s.extract_text() or "") for s in leser.pages])


@lru_cache(maxsize=1)
def _ohne_pymupdf() -> None:
    logger.warning("PyMuPDF fehlt — PDF-Text wird mit pypdf gelesen (Wortrisse wie "
                   "„de r“ möglich). pip install pymupdf -c constraints.txt")


def finanz_muster() -> list[str]:
    """Die Label-Muster der Finanzschichten (SQL-``LIKE``) — aus der Registry,
    nicht doppelt.

    Der Haushalts-Bereich liest sieben Schichten aus Anlagen (Jahresabschluss,
    Teilhaushalte, Stellenplan, …). Die Muster stehen in ``finanzquellen`` —
    hier nur geholt, damit sie nicht an zwei Stellen gepflegt werden müssen.
    Bis 10/2026 stand diese Funktion im Backfill-Skript."""
    from council import finanzquellen as fq  # noqa: PLC0415 — schwer, nur bei Bedarf

    muster: list[str] = []
    for key in fq.REIHENFOLGE:
        erkennung = getattr(fq.QUELLEN[key], "erkennung", None)
        if erkennung is None:
            continue
        muster.extend(getattr(erkennung, "label_muster", None) or ())
    return sorted(set(muster))


def _like_regex(muster: list[str]) -> re.Pattern:
    # SQL-LIKE nachgebaut: ``%`` beliebig viel, ``_`` genau ein Zeichen, ohne
    # Unterschied der Groß-/Kleinschreibung (wie LIKE in SQLite).
    teile = ["".join(".*" if z == "%" else "." if z == "_" else re.escape(z) for z in m)
             for m in muster]
    return re.compile("|".join(f"(?:{t})" for t in teile) or r"(?!)", re.IGNORECASE | re.DOTALL)


@lru_cache(maxsize=1)
def _finanz_regexe() -> tuple[re.Pattern, re.Pattern]:
    """(Label, Vorlagentitel) — dieselben zwei Musterlisten, aus denen
    ``finanzquellen.finanz_anlagen_where`` sein ODER baut."""
    from council import finanzquellen as fq  # noqa: PLC0415

    titel: list[str] = []
    for key in fq.REIHENFOLGE:
        e = fq.QUELLEN[key].erkennung
        if e is not None:
            titel.extend(e.vorlagen_muster)
    return _like_regex(finanz_muster()), _like_regex(sorted(set(titel)))


def extraktor_fuer(label: str | None, vorlagentitel: str | None = None) -> str:
    """pypdf für Anlagen, die eine Haushalts-Schicht füllen könnten (ihre
    Parser sind darauf abgestimmt, s. Modulkopf), PyMuPDF für alles andere.

    Erkannt wie in ``finanzquellen.finanz_anlagen_where``: am Label ODER am
    Titel der Vorlage, an der die Anlage hängt — die Gebührenbedarfsberechnung
    2021 heißt im RIS nur „Anlagen 1-4“, ihre Vorlage aber
    „Gebührenbedarfsberechnungen 2021 - Bericht“."""
    nach_label, nach_titel = _finanz_regexe()
    if (label and nach_label.fullmatch(label)) or (vorlagentitel and nach_titel.fullmatch(vorlagentitel)):
        return PYPDF
    return PYMUPDF

MIN_TEXT = 200          # darunter gilt das PDF als Scan/Bild ('empty')

#: Mindestanteil echter Buchstaben. Darunter ist die Zeichenzuordnung der PDF
#: kaputt, und was herauskommt, ist kein Text.
#:
#: DER FALL, DER DIESE SCHWELLE ERZWUNGEN HAT: Der Schlussbericht des
#: Rechnungsprüfungsamts zum Jahresabschluss 2024 (Dokument 295296) liefert
#: 460.084 Zeichen — und **keinen einzigen Buchstaben**. Seine Schrift bringt
#: keine ToUnicode-Tabelle mit, deshalb extrahiert pypdf die Glyph-Nummern
#: („/1 /2 /3 …") und Kästchen. Ohne diese Prüfung stünden 460 KB Rauschen in
#: der Datenbank, im Volltextindex und damit in den Treffern der KI-Frage —
#: und der Bericht sähe aus, als sei er gelesen worden.
#:
#: 0,05 IST GEMESSEN, NICHT GEGRIFFEN: Über die 558 Anlagen mit Volltext liegt
#: der Median bei 0,69, das erste Perzentil bei 0,32. Unterhalb von 0,12 liegen
#: genau zwei Dokumente — die beiden kaputten. Die Schwelle hat also nach oben
#: den doppelten Abstand zum nächsten echten Dokument.
MIN_BUCHSTABEN = 0.05

#: Obergrenze je Anlage. Kappt Extrem-PDFs, damit ein einzelnes Gutachten die
#: Datenbank nicht aufbläht.
#:
#: WARUM 800.000 UND NICHT MEHR 400.000. Bei 400.000 endeten die
#: Jahresabschlüsse mitten im Dokument — und zwar ausgerechnet vor Abschnitt 8
#: („Anlagen zum Anhang" mit Anlagen-, Forderungs-, Schulden- und
#: Rückstellungsübersicht). Für 2022 ließ sich das nachweisen: Die Abschnitte
#: 8.3 und 8.4 stehen bei 70 % des Textes, der Schnitt lag bei 56 %.
#:
#: Der Preis ist klein, weil die Grenze fast niemanden trifft: Von 6.366
#: Anlagen mit Volltext standen **23** exakt an ihr, davon acht die
#: Jahresabschlüsse (gemessen 18.08.2026). Die längste ist der Abschluss 2022
#: mit 709.076 Zeichen; 800.000 nimmt sie vollständig auf und lässt Luft für
#: einen dickeren Jahrgang, ohne dass jemand die Zahl wieder anfassen muss.
#: In einer 263-MB-Datenbank kostet das rund 7 MB.
MAX_TEXT = 800_000


def buchstabenanteil(text: str) -> float:
    """Wie viel des Textes wirklich aus Buchstaben besteht (0 bis 1)."""
    return sum(ch.isalpha() for ch in text) / len(text) if text else 0.0


def beurteilen(text: str | None) -> str:
    """Der Text, wie er gespeichert wird — oder ``""``, wenn das PDF als
    Scan bzw. kaputte Zeichenzuordnung gilt (Status ``empty``).

    Kontonummern und Anschriften fallen schon hier heraus (``entfernen``):
    Was beim Speichern gestrichen ist, kann kein späterer Weg ausgeben."""
    t = entfernen((text or "").strip())[:MAX_TEXT]
    if t and buchstabenanteil(t) < MIN_BUCHSTABEN:
        return ""
    return t if len(t) >= MIN_TEXT else ""
