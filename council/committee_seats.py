"""Die aktuelle Besetzung von Rat und Ausschüssen aus dem Ratsinformationssystem.

Grundlage des Mehrheitsrechners in den Werkzeugen (``/werkzeuge/mehrheiten``):
Wer sitzt in welchem Gremium, für welche Fraktion oder Gruppe, mit Stimme oder
nur beratend. Drei SessionNet-Seiten, ohne Sprachmodell gelesen:

- ``gr0040.asp`` — die **Gremienübersicht** mit den Gremiennummern (kgrnr).
- ``kp0040.asp?__kgrnr=`` — die **Mitglieder eines Gremiums**: Name, Fraktion
  oder Gruppe, Art der Mitarbeit (Ausschussmitglied, Grundmandat, …). Auch die
  Mitglieder ohne Ratsmandat stehen hier — Eltern- und Lehrkräftevertretung im
  Schulausschuss, Beschäftigte in den Betriebsausschüssen —, und die stimmen mit.
- ``kp0050.asp?__kpenr=`` — die **Mitarbeit einer Person**. Gebraucht nur für
  Gremien, die die Übersicht nicht verlinkt: Der **Verwaltungsausschuss** tagt
  nichtöffentlich und hat keine eigene Mitgliederseite, seine Beigeordneten
  stehen nur auf ihren Personenseiten.

Dazu ``kp0041.asp`` (die Mandatsträger) für die Personennummern und die eine
Stimme, die auf keiner Mitgliederseite des Rats steht: die der
Oberbürgermeisterin oder des Oberbürgermeisters. Sie ist kraft Amtes Mitglied
des Rats und stimmt dort mit (§ 45 Abs. 1 NKomVG).

**Host:** Seit 11/2026 liegt das Ratsinfo unter ``ratsinfo.oldenburg.de/bi``
(ASP statt PHP). Der alte Host ``buergerinfo.oldenburg.de`` leitet per 301 auf
die Startseite um und verliert dabei den Pfad — eine Anfrage dorthin bekommt
eine Seite ohne einen einzigen Treffer, keinen Fehler. Deshalb steht der Host
hier ausdrücklich und nicht über ``council.scraper.BASE``.

Bewusst NICHT gespeichert: Namen von Mitgliedern ohne Ratsmandat (sie stehen
unter ihrer Funktion, etwa „Elternvertreter“) und Stellvertretungen — die
stimmen nur im Vertretungsfall und gehören in keine Mehrheitsrechnung.
"""
from __future__ import annotations

import html
import re
import time
from collections.abc import Callable, Iterable

import requests
from bs4 import BeautifulSoup, Tag

RIS_BASE = "https://ratsinfo.oldenburg.de/bi"

#: Das Gremium, dessen Mitgliederseite der Rat selbst ist.
RAT = "Rat"

#: Arten der Mitarbeit, die eine Stimme tragen. Alles andere ist beratend
#: (Grundmandat, beratendes Mitglied) oder Stellvertretung.
_STIMME = frozenset({
    "ratsmitglied", "ausschussmitglied", "ausschussvorsitzende/r",
    "stellv. ausschussvorsitzende/r", "beigeordnete/r", "stimmberechtigtes mitglied",
    "vorsitzende/r", "ratsvorsitzende/r", "oberbürgermeister/in",
})
_BERATEND = ("grundmandat", "beratend")
_STELLVERTRETUNG = ("vertreter/in", "stellvertreter")

_KGRNR = re.compile(r"__kgrnr=(\d+)")
_KPENR = re.compile(r"__kpenr=(\d+)")
_OB = re.compile(r"^Oberbürgermeister(in)?\s+", re.I)


def faction_label(raw: str | None) -> str | None:
    """Das Fraktionsetikett, wie das Ratsinfo es führt — nur geglättet.

    Dasselbe Etikett steht dort in zwei Schreibweisen („Bündnis 90/Die Grünen“
    und „Bündnis 90/ Die Grünen“); ungeglättet wären das im Rechner zwei
    Fraktionen mit 12 und 1 Sitz."""
    if not raw:
        return None
    txt = re.sub(r"\s*/\s*", "/", " ".join(html.unescape(raw).split()))
    return txt or None


