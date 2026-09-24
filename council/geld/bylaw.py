"""Die Haushaltssatzung — der Rahmen, den die Zahlen des Haushalts bekommen.

Der Haushaltsplan sagt, wofür das Geld ausgegeben werden SOLL; die Satzung
sagt, was die Stadt DÜRFTE: die Gesamtbeträge beider Haushalte (§ 1), die
Kreditermächtigung für Investitionen (§ 2), die Verpflichtungsermächtigungen
(§ 3), den Höchstbetrag für Liquiditätskredite (§ 4) und die Hebesätze (§ 5).

ZWEI DINGE MUSS JEDE ANTWORT MITFÜHREN, und beide stehen deshalb im
Baustein und nicht nur hier:

* **Es ist ein Entwurf.** Im Ratsinformationssystem liegen ausschließlich
  Verwaltungsentwürfe — Deckblatt „Verwaltungsentwurf", Sitzungsdatum
  „xx.xx.JJJJ". Die beschlossene Satzung erscheint im Amtsblatt der Stadt,
  nicht im RIS. Jede Zeile trägt darum ``version = 'draft'``, und eine
  Antwort, die das wegließe, machte aus einem Vorschlag der Verwaltung einen
  Ratsbeschluss (``council/budget_bylaw.py``, Modulkopf).
* **„Nicht veranschlagt" ist keine Null.** § 2 steht in jedem gelesenen
  Jahrgang auf null, und die Satzung schreibt dort einen Satz statt einer
  Ziffer. „0 €" wäre die schlechtere Auskunft: Die Stadt hat sich keine
  Kreditermächtigung geben lassen, sie hat nicht null Euro aufgenommen.

OB und WANN der Rat beschlossen hat, steht trotzdem im Baustein — aus den
Ratsbeschlüssen (``budget_adoption``), nicht aus dem Entwurf. Der Entwurf
2026 nannte den 15.12.2025, den Tag der Vertagung; beschlossen wurde am
09.02.2026 (Fakten-Eval 23.09.2026).

Die Hebesätze aus § 5 kommen mit, aber immer mit dem Vorschlags-Vermerk: Was
hier steht, ist der Satz, den die Verwaltung vorgeschlagen hat. Ob der Rat
ihn beschlossen hat, sagt diese Quelle nicht — die geltenden Sätze führt die
Steuer-Schicht. Die Erkennung feuert deshalb auch nicht auf „Hebesatz".
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "bylaw"

#: Die Wörter, die nur in dieser Satzung vorkommen.
_HART = re.compile(
    r"haushaltssatzung|kreditermaechtigung|verpflichtungsermaechtigung|"
    r"liquiditaetskredit|kassenkredit|kredite fuer investitionen")
#: „Satzung", „Ermächtigung" und „Höchstbetrag" brauchen einen Haushalts-
#: Anker: Oldenburg hat eine Baumschutzsatzung, eine Gebührensatzung und ein
#: Dutzend andere, und ein Höchstbetrag steht in jeder zweiten davon.
#: (Gefaltet greift `\bsatzung` in „Baumschutzsatzung" ohnehin nicht — die
#: Wortgrenze fehlt dort; die Regel ist trotzdem die richtige.)
_WEICH = re.compile(
    r"\bsatzung|ermaechtigung|hoechstbetrag|"
    # „Wann hat der Rat den Haushalt 2026 beschlossen?" — die Satzung ist der
    # Beschluss, und ihr Baustein trägt seit 09/2026 das Datum aus den
    # Ratsbeschlüssen (`budget_adoption`). Ohne ihn stand dort nur „ES IST
    # DER VERWALTUNGSENTWURF", und beide Modelle antworteten, der Haushalt
    # sei noch nicht beschlossen (Fakten-Eval 23.09.2026).
    # Nur die Frage nach dem OB und WANN — nicht jedes „beschlossen": „Was
    # hat der Rat zum Haushalt beschlossen?" fragt nach Inhalten, und der
    # Baustein stünde mit knapp 2.000 Zeichen vorn im Deckel.
    r"wann[^.?!]{0,60}(?:beschlossen|verabschiedet)|"
    r"(?:schon|bereits|noch nicht|endlich)\s+(?:beschlossen|verabschiedet)|"
    r"verabschiedung|haushaltsbeschluss")
_ANKER = frozenset(("plan", "ansatz"))
#: „Wie viel Kredit darf die Stadt 2026 aufnehmen?" — die Frage nach dem
#: RAHMEN, also nach § 2 und § 4. Bis 09/2026 zog sie nur Schuldenstand und
#: Kreditkonditionen; der Höchstbetrag der Liquiditätskredite (100 Mio. €)
#: stand in keinem Prompt (Fakten-Eval 23.09.2026). Eigenständig, weil die
#: Frage kein Haushalts-Wort trägt.
_DARF = re.compile(
    r"\bdarf[^.?!]{0,40}(?:kredit|aufnehmen|leihen|verschulden)|"
    r"(?:kredit|schulden)[^.?!]{0,40}\b(?:darf|duerfen|erlaubt|maximal|hoechstens)|"
    # Frag den Rat sucht mit der UMFORMULIERTEN Frage: Aus „Wie viel Kredit
    # darf die Stadt 2026 aufnehmen?" machte die Analyse „Wie hoch ist die
    # Kreditaufnahmegrenze der Stadt für das Jahr 2026?" (Fakten-Eval,
    # 23.09.2026) — dieselbe Frage, als Substantiv.
    r"kredit\w*(?:grenze|rahmen|limit)|(?:obergrenze|grenze|rahmen) (?:fuer|der) kredit")


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    if _HART.search(text) or _DARF.search(text):
        return True
    return bool(_WEICH.search(text) and (facets & _ANKER))


#: Die drei Ermächtigungen, deren Reihe über die Jahrgänge jemand meinen
#: kann — je Spalte ihr Name und das Muster, das sie in den Suchbegriffen
#: erkennt. Geprüft wird IN DIESER REIHENFOLGE, die engste zuerst; die erste,
#: die trifft, gewinnt.
#:
#: Hier steht bewusst nicht ``_trifft``, obwohl es die Hausmethode ist: Es
#: kappt Begriffe auf sechs Zeichen, und damit sind „Kassenkredit" und
#: „Kreditermächtigung" beide bloß „kredit" — die Auswahl fiel dann auf die
#: Reihe, die zufällig vorn stand (gemessen). Wo es ums UNTERSCHEIDEN geht
#: statt ums Finden, ist die Kappung genau das Falsche.
_REIHEN: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("liquidity_loans", "Höchstbetrag für Liquiditätskredite (§ 4)",
     re.compile(r"liquiditaet|kassenkredit|hoechstbetrag|dispo|zahlungsfaehig")),
    ("commitment_authorizations", "Verpflichtungsermächtigungen (§ 3)",
     re.compile(r"verpflichtungsermaecht|kuenftige jahre|vorbelast")),
    ("investment_loans", "Kredite für Investitionen (§ 2)",
     re.compile(r"kreditermaecht|\bkredit|darlehen|verschuld|aufnehmen|leihen")),
)


def _betrag(v: float | None) -> str:
    """Beträge der Satzung — mit dem Satz statt der Ziffer für die Null.

    § 2 steht in jedem Jahrgang auf null, und „nicht veranschlagt" ist die
    Auskunft, die dort im Dokument steht (so hält es auch die Seite)."""
    if v is None:
        return "sagt die Satzung nichts dazu"
    if v == 0:
        return "nicht veranschlagt"
    return geld.de_mio(v)


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die Satzungs-Jahrgänge für den Prompt."""

    def budget_adoption(self, year: int) -> dict | None:
        """Wann der RAT Haushaltssatzung und Haushaltsplan eines Jahres
        beschlossen hat — aus den Ratsbeschlüssen, nicht aus der Satzung.

        Die Satzung im Bestand ist immer der Verwaltungsentwurf, und ihr Datum
        ist die GEPLANTE Sitzung: Für 2026 stand dort der 15.12.2025 — an dem
        Tag hat der Finanzausschuss vertagt (Beschluss 9283); beschlossen hat
        der Rat am 09.02.2026 (Beschluss 8286). Die Beschlüsse kennen das
        Ergebnis, die Satzung nicht.

        Gesucht wird der angenommene Ratsbeschluss mit dem Titel, den die
        Verwaltung seit 2019 jedes Jahr gleich setzt („Haushaltssatzung und
        Haushaltsplan JAHR …"). Kein Treffer = noch nicht beschlossen (oder
        der Beschluss ist noch nicht eingelesen) — ``None``, nie geraten.
        """
        try:
            r = self._conn.execute(
                "SELECT d.id, s.session_date, d.title FROM council_decisions d "
                "JOIN council_sessions s ON s.ksinr = d.ksinr "
                "WHERE s.committee = 'Rat' AND d.outcome = 'accepted' "
                "  AND d.title LIKE ? "
                "ORDER BY s.session_date DESC, d.id DESC LIMIT 1",
                (f"Haushaltssatzung und Haushaltsplan {int(year)}%",)).fetchone()
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if not r or not r["session_date"]:
            return None
        return {"date": r["session_date"], "decision_id": r["id"], "title": r["title"]}

    def bylaw_context(self, terms: list[str],
                      year: int | None = None) -> dict | None:
        """Die Haushaltssatzung eines Jahrgangs, dazu eine Reihe auf Wunsch.

        Nachträge (``supplement > 0``) liest die Schicht nicht; abgefragt
        wird deshalb nur die Satzung selbst.

        ``terms`` wählen die eine Kennzahl aus, deren Reihe über alle
        Jahrgänge mitkommt — nach der Kreditermächtigung zu fragen und in
        JEDEM Jahrgang „nicht veranschlagt" zu lesen, IST die Antwort. Ohne
        Treffer bleibt es beim gefragten Jahrgang.
        """
        try:
            jahr, abweichend = geld.jahrgang(
                self._conn, "council_budget_bylaw", "year", year,
                wo="supplement = 0")
            if jahr is None:
                return None
            zeile = self._conn.execute(
                "SELECT * FROM council_budget_bylaw "
                "WHERE year = ? AND supplement = 0", (jahr,)).fetchone()
            jahrgaenge = [r[0] for r in self._conn.execute(
                "SELECT year FROM council_budget_bylaw WHERE supplement = 0 "
                "ORDER BY year")]
            gemeint = geld.falte(" ".join(terms or []))
            gewaehlt = next(((spalte, name) for spalte, name, muster in _REIHEN
                             if muster.search(gemeint)), None)
            reihe = [dict(r) for r in self._conn.execute(
                f"SELECT year, {gewaehlt[0]} AS wert FROM council_budget_bylaw "
                "WHERE supplement = 0 ORDER BY year")] if gewaehlt else []
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        if zeile is None:
            return None
        return {
            "year": jahr,
            "anderer_jahrgang": abweichend,
            "zeile": dict(zeile),
            # Eine Lücke ist eine Auskunft: 2022 fehlt im Bestand, und ohne
            # den Satz liest ein Modell die Reihe als geschlossen.
            "fehlend": [j for j in range(min(jahrgaenge), max(jahrgaenge) + 1)
                        if j not in jahrgaenge],
            "reihe": {"name": gewaehlt[1], "werte": reihe} if gewaehlt else None,
            "beschluss": self.budget_adoption(jahr),
            "beleg": self._beleg(zeile["herkunft_id"]),
        }


