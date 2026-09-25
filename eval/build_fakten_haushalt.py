#!/usr/bin/env python3
"""Baut ``eval/cases_fakten_haushalt.json`` — die Haushaltsfälle der Fakten-Eval.

**Jeder Goldwert kommt aus einer SQL-Abfrage auf** ``data/council.sqlite``,
nie aus einer Modellantwort und nie aus dem Kontext, den die Eval prüfen
soll: Stünden die Goldwerte aus ``qa.geld_kontext`` hier, prüfte die Eval
den Kontext gegen sich selbst und fände keinen einzigen seiner Fehler. Die
Abfrage steht als ``quelle`` am Goldfakt (Tabelle, Spalte, Zeile) — wer einen
Wert anzweifelt, führt sie aus.

**Neue Daten?** ``python eval/build_fakten_haushalt.py`` zieht alle Werte
neu. Ändert sich einer, zeigt ``git diff`` es; ändert sich eine Abfrage so,
dass sie nicht mehr genau einen Wert liefert, bricht der Bau ab, statt einen
Fall mit falschem Gold zu schreiben.

**Wie die Fälle gewählt sind** (Auftrag vom 23.09.2026): alle Haushaltsseiten
aus ``kern/knowledge.py`` und alle Facetten aus ``council/qa.py`` /
``council/geld/``; etwa 60 % Lotti — auf der passenden Seite UND auf einer
unpassenden (eine Investitionsfrage auf ``/haushalt/schulden``) —, 40 % Frag
den Rat; Jahres-Fallen (Vorjahr, Rekordjahr, Plan statt Ist) als
``verboten``; und Fälle, die die Daten NICHT beantworten
(``antwort_in_daten: false``), bei denen die richtige Antwort „steht nicht
in den Daten“ ist.

``baustein`` nennt den Codeteil, der den Fakt liefern muss — nach ihm
gruppiert der Bericht die Kontextfehler. ``bekannt`` markiert die drei
Kontextfehler, die der Faktencheck vom 23.09. schon fand und die ein anderer
Zweig (``claude/geld-kontext-korrekt``) gerade repariert.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

ZIEL = WURZEL / "eval" / "cases_fakten_haushalt.json"
DB = Path(os.environ.get("COUNCIL_DB") or WURZEL / "data" / "council.sqlite")

# Die Bausteine — Codeteil, der den Fakt in den Prompt bringen muss.
B_SCHULDEN = "store.schulden_kontext (qa: schulden)"
B_PLAN = "store.haushalt_fuer_begriffe (qa: plan)"
B_ANSATZ = "store.ansatz_fuer_begriffe (qa: ansatz)"
B_IST = "store.result_actual_for_terms (qa: ist)"
B_GRUENDE = "store.abweichungsgruende_fuer_begriffe (qa: gruende)"
B_KASSE = "store.kassensicht_kontext (qa: kassensicht)"
B_INVEST_PLAN = "store.investitionen_fuer_begriffe (qa: investitionen)"
B_INVEST_IST = "store.investitionen_ist_kontext (qa: gebaut)"
B_MASSNAHMEN = "council/geld/measures.py"
B_WIRTSCHAFTSPLAN = "council/geld/business_plans.py"
B_KONZERN = "store.konzern_kontext (qa: konzern)"
B_BETEILIGUNGEN = "council/geld/companies.py"
B_STEUERN = "store.steuern_fuer_begriffe (qa: taxes)"
B_STEUERPLAN = "council/geld/tax_plan.py"
B_HEBESATZ = "council/geld/tax_rates.py"
B_STEUERKRAFT = "store.steuerkraft_kontext (qa: ausgleich)"
B_GEWST_STAT = "Gewerbesteuerstatistik (council_trade_tax_statistics)"
B_GEBUEHREN = "store.gebuehren_fuer_begriffe (qa: fees)"
B_GEBUEHRSAETZE = "council/geld/fee_rates.py"
B_STELLEN = "store.stellenplan_kontext (qa: stellenplan)"
B_SATZUNG = "council/geld/bylaw.py"
B_VERGLEICH = "store.staedtevergleich_kontext (qa: vergleich)"
B_ANTRAEGE = "store.haushaltsantraege_kontext (qa: antraege) / council/geld/amendments.py"
B_PRODUKTE = "store.produkte_fuer_begriffe (qa: produkte)"
B_PRUEFUNG = "store.pruefberichte_fuer_begriffe (qa: pruefung)"
B_KENNZAHLEN = "store.kennzahlen_kontext (qa: indicators)"
B_BILANZ = "store.bilanz_kontext (qa: bilanz)"
B_LIQUIDITAET = "council/geld/liquidity.py"
B_VOLLZUG = "council/geld/execution.py"
B_NACHBEWILLIGUNG = "store.nachbewilligungen_kontext (qa: supplementary_approvals)"
B_SPENDEN = "council/geld/donations.py"
B_REIHE = "council/geld/expense_series.py"
B_GLOSSAR = "kern/glossar.py + Seitenwissen (kern/knowledge.py)"
B_SEITE = "Seitenwissen (kern/knowledge.py)"
B_KEINE = "— (die Daten geben es nicht her)"
B_ARCHIV = "Ratsarchiv (Lotti → Frag den Rat, assistant.projekt_ins_archiv)"
B_KERN = "Seiten-Kernzahlen (assistant.SEITEN_KERN)"

_con: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _con
    if _con is None:
        if not DB.exists():
            raise SystemExit(f"Keine Ratsdatenbank unter {DB} (scripts/lokale_daten.py hol + setz)")
        _con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return _con


def wert(sql: str, *args: Any) -> float:
    """Genau EIN Wert — sonst bricht der Bau ab."""
    zeilen = _db().execute(sql, args).fetchall()
    if len(zeilen) != 1 or zeilen[0][0] is None:
        raise SystemExit(f"Abfrage liefert nicht genau einen Wert ({len(zeilen)} Zeilen):\n"
                         f"  {sql} {args}")
    return float(zeilen[0][0])


def _quelle(sql: str, args: tuple) -> str:
    text = " ".join(sql.split())
    for a in args:
        text = text.replace("?", repr(a), 1)
    return text


def Z(sql: str, *args: Any, jahr: int | None = None, bez: str = "", einheit: str = "€",
      faktor: float = 1.0, toleranz: float | None = None, pflicht: bool = True,
      label: list[str] | None = None, oder: list[dict] | None = None,
      teile: list[float] | None = None, baustein: str | None = None,
      betrag: bool = False) -> dict:
    """Ein Zahl-Goldfakt aus einer Abfrage."""
    w = wert(sql, *args) * faktor
    g: dict[str, Any] = {"art": "zahl", "wert": abs(w) if betrag else round(w, 2),
                         "einheit": einheit, "bezeichnung": bez,
                         "quelle": _quelle(sql, args) + (f" × {faktor:g}" if faktor != 1 else "")}
    if jahr is not None:
        g["jahr"] = jahr
    if toleranz is not None:
        g["toleranz"] = toleranz
    if not pflicht:
        g["pflicht"] = False
    if label:
        g["label"] = label
    if oder:
        g["oder"] = oder
    if teile:
        g["teile"] = teile
    if baustein:
        g["baustein"] = baustein
    return g


def ALT(sql: str, *args: Any, jahr: int | None = None, faktor: float = 1.0) -> dict:
    """Eine gleichwertige Antwort für ``oder``."""
    a: dict[str, Any] = {"wert": round(wert(sql, *args) * faktor, 2),
                         "quelle": _quelle(sql, args)}
    if jahr is not None:
        a["jahr"] = jahr
    return a


def T(muss: list, quelle: str, pflicht: bool = True, baustein: str | None = None) -> dict:
    g: dict[str, Any] = {"art": "text", "muss": muss, "quelle": quelle}
    if not pflicht:
        g["pflicht"] = False
    if baustein:
        g["baustein"] = baustein
    return g


def V(sql: str, *args: Any, grund: str, als_jahr: int | None = None, einheit: str = "€",
      faktor: float = 1.0) -> dict:
    v: dict[str, Any] = {"art": "zahl", "wert": round(wert(sql, *args) * faktor, 2),
                         "einheit": einheit, "grund": grund, "quelle": _quelle(sql, args)}
    if als_jahr is not None:
        v["als_jahr"] = als_jahr
    return v


def _seitentitel(route: str) -> str:
    from kern import knowledge
    w = knowledge.fuer_route(route)
    return w.title if w else ""


FAELLE: list[dict] = []

#: Was das Fenster je Haushaltsseite mitschickt — `page_title`, `heading`,
#: `anchors`, abgelesen am 24.09.2026 aus den Requests des echten Fensters
#: (Playwright, dev-Datenstand). Die Überschrift der Übersicht trägt eine
#: Zahl aus den Daten; ändert sie sich, ist sie hier nachzuziehen.
_TITEL = "Ratslotse — Oldenburger Ratsinformationen verständlich"
FENSTER: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "/haushalt": (_TITEL, "Oldenburg plant Ausgaben von 883,9 Millionen Euro.",
                  ("Die Anzeigetafel", "Der Kassenzettel", "Verfügbar nach Jahresergebnis",
                   "Die Teilhaushalte")),
    "/haushalt/schulden": (_TITEL, "Wie viel Schulden hat Oldenburg?",
                           ("Drei Zählweisen, eine Stadt · Stand 31.12.2024", "Kredite und Zinsen",
                            "Schulden total", "Verbürgt und selbst geschuldet", "Liquiditätsstand")),
    "/haushalt/einnahmen": (_TITEL, "Woher kommt das Geld?", ("Spielraum über alle Quellen",)),
    "/haushalt/investitionen": (_TITEL, "Was gebaut wird — und was daraus wurde",
                                ("Investitionsprogramm · Pläne 2019–2026", "Vorhaben")),
    "/haushalt/pflicht": (_TITEL, "Muss oder kann?", ("Anteil an allen Ausgaben · Plan 2026",)),
    "/haushalt/produkte": (_TITEL, "Was kostet eigentlich …?", ("Produktebene · Haushaltsjahr 2026",)),
    "/haushalt/personal": (_TITEL, "Wer macht die Arbeit?",
                           ("Stellenplan Teil A · Beamtinnen und Beamte · Plan 2026",
                            "Personalaufwand")),
    "/haushalt/plan-ist": (_TITEL, "Geplant und geworden",
                           ("Jahresabschluss 2024 · Mio. € Aufwand", "Der Haushaltsvollzug")),
    "/haushalt/konzern": (_TITEL, "Und ist das die ganze Stadt?",
                          ("Gesamtabschluss · Konzern Oldenburg · 2024", "Jahresergebnis im Plan",
                           "Gebühr im Zeitverlauf")),
    "/haushalt/vergleich": (_TITEL, "Steht Oldenburg besser da als Osnabrück?",
                            ("Kreisfreie Städte Niedersachsens",)),
    "/haushalt/steuer": (_TITEL, "Gewerbesteuer",
                         ("Steuer-Steckbrief · Hebesatz Gewerbesteuer", "Der Verlauf im Jahr",
                          "Steuern: geplant und geworden", "Wer zahlt das?", "Hebesatz-Treppe",
                          "Was die Stadt nicht entscheidet")),
    "/haushalt/mitreden": (_TITEL, "Mitreden", ("Haushaltsberatungen 2019–2026", "Position",
                                                "Vorhaben")),
}


def F(id_: str, kanal: str, frage: str, kategorie: str, baustein: str, gold: list[dict], *,
      route: str | None = None, verboten: list[dict] | None = None, in_daten: bool = True,
      notiz: str = "", bekannt: str | None = None, fenster: bool = False,
      vorfragen: list[str] | None = None) -> None:
    # Kurzform „lotti:/haushalt/schulden“ = Lotti auf dieser Seite.
    if kanal.startswith("lotti:"):
        kanal, route = "lotti", kanal.split(":", 1)[1]
    fall: dict[str, Any] = {"id": id_, "kanal": kanal}
    if kanal == "lotti":
        assert route, id_
        fall["route"] = route
        fall["refs"] = {}
        # Die Überschrift der Seite reist im echten Fenster mit (`heading`)
        # und zieht auf Haushalts-Seiten eigene Facetten — also auch hier.
        fall["heading"] = _seitentitel(route)
        # `fenster`: Titel, Überschrift und Bausteine, wie das ECHTE Fenster
        # sie schickt (gemessen 24.09.2026 mit Playwright, s. FENSTER). Der
        # Seitentitel aus kern/knowledge.py ist nicht die Überschrift der
        # Seite — auf der Übersicht steht „Oldenburg plant Ausgaben von 883,9
        # Millionen Euro.“, nicht „Haushalt — Übersicht“; und die Überschrift
        # zieht eigene Facetten. Ohne sie mäße die Eval einen anderen Prompt
        # als den, den die Laienfragen im Fenster bekommen.
        if fenster:
            titel, ueberschrift, anker = FENSTER[route]
            fall.update({"page_title": titel, "heading": ueberschrift, "anchors": list(anker)})
    fall.update({"frage": frage, "kategorie": kategorie, "baustein": baustein,
                 "antwort_in_daten": in_daten, "gold": gold, "verboten": verboten or []})
    if notiz:
        fall["notiz"] = notiz
    if vorfragen:
        # Anschlussfrage: Die Eval stellt erst diese Fragen und schickt die
        # Antworten als Verlauf mit, wie das Fenster (run_fakten.frage_stellen).
        fall["vorfragen"] = vorfragen
    if bekannt:
        fall["bekannt"] = bekannt
    assert all(f["id"] != id_ for f in FAELLE), f"doppelte id {id_}"
    FAELLE.append(fall)


# --------------------------------------------------------------------------- #
# Abfragen, die mehrfach gebraucht werden
# --------------------------------------------------------------------------- #
DEBT = "SELECT {} FROM council_debt WHERE year = ?"
TAX = "SELECT amount FROM council_taxes WHERE year = ? AND kind = ?"
BUDGET_SUM = "SELECT {} FROM council_budget WHERE year = ? AND is_total = 1"
BUDGET_AREA = "SELECT {} FROM council_budget WHERE year = ? AND area = ?"
IST = ("SELECT {} FROM council_income_statement WHERE year = ? AND sub_budget_no IS NULL "
       "AND nr = ?")
INV_IST = "SELECT total FROM council_investments_actual WHERE year = ?"
INV_ART = "SELECT amount FROM council_investments_actual_kinds WHERE year = ? AND title = ?"
INV_PLAN = "SELECT outflows FROM council_investments WHERE year = ? AND label = ?"
BP = "SELECT {} FROM council_business_plans WHERE enterprise = ? AND year = ?"
GRUPPE = ("SELECT amount_keur FROM council_group_entities WHERE year = ? AND kind = ? "
          "AND entity = ?")
FIRMA = ("SELECT value FROM council_company_indicators WHERE company = ? AND indicator = ? "
         "AND year = ?")
STELLEN = ("SELECT {} FROM council_staff_plan WHERE budget_year = ? AND kind = 'total' "
           "AND label = 'Summe' AND positions_planned = ?")
STELLEN_TEIL = ("SELECT {} FROM council_staff_plan WHERE budget_year = ? AND kind = 'group' "
                "AND label = ?")
RATE = "SELECT rate FROM council_tax_rates WHERE year = ? AND kind = ?"
CITY = ("SELECT value FROM council_city_comparison WHERE year = ? AND city = ? "
        "AND indicator = ?")
PRODUKT = "SELECT {} FROM council_products WHERE year = ? AND product_name = ?"
FEE = "SELECT amount FROM council_fee_rates WHERE year = ? AND key = ?"
BYLAW = "SELECT {} FROM council_budget_bylaw WHERE year = ? AND supplement = 0"
KENNZ = ("SELECT value FROM council_indicators WHERE report_year = ? AND year = ? "
         "AND indicator = ?")
VOLLZUG = ("SELECT {} FROM council_budget_execution WHERE budget_year = ? AND as_of = ? "
           "AND budget = ? AND kind = ? AND is_total = 1 AND label = 'Summen'")


def bauen() -> list[dict]:  # noqa: PLR0915 — eine Liste, kein Algorithmus
    FAELLE.clear()

    # ------------------------------------------------------------------ #
    # Schulden
    # ------------------------------------------------------------------ #
    stand25 = Z(DEBT.format("total"), 2025, jahr=2025, bez="Schuldenstand Kern + Eigenbetriebe",
                label=["Schuld", "Jahresende", "Stand"])
    eb_text = T([["Eigenbetrieb", "Eigenbetriebe"]], "council_debt: Abgrenzung Tabelle 1108 "
                "(Kernhaushalt und Eigenbetriebe)")
    vorjahr_als_25 = V(DEBT.format("total"), 2024, grund="Wert von 2024 als Stand 2025",
                       als_jahr=2025)
    F("hh-schulden-stand-lotti", "lotti", "Wie hoch sind die Schulden der Stadt?",
      "haushalt/schulden", B_SCHULDEN, [stand25, eb_text], route="/haushalt/schulden",
      verboten=[vorjahr_als_25],
      notiz="Faktencheck lotti[0]: beide Modelle richtig — der Fall hält das fest.")
    F("hh-schulden-stand-rat", "rat", "Wie hoch sind die Schulden der Stadt Oldenburg?",
      "haushalt/schulden", B_SCHULDEN, [stand25, eb_text], verboten=[vorjahr_als_25],
      notiz="Faktencheck rat[5]: Gemini las die Aufschlüsselung 2025 als 2024.")
    F("hh-schulden-stand-heute", "lotti", "Wie hoch sind die Schulden der Stadt?",
      "haushalt/schulden", B_SCHULDEN, [stand25], route="/dashboard",
      verboten=[vorjahr_als_25],
      notiz="Außerhalb des Haushalts-Bereichs: seit 22.09. zieht die Frage allein die Zahlen.")
    F("hh-schulden-auf-investitionen", "lotti", "Wie viel Schulden hat die Stadt?",
      "haushalt/schulden", B_SCHULDEN, [stand25], route="/haushalt/investitionen",
      verboten=[vorjahr_als_25], notiz="Unpassende Seite: die Überschrift zieht Investitionen.")
    prokopf = Z(DEBT.format("per_capita"), 2025, jahr=2025, bez="Schulden je Einwohner*in")
    F("hh-schulden-prokopf-lotti", "lotti", "Wie viel Schulden hat Oldenburg pro Kopf?",
      "haushalt/schulden", B_SCHULDEN, [prokopf], route="/haushalt/schulden",
      verboten=[V(DEBT.format("per_capita"), 2024, grund="je EW 2024 als 2025", als_jahr=2025)])
    F("hh-schulden-prokopf-rat", "rat", "Wie hoch ist die Verschuldung je Einwohner in Oldenburg?",
      "haushalt/schulden", B_SCHULDEN, [prokopf],
      verboten=[V(DEBT.format("per_capita"), 2024, grund="je EW 2024 als 2025", als_jahr=2025)])
    F("hh-schulden-kreditmarkt-2025", "lotti",
      "Wie viel Schulden hatte die Stadt Ende 2025 am Kreditmarkt?",
      "haushalt/schulden", B_SCHULDEN,
      [Z(DEBT.format("credit_market"), 2025, jahr=2025, bez="Kreditmarktschulden",
         label=["Kreditmarkt"])], route="/haushalt/schulden",
      verboten=[V(DEBT.format("credit_market"), 2024, grund="Kreditmarkt 2024 als 2025",
                  als_jahr=2025)],
      bekannt="Faktencheck 23.09.: „davon“-Zeilen 2025 stehen unter „Ein Jahr davor (2024)“",
      notiz="Die Aufschlüsselung des jüngsten Jahres — der bekannte Zuordnungsfehler.")
    F("hh-schulden-eigenbetriebe-2025", "rat",
      "Wie viel der städtischen Schulden entfielen Ende 2025 auf die Eigenbetriebe?",
      "haushalt/schulden", B_SCHULDEN,
      [Z(DEBT.format("municipal_enterprises"), 2025, jahr=2025, bez="Schulden der Eigenbetriebe",
         label=["Eigenbetrieb"])],
      verboten=[V(DEBT.format("municipal_enterprises"), 2024, grund="Eigenbetriebe 2024 als 2025",
                  als_jahr=2025)],
      bekannt="Faktencheck 23.09.: „davon“-Zeilen 2025 stehen unter „Ein Jahr davor (2024)“")
    F("hh-schulden-kern-lotti", "lotti", "Wie hoch ist der Schuldenstand des Kernhaushalts allein?",
      "haushalt/schulden", B_SCHULDEN,
      [Z("SELECT core_budget FROM council_integrated_debt WHERE year = ?", 2024, jahr=2024,
         bez="Kernhaushalt (nur Geldschulden)",
         oder=[ALT(DEBT.format("credit_market"), 2025, jahr=2025)])],
      route="/haushalt/schulden",
      notiz="Startfrage der Seite. Zwei ehrliche Antworten: Bilanz 2024 oder Kreditmarkt 2025.")
    konzern_schulden = Z("SELECT total FROM council_integrated_debt WHERE year = ?", 2024,
                         jahr=2024, bez="Integrierte Schulden Konzern Stadt")
    F("hh-schulden-konzern-lotti", "lotti",
      "Wie hoch sind die Schulden, wenn man alle Beteiligungen mitzählt?",
      "haushalt/schulden", B_SCHULDEN, [konzern_schulden], route="/haushalt/konzern")
    F("hh-schulden-konzern-rat", "rat",
      "Wie hoch ist die Verschuldung des Konzerns Stadt Oldenburg mit allen Beteiligungen?",
      "haushalt/schulden", B_SCHULDEN, [konzern_schulden])
    F("hh-schulden-2020-lotti", "lotti", "Wie hoch waren die Schulden der Stadt 2020?",
      "haushalt/schulden", B_SCHULDEN,
      [Z(DEBT.format("total"), 2020, jahr=2020, bez="Schuldenstand 2020")],
      route="/haushalt/schulden",
      verboten=[V(DEBT.format("total"), 2025, grund="jüngster Stand statt 2020", als_jahr=2020)],
      notiz="Jahres-Falle: ein älteres Jahr, das die Reihe hat (1995–2025).")
    F("hh-schulden-entwicklung-rat", "rat",
      "Wie haben sich die Schulden der Stadt seit 2015 entwickelt?",
      "haushalt/schulden", B_SCHULDEN,
      [Z(DEBT.format("total"), 2015, jahr=2015, bez="Schuldenstand 2015"), stand25])
    F("hh-schulden-rekord-rat", "rat", "In welchem Jahr hatte die Stadt die höchsten Schulden?",
      "haushalt/schulden", B_SCHULDEN,
      [Z("SELECT total FROM council_debt ORDER BY total DESC LIMIT 1", jahr=2025,
         bez="Höchster Schuldenstand der Reihe")],
      notiz="Rekordjahr-Falle: 2025 knapp vor 1998 (325,5 Mio. €).")
    F("hh-schulden-zinsen-lotti", "lotti", "Wie viel Zinsen zahlt die Stadt für ihre Schulden?",
      "haushalt/schulden", B_ANSATZ,
      [Z(IST.format("result"), 2024, 17, jahr=2024, bez="Zinsaufwendungen Ist 2024",
         oder=[ALT("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? "
                   "AND year = ? AND nr = ?", 2026, 2026, 17, jahr=2026)])],
      route="/haushalt/schulden",
      notiz="Die Seite verspricht „was jährlich an Zinsen und Tilgung fällig wird“.")
    F("hh-schulden-tilgung-lotti", "lotti:/haushalt/schulden", "Wie viel tilgt die Stadt Oldenburg jedes Jahr?",
      "haushalt/schulden", B_SATZUNG,
      [Z(BYLAW.format("out_financing"), 2026, jahr=2026, bez="Auszahlungen Finanzierungstätigkeit",
         oder=[ALT("SELECT result FROM council_cash_flow_statement WHERE year = ? AND "
                   "role = 'balance_financing'", 2024, jahr=2024)])])
    # 2025 gleichwertig: Der Jahresabschluss 2025 ist seit 24.09.2026 im
    # Bestand, Lotti nennt dann den jüngeren Stand (gilt für alle „oder 2025“).
    buerg = Z("SELECT balance FROM council_buergschaften WHERE year = ?", 2024, jahr=2024,
              bez="Bürgschaften",
              oder=[ALT("SELECT balance FROM council_buergschaften WHERE year = ?", 2025, jahr=2025)])
    F("hh-buergschaften-lotti", "lotti", "Für wie viel Geld bürgt die Stadt?",
      "haushalt/schulden", B_SCHULDEN, [buerg], route="/haushalt/schulden")
    F("hh-buergschaften-rat", "rat", "Wofür bürgt die Stadt Oldenburg und in welcher Höhe?",
      "haushalt/schulden", B_SCHULDEN, [buerg])
    F("hh-kredite-2026-rat", "rat", "Wie viel Kredit darf die Stadt 2026 aufnehmen?",
      "haushalt/satzung", B_SATZUNG,
      [Z(BYLAW.format("liquidity_loans"), 2026, jahr=2026, bez="Höchstbetrag Liquiditätskredite"),
       T([["Liquiditätskredit", "Liquiditätskredite", "Kassenkredit"]],
         "council_budget_bylaw.liquidity_loans, year=2026")])
    F("hh-satzung-liquiditaet-lotti", "lotti", "Wie hoch darf der Liquiditätskredit sein?",
      "haushalt/satzung", B_SATZUNG,
      [Z(BYLAW.format("liquidity_loans"), 2026, jahr=2026, bez="Höchstbetrag Liquiditätskredite")],
      route="/haushalt/schulden")

    # ------------------------------------------------------------------ #
    # Ergebnishaushalt: Plan
    # ------------------------------------------------------------------ #
    aufwand26 = Z(BUDGET_SUM.format("expenses"), 2026, jahr=2026, bez="Aufwendungen Plan 2026",
                  oder=[ALT("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? "
                            "AND year = ? AND nr = 20", 2026, 2026, jahr=2026),
                        ALT("SELECT expenses FROM council_budget_amendments_totals WHERE "
                            "budget_year = ? AND list_key = 'fc_decided' AND year = ? "
                            "AND kind = 'final_total'", 2026, 2026, jahr=2026)])
    F("hh-plan-aufwand-2026-lotti", "lotti", "Wie viel gibt die Stadt 2026 aus?",
      "haushalt/plan", B_PLAN, [aufwand26], route="/haushalt",
      verboten=[V(BUDGET_SUM.format("expenses"), 2025, grund="Plan 2025 als 2026", als_jahr=2026)])
    F("hh-plan-aufwand-2026-rat", "rat", "Wie viel Geld will die Stadt Oldenburg 2026 ausgeben?",
      "haushalt/plan", B_PLAN, [aufwand26],
      verboten=[V(BUDGET_SUM.format("expenses"), 2025, grund="Plan 2025 als 2026", als_jahr=2026)])
    F("hh-plan-ertrag-2026-lotti", "lotti:/haushalt/einnahmen", "Wie viel nimmt die Stadt 2026 ein?",
      "haushalt/plan", B_PLAN,
      [Z(BUDGET_SUM.format("revenues"), 2026, jahr=2026, bez="Erträge Plan 2026",
         oder=[ALT("SELECT revenues FROM council_budget_amendments_totals WHERE "
                   "budget_year = ? AND list_key = 'fc_decided' AND year = ? "
                   "AND kind = 'final_total'", 2026, 2026, jahr=2026),
               ALT("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? "
                   "AND year = ? AND nr = 12", 2026, 2026, jahr=2026)])])
    defizit26 = Z(BUDGET_SUM.format("result"), 2026, jahr=2026, bez="Fehlbetrag Plan 2026",
                  oder=[ALT("SELECT balance FROM council_budget_amendments_totals WHERE "
                            "budget_year = ? AND list_key = 'fc_decided' AND year = ? "
                            "AND kind = 'final_total'", 2026, 2026, jahr=2026),
                        ALT(VOLLZUG.format("budgeted"), 2026, "2026-06-30", "result", "result",
                            jahr=2026)])
    F("hh-plan-defizit-2026-lotti", "lotti", "Mit welchem Defizit plant die Stadt 2026?",
      "haushalt/plan", B_PLAN, [defizit26], route="/haushalt")
    F("hh-plan-defizit-2026-rat", "rat", "Wie groß ist das geplante Defizit im Haushalt 2026?",
      "haushalt/plan", B_PLAN, [defizit26])
    F("hh-plan-groesster-bereich-rat", "rat",
      "Welcher Bereich des städtischen Haushalts kostet 2026 am meisten?",
      "haushalt/plan", B_PLAN,
      [T(["Soziales"], "council_budget year=2026: größte expenses = Soziales und Gesundheit"),
       Z(BUDGET_AREA.format("expenses"), 2026, "Soziales und Gesundheit", jahr=2026,
         bez="Aufwendungen Soziales und Gesundheit")])
    F("hh-plan-meiste-lotti", "lotti", "Wofür gibt die Stadt am meisten aus?",
      "haushalt/plan", B_PLAN,
      [T(["Soziales"], "council_budget year=2026: größte expenses = Soziales und Gesundheit"),
       Z(BUDGET_AREA.format("expenses"), 2026, "Soziales und Gesundheit", jahr=2026,
         bez="Aufwendungen Soziales und Gesundheit", pflicht=False)],
      route="/haushalt", notiz="Startfrage der Übersicht.")
    F("hh-plan-jugend-2026-lotti", "lotti", "Was kostet der Bereich Jugend und Familie 2026?",
      "haushalt/plan", B_PLAN,
      [Z(BUDGET_AREA.format("expenses"), 2026, "Jugend und Familie", jahr=2026,
         bez="Aufwendungen Jugend und Familie",
         oder=[ALT(BUDGET_AREA.format("-result"), 2026, "Jugend und Familie", jahr=2026)])],
      route="/haushalt/produkte")
    F("hh-plan-schule-2025-rat", "rat", "Wie viel war 2025 für Schule und Bildung eingeplant?",
      "haushalt/plan", B_PLAN,
      [Z(BUDGET_AREA.format("expenses"), 2025, "Schule und Bildung", jahr=2025,
         bez="Aufwendungen Schule und Bildung 2025",
         oder=[ALT(BUDGET_AREA.format("-result"), 2025, "Schule und Bildung", jahr=2025)])],
      verboten=[V(BUDGET_AREA.format("expenses"), 2026, "Schule und Bildung",
                  grund="Plan 2026 als 2025", als_jahr=2025)],
      notiz="Jahres-Falle: ein älterer Plan, der nicht der jüngste ist.")
    F("hh-plan-personal-rat", "rat", "Was kostet das Personal der Stadt im Jahr 2026?",
      "haushalt/plan", B_ANSATZ,
      [Z("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? AND year = ? "
         "AND nr = 13", 2026, 2026, jahr=2026, bez="Personalaufwendungen Plan 2026")])
    F("hh-plan-personal-lotti", "lotti", "Wie viel gibt die Stadt 2026 für Personal aus?",
      "haushalt/plan", B_ANSATZ,
      [Z("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? AND year = ? "
         "AND nr = 13", 2026, 2026, jahr=2026, bez="Personalaufwendungen Plan 2026")],
      route="/haushalt/personal")
    F("hh-plan-transfer-lotti", "lotti:/haushalt/pflicht",
      "Wie viel gibt die Stadt 2026 für Transferleistungen wie Sozialhilfe aus?",
      "haushalt/plan", B_ANSATZ,
      [Z("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? AND year = ? "
         "AND nr = 18", 2026, 2026, jahr=2026, bez="Transferaufwendungen Plan 2026")])
    F("hh-ergebnis-finanz-lotti", "lotti",
      "Was ist der Unterschied zwischen Ergebnishaushalt und Finanzhaushalt?",
      "haushalt/begriffe", B_GLOSSAR,
      [T([["Ertrag", "Erträge", "einnimmt", "Einnahmen"], ["Aufwand", "Aufwendungen"],
          ["Einzahlung", "Auszahlung", "ein- und ausgeht", "tatsächlich fließt",
           "tatsächlich geflossen"]],
         "Glossar (kern/glossar.py): Ergebnishaushalt, Finanzhaushalt")],
      route="/haushalt", notiz="Faktencheck lotti[3]: beide richtig.")
    F("hh-konzern-groesse-lotti", "lotti", "Wie groß ist der Haushalt mit den Eigenbetrieben?",
      "haushalt/konzern", B_KONZERN,
      [Z("SELECT amount FROM council_group_items WHERE year = ? AND role = 'expenses_total'",
         2024, jahr=2024, bez="Konzern: Summe ordentliche Aufwendungen (Gesamtabschluss)"),
       Z(GRUPPE, 2024, "expenses", "Kernverwaltung (Stadt Oldenburg)", jahr=2024, faktor=1000,
         bez="Kernverwaltung: Aufwendungen 2024", pflicht=False)],
      route="/haushalt", notiz="Startfrage der Übersicht; PR 27 „zwei Zählweisen“.")

    # ------------------------------------------------------------------ #
    # Ist, Plan-Ist, Kassensicht, Vollzug
    # ------------------------------------------------------------------ #
    F("hh-ist-abweichung-2024-lotti", "lotti", "Wie stark wich das Ergebnis 2024 vom Ansatz ab?",
      "haushalt/ist", B_IST,
      [Z(IST.format("result"), 2024, 21, jahr=2024, bez="ordentliches Ergebnis Ist 2024"),
       Z(IST.format("budgeted"), 2024, 21, jahr=2024, bez="ordentliches Ergebnis Ansatz 2024")],
      route="/haushalt/plan-ist", notiz="Startfrage der Seite.")
    ist_aufwand24 = Z(IST.format("result"), 2024, 20, jahr=2024,
                      bez="Summe ordentliche Aufwendungen Ist 2024",
                      oder=[ALT("SELECT amount FROM council_expense_series WHERE year = ?", 2024,
                                jahr=2024)])
    F("hh-ist-aufwand-2024-lotti", "lotti", "Wie viel hat die Stadt 2024 tatsächlich ausgegeben?",
      "haushalt/ist", B_IST, [ist_aufwand24], route="/haushalt/plan-ist",
      notiz="Startfrage der Seite. Plan-statt-Ist-Falle.")
    F("hh-ist-aufwand-2024-rat", "rat", "Wie viel hat die Stadt Oldenburg 2024 tatsächlich ausgegeben?",
      "haushalt/ist", B_IST, [ist_aufwand24])
    F("hh-ist-aufwand-2023-lotti", "lotti", "Wie viel hat die Stadt 2023 tatsächlich ausgegeben?",
      "haushalt/ist", B_IST,
      [Z(IST.format("result"), 2023, 20, jahr=2023, bez="Summe ordentliche Aufwendungen Ist 2023",
         oder=[ALT("SELECT amount FROM council_expense_series WHERE year = ?", 2023, jahr=2023)])],
      route="/haushalt/plan-ist",
      verboten=[V(IST.format("result"), 2024, 20, grund="Ist 2024 als 2023", als_jahr=2023)])
    F("hh-ist-ergebnis-2024-rat", "rat", "Mit welchem Ergebnis hat die Stadt 2024 abgeschlossen?",
      "haushalt/ist", B_IST,
      [Z(IST.format("result"), 2024, 21, jahr=2024, bez="ordentliches Ergebnis Ist 2024")],
      verboten=[V(IST.format("budgeted"), 2024, 21, grund="Ansatz statt Ergebnis", als_jahr=2024)])
    F("hh-ist-gruende-2024-rat", "rat", "Warum war das Ergebnis 2024 besser als geplant?",
      "haushalt/ist", B_GRUENDE,
      [T([["Steuer", "Gewerbesteuer"]], "council_variance_reasons year=2024 nr=1: +75,1 Mio. €"),
       Z("SELECT delta_meur FROM council_variance_reasons WHERE year = ? AND nr = 1", 2024,
         jahr=2024, faktor=1e6, bez="Mehrertrag Steuern 2024", toleranz=0.01)])
    F("hh-ist-gruende-2024-lotti", "lotti", "Woran lag es, dass 2024 besser lief als geplant?",
      "haushalt/ist", B_GRUENDE,
      [T([["Steuer", "Gewerbesteuer"]], "council_variance_reasons year=2024 nr=1: +75,1 Mio. €")],
      route="/haushalt/plan-ist")
    F("hh-ist-reihe-lotti", "lotti:/haushalt/plan-ist", "Wie haben sich die Ausgaben der Stadt seit 2020 entwickelt?",
      "haushalt/ist", B_REIHE,
      [Z("SELECT amount FROM council_expense_series WHERE year = ?", 2020, jahr=2020,
         bez="Ordentliche Aufwendungen 2020"),
       Z("SELECT amount FROM council_expense_series WHERE year = ?", 2025, jahr=2025,
         bez="Ordentliche Aufwendungen 2025")])
    F("hh-kasse-2024-lotti", "lotti",
      "Wie viel Geld ist 2024 in der Kasse tatsächlich geflossen — gab es ein Plus oder Minus?",
      "haushalt/ist", B_KASSE,
      [Z("SELECT result FROM council_cash_flow_statement WHERE year = ? AND role = 'cash_surplus'",
         2024, jahr=2024, bez="Finanzmittelfehlbetrag 2024")],
      route="/haushalt/plan-ist",
      notiz="Die zweite Rechnung desselben Abschlusses: Ergebnis +34,6 Mio., Kasse −22,4 Mio.")
    F("hh-liquide-mittel-rat", "rat", "Wie viel Geld hat die Stadt auf dem Konto?",
      "haushalt/ist", B_LIQUIDITAET,
      [Z("SELECT amount FROM council_liquidity WHERE month = ?", "2026-05", jahr=2026,
         bez="Liquidität Mai 2026",
         oder=[ALT("SELECT value FROM council_balance_sheet WHERE year = ? AND "
                   "role = 'cash_and_equivalents'", 2024, jahr=2024)])])
    F("hh-vollzug-2026-lotti", "lotti", "Was erwartet die Verwaltung für das laufende Jahr?",
      "haushalt/vollzug", B_VOLLZUG,
      [Z(VOLLZUG.format("forecast"), 2026, "2026-06-30", "result", "result", jahr=2026,
         bez="Prognose Ergebnis 2026 (Stand 30.06.2026)")],
      route="/haushalt/plan-ist", notiz="Die Seite verspricht genau das.")
    F("hh-vollzug-2026-rat", "rat",
      "Wie entwickelt sich der Haushalt 2026 laut dem letzten Bericht der Verwaltung?",
      "haushalt/vollzug", B_VOLLZUG,
      [Z(VOLLZUG.format("forecast"), 2026, "2026-06-30", "result", "result", jahr=2026,
         bez="Prognose Ergebnis 2026 (Stand 30.06.2026)"),
       Z(VOLLZUG.format("budgeted"), 2026, "2026-06-30", "result", "result", jahr=2026,
         bez="Ansatz Ergebnis 2026", pflicht=False)])
    F("hh-vollzug-2025-rat", "rat", "Wie ist das Haushaltsjahr 2025 ausgegangen?",
      "haushalt/vollzug", B_VOLLZUG,
      [Z(VOLLZUG.format("forecast"), 2025, "2025-12-31", "result", "result", jahr=2025,
         bez="Ergebnis 2025 laut Vollzugsbericht zum 31.12.2025")],
      notiz="Der Jahresabschluss 2025 fehlt noch; der Vollzugsbericht zum 31.12. hat das Ergebnis.")

    # ------------------------------------------------------------------ #
    # Investitionen
    # ------------------------------------------------------------------ #
    inv_ist25 = Z(INV_IST, 2025, jahr=2025, bez="Investitionen Ist 2025")
    inv_vorjahr = V(INV_IST, 2024, grund="Ist 2024 als 2025", als_jahr=2025)
    F("hh-invest-gesamt-lotti", "lotti", "Wie viel investiert die Stadt insgesamt?",
      "haushalt/investitionen", B_INVEST_PLAN,
      [Z(VOLLZUG.format("budgeted"), 2026, "2026-06-30", "cash", "outflow", jahr=2026,
         bez="Investitionsauszahlungen Plan 2026 (Vollzugsbericht)",
         oder=[ALT(BYLAW.format("out_capital"), 2026, jahr=2026)])],
      route="/haushalt/investitionen",
      notiz="Startfrage. Der Finanzhaushalt je Teilhaushalt reicht nur bis 2025; der Plan 2026 "
            "steht in Satzung und Vollzugsbericht.")
    F("hh-invest-gesamt-rat", "rat", "Wie viel will die Stadt 2026 investieren?",
      "haushalt/investitionen", B_INVEST_PLAN,
      [Z(VOLLZUG.format("budgeted"), 2026, "2026-06-30", "cash", "outflow", jahr=2026,
         bez="Investitionsauszahlungen Plan 2026 (Vollzugsbericht)",
         oder=[ALT(BYLAW.format("out_capital"), 2026, jahr=2026)])],
      verboten=[V(INV_PLAN, 2025, "Finanzhaushalt Gesamtinvestitionen", grund="Plan 2025 als 2026",
                  als_jahr=2026)])
    F("hh-invest-ist-2025-lotti", "lotti", "Wie viel wurde 2025 tatsächlich investiert?",
      "haushalt/investitionen", B_INVEST_IST, [inv_ist25], route="/haushalt/investitionen",
      verboten=[inv_vorjahr], notiz="Startfrage der Seite.")
    F("hh-invest-ist-2025-rat", "rat", "Wie viel hat die Stadt 2025 wirklich investiert?",
      "haushalt/investitionen", B_INVEST_IST, [inv_ist25], verboten=[inv_vorjahr])
    F("hh-invest-ist-auf-schulden", "lotti", "Wie viel hat die Stadt 2025 tatsächlich investiert?",
      "haushalt/investitionen", B_INVEST_IST, [inv_ist25], route="/haushalt/schulden",
      verboten=[inv_vorjahr], notiz="Unpassende Seite: die Überschrift zieht Schulden.")
    F("hh-invest-meiste-lotti", "lotti",
      "Wofür gibt die Stadt bei den Investitionen am meisten aus?",
      "haushalt/investitionen", B_INVEST_IST,
      [Z(INV_ART, 2025, "Sonstige Investitionstätigkeit", jahr=2025,
         bez="Ist 2025: Sonstige Investitionstätigkeit", label=["Sonstige"]),
       Z(INV_PLAN, 2025, "Finanzmanagement und Recht", jahr=2025,
         bez="Plan 2025: größter Teilhaushalt", pflicht=False, baustein=B_INVEST_PLAN)],
      route="/haushalt/investitionen",
      bekannt="Faktencheck 23.09.: Auszahlungsarten 2025 stehen unter „Höchster Wert (2020)“",
      notiz="Faktencheck lotti[4].")
    F("hh-invest-bau-2025-rat", "rat", "Wie viel hat die Stadt 2025 für Baumaßnahmen ausgegeben?",
      "haushalt/investitionen", B_INVEST_IST,
      [Z(INV_ART, 2025, "Baumaßnahmen", jahr=2025, bez="Ist 2025: Baumaßnahmen",
         label=["Baumaßnahmen"])],
      verboten=[V(INV_ART, 2024, "Baumaßnahmen", grund="Baumaßnahmen 2024 als 2025",
                  als_jahr=2025)],
      bekannt="Faktencheck 23.09.: Auszahlungsarten 2025 stehen unter „Höchster Wert (2020)“")
    F("hh-invest-rekord-lotti", "lotti", "In welchem Jahr hat die Stadt am meisten investiert?",
      "haushalt/investitionen", B_INVEST_IST,
      [Z("SELECT total FROM council_investments_actual ORDER BY total DESC LIMIT 1", jahr=2020,
         bez="Höchster Wert der Reihe (2020)")],
      route="/haushalt/investitionen",
      verboten=[V(INV_IST, 2025, grund="jüngstes Jahr als Rekord", als_jahr=2020)])
    F("hh-invest-2022-lotti", "lotti", "Wie viel wurde 2022 tatsächlich investiert?",
      "haushalt/investitionen", B_INVEST_IST,
      [Z(INV_IST, 2022, jahr=2022, bez="Investitionen Ist 2022")], route="/haushalt/investitionen",
      verboten=[V(INV_IST, 2025, grund="jüngstes Jahr als 2022", als_jahr=2022)])
    F("hh-invest-verkehr-lotti", "lotti:/haushalt/investitionen",
      "Wie viel wollte die Stadt 2025 in Verkehr und Straßenbau investieren?",
      "haushalt/investitionen", B_INVEST_PLAN,
      [Z(INV_PLAN, 2025, "Verkehr und Straßenbau", jahr=2025,
         bez="Plan 2025: Investitionen Verkehr und Straßenbau")])
    F("hh-invest-teilhaushalt-lotti", "lotti",
      "Welcher Teilhaushalt hatte 2025 den größten Investitionsplan?",
      "haushalt/investitionen", B_INVEST_PLAN,
      [T(["Finanzmanagement"], "council_investments year=2025 level=sub_budget: größte outflows"),
       Z(INV_PLAN, 2025, "Finanzmanagement und Recht", jahr=2025,
         bez="Plan 2025: Finanzmanagement und Recht")],
      route="/haushalt/investitionen")
    F("hh-invest-schule-lotti", "lotti", "Wie viel investiert die Stadt 2025 in Schulen?",
      "haushalt/investitionen", B_INVEST_PLAN,
      [T([["Gebäudewirtschaft", "Eigenbetrieb", "Wirtschaftsplan"]],
         "Schulbau liegt beim Eigenbetrieb Gebäudewirtschaft und Hochbau (Hinweis im Baustein)"),
       Z(INV_PLAN, 2025, "Schule und Bildung", jahr=2025, bez="Plan 2025: Teilhaushalt Schule",
         pflicht=False)],
      route="/haushalt/investitionen",
      notiz="Falle: Der Teilhaushalt Schule ist klein (1,9 Mio.), weil Schulbau im Eigenbetrieb liegt.")
    F("hh-invest-vorhaben-rat", "rat",
      "Welches ist das größte einzelne Vorhaben im Investitionsprogramm 2025?",
      "haushalt/investitionen", B_MASSNAHMEN,
      [T(["Kampfmittel"], "council_investment_measures year=2025 level=measure: größte grand_total"),
       Z("SELECT grand_total FROM council_investment_measures WHERE year = ? AND level = 'measure' "
         "ORDER BY grand_total DESC LIMIT 1", 2025, jahr=2025,
         bez="Fliegerhorst Kampfmittelsondierung (Gesamtsumme)")])
    F("hh-invest-plan-ist-rat", "rat",
      "Wie viel hat die Stadt 2025 geplant zu investieren und wie viel wurde es tatsächlich?",
      "haushalt/investitionen", B_INVEST_PLAN,
      [Z(INV_PLAN, 2025, "Finanzhaushalt Gesamtinvestitionen", jahr=2025,
         bez="Plan 2025: Gesamtinvestitionen"), dict(inv_ist25, baustein=B_INVEST_IST)])

    # ------------------------------------------------------------------ #
    # Eigenbetriebe, Konzern, Beteiligungen
    # ------------------------------------------------------------------ #
    awb26 = Z(BP.format("expenses"), "awb", 2026, jahr=2026, bez="AWB Aufwendungen Plan 2026")
    egh26 = Z(BP.format("expenses"), "egh", 2026, jahr=2026, bez="EGH Aufwendungen Plan 2026",
              oder=[ALT(GRUPPE, 2024, "expenses", "Eigenbetrieb Gebäudewirtschaft und Hochbau",
                        jahr=2024, faktor=1000)])
    F("hh-eb-liste-lotti", "lotti", "Welche Eigenbetriebe gibt es und wie viel geben sie aus?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [T([["Abfall"], ["Gebäudewirtschaft"], ["Bäder", "Bäderbetrieb"]],
         "council_business_plans: awb, egh, bbo"), awb26, egh26,
       Z(GRUPPE, 2024, "expenses", "Bäderbetrieb", jahr=2024, faktor=1000,
         bez="Bäderbetrieb Aufwendungen 2024 (Gesamtabschluss)", baustein=B_KONZERN)],
      route="/haushalt/konzern",
      bekannt="Faktencheck 23.09.: Eigenbetriebe ohne Aufwendungen im Kontext",
      notiz="Faktencheck lotti[2]. Der Bäderbetrieb hat eine Aufwandszahl — im Gesamtabschluss.")
    F("hh-eb-awb-lotti", "lotti:/haushalt/konzern", "Wie viel gibt der Abfallwirtschaftsbetrieb 2026 aus?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN, [awb26],
      verboten=[V(BP.format("expenses"), "awb", 2025, grund="Plan 2025 als 2026", als_jahr=2026)])
    F("hh-eb-egh-ergebnis-lotti", "lotti",
      "Welches Ergebnis plant die Gebäudewirtschaft für 2026?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "egh", 2026, jahr=2026, bez="EGH Ergebnis Plan 2026")],
      route="/haushalt/konzern",
      verboten=[V(BP.format("result"), "egh", 2025, grund="Plan 2025 als 2026", als_jahr=2026)])
    F("hh-eb-egh-ist-2024-rat", "rat",
      "Mit welchem Jahresergebnis hat der Eigenbetrieb Gebäudewirtschaft 2024 abgeschlossen?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [Z("SELECT value FROM council_enterprise_accounts WHERE enterprise = ? AND year = ? "
         "AND metric = 'result'", "egh", 2024, jahr=2024, bez="EGH Jahresergebnis 2024")],
      verboten=[V(BP.format("result"), "egh", 2024, grund="Plan statt Abschluss", als_jahr=2024)])
    F("hh-eb-egh-invest-lotti", "lotti:/haushalt/konzern",
      "Wie viel will der Eigenbetrieb Gebäudewirtschaft und Hochbau 2026 investieren?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [Z(BP.format("capital_plan"), "egh", 2026, jahr=2026, bez="EGH Vermögensplan 2026")])
    F("hh-eb-baeder-invest-rat", "rat", "Wie viel investiert der Bäderbetrieb 2026?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [Z(BP.format("investments"), "bbo", 2026, jahr=2026, bez="Bäderbetrieb Investitionen 2026")])
    F("hh-baeder-verlust-lotti", "lotti", "Wie hoch ist der Verlust der Bäderbetriebsgesellschaft?",
      "haushalt/eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "bbgo", 2026, jahr=2026, bez="BBGO Ergebnis Plan 2026",
         oder=[ALT(FIRMA, "bbgo", "jahresergebnis", 2024, jahr=2024)])],
      route="/haushalt/konzern")
    F("hh-klinikum-aufwand-lotti", "lotti", "Wie hoch sind die Aufwendungen des Klinikums?",
      "haushalt/konzern", B_KONZERN,
      [Z(GRUPPE, 2024, "expenses", "Klinikum Oldenburg AöR", jahr=2024, faktor=1000,
         bez="Klinikum Aufwendungen 2024 (Gesamtabschluss)")],
      route="/haushalt/konzern", notiz="Startfrage der Seite.")
    F("hh-klinikum-ergebnis-rat", "rat", "Welches Jahresergebnis hatte das Klinikum Oldenburg 2024?",
      "haushalt/konzern", B_BETEILIGUNGEN,
      [Z(FIRMA, "klinikum", "jahresergebnis", 2024, jahr=2024, bez="Klinikum Jahresergebnis 2024")])
    F("hh-konzern-liste-lotti", "lotti", "Welche Betriebe gehören zum Konzern?",
      "haushalt/konzern", B_BETEILIGUNGEN,
      [T([["Klinikum"], ["GSG"], ["Verkehr und Wasser", "VWG"], ["Weser-Ems"],
          ["Abfallwirtschaft", "AWB"]],
         "council_companies report_year=2024")],
      route="/haushalt/konzern", notiz="Startfrage der Seite.")
    F("hh-gsg-ergebnis-rat", "rat", "Wie viel Gewinn hat die GSG Oldenburg 2024 gemacht?",
      "haushalt/konzern", B_BETEILIGUNGEN,
      [Z(FIRMA, "gsg", "jahresergebnis", 2024, jahr=2024, bez="GSG Jahresergebnis 2024")])
    F("hh-stadion-gesellschaft-rat", "rat",
      "Welchen Verlust plant die Stadion Oldenburg GmbH & Co. KG für 2026?",
      "haushalt/konzern", B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "stadion", 2026, jahr=2026, bez="Stadion-KG Ergebnis Plan 2026")],
      verboten=[V(BP.format("result"), "stadion", 2025, grund="Plan 2025 als 2026",
                  als_jahr=2026)])
    F("hh-konzern-aufwand-rat", "rat",
      "Wie viel gibt der gesamte Konzern Stadt Oldenburg mit Klinikum und Betrieben aus?",
      "haushalt/konzern", B_KONZERN,
      [Z("SELECT amount FROM council_group_items WHERE year = ? AND role = 'expenses_total'",
         2024, jahr=2024, bez="Konzern: Summe ordentliche Aufwendungen 2024")])

    # ------------------------------------------------------------------ #
    # Steuern, Hebesätze, Zuweisungen
    # ------------------------------------------------------------------ #
    gewst25 = Z(TAX, 2025, "Gewerbesteuer (-umlage)", jahr=2025, bez="Gewerbesteuer 2025")
    F("hh-steuern-gesamt-2025-rat", "rat", "Wie viel Steuern hat die Stadt 2025 eingenommen?",
      "haushalt/steuern", B_STEUERN,
      [Z(TAX, 2025, "total", jahr=2025, bez="Steuern gesamt 2025 (vorläufig)")],
      verboten=[V(TAX, 2024, "total", grund="2024 als 2025", als_jahr=2025)])
    F("hh-gewst-2025-lotti", "lotti", "Wie viel Gewerbesteuer hat die Stadt 2025 eingenommen?",
      "haushalt/steuern", B_STEUERN, [gewst25], route="/haushalt/einnahmen",
      verboten=[V(TAX, 2024, "Gewerbesteuer (-umlage)", grund="2024 als 2025", als_jahr=2025)])
    F("hh-gewst-2025-rat", "rat", "Wie hoch waren die Gewerbesteuereinnahmen 2025?",
      "haushalt/steuern", B_STEUERN, [gewst25],
      verboten=[V(TAX, 2024, "Gewerbesteuer (-umlage)", grund="2024 als 2025", als_jahr=2025)])
    F("hh-gewst-steckbrief-lotti", "lotti", "Wie hat sich diese Steuer zuletzt entwickelt?",
      "haushalt/steuern", B_STEUERN, [dict(gewst25, pflicht=False),
                                      T(["Gewerbesteuer"], "Steckbrief-Seite /haushalt/steuer")],
      route="/haushalt/steuer",
      notiz="Ohne ?art= weiß die Seite nicht, welche Steuer — ein Fall für die Rückfrage.")
    F("hh-gewst-plan-ist-2024-rat", "rat", "Wie weit lag die Gewerbesteuer 2024 über dem Plan?",
      "haushalt/steuern", B_STEUERPLAN,
      [Z("SELECT plan FROM council_tax_plan WHERE year = ? AND kind = ?", 2024,
         "Gewerbesteuer (-umlage)", jahr=2024, bez="Gewerbesteuer Plan 2024"),
       # Die Antwort IST die Differenz; Plan und Ist genügen als ihre Teile.
       Z("SELECT actual - plan FROM council_tax_plan WHERE year = ? AND kind = ?", 2024,
         "Gewerbesteuer (-umlage)", jahr=2024, bez="Gewerbesteuer Ist über Plan 2024",
         teile=[wert("SELECT plan FROM council_tax_plan WHERE year = 2024 AND "
                     "kind = 'Gewerbesteuer (-umlage)'"),
                wert("SELECT actual FROM council_tax_plan WHERE year = 2024 AND "
                     "kind = 'Gewerbesteuer (-umlage)'")])])
    F("hh-gewst-auf-schulden", "lotti", "Wie viel Gewerbesteuer hat die Stadt 2024 eingenommen?",
      "haushalt/steuern", B_STEUERN,
      [Z(TAX, 2024, "Gewerbesteuer (-umlage)", jahr=2024, bez="Gewerbesteuer 2024")],
      route="/haushalt/schulden", notiz="Unpassende Seite.")
    F("hh-grundsteuer-lotti", "lotti", "Wie viel Grundsteuer nimmt die Stadt ein?",
      "haushalt/steuern", B_STEUERN,
      [Z(TAX, 2025, "Grundsteuer A+B", jahr=2025, bez="Grundsteuer 2025 (vorläufig)",
         oder=[ALT(TAX, 2024, "Grundsteuer A+B", jahr=2024)])],
      route="/haushalt/steuer")
    F("hh-est-anteil-lotti", "lotti", "Wie viel bekommt die Stadt aus der Einkommensteuer?",
      "haushalt/steuern", B_STEUERN,
      [Z(TAX, 2025, "Einkommensteueranteil", jahr=2025, bez="Einkommensteueranteil 2025",
         oder=[ALT(TAX, 2024, "Einkommensteueranteil", jahr=2024)])],
      route="/haushalt/einnahmen")
    F("hh-steuer-vergnuegung-lotti", "lotti:/haushalt/einnahmen", "Wie viel bringt die Vergnügungssteuer der Stadt ein?",
      "haushalt/steuern", B_STEUERN,
      [Z(TAX, 2025, "Vergnügungssteuer", jahr=2025, bez="Vergnügungssteuer 2025",
         oder=[ALT(TAX, 2024, "Vergnügungssteuer", jahr=2024)])])
    F("hh-hebesatz-grundb-lotti", "lotti", "Wie hoch ist der Hebesatz der Grundsteuer B?",
      "haushalt/steuern", B_HEBESATZ,
      [Z(RATE, 2025, "Grundsteuer B", jahr=2025, einheit="%", bez="Hebesatz Grundsteuer B")],
      route="/haushalt/steuer",
      verboten=[V(RATE, 2015, "Grundsteuer B", grund="alter Hebesatz als aktueller", als_jahr=2025,
                  einheit="%")])
    F("hh-hebesatz-gewst-lotti", "lotti:/haushalt/steuer", "Wie hoch ist der Gewerbesteuer-Hebesatz in Oldenburg?",
      "haushalt/steuern", B_HEBESATZ,
      [Z(RATE, 2025, "Gewerbesteuer", jahr=2025, einheit="%", bez="Hebesatz Gewerbesteuer")])
    F("hh-hebesatz-entwicklung-rat", "rat",
      "Wie haben sich die Hebesätze der Grundsteuer in Oldenburg entwickelt?",
      "haushalt/steuern", B_HEBESATZ,
      [Z(RATE, 2025, "Grundsteuer B", jahr=2025, einheit="%", bez="Hebesatz B ab 2025"),
       Z(RATE, 2015, "Grundsteuer B", jahr=2015, einheit="%", bez="Hebesatz B ab 2015"),
       Z(RATE, 2025, "Grundsteuer A", jahr=2025, einheit="%", bez="Hebesatz A ab 2025",
         pflicht=False)],
      notiz="Faktencheck rat[3].")
    F("hh-steuern-einfluss-lotti", "lotti", "Wie viel Einfluss hat der Rat auf die Steuern?",
      "haushalt/steuern", B_SEITE,
      [T([["Hebesatz", "Hebesätze"], ["Gewerbesteuer", "Grundsteuer"]],
         "Seitenwissen /haushalt/einnahmen; council_tax_rates")],
      route="/haushalt/einnahmen", notiz="Startfrage der Seite.")
    F("hh-schluesselzuweisung-rat", "rat", "Wie viel Schlüsselzuweisungen bekommt Oldenburg vom Land?",
      "haushalt/steuern", B_STEUERKRAFT,
      [Z("SELECT allocations FROM council_tax_capacity WHERE year = ?", 2026, jahr=2026,
         bez="Schlüsselzuweisungen 2026")],
      verboten=[V("SELECT allocations FROM council_tax_capacity WHERE year = ?", 2025,
                  grund="2025 als 2026", als_jahr=2026)])
    F("hh-gewst-betriebe-lotti", "lotti:/haushalt/steuer", "Wie viele Betriebe zahlen in Oldenburg Gewerbesteuer?",
      "haushalt/steuern", B_GEWST_STAT,
      [Z("SELECT cases_positive FROM council_trade_tax_statistics WHERE city = 'Oldenburg' "
         "AND year = ?", 2021, jahr=2021, einheit="", bez="Steuerpflichtige mit positivem "
         "Messbetrag 2021",
         oder=[ALT("SELECT cases FROM council_trade_tax_statistics WHERE city = 'Oldenburg' "
                   "AND year = ?", 2021, jahr=2021)])],
      notiz="Die Statistik endet 2021 — die Antwort muss das Jahr nennen.")

    # ------------------------------------------------------------------ #
    # Gebühren
    # ------------------------------------------------------------------ #
    F("hh-gebuehr-grund-2026-lotti", "lotti", "Wie hoch ist die Grundgebühr für den Müll 2026?",
      "haushalt/gebuehren", B_GEBUEHRSAETZE,
      [Z(FEE, 2026, "base_fee", jahr=2026, bez="Grundgebühr Abfall 2026")],
      route="/haushalt/einnahmen",
      verboten=[V(FEE, 2025, "base_fee", grund="Grundgebühr 2025 als 2026", als_jahr=2026)])
    F("hh-gebuehr-strasse-rat", "rat", "Was kostet die Straßenreinigung pro Meter?",
      "haushalt/gebuehren", B_GEBUEHRSAETZE,
      [Z(FEE, 2026, "street_cleaning_per_metre", jahr=2026, bez="Straßenreinigung je Meter 2026")],
      verboten=[V(FEE, 2025, "street_cleaning_per_metre", grund="Satz 2025 als aktueller",
                  als_jahr=2026)])
    F("hh-gebuehr-liter-lotti", "lotti:/haushalt/einnahmen", "Wie hoch ist die Litergebühr für die Mülltonne?",
      "haushalt/gebuehren", B_GEBUEHRSAETZE,
      [Z(FEE, 2026, "per_litre_fee", jahr=2026, bez="Allgemeine Litergebühr 2026")])
    F("hh-gebuehr-abfall-kosten-rat", "rat",
      "Welche Kosten muss die Abfallgebühr 2026 decken?",
      "haushalt/gebuehren", B_GEBUEHREN,
      [Z("SELECT costs_to_cover FROM council_fees WHERE year = ? AND area = 'waste_collection'",
         2026, jahr=2026, bez="Abfallsammlung: zu deckende Kosten 2026"),
       Z("SELECT costs_to_cover FROM council_fees WHERE year = ? AND area = 'waste_treatment'",
         2026, jahr=2026, bez="Abfallbehandlung: zu deckende Kosten 2026", pflicht=False)])
    F("hh-gebuehr-einnahmen-lotti", "lotti", "Wie viel Gebühren nimmt die Stadt ein?",
      "haushalt/gebuehren", B_ANSATZ,
      [Z("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? AND year = ? "
         "AND nr = 5", 2026, 2026, jahr=2026, bez="öffentlich-rechtliche Entgelte Plan 2026",
         oder=[ALT(IST.format("result"), 2024, 5, jahr=2024)])],
      route="/haushalt/einnahmen", notiz="Startfrage der Seite.")
    F("hh-gebuehr-strasse-auf-personal", "lotti",
      "Wie stark ist die Straßenreinigungsgebühr 2026 gestiegen?",
      "haushalt/gebuehren", B_GEBUEHRSAETZE,
      [Z(FEE, 2026, "street_cleaning_per_metre", jahr=2026, bez="Satz 2026"),
       Z(FEE, 2025, "street_cleaning_per_metre", jahr=2025, bez="Satz 2025")],
      route="/haushalt/personal", notiz="Unpassende Seite.")

    # ------------------------------------------------------------------ #
    # Stellenplan
    # ------------------------------------------------------------------ #
    def stellen(spalte: str, jahr: int) -> list[float]:
        return [wert(STELLEN_TEIL.format(spalte), jahr, "Summe Laufbahngruppe 1")
                + wert(STELLEN_TEIL.format(spalte), jahr, "Summe Laufbahngruppe 2")
                + wert(STELLEN_TEIL.format(spalte), jahr, "Summe Beamte auf Zeit"),
                wert(STELLEN_TEIL.format(spalte), jahr, "Summe Beschäftigte TVöD")]

    def stellen_gold(spalte: str, jahr: int, bez: str, toleranz: float | None = None) -> dict:
        teile = [round(t, 2) for t in stellen(spalte, jahr)]
        g: dict[str, Any] = {
            "art": "zahl", "wert": round(sum(teile), 2), "einheit": "Stellen",
            "bezeichnung": bez, "teile": teile, "toleranz": toleranz or 0.005,
            "quelle": f"council_staff_plan budget_year={jahr}, kind='group', Spalte {spalte}: "
                      "Laufbahngruppe 1 + 2 + Beamte auf Zeit (Beamte) und Beschäftigte TVöD"}
        # Besetzt/unbesetzt sind ein Stichtag im Vorjahr (30.06.), der
        # Stellenplan trägt das Haushaltsjahr — beide Jahre sind richtig.
        if spalte == "positions_planned":
            g["jahr"] = jahr
        return g

    F("hh-stellen-gesamt-lotti", "lotti", "Wie viele Stellen plant die Stadt insgesamt?",
      "haushalt/stellenplan", B_STELLEN,
      [stellen_gold("positions_planned", 2026, "Stellen im Stellenplan 2026")],
      route="/haushalt/personal", notiz="Startfrage der Seite.")
    F("hh-stellen-unbesetzt-lotti", "lotti", "Wie viele Stellen sind unbesetzt?",
      "haushalt/stellenplan", B_STELLEN,
      [stellen_gold("vacant", 2026, "unbesetzte Stellen (Stand 30.06.2025)", 0.01)],
      route="/haushalt/personal", notiz="Startfrage der Seite.")
    F("hh-stellen-besetzt-rat", "rat", "Wie viele Stellen der Stadtverwaltung sind besetzt?",
      "haushalt/stellenplan", B_STELLEN,
      [stellen_gold("filled", 2026, "besetzte Stellen (Stand 30.06.2025)", 0.01)])
    F("hh-stellen-2025-lotti", "lotti:/haushalt/personal", "Wie viele Stellen hatte der Stellenplan 2025?",
      "haushalt/stellenplan", B_STELLEN,
      [stellen_gold("positions_planned", 2025, "Stellen im Stellenplan 2025")],
      notiz="Jahres-Falle: nicht der jüngste Stellenplan.")
    F("hh-stellen-auf-haushalt", "lotti", "Wie viele Leute arbeiten bei der Stadt?",
      "haushalt/stellenplan", B_STELLEN,
      [stellen_gold("filled", 2026, "besetzte Stellen (Stand 30.06.2025)", 0.01)],
      route="/haushalt")

    # ------------------------------------------------------------------ #
    # Haushaltssatzung
    # ------------------------------------------------------------------ #
    F("hh-satzung-vpe-lotti", "lotti:/haushalt/mitreden",
      "Wie hoch sind die Verpflichtungsermächtigungen in der Haushaltssatzung 2026?",
      "haushalt/satzung", B_SATZUNG,
      [Z(BYLAW.format("commitment_authorizations"), 2026, jahr=2026,
         bez="Verpflichtungsermächtigungen 2026")])
    F("hh-satzung-beschluss-rat", "rat", "Wann hat der Rat den Haushalt 2026 beschlossen?",
      "haushalt/satzung", B_SATZUNG,
      [T([["09.02.2026", "9.2.2026", "9. Februar 2026", "09. Februar 2026", "2026-02-09"]],
         "council_decisions id=8286 (Rat, council_sessions.session_date 2026-02-09, "
         "outcome accepted)")],
      notiz="Datenbefund: council_budget_bylaw.session_date sagt 15.12.2025 — an dem Tag "
            "wurde vertagt (council_decisions 9283, postponed); beschlossen hat der Rat am "
            "09.02.2026.")
    F("hh-satzung-ergebnis-lotti", "lotti",
      "Welche Summe an Erträgen und Aufwendungen setzt die Haushaltssatzung 2026 fest?",
      "haushalt/satzung", B_SATZUNG,
      [Z(BYLAW.format("ordinary_revenues"), 2026, jahr=2026, bez="Satzung: ordentliche Erträge"),
       Z(BYLAW.format("ordinary_expenses"), 2026, jahr=2026, bez="Satzung: ordentliche Aufwendungen")],
      route="/haushalt/mitreden")

    # ------------------------------------------------------------------ #
    # Städtevergleich
    # ------------------------------------------------------------------ #
    F("hh-vergleich-steuerkraft-lotti", "lotti", "Wie steht Oldenburg bei der Steuerkraft da?",
      "haushalt/vergleich", B_VERGLEICH,
      [Z(CITY, 2026, "Oldenburg", "steuerkraftmesszahl", jahr=2026, faktor=1000,
         bez="Steuerkraftmesszahl Oldenburg 2026"),
       T(["Braunschweig"], "council_city_comparison 2026: Braunschweig vor Oldenburg")],
      route="/haushalt/vergleich", notiz="Startfrage der Seite.")
    F("hh-vergleich-gewst-hebesatz-rat", "rat",
      "Hat Oldenburg einen höheren Gewerbesteuer-Hebesatz als Osnabrück?",
      "haushalt/vergleich", B_VERGLEICH,
      [Z(CITY, 2025, "Oldenburg", "hebesatz_gewerbesteuer", jahr=2025, einheit="%",
         bez="Hebesatz Gewerbesteuer Oldenburg"),
       Z(CITY, 2025, "Osnabrück", "hebesatz_gewerbesteuer", jahr=2025, einheit="%",
         bez="Hebesatz Gewerbesteuer Osnabrück")])
    F("hh-vergleich-einnahmekraft-lotti", "lotti:/haushalt/vergleich",
      "Wie hoch ist die Steuereinnahmekraft je Einwohner in Oldenburg im Vergleich zu Wolfsburg?",
      "haushalt/vergleich", B_VERGLEICH,
      [Z(CITY, 2025, "Oldenburg", "steuereinnahmekraft_je_ew", jahr=2025,
         bez="Steuereinnahmekraft je EW Oldenburg"),
       Z(CITY, 2025, "Wolfsburg", "steuereinnahmekraft_je_ew", jahr=2025,
         bez="Steuereinnahmekraft je EW Wolfsburg")])
    F("hh-vergleich-grundb-lotti", "lotti", "In welcher Stadt ist die Grundsteuer B am höchsten?",
      "haushalt/vergleich", B_VERGLEICH,
      [T(["Braunschweig"], "council_city_comparison 2025 hebesatz_grundsteuer_b: Maximum"),
       Z(CITY, 2025, "Braunschweig", "hebesatz_grundsteuer_b", jahr=2025, einheit="%",
         bez="Hebesatz B Braunschweig")],
      route="/haushalt/vergleich")
    F("hh-vergleich-grenzen-lotti", "lotti", "Warum hat ein Ausgabenvergleich Grenzen?",
      "haushalt/vergleich", B_SEITE,
      [T([["Aufgaben", "aufgaben"]], "Seitenwissen /haushalt/vergleich")],
      route="/haushalt/vergleich", notiz="Startfrage der Seite.")

    # ------------------------------------------------------------------ #
    # Mitreden: Änderungslisten
    # ------------------------------------------------------------------ #
    F("hh-antraege-lotti", "lotti", "Welche Anträge gab es zum Haushalt?",
      "haushalt/mitreden", B_ANTRAEGE,
      [T([["SPD"], ["CDU"], ["Grüne"]],
         "Änderungslisten zum Haushalt 2026 (Rat 09.02.2026): Anträge von SPD, CDU, FDP, "
         "Grünen, BSW, Für Oldenburg — council_budget_amendments_totals list_key='fc_decided', "
         "Sitzungs-Änderungslisten")],
      route="/haushalt/mitreden", notiz="Startfrage der Seite.")
    F("hh-aenderungsliste-2026-rat", "rat",
      "Wie hat die erste Änderungsliste der Verwaltung das Ergebnis 2026 verändert?",
      "haushalt/mitreden", B_ANTRAEGE,
      [Z("SELECT balance FROM council_budget_amendments_totals WHERE budget_year = ? AND "
         "list_key = 'fc_decided' AND year = ? AND label LIKE 'Änderungsliste v. 24.11.2025%'",
         2026, 2026, jahr=2026, bez="Änderungsliste Verw. I: Verbesserung 2026")])
    F("hh-haushalt-entwurf-final-rat", "rat",
      "Um wie viel hat sich das Defizit 2026 zwischen Verwaltungsentwurf und Beschluss verändert?",
      "haushalt/mitreden", B_ANTRAEGE,
      [Z("SELECT balance FROM council_budget_amendments_totals WHERE budget_year = ? AND "
         "list_key = 'fc_decided' AND year = ? AND kind = 'draft'", 2026, 2026, jahr=2026,
         bez="Fehlbetrag Verwaltungsentwurf 2026"),
       Z("SELECT balance FROM council_budget_amendments_totals WHERE budget_year = ? AND "
         "list_key = 'fc_decided' AND year = ? AND kind = 'final_total'", 2026, 2026, jahr=2026,
         bez="Fehlbetrag nach Beschluss 2026")])

    # ------------------------------------------------------------------ #
    # Produkte, Pflicht
    # ------------------------------------------------------------------ #
    F("hh-produkt-feuerwehr-lotti", "lotti", "Was kostet die Feuerwehr im Jahr?",
      "haushalt/produkte", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Brand- und Katastrophenschutz", jahr=2026,
         bez="Brand- und Katastrophenschutz Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Brand- und Katastrophenschutz", jahr=2026)])],
      route="/haushalt/produkte", notiz="Startfrage der Seite.")
    F("hh-produkt-klimaschutz-rat", "rat", "Was kostet der Klimaschutz die Stadt im Jahr?",
      "haushalt/produkte", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Klimaschutz", jahr=2026, bez="Klimaschutz Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Klimaschutz", jahr=2026)])])
    F("hh-produkt-kita-rat", "rat", "Was kostet die Kinderbetreuung in Kitas die Stadt?",
      "haushalt/produkte", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Kindertagesbetreuung", jahr=2026,
         bez="Kindertagesbetreuung Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Kindertagesbetreuung", jahr=2026)])])
    F("hh-produkt-sport-lotti", "lotti:/haushalt/produkte", "Wie viel gibt die Stadt für Sportförderung aus?",
      "haushalt/produkte", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Sportförderung", jahr=2026,
         bez="Sportförderung Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Sportförderung", jahr=2026)])])
    F("hh-produkt-archiv-lotti", "lotti", "Was kostet das Stadtarchiv?",
      "haushalt/produkte", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Archivierung", jahr=2026, bez="Archivierung Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Archivierung", jahr=2026)])],
      route="/haushalt/produkte")
    F("hh-produkt-feuerwehr-auf-schulden", "lotti", "Was kostet die Feuerwehr im Jahr?",
      "haushalt/produkte", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Brand- und Katastrophenschutz", jahr=2026,
         bez="Brand- und Katastrophenschutz Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Brand- und Katastrophenschutz", jahr=2026)])],
      route="/haushalt/schulden", notiz="Unpassende Seite.")
    F("hh-pflicht-lotti", "lotti", "Was muss die Stadt gesetzlich bezahlen?",
      "haushalt/produkte", B_PRODUKTE,
      [T([["SGB", "Sozialgesetzbuch"], ["Eingliederungshilfe", "Grundsicherung",
                                        "Kindertagesbetreuung", "Jugendhilfe"]],
         "council_products year=2026 controllability='low' (größte: Kindertagesbetreuung, "
         "Grundsicherung SGB II, Eingliederungshilfe SGB IX)")],
      route="/haushalt/pflicht", notiz="Startfrage der Seite.")
    F("hh-spielraum-rat", "rat", "Wo hat der Rat beim Haushalt echten Entscheidungsspielraum?",
      "haushalt/produkte", B_PRODUKTE,
      [T([["Kultur", "Sportförderung", "Klimaschutz", "Wirtschaftsförderung"]],
         "council_products year=2026 controllability='high'")])

    # ------------------------------------------------------------------ #
    # Prüfung, Kennzahlen, Bilanz, Nachbewilligungen, Spenden
    # ------------------------------------------------------------------ #
    F("hh-kennzahl-ekq-lotti", "lotti", "Wie hoch ist die Eigenkapitalquote der Stadt?",
      "haushalt/pruefung", B_KENNZAHLEN,
      [Z(KENNZ, 2024, 2024, "eigenkapitalquote_1", jahr=2024, einheit="%",
         bez="Eigenkapitalquote I 2024",
         oder=[ALT(KENNZ, 2024, 2024, "eigenkapitalquote_2", jahr=2024),
               ALT(KENNZ, 2025, 2025, "eigenkapitalquote_1", jahr=2025),
               ALT(KENNZ, 2025, 2025, "eigenkapitalquote_2", jahr=2025)])],
      route="/haushalt/pruefung",
      verboten=[V(KENNZ, 2024, 2023, "eigenkapitalquote_1", grund="2023 als 2024", als_jahr=2024,
                  einheit="%")])
    F("hh-kennzahl-personal-lotti", "lotti:/haushalt/pruefung", "Wie hoch ist die Personalintensität der Stadt Oldenburg?",
      "haushalt/pruefung", B_KENNZAHLEN,
      [Z(KENNZ, 2024, 2024, "personalintensitaet", jahr=2024, einheit="%",
         bez="Personalintensität 2024",
         oder=[ALT(KENNZ, 2025, 2025, "personalintensitaet", jahr=2025)])])
    F("hh-vermoegen-lotti", "lotti", "Wie viel Vermögen hat die Stadt pro Einwohner?",
      "haushalt/pruefung", B_KENNZAHLEN,
      [Z(KENNZ, 2024, 2024, "vermoegen_je_einwohner", jahr=2024, bez="Vermögen je EW 2024",
         oder=[ALT(KENNZ, 2025, 2025, "vermoegen_je_einwohner", jahr=2025)])],
      route="/haushalt/pruefung")
    F("hh-rpa-lotti", "lotti", "Was hat das Rechnungsprüfungsamt beanstandet?",
      "haushalt/pruefung", B_PRUEFUNG,
      [T([["Vier-Augen", "Funktionstrennung", "Inventur", "Verpflichtungsermächtigung",
           "Haushaltsreste", "außerplanmäßig", "überplanmäßig"]],
         "council_audit_reports year=2024 mark in ('B','WB')")],
      route="/haushalt/pruefung", notiz="Startfrage der Seite.")
    F("hh-rpa-rat", "rat",
      "Was hat das Rechnungsprüfungsamt beim Jahresabschluss 2024 beanstandet?",
      "haushalt/pruefung", B_PRUEFUNG,
      [T([["Vier-Augen", "Funktionstrennung", "Inventur", "Verpflichtungsermächtigung",
           "Haushaltsreste", "außerplanmäßig", "überplanmäßig"]],
         "council_audit_reports year=2024 mark in ('B','WB')")])
    F("hh-bilanz-lotti", "lotti", "Was besitzt die Stadt laut Bilanz?",
      "haushalt/pruefung", B_BILANZ,
      [Z("SELECT value FROM council_balance_sheet WHERE year = ? AND role = 'net_position'", 2024,
         jahr=2024, bez="Nettoposition (Eigenkapital) 2024",
         oder=[ALT("SELECT value FROM council_balance_sheet WHERE year = ? AND "
                   "role = 'tangible_assets'", 2024, jahr=2024),
               ALT("SELECT value FROM council_balance_sheet WHERE year = ? AND "
                   "role = 'net_position'", 2025, jahr=2025),
               ALT("SELECT value FROM council_balance_sheet WHERE year = ? AND "
                   "role = 'tangible_assets'", 2025, jahr=2025)])],
      route="/haushalt/pruefung")
    F("hh-nachbewilligung-2025-rat", "rat",
      "Welche größte überplanmäßige Ausgabe hat der Rat 2025 nachbewilligt?",
      "haushalt/nachbewilligungen", B_NACHBEWILLIGUNG,
      [Z("SELECT amount FROM council_supplementary_approvals WHERE year = ? AND kind = 'approval' "
         "ORDER BY amount DESC LIMIT 1", 2025, jahr=2025,
         bez="größte über-/außerplanmäßige Bewilligung 2025 (Teilhaushalt 10)")])
    F("hh-spenden-2025-rat", "rat", "Wie viel Geld hat die Stadt 2025 an Spenden angenommen?",
      "haushalt/spenden", B_SPENDEN,
      [Z("SELECT SUM(amount) FROM council_donations WHERE year = ?", 2025, jahr=2025,
         bez="Spenden 2025 (Summe)", toleranz=0.01)])

    # ------------------------------------------------------------------ #
    # Die Daten geben es NICHT her
    # ------------------------------------------------------------------ #
    nd = "haushalt/nicht-in-daten"
    F("hh-nd-schulden-vergleich-lotti", "lotti", "Ist das viel im Vergleich zu anderen Städten?",
      nd, B_KEINE,
      [Z(CITY, 2026, "Oldenburg", "steuerkraftmesszahl", jahr=2026, faktor=1000, pflicht=False,
         bez="Steuerkraftmesszahl (nur zur Einordnung)", baustein=B_VERGLEICH)],
      route="/haushalt/schulden", in_daten=False,
      notiz="Faktencheck lotti[1]: Gemini beantwortete die Schuldenfrage mit der Steuerkraft. "
            "Schulden gibt es nur für Oldenburg (council_integrated_debt: 1 Zeile, ARS Oldenburg).")
    F("hh-nd-schulden-osnabrueck-rat", "rat", "Wie hoch sind die Schulden von Osnabrück?",
      nd, B_KEINE, [], in_daten=False)
    F("hh-nd-schulden-wolfsburg-rat", "rat",
      "Hat Oldenburg mehr Schulden pro Kopf als Wolfsburg?", nd, B_KEINE,
      [prokopf | {"pflicht": False}], in_daten=False)
    F("hh-nd-kita-vergleich-lotti", "lotti", "Gibt Oldenburg mehr für Kitas aus als Braunschweig?",
      nd, B_KEINE, [], route="/haushalt/vergleich", in_daten=False)
    F("hh-nd-defizit-delmenhorst-rat", "rat", "Wie hoch ist das Haushaltsdefizit von Delmenhorst?",
      nd, B_KEINE, [], in_daten=False)
    F("hh-nd-gewst-firma-rat", "rat", "Wie viel Gewerbesteuer zahlt die EWE in Oldenburg?",
      nd, B_KEINE, [], in_daten=False,
      notiz="Steuergeheimnis: einzelne Zahler stehen in keiner Quelle.")
    F("hh-nd-schulden-1990-lotti", "lotti", "Wie hoch waren die Schulden 1990?", nd, B_KEINE, [],
      route="/haushalt/schulden", in_daten=False,
      notiz="Die Reihe beginnt 1995 (council_debt MIN(year)).")
    F("hh-nd-gewst-2026-rat", "rat",
      "Wie viel Gewerbesteuer hat die Stadt 2026 bis jetzt tatsächlich eingenommen?", nd, B_KEINE,
      [], in_daten=False,
      notiz="council_taxes endet 2025; der Vollzugsbericht nennt keine Steuerarten.")
    F("hh-nd-hundesteuer-lotti", "lotti", "Wie viel bringt die Hundesteuer?", nd, B_KEINE,
      [Z(TAX, 2025, "sonstige Steuern", jahr=2025, pflicht=False,
         bez="sonstige Steuern 2025 (Hundesteuer nicht einzeln)", baustein=B_STEUERN)],
      route="/haushalt/einnahmen", in_daten=False,
      notiz="Die Hundesteuer steht nicht einzeln in council_taxes, nur „sonstige Steuern“.")
    F("hh-nd-stellen-2028-lotti", "lotti", "Wie viele Stellen will die Stadt 2028 schaffen?",
      nd, B_KEINE, [], route="/haushalt/personal", in_daten=False)
    F("hh-nd-abwasser-rat", "rat", "Wie hoch ist die Abwassergebühr in Oldenburg?", nd, B_KEINE, [],
      in_daten=False, notiz="council_fees/council_fee_rates kennen nur Abfall und Straßenreinigung.")
    F("hh-nd-ekq-2025-lotti", "lotti", "Wie hoch war die Eigenkapitalquote 2025?",
      "haushalt/pruefung", B_KENNZAHLEN,
      [Z(KENNZ, 2025, 2025, "eigenkapitalquote_1", jahr=2025, einheit="%",
         bez="Eigenkapitalquote I 2025",
         oder=[ALT(KENNZ, 2025, 2025, "eigenkapitalquote_2", jahr=2025)])],
      route="/haushalt/pruefung",
      verboten=[V(KENNZ, 2024, 2024, "eigenkapitalquote_1", grund="2024 als 2025", als_jahr=2025,
                  einheit="%")],
      notiz="Bis 24.09.2026 ein Fall ohne Antwort in den Daten; seitdem ist der "
            "Jahresabschluss 2025 im Bestand (ID bleibt für den Vergleich der Läufe).")
    F("hh-nd-schulden-2030-rat", "rat", "Wie hoch werden die Schulden der Stadt 2030 sein?",
      nd, B_KEINE, [], in_daten=False)
    F("hh-nd-zinsen-braunschweig-rat", "rat", "Wie viel Zinsen zahlt Braunschweig für seine Kredite?",
      nd, B_KEINE, [], in_daten=False)
    F("hh-nd-klinikum-gehaelter-lotti", "lotti",
      "Wie viel verdient die Geschäftsführung des Klinikums?", nd, B_KEINE, [],
      route="/haushalt/konzern", in_daten=False)
    laien()
    mehrstufig()
    mehrstufig_anschluss()
    mehrstufig_neue_reihen()
    return FAELLE


def laien() -> None:
    """Die 36 Laienfragen vom 24.09.2026 — wie sie im Fenster gestellt wurden.

    Tim: „Die meisten Leute stellen keine technisch perfekten Fragen …
    Trotzdem müssen wir gute Antworten geben.“ Kleinschreibung und Tippfehler
    („schulen pro einwohner“) sind Absicht. Jeder Fall läuft mit Überschrift
    und Bausteinen des echten Fensters (``fenster=True``).

    **Wertungsfragen** („Hat die Stadt genug Geld?“, „Ist das schlimm?“) haben
    als Gold den MASSSTAB — die Zahl, an der man es selbst einordnen kann.
    Eine ehrliche Absage besteht, wenn sie den Maßstab nennt; eine Absage
    ohne Zahl nicht. Reine Begriffsfragen („Was ist ein Haushalt?“) prüfen
    Wörter statt Zahlen.
    """
    k = "haushalt/laien"
    aufwand26 = Z(BUDGET_SUM.format("expenses"), 2026, jahr=2026, bez="Aufwendungen Plan 2026",
                  baustein=B_KERN)
    ertrag26 = Z(BUDGET_SUM.format("revenues"), 2026, jahr=2026, bez="Erträge Plan 2026",
                 baustein=B_KERN)
    haushalt26 = Z(BUDGET_SUM.format("expenses"), 2026, jahr=2026, bez="Aufwendungen Plan 2026",
                   baustein=B_KERN, oder=[ALT(BUDGET_SUM.format("revenues"), 2026, jahr=2026)])
    schulden25 = Z(DEBT.format("total"), 2025, jahr=2025, bez="Schuldenstand Kern + Eigenbetriebe",
                   baustein=B_SCHULDEN)
    ergebnis24 = Z(IST.format("result"), 2024, 21, jahr=2024, bez="ordentliches Ergebnis Ist 2024",
                   pflicht=False, baustein=B_IST)
    ansatz = ("SELECT amount FROM council_income_budget WHERE plan_budget_year = ? AND year = ? "
              "AND nr = ? AND kind = 'budget'")

    def L(nr: int, route: str, frage: str, baustein: str, gold: list[dict], **kw: Any) -> None:
        F(f"hh-laien-{nr:02d}", "lotti", frage, k, baustein, gold, route=route, fenster=True, **kw)

    L(1, "/haushalt", "wie viele schulden hat die stadt", B_SCHULDEN, [schulden25])
    L(2, "/haushalt", "was gibt die stadt eigentlich so aus", B_KERN,
      [aufwand26, Z(BUDGET_AREA.format("expenses"), 2026, "Soziales und Gesundheit", jahr=2026,
                    bez="größter Teilhaushalt", pflicht=False, baustein=B_KERN)],
      notiz="Befund A: bekam die Stadtplanung (7,4 Mio. €) über das Wort „Stadt“.")
    L(3, "/haushalt", "hat die stadt genug geld", B_KERN, [haushalt26, ergebnis24],
      notiz="Wertungsfrage: Maßstab = Aufwand/Ertrag des Plans.")
    L(4, "/haushalt", "wo kann die stadt sparen", B_PRODUKTE,
      [T([["Spielraum", "freiwillig"]], "council_products.controllability = 'high'")])
    L(5, "/haushalt", "warum ist die stadt pleite", B_KERN, [haushalt26, ergebnis24],
      notiz="Wertungsfrage mit falscher Voraussetzung; Maßstab = Plan und Abschluss.")
    L(6, "/haushalt", "wieviel geld hat oldenburg im jahr", B_KERN, [haushalt26],
      notiz="Befund A: 884 Mio. ohne Jahr und Quelle.")
    L(7, "/haushalt", "was kostet mich die stadt pro jahr", B_KERN,
      [aufwand26, Z("SELECT population FROM council_einwohner WHERE year = ?", 2025, jahr=2025,
                    einheit="", bez="Einwohner*innen Ende 2025", pflicht=False,
                    baustein="council/geld/population.py")],
      notiz="Die Pro-Kopf-Rechnung ist Sache der Einordnung, hier nicht Pflicht.")
    L(8, "/haushalt", "wofür geht das meiste geld drauf", B_PLAN,
      [Z(BUDGET_AREA.format("expenses"), 2026, "Soziales und Gesundheit", jahr=2026,
         bez="größter Teilhaushalt")])
    L(9, "/haushalt", "was ist ein haushalt überhaupt", B_GLOSSAR,
      [T([["Plan", "plant"], ["Einnahmen", "Erträge", "einnimmt"]], "Glossar/Seitenwissen")])
    L(10, "/haushalt", "kann sich die stadt das neue stadion leisten", B_ARCHIV,
      [Z("SELECT MAX(amount_eur) FROM council_decisions WHERE title LIKE '%Stadion%'",
         bez="Stadion Pauschalpreis netto (Beschluss)", baustein=B_ARCHIV),
       T([["Bürgschaft", "bürgt", "Ausfallbürgschaft"]], "Stadion-Beschlüsse", pflicht=False)],
      notiz="Befund A: kein Weg ins Archiv. Jetzt: projekt_ins_archiv → Frag den Rat.")
    L(11, "/haushalt/schulden", "ist das schlimm?", B_SCHULDEN, [schulden25])
    L(12, "/haushalt/schulden", "ist das viel oder wenig", B_SCHULDEN, [schulden25])
    L(13, "/haushalt/schulden", "wer muss das alles zurückzahlen", B_SCHULDEN,
      [T([["Eigenbetrieb", "Eigenbetriebe"]], "council_debt: Abgrenzung Tabelle 1108")])
    L(14, "/haushalt/schulden", "wann sind die schulden weg", B_SCHULDEN, [schulden25],
      notiz="Einen Tilgungsplan gibt es nicht; der Maßstab ist der Stand.")
    L(15, "/haushalt/schulden", "warum macht die stadt überhaupt schulden", B_SCHULDEN,
      [schulden25 | {"pflicht": False},
       T([["Kredit", "Kredite", "investier", "Investition"]], "Erklärung")])
    L(16, "/haushalt/schulden", "wie hoch sind die schulen pro einwohner", B_SCHULDEN,
      [Z(DEBT.format("per_capita"), 2025, jahr=2025, bez="Schulden je Einwohner*in")],
      notiz="Tippfehler „schulen“ gewollt. Befund C: 1.908 € gerundet zu „rund 1.900 €“.")
    L(17, "/haushalt/einnahmen", "woher hat die stadt ihr geld", B_KERN,
      [Z(ansatz, 2026, 2026, 1, jahr=2026, bez="Steuern und ähnliche Abgaben Ansatz 2026",
         baustein=B_ANSATZ, oder=[ALT(TAX, 2025, "total", jahr=2025)])],
      notiz="Befund A: keine Beträge, obwohl Steuern 2025 (387 Mio. €) im Bestand.")
    L(18, "/haushalt/einnahmen", "zahlen wir zu viele steuern", B_STEUERN,
      [Z(TAX, 2025, "total", jahr=2025, bez="Steuereinnahmen 2025", baustein=B_STEUERN,
         oder=[ALT(ansatz, 2026, 2026, 1, jahr=2026)])])
    L(19, "/haushalt/einnahmen", "bekommt die stadt geld vom land", B_ANSATZ,
      [Z(ansatz, 2026, 2026, 2, jahr=2026, bez="Zuwendungen und allg. Umlagen Ansatz 2026",
         oder=[ALT("SELECT allocations FROM council_tax_capacity WHERE year = ?", 2026,
                   jahr=2026)])],
      notiz="Befund A: „wie viel geht nicht hervor“.")
    L(20, "/haushalt/investitionen", "was wird gebaut", B_MASSNAHMEN,
      [T(["Kampfmittel"], "council_investment_measures year=2026: größte grand_total"),
       Z("SELECT grand_total FROM council_investment_measures WHERE year = ? AND "
         "level = 'measure' ORDER BY grand_total DESC LIMIT 1", 2026, jahr=2026,
         bez="größtes Vorhaben 2026 (Gesamtsumme)", pflicht=False)],
      notiz="Befund A: „einzelne Vorhaben stehen hier nicht“.")
    L(21, "/haushalt/investitionen", "wird was für schulen gemacht", B_MASSNAHMEN,
      [T([["Schule", "Schulen"]], "council_investment_measures: Schul-Posten")])
    L(22, "/haushalt/investitionen", "warum dauern die baustellen immer so lange", B_KEINE, [],
      in_daten=False, notiz="Gründe für Bauzeiten stehen in keiner Haushaltsquelle.")
    L(23, "/haushalt/pflicht", "was muss die stadt bezahlen und was nicht", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Kindertagesbetreuung", jahr=2026,
         bez="Kindertagesbetreuung Aufwand 2026", pflicht=False),
       T([["Spielraum", "Pflicht", "pflicht", "gesetzlich"]], "council_products.controllability")])
    L(24, "/haushalt/pflicht", "könnte man nicht einfach das theater streichen", B_PRODUKTE,
      [Z(PRODUKT.format("-result"), 2026, "Kultur- u. Künstlerförderung", jahr=2026,
         bez="Kultur- und Künstlerförderung Zuschussbedarf 2026",
         oder=[ALT(PRODUKT.format("expenses"), 2026, "Kultur- u. Künstlerförderung", jahr=2026)])],
      notiz="Befund A: „keine Angaben zu Kosten des Theaters“. Das Staatstheater trägt das "
            "Land; im Haushalt steht die Kulturförderung.")
    L(25, "/haushalt/produkte", "was kostet die feuerwehr", B_PRODUKTE,
      [Z(PRODUKT.format("expenses"), 2026, "Brand- und Katastrophenschutz", jahr=2026,
         bez="Brand- und Katastrophenschutz Aufwand 2026",
         oder=[ALT(PRODUKT.format("-result"), 2026, "Brand- und Katastrophenschutz",
                   jahr=2026)])])
    kita = Z(PRODUKT.format("expenses"), 2026, "Kindertagesbetreuung", jahr=2026,
             bez="Kindertagesbetreuung Aufwand 2026",
             oder=[ALT(PRODUKT.format("-result"), 2026, "Kindertagesbetreuung", jahr=2026)])
    L(26, "/haushalt/produkte", "wie viel geld geht in kitas", B_PRODUKTE, [kita])
    L(27, "/haushalt/personal", "wie viele leute arbeiten bei der stadt", B_STELLEN,
      [T([["Stellen"]], "council_staff_plan: Stellen, keine Köpfe")])
    L(28, "/haushalt/personal", "sind das nicht zu viele", B_STELLEN,
      [T([["Stellen"]], "council_staff_plan")],
      notiz="Wertungsfrage: Maßstab = der Stellenplan selbst.")
    L(29, "/haushalt/plan-ist", "hat die stadt mehr ausgegeben als geplant", B_IST,
      [Z(IST.format("result"), 2024, 20, jahr=2024, bez="Aufwendungen Ist 2024",
         oder=[ALT(IST.format("result"), 2025, 20, jahr=2025)]),
       Z(IST.format("budgeted"), 2024, 20, jahr=2024, bez="Aufwendungen Ansatz 2024",
         oder=[ALT(IST.format("budgeted"), 2025, 20, jahr=2025)])])
    L(30, "/haushalt/konzern", "was sind eigenbetriebe", B_WIRTSCHAFTSPLAN,
      [T([["eigene", "eigenen", "eigener", "eigenem"],
          ["Wirtschaftsplan", "Buchführung", "Jahresplan", "getrennt"]], "Glossar/Seitenwissen")])
    L(31, "/haushalt/konzern", "verdient die stadt mit den bädern geld", B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "bbgo", 2026, jahr=2026, bez="BBGO Ergebnis Plan 2026",
         betrag=True)],
      notiz="Befund A: „keine Angaben“ — „Bädern“ traf das Muster für „Bäder“ nicht.")
    L(32, "/haushalt/vergleich", "sind wir ärmer als osnabrück", B_VERGLEICH,
      [Z(CITY, 2026, "Oldenburg", "steuerkraftmesszahl", jahr=2026, faktor=1000,
         bez="Steuerkraftmesszahl Oldenburg")])
    L(33, "/haushalt/steuer", "warum ist die grundsteuer so hoch", B_HEBESATZ,
      [Z(RATE, 2025, "Grundsteuer B", jahr=2025, einheit="%", bez="Hebesatz Grundsteuer B",
         oder=[ALT(TAX, 2025, "Grundsteuer A+B", jahr=2025)])])
    L(34, "/haushalt/mitreden", "kann ich mitbestimmen wofür das geld ausgegeben wird",
      B_SEITE, [T([["Rat", "Fraktion", "Fraktionen", "Antrag", "Anträge"]], "Seitenwissen")])
    L(35, "/haushalt", "stimmt es dass für kitas kein geld mehr da ist", B_PRODUKTE, [kita],
      notiz="Befund A: nur „Jugend und Familie 169 Mio.“, die Kindertagesbetreuung fehlte.")
    L(36, "/haushalt", "was bedeutet defizit", B_GLOSSAR,
      [T([["mehr"], ["aus", "Ausgaben", "Aufwendungen"]], "Glossar"),
       aufwand26 | {"pflicht": False}, ertrag26 | {"pflicht": False}],
      notiz="Befund B: richtig, aber ohne Oldenburger Zahl.")



def mehrstufig() -> None:
    """30 Fragen, für die EIN vorbereiteter Kontext nicht reicht (25.09.2026).

    Tim: „Ob eine Schwäche von Lotti nicht vielleicht ist, dass sie nicht
    agentisch auf den Daten handeln kann — sie kriegt den Kontext und muss
    direkt daraus antworten.“ Die übrigen Fälle sind an der Vorauswahl
    ausgerichtet; diese hier verlangen, was die Vorauswahl nicht vorhersieht:

    - **zeitreihe:** eine Entwicklung über mehr Jahre, als ein Baustein zeigt
      (der Schulden-Baustein nennt das jüngste Jahr, das Vorjahr und den
      Höchstwert — nicht 2010);
    - **seitenwechsel:** die Antwort steht auf einer ANDEREN Haushaltsseite
      als der, auf der gefragt wird;
    - **rechnen:** ein Anteil oder eine Veränderung, die in keinem Dokument
      steht (Lotti darf nicht selbst rechnen — ohne Rechenweg ist die Zahl
      „erfunden“, und genau das soll der Fall zeigen);
    - **kombination:** zwei Datenarten zusammen (Plan und Ist, zwei Städte,
      Haushalt und Ratsbeschluss).

    Zwei Fälle ohne Antwort in den Daten halten fest, dass mehr Nachschlagen
    nicht zu mehr Erfinden führt.
    """
    k = "haushalt/mehrstufig"
    pct = ("SELECT 100.0 * ({}) / ({})")
    kita = "SELECT expenses FROM council_products WHERE year = ? AND product_name = 'Kindertagesbetreuung'"
    brand = ("SELECT expenses FROM council_products WHERE year = ? "
             "AND product_name = 'Brand- und Katastrophenschutz'")
    stellen = ("SELECT positions_planned FROM council_staff_plan WHERE budget_year = ? "
               "AND part = ? AND kind = 'total' AND label = 'Summe'")
    gewst = "SELECT amount FROM council_taxes WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'"
    personal = IST.format("result")
    area = BUDGET_AREA.format("expenses")
    inv_plan = ("SELECT outflows FROM council_investments WHERE year = ? "
                "AND label = 'Finanzhaushalt Gesamtinvestitionen'")
    steuerplan = "SELECT {} FROM council_tax_plan WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'"

    # --- zeitreihe ---------------------------------------------------------
    F("hh-mehr-schulden-seit-2010", "lotti:/haushalt/schulden",
      "wie haben sich die schulden seit 2010 entwickelt", f"{k}/zeitreihe", B_SCHULDEN,
      [Z(DEBT.format("total"), 2010, jahr=2010, bez="Schuldenstand 2010"),
       Z(DEBT.format("total"), 2025, jahr=2025, bez="Schuldenstand 2025")], fenster=True,
      notiz="Der Schulden-Baustein zeigt jüngstes Jahr, Vorjahr, Höchstwert — 2010 nicht.")
    F("hh-mehr-schulden-2015-heute", "lotti:/haushalt/schulden",
      "waren die schulden 2015 höher oder niedriger als heute", f"{k}/zeitreihe", B_SCHULDEN,
      [Z(DEBT.format("total"), 2015, jahr=2015, bez="Schuldenstand 2015"),
       Z(DEBT.format("total"), 2025, jahr=2025, bez="Schuldenstand 2025")], fenster=True)
    F("hh-mehr-gewst-zehn-jahre", "lotti:/haushalt/einnahmen",
      "wie viel mehr gewerbesteuer nimmt die stadt heute ein als vor zehn jahren",
      f"{k}/zeitreihe", B_STEUERN,
      [Z(gewst, 2015, jahr=2015, bez="Gewerbesteuer 2015"),
       Z(gewst, 2025, jahr=2025, bez="Gewerbesteuer 2025")], fenster=True)
    F("hh-mehr-kita-seit-2020", "lotti:/haushalt/produkte",
      "wie haben sich die kita-kosten seit 2020 entwickelt", f"{k}/zeitreihe", B_PRODUKTE,
      [Z(kita, 2020, jahr=2020, bez="Kindertagesbetreuung Aufwand Plan 2020"),
       Z(kita, 2026, jahr=2026, bez="Kindertagesbetreuung Aufwand Plan 2026")], fenster=True)
    F("hh-mehr-stellen-seit-2023", "lotti:/haushalt/personal",
      "hat die stadt heute mehr stellen als 2023", f"{k}/zeitreihe", B_STELLEN,
      [Z(stellen, 2023, "B", jahr=2023, einheit="", bez="Stellen Teil B Plan 2023"),
       Z(stellen, 2026, "B", jahr=2026, einheit="", bez="Stellen Teil B Plan 2026")],
      fenster=True, notiz="Teil A und B nie addieren (die Seite sagt das ausdrücklich).")
    F("hh-mehr-personalkosten", "lotti:/haushalt/plan-ist",
      "sind die personalkosten in den letzten jahren gestiegen", f"{k}/zeitreihe", B_IST,
      [Z(personal, 2019, 13, jahr=2019, bez="Personalaufwendungen Ist 2019",
         # „In den letzten Jahren“ legt kein Startjahr fest; 2020 ist so
         # richtig wie 2019 (Nachprüfung 24.09.2026).
         oder=[ALT(personal, 2020, 13, jahr=2020), ALT(personal, 2021, 13, jahr=2021)]),
       Z(personal, 2024, 13, jahr=2024, bez="Personalaufwendungen Ist 2024")], fenster=True)
    F("hh-mehr-feuerwehr-2020", "lotti:/haushalt/produkte",
      "was kostet die feuerwehr heute im vergleich zu 2020", f"{k}/zeitreihe", B_PRODUKTE,
      [Z(brand, 2020, jahr=2020, bez="Brand- und Katastrophenschutz Plan 2020"),
       Z(brand, 2026, jahr=2026, bez="Brand- und Katastrophenschutz Plan 2026")], fenster=True)
    F("hh-mehr-hebesatz-2002", "lotti:/haushalt/steuer",
      "wie hat sich der gewerbesteuer-hebesatz seit 2002 verändert", f"{k}/zeitreihe", B_HEBESATZ,
      [Z(RATE, 2002, "Gewerbesteuer", jahr=2002, einheit="%", bez="Hebesatz 2002"),
       # Der Satz gilt seit 2015 unverändert — „seit 2015 439 %“ nennt den
       # heutigen Satz richtig (Nachprüfung 24.09.2026).
       Z(RATE, 2025, "Gewerbesteuer", jahr=2025, einheit="%", bez="Hebesatz 2025",
         oder=[ALT(RATE, 2015, "Gewerbesteuer", jahr=2015)])],
      fenster=True)

    # --- seitenwechsel -----------------------------------------------------
    F("hh-mehr-invest-auf-schulden", "lotti:/haushalt/schulden",
      "wie viel hat die stadt 2024 tatsächlich investiert", f"{k}/seitenwechsel", B_INVEST_IST,
      [Z(INV_IST, 2024, jahr=2024, bez="Investitionsauszahlungen Ist 2024")], fenster=True)
    F("hh-mehr-gewst-auf-invest", "lotti:/haushalt/investitionen",
      "wie viel gewerbesteuer hat die stadt 2025 eingenommen", f"{k}/seitenwechsel", B_STEUERN,
      [Z(gewst, 2025, jahr=2025, bez="Gewerbesteuer 2025")], fenster=True)
    F("hh-mehr-prokopf-auf-vergleich", "lotti:/haushalt/vergleich",
      "wie hoch sind oldenburgs schulden pro einwohner", f"{k}/seitenwechsel", B_SCHULDEN,
      [Z(DEBT.format("per_capita"), 2025, jahr=2025, bez="Schulden je Einwohner*in 2025")],
      fenster=True)
    F("hh-mehr-kita-auf-steuer", "lotti:/haushalt/steuer",
      "was kostet die kinderbetreuung die stadt", f"{k}/seitenwechsel", B_PRODUKTE,
      [Z(kita, 2026, jahr=2026, bez="Kindertagesbetreuung Aufwand Plan 2026")], fenster=True)
    F("hh-mehr-stellen-auf-konzern", "lotti:/haushalt/konzern",
      "wie viele stellen hat die stadtverwaltung", f"{k}/seitenwechsel", B_STELLEN,
      [Z(stellen, 2026, "B", jahr=2026, einheit="", bez="Stellen Teil B Plan 2026"),
       Z(stellen, 2026, "A", jahr=2026, einheit="", bez="Stellen Teil A Plan 2026")],
      fenster=True)
    F("hh-mehr-schulden-auf-personal", "lotti:/haushalt/personal",
      "wie hoch ist der schuldenstand der stadt", f"{k}/seitenwechsel", B_SCHULDEN,
      [Z(DEBT.format("total"), 2025, jahr=2025, bez="Schuldenstand 2025")], fenster=True)

    # --- rechnen -----------------------------------------------------------
    F("hh-mehr-anteil-soziales", "lotti:/haushalt",
      "welcher anteil der ausgaben geht in soziales und gesundheit", f"{k}/rechnen", B_PLAN,
      [Z(area, 2026, "Soziales und Gesundheit", jahr=2026, bez="Soziales und Gesundheit 2026"),
       Z(pct.format(area, BUDGET_SUM.format("expenses")), 2026, "Soziales und Gesundheit", 2026,
         jahr=2026, einheit="%", toleranz=0.03, bez="Anteil an den Aufwendungen 2026")],
      fenster=True)
    F("hh-mehr-anteil-gewst", "lotti:/haushalt/einnahmen",
      "wie viel prozent der steuereinnahmen kommen aus der gewerbesteuer", f"{k}/rechnen",
      B_STEUERN,
      [Z(pct.format(gewst, TAX), 2025, 2025, "total", jahr=2025, einheit="%", toleranz=0.03,
         bez="Anteil Gewerbesteuer an den Steuern 2025")], fenster=True)
    F("hh-mehr-schulden-prozent-2020", "lotti:/haushalt/schulden",
      "um wie viel prozent sind die schulden seit 2020 gestiegen", f"{k}/rechnen", B_SCHULDEN,
      [Z(DEBT.format("total"), 2020, jahr=2020, bez="Schuldenstand 2020"),
       Z("SELECT 100.0 * ((SELECT total FROM council_debt WHERE year = ?) / "
         "(SELECT total FROM council_debt WHERE year = ?) - 1)", 2025, 2020,
         einheit="%", toleranz=0.04, bez="Anstieg 2020→2025")], fenster=True)
    F("hh-mehr-gewst-ueber-plan", "lotti:/haushalt/plan-ist",
      "wie viel mehr gewerbesteuer als geplant hat die stadt 2024 bekommen", f"{k}/rechnen",
      B_STEUERPLAN,
      [Z(steuerplan.format("plan"), 2024, jahr=2024, bez="Gewerbesteuer Plan 2024"),
       Z(steuerplan.format("actual"), 2024, jahr=2024, bez="Gewerbesteuer Ist 2024"),
       Z(f"SELECT ({steuerplan.format('actual')}) - ({steuerplan.format('plan')})", 2024, 2024,
         jahr=2024, bez="Mehreinnahme 2024", toleranz=0.02, pflicht=False)], fenster=True)
    F("hh-mehr-kita-prozent", "lotti:/haushalt/produkte",
      "um wie viel prozent ist die kita teurer geworden seit 2020", f"{k}/rechnen", B_PRODUKTE,
      [Z(f"SELECT 100.0 * (({kita}) / ({kita}) - 1)", 2026, 2020, einheit="%", toleranz=0.04,
         bez="Anstieg Kita-Aufwand 2020→2026")], fenster=True)
    F("hh-mehr-zinsen-prokopf", "lotti:/haushalt/schulden",
      "wie viel zinsen zahlt die stadt pro einwohner", f"{k}/rechnen", B_IST,
      [Z(personal, 2024, 17, jahr=2024, bez="Zinsaufwand Ist 2024"),
       Z(f"SELECT ({personal}) / (SELECT population FROM council_einwohner WHERE year = ?)",
         2024, 17, 2024, jahr=2024, toleranz=0.05, bez="Zinsen je Einwohner*in 2024")],
      fenster=True)

    # --- kombination -------------------------------------------------------
    F("hh-mehr-gewst-staedte", "lotti:/haushalt/vergleich",
      "zahlen firmen in oldenburg pro kopf mehr gewerbesteuer als in osnabrück",
      f"{k}/kombination", B_VERGLEICH,
      [Z(CITY, 2025, "Oldenburg", "ist_je_ew_gewerbesteuer", jahr=2025,
         bez="Gewerbesteuer je Einwohner*in Oldenburg"),
       Z(CITY, 2025, "Osnabrück", "ist_je_ew_gewerbesteuer", jahr=2025,
         bez="Gewerbesteuer je Einwohner*in Osnabrück")], fenster=True)
    F("hh-mehr-invest-plan-ist-2024", "lotti:/haushalt/investitionen",
      "wurde 2024 so viel investiert wie geplant", f"{k}/kombination", B_INVEST_PLAN,
      [Z(inv_plan, 2024, jahr=2024, bez="Investitionen Plan 2024"),
       Z(INV_IST, 2024, jahr=2024, bez="Investitionsauszahlungen Ist 2024")], fenster=True)
    F("hh-mehr-steuern-personal", "lotti:/haushalt/einnahmen",
      "reichen die steuereinnahmen um das personal zu bezahlen", f"{k}/kombination", B_IST,
      [Z(personal, 2024, 13, jahr=2024, bez="Personalaufwendungen Ist 2024"),
       Z(TAX, 2024, "total", jahr=2024, bez="Steuern 2024",
         oder=[ALT(personal, 2024, 1, jahr=2024)])], fenster=True)
    F("hh-mehr-soziales-jugend", "lotti:/haushalt",
      "wofür gibt die stadt mehr aus: soziales oder jugend und familie", f"{k}/kombination",
      B_PLAN,
      [Z(area, 2026, "Soziales und Gesundheit", jahr=2026, bez="Soziales und Gesundheit 2026"),
       Z(area, 2026, "Jugend und Familie", jahr=2026, bez="Jugend und Familie 2026")],
      fenster=True)
    F("hh-mehr-schulden-prokopf-2015", "lotti:/haushalt/schulden",
      "wie viel schulden hatte jeder einwohner 2015 und wie viel heute", f"{k}/kombination",
      B_SCHULDEN,
      [Z(DEBT.format("per_capita"), 2015, jahr=2015, bez="je Einwohner*in 2015"),
       Z(DEBT.format("per_capita"), 2025, jahr=2025, bez="je Einwohner*in 2025")],
      fenster=True)
    F("hh-mehr-baeder-minus", "lotti:/haushalt/konzern",
      "welcher städtische betrieb plant 2026 das größte minus", f"{k}/kombination",
      B_WIRTSCHAFTSPLAN,
      [T([["Bäder", "Bad"]], "council_business_plans year=2026: kleinstes result = bbgo"),
       Z(BP.format("result"), "bbgo", 2026, jahr=2026, bez="Plan-Ergebnis Bäder 2026",
         betrag=True)], fenster=True)
    F("hh-mehr-fliegerhorst", "lotti:/haushalt/investitionen",
      "was kostet die kampfmittelsondierung auf dem fliegerhorst", f"{k}/kombination",
      B_MASSNAHMEN,
      [Z("SELECT grand_total FROM council_investment_measures WHERE year = ? AND level = 'measure' "
         "AND label = 'Fliegerhorst Kampfmittelsondierung'", 2026, jahr=2026,
         bez="Fliegerhorst Kampfmittelsondierung Gesamtsumme")], fenster=True)
    F("hh-mehr-stadion-kosten", "lotti:/haushalt",
      "was kostet das neue stadion", f"{k}/kombination",
      "Ratsarchiv (Beschluss 8677)",
      [Z("SELECT amount_eur FROM council_decisions WHERE id = ?", 8677,
         bez="Pauschalpreis Stadionneubau netto (Beschluss 8677)")], fenster=True,
      notiz="Steht in einem Ratsbeschluss, nicht in den Haushaltsdaten.")

    # --- nicht in den Daten -------------------------------------------------
    F("hh-mehr-nd-hannover", "lotti:/haushalt/schulden",
      "wie viel schulden hat hannover", f"{k}/nicht-in-daten", B_VERGLEICH, [], fenster=True,
      in_daten=False, notiz="Schuldenzahlen anderer Städte gibt es im Bestand nicht.")
    F("hh-mehr-nd-kitaplatz", "lotti:/haushalt/produkte",
      "was kostet ein kitaplatz pro kind", f"{k}/nicht-in-daten", B_PRODUKTE, [], fenster=True,
      in_daten=False, notiz="Keine Kinderzahlen im Bestand — pro Kind lässt sich nicht rechnen.")


def mehrstufig_anschluss() -> None:
    """Anschlussfragen: Die zweite Frage versteht nur, wer die erste kennt.

    Lotti bekommt aus früheren Runden die Frage und die ersten 300 Zeichen
    der Antwort (``panel.tsx``) — nicht, was sie dafür nachgeschlagen hat.
    „Und 2015?“ muss sie also neu nachschlagen (24.09.2026, Tims Auftrag
    „1–5“, Schritt 1).
    """
    k = "haushalt/mehrstufig/anschluss"
    kita = "SELECT expenses FROM council_products WHERE year = ? AND product_name = 'Kindertagesbetreuung'"
    stellen = ("SELECT positions_planned FROM council_staff_plan WHERE budget_year = ? "
               "AND part = ? AND kind = 'total' AND label = 'Summe'")
    steuerplan = "SELECT {} FROM council_tax_plan WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'"
    personal = IST.format("result")
    gewst = "SELECT amount FROM council_taxes WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'"

    F("hh-anschl-schulden-2015", "lotti:/haushalt/schulden", "und wie war das 2015?", k,
      B_SCHULDEN, [Z(DEBT.format("total"), 2015, jahr=2015, bez="Schuldenstand 2015")],
      fenster=True, vorfragen=["wie hoch sind die schulden der stadt"])
    F("hh-anschl-gewst-plan", "lotti:/haushalt/einnahmen", "und wie viel war dafür geplant?", k,
      B_STEUERPLAN, [Z(steuerplan.format("plan"), 2025, jahr=2025, bez="Gewerbesteuer Plan 2025")],
      fenster=True, vorfragen=["wie viel gewerbesteuer hat die stadt 2025 eingenommen"])
    F("hh-anschl-kita-2020", "lotti:/haushalt/produkte", "und wie viel war es 2020?", k,
      B_PRODUKTE, [Z(kita, 2020, jahr=2020, bez="Kindertagesbetreuung Aufwand Plan 2020")],
      fenster=True, vorfragen=["was kostet die kinderbetreuung"])
    F("hh-anschl-stellen-2023", "lotti:/haushalt/personal", "und 2023?", k, B_STELLEN,
      [Z(stellen, 2023, "B", jahr=2023, einheit="", bez="Stellen Teil B Plan 2023")],
      fenster=True, vorfragen=["wie viele beschäftigte hat die stadtverwaltung"])
    F("hh-anschl-personal-prozent", "lotti:/haushalt/plan-ist",
      "um wie viel prozent ist das seit 2020 gestiegen?", k, B_IST,
      [Z(f"SELECT 100.0 * (({personal}) / ({personal}) - 1)", 2024, 13, 2020, 13, einheit="%",
         toleranz=0.04, bez="Anstieg Personalaufwand 2020→2024")],
      fenster=True, vorfragen=["wie hoch waren die personalkosten 2024 tatsächlich"])
    F("hh-anschl-invest-ist", "lotti:/haushalt/investitionen",
      "und wie viel wurde dann tatsächlich investiert?", k, B_INVEST_IST,
      [Z(INV_IST, 2024, jahr=2024, bez="Investitionsauszahlungen Ist 2024")],
      fenster=True, vorfragen=["wie viel wollte die stadt 2024 investieren"])
    F("hh-anschl-hebesatz-davor", "lotti:/haushalt/steuer", "und wie hoch war er davor?", k,
      B_HEBESATZ, [Z(RATE, 2015, "Grundsteuer B", jahr=2015, einheit="%",
                     bez="Hebesatz Grundsteuer B 2015–2024")],
      fenster=True, vorfragen=["wie hoch ist der hebesatz der grundsteuer b"])
    F("hh-anschl-zinsen-prokopf", "lotti:/haushalt/schulden", "und pro einwohner?", k, B_IST,
      [Z(f"SELECT ({personal}) / (SELECT population FROM council_einwohner WHERE year = ?)",
         2024, 17, 2024, jahr=2024, toleranz=0.05, bez="Zinsen je Einwohner*in 2024")],
      fenster=True, vorfragen=["wie viel zinsen hat die stadt 2024 gezahlt"])
    F("hh-anschl-baeder-2020", "lotti:/haushalt/konzern", "und wie sah das 2020 aus?", k,
      B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "bbgo", 2020, jahr=2020, bez="Plan-Ergebnis Bäder 2020",
         betrag=True)],
      fenster=True, vorfragen=["wie viel minus planen die bäder 2026"])
    F("hh-anschl-gewst-anteil", "lotti:/haushalt/einnahmen",
      "wie viel prozent davon ist gewerbesteuer?", k, B_STEUERN,
      [Z("SELECT 100.0 * (" + gewst + ") / (" + TAX + ")", 2025, 2025, "total", jahr=2025,
         einheit="%", toleranz=0.03, bez="Anteil Gewerbesteuer an den Steuern 2025")],
      fenster=True, vorfragen=["wie viel steuern hat die stadt 2025 eingenommen"])


def mehrstufig_neue_reihen() -> None:
    """Reihen, die heute kein Werkzeug über die Jahre zeigt (Schritt 4).

    Gebühren, Kassenstand, Eigenbetriebe und Steuerplan liegen je Jahr in der
    Datenbank; die Bausteine zeigen davon das jüngste Jahr.
    """
    k = "haushalt/mehrstufig/neue-reihen"
    fee = "SELECT {} FROM council_fees WHERE year = ? AND area = ?"
    kasse = "SELECT amount FROM council_liquidity WHERE month = ?"
    gewst = "SELECT amount FROM council_taxes WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'"
    personal = IST.format("result")

    F("hh-reihe-strassenreinigung", "lotti:/haushalt/konzern",
      "wie hat sich die straßenreinigungsgebühr seit 2019 verändert", k, B_GEBUEHREN,
      [Z(fee.format("fee"), 2019, "street_cleaning", jahr=2019, einheit="", toleranz=0.01,
         bez="Straßenreinigungsgebühr 2019"),
       Z(fee.format("fee"), 2026, "street_cleaning", jahr=2026, einheit="", toleranz=0.01,
         bez="Straßenreinigungsgebühr 2026")], fenster=True)
    F("hh-reihe-abfall-kosten", "lotti:/haushalt/einnahmen",
      "sind die kosten der müllabfuhr seit 2019 gestiegen", k, B_GEBUEHREN,
      [Z(fee.format("costs_to_cover"), 2019, "waste_collection", jahr=2019,
         bez="Abfallsammlung zu deckende Kosten 2019"),
       Z(fee.format("costs_to_cover"), 2026, "waste_collection", jahr=2026,
         bez="Abfallsammlung zu deckende Kosten 2026")], fenster=True)
    F("hh-reihe-kasse-jahresanfang", "lotti:/haushalt/schulden",
      "wie hat sich der kassenstand seit januar entwickelt", k, B_LIQUIDITAET,
      [Z(kasse, "2026-01", jahr=2026, bez="Liquidität Januar 2026"),
       Z(kasse, "2026-08", jahr=2026, bez="Liquidität August 2026")], fenster=True)
    F("hh-reihe-kasse-2025", "lotti:/haushalt",
      "wie viel geld hatte die stadt ende 2025 auf dem konto", k, B_LIQUIDITAET,
      [Z(kasse, "2025-12", jahr=2025, bez="Liquidität Dezember 2025")], fenster=True)
    F("hh-reihe-baeder-defizit", "lotti:/haushalt/schulden",
      "wie hat sich das defizit der bädergesellschaft seit 2020 entwickelt", k,
      B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "bbgo", 2020, jahr=2020, bez="Plan-Ergebnis BBGO 2020", betrag=True),
       Z(BP.format("result"), "bbgo", 2026, jahr=2026, bez="Plan-Ergebnis BBGO 2026",
         betrag=True)], fenster=True)
    F("hh-reihe-awb-ausgaben", "lotti:/haushalt/konzern",
      "wie viel mehr gibt der abfallwirtschaftsbetrieb heute aus als 2019", k,
      B_WIRTSCHAFTSPLAN,
      [Z(BP.format("expenses"), "awb", 2019, jahr=2019, bez="AWB Aufwendungen Plan 2019"),
       Z(BP.format("expenses"), "awb", 2026, jahr=2026, bez="AWB Aufwendungen Plan 2026")],
      fenster=True)
    F("hh-reihe-gebaeudewirtschaft", "lotti:/haushalt/investitionen",
      "hat die gebäudewirtschaft früher mehr verlust geplant als heute", k, B_WIRTSCHAFTSPLAN,
      [Z(BP.format("result"), "egh", 2025, jahr=2025, bez="Plan-Ergebnis EGH 2025", betrag=True,
         oder=[ALT(BP.format("result"), "egh", 2024, jahr=2024),
               ALT(BP.format("result"), "egh", 2023, jahr=2023)]),
       Z(BP.format("result"), "egh", 2026, jahr=2026, bez="Plan-Ergebnis EGH 2026", betrag=True)],
      fenster=True)
    F("hh-reihe-gewst-plan-ist", "lotti:/haushalt/steuer",
      "lag die gewerbesteuer in den letzten jahren immer über dem plan", k, B_STEUERPLAN,
      [Z("SELECT plan FROM council_tax_plan WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'",
         2023, jahr=2023, bez="Gewerbesteuer Plan 2023"),
       Z("SELECT actual FROM council_tax_plan WHERE year = ? AND kind = 'Gewerbesteuer (-umlage)'",
         2023, jahr=2023, bez="Gewerbesteuer Ist 2023")], fenster=True)
    F("hh-reihe-invest-2020-2024", "lotti:/haushalt/plan-ist",
      "wurde 2020 mehr investiert als 2024", k, B_INVEST_IST,
      [Z(INV_IST, 2020, jahr=2020, bez="Investitionsauszahlungen Ist 2020"),
       Z(INV_IST, 2024, jahr=2024, bez="Investitionsauszahlungen Ist 2024")], fenster=True)
    F("hh-reihe-zinsen-2017", "lotti:/haushalt/schulden",
      "zahlt die stadt heute mehr zinsen als 2017", k, B_IST,
      [Z(personal, 2017, 17, jahr=2017, bez="Zinsaufwand Ist 2017"),
       Z(personal, 2024, 17, jahr=2024, bez="Zinsaufwand Ist 2024",
         oder=[ALT(personal, 2025, 17, jahr=2025)])], fenster=True)
    F("hh-reihe-einwohner-2010", "lotti:/haushalt/vergleich",
      "wie viele einwohner hat oldenburg mehr als 2010", k, B_REIHE,
      [Z("SELECT population FROM council_einwohner WHERE year = ?", 2010, jahr=2010, einheit="",
         bez="Einwohner*innen 2010"),
       Z("SELECT population FROM council_einwohner WHERE year = ?", 2025, jahr=2025, einheit="",
         bez="Einwohner*innen 2025")], fenster=True)
    F("hh-reihe-grundsteuer-sprung", "lotti:/haushalt/steuer",
      "um wie viel prozent wurde die grundsteuer b 2025 erhöht", k, B_HEBESATZ,
      # 1.0 *: Hebesätze sind ganze Zahlen, und SQLite teilt dann ganzzahlig
      # (539 / 445 = 1) — das Gold stand bis 25.09.2026 auf 0,0 %.
      [Z("SELECT 100.0 * (1.0 * (" + RATE + ") / (" + RATE + ") - 1)", 2025, "Grundsteuer B", 2015,
         "Grundsteuer B", einheit="%", toleranz=0.03, bez="Erhöhung Hebesatz Grundsteuer B 2025")],
      fenster=True)
    F("hh-reihe-anteil-grundsteuer", "lotti:/haushalt/einnahmen",
      "welcher anteil der steuereinnahmen kommt aus der grundsteuer", k, B_STEUERN,
      [Z("SELECT 100.0 * (" + TAX + ") / (" + TAX + ")", 2025, "Grundsteuer A+B", 2025, "total",
         jahr=2025, einheit="%", toleranz=0.03, bez="Anteil Grundsteuer an den Steuern 2025")],
      fenster=True)
    F("hh-reihe-gewst-verdopplung", "lotti:/haushalt/steuer",
      "hat sich die gewerbesteuer seit 2012 verdoppelt", k, B_STEUERN,
      [Z(gewst, 2012, jahr=2012, bez="Gewerbesteuer 2012"),
       Z(gewst, 2025, jahr=2025, bez="Gewerbesteuer 2025")], fenster=True)


def main() -> int:
    faelle = bauen()
    ZIEL.write_text(json.dumps(faelle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lotti = sum(1 for f in faelle if f["kanal"] == "lotti")
    nd = sum(1 for f in faelle if not f["antwort_in_daten"])
    print(f"✓ {ZIEL.relative_to(WURZEL)}: {len(faelle)} Fälle, {lotti} Lotti / "
          f"{len(faelle) - lotti} Frag den Rat, {nd} ohne Antwort in den Daten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
