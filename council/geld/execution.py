"""Der Haushaltsvollzug — was die Verwaltung für den 31.12. ERWARTET.

Die Schicht schließt die Lücke, die die KI-Frage bis 09/2026 hatte: Sie
kannte den Plan für das kommende Jahr und den Jahresabschluss von
vorvorletztem — dazwischen lag das Jahr, das gerade läuft. Genau darüber
berichtet die Stadt vierteljährlich an den Ausschuss für Finanzen und
Beteiligungen (§ 31 KomHKVO, „Finanz- und Leistungsbericht"), zu den
Stichtagen 30.06., 30.09. und 31.12.

DIE PROGNOSE IST KEIN IST, und dagegen schreibt der Baustein an. „Zum
30. Juni" ist der Tag, an dem die Ämter ihre Erwartung für den 31. Dezember
abgegeben haben — kein Halbjahresergebnis. Die Quelle führt überhaupt keine
Spalte für das bis zum Stichtag Gebuchte (``council/budget_execution.py``,
Abschnitt „Was der Bericht nicht hergibt"), und die Seite hält dieselbe
Wortwahl durch: „geplant → erwartet", nie „tatsächlich". Ein Sprachmodell,
das eine Prognose im Kontext hat und nach dem laufenden Jahr gefragt wird,
schreibt sonst „die Stadt hat 2026 ausgegeben" — und behauptet damit ein
Ergebnis, das erst zwei Jahre später existiert.

Die zweite Falle ist ``plan_basis``: Bis zum Haushaltsjahr 2020 rechnet die
Ansatz-Spalte die Ermächtigungsübertragungen aus dem Vorjahr mit ein, ab
2021 nicht mehr. Wo der gelieferte Jahrgang die alte Basis führt, steht der
Satz dazu im Baustein — sonst vergliche eine Antwort zwei verschiedene
Größen.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date

from council import geld

NAME = "execution"

#: Die Wörter, die NUR diesen Bericht meinen können — sie feuern allein.
_HART = re.compile(
    r"haushaltsvollzug|zwischenstand|zwischenbericht|quartalsbericht|"
    r"finanz und leistungsbericht|leistungsbericht|hochrechnung|hochgerechnet")
#: Und die weichen, die einen Geld-Anker brauchen. Jedes einzelne davon
#: gehört auch zu ganz anderen Fragen: „Wie ist der Stand beim Stadion?",
#: „Was passiert im laufenden Verfahren?", „Wie ist die
#: Bevölkerungsprognose?" — alle drei dürfen den Haushalt nicht anfassen.
#: `nach plan` steht bewusst hier und nicht oben: „Läuft das Stadion nach
#: Plan?" ist dieselbe Formulierung und meint ein Bauvorhaben.
#:
#: „Stand" nur mit Artikel („der/zum/beim Stand", „Stand der …"), denn das
#: nackte Wort ist im Deutschen zuerst ein VERB: „Was stand in der
#: Haushaltssatzung 2020?" hat mit dem Zwischenstand des laufenden Jahres
#: nichts zu tun und zog ihn trotzdem (gemessen an der dev-Datenbank).
_WEICH = re.compile(
    r"prognos|erwartet|voraussichtlich|\baktuell|bisher|nach plan|sachstand|"
    r"(?:der|zum|beim|aktuelle[rn]?) stand\b|\bstand der\b|"
    # `\blaufen` deckt „laufende(n)" mit ab — die Wortgrenze steht nur vorn.
    r"halbjahr|quartal|\blaeuft|\blaufen|gelaufen|\blief\b")
#: Der Anker ist die FACETTE, nicht noch einmal ein Wortmuster: `_F_PLAN` in
#: `qa.py` enthält `haushalt|etat|budget` bereits, ein zusätzlicher Texttest
#: darauf könnte also nie etwas beitragen, was `plan` nicht schon sagt.
_ANKER = frozenset(("plan", "ist", "ansatz"))
_JAHR = re.compile(r"\b(20\d\d)\b")


def _abschlussjahr() -> int:
    """Bis zu welchem Jahr es einen Jahresabschluss gibt — gerechnet.

    Der Abschluss hinkt zwei Jahre hinterher (so beschreibt es
    ``council/store.py`` über der Tabelle: „die Lücke zwischen Plan
    (kommendes Jahr) und Jahresabschluss (vorvorletztes Jahr)"). Gerechnet
    statt als Konstante 2024 hingeschrieben, weil eine Konstante genau ein
    Jahr lang stimmt und danach still falsch wird."""
    return date.today().year - 2


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    if _HART.search(text):
        return True
    if _WEICH.search(text) and (facets & _ANKER):
        return True
    # Zweite Regel, ohne die die Facette ihre häufigste Frage verpasst: Wer
    # nach dem Ist eines Jahres fragt, für das es noch keinen Jahresabschluss
    # gibt („Wie viel hat die Stadt 2026 ausgegeben?"), bekommt sonst gar
    # nichts — der Vollzug ist für diese Jahre die einzige Quelle dazu.
    #
    # Nur `ist`, NICHT auch `plan`: Der Auftrag sah beides vor, aber „plan"
    # plus Jahreszahl trifft auch „Welche Änderungslisten gab es zum Haushalt
    # 2026?" — eine Verfahrensfrage, deren Antwort der Vollzug nicht ist
    # (gemessen am Korpus in tests/test_qa_geldquellen.py).
    m = _JAHR.search(text)
    return bool(m and int(m.group(1)) > _abschlussjahr() and "ist" in facets)


#: Womit die Begriffe den Finanzhaushalt dazuholen. Er bewegt Ein- und
#: Auszahlungen der Investitionstätigkeit und ist ein anderes Zahlenwerk als
#: der Ergebnishaushalt — er kommt deshalb nur, wenn die Frage ihn meint.
#:
#: Das Wort „Finanzhaushalt" steht hier NICHT, obwohl es das treffendste
#: wäre: `_trifft` kappt auf sechs Zeichen, und „Haushalt" (in fast jeder
#: Expansion) steckt als Stamm in „finanzhaushalt". Der Auslöser hätte damit
#: immer gefeuert — gemessen, nicht befürchtet.
_INVESTIV = ("Investitionen investiv Auszahlungen Investitionstätigkeit "
             "Baumaßnahmen Neubau")
#: Wie die Quelle ihre beiden Haushalte und ihre Salden nennt (die Wortwahl
#: stammt aus `budget_execution.HAUSHALT_NAMEN` und `haushalt-vollzug.ts`).
_ERGEBNIS_WORT = {"result": "Jahresergebnis", "cash": "Saldo aus Investitionen"}
_BASIS_SATZ = (
    "Der Ansatz dieses Jahrgangs enthält die Ermächtigungsübertragungen aus "
    "dem Vorjahr („verfügbare Mittel“, so berichtete die Stadt bis 2020) — "
    "nicht dieselbe Größe wie der Ansatz ab 2021.")


def _beleg_text(b: dict | None) -> str:
    if not b:
        return ""
    teile = [str(t) for t in (b.get("label"), b.get("citation")) if t]
    return f" — Beleg: {', '.join(teile)}" if teile else ""


def _de_tag(iso: str | None) -> str:
    """„30.06.2026" aus „2026-06-30" — wie die Seite den Stichtag schreibt."""
    if not iso or len(iso) < 10:
        return str(iso or "–")
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


class Store:
    """Mixin für ``CouncilStore`` — der Zwischenstand des laufenden Jahres."""

    def execution_context(self, terms: list[str],
                          year: int | None = None) -> dict | None:
        """Der jüngste Bericht eines Jahrgangs: Summe, Verlauf, Teilhaushalte.

        Geliefert wird immer nur EIN Stichtag — der jüngste des Jahrgangs.
        Drei Berichte nebeneinander wären drei Erwartungen für denselben
        31. Dezember, und die jüngste ist die, die gilt; die älteren stehen
        als Verlauf daneben, damit die Bewegung im Jahr sichtbar bleibt.

        ``terms`` wählen bis zu drei Teilhaushalte aus (Treffer auf ihrer
        gedruckten Bezeichnung) und entscheiden, ob der Finanzhaushalt
        dazukommt. Ohne Treffer bleibt es bei den Summenzeilen des
        Ergebnishaushalts — dreizehn Bereiche wären der halbe Prompt.
        """
        try:
            jahr, abweichend = geld.jahrgang(
                self._conn, "council_budget_execution", "budget_year", year)
            if jahr is None:
                return None
            stichtag = self._conn.execute(
                "SELECT MAX(as_of) FROM council_budget_execution "
                "WHERE budget_year = ?", (jahr,)).fetchone()[0]
            if not stichtag:
                return None
            summen = self._conn.execute(
                "SELECT budget, kind, budgeted, forecast, deviation, carryover, "
                "       plan_basis, herkunft_id "
                "FROM council_budget_execution "
                "WHERE budget_year = ? AND as_of = ? AND is_total = 1",
                (jahr, stichtag)).fetchall()
            verlauf = self._conn.execute(
                "SELECT as_of, forecast FROM council_budget_execution "
                "WHERE budget_year = ? AND is_total = 1 AND budget = 'result' "
                "  AND kind = 'result' ORDER BY as_of", (jahr,)).fetchall()
            bereiche = self._conn.execute(
                "SELECT label, budgeted, forecast, deviation "
                "FROM council_budget_execution "
                "WHERE budget_year = ? AND as_of = ? AND is_total = 0 "
                "  AND budget = 'result' AND kind = 'result' "
                "ORDER BY sub_budget", (jahr, stichtag)).fetchall()
        except sqlite3.OperationalError:
            return None
        nach = {(r["budget"], r["kind"]): dict(r) for r in summen}
        ergebnis = nach.get(("result", "result"))
        if not ergebnis:
            return None
        # Nach Begriffs-Treffern, bei Gleichstand die größte Abweichung
        # zuerst: Wer „Soziales" fragt, will den Bereich; wer nichts trifft,
        # bekommt keinen — nicht dreizehn.
        getroffen = [(self._trifft(r["label"], terms), abs(r["deviation"] or 0), dict(r))
                     for r in bereiche]
        gewaehlt = [t[2] for t in sorted(getroffen, key=lambda t: (-t[0], -t[1]))
                    if t[0]][:3]
        return {
            "year": jahr,
            "anderer_jahrgang": abweichend,
            "as_of": stichtag,
            "ergebnis": ergebnis,
            "ertrag": nach.get(("result", "revenue")),
            "aufwand": nach.get(("result", "expense")),
            "plan_basis": ergebnis.get("plan_basis"),
            "verlauf": [dict(v) for v in verlauf],
            "bereiche": gewaehlt,
            "finanzhaushalt": (nach.get(("cash", "result"))
                               if self._trifft(_INVESTIV, terms) else None),
            "beleg": self._beleg(ergebnis.get("herkunft_id")),
        }


def block(data: dict | None) -> str:
    """Der Baustein — mit dem Wort „erwartet" an jeder Zahl."""
    if not data or not data.get("ergebnis"):
        return ""
    e = data["ergebnis"]
    tag = _de_tag(data["as_of"])
    zeilen = [
        f"- {_ERGEBNIS_WORT['result']} {data['year']}, Stand {tag}: geplant "
        f"{geld.de_mio(e.get('budgeted'))}, erwartet {geld.de_mio(e.get('forecast'))} "
        f"— Abweichung {geld.de_mio(e.get('deviation'))} (so im Bericht gedruckt)"
        + _beleg_text(data.get("beleg"))
    ]
    if data.get("anderer_jahrgang"):
        zeilen.append("- Für das gefragte Jahr liegt kein Bericht vor; die "
                      f"Zahlen sind die des Haushaltsjahres {data['year']}.")
    if data.get("ertrag") and data.get("aufwand"):
        zeilen.append(
            f"  - davon Erträge: geplant {geld.de_mio(data['ertrag'].get('budgeted'))}, "
            f"erwartet {geld.de_mio(data['ertrag'].get('forecast'))}; Aufwendungen: "
            f"geplant {geld.de_mio(data['aufwand'].get('budgeted'))}, erwartet "
            f"{geld.de_mio(data['aufwand'].get('forecast'))}")
    if len(data.get("verlauf") or []) > 1:
        lauf = ", ".join(f"{_de_tag(v['as_of'])}: {geld.de_mio(v['forecast'])}"
                         for v in data["verlauf"])
        zeilen.append(f"- Wie sich die Erwartung im Jahr bewegte — {lauf}; alle "
                      "für denselben 31. Dezember, keine Zwischenergebnisse.")
    for r in data.get("bereiche") or []:
        zeilen.append(f"- Teilhaushalt {r['label']}: geplant "
                      f"{geld.de_mio(r.get('budgeted'))}, erwartet "
                      f"{geld.de_mio(r.get('forecast'))}")
    f = data.get("finanzhaushalt")
    if f:
        zeilen.append(f"- {_ERGEBNIS_WORT['cash']} (Finanzhaushalt): geplant "
                      f"{geld.de_mio(f.get('budgeted'))}, erwartet "
                      f"{geld.de_mio(f.get('forecast'))} — anderes Zahlenwerk "
                      "als der Ergebnishaushalt, nicht addieren.")
    if data.get("plan_basis") == "budget_plus_carryover":
        zeilen.append(f"- {_BASIS_SATZ}")
    return (f"\nHAUSHALTSVOLLZUG {data['year']} (Finanz- und Leistungsbericht an "
            "den Finanz-\nausschuss, § 31 KomHKVO). Für Jahre ohne "
            "Jahresabschluss die einzige Quelle\ndazu, wie der Haushalt gegen "
            "seinen Plan läuft.\nES IST EINE ERWARTUNG, KEIN IST: „Stand 30.06.“ "
            "ist der Tag, an dem die Ämter\nihre Prognose für den 31. Dezember "
            "abgegeben haben, kein Halbjahresergebnis —\nwas bis dahin gebucht "
            "war, sagt der Bericht nirgends. Schreibe „erwartet“, nie\n"
            "„tatsächlich“, „ausgegeben“ oder „eingenommen“; das steht erst im "
            "Jahres-\nabschluss, und der kommt zwei Jahre später.\nGeltung: "
            "Kernverwaltung, dreizehn Teilhaushalte — die Eigenbetriebe "
            "berichten\ngetrennt. Einzelne Vorhaben nennt der Bericht nicht. "
            "NIE mit [id]:\n"
            + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME,
    methode="execution_context",
    erkennen=recognize,
    block=block,
    mixin=Store,
    rang=10,
    grenze=1900,
    probefrage="Wie läuft der Haushalt im laufenden Jahr?",
)