def block(data: dict | None) -> str:
    """Der Baustein — mit dem Entwurfs-Vermerk vor den Zahlen, nicht danach."""
    if not data or not data.get("zeile"):
        return ""
    z = data["zeile"]
    ergebnis = (z.get("ordinary_revenues") or 0) - (z.get("ordinary_expenses") or 0)
    zeilen = [
        f"- Ergebnishaushalt {data['year']} (§ 1): ordentliche Erträge "
        f"{geld.de_mio(z.get('ordinary_revenues'))}, ordentliche Aufwendungen "
        f"{geld.de_mio(z.get('ordinary_expenses'))} — der Entwurf plant damit "
        f"{'einen Überschuss' if ergebnis >= 0 else 'einen Fehlbetrag'} von "
        f"{geld.de_mio(abs(ergebnis))}" + geld.beleg_text(data.get("beleg")),
        # Auszahlungen und Einzahlungen auf je einer eigenen Zeile: Die
        # „davon" darunter gehören zu den AUSZAHLUNGEN, und eine Zeile, die mit
        # den Einzahlungen anfinge, läse sich als ihre Summe
        # (tests/test_geld_gliederung.py).
        f"- Finanzhaushalt {data['year']} (§ 1, „Nachrichtlich“), Auszahlungen "
        f"insgesamt: {geld.de_mio(z.get('out_total'))}",
        # Die drei Auszahlungsarten, die die Satzung selbst zur Summe darüber
        # addiert (ihre Probe). Bis 09/2026 fehlten sie: „Wie viel investiert
        # die Stadt 2026?" und „Wie viel tilgt sie?" hatten hier ihre Zahl und
        # bekamen sie nicht (Fakten-Eval 23.09.2026).
        f"  - davon Auszahlungen aus laufender Verwaltungstätigkeit {data['year']}: "
        f"{geld.de_mio(z.get('out_operating'))}",
        f"  - davon Auszahlungen für Investitionstätigkeit {data['year']}: "
        f"{geld.de_mio(z.get('out_capital'))}",
        f"  - davon Auszahlungen aus Finanzierungstätigkeit (Tilgung) {data['year']}: "
        f"{geld.de_mio(z.get('out_financing'))}",
        f"- Finanzhaushalt {data['year']}, Einzahlungen insgesamt: "
        f"{geld.de_mio(z.get('in_total'))}",
        f"- Kredite für Investitionen (§ 2): {_betrag(z.get('investment_loans'))} "
        "— das ist die ERMÄCHTIGUNG, sich zu verschulden, nicht der "
        "Schuldenstand",
        f"- Höchstbetrag für Liquiditätskredite (§ 4): "
        f"{_betrag(z.get('liquidity_loans'))}; Verpflichtungsermächtigungen "
        f"(§ 3): {_betrag(z.get('commitment_authorizations'))}",
    ]
    b = data.get("beschluss")
    if b:
        d = b["date"]
        tag = f"{d[8:10]}.{d[5:7]}.{d[:4]}" if len(d) >= 10 and d[4] == "-" else d
        zeilen.insert(0, f"- BESCHLOSSEN hat der Rat Haushaltssatzung und Haushaltsplan "
                         f"{data['year']} am {tag} (Ratsbeschluss; die Zahlen unten "
                         "stammen aus dem Entwurf, der dafür eingebracht wurde)")
    else:
        zeilen.insert(0, f"- Einen Ratsbeschluss zu Haushaltssatzung und Haushaltsplan "
                         f"{data['year']} gibt es im Bestand (noch) nicht.")
    if data.get("anderer_jahrgang"):
        zeilen.append("- Zum gefragten Jahr liegt keine Satzung im Bestand; die "
                      f"Zahlen sind die des Jahrgangs {data['year']}.")
    saetze = [(n, s) for n, s in (
        ("Grundsteuer A", z.get("property_tax_a_rate")),
        ("Grundsteuer B", z.get("property_tax_b_rate")),
        ("Gewerbesteuer", z.get("trade_tax_rate"))) if s]
    if saetze:
        zeilen.append("- Hebesätze (§ 5), VORGESCHLAGEN: "
                      + ", ".join(f"{n} {s} %" for n, s in saetze)
                      + ". Ob der Rat sie so beschlossen hat, sagt diese Quelle "
                      "nicht.")
    if data.get("reihe"):
        werte = data["reihe"]["werte"]
        einzig = {r["wert"] for r in werte}
        if len(einzig) == 1:
            # Die Kreditermächtigung steht in JEDEM Jahrgang auf null. Sieben
            # gleiche Zeilen aufzuzählen wäre die schlechtere Auskunft als der
            # Satz, der die Gleichheit selbst zur Aussage macht.
            zeilen.append(f"- {data['reihe']['name']} in allen "
                          f"{len(werte)} Jahrgängen {werte[0]['year']}–"
                          f"{werte[-1]['year']}: {_betrag(einzig.pop())}")
        else:
            zeilen.append(f"- {data['reihe']['name']} über die Jahrgänge — "
                          + ", ".join(f"{r['year']}: {_betrag(r['wert'])}"
                                      for r in werte))
    if data.get("fehlend"):
        fehlt = ", ".join(str(j) for j in data["fehlend"])
        zeilen.append(f"- NICHT im Bestand: {fehlt}. Diese Jahrgänge haben "
                      "keinen Wert — weder null noch geschätzt.")
    return (f"\nHAUSHALTSSATZUNG {data['year']} (§§ 1–5). Sie sagt, was die Stadt "
            "DÜRFTE; der\nHaushaltsplan daneben, wofür sie es ausgeben will.\n"
            "DIE ZAHLEN SIND DER VERWALTUNGSENTWURF, und das gehört in die "
            "Antwort: Im\nRatsinformationssystem liegen ausschließlich Entwürfe, "
            "die beschlossene Fassung\nerscheint im Amtsblatt und ist nicht im "
            "Bestand. Schreibe bei den Zahlen also\n„laut Entwurf der "
            "Verwaltung“; OB und WANN der Rat beschlossen hat, sagt die\n"
            "erste Zeile (aus den Ratsbeschlüssen). Was der Rat am Entwurf "
            "änderte, steht in\nden Änderungslisten.\n„Nicht veranschlagt“ ist KEINE Null — die Satzung "
            "schreibt dort einen Satz statt\neiner Ziffer: Die Stadt hat sich die "
            "Ermächtigung nicht geben lassen, nicht\nnull Euro aufgenommen. NIE "
            "mit [id]:\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="bylaw_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=20,
    # 2.064 Zeichen gemessen (dev-Abzug, 23.09.2026: Kassenkredit-Frage mit
    # der Reihe über acht Jahrgänge). Bis dahin 1.800; dazugekommen sind das
    # Datum des Ratsbeschlusses und die drei Auszahlungsarten des
    # Finanzhaushalts (Investitionen, Tilgung — beide in der Fakten-Eval
    # gefragt und nicht im Prompt).
    grenze=2200,
    probefrage="Was steht in der Haushaltssatzung?",
)
