"""Steuern: was angesetzt war, neben dem, was kam — Tabelle 1103.

Die Facette ``taxes`` liefert die Ist-Einnahmen je Steuerart (Tabelle 1104).
Was dort fehlt, ist die andere Hälfte der Frage „lief es wie geplant?": der
**Ansatz der beschlossenen Haushaltssatzung**. Tabelle 1103 ist die einzige
Stelle, an der wir die Plan-Seite je Steuerart überhaupt bekommen — weder der
Ergebnishaushalt noch die Ergebnisrechnung schlüsseln Steuern auf, beide führen
nur „Steuern und ähnliche Abgaben" als eine Summe
(``council/steuertabellen.py``).

Der Befund, den die Tabelle sichtbar macht, ist deutlich: Die Gewerbesteuer lag
2023, 2024 und 2025 zwischen 42 und 52 % über ihrem Ansatz. **Das ist keine
Note.** Sie hängt an den Gewinnen weniger großer Zahler und schwankte in
unserer eigenen Reihe zwischen 42,7 und 222,1 Mio. €; wer sie vorsichtig
ansetzt, plant nicht schlecht, sondern vermeidet ein Haushaltsloch, das im
laufenden Jahr niemand mehr schließt. Der Baustein stellt die Zahlen deshalb
nebeneinander und bewertet sie nicht — dieselbe Regel wie in
``components/haushalt/steuer-plan-ist.tsx``.

KEINE SUMME ÜBER DIE ARTEN. Die Tabelle führt sechs Steuerarten und im
Bestand keine Zeile „insgesamt". Die sechs zu addieren wäre unsere Rechnung und
nicht ihre — dieselbe Zurückhaltung wie bei den Investitionen, wo der Baustein
ausdrücklich die Summenzeile des Dokuments nimmt „und nicht unsere Addition".
Führt der Bestand eines Tages eine ``total``-Zeile, kommt sie mit.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "tax_plan"

#: Die Plan-Seite beim Wort. „\bplan\b" mit beiden Grenzen: „Haushaltsplan"
#: allein macht aus einer Steuerfrage noch keine Plan-Ist-Frage, und
#: „Bebauungsplan" schon gar nicht.
_PLAN_WORT = re.compile(
    r"geplant|\bplan\b|\bansatz|angesetzt|veranschlagt|eingeplant|kalkuliert|"
    r"erwartet|abweich|steuerschaetzung|"
    r"(?:mehr|weniger)[^.?!]{0,25}als (?:geplant|erwartet|gedacht)")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Steuer-Anker UND Plan-Wort — beides, sonst nichts.

    Ein Plan-Wort allein zöge die Steuertabelle in „Was ist im Haushalt für
    Schulen geplant?"; ein Steuer-Anker allein in „Wie hoch waren die
    Steuereinnahmen 2024?", die ``taxes`` vollständig beantwortet. Erst
    zusammen fragen sie nach dem Abstand zwischen beidem.
    """
    if "taxes" not in facets and "steuer" not in text:
        return False
    return bool(_PLAN_WORT.search(text))


class Store:
    """Mixin für ``CouncilStore`` — Ansatz und Rechnungsergebnis je Steuerart."""

    def tax_plan_context(self, terms: list[str],
                         year: int | None = None) -> dict | None:
        """Plan und Ist aller Steuerarten eines Jahres, dazu eine Kurzreihe.

        Der **Abstand** steht nicht in der Quelle und wird hier gebildet: Ist
        minus Plan derselben Zeile. Das ist eine Subtraktion innerhalb einer
        Tabelle und genau das, was die Hantel auf der Steuer-Seite zeigt — im
        Unterschied zu einer „Planungsgenauigkeit in Prozent", die eine Note
        wäre und die niemand veröffentlicht hat.

        Die Kurzreihe gibt es nur für die Art, nach der gefragt wurde: Alle
        sechs über drei Jahre wären achtzehn Zeilen für eine Frage, die eine
        meint. Passt keine, bleibt es bei dem einen Jahrgang.
        """
        jahr, abweichend = geld.jahrgang(
            self._conn, "council_tax_plan", "year", year)
        if jahr is None:
            return None
        try:
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT year, kind, plan, actual, provisional, herkunft_id "
                "FROM council_tax_plan WHERE year = ? ORDER BY plan DESC",
                (jahr,))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not zeilen:
            return None
        for r in zeilen:
            r["deviation"] = r["actual"] - r["plan"]
            r["deviation_pct"] = (
                (r["actual"] / r["plan"] - 1) * 100 if r["plan"] else None)
        bewertet = [(self._trifft(r["kind"], terms), r) for r in zeilen]
        beste = max(bewertet, key=lambda x: x[0])
        reihe = []
        if beste[0]:
            art = beste[1]["kind"]
            reihe = [dict(r) for r in self._conn.execute(
                "SELECT year, plan, actual FROM council_tax_plan "
                "WHERE kind = ? ORDER BY year", (art,))]
            reihe = [dict(r, kind=art) for r in reihe]
        return {"year": jahr, "year_deviates": abweichend, "asked_year": year,
                "kinds": zeilen, "series": reihe,
                "beleg": self._beleg(zeilen[0].get("herkunft_id"))}


