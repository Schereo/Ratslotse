"""Fördermittel von außen — was EU und Bund der Stadt und ihren Gesellschaften
für einzelne Vorhaben bewilligt haben (Plan Haushalt-Blickwinkel, B2).

Der Haushalt zeigt Zuweisungen als Summe je Ertragsart. Welche Vorhaben
dahinterstehen, steht in zwei öffentlichen Listen:

* **EU** — die „Liste der Vorhaben" für EFRE und ESF(+) in Niedersachsen
  (Transparenzpflicht nach Art. 49 der Dachverordnung), halbjährlich als
  XLSX auf europa-fuer-niedersachsen.niedersachsen.de, je Förderperiode
  eine Datei je Fonds. Spalten: Begünstigter, Vorhaben, Laufzeit,
  förderfähige Kosten, Unionsbeitrag.
* **Bund** — der Förderkatalog (foerderportal.bund.de/foekat): jedes
  Vorhaben der Projektförderung des Bundes mit Förderkennzeichen, Ressort,
  Laufzeit und Bundesanteil. Eine Suche nach der Gemeinde Oldenburg (Oldb)
  liefert rund 1.300 Vorhaben aller Empfänger als CSV.

WER ZÄHLT (Tims Entscheidung 24.09.2026: Vereine und Träger mit Namen,
Privatpersonen nie): nur die Stadt und ihre Gesellschaften, über eine
**kuratierte** Namensliste (:data:`EMPFAENGER`) — kein unscharfer Abgleich.
„Stadt Oldenburg in Holstein" ist ein anderer Empfänger, und der Name
„Volkshochschule Oldenburg" gehört in beiden Listen derselben gGmbH, aber
nur, weil jemand es nachgesehen hat. Im Förderkatalog muss zusätzlich die
Gemeindekennziffer 03403000 stimmen.

WAS DIE LISTEN NICHT ZEIGEN, und die Seite sagt es: Städtebauförderung und
Landesprogramme (ohne EU-Anteil) stehen in keiner der beiden. Der
Unionsbeitrag ist die Bewilligung, nicht der ausgezahlte Betrag.

DIE PROBE
---------

* Förderkatalog: Die CSV hat so viele Zeilen, wie die Suche Treffer meldet
  — sonst ist der Export abgeschnitten.
* EU: Die Spalten werden am Kopf erkannt, nicht an ihrer Position (die
  Periode 2021–2027 ordnet sie anders als 2014–2020). Jede übernommene Zeile
  hat einen Betrag, einen Beginn, und der Unionsbeitrag übersteigt die Kosten
  nicht.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

PROBE_FOEKAT = "foekat_export_complete"
PROBE_EU = "eu_list_columns"

LISTEN_URL = ("https://www.europa-fuer-niedersachsen.niedersachsen.de/startseite/"
              "regionen_und_foerderung/efre_und_esf/liste-der-vorhaben-152610.html")
FOEKAT_BASIS = "https://foerderportal.bund.de/foekat/jsp/"
FOEKAT_GEMEINDE = "Oldenburg (Oldb)"
GEMEINDEKENNZIFFER = "03403000"

#: Die Empfänger, die zur Stadt gehören — Schlüssel, Anzeigename und die
#: Schreibweisen, unter denen die Listen sie führen (gemessen 24.09.2026).
#: Nur hier eintragen, was nachgesehen ist: „GSG ENERGIE GmbH" ist eine
#: Tochter der GSG und steht nicht im Beteiligungsbericht, der Zweckverband
#: KDO ist keine Gesellschaft der Stadt.
EMPFAENGER: dict[str, tuple[str, tuple[str, ...]]] = {
    "city": ("Stadt Oldenburg", (
        "Stadt Oldenburg", "Stadt Oldenburg (Oldb)",
        "Stadt Oldenburg Amt für Wirtschaftsförderung")),
    "transit": ("Verkehr und Wasser GmbH", ("Verkehr und Wasser GmbH",)),
    "adult_education": ("Volkshochschule Oldenburg", (
        "Volkshochschule Oldenburg", "Volkshochschule Oldenburg gGmbH")),
    "housing": ("GSG Oldenburg", (
        "GSG Oldenburg Bau- und Wohngesellschaft mbH",
        "GSG Oldenburg Bau- und Wohngesellschaft mit beschränkter Haftung")),
    "hospital": ("Klinikum Oldenburg", (
        "Klinikum Oldenburg AöR", "Klinikum Oldenburg Anstalt des öffentlichen Rechts")),
    "tech_center": ("TGO Technologie- und Gründerzentrum", (
        "TGO GmbH", "TGO Besitz GmbH & Co. KG",
        "TGO Technologie- und Gründerzentrum Oldenburg GmbH")),
    "tourism": ("Oldenburg Tourismus und Marketing", (
        "Oldenburg Tourismus & Marketing GmbH", "Oldenburg Tourismus und Marketing GmbH")),
    "dispatch_center": ("Großleitstelle Oldenburger Land", (
        "Großleitstelle Oldenburger Land AöR",)),
    "event_hall": ("Weser-Ems Halle", ("Weser-Ems Halle Oldenburg GmbH & Co. KG",)),
    "pools": ("Bäderbetriebsgesellschaft", ("Bäderbetriebsgesellschaft Oldenburg mbH",)),
}


def _norm(name: str) -> str:
    return " ".join(str(name or "").split()).casefold()


_SCHLUESSEL = {_norm(n): k for k, (_, namen) in EMPFAENGER.items() for n in namen}


def empfaenger_schluessel(name: str) -> str | None:
    """Der Schlüssel aus :data:`EMPFAENGER` — nur bei exakt gleichem Namen."""
    return _SCHLUESSEL.get(_norm(name))


class FoerderFehler(ValueError):
    """Eine Liste lässt sich nicht so lesen, dass die Probe besteht."""


@dataclass
class Vorhaben:
    source: str                    # efre | esf | foekat
    source_id: str
    recipient: str
    recipient_key: str
    title: str
    funder: str                    # „EU" oder das Ressort (BMV, BMWE …)
    program: str | None            # Fonds/Periode bzw. Leistungsplansystematik
    amount_total: float | None     # förderfähige bzw. Gesamtkosten (nur EU)
    amount_granted: float | None   # Unionsbeitrag bzw. Bundesanteil
    start: str | None              # ISO
    end: str | None
    summary: str | None = None
    period: str | None = None      # 2014-2020 | 2021-2027 (nur EU)


@dataclass
class Lesung:
    vorhaben: list[Vorhaben] = field(default_factory=list)
    stand: str | None = None       # Datenstand der Liste, ISO
    zeilen: int = 0                # Datenzeilen der ganzen Liste
    hinweise: list[str] = field(default_factory=list)


def _datum(wert) -> str | None:
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.date().isoformat()
    if isinstance(wert, date):
        return wert.isoformat()
    s = str(wert).strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else None


def _betrag(wert) -> float | None:
    if wert is None or wert == "":
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    s = str(wert).strip().replace("€", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


_MONATE = {m: i for i, m in enumerate(
    ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "dezember"], 1)}

#: Spaltenköpfe der EU-Listen → Feld. Beide Perioden, deutsch; gesucht wird
#: der Anfang des Kopfes (Zeilenumbrüche im Kopf zählen als Leerzeichen).
_EU_SPALTEN = {
    "name des begünstigten": "recipient",
    "code des vorhabens": "code",
    "bezeichnung des vorhabens": "title",
    "zusammenfassung des vorhabens": "summary",
    "zweck und erwartete": "summary",
    "datum des beginns": "start",
    "datum des endes": "end",
    "voraussichtliches oder tatsächliches datum des abschlusses": "end",
    "gesamtbetrag der förderfähigen": "total",
    "gesamtkosten des vorhabens": "total",
    "unionsbeitrag": "eu",
    "betroffener fonds": "fund",
    "kategorie der region": "fund",
}


def lies_eu(zeilen: list[tuple], *, fonds: str, periode: str) -> Lesung:
    """Eine Liste der Vorhaben (Zeilen des ersten Blatts) → die Vorhaben der
    Stadt und ihrer Gesellschaften. Wirft :class:`FoerderFehler`, wenn der
    Kopf fehlt."""
    aus = Lesung()
    kopf_i, spalten = None, {}
    for i, r in enumerate(zeilen[:30]):
        zellen = [" ".join(str(c).split()).casefold() if c is not None else "" for c in r]
        treffer = {}
        for j, z in enumerate(zellen):
            for anfang, feld in _EU_SPALTEN.items():
                if z.startswith(anfang) and feld not in treffer:
                    treffer[feld] = j
        if {"recipient", "title", "start", "eu"} <= set(treffer):
            kopf_i, spalten = i, treffer
            break
        stand = re.search(r"DS:\s*(\d{1,2})\.\s*([A-Za-zä]+)\s+(\d{4})", " ".join(map(str, filter(None, r))))
        if stand and stand.group(2).casefold() in _MONATE:
            aus.stand = (f"{stand.group(3)}-{_MONATE[stand.group(2).casefold()]:02d}-"
                         f"{int(stand.group(1)):02d}")
    if kopf_i is None:
        raise FoerderFehler(f"{fonds} {periode}: Spaltenkopf nicht gefunden")
    for r in zeilen[kopf_i + 1:]:
        if not r or len(r) <= max(spalten.values()):
            continue
        name = r[spalten["recipient"]]
        if name is None or _norm(name) in ("beneficiary name", ""):
            continue
        aus.zeilen += 1
        schluessel = empfaenger_schluessel(name)
        if not schluessel:
            continue
        eu = _betrag(r[spalten["eu"]])
        gesamt = _betrag(r[spalten["total"]]) if "total" in spalten else None
        beginn = _datum(r[spalten["start"]])
        titel = " ".join(str(r[spalten["title"]] or "").split())
        if eu is None or beginn is None or not titel:
            aus.hinweise.append(f"{titel or '?'}: Betrag oder Beginn fehlt — nicht übernommen")
            continue
        if gesamt is not None and eu > gesamt + 1:
            aus.hinweise.append(f"{titel}: Unionsbeitrag über den Kosten — nicht übernommen")
            continue
        code = r[spalten["code"]] if "code" in spalten else None
        if not code:
            # 2014–2020 führt keinen Code: Name, Titel und Beginn sind der
            # Schlüssel (zwei Zeilen mit allen dreien gleich gibt es dort nicht).
            code = "h" + hashlib.sha1(f"{_norm(name)}|{_norm(titel)}|{beginn}".encode(),
                                    usedforsecurity=False).hexdigest()[:12]
        aus.vorhaben.append(Vorhaben(
            source=fonds, source_id=str(code), recipient=" ".join(str(name).split()),
            recipient_key=schluessel, title=titel, funder="EU",
            program=f"{fonds.upper()} {periode}", amount_total=gesamt, amount_granted=eu,
            start=beginn, end=_datum(r[spalten["end"]]) if "end" in spalten else None,
            summary=(" ".join(str(r[spalten["summary"]] or "").split()) or None)
            if "summary" in spalten else None,
            period=periode))
    if not aus.zeilen:
        raise FoerderFehler(f"{fonds} {periode}: keine Datenzeile")
    return aus


def lies_foekat(text: str, treffer: int | None) -> Lesung:
    """Die CSV des Förderkatalogs (Semikolon, Zellen als ``="…"``).

    ``treffer`` ist die Zahl, die die Suchseite meldet; die Probe verlangt
    genau so viele Zeilen."""
    zeilen = [[c.removeprefix("=").strip('"') for c in r]
              for r in csv.reader(io.StringIO(text), delimiter=";") if r]
    if not zeilen:
        raise FoerderFehler("Förderkatalog: leere Datei")
    kopf = [" ".join(k.split()) for k in zeilen[0]]

    def spalte(name: str, nach: int = -1) -> int:
        for i, k in enumerate(kopf):
            if i > nach and k.startswith(name):
                return i
        raise FoerderFehler(f"Förderkatalog: Spalte „{name}“ fehlt")

    fkz, ressort = spalte("FKZ"), spalte("Ressort")
    name = spalte("Förderempfänger")
    gkz = spalte("Gemeindekennziffer")
    thema, lps = spalte("Thema"), spalte("Klartext Leistungsplansystematik")
    von, bis, summe = spalte("Laufzeit von"), spalte("Laufzeit bis"), spalte("Förder- / Auftragssumme")
    daten = [r for r in zeilen[1:] if len(r) > summe]
    aus = Lesung(zeilen=len(daten))
    if treffer is not None and len(daten) != treffer:
        raise FoerderFehler(f"Förderkatalog: {len(daten)} Zeilen, die Suche meldet {treffer}")
    for r in daten:
        schluessel = empfaenger_schluessel(r[name])
        if not schluessel or r[gkz] != GEMEINDEKENNZIFFER:
            continue
        betrag = _betrag(r[summe])
        if betrag is None:
            aus.hinweise.append(f"{r[fkz]}: kein Betrag — nicht übernommen")
            continue
        aus.vorhaben.append(Vorhaben(
            source="foekat", source_id=r[fkz], recipient=" ".join(r[name].split()),
            recipient_key=schluessel, title=" ".join(r[thema].split()), funder=r[ressort],
            program=r[lps] or None, amount_total=None, amount_granted=betrag,
            start=_datum(r[von]), end=_datum(r[bis])))
    return aus


def treffer_aus_seite(html: str) -> int | None:
    """„Suchergebnis (1295 Treffer)" → 1295; ``0`` bei „keine Ergebnisse"."""
    m = re.search(r"\(([\d.]+)(?:&nbsp;|\s)Treffer\)", html)
    if m:
        return int(m.group(1).replace(".", ""))
    return 0 if "liefert keine Ergebnisse" in html else None


def dubletten(vorhaben: list[Vorhaben]) -> list[tuple[Vorhaben, Vorhaben]]:
    """Paare aus EU- und Bundesliste mit gleichem Titel und Beginn — ein
    Vorhaben, das beide Geber führen, erschiene sonst doppelt in der Summe."""
    eu = {(_norm(v.title), v.start): v for v in vorhaben if v.funder == "EU"}
    return [(eu[(_norm(v.title), v.start)], v) for v in vorhaben
            if v.funder != "EU" and (_norm(v.title), v.start) in eu]


def eu_listen(html: str) -> list[tuple[str, str, str]]:
    """Die XLSX-Links der Übersichtsseite: ``(url, fonds, periode)``."""
    aus = []
    for url in dict.fromkeys(re.findall(r'href="([^"]+\.xlsx)"', html)):
        datei = url.rsplit("/", 1)[-1]
        fonds = "esf" if re.search(r"_ESF", datei) else "efre" if "EFRE" in datei else None
        if not fonds:
            continue
        periode = "2014-2020" if "2014-2020" in datei else "2021-2027"
        aus.append((url, fonds, periode))
    return aus
