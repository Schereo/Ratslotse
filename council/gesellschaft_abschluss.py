"""Die Jahresabschlüsse der städtischen Gesellschaften — das Jahr, das der
Beteiligungsbericht noch nicht hat.

Der Beteiligungsbericht (``council/beteiligungsbericht.py``) erscheint rund
anderthalb Jahre nach dem Geschäftsjahr: Im September 2026 reicht er bis 2024.
Die Gesellschaften legen ihren Jahresabschluss aber schon im Sommer nach dem
Geschäftsjahr dem Rat vor — Bilanz und Gewinn- und Verlustrechnung als eigene
Anlagen der Vorlage „Verkehr und Wasser GmbH (VWG): Jahresabschluss 2025 -
Beschluss". Daraus kommt ein Jahr früher dieselbe Zahl.

EINE REIHE, ZWEI QUELLEN (Tims Entscheidung 24.09.2026): Die Seite zeigt je
Gesellschaft eine Reihe. Der Jahresabschluss füllt, was im Bericht noch
fehlt, und bezeugt den Rest; weichen beide ab, gilt der Abschluss (gemessen
24.09.2026: 63 von 63 Überlappungen gleich, der Fall ist bisher leer). Deshalb eine eigene Tabelle — der Beteiligungsbericht-Ingest leert
``council_company_indicators`` bei jedem Lauf, und die Jahresabschluss-Zahlen
gingen dabei mit unter.

WAS GELESEN WIRD
----------------

Zwei Zahlen, dieselben wie im Beteiligungsbericht:

* **Bilanzsumme** — die Summe der Aktiva steht in jeder Bilanz zweimal: als
  Summe der Aktiva und als Summe der Passiva. Gelesen wird das größte
  Betragspaar (Geschäftsjahr, Vorjahr), das mindestens zweimal vorkommt. Die
  Doppelung IST die Probe: Stimmt Aktiva nicht mit Passiva, gibt es kein Paar.
* **Jahresergebnis** — die GuV-Zeile „Jahresüberschuss", „Jahresfehlbetrag"
  oder „Jahresüberschuss/-fehlbetrag". Einige Abschlüsse drucken den
  Fehlbetrag ohne Minus (Stadion 2025: „6. Jahresfehlbetrag 781.488,67"); ein
  Fehlbetrag ist dann negativ, ein Überschuss positiv.

Der Textauszug im Bestand taugt dafür nicht: Die Bilanz steht zweispaltig,
Aktiva links, Passiva rechts, und der Extrakt setzt die Zellen durcheinander.
Die Wortrahmen des PDFs (``eigenbetriebe_abschluss.text_aus_wortrahmen``)
setzen die Zeilen neu — der Lauf lädt deshalb die zwei einseitigen Anlagen je
Vorlage selbst.

DIE ZWEITE PROBE IST DIE ÜBERLAPPUNG — wie bei den Eigenbetrieben: Jede Anlage
nennt auch das Vorjahr, und das steht schon im Abschluss davor und im
Beteiligungsbericht. Stimmen sie überein, ist die Zahl bezeugt.
"""
from __future__ import annotations

import re
from collections import Counter

from council.eigenbetriebe_abschluss import Kennzahl, Lesung

PROBE_BILANZ = "company_accounts_balance"
PROBE_GUV = "company_accounts_result_line"
PROBE_UEBERLAPPUNG = "company_accounts_overlap"

FUNDSTELLE_BILANZ = "Bilanz — Summe der Aktiva gleich Summe der Passiva (in Euro)"
FUNDSTELLE_GUV = "Gewinn- und Verlustrechnung — Jahresüberschuss/-fehlbetrag (in Euro)"

#: Die Vorlagen — Titel „<Gesellschaft>: Jahresabschluss 2025 - Beschluss".
#: „mbH" deckt GmbH, gGmbH und „Gesellschaft mbH"; „KG" die beiden
#: GmbH & Co. KG. Was keiner Gesellschaft in ``GESELLSCHAFTEN`` zuzuordnen
#: ist, fällt in ``gesellschaft_aus_titel`` heraus.
TITEL_MUSTER: tuple[str, ...] = (
    "%mbH%Jahresabschluss 20%",
    "%KG%Jahresabschluss 20%",
)
TITEL_SQL = "(" + " OR ".join("t.title LIKE ?" for _ in TITEL_MUSTER) + ")"

#: Titelteil → Kürzel wie im Beteiligungsbericht (``council_companies``).
#: Reihenfolge entscheidet: Die Beteiligungs-GmbH (Komplementärin) vor der KG,
#: deren Name in ihrem steckt.
GESELLSCHAFTEN: tuple[tuple[str, str], ...] = (
    ("Verkehr und Wasser", "vwg"),
    ("Tourismus und Marketing", "otm"),
    ("Volkshochschule", "vhs"),
    ("Bäderbetriebsgesellschaft", "bbgo"),
    ("Weser-Ems Halle Oldenburg Beteiligungs", "weh_komplementaer"),
    ("Weser-Ems Halle Oldenburg GmbH & Co", "weh"),
    # Dieselbe Gesellschaft unter altem Namen: Die Stadionplanungsgesellschaft
    # mbH heißt seit 2024 Stadion Oldenburg Beteiligungs-GmbH — ihre Bilanz
    # 2024 nennt als Vorjahr genau die Bilanzsumme 2023 der Planungsgesellschaft
    # (339.196,60 €). Der Beteiligungsbericht führt sie unter zwei Kürzeln.
    ("Stadionplanungsgesellschaft", "stadion_komplementaer"),
    ("Stadion Oldenburg Beteiligungs", "stadion_komplementaer"),
    ("Stadion Oldenburg GmbH & Co", "stadion"),
)

