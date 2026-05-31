from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


@dataclass
class Article:
    refid: str
    external_id: str
    page: int
    category_number: int | None
    category_name: str
    title: str
    subtitle: str
    authors: list[str] = field(default_factory=list)
    content_html: str = ""
    content_text: str = ""
    priority: int = 0


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text


def parse_publication(xml_bytes: bytes) -> tuple[dict, list[Article]]:
    """Returns (paper_meta, articles)."""
    root = ET.fromstring(xml_bytes)
    meta = {
        "language": _text(root.find("language")),
        "title": _text(root.find("title")),
        "published": _text(root.find("published")),
        "pages": int(_text(root.find("pages")) or 0),
        "customer": _text(root.find("customer")),
        "catalog": int(_text(root.find("catalog")) or 0),
        "folder": int(_text(root.find("folder")) or 0),
        "edition": _text(root.find("edition")),
        "content_version": int(_text(root.find("content_version")) or 0),
    }

    articles: list[Article] = []
    for a in root.iterfind(".//article"):
        titles_el = a.find("titles")
        title = _text(titles_el.find("title")) if titles_el is not None else ""
        subtitle = _text(titles_el.find("subtitle")) if titles_el is not None else ""
        bylines_el = a.find("bylines")
        authors = []
        if bylines_el is not None:
            for b in bylines_el.iterfind("byline"):
                au = _text(b.find("author")).strip()
                if au:
                    authors.append(au)
        content_html = _text(a.find("content"))
        articles.append(
            Article(
                refid=_text(a.find("refid")).strip(),
                external_id=_text(a.find("external_id")).strip(),
                page=int(_text(a.find("page")) or 0),
                category_number=int(_text(a.find("category_number")) or 0) or None,
                category_name=_text(a.find("category_name")).strip(),
                title=title.strip(),
                subtitle=subtitle.strip(),
                authors=authors,
                content_html=content_html,
                content_text=_strip_html(content_html),
                priority=int(_text(a.find("priority")) or 0),
            )
        )
    return meta, articles
