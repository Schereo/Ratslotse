"""Die Änderungslisten zum Haushalt — was zwischen Entwurf und Beschluss geschah.

Die alte Facette ``antraege`` zählt: „CDU: 9 Listen, 2 angenommen". Was in
den Listen STEHT, kannte die KI-Frage bis 09/2026 nicht, obwohl
``council_budget_amendments`` seit #734 die Positionen führt — mit
Erläuterung der Verwaltung („Die November-Steuerschätzung prognostiziert
höhere Erträge …") und den Zusammenstellungen je Dokument: Entwurf → nach
Änderungsliste → Beschluss des Finanzausschusses. Damit ist „Wie kam der
Haushalt 2026 von −89 auf −69 Millionen?" beantwortbar — und „Was änderte
die Verwaltung noch am Entwurf?".

WAS DIESE QUELLE NICHT WEISS, und der Baustein sagt es: WER eine Position
beantragt hat. Die Spalte „Vorschlag von" führt nur der Beschluss-Datei des
Jahrgangs 2021; überall sonst ist ``author`` NULL — und dann darf die Antwort
keine Fraktion dazuerfinden. Die Verwaltungslisten (Verw. I–III) sind
Fortschreibungen des eigenen Entwurfs, keine Fraktionsanträge.

Die Dokumente stehen in fester Reihenfolge: ``administration_1`` bis ``_3``
sind die Fortschreibungen, ``fc_decided`` die vom Ausschuss für Finanzen
beschlossene Fassung — das jüngste vorhandene Dokument trägt den Endstand.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "amendments"

_REIHENFOLGE = ("administration_1", "administration_2", "administration_3", "fc_decided")
#: Wann die Listen zum FINANZHAUSHALT mitkommen: Wenn die Frage den
#: Finanzhaushalt, Investitionen oder Zahlungen nennt. Ohne das bleibt der
#: Baustein beim Ergebnishaushalt — zwei Rechenwerke nebeneinander ohne
#: Anlass wären doppelt so lang und halb so klar.
_FHH_BEGRIFFE = re.compile(
    r"finanzhaushalt|investition|auszahlung|einzahlung|vorhaben|bau\b|baumassnahme")
_DOKUMENT = {
    "administration_1": "Änderungsliste Verwaltung I",
    "administration_2": "Änderungsliste Verwaltung II",
    "administration_3": "Änderungsliste Verwaltung III",
    "fc_decided": "Beschluss-Fassung des Ausschusses für Finanzen und Beteiligungen",
}
_EIGEN = re.compile(
    r"aenderungsliste|aenderungslisten|aenderungsantr|haushaltsantr|"
    r"verwaltungsentwurf|zwischen entwurf|vom entwurf|nachgebessert|"
    r"steuerschaetzung|entwurf[^.?!]{0,30}(?:haushalt|beschluss|geaendert)|"
    r"haushalt[^.?!]{0,30}entwurf")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Dieselben Fragen wie ``antraege`` — plus die nach dem Entwurf.

    Andocken statt kopieren: ``antraege`` hat die Streit-Wörter mit
    Haushalts-Anker („wer wollte", „abgelehnt", „debatt" …) schon erkannt;
    wo es feuert, gehört der Inhalt der Listen dazu. Eigene Wörter nur für
    die Fragen, die kein Streit sind: der Weg vom Entwurf zum Beschluss."""
    return "antraege" in facets or bool(_EIGEN.search(text))


