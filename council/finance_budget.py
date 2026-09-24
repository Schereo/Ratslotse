"""Der Gesamtfinanzhaushalt: was die Stadt für ein Planjahr an Geld ein- und
auszahlen will — laufend, für Investitionen und zur Finanzierung.

Anlage 006 jedes Haushaltsplans, vier Seiten, dieselbe Postengliederung wie die
Finanzrechnung im Jahresabschluss (01 Steuern … 36 Finanzmittelveränderung).
Die Schwester der Anlage 005 (``council/income_budget.py``): dort Erträge und
Aufwendungen, hier Zahlungen. Nur hier stehen die **Investitionen** eines
Planjahres samt Finanzplanung bis drei Jahre voraus — die Open-Data-Dateien
(``council_investments``) tragen je Plan nur das eine Jahr.

Warum Wortkoordinaten und kein Textauszug
-----------------------------------------
Im Textauszug ist diese Tabelle nicht sicher zu lesen, gemessen am Plan 2026
(Dok. 297442):

* **Leere Zellen fehlen einfach.** „19. Beiträge … 1.747.821,05 1.956.000
  430.000" — drei Zahlen für sechs Spalten, und aus dem Text geht nicht
  hervor, welche drei.
* **Die hervorgehobene Planjahr-Spalte wandert.** Bei Einzelposten gibt der
  Auszug sie ans Zeilenende aus („… 214.490.990202.287.524" — 202.287.524 ist
  Ansatz 2026, nicht 2030), bei Summenzeilen dagegen an ihrer Stelle **und**
  noch einmal am Ende.

Über die Koordinaten ist beides eindeutig: Jede Zahl steht rechtsbündig unter
ihrer Kopfspalte („Ergebnis 2024", „Ansatz 2025" …). Zugeordnet wird über die
rechte Kante; eine Zahl, die zu keiner Spalte passt, ist kein Tabellenwert.

Gespeichert wird wie beim Gesamtergebnishaushalt nur die dritte Spalte als
Ansatz (``budget``) und die drei folgenden als Finanzplanung
(``financial_plan``). Die Ist-Spalte (Vorvorjahr) und der fortgeschriebene
Vorjahresansatz bleiben liegen — dieselbe Begründung wie in
``income_budget.py``.

Die Rechenprobe
---------------
Die Tabelle rechnet sich selbst vor, in **jeder** der sechs Spalten:

* Summe der laufenden Einzahlungen = ihre Posten, dasselbe für die
  Auszahlungen, Saldo = Einzahlungen − Auszahlungen,
* dasselbe für die Investitionstätigkeit, Finanzmittel-Überschuss = beide
  Salden,
* Saldo der Finanzierung = Kredite − Tilgung, Finanzmittelveränderung =
  Überschuss + Finanzierung.

Die Nummern der Posten verschieben sich zwischen den Jahrgängen (bis 2022
steht die erste Summe unter 10, ab 2023 unter 09); die Summenzeilen werden
deshalb an ihrer Beschriftung erkannt. Neun Beziehungen × sechs Spalten = 54 Proben je Dokument. Ein Dokument, in dem
eine davon reißt, gibt keine einzige Zahl her. Leere Zellen zählen als 0 — die
Summenzeilen beweisen dann selbst, dass sie 0 waren.

Es ist der Entwurf
------------------
Wie Anlage 005 hängt 006 an der Vorlage, mit der die Verwaltung den Haushalt
einbringt. Die Herkunft sagt es: „Stand der Einbringung".
"""
from __future__ import annotations

import re

from council.finanzberichte import _rolle

#: Die Nummern verschieben sich zwischen den Jahrgängen: Bis 2022 führt das
#: Muster „08. Einzahlungen aus der Veräußerung geringwertiger
#: Vermögensgegenstände" als eigenen Posten, die Summe steht dort unter 10,
#: ab 2023 unter 09. Erkannt werden die Summen- und Saldenzeilen deshalb an
#: ihrer **Beschriftung** (dieselben Muster wie in der Finanzrechnung,
#: ``finanzberichte.ROLLEN``), und die Blöcke, die sie summieren, ergeben sich
#: aus der Nummerierung DIESES Dokuments.
PFLICHT = ("total_in_operating", "total_out_operating", "balance_operating",
           "total_in_capital", "total_out_capital", "balance_capital",
           "cash_surplus", "balance_financing", "cash_change")