def seat_kind(role: str | None) -> str:
    """``voting`` | ``advisory`` | ``deputy`` | ``other`` für eine Art der Mitarbeit."""
    low = " ".join((role or "").split()).lower()
    if low in _STIMME:
        return "voting"
    if any(w in low for w in _BERATEND):
        return "advisory"
    if any(w in low for w in _STELLVERTRETUNG):
        return "deputy"
    return "other"


def _cells(tr: Tag) -> dict[str, list[Tag]]:
    out: dict[str, list[Tag]] = {}
    for td in tr.find_all("td"):
        if isinstance(td, Tag):
            out.setdefault(str(td.get("data-label") or ""), []).append(td)
    return out


def _text(td: Tag | None) -> str:
    return " ".join(td.get_text(" ", strip=True).split()) if td is not None else ""


def _kpenr(td: Tag | None) -> int | None:
    if td is None:
        return None
    a = td.find("a", href=_KPENR)
    if not isinstance(a, Tag):
        return None
    m = _KPENR.search(str(a.get("href") or ""))
    return int(m.group(1)) if m else None


def parse_committee_list(page: str) -> list[tuple[str, int]]:
    """Gremienübersicht → ``[(name, kgrnr)]`` in der Reihenfolge der Seite."""
    soup = BeautifulSoup(page, "html.parser")
    out: list[tuple[str, int]] = []
    seen: set[int] = set()
    for a in soup.find_all("a", href=re.compile(r"kp0040\.asp\?__kgrnr=\d+")):
        if not isinstance(a, Tag):
            continue
        m = _KGRNR.search(str(a.get("href") or ""))
        name = " ".join(a.get_text(" ", strip=True).split())
        if m and name and int(m.group(1)) not in seen:
            seen.add(int(m.group(1)))
            out.append((name, int(m.group(1))))
    return out


def parse_committee_members(page: str, committee: str, kgrnr: int | None) -> list[dict]:
    """Mitgliederseite eines Gremiums → Sitze ohne Stellvertretungen.

    Die Zwischenüberschriften der Seite („Vorsitzende/r“, „Grundmandat“) sind
    nicht verlässlich — gemessen stand im Betriebsausschuss Abfall ein
    Grundmandat unter „Vorsitzende/r“. Maßgeblich ist die Spalte *Art der
    Mitarbeit* jeder Zeile."""
    soup = BeautifulSoup(page, "html.parser")
    out: list[dict] = []
    for tr in soup.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        c = _cells(tr)
        if "Name" not in c or "Mitarbeit" not in c:
            continue
        role = _text(c["Mitarbeit"][0])
        kind = seat_kind(role)
        if kind not in ("voting", "advisory"):
            continue
        kpenr = _kpenr(c["Name"][0])
        faction = faction_label(_text(c.get("Mitgliedschaft", [None])[0]))
        # Ohne Personenseite (Eltern-, Lehrkräfte-, Beschäftigtenvertretung):
        # die Funktion statt des Namens.
        name = _text(c["Name"][0]) if kpenr is not None else (faction or role)
        out.append({
            "committee": committee, "kgrnr": kgrnr, "position": len(out),
            "kpenr": kpenr, "name": name,
            "faction": faction if kpenr is not None else None,
            "role": role, "voting": kind == "voting",
        })
    return out


def parse_mandate_holders(page: str) -> list[dict]:
    """Mandatsträger der laufenden Wahlperiode → ``[{kpenr, name, faction}]``."""
    soup = BeautifulSoup(page, "html.parser")
    out: list[dict] = []
    for tr in soup.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        c = _cells(tr)
        if "Name" not in c:
            continue
        kpenr = _kpenr(c["Name"][0])
        if kpenr is None:
            continue
        out.append({"kpenr": kpenr, "name": _text(c["Name"][0]),
                    "faction": faction_label(_text(c.get("Mitgliedschaft", [None])[0]))})
    return out


