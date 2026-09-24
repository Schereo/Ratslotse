"""Das Amtsblatt der Stadt Oldenburg — die beschlossene Haushaltssatzung.

Im Ratsinformationssystem steht die Haushaltssatzung nur als
Verwaltungsentwurf (``council/budget_bylaw.py``). Was der Rat beschlossen hat,
wird im **Amtsblatt** öffentlich bekannt gemacht, und erst damit tritt die
Satzung in Kraft. Diese Schicht liest diese Fassung und stellt sie neben den
Entwurf — mit dem Beschlussdatum, dem Tag der Bekanntmachung und, wo das
Amtsblatt sie nennt, der Genehmigung der Kommunalaufsicht.

WAS DIE QUELLE HERGIBT (gemessen 24.09.2026)
--------------------------------------------

* Die Übersichtsseite auf oldenburg.de verlinkt die Ausgaben ab 2020, rund
  20 je Jahr. 2019 ist dort nicht verlinkt — und Adressen werden nicht
  geraten (Tims Regel), also fehlt 2019.
* Bis 2025 sind die Ausgaben **eingescannt**, ohne Textebene; ab 2026 tragen
  sie Text. Gescannte Seiten liest das Sehmodell (``council/ocr.py``, 0,002 $
  je Seite gemessen). Welche Ausgabe die Satzung trägt, verrät Seite 1 (dort
  beginnt sie jedes Jahr), deshalb wird zuerst nur Seite 1 gelesen.
* Eine Genehmigung druckt das Amtsblatt 2020–2026 bei keiner Satzung ab: Alle
  sieben setzen in § 2 keine Kredite fest, und genehmigungspflichtig wären
  vor allem die. Steht kein Vermerk da, bleibt das Feld leer — erfunden wird
  nichts.

DIE PROBE ist die des Entwurfs-Lesers: Die sechs Finanzhaushalts-Zeilen
ergeben die beiden „Nachrichtlich"-Summen der Satzung, auf den Cent. Dazu
wird jede Zahl mit dem Entwurf verglichen; eine Abweichung ist kein Fehler,
sondern das, was der Rat geändert hat, und wird so ausgewiesen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from council.budget_bylaw import Haushaltssatzung, SatzungFehler, parse_satzung

UEBERSICHT_URL = ("https://www.oldenburg.de/startseite/rathaus/informiert-bleiben/"
                  "bekanntmachungen/amtsblatt.html")
PROBE_VEROEFFENTLICHT = "bylaw_published"

_LINK = re.compile(r'href="([^"]*Amtsblatt[^"]*?/(?:(\d{1,2}a?)-(20\d\d)|(20\d\d)-(\d{1,2}a?))\.pdf)"')
_MONATE = {m: i for i, m in enumerate(
    ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
     "September", "Oktober", "November", "Dezember"], 1)}
_DATUM_KOPF = re.compile(
    r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Oldenburg),?\s+den\s+"
    r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s+(20\d\d)")
_SITZUNG = re.compile(r"in der Sitzung am\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)")
_BEGINN = re.compile(r"Haushaltssatzung\s+der\s+Stadt\s+Oldenburg", re.I)
_ENDE = re.compile(r"Der\s+Oberb[üu]rgermeister", re.I)
#: Satzgrenze: ein Punkt, dem ein Großbuchstabe folgt und keine Ziffer oder
#: Abkürzung vorausgeht („§ 120 Abs. 2", „am 1. März" trennen nicht) — oder
#: eine Leerzeile (Ort und Datum über der Unterschrift enden ohne Punkt).
_SATZENDE = re.compile(r"(?<![\d])(?<!Abs)(?<!Nr)(?<!Art)(?<!bzw)\.\s+(?=[A-ZÄÖÜ])|\n\s*\n")
_HAT_SATZUNG = re.compile(r"Haushaltssatzung\s+der\s+Stadt\s+Oldenburg|folgende\s+Haushaltssatzung", re.I)


@dataclass(frozen=True)
class Ausgabe:
    url: str
    year: int
    nr: str


def ausgaben(html: str, basis: str = "https://www.oldenburg.de") -> list[Ausgabe]:
    """Die verlinkten Ausgaben der Übersichtsseite (Schreibweisen „4-2020.pdf"
    und „2026-8.pdf")."""
    aus: dict[str, Ausgabe] = {}
    for m in _LINK.finditer(html or ""):
        pfad = m.group(1)
        nr, jahr = (m.group(2), m.group(3)) if m.group(2) else (m.group(5), m.group(4))
        url = pfad if pfad.startswith("http") else basis + pfad
        aus[url] = Ausgabe(url=url, year=int(jahr), nr=nr)
    return sorted(aus.values(), key=lambda a: (a.year, int(re.sub(r"\D", "", a.nr) or 0), a.nr))


def hat_satzung(text: str) -> bool:
    """Trägt diese Seite eine Haushaltssatzung (keine Nachtragssatzung)?"""
    return bool(_HAT_SATZUNG.search(text or "")) and "Nachtragshaushaltssatzung" not in (text or "")


def _iso(tag: str, monat: str, jahr: str) -> str | None:
    m = _MONATE.get(monat) if not monat.isdigit() else int(monat)
    return f"{int(jahr):04d}-{m:02d}-{int(tag):02d}" if m else None


@dataclass
class Veroeffentlichung:
    satzung: Haushaltssatzung
    session_date: str | None      # ISO, Tag des Ratsbeschlusses
    published_on: str | None      # ISO, Datum der Amtsblatt-Ausgabe
    approval_note: str | None     # Wortlaut, wo das Amtsblatt eine Genehmigung nennt


def lies(text: str) -> Veroeffentlichung:
    """Die Satzung aus dem Text einer Ausgabe; wirft ``SatzungFehler``."""
    t = text or ""
    # Die Überschrift steht auch im Inhaltsverzeichnis der Ausgabe, und dort
    # folgt „Aufgrund des § 112 …" oft keine 900 Zeichen später (2021). Die
    # Satzung beginnt deshalb an der LETZTEN Überschrift vor diesem Satz.
    kandidaten = [m for m in _BEGINN.finditer(t)
                  if re.search(r"Aufgrund", t[m.end():m.end() + 900])]
    beginn = None
    if kandidaten:
        auf = re.search(r"Aufgrund", t[kandidaten[0].end():])
        grenze = kandidaten[0].end() + (auf.start() if auf else 0)
        beginn = [m for m in kandidaten if m.start() < grenze][-1]
    if not beginn:
        raise SatzungFehler("keine Haushaltssatzung in dieser Ausgabe")
    ende = None
    for m in _ENDE.finditer(t, beginn.end()):
        ende = m
        # Die Bekanntmachung („Die vorstehende Haushaltssatzung … wird hiermit
        # öffentlich bekannt gemacht") folgt der Unterschrift und endet selbst
        # mit „Der Oberbürgermeister" — bis dahin gehört der Abschnitt dazu.
        if "bekannt" in t[beginn.end():m.start()].lower():
            break
    abschnitt = t[beginn.start():ende.end() if ende else len(t)]
    # Der Satz des Amtsblatts trennt Wörter am Zeilenende („Verpflichtungs-
    # ermächtigun-/gen"); die Muster des Entwurfs-Lesers kennen nur ganze Wörter.
    abschnitt = re.sub(r"(\w)-[ \t]*\n\s*(?=[a-zäöüß])", r"\1", abschnitt)
    satzung = parse_satzung(abschnitt)
    s = _SITZUNG.search(" ".join(abschnitt.split()))
    k = _DATUM_KOPF.search(" ".join(t[:1500].split()))
    # Nur Sätze über DIESE Satzung: Im selben Abschnitt kann eine fremde
    # Bekanntmachung stehen („… über die Genehmigung der Änderung Nummer 78"
    # des Flächennutzungsplans, 2021).
    saetze = [" ".join(z.split()) for z in _SATZENDE.split(abschnitt)]
    gen = [z if z.endswith(".") else z + "." for z in saetze
           if re.search(r"genehmig", z, re.I)
           and re.search(r"Haushalt|Kommunalaufsicht|Innern|Inneres|Innenminist|NKomVG", z, re.I)
           and not re.search(r"Flächennutzungsplan|Bebauungsplan", z, re.I)]
    return Veroeffentlichung(
        satzung=satzung,
        session_date=_iso(*s.groups()) if s else None,
        published_on=_iso(*k.groups()) if k else None,
        approval_note=" ".join(gen) or None,
    )


#: Die Felder, die Entwurf und beschlossene Fassung gemeinsam haben.
FELDER = ("ordinary_revenues", "ordinary_expenses", "extraordinary_revenues",
          "extraordinary_expenses", "in_operating", "out_operating", "in_capital",
          "out_capital", "in_financing", "out_financing", "in_total", "out_total",
          "investment_loans", "commitment_authorizations", "liquidity_loans",
          "property_tax_a_rate", "property_tax_b_rate", "trade_tax_rate")


def abweichungen(entwurf: dict | None, beschlossen: Haushaltssatzung) -> list[str]:
    """Welche Zahlen der Rat gegenüber dem Entwurf geändert hat — Feldnamen."""
    if not entwurf:
        return []
    aus = []
    for f in FELDER:
        a, b = entwurf.get(f), getattr(beschlossen, f)
        if a is None or b is None:
            continue
        if abs(float(a) - float(b)) > 0.5:
            aus.append(f)
    return aus