class Store:
    """Mixin für ``CouncilStore`` — die Änderungslisten eines Jahrgangs."""

    def amendments_context(self, terms: list[str],
                           year: int | None = None) -> dict | None:
        """Entwurf → Beschluss, die Listen-Summen, die passenden Positionen.

        ``terms`` wählen bis zu vier Positionen (Treffer auf Bezeichnung,
        Produkt und Erläuterung); ohne Treffer kommen die drei größten des
        Endstands. Das Jahr ist das HAUSHALTSJAHR der Liste — die Positionen
        der Folgejahre (Finanzplanung) bleiben draußen."""
        try:
            jahr, abweicht = geld.jahrgang(
                self._conn, "council_budget_amendments_totals", "budget_year", year)
            if jahr is None:
                return None
            summen = [dict(r) for r in self._conn.execute(
                "SELECT list_key, kind, label, revenues, expenses, balance, own, herkunft_id "
                "FROM council_budget_amendments_totals "
                "WHERE budget_year = ? AND year = ?", (jahr, jahr))]
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT list_key, sub_budget, product, label, revenue, expense, "
                "       explanation, author FROM council_budget_amendments "
                "WHERE budget_year = ? AND year = ? ORDER BY list_key, seq", (jahr, jahr))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not summen and not zeilen:
            return None
        dokumente = [k for k in _REIHENFOLGE
                     if any(s["list_key"] == k for s in summen)
                     or any(z["list_key"] == k for z in zeilen)]
        if not dokumente:
            return None
        letztes = dokumente[-1]
        entwurf = next((s for s in summen if s["kind"] == "draft"), None)
        endstand = next((s for s in summen
                         if s["list_key"] == letztes and s["kind"] == "final_total"), None)
        listen = [s for s in summen if s["kind"] == "list" and s["own"]]
        listen.sort(key=lambda s: _REIHENFOLGE.index(s["list_key"])
                    if s["list_key"] in _REIHENFOLGE else 9)

        # Die Positionen des Endstands — die Fortschreibungen davor stecken
        # darin, doppelt gezählt würde sonst.
        pos = [z for z in zeilen if z["list_key"] == letztes] or zeilen

        def betrag(z: dict) -> float:
            return abs(z.get("expense") or 0) + abs(z.get("revenue") or 0)

        treffer = []
        if terms:
            bewertet = [(self._trifft(f"{z['label']} {z.get('product') or ''} "
                                      f"{z.get('explanation') or ''}", terms), z)
                        for z in pos]
            treffer = [z for n, z in sorted(bewertet, key=lambda x: (-x[0], -betrag(x[1])))
                       if n][:3]
        if not treffer:
            treffer = sorted(pos, key=betrag, reverse=True)[:3]

        urheber: dict[str, int] = {}
        for z in pos:
            if z.get("author"):
                urheber[z["author"]] = urheber.get(z["author"], 0) + 1
        beleg_id = (endstand or entwurf or (listen[0] if listen else {})).get("herkunft_id")
        return {
            "year": jahr,
            "documents": dokumente,
            "draft": entwurf,
            "final": endstand,
            "final_document": letztes,
            "lists": listen,
            "positions": treffer,
            "matched": bool(terms) and treffer is not sorted(pos, key=betrag, reverse=True)[:3],
            "authors": sorted(urheber.items(), key=lambda kv: -kv[1]),
            "beleg": self._beleg(beleg_id),
            "cash": self._finanzhaushalt(jahr, terms),
            **({"year_asked": year} if abweicht else {}),
        }

    def _finanzhaushalt(self, jahr: int, terms: list[str]) -> dict | None:
        """Die Listen zum FINANZHAUSHALT (Investitionen) — nur, wenn die Frage
        danach klingt. Sie stehen in eigenen Dokumenten mit eigener Probe
        (``council/aenderungslisten_fhh.py``); ein Ergebnishaushalts-Baustein
        ohne sie beantwortete „Welche Änderungen am Finanzhaushalt?“ bis
        09/2026 mit den Erträgen und Aufwendungen — live gemessen."""
        gefragt = " ".join(geld.falte(w) for w in terms)
        if not _FHH_BEGRIFFE.search(gefragt):
            return None
        try:
            summen = [dict(r) for r in self._conn.execute(
                "SELECT list_key, kind, label, inflows, outflows, balance, own, herkunft_id "
                "FROM council_budget_amendments_cash_totals "
                "WHERE budget_year = ? AND year = ?", (jahr, jahr))]
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT list_key, sub_budget, product, label, inflow, outflow, explanation "
                "FROM council_budget_amendments_cash WHERE budget_year = ? AND year = ? "
                "ORDER BY list_key, seq", (jahr, jahr))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not summen and not zeilen:
            return None
        letztes = next((k for k in reversed(_REIHENFOLGE)
                        if any(s["list_key"] == k for s in summen)
                        or any(z["list_key"] == k for z in zeilen)), None)
        pos = [z for z in zeilen if z["list_key"] == letztes] or zeilen

        def betrag(z: dict) -> float:
            return abs(z.get("inflow") or 0) + abs(z.get("outflow") or 0)

        treffer = []
        if terms:
            bewertet = [(self._trifft(f"{z['label']} {z.get('product') or ''} "
                                      f"{z.get('explanation') or ''}", terms), z) for z in pos]
            treffer = [z for n, z in sorted(bewertet, key=lambda x: (-x[0], -betrag(x[1]))) if n][:3]
        if not treffer:
            treffer = sorted(pos, key=betrag, reverse=True)[:3]
        return {
            "draft": next((s for s in summen if s["kind"] == "draft"), None),
            "final": next((s for s in summen if s["kind"] == "final_total"
                           and s["list_key"] == letztes), None),
            "lists": [s for s in summen if s["kind"] == "list" and s.get("own")],
            "final_document": letztes,
            "positions": treffer,
        }


