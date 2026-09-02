"""Die Jahresabschlüsse der Eigenbetriebe — das Ist neben dem Wirtschaftsplan.

Der Rat beschließt je Eigenbetrieb einen Wirtschaftsplan (``council/
wirtschaftsplan.py``) — und ein gutes halbes Jahr nach Jahresende stellt er
den **Jahresabschluss** fest: Bilanz, Gewinn- und Verlustrechnung, Lagebericht,
geprüft vom Rechnungsprüfungsamt (EGH, Hafen) oder von einem
Wirtschaftsprüfer (AWB). Bis 09/2026 kannte der Bereich nur den Plan; was
aus ihm wurde, stand nirgends — und der Eigenbetrieb Gebäudewirtschaft und
Hochbau ist der Betrieb, in dem die Schulen stecken.

DREI BAUFORMEN, EIN BESTAND
---------------------------

* **Mehrjahresübersicht** (RPA-Schlussberichte EGH 2017–2025 und Hafen
  2017–2020; Wirtschaftsprüfer-Bericht AWB 2019, 2022–2025): eine Kopfzeile
  mit drei bis fünf Jahren, jüngstes zuerst, darunter je Kennzahl eine Zeile
  in **TEUR** — Bilanzsumme, Anlage- und Umlaufvermögen, Eigenkapital,
  Verbindlichkeiten, Umsatzerlöse, Rohertrag, Abschreibungen, Jahresergebnis,
  Cashflow, Investitionen, beim AWB auch die Zahl der Arbeitnehmer. Fußnoten-
  ziffern stehen VOR den Werten („Rohertrag 2 31.345 …"), Beschriftungen
  brechen um („Cashflow aus lfd. / Geschäftstätigkeit / 3 / 27.593 …").
* **GuV in Euro** (Bäderbetrieb, als eigene einseitige Anlage; 2017/2018 im
  Gesamtdokument): „1. Umsatzerlöse 2.145.244,92 2.137.598,40", am Ende
  „16. Jahresüberschuss/-fehlbetrag 0,00 0,00" — zwei Spalten, Geschäftsjahr
  und Vorjahr. Bis 2018 steht das Vorjahr in TEUR ohne Nachkommastellen.
* **Bilanz in Euro** (Bäderbetrieb): Bilanzsumme ist die Zeile mit dem
  größten Betrag (die Summe der Aktiva), das Eigenkapital die Zwischensumme
  vor den Rückstellungen.

DIE PROBE IST DIE ÜBERLAPPUNG
-----------------------------

Dieselbe Zahl steht in bis zu fünf Berichten: als Geschäftsjahr im eigenen,
als Vorjahr in den folgenden. Wo zwei Berichte dasselbe Jahr nennen, müssen
sie dieselbe Zahl nennen — auf Tausend gerundet, weil die Übersicht in TEUR
schreibt und die GuV in Euro. Gilt der jüngste Bericht als Quelle, zählt
``confirmations``, wie viele Berichte ihn bestätigen; widerspricht einer,
bleibt der jüngste und ``conflicts`` sagt es. Nichts wird verworfen, aber
nichts steht ohne Zeugen da.

Was NICHT geht: Der AWB-Bericht 2025 (Anlage 310439) verliert im Textextrakt
alle Leerzeichen („BilanzsummeT€24.50625.50026.499…"); die Zahlen kleben, und
kein Zeilenmodell trennt sie. Der Jahrgang 2025 des AWB kommt erst mit dem
Vorjahres-Vergleich des Berichts 2026 — oder mit einer OCR-Lesung.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from council.herkunft import Herkunft
from council.wirtschaftsplan import BETRIEBE, betrieb_aus_titel

PROBE_SPALTEN = "enterprise_accounts_columns"
PROBE_UEBERLAPPUNG = "enterprise_accounts_overlap"

#: Die Vorlagen — dieselbe Auswahl für Ingest, Dokumentmarke und Erkennung.
TITEL_MUSTER: tuple[str, ...] = (
    "%Jahresabschluss%Gebäudewirtschaft%",
    "%Jahresabschluss%Abfallwirtschaftsbetrieb%",
    "%Bäderbetrieb der Stadt%Jahresabschluss%",
    "%Jahresabschluss%Eigenbetrieb Hafen%",
    "%Eigenbetrieb Hafen%Jahresabschluss%",
)
TITEL_SQL = "(" + " OR ".join("title LIKE ?" for _ in TITEL_MUSTER) + ")"

FUNDSTELLE_UEBERSICHT = ("Mehrjahresübersicht des Prüfberichts (Kennzahlen in TEUR, "
                         "jüngstes Jahr zuerst)")
FUNDSTELLE_GUV = "Gewinn- und Verlustrechnung (Geschäftsjahr und Vorjahr, in Euro)"
FUNDSTELLE_BILANZ = "Bilanz (Summe der Aktiva und Eigenkapital, in Euro)"

#: Was diese Zahlen sind — reist mit den Daten (dieselbe Regel wie bei den
#: Wirtschaftsplänen): Ein Eigenbetrieb rechnet handelsrechtlich; sein
#: Jahresergebnis ist kein Haushaltsergebnis und mit dem Kernhaushalt nicht
#: addierbar.
ABGRENZUNG = (
    "Geprüfter Jahresabschluss des Eigenbetriebs nach Handelsrecht — eigenes "
    "Rechenwerk neben dem Kernhaushalt, mit ihm nicht addierbar. Das "
    "Jahresergebnis ist der Jahresüberschuss oder -fehlbetrag der Gewinn- und "
    "Verlustrechnung, nicht das Ergebnis eines Haushalts."
)

#: Kennzahl → Muster am Zeilenanfang der Mehrjahresübersicht. Reihenfolge
#: entscheidet: „Eigenkapitalquote" darf nicht als „Eigenkapital" gelten, und
#: „Jahresüberschuss / Jahresfehlbetrag" ist EINE Zeile.
METRIKEN: tuple[tuple[str, str], ...] = (
    ("balance_total", r"Bilanzsumme"),
    ("fixed_assets", r"Anlagevermögen"),
    ("current_assets", r"Umlaufvermögen"),
    ("equity", r"Eigenkapital(?!quote|rendite)"),
    ("liabilities", r"Verbindlichkeiten"),
    ("revenues", r"Umsatzerlöse"),
    ("gross_profit", r"Rohertrag"),
    ("depreciation", r"Abschreibungen"),
    ("operating_result", r"Betriebsergebnis"),
    ("financial_result", r"Finanzergebnis"),
    ("result", r"Jahresergebnis|Jahresüberschuss\s*/\s*Jahresfehlbetrag|"
               r"Jahresüberschuss/-fehlbetrag|Jahresüberschuss|Jahresfehlbetrag"),
    ("cashflow", r"Cash\s?flow"),
    ("investments", r"Investitionen"),
    ("employees", r"durchschnittl\.?\s*Arbeitnehmer"),
)
METRIK_NAMEN: dict[str, str] = {
    "balance_total": "Bilanzsumme", "fixed_assets": "Anlagevermögen",
    "current_assets": "Umlaufvermögen", "equity": "Eigenkapital",
    "liabilities": "Verbindlichkeiten", "revenues": "Umsatzerlöse",
    "gross_profit": "Rohertrag", "depreciation": "Abschreibungen",
    "operating_result": "Betriebsergebnis", "financial_result": "Finanzergebnis",
    "result": "Jahresergebnis", "cashflow": "Cashflow aus laufender Geschäftstätigkeit",
    "investments": "Investitionen", "employees": "Beschäftigte (Durchschnitt)",
}
#: Kennzahlen in Stück statt Euro.
_STUECK = {"employees"}

_JAHRESKOPF = re.compile(r"^\s*((?:20\d\d\s+){2,4}20\d\d)\s*$", re.M)
_ZAHL = re.compile(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?")
_PROZENT = re.compile(r"%")
_EUR_PAAR = re.compile(r"(-?\d{1,3}(?:\.\d{3})*,\d{2})\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*$", re.M)
_GESCHAEFTSJAHR = re.compile(r"(?:Gesch[äa]ftsjahr|Wirtschaftsjahr)\s+(20\d\d)", re.I)
_JAHR_TITEL = re.compile(r"\b(20\d\d)\b")


class AbschlussFehler(RuntimeError):
    """Ein Dokument, dessen Tabelle nicht aufgeht."""


@dataclass(frozen=True)
class Kennzahl:
    """Eine Zahl eines Betriebs für ein Jahr, aus einem Dokument."""
    enterprise: str
    year: int
    metric: str
    value: float          # Euro (bzw. Stück bei ``employees``)
    unit: str             # "TEUR" | "EUR" | "Stück"
    report_year: int
    document_id: int | None
    fundstelle: str
    probe: str


@dataclass
class Lesung:
    kennzahlen: list[Kennzahl] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    form: str | None = None


# --------------------------------------------------------------------------
# Zahlen
# --------------------------------------------------------------------------

def _wert(token: str) -> float:
    token = token.replace(".", "").replace(",", ".")
    return float(token)


def _ist_euro(token: str) -> bool:
    """Ein Betrag mit zwei Nachkommastellen ist Euro; ohne ist er TEUR."""
    return bool(re.search(r",\d{2}$", token))


# --------------------------------------------------------------------------
# Bauform 1: die Mehrjahresübersicht (TEUR)
# --------------------------------------------------------------------------

_JAHR_ALLEIN = re.compile(r"^\s*(20\d\d)\s*$")
_EINHEIT_ALLEIN = re.compile(r"^\s*(?:TEUR|T€|Tausend|Euro|EUR)\s*$", re.I)


def _jahreskopf(glatt: str, report_year: int) -> tuple[int, list[int]] | None:
    """Wo die Übersicht beginnt und welche Jahre sie trägt.

    Zwei Schreibweisen: alle Jahre in EINER Zeile („2024 2023 2022 2021 2020",
    EGH ab 2018, AWB) — oder Jahr und Einheit abwechselnd auf eigenen Zeilen
    („2017 / TEUR / 2016 / TEUR / 2015 / TEUR", EGH 2017). Gilt nur ein Kopf,
    dessen erstes Jahr das Berichtsjahr ist und der absteigend zählt."""
    for m in _JAHRESKOPF.finditer(glatt):
        jahre = [int(j) for j in m.group(1).split()]
        if jahre == sorted(jahre, reverse=True) and jahre[0] == report_year:
            return m.end(), jahre
    zeilen = glatt.split("\n")
    for i, zeile in enumerate(zeilen):
        if not (_JAHR_ALLEIN.match(zeile) and int(zeile) == report_year):
            continue
        jahre = [int(zeile)]
        pos = i + 1
        while pos < len(zeilen) and pos < i + 12:
            if _EINHEIT_ALLEIN.match(zeilen[pos]):
                pos += 1
                continue
            if _JAHR_ALLEIN.match(zeilen[pos]) and int(zeilen[pos]) == jahre[-1] - 1:
                jahre.append(int(zeilen[pos]))
                pos += 1
                continue
            break
        if len(jahre) >= 3:
            ende = sum(len(z) + 1 for z in zeilen[:pos])
            return ende, jahre
    return None


def lies_mehrjahresuebersicht(text: str, enterprise: str, report_year: int,
                              document_id: int | None) -> Lesung:
    """Die Kennzahlen-Tabelle mit Jahreskopf — jede Zeile eine Kennzahl."""
    aus = Lesung(form="uebersicht")
    glatt = re.sub(r"[ \t]+", " ", text or "")
    kopf = _jahreskopf(glatt, report_year)
    if kopf is None:
        aus.hinweise.append("keine Mehrjahresübersicht mit dem Jahreskopf des Berichtsjahres")
        return aus
    ende, jahre = kopf
    n = len(jahre)
    zeilen = glatt[ende:].split("\n")[:60]
    gesehen: set[str] = set()
    for i, zeile in enumerate(zeilen):
        kern = zeile.strip()
        if not kern:
            continue
        # Ein zweiter Jahreskopf beendet die Tabelle (die nächste Übersicht) —
        # und die erste Prozentzeile ebenfalls: Eigenkapitalquote und Renditen
        # stehen in jeder Bauform ganz unten. Was danach kommt, ist eine
        # andere Tabelle; der AWB-Bericht führt dort „Verbindlichkeiten" mit
        # ganz anderen Spalten, und die landeten sonst als Kennzahl.
        if _JAHRESKOPF.match(kern + "\n") and i > 0:
            break
        if _PROZENT.search(kern) and i > 0:
            break
        for metric, muster in METRIKEN:
            # Das Label muss frei stehen: „BilanzsummeT€24.506…" (AWB 2025,
            # Textextrakt ohne Leerzeichen) ist keine lesbare Zeile.
            if metric in gesehen or not re.match(muster + r"(?=\s|$)", kern, re.I):
                continue
            # Werte dieser Zeile und der folgenden, bis n Zahlen beisammen
            # sind — Fußnotenziffern stehen davor, also zählen die LETZTEN n.
            tokens: list[str] = []
            for folge in zeilen[i:i + 4]:
                if _PROZENT.search(folge):
                    break
                tokens.extend(_ZAHL.findall(re.sub(r"T€|TEUR", "", folge)))
                if len(tokens) >= n:
                    break
            if len(tokens) < n:
                aus.hinweise.append(f"{METRIK_NAMEN[metric]}: {len(tokens)} statt {n} Werte")
                gesehen.add(metric)
                break
            werte = tokens[-n:]
            for jahr, tok in zip(jahre, werte):
                if metric in _STUECK:
                    aus.kennzahlen.append(Kennzahl(enterprise, jahr, metric, _wert(tok), "Stück",
                                                   report_year, document_id,
                                                   FUNDSTELLE_UEBERSICHT, PROBE_SPALTEN))
                else:
                    aus.kennzahlen.append(Kennzahl(enterprise, jahr, metric, _wert(tok) * 1000.0,
                                                   "TEUR", report_year, document_id,
                                                   FUNDSTELLE_UEBERSICHT, PROBE_SPALTEN))
            gesehen.add(metric)
            break
    if not aus.kennzahlen:
        aus.hinweise.append("Mehrjahresübersicht ohne lesbare Kennzahl-Zeile")
    return aus


# --------------------------------------------------------------------------
# Bauform 2 und 3: GuV und Bilanz in Euro (Bäderbetrieb)
# --------------------------------------------------------------------------

def _paar(zeile: str) -> tuple[float, float, str] | None:
    """„X Y" am Zeilenende: Geschäftsjahr in Euro, Vorjahr in Euro oder TEUR."""
    m = _EUR_PAAR.search(zeile)
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    vor = _wert(b) if _ist_euro(b) else _wert(b) * 1000.0
    return _wert(a), vor, ("EUR" if _ist_euro(b) else "TEUR")


def _geschaeftsjahr(text: str, fallback: int) -> int:
    m = _GESCHAEFTSJAHR.search(text or "")
    return int(m.group(1)) if m else fallback


def lies_guv(text: str, enterprise: str, report_year: int,
             document_id: int | None) -> Lesung:
    """Umsatzerlöse und Jahresergebnis aus der GuV — Geschäftsjahr und Vorjahr."""
    aus = Lesung(form="guv")
    glatt = re.sub(r"[ \t]+", " ", text or "")
    jahr = _geschaeftsjahr(glatt, report_year)
    for metric, muster in (("revenues", r"^\s*\d{1,2}\.\s*Umsatzerlöse\b"),
                           ("result", r"^\s*\d{1,2}\.\s*Jahres(?:überschuss|fehlbetrag)")):
        for zeile in glatt.split("\n"):
            if not re.match(muster, zeile):
                continue
            paar = _paar(zeile)
            if paar is None:
                continue
            akt, vor, vor_einheit = paar
            aus.kennzahlen.append(Kennzahl(enterprise, jahr, metric, akt, "EUR", report_year,
                                           document_id, FUNDSTELLE_GUV, PROBE_UEBERLAPPUNG))
            aus.kennzahlen.append(Kennzahl(enterprise, jahr - 1, metric, vor, vor_einheit,
                                           report_year, document_id, FUNDSTELLE_GUV,
                                           PROBE_UEBERLAPPUNG))
            break
    if not aus.kennzahlen:
        aus.hinweise.append("keine GuV-Zeile (Umsatzerlöse, Jahresüberschuss) mit zwei Beträgen")
    return aus


def lies_bilanz(text: str, enterprise: str, report_year: int,
                document_id: int | None) -> Lesung:
    """Bilanzsumme (die größte Zeile) und Eigenkapital (vor den Rückstellungen)."""
    aus = Lesung(form="bilanz")
    glatt = re.sub(r"[ \t]+", " ", text or "")
    m = re.search(r"Bilanz zum 31\. Dezember (20\d\d)|BILANZ ZUM 31\. DEZEMBER (20\d\d)", glatt, re.I)
    jahr = int(m.group(1) or m.group(2)) if m else report_year
    paare = [(z, _paar(z)) for z in glatt.split("\n")]
    paare = [(z, p) for z, p in paare if p is not None]
    if not paare:
        aus.hinweise.append("keine Bilanzzeile mit zwei Beträgen")
        return aus
    _z, (akt, vor, vor_einheit) = max(paare, key=lambda zp: zp[1][0])
    for jahr_, wert, einheit in ((jahr, akt, "EUR"), (jahr - 1, vor, vor_einheit)):
        aus.kennzahlen.append(Kennzahl(enterprise, jahr_, "balance_total", wert, einheit,
                                       report_year, document_id, FUNDSTELLE_BILANZ,
                                       PROBE_UEBERLAPPUNG))
    # Eigenkapital: die letzte Paarzeile im Abschnitt „Eigenkapital" vor den
    # Rückstellungen — die Zwischensumme aus Stammkapital und Rücklagen.
    ek = re.search(r"Eigenkapital(.*?)R[üu]ckstellungen", glatt, re.S | re.I)
    if ek:
        block = [(z, _paar(z)) for z in ek.group(1).split("\n")]
        block = [p for _z, p in block if p is not None]
        if block:
            akt, vor, vor_einheit = block[-1]
            for jahr_, wert, einheit in ((jahr, akt, "EUR"), (jahr - 1, vor, vor_einheit)):
                aus.kennzahlen.append(Kennzahl(enterprise, jahr_, "equity", wert, einheit,
                                               report_year, document_id, FUNDSTELLE_BILANZ,
                                               PROBE_UEBERLAPPUNG))
    return aus


# --------------------------------------------------------------------------
# Ein Dokument: welche Bauform, welche Zahlen
# --------------------------------------------------------------------------

def betriebsjahr(title: str) -> tuple[str, int] | None:
    """Kürzel und Berichtsjahr aus dem Vorlagentitel — oder ``None``."""
    betrieb = betrieb_aus_titel(title or "")
    jahr = _JAHR_TITEL.search(title or "")
    if not betrieb or not jahr:
        return None
    return betrieb[0], int(jahr.group(1))


#: Ab dieser Seitenzahl ist ein Dokument ein Prüfbericht, und GuV und Bilanz
#: darin sind Anhänge unter vielen Tabellen — der Griff nach „der größten
#: Zeile" träfe dort die falsche. Die eigenen GuV- und Bilanz-Anlagen des
#: Bäderbetriebs haben ein bis zwei Seiten, sein Gesamtdokument zwanzig.
_KURZES_DOKUMENT = 25
_GUV_BILANZ_LABEL = re.compile(r"GuV|Gewinn|Bilanz", re.I)


def lies_dokument(text: str, title: str, label: str,
                  document_id: int | None, n_pages: int | None = None) -> Lesung:
    """Die passende Bauform für dieses Dokument — Übersicht, GuV oder Bilanz.

    Die Übersicht hat Vorrang. GuV und Bilanz werden nur in Dokumenten
    gelesen, die eine SIND (Label) oder kurz genug dafür (Seitenzahl): Im
    RPA-Bericht 2022 des EGH fehlt die Übersicht, und der Griff nach der
    größten Zahlenzeile machte dort den Jahresüberschuss zum Eigenkapital."""
    bj = betriebsjahr(title)
    if bj is None:
        aus = Lesung(); aus.hinweise.append("Betrieb oder Jahr nicht im Vorlagentitel")
        return aus
    enterprise, report_year = bj
    text = text or ""
    lesung = lies_mehrjahresuebersicht(text, enterprise, report_year, document_id)
    if lesung.kennzahlen:
        return lesung
    hinweise = list(lesung.hinweise)
    if not (_GUV_BILANZ_LABEL.search(label or "")
            or (n_pages is not None and n_pages <= _KURZES_DOKUMENT)):
        hinweise.append("kein GuV-/Bilanz-Dokument (Label, Seitenzahl) — kein Notweg")
        aus = Lesung(); aus.hinweise = hinweise
        return aus
    aus = Lesung(form="guv+bilanz")
    if re.search(r"Gewinn-?\s*und\s*Verlustrechnung|GuV", text + " " + (label or ""), re.I):
        g = lies_guv(text, enterprise, report_year, document_id)
        aus.kennzahlen.extend(g.kennzahlen); hinweise.extend(g.hinweise)
    if re.search(r"\bBilanz\b", text + " " + (label or ""), re.I):
        b = lies_bilanz(text, enterprise, report_year, document_id)
        aus.kennzahlen.extend(b.kennzahlen); hinweise.extend(b.hinweise)
    aus.hinweise = hinweise
    return aus


# --------------------------------------------------------------------------
# Der Notweg für verklebten Text: die Wortrahmen des PDFs
# --------------------------------------------------------------------------
#
# Der AWB-Prüfbericht 2025 (Anlage 310439) liefert im Textextrakt keine
# Leerzeichen zwischen den Zellen: „BilanzsummeT€24.50625.500…“. Für den
# Extrakt sind das Zeichen ohne Abstand; für das PDF sind es getrennte Wörter
# mit eigenen Rahmen. Aus den Rahmen lässt sich die Zeile wiederherstellen —
# Wörter derselben Grundlinie, nach x sortiert, mit Leerzeichen dazwischen.
# Der Weg wird nur beschritten, wenn der Extrakt die Übersicht zwar findet,
# aber keine Zeile daraus lesen kann; und ``pymupdf`` bleibt bewusst keine
# Abhängigkeit des Projekts (s. ``council/budget_execution.py``).

#: Verklebte Zellen: ein Kleinbuchstabe direkt vor „T€“ und einer Ziffer
#: („BilanzsummeT€24.506“) oder zwei Tausenderzahlen ohne Abstand
#: („24.50625.500“). Der Jahreskopf verklebt dabei gleich mit
#: („20252024202320222021“), deshalb kann nicht die Lesung entscheiden,
#: sondern nur der Text.
_VERKLEBT = re.compile(r"[a-zäöüß]T€\d|\d\.\d{3}\d{2}\.\d{3}")


def braucht_wortrahmen(lesung: Lesung, text: str) -> bool:
    """Nichts gelesen, und der Text zeigt verklebte Zellen — der Fall für die Rahmen."""
    return not lesung.kennzahlen and _VERKLEBT.search(text or "") is not None


def text_aus_wortrahmen(pdf_bytes: bytes) -> str:
    """Den Text aus den Wortrahmen des PDFs zeilenweise neu setzen.

    Zeile ist, was dieselbe Grundlinie teilt (2,5 pt Spiel, wie im
    Vollzugsbericht-Leser); die Wörter darin stehen nach ihrer linken Kante.
    """
    try:
        import pymupdf  # noqa: PLC0415 — bewusst optional, s. o.
    except ImportError as e:  # pragma: no cover — auf Maschinen mit Paket unerreichbar
        raise AbschlussFehler(
            "pymupdf fehlt — die Wortrahmen brauchen das Paket. "
            "Einmalig installieren: .venv/bin/pip install pymupdf") from e
    seiten: list[str] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            woerter = sorted((round(w[3], 1), w[0], w[4]) for w in page.get_text("words"))
            zeilen: list[tuple[float, list[tuple[float, str]]]] = []
            for y, x, t in woerter:
                if zeilen and abs(y - zeilen[-1][0]) <= 2.5:
                    zeilen[-1][1].append((x, t))
                else:
                    zeilen.append((y, [(x, t)]))
            seiten.append("\n".join(" ".join(t for _x, t in sorted(z)) for _y, z in zeilen))
    return "\n".join(seiten)


# --------------------------------------------------------------------------
# Der Bestand: jüngster Bericht gewinnt, die anderen bezeugen
# --------------------------------------------------------------------------

def _toleranz(*einheiten: str) -> float:
    return 500.0 if "TEUR" in einheiten else 1.0


def zusammenfuehren(kennzahlen: list[Kennzahl]) -> tuple[list[dict], list[str]]:
    """Je (Betrieb, Jahr, Kennzahl) EINE Zeile: die aus dem jüngsten Bericht,
    mit ``confirmations`` (Berichte, die dieselbe Zahl nennen) und
    ``conflicts`` (Berichte, die eine andere nennen)."""
    gruppen: dict[tuple[str, int, str], list[Kennzahl]] = {}
    for k in kennzahlen:
        gruppen.setdefault((k.enterprise, k.year, k.metric), []).append(k)
    zeilen: list[dict] = []
    strittig: list[str] = []
    for (enterprise, year, metric), gruppe in sorted(gruppen.items()):
        gruppe.sort(key=lambda k: (k.report_year, k.document_id or 0), reverse=True)
        fuehrend = gruppe[0]
        bestaetigt = 1
        widerspruch: list[Kennzahl] = []
        # Je Bericht zählt eine Stimme — dieselbe Zahl kann im selben Bericht
        # zweimal stehen (Übersicht UND GuV).
        gesehen = {fuehrend.report_year}
        for k in gruppe[1:]:
            if k.report_year in gesehen:
                continue
            gesehen.add(k.report_year)
            if abs(k.value - fuehrend.value) <= _toleranz(k.unit, fuehrend.unit):
                bestaetigt += 1
            else:
                widerspruch.append(k)
        if widerspruch:
            strittig.append(
                f"{BETRIEBE[enterprise][1] if enterprise in BETRIEBE else enterprise} {year} "
                f"{METRIK_NAMEN.get(metric, metric)}: Bericht {fuehrend.report_year} sagt "
                f"{fuehrend.value:,.0f}, " + ", ".join(
                    f"Bericht {k.report_year} {k.value:,.0f}" for k in widerspruch))
        zeilen.append({
            "enterprise": enterprise, "year": year, "metric": metric,
            "value": fuehrend.value, "unit": fuehrend.unit,
            "report_year": fuehrend.report_year, "document_id": fuehrend.document_id,
            "confirmations": bestaetigt, "conflicts": len(widerspruch),
            "fundstelle": fuehrend.fundstelle,
            "probes": sorted({fuehrend.probe, PROBE_UEBERLAPPUNG} if bestaetigt > 1
                             else {fuehrend.probe}),
        })
    return zeilen, strittig


def herkunft_fuer(zeile: dict, *, url: str | None, label: str | None) -> Herkunft:
    name = BETRIEBE.get(zeile["enterprise"], ("", zeile["enterprise"]))[1]
    return Herkunft(
        kind="ris", probe=list(zeile["probes"]),
        document_id=zeile.get("document_id"), url=url,
        label=label or f"Jahresabschluss {zeile['report_year']} {name}",
        citation=zeile["fundstelle"],
        as_of=f"Jahresabschluss {zeile['report_year']}",
        probe_result=(f"{zeile['confirmations']} Bericht(e) nennen dieselbe Zahl"
                      + (f", {zeile['conflicts']} eine andere" if zeile["conflicts"] else "")),
    )