def _beleg_zeile(b: dict | None) -> str:
    """„ — Beleg: Dokument, Stelle". Ohne Fundstelle keine Zahl.

    Ohne das ``as_of`` von ``qa._beleg_text``, und das ist gemessen: Bei den
    Haushalts-Herkünften steht dort die Abgrenzung — bei Tabelle 1105 wörtlich
    derselbe Satz, den der Kopf dieses Bausteins schon als Anweisung führt. Ihn
    ein drittes Mal anzuhängen kostete 230 Zeichen und sagte nichts Neues."""
    if not b:
        return ""
    teile = [str(t) for t in (b.get("label"), b.get("citation")) if t]
    if b.get("page"):
        teile.append(f"S. {b['page']}")
    return f" — Beleg: {', '.join(teile)}" if teile else ""


def block(daten: dict | None) -> str:
    """Der Prompt-Baustein: Ansatz, Ergebnis, Abstand — ohne Note."""
    if not daten or not daten.get("kinds"):
        return ""
    zeilen = []
    for r in daten["kinds"]:
        pct = (f", {r['deviation_pct']:+.1f} %".replace(".", ",")
               if r.get("deviation_pct") is not None else "")
        # Unter 50.000 € rundet `de_mio` auf „0,0 Mio. €", und ein Abstand von
        # „-0,0 Mio. €" liest sich wie ein Messfehler statt wie eine Punktlandung.
        abstand = (geld.de_mio(r["deviation"]) if abs(r["deviation"]) >= 50_000
                   else "unter 0,1 Mio. €")
        zeilen.append(
            f"- {r['kind']}: Ansatz {geld.de_mio(r['plan'])}, Ergebnis "
            f"{geld.de_mio(r['actual'])} (Abstand {abstand}{pct})")
    if daten.get("series") and len(daten["series"]) > 1:
        folge = " · ".join(
            f"{r['year']}: {geld.de_mio(r['plan'])} → {geld.de_mio(r['actual'])}"
            for r in daten["series"])
        zeilen.append(f"- {daten['series'][0]['kind']} über alle vorliegenden "
                      f"Jahre, Ansatz → Ergebnis: {folge}")
    if any(r.get("provisional") for r in daten["kinds"]):
        zeilen.append(f"- Das Rechnungsergebnis {daten['year']} ist VORLÄUFIG "
                      "— so weist die Tabelle es selbst aus; es kann sich mit "
                      "dem Jahresabschluss noch ändern.")
    if daten.get("year_deviates"):
        zeilen.append(f"- Zu {daten['asked_year']} führt diese Quelle keine "
                      f"Zeile; hier steht {daten['year']}. Nenne dieses Jahr, "
                      "nicht das gefragte.")
    return (
        f"\nSTEUERN {daten['year']}: ANSATZ UND ERGEBNIS (Statistisches "
        "Jahrbuch, Tabelle 1103) — die einzige Quelle, die die Plan-Seite je "
        "Steuerart ausweist; der Abstand ist Ergebnis minus Ansatz derselben "
        "Zeile.\nER IST KEINE NOTE: Die Gewerbesteuer hängt an den Gewinnen "
        "weniger großer Zahler und schwankte zwischen 42,7 und 222,1 Mio. €; "
        "wer sie vorsichtig ansetzt, vermeidet ein Loch, das im laufenden Jahr "
        "niemand mehr schließt. Nenne den Abstand, bewerte ihn nicht.\n"
        "Die Arten nicht zu einer Summe addieren und nicht mit den "
        "Ist-Einnahmen aus einem anderen Abschnitt mischen. NIE mit [id]"
        + _beleg_zeile(daten.get("beleg")) + ":\n"
        + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="tax_plan_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=80,
    grenze=1900,
    probefrage="Kam bei der Gewerbesteuer mehr rein als geplant?",
)
