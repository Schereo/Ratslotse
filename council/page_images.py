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
import threading
import time
from pathlib import Path

import requests

from council import ris

#: Widths a client may ask for. Each width is a file per page; a free number
#: would let anyone fill the disk. 1280 is the enlarged view (sharp at about
#: 900 CSS pixels on a retina screen).
WIDTHS = (320, 640, 1280)
#: Larger documents get no preview (the budget books run to 80 MB).
PDF_MAX_BYTES = 60 * 1024 * 1024
PDF_CACHE_MAX = 400 * 1024 * 1024
IMG_CACHE_MAX = 200 * 1024 * 1024

_session = requests.Session()

#: Höchstens so viele Abrufe und Renderings zugleich: Beides läuft im
#: Threadpool des einzigen API-Prozesses, neben jeder anderen Anfrage.
_SLOTS = threading.BoundedSemaphore(2)
_SLOT_WAIT = 20
#: Eine Absage je Unterlage, gemerkt bis zum Zeitpunkt: Eine zu große oder
#: kaputte Unterlage soll nicht bei jedem Überfahren neu geladen werden.
_REFUSED: dict[int, tuple[str, float]] = {}
_REFUSE_FOR = {"too_large": 24 * 3600, "not_pdf": 24 * 3600, "fetch": 300}


class NoPreview(Exception):
    """Why there is no picture: ``unavailable`` (no PyMuPDF), ``not_ris``,
    ``fetch`` (Ratsinfo did not deliver), ``too_large``, ``not_pdf``,
    ``no_page``, ``busy`` (too many renders at once)."""

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


def _refuse(document_id: int, reason: str) -> NoPreview:
    if reason in _REFUSE_FOR:
        _REFUSED[int(document_id)] = (reason, time.monotonic() + _REFUSE_FOR[reason])
    return NoPreview(reason)


def _download(url: str) -> bytes:
    """The PDF, read in pieces and given up as soon as it is too large —
    announced (``Content-Length``) or while reading. Never the whole thing
    first and the check afterwards."""
    try:
        response = ris.fetch(_session, url, timeout=45, stream=True)
    except (requests.RequestException, ris.RisError) as exc:
        raise NoPreview("fetch") from exc
    try:
        announced = response.headers.get("Content-Length")
        if announced and announced.isdigit() and int(announced) > PDF_MAX_BYTES:
            raise NoPreview("too_large")
        parts: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=256 * 1024):
            total += len(chunk)
            if total > PDF_MAX_BYTES:
                raise NoPreview("too_large")
            parts.append(chunk)
        return b"".join(parts)
    except requests.RequestException as exc:
        raise NoPreview("fetch") from exc
    finally:
        response.close()


def pdf_bytes(cache: Path, document_id: int, url: str) -> bytes:
    path = cache / "pdf" / f"{int(document_id)}.pdf"
    if path.is_file():
        path.touch()
        return path.read_bytes()
    if not url or not ris.is_ris(url):
        raise NoPreview("not_ris")
    refused = _REFUSED.get(int(document_id))
    if refused and refused[1] > time.monotonic():
        raise NoPreview(refused[0])
    try:
        data = _download(url)
    except NoPreview as exc:
        raise _refuse(document_id, exc.reason) from exc
    if not data.startswith(b"%PDF"):
        raise _refuse(document_id, "not_pdf")
    _REFUSED.pop(int(document_id), None)
    _write(path, data)
    _trim(path.parent, PDF_CACHE_MAX)
    return data


class _Slot:
    """Einer der Plätze für Abruf und Rendern — oder ``busy`` nach Wartezeit."""

    def __enter__(self):
        if not _SLOTS.acquire(timeout=_SLOT_WAIT):
            raise NoPreview("busy")
        return self

    def __exit__(self, *exc):
        _SLOTS.release()


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
    with _Slot(), _open(pdf_bytes(cache, document_id, url)) as doc:
        return doc.page_count


def page_image(cache: Path, document_id: int, url: str, page: int, width: int) -> Path:
    """The page as a JPEG file — rendered once, then from the cache."""
    if width not in WIDTHS:
        raise ValueError(f"width {width} not in {WIDTHS}")
    out = cache / "img" / f"{int(document_id)}-{int(page)}-{width}.jpg"
    if out.is_file():
        out.touch()
        return out
    with _Slot(), _open(pdf_bytes(cache, document_id, url)) as doc:
        if not 1 <= page <= doc.page_count:
            raise NoPreview("no_page")
        import pymupdf  # noqa: PLC0415 — _open hat den Import schon geprüft

        p = doc[page - 1]
        zoom = width / max(p.rect.width, 1)
        pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        _write(out, pix.tobytes(output="jpg", jpg_quality=82))
    _trim(out.parent, IMG_CACHE_MAX)
    return out
