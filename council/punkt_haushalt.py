"""Haushaltswissen an einem Tagesordnungspunkt: der Kasten „Im Haushalt".

Tim, 13.11.2026: „können wir zu allen finanzpolitischen TOPs (von denen es ja
regelmäßig viele gibt) Wissen von unserer Haushaltsseite einbringen?" — für
alle, nicht nur mit Haushaltsrecht.

Gemessen an den 983 öffentlichen Punkten mit Vorlage seit 11/2025: Rund jeder
sechste nennt etwas, wozu die Haushaltsdaten eine Zahlenreihe haben — einen
Teilhaushalt, ein Produkt mit Nummer, einen städtischen Betrieb, eine Steuer,
die Schulden. Die Seite zeigt dann die letzten Jahre dieser Reihe, damit eine
Zahl aus der Vorlage eine Größenordnung bekommt („481.300 Euro mehr für den
Rettungsdienst" — bei 65 Millionen im Teilhaushalt).

**Ohne Modell, und lieber nichts als etwas Falsches.** Zugeordnet wird nur,
was die Vorlage ausdrücklich nennt:

- die Nummer eines Teilhaushalts oder Produkts — aber nicht aus dem Satz zur
  Deckung („gedeckt durch Mehrerträge im Teilhaushalt 04"): Das ist die
  Quelle des Geldes, nicht der Gegenstand des Punkts;
- den Namen eines Betriebs zusammen mit einem Finanzwort (der
  „Betriebsausschuss Abfallwirtschaftsbetrieb" im Titel „Sitzungstermine 2026"
  ist kein Finanzpunkt);
- eine Steuer, die Schulden, den Haushalt als Ganzes im TITEL.

Geprüft an 59 verschiedenen Punkten (13.11.2026, ein Modell urteilte „betrifft
die Reihe den Punkt?" und „hilft sie beim Einordnen?"). Daraus stammen drei
Regeln: kein Teilhaushalt neben einer investiven Mehrauszahlung, bei
Nachbewilligungen nur die Aufwendungen, und der Betrieb über seine Kennung
statt über den Namen.

**Plan und Ist stehen nie in einer Reihe** — jede Reihe sagt, was sie ist
(``basis``), und trägt ihre Belege.
"""
from __future__ import annotations

import re

from council import lotti_werkzeuge as lw

#: Wie viele Jahre eine Reihe zeigt — genug für eine Richtung, wenig genug für einen Kasten.
JAHRE = 3
MAX_BLOECKE = 3

_SATZ = re.compile(r"(?<=[.!?])\s+")
_DECKUNG = re.compile(r"deckung|gedeckt", re.IGNORECASE)
_TEILHAUSHALT = re.compile(r"Teilhaushalt(?:e?s)?\s+(\d{1,2})\b")
_PRODUKT = re.compile(r"\bP\d{2}\.\d{6}\b")
_MEHRAUFWAND = re.compile(r"Mehraufwendung\w*\s+in\s+Höhe\s+von\s+([\d.]+(?:,\d{1,2})?)\s*(?:Euro|EUR|€)", re.IGNORECASE)
_MEHRAUSZAHLUNG = re.compile(r"mehrauszahlung", re.IGNORECASE)
_BEWILLIGUNG = re.compile(r"überplanmäßig|außerplanmäßig|mehraufwendung", re.IGNORECASE)
_FINANZWORT = re.compile(r"wirtschaftsplan|finanzplan|jahresabschluss|lagebericht|zwischenbericht|quartalsbericht|"
                         r"ergebnisverwendung|verlustausgleich|entlastung", re.IGNORECASE)
