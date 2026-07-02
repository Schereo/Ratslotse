"""Fetch and store Vorlagen (Beschlussvorlagen, Anträge, Berichte) as full text.

A Vorlage is the document a decision is ABOUT: it carries the Sachverhalt and the
Begründung — the *why* behind a Beschluss, which the protocol only records the
outcome of. The vo0050 page itself holds only metadata (Betreff, Nr., Art); the
content lives in the attached "Vorlage" PDF, so we download that and extract its
text (``pypdf``). No LLM here — ingestion is pure network + parsing; consumers
(Q&A context, FTS, decision pages) work on the raw text.

Deliberately NOT fetched: the further Anlagen (maps, balance sheets, fraction
motions) — they are linked from the same page and can become their own ingestion
step later.
"""
from __future__ import annotations

import io
import re

import requests
import pypdf
from bs4 import BeautifulSoup

BASE = "https://buergerinfo.oldenburg.de"

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"

# Section headings that start the substantive part of a Vorlage. A heading only
# counts at the start of a line, either standalone or directly followed by ":" —
# the bare words also appear mid-sentence ("… in der Begründung des Antrages …").
# Two tiers: Sachverhalt/Begründung/Anlass/Bericht carry the actual reasoning;
# "Beschlussvorschlag" is only a fallback because it usually just repeats what
# the decision row already shows — and it appears BEFORE the Sachverhalt.
_HEADING = r"Sachverhalt(?:\s+und\s+Begründung)?|Sach-\s*und\s*Rechtslage|Begründung|Ausgangslage|Anlass|Bericht"
_SECTION_RE = re.compile(rf"^(?:{_HEADING})(?::|\s*$)")
_FALLBACK_SECTION_RE = re.compile(r"^Beschlussvorschlag(?::|\s*$)")
# Per-page boilerplate that pypdf interleaves with the content.
_NOISE_RE = re.compile(
    r"^(Seite:?\s*\d+\s*/\s*\d+.*|Ausdruck vom:.*|Vorlagen?-?\s*Nr\.?:.*|\s*-\s*\d+\s*-\s*)$"
)


def parse_vorlage_page(html: str) -> dict | None:
    """Extract metadata + the main PDF link from a vo0050 page.

    Returns ``{vorlage_nr, title, art, document_id, document_url}`` (PDF fields
    ``None`` when the page has no public "Vorlage" document) or ``None`` when the
    page is no Vorlage at all (invalid kvonr)."""
    soup = BeautifulSoup(html, "html.parser")
    title_cell = soup.find(class_="vobetr")
    nr_cell = soup.find(class_="voname")
    if title_cell is None and nr_cell is None:
        return None
    art_cell = soup.find(class_="vovaname")

    document_id = document_url = None
    for a in soup.find_all("a", href=True):
        if "getfile.php" not in a["href"]:
            continue
        # Every document renders two links (icon + label); the main document's
        # label is exactly "Vorlage", the Anlagen carry their own names.
        if a.get_text(" ", strip=True) != "Vorlage":
            continue
        href = a["href"] if a["href"].startswith("http") else f"{BASE}/{a['href'].lstrip('/')}"
        m = re.search(r"id=(\d+)", href)
        document_id = int(m.group(1)) if m else None
        document_url = href
        break

    return {
        "vorlage_nr": nr_cell.get_text(" ", strip=True) if nr_cell else "",
        "title": title_cell.get_text(" ", strip=True) if title_cell else "",
        "art": art_cell.get_text(" ", strip=True) if art_cell else "",
        "document_id": document_id,
        "document_url": document_url,
    }


def _pdf_text(url: str) -> tuple[str, int]:
    """Download a PDF and return (text, n_pages). Mirrors protocols.extract_pdf_text
    but keeps this module free of the LLM import chain."""
    r = _session.get(url, timeout=45)
    r.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    return text, len(reader.pages)


def fetch_vorlage(kvonr: int) -> dict | None:
    """Full ingestion for one Vorlage: metadata from vo0050 + text from the PDF.

    Returns a row ready for ``CouncilStore.save_vorlage`` with ``status`` one of
    ``ok`` (text extracted), ``empty`` (PDF has no text layer — scanned) or
    ``no_pdf`` (no public document). ``None`` for an invalid kvonr. Network
    errors propagate — the caller decides between retry and mark-failed."""
    r = _session.get(f"{BASE}/vo0050.php", params={"__kvonr": kvonr}, timeout=20)
    r.raise_for_status()
    meta = parse_vorlage_page(r.text)
    if meta is None:
        return None
    row = {"kvonr": kvonr, **meta, "raw_text": "", "n_pages": 0, "status": "no_pdf"}
    if meta["document_url"]:
        text, n_pages = _pdf_text(meta["document_url"])
        row["raw_text"] = text
        row["n_pages"] = n_pages
        row["status"] = "ok" if len(text.strip()) >= 50 else "empty"
    return row


def excerpt(raw_text: str, chars: int = 400) -> str:
    """A readable excerpt of a Vorlage text: starts at the first substantive
    section (Sachverhalt/Begründung/…) when one is found, drops per-page
    boilerplate lines, collapses whitespace. Empty string when there is no text."""
    if not raw_text:
        return ""
    lines = [ln.strip() for ln in raw_text.splitlines()]
    kept = [ln for ln in lines if ln and not _NOISE_RE.match(ln)]
    start = next((i for i, ln in enumerate(kept) if _SECTION_RE.match(ln)), None)
    if start is None:
        start = next((i for i, ln in enumerate(kept) if _FALLBACK_SECTION_RE.match(ln)), 0)
    text = "\n".join(kept[start:])
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) > chars:
        # Cut at a word boundary so the ellipsis doesn't split a word.
        cut = text[:chars].rsplit(" ", 1)[0]
        text = cut + " …"
    return text