_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
_JAHR_TITEL = re.compile(r"Jahresabschluss\s+(20\d\d)")
_ERGEBNIS = re.compile(
    r"^\s*(?:\d{1,2}\.\s*)?(Jahresüberschuss|Jahresfehlbetrag|Jahresergebnis)"
    r"(?:\s*/\s*-?\s*(?:fehlbetrag|überschuss|Jahresfehlbetrag))?\b", re.I)
_BILANZ_LABEL = re.compile(r"Bilanz", re.I)
_GUV_LABEL = re.compile(r"GuV|Gewinn|Verlust", re.I)


def gesellschaft_aus_titel(title: str) -> tuple[str, int] | None:
    """Kürzel und Geschäftsjahr aus dem Vorlagentitel — oder ``None``."""
    jahr = _JAHR_TITEL.search(title or "")
    if not jahr:
        return None
    for teil, kuerzel in GESELLSCHAFTEN:
        if teil in title:
            return kuerzel, int(jahr.group(1))
    return None


def art_aus_label(label: str) -> str | None:
    """``bilanz``, ``guv``, ``beide`` (eine Anlage mit allem) oder ``None``."""
    b = bool(_BILANZ_LABEL.search(label or ""))
    g = bool(_GUV_LABEL.search(label or ""))
    if re.search(r"Lagebericht|Prüfungsbericht|Feststellungsvermerk", label or "", re.I) and not (b and g):
        return None
    if b and g:
        return "beide"
    return "bilanz" if b else "guv" if g else None