_BETRIEBE: tuple[tuple[str, re.Pattern], ...] = (
    ("awb", re.compile(r"abfallwirtschaftsbetrieb|\bAWB\b", re.IGNORECASE)),
    ("bbgo", re.compile(r"bäderbetriebsgesellschaft|\bBBGO\b", re.IGNORECASE)),
    ("bbo", re.compile(r"bäderbetrieb(?!sgesellschaft)|eigenbetrieb(?:e?s)?\s+bäder|\bBBO\b", re.IGNORECASE)),
    ("egh", re.compile(r"gebäudewirtschaft\s+und\s+hochbau|\bEGH\b", re.IGNORECASE)),
    ("hafen", re.compile(r"eigenbetrieb(?:e?s)?\s+hafen|hafen\s+der\s+stadt", re.IGNORECASE)),
    ("stadion_planung", re.compile(r"stadionplanungsgesellschaft", re.IGNORECASE)),
    ("stadion", re.compile(r"stadion\s+oldenburg\s+gmbh", re.IGNORECASE)),
)
_GRUNDSTEUER = re.compile(r"grundsteuer", re.IGNORECASE)
_GEWERBESTEUER = re.compile(r"gewerbesteuer", re.IGNORECASE)
_HEBESATZ = re.compile(r"hebes[aä]tz", re.IGNORECASE)
_REALSTEUER = re.compile(r"realsteuer", re.IGNORECASE)
_SCHULDEN = re.compile(r"kreditaufnahme|schulden|umschuldung|kreditermächtigung", re.IGNORECASE)
#: Der Haushalt als Ganzes — nicht ein Teil davon („Haushalt 2026 –
#: Verwaltungsentwurf – Rechtsfähige Stiftungen") und nicht sein Zeitplan:
#: Daneben stünde die Summe aller Teilhaushalte ohne Bezug zum Punkt.
_HAUSHALT_GANZ = re.compile(r"haushalt(?:splan)?\s+20\d\d(?:\s*[-–—]\s*verwaltungsentwurf)?", re.IGNORECASE)
_HAUSHALT_WORT = re.compile(r"haushaltssatzung|nachtragshaushalt", re.IGNORECASE)
_TITEL_ENDE = re.compile(r"\s*[-–—]\s*(?:Bericht|Beschluss|Beschlussantrag|Antrag)\b.*$", re.IGNORECASE)
_ABSCHLUSS_STADT = re.compile(r"jahresabschluss.{0,60}(?:kernverwaltung|der\s+stadt\s+oldenburg)", re.IGNORECASE)


def _ohne_deckung(text: str | None) -> str:
    """Der Text ohne die Sätze, die sagen, woraus etwas bezahlt wird."""
    return " ".join(s for s in _SATZ.split(text or "") if not _DECKUNG.search(s))


def _betrag(text: str) -> float | None:
    m = _MEHRAUFWAND.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


class _Belege:
    """Die Belege eines Blocks, je Dokument einmal."""

    def __init__(self, store) -> None:
        self._store, self.liste = store, []

    def merke(self, herkunft_id: int | None) -> None:
        b = lw._beleg(self._store, herkunft_id)  # noqa: SLF001 — derselbe Beleg wie in Lottis Antworten
        if b and all(b["url"] != x["url"] for x in self.liste) and len(self.liste) < 3:
            self.liste.append({"label": b["label"], "year": b.get("year"), "url": b["url"]})


def _block(key: str, title: str, basis: str, note: str, unit: str, columns: list[str], rows: list[dict],
           belege: _Belege, page: str | None, **mehr) -> dict | None:
    rows = [r for r in rows if any(v is not None for v in r["values"])]
    if not rows:
        return None
    return {"key": key, "title": title, "basis": basis, "note": note, "unit": unit, "columns": columns,
            "rows": rows, "sources": belege.liste, "page": page, "description": mehr.get("description"),
            "share": mehr.get("share")}


def _teilhaushalt(store, nr: int, jahr: int, mehraufwand: float | None, nur_aufwand: bool) -> dict | None:
    zeilen = store.teilhaushalt_plan(nr, jahr + 1, JAHRE)
    if not zeilen:
        return None
    belege = _Belege(store)
    for z in zeilen:
        belege.merke(z["herkunft_id"])
    anteil = None
    im_jahr = next((z for z in zeilen if z["year"] == jahr and z["expenses"]), None)
    if mehraufwand and im_jahr:
        # Exakt; die Seite rundet genau einmal.
        anteil = {"amount": mehraufwand, "of": im_jahr["expenses"], "year": jahr,
                  "percent": mehraufwand / im_jahr["expenses"] * 100}
    # Bei einer Nachbewilligung geht es um Ausgaben. Die Erträge daneben
    # führten in die Irre: Im Teilhaushalt 04 stehen dort 529 Millionen Euro
    # Steuern, die mit dem Rechtsamt nichts zu tun haben.
    spalten = ["Aufwendungen"] if nur_aufwand else ["Aufwendungen", "Erträge"]
    return _block(f"sub_budget:{nr}", f"Teilhaushalt {nr:02d} · {zeilen[-1]['name']}", "plan",
                  "Haushaltsplan des jeweiligen Jahres", "EUR", spalten,
                  [{"year": z["year"], "values": [z["expenses"]] if nur_aufwand else [z["expenses"], z["revenues"]]}
                   for z in zeilen], belege, "sub_budgets", share=anteil)


