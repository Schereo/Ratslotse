"""Die einzelnen Vorhaben des Investitionsprogramms — welche Straße, welcher Bau.

Die Facette ``investitionen`` beantwortet „wie viel investiert die Stadt?" mit
den Summen je Teilhaushalt, und ihr Baustein schreibt selbst an, was ihr fehlt:
„‚Verkehr und Straßenbau: 10,5 Mio. €' sagt nicht, welche Straße." Genau die
Ebene darunter steht hier — 4.569 Maßnahmen aus acht Jahrgängen der Anlage 004
(``council/investitionsprogramm.py``), je mit Bezeichnung, Teilhaushalt und
Gesamtinvestitionssumme.

ZWEI DINGE, DIE MIT JEDER ZAHL REISEN und deshalb im Baustein stehen, nicht in
diesem Docstring — sie sind dieselben zwei Kästen, die auch über dem
Vorhaben-Explorer der Haushalts-Seite stehen
(``components/haushalt/vorhaben.tsx``):

1. **Der Betrag ist die Gesamtinvestitionssumme, keine Jahresrate.** Die
   Jahresaufteilung steht zwar im PDF, ist aus dessen Textextrakt aber nicht
   sicher zu holen (leere Zellen fallen ersatzlos weg) — die Begründung steht
   im Modulkopf des Parsers. Ein Sprachmodell, dem niemand das sagt, liest
   „24,8 Mio. €" als Betrag des Haushaltsjahres.
2. **Schulgebäude stehen nicht drin.** „Wird meine Schule saniert?" ist die
   häufigste Erwartung an diese Zahlen und die eine, die sie nicht erfüllen:
   Sanierung und Neubau der Schulgebäude verantwortet der Eigenbetrieb
   Gebäudewirtschaft und Hochbau mit eigenem Wirtschaftsplan.

OHNE BEGRIFFSTREFFER KOMMT NICHTS. Die Summen macht ``investitionen``; diese
Facette hat nur dann etwas zu sagen, wenn die Frage ein Vorhaben benennt. Sie
darf deshalb an ``investitionen`` andocken (jede Investitionsfrage prüft sie
mit), ohne den Prompt jeder Investitionsfrage zu verlängern — die Store-Methode
gibt ``None`` zurück, und der Baustein bleibt leer.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt

NAME = "measures"

#: Wörter, die ein VORGANG sind: Da wird etwas gebaut, saniert, erneuert. Sie
#: feuern die Facette auch ohne Geld-Wort, denn „Wird die Nadorster Straße
#: saniert?" ist eine Frage an dieses Programm und trägt keinen Euro.
_VORHABEN = re.compile(
    r"sanier|ausbau|umbau|neubau|erneuerung|strassenbau|vorhaben|bauprojekt|"
    r"baumassnahm|investitionsprogramm|"
    r"wird[^.?!]{0,40}(?:gebaut|saniert|ausgebaut|erneuert)|"
    r"kostet[^.?!]{0,20}\b(?:neu)?bau\b")

#: Wörter, die ein BAUWERK sind — und damit genauso gut ein Thema. Sie
#: brauchen einen Geld-Anker, und das ist gemessen: Der Testkorpus hält „Was
#: wurde zum Radweg an der Donnerschweer Straße beschlossen?" und „Wer stellte
#: den Antrag zum Radweg?" ausdrücklich für Fragen OHNE Haushalts-Bezug — sie
#: fragen nach einem Beschluss und nach einem Antragsteller, nicht nach einer
#: Investitionssumme. „radweg" allein zöge in beide das Investitionsprogramm.
#:
#: ``\bbruecke`` mit Wortgrenze VORN, und das gegen die Regel, dass deutsche
#: Komposita die Grenze hinten brauchen: „CäcilienBRÜCKE" steckt in „Wann wurde
#: die Cäcilienbrücke gesperrt?", einer Sperrungs-Frage ohne jedes Vorhaben.
#: Die Grenze vorn sperrt sie aus und lässt „Brücke" und „Brückensanierung"
#: durch — letztere trägt ohnehin schon „sanier".
_BAUWERK = re.compile(r"radweg|\bbruecke|kreuzung")

#: Begriffe, die in diesem Register alles und damit nichts treffen.
#:
#: Die Suchbegriffe kommen aus der Query-Expansion, und die stellt „Was wird
#: gebaut?" pflichtgemäß auch als Finanzierungsfrage — „Investition", „Bau",
#: „Stadt", „Oldenburg" stehen dann in der Liste. ``_trifft`` sucht in beide
#: Richtungen und mit einem Wortstamm von vier Zeichen: „stadt" steckt in „SUG
#: Alter STADThafen", „bau" in jedem zweiten Namen. Fünf Vorhaben, die nur so
#: zusammengekommen sind, sind keine Antwort auf eine Vorhaben-Frage, sondern
#: fünf zufällige Zeilen — deshalb zählen diese Begriffe nicht als Treffer.
#: Bleibt danach kein Begriff übrig, liefert die Methode nichts.
_ALLERWELTSWOERTER = frozenset({
    "stadt", "stadtverwaltung", "oldenburg", "kommune", "verwaltung",
    "investition", "investitionen", "investiert", "investiv",
    "bau", "baut", "bauen", "gebaut", "baumassnahme", "baumassnahmen",
    "neubau", "vorhaben", "projekt", "projekte", "massnahme", "massnahmen",
    "haushalt", "haushaltsplan", "etat", "budget", "geld", "euro",
    "kosten", "kostet", "ausgaben", "finanzierung", "gesamt", "gesamtkosten",
})


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    """Vorhaben-Frage? Angedockt an ``investitionen``, sonst an Bau-Wörtern."""
    if "investitionen" in facets:
        return True
    # `plan` steht für den Geld-Anker: Es ist genau die Facette, die `_F_PLAN`
    # setzt — der Bauwerk-Zweig braucht ihn, der Vorgangs-Zweig nicht.
    if not _VORHABEN.search(text) and not (
            _BAUWERK.search(text) and "plan" in facets):
        return False
    # Dieselbe Bremse, die `investitionen` in qa.py hat, und aus demselben
    # Grund: „Was sagte die SPD zum Stadionneubau?" ist eine Positionsfrage,
    # „Wie entwickelte sich die Diskussion?" eine Verlaufsfrage. Ein Bau-Wort
    # ist dort das Thema und noch keine Frage nach dem Haushalt.
    return typ not in ("party", "person", "history") or "plan" in facets


class Store:
    """Mixin für ``CouncilStore`` — die Vorhaben zur Frage."""

    def measures_context(self, terms: list[str],
                         year: int | None = None) -> dict | None:
        """Bis zu fünf Vorhaben, deren Bezeichnung zur Frage passt.

        Gesucht wird über drei Felder: die Bezeichnung der Maßnahme, die Namen
        ihrer Sachkonto-Detailzeilen (``details`` — dort stehen die
        Bauabschnitte und Straßennamen, die der Kurzname verschweigt) und den
        Namen des Teilhaushalts. Straßennamen sind der häufigste Fall, und sie
        stehen mal im einen, mal im anderen Feld.

        Ohne Begriffstreffer: ``None``. Die größten Brocken als Trostpreis
        auszugeben, wie ``investitionen_fuer_begriffe`` es tut, wäre hier
        falsch — dort sind es dreizehn Teilhaushalte, von denen jeder die Frage
        „was wird gebaut" mitbeantwortet, hier 565 Vorhaben je Jahrgang, von
        denen fünf zufällige nichts beantworten.
        """
        jahr, abweichend = geld.jahrgang(
            self._conn, "council_investment_measures", "year", year,
            "level = 'measure'")
        if jahr is None:
            return None
        begriffe = [w for w in terms
                    if geld.falte(w).replace(" ", "") not in _ALLERWELTSWOERTER]
        if not begriffe:
            return None
        try:
            thh = {r["sub_budget_no"]: r["label"] for r in self._conn.execute(
                "SELECT sub_budget_no, label FROM council_investment_measures "
                "WHERE year = ? AND level = 'sub_budget'", (jahr,))}
            zeilen = [dict(r) for r in self._conn.execute(
                "SELECT sub_budget_no, code, label, grand_total, details, "
                "herkunft_id FROM council_investment_measures "
                "WHERE year = ? AND level = 'measure'", (jahr,))]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        bewertet = []
        for r in zeilen:
            bereich = thh.get(r["sub_budget_no"], "")
            n = (self._trifft(r["label"], begriffe)
                 + self._trifft(r["details"], begriffe)
                 + self._trifft(bereich, begriffe))
            if n:
                r["sub_budget"] = bereich
                bewertet.append((n, r))
        if not bewertet:
            return None
        treffer = [r for _, r in sorted(
            bewertet, key=lambda x: (-x[0], -(x[1]["grand_total"] or 0)))][:5]
        # Derselbe Code im Vorjahrgang: Das Programm wird jedes Jahr neu
        # aufgelegt, und die Gesamtsumme eines Vorhabens ändert sich dabei.
        # Zwei Ausgaben derselben Zeile nebeneinander sind keine Rechnung über
        # Quellen hinweg — es ist dieselbe Spalte desselben Dokuments, ein Jahr
        # früher.
        for r in treffer:
            davor = self._conn.execute(
                "SELECT year, grand_total FROM council_investment_measures "
                "WHERE code = ? AND level = 'measure' AND year < ? "
                "ORDER BY year DESC LIMIT 1", (r["code"], jahr)).fetchone()
            r["davor"] = dict(davor) if davor else None
        return {"year": jahr, "year_deviates": abweichend, "asked_year": year,
                "measures": treffer,
                "beleg": self._beleg(treffer[0].get("herkunft_id"))}


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
    """Der Prompt-Baustein: die Vorhaben, und was ihre Beträge nicht sind."""
    if not daten or not daten.get("measures"):
        return ""
    zeilen = []
    for r in daten["measures"]:
        betrag = geld.de_mio(r["grand_total"])
        s = f"- {r['label']} ({r['sub_budget']}): {betrag}"
        davor = r.get("davor")
        # Nur nennen, wenn es auf eine Nachkommastelle auch ANDERS aussieht:
        # „4,3 statt 4,3" liest sich als Änderung, wo keine ist.
        if davor and geld.de_mio(davor["grand_total"]) != betrag:
            s += (f" — im Programm {davor['year']} noch "
                  f"{geld.de_mio(davor['grand_total'])}")
        zeilen.append(s)
    hinweis = ""
    if daten.get("year_deviates"):
        hinweis = (f"\nZum Haushaltsjahr {daten['asked_year']} liegt kein "
                   f"Investitionsprogramm vor; hier steht der Jahrgang "
                   f"{daten['year']}. Nenne dieses Jahr, nicht das gefragte.")
    return (
        f"\nEINZELNE INVESTITIONS-VORHABEN (Investitionsprogramm zum "
        f"Haushaltsplan {daten['year']}, Anlage 004 — Verwaltungsentwurf, also "
        "GEPLANT und nicht beschlossen). Nur nutzen, wenn nach einem "
        "bestimmten Vorhaben gefragt ist.\n"
        "JEDER BETRAG IST DIE GESAMTINVESTITIONSSUMME über alle Jahre, KEINE "
        "Jahresrate — die Aufteilung auf die Jahre steht in dieser Quelle "
        "nicht.\n"
        "SCHULGEBÄUDE FEHLEN HIER: Sanierung und Neubau der Schulen "
        "verantwortet der Eigenbetrieb Gebäudewirtschaft und Hochbau mit "
        "eigenem Wirtschaftsplan; steht eine Schule nicht dabei, heißt das "
        "nicht, dass nichts geschieht.\n"
        "Keine Summe über diese Zeilen, nicht mit dem Finanzhaushalt "
        "verrechnen. NIE mit [id]"
        + _beleg_zeile(daten.get("beleg")) + ":\n"
        + "\n".join(zeilen) + hinweis + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="measures_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=60,
    grenze=1500,
    probefrage="Was kostet der Ausbau der Nadorster Straße?",
)
