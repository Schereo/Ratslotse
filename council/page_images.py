"""Pictures of single PDF pages — the preview behind a reference in a note
(Tims Wunsch 23.11.2026: beim Auswählen der Seite sehen, was man einfügt,
und in der Notiz beim Überfahren).

The browser cannot load the PDF itself: the Ratsinfo sends no CORS headers.
So the server fetches it once, renders the page with PyMuPDF and keeps both:

    <cache>/pdf/<document_id>.pdf            the document, as fetched
    <cache>/img/<document_id>-<page>-<w>.jpg one page at one width

Both folders have a ceiling; the least recently used files go first. A
getfile id names one fixed document, so nothing here ever needs refreshing.

**Only addresses from our own database, only the Ratsinfo.** The caller
passes the URL it looked up by id (``store.document_source``); this module
refuses anything that is not the Ratsinfo — no client ever names a URL.

PyMuPDF is on dev and Prod (in the venv the web service shares with the
crons), but deliberately not in ``requirements.txt`` (AGPL, see
``scripts/render_plaene.py``). Without it there is no preview, and
``NoPreview("unavailable")`` says so.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests

from council import ris

#: Widths a client may ask for. Each width is a file per page; a free number
#: would let anyone fill the disk.
WIDTHS = (320, 640)
#: Larger documents get no preview (the budget books run to 80 MB).
PDF_MAX_BYTES = 60 * 1024 * 1024
PDF_CACHE_MAX = 400 * 1024 * 1024
IMG_CACHE_MAX = 200 * 1024 * 1024

_session = requests.Session()


class NoPreview(Exception):
    """Why there is no picture: ``unavailable`` (no PyMuPDF), ``not_ris``,
    ``fetch`` (Ratsinfo did not deliver), ``too_large``, ``not_pdf``,
    ``no_page``."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def available() -> bool:
    try:
        import pymupdf  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True


def _write(path: Path, data: bytes) -> None:
    """Atomically: two requests for the same page must not see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _trim(folder: Path, max_bytes: int) -> None:
    """Oldest-touched files out until the folder fits again."""
    files = [(p.stat().st_mtime, p.stat().st_size, p) for p in folder.glob("*") if p.is_file()
             and not p.name.startswith(".tmp-")]
    total = sum(s for _, s, _ in files)
    for _, size, p in sorted(files):
        if total <= max_bytes:
            break
        p.unlink(missing_ok=True)
        total -= size


def pdf_bytes(cache: Path, document_id: int, url: str) -> bytes:
    path = cache / "pdf" / f"{int(document_id)}.pdf"
    if path.is_file():
        path.touch()
        return path.read_bytes()
    if not url or not ris.is_ris(url):
        raise NoPreview("not_ris")
    try:
        response = ris.fetch(_session, url, timeout=45)
    except (requests.RequestException, ris.RisError) as exc:
        raise NoPreview("fetch") from exc
    data = response.content
    if len(data) > PDF_MAX_BYTES:
        raise NoPreview("too_large")
    if not data.startswith(b"%PDF"):
        raise NoPreview("not_pdf")
    _write(path, data)
    _trim(path.parent, PDF_CACHE_MAX)
    return data


def _open(data: bytes):
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:
        raise NoPreview("unavailable") from exc
    try:
        return pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — ein kaputtes PDF ist kein Serverfehler
        raise NoPreview("not_pdf") from exc


def page_count(cache: Path, document_id: int, url: str) -> int:
    with _open(pdf_bytes(cache, document_id, url)) as doc:
        return doc.page_count


def page_image(cache: Path, document_id: int, url: str, page: int, width: int) -> Path:
    """The page as a JPEG file — rendered once, then from the cache."""
    if width not in WIDTHS:
        raise ValueError(f"width {width} not in {WIDTHS}")
    out = cache / "img" / f"{int(document_id)}-{int(page)}-{width}.jpg"
    if out.is_file():
        out.touch()
        return out
    with _open(pdf_bytes(cache, document_id, url)) as doc:
        if not 1 <= page <= doc.page_count:
            raise NoPreview("no_page")
        import pymupdf  # noqa: PLC0415 — _open hat den Import schon geprüft

        p = doc[page - 1]
        zoom = width / max(p.rect.width, 1)
        pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        _write(out, pix.tobytes(output="jpg", jpg_quality=82))
    _trim(out.parent, IMG_CACHE_MAX)
    return out
