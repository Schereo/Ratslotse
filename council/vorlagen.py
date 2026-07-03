"""Fetch and store Vorlagen (Beschlussvorlagen, Anträge, Berichte) as full text.

A Vorlage is the document a decision is ABOUT: it carries the Sachverhalt and the
Begründung — the *why* behind a Beschluss, which the protocol only records the
outcome of. The vo0050 page itself holds only metadata (Betreff, Nr., Art); the
content lives in the attached "Vorlage" PDF, so we download that and extract its
text (``pypdf``). No LLM here — ingestion is pure network + parsing; consumers
(Q&A context, FTS, decision pages) work on the raw text.

Anlagen: every further document on the page is recorded with label + link. In
Oldenburg the ORIGINAL fraction motions live here ("Antrag der SPD-Fraktion vom
…") — there is no Vorlagen-Art "Antrag". Anlagen whose label looks like a motion
also get their PDF text ingested plus the submitting parties (Antragsteller,
recognised via council.parties); maps/balance sheets stay link-only.
"""
from __future__ import annotations

import io
import re

import requests
import pypdf
from bs4 import BeautifulSoup

from council.parties import parties_in_text

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
    """Extract metadata, the main PDF link and the Anlagen list from a vo0050 page.

    Returns ``{vorlage_nr, title, art, document_id, document_url, anlagen}`` —
    ``anlagen`` is ``[{document_id, url, label}]`` for every further document
    (PDF fields ``None`` when the page has no public "Vorlage" document) — or
    ``None`` when the page is no Vorlage at all (invalid kvonr)."""
    soup = BeautifulSoup(html, "html.parser")
    title_cell = soup.find(class_="vobetr")
    nr_cell = soup.find(class_="voname")
    if title_cell is None and nr_cell is None:
        return None
    art_cell = soup.find(class_="vovaname")

    # Every document renders two links (icon + label). Collect per document_id;
    # the non-empty text is the label. Label "Vorlage" = the main document.
    docs: dict[int, dict] = {}
    for a in soup.find_all("a", href=True):
        if "getfile.php" not in a["href"]:
            continue
        href = a["href"] if a["href"].startswith("http") else f"{BASE}/{a['href'].lstrip('/')}"
        m = re.search(r"id=(\d+)", href)
        if not m:
            continue
        doc_id = int(m.group(1))
        entry = docs.setdefault(doc_id, {"document_id": doc_id, "url": href, "label": ""})
        text = a.get_text(" ", strip=True)
        if text and not entry["label"]:
            entry["label"] = text

    document_id = document_url = None
    anlagen: list[dict] = []
    for entry in docs.values():
        if entry["label"] == "Vorlage" and document_id is None:
            document_id, document_url = entry["document_id"], entry["url"]
        else:
            anlagen.append(entry)

    return {
        "vorlage_nr": nr_cell.get_text(" ", strip=True) if nr_cell else "",
        "title": title_cell.get_text(" ", strip=True) if title_cell else "",
        "art": art_cell.get_text(" ", strip=True) if art_cell else "",
        "document_id": document_id,
        "document_url": document_url,
        "anlagen": anlagen,
    }


def _pdf_text(url: str) -> tuple[str, int]:
    """Download a PDF and return (text, n_pages). Mirrors protocols.extract_pdf_text
    but keeps this module free of the LLM import chain."""
    r = _session.get(url, timeout=45)
    r.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    return text, len(reader.pages)


# Anlagen whose label smells like a fraction motion get their text ingested.
# Broad on purpose ("Antrag auf Aufhebung …" from an investor also matches) —
# the Antragsteller party filter keeps the statistics clean.
_ANTRAG_LABEL_RE = re.compile(r"\b(antr[aä]g|anfrage)", re.IGNORECASE)


def _build_anlage_rows(anlagen: list[dict], skip_document_ids: frozenset = frozenset()) -> list[dict]:
    """Rows for ``CouncilStore.save_anlagen``: motion-like Anlagen get PDF text +
    Antragsteller (from the label, else the first PDF page); everything else is
    recorded link-only (status ``listed``). Already-known document_ids are kept
    link-only so daily re-scans don't re-download their PDFs."""
    rows: list[dict] = []
    for a in anlagen:
        row = {**a, "is_antrag": 0, "antragsteller": [], "raw_text": "", "n_pages": 0,
               "status": "listed"}
        if _ANTRAG_LABEL_RE.search(a["label"] or "") and a["document_id"] not in skip_document_ids:
            row["is_antrag"] = 1
            try:
                text, n_pages = _pdf_text(a["url"])
                row["raw_text"], row["n_pages"] = text, n_pages
                row["status"] = "ok" if len(text.strip()) >= 50 else "empty"
            except Exception:  # noqa: BLE001 — ein kaputtes Anlagen-PDF kippt nicht den ganzen kvonr
                row["status"] = "failed"
            row["antragsteller"] = parties_in_text(a["label"]) or parties_in_text(row["raw_text"][:1500])
        rows.append(row)
    return rows


def fetch_vorlage(kvonr: int) -> dict | None:
    """Full ingestion for one Vorlage: metadata from vo0050, text from the main
    PDF, plus the Anlagen rows (motions with text, the rest link-only) under
    ``row["anlagen"]``.

    ``status`` is one of ``ok`` (text extracted), ``empty`` (PDF has no text
    layer — scanned) or ``no_pdf`` (no public document). ``None`` for an invalid
    kvonr. Network errors on the MAIN document propagate — the caller decides
    between retry and mark-failed."""
    r = _session.get(f"{BASE}/vo0050.php", params={"__kvonr": kvonr}, timeout=20)
    r.raise_for_status()
    meta = parse_vorlage_page(r.text)
    if meta is None:
        return None
    anlagen = _build_anlage_rows(meta.pop("anlagen"))
    row = {"kvonr": kvonr, **meta, "raw_text": "", "n_pages": 0, "status": "no_pdf",
           "anlagen": anlagen}
    if meta["document_url"]:
        text, n_pages = _pdf_text(meta["document_url"])
        row["raw_text"] = text
        row["n_pages"] = n_pages
        row["status"] = "ok" if len(text.strip()) >= 50 else "empty"
    return row


def fetch_anlagen(kvonr: int, skip_document_ids: frozenset = frozenset()) -> list[dict] | None:
    """Anlagen-only pass for an already-ingested Vorlage (historical catch-up and
    the daily re-scan of recent sessions — Änderungsanträge often appear on the
    page days after the Vorlage itself). Does NOT touch the main Vorlage PDF.
    ``None`` for an invalid kvonr; network errors on the page propagate."""
    r = _session.get(f"{BASE}/vo0050.php", params={"__kvonr": kvonr}, timeout=20)
    r.raise_for_status()
    meta = parse_vorlage_page(r.text)
    if meta is None:
        return None
    return _build_anlage_rows(meta["anlagen"], skip_document_ids)


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
