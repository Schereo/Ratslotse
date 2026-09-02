"""Kredite und Zinsen — die Unterrichtungen des Rates nach der Kreditrichtlinie.

Die Schuldenseite sagt, wie hoch die Schulden sind (Statistisches Jahrbuch,
Bilanz, integrierte Schulden). Was sie KOSTEN, sagte bis 09/2026 keine
Schicht — obwohl die Verwaltung den Rat seit 2018 regelmäßig darüber
unterrichtet: „Unterrichtung des Rates über Kreditaufnahmen,
Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie", seit
2022 monatlich bis vierteljährlich, davor als Einzelbericht je Umschuldung.

Was die Vorlagen hergeben — und was nicht
-----------------------------------------
Der Bericht ist Prosa in nummerierten Posten:

    1.) Kreditaufnahme des Bäderbetriebs Oldenburg am Kapitalmarkt in Höhe
        von 8.000.000,00 Euro … Zinssatz in Höhe von 3,46 % p. a. …
    2.) Umschuldung von Kommunalkrediten (Grundgeschäfte) in Höhe von
        insgesamt 48.241.251,34 Euro …

Aus der Überschrift kommen Art, Schuldner und Betrag; aus dem Absatz Zinssatz,
Zinsbindung und das Datum der Kreditentscheidung — soweit sie darin stehen.
Die Konditionen der Umschuldungen (Bank, Marge, Laufzeit je Darlehen) stehen in
den ANLAGEN, nicht im Vorlagentext; sie sind hier nicht drin, und der
Baustein sagt das. Bis 2021 hatte ein Bericht die Form „Umschuldung von
Kommunalkrediten in Höhe von insgesamt 95.480.807,12 EUR" — Betrag im Titel,
Zeitraum nur im Abschnitt „Finanzielle Auswirkungen".

Der Abschnitt „Finanzielle Auswirkungen" trägt bei Umschuldungen die einzige
Zahl, die den Nutzen beziffert: „… wird der Zinsaufwand gegenüber der
vergleichbaren herkömmlichen Kommunalkreditfinanzierung für den Zeitraum
16.11.2021 bis 16.02.2022 um 75.604,35 Euro reduziert." Sie reist als
``interest_saving`` mit, samt Zeitraum.

Berichte ohne Vorgang („Im Monat September 2022 sind keine Kredite …
aufgenommen oder umgeschuldet worden") kommen als Unterrichtung mit null
Posten herein: Der Monat ist damit belegt, nicht nur leer.

Zwei Proben, beide je Vorlage:

* :data:`ZEITRAUM` — der Berichtszeitraum steht im ersten Satz des Berichts
  (oder, bei der alten Form, im Zeitraum der Zinsersparnis). Ohne ihn hängt
  eine Unterrichtung an keinem Monat und fällt heraus.
* :data:`POSTEN_BETRAG` — jeder nummerierte Posten trägt seinen Betrag in der
  Überschrift („in Höhe von [insgesamt] X Euro"). Posten ohne Betrag
  (Ausleihungen ohne Summe, Verweise) bleiben als Posten mit ``amount NULL``
  stehen; die Probe gilt als bestanden, wenn kein Betrag ANDERS gelesen wurde
  als in der Überschrift.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

ZEITRAUM = "loan_notice_period"
POSTEN_BETRAG = "loan_item_heading_amount"

#: Fundstelle, die an jeder Zeile steht.
FUNDSTELLE = ("Abschnitt „Bericht“ der Unterrichtung — nummerierte Posten; "
              "Zinsersparnis aus „Finanzielle Auswirkungen“")

TITEL = re.compile(
    r"Unterrichtung des Rates über Kreditaufnahmen|"
    r"^Unterrichtung nach § 8 der Kreditrichtlinie|"
    r"^Umschuldung (?:von|eines) (?:Kommunal|Investitions)kredit", re.IGNORECASE)

#: Dieselbe Auswahl als SQL — für ``store.kreditunterrichtungen()`` und die
#: Dokumentmarke der Finanzquelle. Bis 09/2026 fehlte das dritte Muster in
#: beiden: Die Unterrichtungen von 2018 bis 2022 heißen „Unterrichtung nach
#: § 8 der Kreditrichtlinie über aufgenommene Kredite …" — ohne das Wort
#: „Kreditaufnahme" — und blieben damit vier Jahrgänge lang unsichtbar.
TITEL_SQL = ("(title LIKE '%Kreditaufnahme%' OR title LIKE 'Umschuldung%' "
             "OR title LIKE 'Unterrichtung nach § 8%')")

_MONATE = {m: i + 1 for i, m in enumerate(
    ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "dezember"))}
_MONAT_RX = "|".join(_MONATE)
_ZEITRAUM = re.compile(
    rf"Bericht:\s*(?:In den Monaten|Im Monat|Im Zeitraum|In dem Monat)\s+"
    rf"((?:{_MONAT_RX})(?:\s*,\s*(?:{_MONAT_RX}))*(?:\s+und\s+(?:{_MONAT_RX}))?)\s+(\d{{4}})"
    rf"(?:\s+und\s+((?:{_MONAT_RX}))\s+(\d{{4}}))?",
    re.IGNORECASE)
#: Die Form von 2021 nennt kein Jahr: „Innerhalb der Monate Januar und
#: Februar sind folgende Kredite …" — das Jahr kommt vom Dokumentdatum.
_ZEITRAUM_OHNE_JAHR = re.compile(
    rf"Bericht:\s*(?:Innerhalb der Monate|In den Monaten|Im Monat)\s+"
    rf"((?:{_MONAT_RX})(?:\s*,\s*(?:{_MONAT_RX}))*(?:\s+und\s+(?:{_MONAT_RX}))?)\s+sind",
    re.IGNORECASE)
_KEINE = re.compile(r"sind keine Kredite", re.IGNORECASE)
_DATUM = r"(\d{2})\.(\d{2})\.(\d{4})"
_DOK_DATUM = re.compile(rf"Datum:\s*{_DATUM}|^\s*{_DATUM}\s+(?:Amt|Fachdienst)")
_POSTEN = re.compile(r"(?<![\d.])(\d{1,2})\.\)\s+")
_BETRAG = re.compile(r"in H[öo]he von\s+(?:insgesamt\s+)?([\d.]+,\d{2})\s*(?:Euro|EUR)", re.IGNORECASE)
_BETRAG_FELD = re.compile(r"(?:Betrag|Abruf):\s*([\d.]+,\d{2})\s*(?:Euro|EUR)")
#: Die Überschrift eines Feldlisten-Vorgangs: Schuldner, Gedankenstrich, Art.
#: „EGH – Kreditaufnahme für Investitionen aus dem Wirtschaftsplan 2018",
#: „EB Hafen – Kreditaufnahme …", „EGH - Kreditneuaufnahme …:" (2018).
_FELD_KOPF = re.compile(
    r"((?:EGH|EB Hafen|Eigenbetrieb [A-ZÄÖÜ][\wäöüß]+(?: und [A-ZÄÖÜ][\wäöüß]+)?|"
    r"Bäderbetrieb(?: Oldenburg)?|BBO|Kernverwaltung|Abfallwirtschaftsbetrieb)\s*[–-]\s*"
    r"(Kredit(?:neu)?aufnahme|Umschuldung|Prolongation|Ausleihung)[^:]*?)\s*:?\s*$")
_ZINS = re.compile(r"Zinssatz(?:\s+in\s+H[öo]he\s+von|:)?\s*([\d]+,\d+)\s*%", re.IGNORECASE)
_BINDUNG_JAHRE = re.compile(r"Zinsbindung(?:en)?\s+(?:für\s+weitere|von|über)\s+(\d{1,2})\s+Jahre", re.IGNORECASE)
_BINDUNG_BIS = re.compile(
    rf"(?:Zinsbindung(?:sende)?|Zinsfestsetzung):?\s*(?:bis\s+(?:zum\s+)?)?{_DATUM}")
_ENTSCHEIDUNG = re.compile(rf"(?:Kreditentscheidung|Entscheidung)(?:en)?\s+vom\s+{_DATUM}")
_AM_ENTSCHIEDEN = re.compile(rf"Am\s+{_DATUM}\s+wurde")
_ERSPARNIS = re.compile(
    rf"Zinsaufwand[^.]{{0,160}}?(?:für den |im )?Zeitraum\s+{_DATUM}\s+bis\s+{_DATUM}\s+um\s+([\d.]+,\d{{2}})\s*(?:Euro|EUR)\s+reduziert",
    re.IGNORECASE)
_FINANZ = re.compile(r"Finanzielle Auswirkungen:?\s*(.*)$", re.IGNORECASE | re.DOTALL)
_SEITENFUSS = re.compile(r"Ausdruck vom:\s*\d{2}\.\d{2}\.\d{4}\s+Seite:\s*\d+/\d+\s*")

ARTEN: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("disbursement", re.compile(r"^\(Teil-\)\s*Auszahlung|Teilauszahlung", re.IGNORECASE)),
    ("loan", re.compile(r"^Kreditaufnahme|^Kreditneuaufnahme|Kreditaufnahme des|Kreditaufnahme für", re.IGNORECASE)),
    ("refinancing", re.compile(r"^Umschuldung", re.IGNORECASE)),
    ("prolongation", re.compile(r"^Prolongation", re.IGNORECASE)),
    ("lending", re.compile(r"^Ausleihung", re.IGNORECASE)),)
ART_NAMEN = {
    "loan": "Kreditaufnahme",
    "refinancing": "Umschuldung",
    "prolongation": "Prolongation",
    "disbursement": "Auszahlung einer Ausleihung",
    "lending": "Ausleihung",
    "other": "Sonstiger Vorgang",
}
_SCHULDNER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Bäderbetrieb Oldenburg", re.compile(r"B[äa]derbetrieb", re.IGNORECASE)),
    ("Eigenbetrieb Gebäudewirtschaft und Hochbau", re.compile(r"Geb[äa]udewirtschaft|\bEGH\b", re.IGNORECASE)),
    ("Eigenbetrieb BBO", re.compile(r"\bBBO\b")),
    ("Eigenbetrieb Hafen", re.compile(r"\bEB Hafen\b|Eigenbetrieb Hafen", re.IGNORECASE)),
    ("Abfallwirtschaftsbetrieb", re.compile(r"Abfallwirtschaftsbetrieb", re.IGNORECASE)),
    ("Kernverwaltung", re.compile(r"Kernverwaltung", re.IGNORECASE)),
)


def glatt(text: str | None) -> str:
    """Der PDF-Extrakt als ein Fließtext, ohne Seitenfüße und Trennstriche."""
    t = (text or "").replace("\r", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t)
    # Die PDFs von 2018 reißen Datumsziffern auseinander („16.0 5.2018",
    # „16. 08.2018") — nur an Datumsstellen zusammenfügen, nirgends sonst.
    t = re.sub(r"(\d{2})\.(\d) (\d)\.(\d{4})", r"\1.\2\3.\4", t)
    t = re.sub(r"(\d{2})\. (\d{2})\.(\d{4})", r"\1.\2.\3", t)
    return _SEITENFUSS.sub(" ", t).strip()


def de_zahl(roh: str) -> float:
    return float(roh.replace(".", "").replace(",", "."))


def iso(tag: str, monat: str, jahr: str) -> str:
    return f"{jahr}-{monat}-{tag}"


def erkenne(title: str | None) -> bool:
    return bool(TITEL.search(title or ""))


def zeitraum(text: str, jahr: int | None = None) -> tuple[str | None, str | None]:
    """„2026-06" bis „2026-08" aus „In den Monaten Juni, Juli und August 2026".

    ``jahr`` ist das Jahr des Dokumentdatums — für die Form ohne Jahr
    („Innerhalb der Monate Januar und Februar sind …", 2021). Reicht der
    Zeitraum über den Jahreswechsel („Dezember und Januar"), gehört der
    Dezember ins Vorjahr."""
    m = _ZEITRAUM.search(text)
    if not m:
        o = _ZEITRAUM_OHNE_JAHR.search(text)
        if not o or jahr is None:
            return None, None
        monate = [x.strip().lower() for x in re.split(r",|\s+und\s+", o.group(1)) if x.strip()]
        erster, letzter = _MONATE[monate[0]], _MONATE[monate[-1]]
        von_jahr = jahr - 1 if erster > letzter else jahr
        return f"{von_jahr}-{erster:02d}", f"{jahr}-{letzter:02d}"
    monate = [x.strip().lower() for x in re.split(r",|\s+und\s+", m.group(1)) if x.strip()]
    jahr = int(m.group(2))
    von = f"{jahr}-{_MONATE[monate[0]]:02d}"
    if m.group(3):   # „Dezember 2022 und Januar 2023"
        return von, f"{int(m.group(4))}-{_MONATE[m.group(3).lower()]:02d}"
    return von, f"{jahr}-{_MONATE[monate[-1]]:02d}"


def art(kopf: str) -> str:
    # Aufzählungs-Glyphen davor („\uf0b7 Umschuldung …", 2018/2019) sind kein
    # Teil der Überschrift — mit ihnen griff kein einziges ^-Muster.
    k = re.sub(r"^[\W_]+", "", kopf.strip())
    for name, rx in ARTEN:
        if rx.search(k):
            return name
    return "other"


def schuldner(kopf: str) -> str | None:
    for name, rx in _SCHULDNER:
        if rx.search(kopf):
            return name
    return None


def _posten(text: str) -> list[dict]:
    """Die nummerierten Posten des Berichts, je mit Überschrift und Absatz."""
    i = text.find("Bericht:")
    j = text.find("Finanzielle Auswirkungen")
    koerper = text[i:j if j > i else None] if i >= 0 else text
    marken = list(_POSTEN.finditer(koerper))
    aus: list[dict] = []
    for n, m in enumerate(marken):
        seq = int(m.group(1))
        if aus and seq <= aus[-1]["seq"]:
            break   # die Zusammenfassung wiederholt die Nummern — Schluss
        ende = marken[n + 1].start() if n + 1 < len(marken) else len(koerper)
        absatz = koerper[m.end():ende].strip()
        # Die Überschrift endet vor dem ersten Satz — der beginnt großgeschrieben
        # nach dem Betrag oder nach „für die Kernverwaltung".
        kopf = absatz
        b = _BETRAG.search(absatz)
        if b:
            rest = absatz[b.end():]
            fuer = re.match(r"\s+(?:für|beim|des|der|an)\s+[^.]{0,80}?(?=\s[A-ZÄÖÜ][a-zäöü]+\s)", rest)
            kopf = absatz[:b.end() + (fuer.end() if fuer else 0)]
        else:
            satz = re.search(r"\s(?=[A-ZÄÖÜ][a-zäöü]+\s)", absatz[40:])
            kopf = absatz[:40 + satz.start()] if satz else absatz[:160]
        kopf = kopf.strip().rstrip(".")
        aus.append({
            "seq": seq, "heading": kopf[:200], "kind": art(kopf),
            "borrower": schuldner(kopf),
            "amount": de_zahl(b.group(1)) if b else None,
            "rate_pct": (lambda z: de_zahl(z.group(1)) if z else None)(_ZINS.search(absatz)),
            "fixed_years": (lambda z: int(z.group(1)) if z else None)(_BINDUNG_JAHRE.search(absatz)),
            "fixed_until": (lambda z: iso(*z.groups()) if z else None)(_BINDUNG_BIS.search(absatz)),
            "decided_at": (lambda z: iso(*z.groups()) if z else None)(
                _ENTSCHEIDUNG.search(absatz) or _AM_ENTSCHIEDEN.search(absatz)),
            "summary": absatz[:400],
        })
    return aus


def _posten_formular(text: str) -> list[dict]:
    """Die Form von 2022: ein Vorgang als Feldliste („Betrag: … Zinssatz: …")."""
    i = text.find("Bericht:")
    j = text.find("Finanzielle Auswirkungen")
    koerper = text[i:j if j > i else None] if i >= 0 else text
    b = _BETRAG_FELD.search(koerper)
    if not b:
        return []
    kopf_ende = koerper.find("Betrag:")
    intro = re.search(r"worden:\s*", koerper)
    kopf = koerper[intro.end() if intro else 0:kopf_ende].strip()
    return [{
        "seq": 1, "heading": kopf[:200], "kind": art(kopf) if art(kopf) != "other" else "loan",
        "borrower": schuldner(kopf) or schuldner(koerper),
        "amount": de_zahl(b.group(1)),
        "rate_pct": (lambda z: de_zahl(z.group(1)) if z else None)(_ZINS.search(koerper)),
        "fixed_years": None,
        "fixed_until": (lambda z: iso(*z.groups()) if z else None)(_BINDUNG_BIS.search(koerper)),
        "decided_at": (lambda z: iso(*z.groups()) if z else None)(
            re.search(rf"Wertstellung:\s*{_DATUM}", koerper)),
        "summary": koerper[kopf_ende:kopf_ende + 400],
    }]


def _posten_feldliste(text: str) -> list[dict]:
    """Die Form von 2018 bis 2021: je Vorgang eine Überschrift („EGH –
    Kreditaufnahme für Investitionen aus dem Wirtschaftsplan 2018") und
    darunter eine Feldliste („Betrag:" oder „Abruf:", „Wertstellung:",
    „Zinssatz:", „Zinsbindung:" bzw. „Zinsfestsetzung:") — mehrere je Bericht,
    gruppiert unter Monatsüberschriften („Dezember 2019", „./." für einen
    Monat ohne Vorgang). :func:`_posten_formular` liest davon genau EINEN
    Vorgang (2022); hier zählt jeder Betrag."""
    i = text.find("Bericht:")
    j = text.find("Finanzielle Auswirkungen")
    koerper = text[i:j if j > i else None] if i >= 0 else text
    felder = list(_BETRAG_FELD.finditer(koerper))
    if not felder:
        return []
    aus: list[dict] = []
    for n, m in enumerate(felder):
        vor = koerper[felder[n - 1].end() if n else 0:m.start()]
        kopf_treffer = None
        for k in _FELD_KOPF.finditer(vor):
            kopf_treffer = k                       # der letzte vor dem Feld
        kopf = (kopf_treffer.group(1) if kopf_treffer else vor[-120:]).strip().rstrip(":").strip()
        art_teil = kopf_treffer.group(2) if kopf_treffer else kopf
        absatz = koerper[m.start():felder[n + 1].start() if n + 1 < len(felder) else None]
        aus.append({
            "seq": n + 1, "heading": kopf[:200],
            "kind": art(art_teil) if art(art_teil) != "other" else "loan",
            "borrower": schuldner(kopf),
            "amount": de_zahl(m.group(1)),
            "rate_pct": (lambda z: de_zahl(z.group(1)) if z else None)(_ZINS.search(absatz)),
            "fixed_years": None,
            "fixed_until": (lambda z: iso(*z.groups()) if z else None)(_BINDUNG_BIS.search(absatz)),
            "decided_at": (lambda z: iso(*z.groups()) if z else None)(
                re.search(rf"Wertstellung:\s*{_DATUM}", absatz)),
            "summary": absatz[:400],
        })
    return aus


def _einzelposten(text: str) -> list[dict]:
    """Ein Bericht mit genau einem Vorgang ohne Nummer (2022): „Umschuldung von
    Kommunalkrediten in Höhe von insgesamt 78.812.404,40 Euro Mit Entscheidung
    vom …" — die Überschrift steht als erster Satz nach dem Einleitungssatz."""
    i = text.find("Bericht:")
    j = text.find("Finanzielle Auswirkungen")
    koerper = text[i:j if j > i else None] if i >= 0 else text
    m = re.search(r"worden:\s*", koerper)
    rest = koerper[m.end():] if m else koerper
    b = _BETRAG.search(rest)
    if not b or b.start() > 220:
        return []
    kopf = re.sub(r"^[\W_]+", "", rest[:b.end()].strip())
    return [{
        "seq": 1, "heading": kopf[:200], "kind": art(kopf), "borrower": schuldner(kopf),
        "amount": de_zahl(b.group(1)),
        "rate_pct": (lambda z: de_zahl(z.group(1)) if z else None)(_ZINS.search(rest)),
        "fixed_years": (lambda z: int(z.group(1)) if z else None)(_BINDUNG_JAHRE.search(rest)),
        "fixed_until": (lambda z: iso(*z.groups()) if z else None)(_BINDUNG_BIS.search(rest)),
        "decided_at": (lambda z: iso(*z.groups()) if z else None)(
            _ENTSCHEIDUNG.search(rest) or _AM_ENTSCHIEDEN.search(rest)),
        "summary": rest[:400],
    }]


def _alte_form(text: str, title: str) -> list[dict]:
    """Bis 2021: ein Bericht je Umschuldung, der Betrag im Titel."""
    b = _BETRAG.search(title)
    if not b:
        return []
    return [{
        "seq": 1, "heading": title.split(" - ")[0].strip()[:200], "kind": art(title),
        "borrower": schuldner(title),
        "amount": de_zahl(b.group(1)), "rate_pct": None, "fixed_years": None,
        "fixed_until": None,
        "decided_at": (lambda z: iso(*z.groups()) if z else None)(_ENTSCHEIDUNG.search(text)),
        "summary": text[text.find("Bericht:"):][:400] if "Bericht:" in text else text[:400],
    }]


def ersparnis(text: str) -> dict | None:
    m = _FINANZ.search(text)
    if not m:
        return None
    e = _ERSPARNIS.search(m.group(1))
    if not e:
        return None
    t1, m1, j1, t2, m2, j2, betrag = e.groups()
    return {"interest_saving": de_zahl(betrag),
            "saving_from": iso(t1, m1, j1), "saving_to": iso(t2, m2, j2)}


def lies(zeilen: Iterable[dict]) -> dict:
    """Aus den Vorlagen die Unterrichtungen und ihre Posten.

    ``zeilen``: dicts mit ``template_number``, ``title``, ``raw_text``,
    ``document_id``, ``document_url`` (Store: ``kreditunterrichtungen``)."""
    notices: list[dict] = []
    items: list[dict] = []
    rejected: list[dict] = []
    for z in zeilen:
        nr, title = z["template_number"], z.get("title") or ""
        if not erkenne(title):
            continue
        text = glatt(z.get("raw_text"))
        if len(text) < 200:
            rejected.append({"template_number": nr, "reason": "kein Volltext"})
            continue
        d = _DOK_DATUM.search(text)
        dok_jahr = int(d.group(3) or d.group(6)) if d else None
        von, bis = zeitraum(text, dok_jahr)
        posten = _posten(text)
        if not posten and ("Betrag:" in text or "Abruf:" in text):
            posten = _posten_feldliste(text)
            if len(posten) == 1 and "Betrag:" in text:
                posten = _posten_formular(text)
        if not posten and _BETRAG.search(title):
            posten = _alte_form(text, title)
        if not posten and not _KEINE.search(text):
            posten = _einzelposten(text)
        sp = ersparnis(text) or {}
        d = _DOK_DATUM.search(text)
        dok_datum = None
        if d:
            g = [x for x in d.groups() if x]
            dok_datum = iso(*g[:3])
        if von is None and sp.get("saving_from"):
            von, bis = sp["saving_from"][:7], sp["saving_to"][:7]
        if von is None and dok_datum:
            # Einzelbericht ohne Zeitraum (2018): Der Monat des Dokuments ist
            # der Monat des Vorgangs — die Unterrichtung folgt der Entscheidung
            # binnen Wochen.
            von = bis = dok_datum[:7]
        if von is None:
            rejected.append({"template_number": nr, "reason": "kein Berichtszeitraum erkannt"})
            continue
        proben = [ZEITRAUM]
        geld = [p for p in posten if p["kind"] in ("loan", "refinancing", "prolongation")]
        if geld and all(p["amount"] is not None for p in geld):
            proben.append(POSTEN_BETRAG)
        notices.append({
            "template_number": nr, "year": int(von[:4]),
            "period_from": von, "period_to": bis,
            "document_date": dok_datum,
            "none_reported": bool(_KEINE.search(text)) and not posten,
            "items": len(posten),
            **sp,
            "document_id": z.get("document_id"), "document_url": z.get("document_url"),
            "probes": proben,
        })
        for p in posten:
            items.append({"template_number": nr, "year": int(von[:4]), **p})
    notices.sort(key=lambda n: (n["period_from"], n["template_number"]))
    return {"notices": notices, "items": items, "rejected": rejected,
            "probes": {"vorlagen": len(notices) + len(rejected), "posten": len(items)}}


def probennachweis(result: dict) -> str:
    n = result["notices"]
    mit = sum(1 for x in n if POSTEN_BETRAG in x["probes"])
    return (f"{len(n)} Unterrichtungen mit Berichtszeitraum, {result['probes']['posten']} Posten; "
            f"bei {mit} von {len(n)} tragen alle Kredit-, Umschuldungs- und "
            f"Prolongationsposten ihren Betrag in der Überschrift.")
