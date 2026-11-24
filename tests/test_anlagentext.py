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


# ---- Ligaturen -----------------------------------------------------------------
# Wörtlich aus dem Quartalsbericht der Beteiligungen zum 30.09.2026 (Anlage
# 316197, Vorlage 26/0818): Seite 3 trägt die Calibri-Ligaturen als Buchstaben
# aus Latin Extended-B, Seite 4 dieselben Glyphen als „0" und „)", Seite 5 ist
# sauber. Das Zitat „Der durchschni0liche Casemix …" stand so auf der Punkt-Seite.
_QUARTAL = [
    "Bericht zum 3. Quartal 2026 der städƟschen Beteiligungsunternehmen BäderbetriebsgesellschaŌ "
    "Oldenburg mbH (BBGO) Gemäß Hochrechnung werden die geplanten Umsatzerlöse voraussichtlich um "
    "758.393 Euro unterschriƩen. Die prognosƟzierte Abweichung ist auf die WiƩerungseinﬂüsse "
    "zurückzuführen. Die Aufwendungen enƞallen.",
    "Die aktuelle Hochrechnung bestägt im Ergebnis den Wirtscha)splan 2026. Der durchschni0liche "
    "Casemix für die Kalenderwochen 2 bis 39 liegt bei 783 Punkten. Benzo(a)pyren, (teil)funktion.",
    "Dennoch besuchen durchschnittlich 269 Gäste pro Tag die Touristinfo. Der Wirtschaftsplan wird eingehalten.",
]


def test_falsch_zugeordnete_ligaturen_werden_aufgeloest():
    s = anlagentext.ligaturen_reparieren(_QUARTAL)
    assert "städtischen" in s[0] and "Bäderbetriebsgesellschaft" in s[0] and "unterschritten" in s[0]
    assert "prognostizierte" in s[0] and "Witterungseinflüsse" in s[0] and "entfallen" in s[0]


def test_ziffer_und_klammer_nur_wo_das_dokument_das_wort_kennt():
    s = anlagentext.ligaturen_reparieren(_QUARTAL)
    assert "durchschnittliche Casemix" in s[1]          # „durchschnittlich" steht auf Seite 3
    assert "Wirtschaftsplan 2026" in s[1]               # „Wirtschaftsplan" auf Seite 3
    assert "Benzo(a)pyren" in s[1] and "(teil)funktion" in s[1]   # richtig geschriebene Klammern bleiben
    assert "bestägt" in s[1]                             # ohne Zeichen kein Hinweis — bleibt, wie es ist
    # Adressen bleiben, auch wenn das Dokument das Wort richtig kennt (Review 23.11.2026:
    # ohne possessiven Quantor umging das Zurückgehen die Sperre).
    s = anlagentext.ligaturen_reparieren(["Der Wirtschaftsplan. Ablage wirtscha/splan/entwurf.pdf, "
                                          "Post an wirtscha/splan@example.org, abc/defgh.html"])[0]
    assert "wirtscha/splan/entwurf.pdf" in s and "wirtscha/splan@example.org" in s
    # Ohne Gegenstück im Dokument wird nicht geraten.
    assert anlagentext.ligaturen_reparieren(["Der durchschni0liche Wert."]) == ["Der durchschni0liche Wert."]


def test_buchstaben_aus_latin_extended_ohne_kleinbuchstaben_daneben_bleiben():
    assert anlagentext.ligaturen_reparieren(["ŌSAKA – Ō."]) == ["ŌSAKA – Ō."]
    assert anlagentext.ligaturen_reparieren(["Ɵef"]) == ["tief"]


def test_gespeicherter_text_behaelt_seine_seiten():
    offsets, text = [], ""
    for s in ["Vorspann ", *_QUARTAL]:
        offsets.append(len(text))
        text += s + "\n"
    offsets = offsets[1:]               # der Vorspann steht vor der ersten Seite
    neu, neu_off = anlagentext.gespeicherten_text_reparieren(text, offsets)
    assert neu.startswith("Vorspann ") and len(neu_off) == 3
    assert neu[neu_off[1]:].startswith("Die aktuelle Hochrechnung")
    assert neu[neu_off[2]:].startswith("Dennoch besuchen")
    assert anlagentext.gespeicherten_text_reparieren("städƟsch", None) == ("städtisch", None)


def test_pdf_seiten_loest_ligaturen_auf(monkeypatch):
    """Neue Texte kommen schon repariert in den Bestand — für beide Leser."""
    monkeypatch.setattr(anlagentext, "_STEUERZEICHEN", __import__("re").compile("(?!)"))
    seiten = anlagentext.pdf_seiten(_pdf(b"BT /F1 11 Tf 40 700 Td (Pflege) Tj ET"), anlagentext.PYPDF)
    assert seiten == anlagentext.ligaturen_reparieren(seiten)
