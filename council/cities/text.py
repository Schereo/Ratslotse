"""PDF → Text. Eine abgeleitete Sicht, deshalb versioniert.

Heute ``pypdf``, morgen vielleicht ein Layout-Parser, der Tabellen und den
Abschnitt „Beschlussvorschlag" erkennt, übermorgen OCR für die Dokumente ohne
Textebene. Weil die Bytes in der Rohablage liegen, ist jede Verbesserung ein
neuer Lauf über den vorhandenen Bestand — kein erneuter Abruf bei den Städten.

``quality`` sagt, ob sich der zweite Blick lohnt: ``empty`` heißt „hier war
keine Textebene", und genau diese Dateien holt ein OCR-Lauf später hervor.
"""
from __future__ import annotations

import io
import logging
import re

EXTRACTOR = "pypdf"
VERSION = "1"

MAX_PAGES = 60
MAX_CHARS = 80_000
#: Ab so vielen Zeichen je Seite gilt eine Textebene als brauchbar. Darunter
#: ist es meist ein Scan mit ein paar Kopfzeilen.
MIN_CHARS_PER_PAGE = 200

logger = logging.getLogger("council.cities.text")

#: Seitenköpfe und -füße, die pypdf zwischen den Inhalt mischt. Dieselben
#: Muster wie in ``council/vorlagen.py``, ergänzt um die der anderen Systeme.
_NOISE = re.compile(
    r"^(?:Seite:?\s*\d+\s*/\s*\d+.*|Ausdruck vom:.*|Vorlagen?-?\s*Nr\.?:.*"
    r"|\d+\s+von\s+\d+\s+in\s+Zusammenstellung|\s*-\s*\d+\s*-\s*)$",
    re.MULTILINE)


def clean(text: str) -> str:
    text = _NOISE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract(pdf_bytes: bytes) -> tuple[str, int | None, str]:
    """``(text, seiten, qualität)`` — ``qualität`` ist ok | thin | empty | error."""
    try:
        import pypdf
    except ImportError:  # pragma: no cover — pypdf steht in requirements.txt
        return "", None, "error"
    try:
        leser = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        seiten = len(leser.pages)
        stuecke = []
        for seite in leser.pages[:MAX_PAGES]:
            try:
                stuecke.append(seite.extract_text() or "")
            except Exception:  # noqa: BLE001 — eine kaputte Seite, nicht das Dokument
                continue
        text = clean("\n".join(stuecke))[:MAX_CHARS]
    except Exception as e:  # noqa: BLE001 — ein kaputtes PDF ist kein Laufabbruch
        logger.info("PDF nicht lesbar: %s", type(e).__name__)
        return "", None, "error"

    gelesen = min(seiten, MAX_PAGES) or 1
    if not text:
        return "", seiten, "empty"
    return text, seiten, "ok" if len(text) / gelesen >= MIN_CHARS_PER_PAGE else "thin"
