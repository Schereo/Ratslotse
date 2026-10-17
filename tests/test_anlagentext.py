"""PDF-Text lesen: PyMuPDF statt pypdf, außer für Haushalts-Anlagen.

Der Anlass (17.10.2026): Im Bestand standen Wörter mit Lücken — „de r“,
„Arbei tsverträge“, „R atsherr“. Das PDF unten stellt die Bauform nach, mit
der Ghostscript (PDF24, damit kommen die Fraktionsanträge) jede Zeile setzt:
die Zeile in zwei ``TJ``-Blöcke geteilt, dazwischen ein ``Td`` an die exakte
Position — mitten im Wort —, und Blocksatz-Abstände zwischen den Buchstaben
des ersten Blocks. Die Messung am Bestand steht in ``council/anlagentext.py``.
"""
from __future__ import annotations

import builtins
import io
import logging

import pytest

from council import anlagentext

ERSTER_TEIL = "laufenden Ratsperiode, die zu einer Verringerung de"
ZWEITER_TEIL = "r personellen Ausstattung"
#: Breite des ersten Blocks in Helvetica 11 pt samt −8/1000 em je Abstand —
#: einmal mit ``pymupdf.get_text_length`` ausgerechnet und hier festgehalten,
#: damit der Test das PDF auch ohne PyMuPDF bauen kann.
SPRUNG = 259.974


def _pdf(*seiten_inhalt: bytes) -> bytes:
    """Ein minimales PDF mit Helvetica, eine Seite je Inhaltsstrom."""
    n = len(seiten_inhalt)
    seiten = " ".join(f"{3 + 2 * i} 0 R" for i in range(n)).encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [" + seiten + b"] /Count %d >>" % n]
    schrift = 3 + 2 * n
    for i, inhalt in enumerate(seiten_inhalt):
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                    % (schrift, 4 + 2 * i))
        objs.append(b"<< /Length %d >>\nstream\n" % len(inhalt) + inhalt + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                b"/Encoding /WinAnsiEncoding >>")
    aus = io.BytesIO()
    aus.write(b"%PDF-1.4\n")
    stellen = []
    for i, o in enumerate(objs, 1):
        stellen.append(aus.tell())
        aus.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = aus.tell()
    aus.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for s in stellen:
        aus.write(b"%010d 00000 n \n" % s)
    aus.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objs) + 1, xref))
    return aus.getvalue()


def _geteilte_zeile() -> bytes:
    tj = " ".join(f"({z}) -8" for z in ERSTER_TEIL[:-1]) + f" ({ERSTER_TEIL[-1]})"
    return f"BT /F1 11 Tf 40 700 Td [{tj}] TJ {SPRUNG} 0 Td [({ZWEITER_TEIL})] TJ ET".encode(
        "latin-1")


def test_pypdf_reisst_das_wort_auf():
    """Hält die Ursache fest. Wird dieser Test rot, hat pypdf seine
    Leerzeichen-Schätzung repariert (``_text_extraction.crlf_space_check``) —
    dann lohnt ein neuer Blick, ob der Haushalt noch an pypdf hängen muss."""
    text = anlagentext.pdf_seiten(_pdf(_geteilte_zeile()), anlagentext.PYPDF)[0]
    assert "Verringerung de r personellen" in text


def test_pymupdf_liest_das_wort_ganz():
    pytest.importorskip("pymupdf")
    text = anlagentext.pdf_seiten(_pdf(_geteilte_zeile()))[0]
    assert "Verringerung der personellen Ausstattung" in text


def test_seiten_enden_ohne_umbruch():
    """Wie bei pypdf: Die Aufrufer verbinden mit ``"\\n"`` und rechnen daraus
    Seiten-Offsets. Ein Umbruch mehr je Seite wäre eine Leerzeile an jeder
    Seitengrenze — und die gilt jedem Absatzschnitt als Absatzende."""
    pytest.importorskip("pymupdf")
    seite = b"BT /F1 11 Tf 40 700 Td (Seite) Tj ET"
    seiten = anlagentext.pdf_seiten(_pdf(seite, seite))
    assert seiten == ["Seite", "Seite"]


def test_ohne_pymupdf_liest_pypdf_weiter(monkeypatch, caplog):
    """PyMuPDF steht in keiner Requirements-Datei. Ein Dienst ohne die
    Bibliothek fällt nicht aus, er liest nur schlechter — und sagt es."""
    echt = builtins.__import__

    def ohne(name, *args, **kwargs):
        if name == "pymupdf":
            raise ImportError("nicht installiert")
        return echt(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", ohne)
    anlagentext._ohne_pymupdf.cache_clear()
    with caplog.at_level(logging.WARNING, logger="council.anlagentext"):
        text = anlagentext.pdf_seiten(_pdf(_geteilte_zeile()))[0]
    assert "Ratsperiode" in text
    assert "PyMuPDF fehlt" in caplog.text
    anlagentext._ohne_pymupdf.cache_clear()


def test_steuerzeichen_kommen_nicht_in_den_bestand():
    """Ein PDF ohne Zeichenzuordnung liefert bei PyMuPDF Glyph-Nummern als
    ``\\x00\\x01…`` — gemessen an Anlage 258443. Die Buchstaben-Schwelle
    erklärt so ein Dokument ohnehin zum Scan, in der Datenbank haben sie
    trotzdem nichts zu suchen."""
    assert anlagentext._STEUERZEICHEN.sub("", "\x00\x01Text\x07\n\tweiter") == "Text\n\tweiter"


@pytest.mark.parametrize(("label", "vorlagentitel", "erwartet"), [
    ("Jahresabschluss 2024 der Stadt Oldenburg", None, anlagentext.PYPDF),
    ("Stellenplan 2026", None, anlagentext.PYPDF),
    ("Antrag CDU Fraktionsbüros", None, anlagentext.PYMUPDF),
    ("Konzept Bolzplatz HES", "Bolzplatz Hermann-Ehlers-Schule", anlagentext.PYMUPDF),
    # Die Gebührenbedarfsberechnung 2021 heißt im RIS nur „Anlagen 1-4“ —
    # erkennbar ist sie allein am Titel ihrer Vorlage.
    ("Anlagen 1-4", "Gebührenbedarfsberechnungen 2021 - Bericht", anlagentext.PYPDF),
    (None, None, anlagentext.PYMUPDF),
])
def test_haushalts_anlagen_bleiben_bei_pypdf(label, vorlagentitel, erwartet):
    """Rund zwanzig Haushalts-Schichten lesen den GESPEICHERTEN Anlagentext mit
    Regexen, die auf pypdfs Zeilenbild abgestimmt sind. Erkannt wird wie in
    ``finanzquellen.finanz_anlagen_where`` — am Label oder am Vorlagentitel."""
    assert anlagentext.extraktor_fuer(label, vorlagentitel) == erwartet
