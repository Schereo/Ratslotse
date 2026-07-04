"""Stammdaten aus dem Ratsinformationssystem: Beratungsfolge, Personen, Gremien.

Drei SessionNet-Seitentypen, alle ohne LLM ausgewertet:

- ``vo0053.php?__kvonr=`` — **Beratungsfolge** einer Vorlage: wann sie in
  welchem Gremium unter welchem TOP behandelt wurde (mit Ergebnis), inklusive
  erst geplanter künftiger Stationen.
- ``kp0041.php?__cwpnr=`` — **Mandatsträger** je Wahlperiode (zurück bis 2001):
  Name, Fraktion, ggf. Austrittsdatum; verlinkt die Personen-Nummer (kpenr).
- ``kp0050.php?__kpenr=&__cwpall=1`` — **Mitarbeit** einer Person über alle
  Wahlperioden: Gremium, Art der Mitarbeit, von/bis.

Wichtig: SessionNet überschreibt die Fraktionszugehörigkeit **rückwirkend**
mit dem aktuellen Stand (verifiziert: ein Linke→BSW-Wechsler zeigt „BSW" auch
für die 1990er). Die Fraktion aus diesen Seiten ist deshalb nur als
*aktueller* Stand brauchbar — die Fraktions-Historie kommt aus unseren
Anwesenheitsdaten (``council_attendance``, je Sitzung seit 2018).

Bewusst NICHT übernommen werden die Kontaktdaten der Personenseiten
(Adresse, Telefon, Beruf, E-Mail) — für das Produkt irrelevant und privat.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from council.scraper import CouncilScraper

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_VON_BIS_RE = re.compile(r"von\s+(\d{2}\.\d{2}\.\d{4})(?:\s+bis\s+(\d{2}\.\d{2}\.\d{4}))?")
_VISIBILITY_RE = re.compile(r"^(.*?)\s+(nicht\s*öffentlich|öffentlich)(?:\s*-\s*(.*))?$", re.S)
_TOP_RE = re.compile(r"^(.*?)(?:\s+TOP\s+(\S+))?$", re.S)


def _iso(d: str | None) -> str | None:
    """'24.06.2013' → '2013-06-24' (None-sicher)."""
    if not d:
        return None
    m = _DATE_RE.search(d)
    if not m:
        return None
    dd, mm, yy = m.groups()
    return f"{yy}-{mm}-{dd}"


# --- Beratungsfolge (vo0053) -------------------------------------------------

def fetch_beratungsfolge(scraper: CouncilScraper, kvonr: int) -> list[dict]:
    """Alle Beratungsstationen einer Vorlage, wie auf dem „Beratungen"-Tab.

    Eine Station ist eine Akkordeon-Karte; der Titel trägt
    ``DD.MM.YYYY Gremium [TOP x] öffentlich[- Ergebnis]``, der Karten-Body
    verlinkt die Sitzung (ksinr). Künftige/geplante Stationen haben (noch)
    kein Ergebnis."""
    soup = scraper._get("vo0053.php", __kvonr=kvonr)
    out: list[dict] = []
    for panel in soup.find_all("div", id=re.compile(r"^smcpanel\d+$")):
        btn = panel.find("button")
        if not btn:
            continue
        for span in btn.find_all("span"):
            span.decompose()  # „1 Dok."-Badge und sr-only-Texte
        txt = " ".join(btn.get_text(" ", strip=True).split())
        if not txt:
            continue

        datum = _iso(txt)
        if datum:  # Datum vorn abschneiden
            txt = _DATE_RE.sub("", txt, count=1).strip()

        is_public: bool | None = None
        ergebnis: str | None = None
        rest = txt
        vm = _VISIBILITY_RE.match(txt)
        if vm:
            rest = vm.group(1).strip()
            is_public = "nicht" not in vm.group(2).replace(" ", "").lower()
            ergebnis = (vm.group(3) or "").strip() or None

        tm = _TOP_RE.match(rest)
        gremium = (tm.group(1) if tm else rest).strip()
        top = tm.group(2) if tm else None

        ksinr = None
        a = panel.find("a", href=re.compile(r"si0057\.php"))
        if a:
            m = re.search(r"__ksinr=(\d+)", a["href"])
            if m:
                ksinr = int(m.group(1))

        if gremium or datum:
            out.append({
                "datum": datum, "gremium": gremium, "top": top,
                "is_public": is_public, "ergebnis": ergebnis, "ksinr": ksinr,
            })
    return out


# --- Wahlperioden & Mandatsträger (kp0041) -----------------------------------

def fetch_wahlperioden(scraper: CouncilScraper) -> list[dict]:
    """Alle auf der Mandatsträger-Seite wählbaren Wahlperioden:
    ``[{wpnr, label, von, bis}]`` — plus die aktuelle (höchste) Nummer."""
    soup = scraper._get("kp0041.php")
    seen: dict[int, dict] = {}
    for a in soup.find_all("a", href=re.compile(r"__cwpnr=\d+")):
        m = re.search(r"__cwpnr=(\d+)", a["href"])
        if not m:
            continue
        wpnr = int(m.group(1))
        title = a.get("title", "")
        von = bis = None
        vb = re.search(r"von\s+(\d{2}\.\d{2}\.\d{4})\s+bis\s+(\d{2}\.\d{2}\.\d{4})", title)
        if vb:
            von, bis = _iso(vb.group(1)), _iso(vb.group(2))
        seen[wpnr] = {"wpnr": wpnr, "label": a.get_text(strip=True), "von": von, "bis": bis}
    return [seen[k] for k in sorted(seen)]


def fetch_mandatstraeger(scraper: CouncilScraper, wpnr: int | None = None) -> list[dict]:
    """Mandatsträger einer Wahlperiode (ohne Param: aktuelle):
    ``[{kpenr, name, fraktion, bis}]``. Zeilen ohne Personen-Link (Verwaltung,
    Einzelfälle ohne Personenseite) werden übersprungen — die tauchen über die
    Anwesenheitsdaten trotzdem im Produkt auf. Die Fraktion ist der AKTUELLE
    RIS-Stand (rückwirkend überschrieben, siehe Modul-Docstring)."""
    params: dict = {"__cwpnr": wpnr, "__cselect": 0} if wpnr is not None else {}
    soup = scraper._get("kp0041.php", **params)
    out: list[dict] = []
    for tr in soup.find_all("tr"):
        a = tr.find("a", href=re.compile(r"__kpenr=\d+"))
        if not a:
            continue
        m = re.search(r"__kpenr=(\d+)", a["href"])
        tds = tr.find_all("td")
        if not m or not tds:
            continue
        name = " ".join(tds[0].get_text(" ", strip=True).split())
        fraktion = " ".join(tds[1].get_text(" ", strip=True).split()) if len(tds) > 1 else ""
        bis = None
        for td in tds[2:]:
            bis = bis or _iso(td.get_text(" ", strip=True))
        if name:
            out.append({"kpenr": int(m.group(1)), "name": name,
                        "fraktion": fraktion or None, "bis": bis})
    return out


# --- Mitarbeit einer Person (kp0050) ------------------------------------------

def fetch_person_mitarbeit(scraper: CouncilScraper, kpenr: int) -> list[dict]:
    """Alle Gremien-Mitgliedschaften einer Person über alle Wahlperioden:
    ``[{kgrnr, gremium, rolle, von, bis}]``.

    Die Tabellenzeilen tragen am Ende einen Volltext „von DD.MM.YYYY
    [bis DD.MM.YYYY]" — die zuverlässigste Quelle für den Zeitraum. Die
    Fraktions-Spalte wird bewusst ignoriert (rückwirkend überschrieben)."""
    soup = scraper._get("kp0050.php", __kpenr=kpenr, __cwpall=1)
    out: list[dict] = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue  # Abschnitts-Überschriften („vom Rat", „Grundmandat" …)
        gremium = " ".join(tds[0].get_text(" ", strip=True).split())
        if not gremium:
            continue
        kgrnr = None
        a = tr.find("a", href=re.compile(r"__kgrnr=\d+"))
        if a:
            m = re.search(r"__kgrnr=(\d+)", a["href"])
            if m:
                kgrnr = int(m.group(1))

        row_text = " ".join(tr.get_text(" ", strip=True).split())
        vb = _VON_BIS_RE.search(row_text)
        von = _iso(vb.group(1)) if vb else None
        bis = _iso(vb.group(2)) if vb and vb.group(2) else None
        if not von:  # Fallback: erste/zweite Datumszelle
            dates = _DATE_RE.findall(row_text)
            if dates:
                von = f"{dates[0][2]}-{dates[0][1]}-{dates[0][0]}"
                if len(dates) > 1:
                    bis = f"{dates[1][2]}-{dates[1][1]}-{dates[1][0]}"

        # Rolle („Art der Mitarbeit"): letzte Zelle ohne Ziffern, die nicht das
        # Gremium ist — robust gegen die responsiven Kombi-Zellen der Tabelle.
        rolle = None
        for td in tds[1:]:
            t = " ".join(td.get_text(" ", strip=True).split())
            if t and not any(ch.isdigit() for ch in t) and t != gremium:
                rolle = t
        if rolle and len(rolle) > 60:  # Kombi-Zelle erwischt → letztes Wortpaar
            rolle = rolle.split()[-1]

        if von or kgrnr:
            out.append({"kgrnr": kgrnr, "gremium": gremium, "rolle": rolle,
                        "von": von, "bis": bis})
    return out


def is_future(datum: str | None) -> bool:
    """True für Beratungsstationen, die noch bevorstehen."""
    return bool(datum) and datum > date.today().isoformat()
