"""Pressemitteilungen der Stadt Oldenburg (TYPO3 EXT:news).

Beschlüsse sagen, was ENTSCHIEDEN wurde — die Pressemitteilungen der Stadt
sagen, was daraus GEWORDEN ist (Spatenstich, Eröffnung, Verzögerung). Dieser
Scraper holt beides zusammen: den RSS-Feed für den täglichen Abgleich und die
paginierte Archiv-Liste für den Backfill (Ketten-Crawl über die cHash-Links im
HTML — die cHashes lassen sich nicht erraten, wohl aber verfolgen).

Amtliche Pressemitteilungen der Stadt, keine Verlagsinhalte: Der Volltext
bleibt intern (Suche/Embedding); angezeigt werden Titel, Datum, kurzer Auszug
und der Link auf oldenburg.de.
"""
from __future__ import annotations

import logging
import re
import time
import warnings
from datetime import datetime

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Bewusst der HTML-Parser fürs RSS (kein stdlib-XML → keine Entity-Angriffe,
# gleiches Muster wie beim RIS-RSS in council/scraper.py) — die Warnung dazu
# ist damit beantwortet.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BASE = "https://www.oldenburg.de"
FEED_URL = f"{BASE}/startseite/rathaus/informiert-bleiben/presse/rss.xml"
LISTE_URL = f"{BASE}/startseite/rathaus/informiert-bleiben/presse/pressemitteilungen.html"

logger = logging.getLogger("council.presse")

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"
_DELAY = 0.5


def fetch_feed() -> list[dict]:
    """Aktuelle Einträge aus dem RSS-Feed → [{url, news_id, titel, datum}].

    Geparst mit BeautifulSoup statt xml.etree — gleiches Muster wie beim
    RIS-RSS (council/scraper.py) und immun gegen die XML-Entity-Angriffsklassen
    der stdlib-Parser."""
    r = _session.get(FEED_URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[dict] = []
    for item in soup.find_all("item"):
        # html.parser kennt <link> als void-Tag: aus <link>url</link> wird ein
        # leeres Tag, die URL hängt als nächstes Text-Geschwister — beide
        # Lesarten abdecken.
        link = ""
        link_tag = item.find("link")
        if link_tag is not None:
            link = link_tag.get_text(strip=True) or str(link_tag.next_sibling or "").strip()
        if not link:
            continue
        guid = item.find("guid")
        m = re.search(r"news-(\d+)", guid.get_text(strip=True) if guid else "")
        title = item.find("title")
        pubdate = item.find("pubdate")
        out.append({
            "url": link if link.startswith("http") else f"{BASE}{link}",
            "news_id": int(m.group(1)) if m else None,
            "title": title.get_text(strip=True) if title else "",
            "date": _parse_rfc2822(pubdate.get_text(strip=True) if pubdate else ""),
        })
    return out


def fetch_liste(url: str | None = None) -> tuple[list[dict], str | None]:
    """Eine Archiv-Listenseite → ([{url, titel}], nächste_seite_oder_None).

    Die Folgeseite kommt aus dem Pagination-Link „nächste Seite" im HTML —
    TYPO3-cHashes machen konstruierte URLs unzuverlässig, verfolgte nicht."""
    time.sleep(_DELAY)
    r = _session.get(url or LISTE_URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    eintraege: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/pressemitteilung/news/" not in href:
            continue
        full = href if href.startswith("http") else f"{BASE}{href}"
        if full in seen:
            continue
        seen.add(full)
        eintraege.append({"url": full, "title": a.get_text(" ", strip=True)})
    # Aktuelle Seitenzahl aus der eigenen URL (Startseite = 1), Folge-Link suchen.
    cur = 1
    m = re.search(r"currentPage(?:%5D|\])=(\d+)", url or "")
    if m:
        cur = int(m.group(1))
    naechste = None
    for a in soup.find_all("a", href=True):
        m = re.search(r"currentPage(?:%5D|\])=(\d+)", a["href"])
        if m and int(m.group(1)) == cur + 1:
            href = a["href"].replace("&amp;", "&")
            naechste = href if href.startswith("http") else f"{BASE}{href}"
            break
    return eintraege, naechste


def fetch_detail(url: str) -> dict | None:
    """Detailseite → {titel, datum, text} — None, wenn kein Textkörper gefunden
    wird (Seite entfernt/umgebaut)."""
    time.sleep(_DELAY)
    r = _session.get(url, timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    wrap = soup.find(class_="news-text-wrap") or soup.find("article")
    if wrap is None:
        return None
    text = re.sub(r"\n{3,}", "\n\n", wrap.get_text("\n", strip=True)).strip()
    if len(text) < 50:
        return None
    # Titel: og:title trägt die echte Überschrift (das h1 ist das generische
    # „Pressemitteilung"), Fallback news-single__title.
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og is not None:
        title = (og.get("content") or "").strip()
    if not title:
        h2 = soup.find("h2", class_="news-single__title")
        if h2 is not None:
            title = h2.get_text(" ", strip=True)
    # Datum: JSON-LD datePublished ist die verlässlichste Quelle der Seite.
    date = None
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', r.text)
    if m:
        date = m.group(1)
    if date is None:
        t = soup.find("time")
        if t is not None:
            date = _parse_datum(t.get("datetime") or t.get_text(strip=True))
    if date is None:
        # TYPO3 rendert das Datum oft als Fließtext „05. August 2026".
        m = re.search(r"(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|"
                      r"September|Oktober|November|Dezember)\s+(\d{4})", soup.get_text(" ", strip=True)[:4000])
        if m:
            monate = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
                      "August", "September", "Oktober", "November", "Dezember"]
            date = f"{m.group(3)}-{monate.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"
    return {"title": title, "date": date, "text": text}


def _parse_rfc2822(s: str) -> str | None:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


def _parse_datum(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:len(datetime.now().strftime(fmt))] if "%z" not in fmt else s,
                                     fmt).date().isoformat()
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None