SPALTEN = 6
#: Welche Spalte was ist — wie in ``income_budget.SPALTEN_ARTEN``.
SPALTEN_ARTEN: tuple[str | None, ...] = (
    None, None, "budget", "financial_plan", "financial_plan", "financial_plan")
TOLERANZ_EUR = 1.0
PROBE = "finance_budget_total_rows"

_BETRAG = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?$")
_POSTEN_NR = re.compile(r"^(\d\d)\.$")
_JAHR = re.compile(r"^20\d\d$")


def _eur(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _kopf(woerter: list[tuple]) -> tuple[list[int], list[float]] | None:
    """Jahre und rechte Kanten der sechs Kopfspalten einer Seite.

    Der Kopf steht auf jeder Tabellenseite: „Ergebnis 2024 · Ansatz 2025 …
    Ansatz 2029", je Wort mit Koordinaten. Die rechte Kante der Jahreszahl ist
    die Kante, an der die Beträge darunter bündig enden (± wenige Punkt)."""
    paare = []
    for i, w in enumerate(woerter[:-1]):
        nxt = woerter[i + 1]
        if w[4] in ("Ergebnis", "Ansatz") and _JAHR.match(nxt[4]) and abs(w[1] - nxt[1]) < 3:
            paare.append((w[4], int(nxt[4]), nxt[2]))
    if len(paare) < SPALTEN:
        return None
    paare = sorted(paare[:SPALTEN], key=lambda p: p[2])
    if [a for a, _, _ in paare] != ["Ergebnis"] + ["Ansatz"] * (SPALTEN - 1):
        return None
    years = [j for _, j, _ in paare]
    if years != list(range(years[0], years[0] + SPALTEN)):
        return None
    return years, [x for _, _, x in paare]


def lies_seiten(seiten: list[list[tuple]]) -> tuple[list[int], dict[int, dict]]:
    """Aus den Wörtern aller Seiten die Postenzeilen.

    ``seiten`` ist je Seite die Wortliste ``(x0, y0, x1, y1, text)`` —
    genau das, was ``pymupdf.Page.get_text("words")`` liefert. Über diese
    Schnittstelle bleibt die Funktion ohne PDF testbar.

    Liefert je Postennummer ``{label, role, werte}`` (``werte``: sechs
    Spalten, ``None`` für eine leere Zelle).

    Eine Zahl gehört zu der Postennummer, die zuletzt **über** ihr steht (der
    Name eines Postens bricht über bis zu vier Zeilen um, die Zahlen stehen
    auf einer mittleren); zur Spalte, deren rechte Kante ihrer am nächsten
    liegt. Nicht gezählt wird, was keine Tabellenzeile ist: die Seitenzahl im
    Fuß, und eine Zahl in einem Satz („Die Liquiditätsprognose zum
    31.12.2025 beträgt 70 Millionen Euro") — erkannt an Wörtern rechts der
    Beschriftungsspalte auf derselben Zeile."""
    years: list[int] = []
    zeilen: dict[int, dict] = {}
    for woerter in seiten:
        kopf = _kopf(woerter)
        if kopf is None:
            continue
        jahre, kanten = kopf
        if years and jahre != years:
            continue                       # fremde Tabelle auf derselben Seite
        years = jahre
        kopf_y = min(w[1] for w in woerter if _JAHR.match(w[4]))
        fuss_y = max(w[3] for w in woerter) - 25
        marken = sorted((w[1], int(m.group(1))) for w in woerter
                        if w[0] < 60 and (m := _POSTEN_NR.match(w[4])))
        prosa_zeilen = {round(w[1]) for w in woerter
                        if w[0] > 240 and not _BETRAG.match(w[4]) and w[1] > kopf_y + 20}

        def posten_ueber(y: float, marken: list[tuple[float, int]] = marken) -> int | None:
            ueber = [nr for my, nr in marken if my <= y + 2]
            return ueber[-1] if ueber else None

        for w in woerter:
            if w[1] <= kopf_y + 20 or w[1] >= fuss_y:
                continue
            nr = posten_ueber(w[1])
            if nr is None:
                continue
            eintrag = zeilen.setdefault(nr, {"label": [], "werte": [None] * SPALTEN,
                                             "_seite_y": None})
            if w[0] < 170 and not _BETRAG.match(w[4]):
                if not _POSTEN_NR.match(w[4]) and w[4] != "=":
                    eintrag["label"].append((w[1], w[0], w[4]))
                continue
            if not _BETRAG.match(w[4]) or round(w[1]) in prosa_zeilen:
                continue
            abstand, sp = min((abs(w[2] - k), i) for i, k in enumerate(kanten))
            if abstand > 12:
                continue
            eintrag["werte"][sp] = _eur(w[4])
    aus: dict[int, dict] = {}
    for nr, e in zeilen.items():
        label = " ".join(x[2] for x in sorted(e["label"]))
        label = re.sub(r"(\w)- (\w)", r"\1-\2", re.sub(r"\s+", " ", label)).strip()
        # Was zwischen zwei Posten ohne eigene Nummer steht, landet im Label
        # des vorigen: Abschnittsüberschriften, der Satz unter der Tabelle,
        # Querverweise („Saldo aus Zeile 34 und 35", die Zahlen fehlen hier,
        # sie stehen rechts der Beschriftungsspalte).
        label = _ANHANG.sub("", label).strip(" ,")
        aus[nr] = {"label": label, "role": _eigene_rolle(label), "werte": e["werte"]}
    # Die Finanzmittelveränderung heißt bis 2022 so, was ab 2023
    # „Finanzmittel-Überschuss/-Fehlbetrag" heißt (Saldo laufend +
    # Investitionen, VOR der Finanzierung); die Veränderung nach der
    # Finanzierung heißt dort „voraussichtlicher Saldo aus Einzahlungen und
    # Auszahlungen". Unterschieden wird an der Stelle: vor oder hinter dem
    # Saldo der Finanzierungstätigkeit.
    fin = next((n for n, e in aus.items() if e["role"] == "balance_financing"), None)
    for n, e in aus.items():
        if e["role"] == "cash_change" and fin is not None and n < fin:
            e["role"] = "cash_surplus"
    return years, aus


#: Was an einem Label hängen bleibt und nicht zu ihm gehört (s. o.).
#: Eine Überschrift folgt immer auf ein Label, das auf „…tätigkeit" oder
#: „…Fehlbetrag" endet — „Summe der Auszahlungen aus laufender
#: Verwaltungstätigkeit" selbst bleibt deshalb unberührt.
_ANHANG = re.compile(
    r"\s*\([^)]*Zeile[^)]*\)|\s+Die Liquidit[äa]tsprognose.*$"
    r"|(?:(?<=t[äa]tigkeit)|(?<=tigkeiten)|(?<=Fehlbetrag))\s+"
    r"(?:Ein-, Auszahlungen aus Finanzierungst[äa]tigkeit|Auszahlungen aus laufender "
    r"Verwaltungst\S*|Auszahlungen f[üu]r Investitionst\S*|Einzahlungen f[üu]r "
    r"Investitionst\S*)$")


def _eigene_rolle(label: str) -> str | None:
    """``finanzberichte._rolle`` plus die zwei Schreibweisen des Plans, die
    die Finanzrechnung nicht kennt: „Finanzmittell-Überschuss" (2026, mit
    Tippfehler) und „voraussichtlicher Saldo aus Einzahlungen und
    Auszahlungen" (bis 2022)."""
    if re.match(r"Finanzmittel+-?\s*[ÜU]berschuss", label):
        return "cash_surplus"
    if re.match(r"voraussichtlicher Saldo aus Einzahlungen und Auszahlungen", label):
        return "cash_change"
    return _rolle(label)


def _bloecke(zeilen: dict[int, dict]) -> list[tuple[str, dict[int, int]]] | str:
    """Die Beziehungen ``Ziel = Σ Vorzeichen × Glied`` dieses Dokuments.

    Die Summenzeilen kennen wir an der Rolle, die Glieder dazwischen an der
    Nummerierung des Dokuments — so wie ``finanzberichte._bereiche`` es für
    die Finanzrechnung macht. Fehlt eine Pflichtrolle, ist das eine
    Begründung und keine Beziehung."""
    nr = {e["role"]: n for n, e in zeilen.items() if e["role"]}
    fehlend = [r for r in PFLICHT if r not in nr]
    if fehlend:
        return "Zeilen nicht gefunden: " + ", ".join(fehlend)

    def bereich(a: int, b: int) -> dict[int, int]:
        return {n: 1 for n in zeilen if a <= n <= b and not zeilen[n]["role"]}

    finanzierung = {n: (-1 if re.search(r"Auszahlung|Tilgung", zeilen[n]["label"]) else 1)
                    for n in zeilen
                    if nr["cash_surplus"] < n < nr["balance_financing"] and not zeilen[n]["role"]}
    return [
        ("total_in_operating", bereich(1, nr["total_in_operating"] - 1)),
        ("total_out_operating", bereich(nr["total_in_operating"] + 1, nr["total_out_operating"] - 1)),
        ("balance_operating", {nr["total_in_operating"]: 1, nr["total_out_operating"]: -1}),
        ("total_in_capital", bereich(nr["balance_operating"] + 1, nr["total_in_capital"] - 1)),
        ("total_out_capital", bereich(nr["total_in_capital"] + 1, nr["total_out_capital"] - 1)),
        ("balance_capital", {nr["total_in_capital"]: 1, nr["total_out_capital"]: -1}),
        ("cash_surplus", {nr["balance_operating"]: 1, nr["balance_capital"]: 1}),
        ("balance_financing", finanzierung),
        ("cash_change", {nr["cash_surplus"]: 1, nr["balance_financing"]: 1}),
    ]


def summenprobe(zeilen: dict[int, dict],
                toleranz: float = TOLERANZ_EUR) -> tuple[bool, str]:
    """Neun Beziehungen in allen sechs Spalten. Leere Zellen zählen als 0 —
    geht die Summe auf, hat das Dokument bewiesen, dass sie 0 waren."""
    bloecke = _bloecke(zeilen)
    if isinstance(bloecke, str):
        return False, bloecke
    nach_rolle = {e["role"]: n for n, e in zeilen.items() if e["role"]}
    for sp in range(SPALTEN):
        for rolle, glieder in bloecke:
            ziel = nach_rolle[rolle]
            gerechnet = sum(v * (zeilen[n]["werte"][sp] or 0.0) for n, v in glieder.items())
            steht = zeilen[ziel]["werte"][sp] or 0.0
            if abs(gerechnet - steht) > toleranz:
                return False, (f"Spalte {sp + 1}: {rolle} (Zeile {ziel}) nennt "
                               f"{steht:,.2f}, gerechnet {gerechnet:,.2f}")
    return True, ""


def lies(seiten: list[list[tuple]]) -> dict:
    """Ein Dokument auswerten: ``{budget_year, years, zeilen, bestanden,
    nachweis}``. ``zeilen`` ist leer, wenn die Probe reißt."""
    years, gelesen = lies_seiten(seiten)
    if len(years) != SPALTEN:
        return {"budget_year": None, "years": [], "zeilen": [], "bestanden": False,
                "nachweis": "Tabellenkopf nicht gefunden"}
    ok, warum = summenprobe(gelesen)
    zeilen: list[dict] = []
    if ok:
        for sp, art in enumerate(SPALTEN_ARTEN):
            if art is None:
                continue
            for nr in sorted(gelesen):
                e = gelesen[nr]
                zeilen.append({"year": years[sp], "kind": art, "nr": nr,
                               "label": e["label"], "role": e["role"],
                               "amount": e["werte"][sp] or 0.0,
                               "is_total": 1 if e["role"] else 0})
    nachweis = (f"{len(PFLICHT) * SPALTEN} Summen- und Saldenproben über "
                f"{SPALTEN} Spalten aufgegangen" if ok else warum)
    return {"budget_year": years[2], "years": years, "zeilen": zeilen,
            "bestanden": ok, "nachweis": nachweis}


def woerter_aus_pdf(daten: bytes) -> list[list[tuple]]:
    """Die Wortlisten aller Seiten eines PDFs (pymupdf)."""
    import pymupdf  # noqa: PLC0415 — nur der Ingest braucht die Bibliothek

    with pymupdf.open(stream=daten, filetype="pdf") as doc:
        return [[tuple(w[:5]) for w in seite.get_text("words")] for seite in doc]