def _wert(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def bilanzsumme(text: str) -> tuple[float, float] | None:
    """Das größte Betragspaar (Geschäftsjahr, Vorjahr), das zweimal steht.

    Paare entstehen nur innerhalb einer Zeile: zwei Beträge am Zeilenende,
    bei der zweispaltigen Bilanz (Aktiva | Passiva) auch vier — dann sind es
    zwei Paare. So kann kein Paar über eine Zeilengrenze entstehen, und die
    Vertauschung „Vorjahr, Geschäftsjahr" am Übergang der vier Beträge zählt
    nur einmal, nie zweimal."""
    paare: Counter[tuple[str, str]] = Counter()
    for zeile in (text or "").split("\n"):
        betraege = _BETRAG.findall(zeile)
        if len(betraege) == 2 or len(betraege) == 4:
            for i in range(0, len(betraege), 2):
                paare[(betraege[i], betraege[i + 1])] += 1
    kandidaten = [p for p, n in paare.items() if n >= 2 and _wert(p[0]) > 0]
    if not kandidaten:
        return None
    a, b = max(kandidaten, key=lambda p: _wert(p[0]))
    return _wert(a), _wert(b)


def jahresergebnis(text: str) -> tuple[float, float | None] | None:
    """Jahresüberschuss/-fehlbetrag, Geschäftsjahr und (wo gedruckt) Vorjahr.

    Die Beträge stehen in der Zeile selbst; nur wenn sie dort GANZ fehlen
    (Umbruch: „17. Jahresüberschuss/ / -fehlbetrag 0,00 0,00"), zählen die
    zwei folgenden Zeilen. Eine Zeile mit EINEM Betrag hat kein Vorjahr — das
    erste Geschäftsjahr der Stadion KG 2024; die nächste Zeile („Belastung
    auf Kapitalkonten 179.711,25") ist dann nicht ihr Vorjahr.

    Ein „Jahresfehlbetrag" ohne Minus wird negativ."""
    zeilen = (text or "").split("\n")
    for i, zeile in enumerate(zeilen):
        m = _ERGEBNIS.match(zeile)
        if not m:
            continue
        betraege = _BETRAG.findall(zeile)
        if not betraege:
            for folge in zeilen[i + 1:i + 3]:
                if _ERGEBNIS.match(folge):
                    break
                betraege.extend(_BETRAG.findall(folge))
                if len(betraege) >= 2:
                    break
        if not betraege:
            continue
        akt = _wert(betraege[0])
        vor = _wert(betraege[1]) if len(betraege) >= 2 else None
        # Nur „Jahresfehlbetrag" allein kehrt das Vorzeichen; die Doppelform
        # „Jahresüberschuss/-fehlbetrag" trägt es im Betrag.
        if m.group(1).lower() == "jahresfehlbetrag" and "/" not in zeile[:m.end()]:
            akt = -abs(akt)
            vor = -abs(vor) if vor is not None else None
        return akt, vor
    return None


def _vorjahr_genannt(text: str, jahr: int) -> bool:
    """Steht das Vorjahr im Dokument? Sonst ist die zweite Spalte keins.

    Die Stadion KG wurde am 07.06.2024 gegründet; ihre Bilanz 2024 stellt
    dem Geschäftsjahr die Eröffnungsbilanz („07. Juni 2024", 5.000 €)
    gegenüber. Die Zahl ist richtig gelesen — nur ist sie keine für 2023."""
    return str(jahr - 1) in (text or "") or bool(re.search(r"Vorjahr", text or "", re.I))


def lies_anlage(text: str, title: str, label: str, document_id: int | None) -> Lesung:
    """Die Zahlen einer Anlage — je nach Label Bilanzsumme, Jahresergebnis oder beides."""
    aus = Lesung()
    gj = gesellschaft_aus_titel(title)
    art = art_aus_label(label)
    if gj is None:
        aus.hinweise.append("Gesellschaft oder Jahr nicht im Vorlagentitel")
        return aus
    if art is None:
        aus.hinweise.append("weder Bilanz noch GuV")
        return aus
    company, jahr = gj
    aus.form = art
    vorjahr = _vorjahr_genannt(text, jahr)
    if art in ("bilanz", "beide"):
        paar = bilanzsumme(text)
        if paar is None:
            aus.hinweise.append("keine Bilanzsumme (kein Betragspaar steht zweimal)")
        else:
            aus.kennzahlen.append(Kennzahl(company, jahr, "bilanzsumme", paar[0], "EUR", jahr,
                                           document_id, FUNDSTELLE_BILANZ, PROBE_BILANZ))
            if vorjahr:
                aus.kennzahlen.append(Kennzahl(company, jahr - 1, "bilanzsumme", paar[1], "EUR",
                                               jahr, document_id, FUNDSTELLE_BILANZ, PROBE_BILANZ))
    if art in ("guv", "beide"):
        erg = jahresergebnis(text)
        if erg is None:
            aus.hinweise.append("keine Zeile Jahresüberschuss/-fehlbetrag mit Betrag")
        else:
            aus.kennzahlen.append(Kennzahl(company, jahr, "jahresergebnis", erg[0], "EUR", jahr,
                                           document_id, FUNDSTELLE_GUV, PROBE_GUV))
            if vorjahr and erg[1] is not None:
                aus.kennzahlen.append(Kennzahl(company, jahr - 1, "jahresergebnis", erg[1], "EUR",
                                               jahr, document_id, FUNDSTELLE_GUV, PROBE_GUV))
    return aus


def reihe_ergaenzen(kennzahlen: list[dict], abschluesse: list[dict],
                    firmen: set[str]) -> list[dict]:
    """Eine Reihe aus zwei Quellen: Beteiligungsbericht vorn, Jahresabschluss dahinter.

    - Nennt der Beteiligungsbericht ein Jahr und der Abschluss denselben
      Betrag (auf den Euro), bleibt die Zeile des Berichts, und der Abschluss
      zählt als weiterer Zeuge (``n_reports`` + 1).
    - Nennen beide verschiedene Beträge, gilt der Abschluss (Tims
      Entscheidung 24.09.2026: das festgestellte Dokument der Gesellschaft
      selbst, nicht die Abschrift im Bericht). ``report_value`` behält die
      Zahl des Berichts, damit die Abweichung sichtbar bleibt.
    - Fehlt das Jahr im Bericht, kommt die Zeile des Abschlusses dazu, mit
      ``source = "annual_accounts"`` — dieselbe Form, damit die Seite nicht
      zwei Reihen kennen muss.

    Nur für ``firmen`` — die Gesellschaften des jüngsten Berichts: Die Seite
    zeigt deren Karten, und eine Zeile ohne Karte wäre eine Zahl, die
    niemand sieht. Die Stadion-Gesellschaften stehen im Bericht 2024 schon
    als Karte, aber noch ohne Kennzahl — ihre Reihe kommt ganz aus den
    Abschlüssen."""
    aus = [dict(k, source="holdings_report") for k in kennzahlen]
    index = {(k["company"], k["indicator"], k["year"]): k for k in aus}
    for a in abschluesse:
        schluessel = (a["company"], a["indicator"], a["year"])
        vorhanden = index.get(schluessel)
        if vorhanden is not None:
            if abs(vorhanden["value"] - a["value"]) <= 1.0:
                vorhanden["n_reports"] = vorhanden["n_reports"] + 1
            else:
                vorhanden.update(report_value=vorhanden["value"], value=a["value"],
                                 herkunft_id=a["herkunft_id"], source="annual_accounts",
                                 n_reports=a["confirmations"])
            continue
        if a["company"] not in firmen:
            continue
        zeile = {"company": a["company"], "indicator": a["indicator"], "year": a["year"],
                 "value": a["value"], "unit": "eur", "report_year": a["report_year"],
                 "n_reports": a["confirmations"], "herkunft_id": a["herkunft_id"],
                 "fetched_at": a["fetched_at"], "source": "annual_accounts"}
        aus.append(zeile)
        index[schluessel] = zeile
    aus.sort(key=lambda k: (k["company"], k["indicator"], k["year"]))
    return aus