def parse_person_committees(page: str) -> list[dict]:
    """Personenseite → laufende Mitarbeit ``[{committee, faction, role}]``.

    Beendete Mitarbeit („von … bis …“) fällt heraus."""
    soup = BeautifulSoup(page, "html.parser")
    out: list[dict] = []
    for tr in soup.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        c = _cells(tr)
        if "Gremium" not in c or "Mitarbeit" not in c:
            continue
        span = " ".join(_text(td) for td in c.get("Beginn Ende", []))
        if " bis " in f" {span} ":
            continue
        out.append({"committee": _text(c["Gremium"][0]),
                    "faction": faction_label(_text(c.get("Mitgliedschaft", [None])[0])),
                    "role": _text(c["Mitarbeit"][0])})
    return out


def mayor_seat(holders: Iterable[dict], position: int) -> dict | None:
    """Die Stimme der Oberbürgermeisterin / des Oberbürgermeisters im Rat."""
    for h in holders:
        if _OB.match(h["name"]):
            return {"committee": RAT, "kgrnr": None, "position": position, "kpenr": h["kpenr"],
                    "name": h["name"], "faction": None, "role": "Oberbürgermeister/in",
                    "voting": True}
    return None


class RisClient:
    """Höflicher Abruf: eine Anfrage nach der anderen, mit Pause."""

    def __init__(self, delay: float = 1.0, base: str = RIS_BASE):
        self._s = requests.Session()
        self._s.headers["User-Agent"] = "Mozilla/5.0 (Ratslotse)"
        self._delay = delay
        self._base = base

    def get(self, path: str, **params) -> str:
        r = self._s.get(f"{self._base}/{path}", params=params, timeout=30)
        r.raise_for_status()
        time.sleep(self._delay)
        return r.text


def fetch_all(client: RisClient, log: Callable[[str], None] = print) -> list[dict]:
    """Die Besetzung aller Gremien — Rat, Ausschüsse, Verwaltungsausschuss.

    Wirft ``RuntimeError``, wenn der Rat weniger als 20 Stimmen hätte: Dann
    hat sich das Ratsinfo verändert (Host, Aufbau), und eine leere oder halbe
    Besetzung darf den gespeicherten Stand nicht ersetzen."""
    committees = parse_committee_list(client.get("gr0040.asp"))
    seats: list[dict] = []
    covered: set[str] = set()
    for name, kgrnr in committees:
        rows = parse_committee_members(client.get("kp0040.asp", __kgrnr=kgrnr), name, kgrnr)
        log(f"  {name}: {sum(r['voting'] for r in rows)} Stimmen, "
            f"{sum(not r['voting'] for r in rows)} beratend")
        seats.extend(rows)
        covered.add(name)

    holders = parse_mandate_holders(client.get("kp0041.asp"))
    ob = mayor_seat(holders, position=sum(1 for s in seats if s["committee"] == RAT))
    if ob:
        seats.append(ob)

    # Gremien ohne eigene Mitgliederseite (der Verwaltungsausschuss) aus den
    # Personenseiten zusammensetzen.
    extra: dict[str, list[dict]] = {}
    for h in holders:
        for row in parse_person_committees(client.get("kp0050.asp", __kpenr=h["kpenr"])):
            if row["committee"] in covered or not row["committee"]:
                continue
            kind = seat_kind(row["role"])
            if kind not in ("voting", "advisory"):
                continue
            # Nur Gremien, in denen jemand eine Stimme hat — eine Fraktion
            # steht auf der Personenseite auch als „Gremium“.
            extra.setdefault(row["committee"], []).append({
                "committee": row["committee"], "kgrnr": None, "kpenr": h["kpenr"],
                "name": h["name"], "faction": row["faction"] or h["faction"],
                "role": row["role"], "voting": kind == "voting",
            })
    for name, rows in sorted(extra.items()):
        if not any(r["voting"] and r["role"].lower() != "ratsmitglied" for r in rows):
            continue
        rows.sort(key=lambda r: (not r["voting"], r["name"]))
        for i, r in enumerate(rows):
            r["position"] = i
        log(f"  {name} (aus Personenseiten): {sum(r['voting'] for r in rows)} Stimmen, "
            f"{sum(not r['voting'] for r in rows)} beratend")
        seats.extend(rows)

    rat = sum(1 for s in seats if s["committee"] == RAT and s["voting"])
    if rat < 20:
        raise RuntimeError(f"Ratsinfo liefert nur {rat} Stimmen im Rat — Besetzung NICHT ersetzt "
                           f"(Host oder Seitenaufbau geändert? {RIS_BASE})")
    return seats