def _teilhaushalte(store, titel: str, gegenstand: str, jahr: int) -> list[int]:
    """Die gemeinten Teilhaushalte: Nummern aus dem Titel (höchstens zwei),
    sonst der Name („Teilhaushalt Kultur, Museen, Sport"), sonst die erste
    Nummer aus dem Beschlussvorschlag."""
    titel_ohne = _ohne_deckung(titel)
    nummern = list(dict.fromkeys(int(n) for n in _TEILHAUSHALT.findall(titel_ohne)))[:2]
    if not nummern and "teilhaushalt" in titel_ohne.lower():
        klein = titel_ohne.lower()
        nummern = [nr for nr, name in sorted(store.teilhaushalt_namen(jahr + 1).items())
                   if name and name.lower() in klein][:1]
    if not nummern:
        m = _TEILHAUSHALT.search(gegenstand)
        nummern = [int(m.group(1))] if m else []
    return nummern


def _produkt(store, nummer: str, jahr: int) -> dict | None:
    zeilen = store.produkt_plan(nummer, jahr + 1, JAHRE)
    if not zeilen:
        return None
    belege = _Belege(store)
    for z in zeilen:
        belege.merke(z["herkunft_id"])
    return _block(f"product:{nummer}", f"Produkt {nummer} · {zeilen[-1]['name']}", "plan",
                  "Haushaltsplan des jeweiligen Jahres", "EUR", ["Aufwendungen", "Erträge"],
                  [{"year": z["year"], "values": [z["expenses"], z["revenues"]]} for z in zeilen],
                  belege, "products", description=(zeilen[-1].get("short_description") or "").strip() or None)


def _betrieb(store, kennung: str, jahr: int) -> dict | None:
    zeilen = store.betrieb_plan(kennung, jahr + 1, JAHRE)
    if not zeilen:
        return None
    belege = _Belege(store)
    for z in zeilen:
        belege.merke(z["herkunft_id"])
    return _block(f"enterprise:{kennung}", zeilen[-1]["name"], "plan", "Wirtschaftsplan des jeweiligen Jahres", "EUR",
                  ["Erträge", "Aufwendungen", "Geplantes Ergebnis"],
                  [{"year": z["year"], "values": [z["revenues"], z["expenses"], z["result"]]} for z in zeilen],
                  belege, "enterprises")


def _reihe(store, reihe: str, jahr: int, basis: str, note: str, page: str, spalte: str, n: int = JAHRE) -> dict | None:
    titel, _sql, einheit = lw.REIHEN[reihe]
    _alle, treffer = lw.zeitreihe_daten(store, reihe, 1900, jahr + 1)
    treffer = [t for t in treffer if t[1] is not None]
    if basis == "rate":
        # Ein Satz „gilt ab" einem Jahr — eine Zeile, die den alten Satz nur
        # wiederholt (die Quelle führt jede Neufestsetzung), sagt nichts.
        treffer = [t for i, t in enumerate(treffer) if i == 0 or t[1] != treffer[i - 1][1]]
    treffer = treffer[-n:]
    if not treffer:
        return None
    belege = _Belege(store)
    for t in treffer:
        belege.merke(t[2])
    return _block(f"series:{reihe}", titel.split(" (")[0], basis, note, {"€": "EUR", "%": "percent"}.get(einheit, "count"),
                  [spalte], [{"year": int(t[0]), "values": [t[1]]} for t in treffer], belege, page)


