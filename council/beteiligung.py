"""Laufende Bauleitplan-Beteiligungen (oldenburg.planungsbeteiligung.de).

Die Stadt listet dort die Planfälle, zu denen GERADE eine Beteiligung möglich
ist — der fehlende Schlussstein hinter unseren Bauleitplan-Beschlüssen: Der
Aufstellungsbeschluss steht bei uns, die Auslegung läuft dort. Über die
Plan-Nummer („Bebauungsplan 831") verbinden wir beides deterministisch.

Die Liste ist klein (eine Handvoll Planfälle) und wird je Lauf komplett
ersetzt — Historie brauchen wir nicht, nur den aktuellen Stand.
"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

BASE = "https://oldenburg.planungsbeteiligung.de"
LIST_URL = f"{BASE}/FRONTEND/PLANFAELLE/list.asp"

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"

# Plan-Nummern aus Titeln: „Bebauungsplan 831“, „Vorhabenbezogener Bebauungs-
# plan 81“, „Änd. 82 Flächennutzungsplan“ / „82. Änderung des Flächennutzungs-
# plans“. Kanonische Schlüssel: bp-831, fnp-82.
_BP_RE = re.compile(r"Bebauungsplan(?:es|s)?\s+(?:Nr\.?\s*)?([A-Za-z]?-?\d+[A-Za-z]?)", re.IGNORECASE)
_FNP_RE = re.compile(
    r"(?:Änd(?:erung)?\.?\s*(?:Nr\.?\s*)?(\d+)\s*(?:des\s+)?Flächennutzungsplan"
    r"|(\d+)\.\s*Änderung\s+des\s+Flächennutzungsplan)", re.IGNORECASE)


def plan_nummern(title: str) -> list[str]:
    """Kanonische Plan-Schlüssel aus einem Titel — leer, wenn keiner erkennbar."""
    out: list[str] = []
    for m in _BP_RE.finditer(title or ""):
        key = f"bp-{m.group(1).lower()}"
        if key not in out:
            out.append(key)
    for m in _FNP_RE.finditer(title or ""):
        nr = m.group(1) or m.group(2)
        key = f"fnp-{nr}"
        if key not in out:
            out.append(key)
    return out


def passt_zu_titel(plan_nrs: list[str], decision_title: str) -> bool:
    """Gehört ein Beschluss (per Titel) zu einem Planfall?

    Bewusst über die NEU extrahierten Nummern des Beschluss-Titels statt über
    Substrings — „Bebauungsplan 81“ darf nicht auf „Bebauungsplan 831“ oder
    einen Betrag „81.000 €“ matchen."""
    if not plan_nrs:
        return False
    return bool(set(plan_nrs) & set(plan_nummern(decision_title)))


def fetch_planfaelle() -> list[dict]:
    """Aktuelle Planfälle → [{titel, ort, schritt, von, bis, url, plan_nrs}].

    ``von``/``bis`` (ISO) nur, wenn die Seite einen Beteiligungszeitraum nennt
    (beim Abwägungsschritt fehlt er)."""
    r = _session.get(LIST_URL, timeout=20)
    r.raise_for_status()
    # Der HTTP-Header nennt kein charset → requests riete Latin-1 und zerlegte
    # die Umlaute; die Seite deklariert UTF-8 nur im <meta>-Tag.
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[dict] = []
    for art in soup.find_all("article"):
        h3 = art.find("h3")
        if h3 is None:
            continue
        title = h3.get_text(" ", strip=True)
        ps = art.find_all("p")
        ort = ps[0].get_text(" ", strip=True) if ps else ""
        strong = art.find("strong")
        schritt = strong.get_text(" ", strip=True) if strong else ""
        a = art.find("a", href=True)
        url = ""
        if a is not None:
            href = a["href"].replace("../", "/FRONTEND/")
            url = href if href.startswith("http") else f"{BASE}{href}"
        von = bis = None
        periods = art.find("section", class_="periods")
        if periods is not None:
            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\D+(\d{2})\.(\d{2})\.(\d{4})",
                          periods.get_text(" ", strip=True).replace("\xa0", " "))
            if m:
                von = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                bis = f"{m.group(6)}-{m.group(5)}-{m.group(4)}"
        out.append({"title": title, "ort": ort, "schritt": schritt,
                    "valid_from": von, "valid_until": bis, "url": url or LIST_URL,
                    "plan_nrs": plan_nummern(title)})
    return out