def _saldo(s: dict | None) -> str:
    if not s:
        return "–"
    return (f"Erträge {geld.de_mio(s['revenues'])}, Aufwendungen {geld.de_mio(s['expenses'])}, "
            f"Saldo {geld.de_mio(s['balance'])}")


def block(data: dict | None) -> str:
    """Der Baustein — mit der Urheber-Grenze als Anweisung."""
    if not data or not (data.get("final") or data.get("draft") or data.get("positions")):
        return ""
    j = data["year"]
    zeilen = []
    if data.get("draft"):
        zeilen.append(f"- Verwaltungsentwurf {j}: {_saldo(data['draft'])}")
    if data.get("final"):
        zeilen.append(f"- Nach allen Änderungen ({_DOKUMENT.get(data['final_document'], data['final_document'])}): "
                      f"{_saldo(data['final'])}")
    for s in data.get("lists") or []:
        zeilen.append(f"  - {s['label']}: verändert den Saldo um {geld.de_mio(s['balance'])}")
    if data.get("positions"):
        zeilen.append("- Positionen" + (" zur Frage" if data.get("matched") else " (die größten)")
                      + " im Endstand:")
        for z in data["positions"]:
            teile = []
            if z.get("revenue") is not None:
                teile.append(f"Erträge {geld.de_mio(z['revenue'])}")
            if z.get("expense") is not None:
                teile.append(f"Aufwendungen {geld.de_mio(z['expense'])}")
            s = f"  - {z['label']}"
            if z.get("sub_budget"):
                s += f" (THH {z['sub_budget']})"
            s += ": " + (", ".join(teile) or "kein Betrag (Vermerk)")
            if z.get("author"):
                s += f" — vorgeschlagen von {z['author']}"
            if z.get("explanation"):
                s += f" — Erläuterung: {' '.join(z['explanation'].split())[:110]}"
            zeilen.append(s)
    if data.get("cash"):
        c = data["cash"]
        zeilen.append("- FINANZHAUSHALT (Investitionen), eigene Listen — Ein- und Auszahlungen:")
        if c.get("draft"):
            zeilen.append(f"  - Verwaltungsentwurf {j}: Einzahlungen {geld.de_mio(c['draft']['inflows'])}, "
                          f"Auszahlungen {geld.de_mio(c['draft']['outflows'])}")
        if c.get("final"):
            zeilen.append(f"  - Nach allen Änderungen ({_DOKUMENT.get(c['final_document'], c['final_document'])}): "
                          f"Einzahlungen {geld.de_mio(c['final']['inflows'])}, "
                          f"Auszahlungen {geld.de_mio(c['final']['outflows'])}")
        for s in c.get("lists") or []:
            zeilen.append(f"  - {s['label']}: Einzahlungen {geld.de_mio(s['inflows'])}, "
                          f"Auszahlungen {geld.de_mio(s['outflows'])}")
        for z in c.get("positions") or []:
            teile = []
            if z.get("inflow"):
                teile.append(f"Einzahlungen {geld.de_mio(z['inflow'])}")
            if z.get("outflow"):
                teile.append(f"Auszahlungen {geld.de_mio(z['outflow'])}")
            s = f"  - {z['label']}"
            if z.get("product"):
                s += f" ({z['product']})"
            s += ": " + (", ".join(teile) or "kein Betrag")
            if z.get("explanation"):
                s += f" — {' '.join(z['explanation'].split())[:100]}"
            zeilen.append(s)
    if data.get("authors"):
        zeilen.append("- Wer die Positionen vorschlug (Spalte „Vorschlag von“): "
                      + ", ".join(f"{a} ({n})" for a, n in data["authors"][:5]))
    else:
        zeilen.append("- WER eine Position beantragt hat, steht in diesem Jahrgang NICHT in der "
                      "Quelle (nur die Beschluss-Datei 2021 führt „Vorschlag von“). Nenne "
                      "keine Fraktion als Urheber; die Verwaltungslisten sind Fortschreibungen "
                      "des eigenen Entwurfs.")
    return (f"\nÄNDERUNGSLISTEN ZUM HAUSHALT {j} (Verwaltungsentwurf → Listen Verw. I–III →\n"
            "Beschluss-Fassung des Finanzausschusses). Positions-Beträge sind ÄNDERUNGEN\n"
            "gegenüber dem Entwurf, keine Gesamtbeträge; negativ = Minderung. Die\n"
            "Erläuterung ist die der Verwaltung. Jahr nennen, NIE mit [id]"
            + geld.beleg_text(data.get("beleg")) + ":\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="amendments_context", erkennen=recognize, block=block,
    mixin=Store, rang=90, grenze=2000,
    probefrage="Was änderte die Verwaltung noch am Haushaltsentwurf 2026?")