def item_budget_context(store, punkt: dict, vorlage: dict | None) -> dict | None:
    """Die Zahlenreihen zum Punkt — oder ``None``, wenn die Vorlage nichts
    nennt, wozu der Haushalt eine Reihe hat."""
    item = punkt.get("item") or {}
    titel = item.get("title") or ""
    vorschlag = (vorlage or {}).get("proposed_decision") or ""
    try:
        jahr = int(str(punkt.get("session_date") or "")[:4])
    except ValueError:
        return None
    gegenstand = f"{_ohne_deckung(titel)} {_ohne_deckung(vorschlag)}"
    bloecke: list[dict | None] = []

    # 1. Teilhaushalt. Nicht bei einer Mehrauszahlung: Die ist eine Investition,
    #    der Teilhaushalt daneben zeigte laufende Aufwendungen — zwei Töpfe.
    teilhaushalte = [] if _MEHRAUSZAHLUNG.search(titel) else _teilhaushalte(store, titel, gegenstand, jahr)
    bewilligung = bool(_BEWILLIGUNG.search(titel))
    betrag = (_betrag(titel) or _betrag(vorschlag)) if len(teilhaushalte) == 1 else None
    bloecke.extend(_teilhaushalt(store, nr, jahr, betrag, bewilligung) for nr in teilhaushalte)

    # 2. Produkte mit Nummer — höchstens zwei; eine Vorlage, die zwanzig
    #    aufzählt (ein ganzer Teilhaushalt), meint keines davon im Besonderen.
    nummern = list(dict.fromkeys(_PRODUKT.findall(gegenstand)))
    if 0 < len(nummern) <= 2:
        bloecke.extend(_produkt(store, n, jahr) for n in nummern)

    # 3. Betriebe: Name UND Finanzwort im Titel.
    if _FINANZWORT.search(titel):
        for kennung, muster in _BETRIEBE:
            if muster.search(titel):
                bloecke.append(_betrieb(store, kennung, jahr))
                break

    # 4. Steuern, Schulden, der Haushalt als Ganzes — nur über den Titel.
    grund, gewerbe = bool(_GRUNDSTEUER.search(titel)), bool(_GEWERBESTEUER.search(titel))
    if _HEBESATZ.search(titel):
        # Eine Hebesatz-Satzung setzt die Sätze fest: erst beide Sätze, dann
        # (soweit Platz ist) was die Steuer einbringt. „Realsteuern" sind
        # Grund- und Gewerbesteuer.
        if _REALSTEUER.search(titel) or not (grund or gewerbe):
            grund = gewerbe = True
        if grund:
            bloecke.append(_reihe(store, "hebesatz_grundsteuer_b", jahr, "rate", "gilt ab dem genannten Jahr", "taxes", "Hebesatz"))
        if gewerbe:
            bloecke.append(_reihe(store, "hebesatz_gewerbesteuer", jahr, "rate", "gilt ab dem genannten Jahr", "taxes", "Hebesatz"))
        if grund:
            bloecke.append(_reihe(store, "grundsteuer", jahr, "actual", "tatsächlich eingenommen", "taxes", "Einnahmen"))
        if gewerbe:
            bloecke.append(_reihe(store, "gewerbesteuer", jahr, "actual", "tatsächlich eingenommen", "taxes", "Einnahmen"))
    else:
        if grund:
            bloecke.append(_reihe(store, "hebesatz_grundsteuer_b", jahr, "rate", "gilt ab dem genannten Jahr", "taxes", "Hebesatz"))
            bloecke.append(_reihe(store, "grundsteuer", jahr, "actual", "tatsächlich eingenommen", "taxes", "Einnahmen"))
        if gewerbe:
            bloecke.append(_reihe(store, "hebesatz_gewerbesteuer", jahr, "rate", "gilt ab dem genannten Jahr", "taxes", "Hebesatz"))
            bloecke.append(_reihe(store, "gewerbesteuer", jahr, "actual", "tatsächlich eingenommen", "taxes", "Einnahmen"))
    if _SCHULDEN.search(titel):
        bloecke.append(_reihe(store, "schulden", jahr, "actual", "Stand am 31.12.", "debt", "Schulden"))
        bloecke.append(_reihe(store, "schulden_je_einwohner", jahr, "actual", "Stand am 31.12.", "debt", "je Einwohner*in"))
    if _ABSCHLUSS_STADT.search(titel):
        bloecke.append(_reihe(store, "ordentliches_ergebnis_ist", jahr, "actual", "laut Jahresabschluss", "plan_actual", "Ergebnis"))
    elif not teilhaushalte and (_HAUSHALT_WORT.search(titel) or _HAUSHALT_GANZ.fullmatch(_TITEL_ENDE.sub("", titel).strip())):
        zeilen = store.haushalt_gesamt_plan(jahr + 1, JAHRE)
        belege = _Belege(store)
        for z in zeilen:
            belege.merke(z["herkunft_id"])
        bloecke.append(_block("budget:total", "Stadthaushalt insgesamt", "plan", "Haushaltsplan des jeweiligen Jahres", "EUR",
                              ["Aufwendungen", "Erträge"],
                              [{"year": z["year"], "values": [z["expenses"], z["revenues"]]} for z in zeilen],
                              belege, None))

    fertig = [b for b in bloecke if b][:MAX_BLOECKE]
    return {"blocks": fertig} if fertig else None
