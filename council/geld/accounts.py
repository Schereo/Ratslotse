"""Die Kontenebene — was eine einzelne Einnahme- oder Ausgabeart bringt.

„Wie hoch sind die Einnahmen durch die Parkgebühren im Jahr?" fragt nach
einem Sachkonto (33211000 im Teilhaushalt 08). Bis 10/2026 kannte die
KI-Frage nur Teilhaushalte, Produkte und den Gesamthaushalt; die Parkgebühren
stehen in keinem davon. Die Antworten der echten Fragen vom 10.10.2026
nannten deshalb einen Ansatz aus dem Entwurf 2023 als „letzten Haushalt",
und auf „Kann man Abweichungen sehen von Soll und Ist?" kam die Gewerbesteuer.

Quelle ist ``council_budget_accounts`` (``council/budget_accounts.py``): je
Haushaltsplan und Teilhaushalt alle Konten mit Ergebnis, Ansätzen und
Finanzplanung. Derselbe Jahrgang steht in mehreren Plänen, und welche Zahl
gemeint ist, entscheidet diese Facette:

* **Ist** — das Ergebnis, das der Plan zwei Jahre später nennt.
* **Ansatz (beschlossen)** — der fortgeschriebene Vorjahresansatz im Plan
  des Folgejahres. Er kann vom Entwurf deutlich abweichen: Parkgebühren 2023
  standen im Entwurf mit 3,74 Mio. €, im Plan 2024 mit 2,65 Mio. €.
* **Ansatz (Entwurf)** — für das jüngste Jahr, das noch kein Folgeplan
  fortschreibt.
* **Finanzplanung** — die Jahre hinter dem Planjahr.

Ausgelöst wird die Facette von jeder Geldfrage; ob sie etwas beiträgt,
entscheidet der Begriffsabgleich gegen die Kontenbezeichnungen. Ohne
Treffer bleibt der Prompt so, wie er war.
"""
from __future__ import annotations

import re
import sqlite3

from council import geld
from kern.dbfehler import tabelle_fehlt
from council.store_basis import StoreBasis

NAME = "accounts"

#: Eine Geldfrage — gefaltet. Nur Wörter, die von Geld sprechen: „Wie
#: viele Anträge …?" und „Was ist am Fliegerhorst geplant?" sind keine, und
#: eine Frage ohne Geldbezug darf keine Haushaltsabfrage auslösen
#: (``test_negativfaelle_fassen_die_datenbank_nicht_an``).
_GELD = re.compile(
    r"einnahm|eingenommen|einnimmt|nimmt [^.?!]{0,25}\bein\b|\bertra|ertraeg|ausgab|"
    r"ausgeb|ausgegeben|\bkost|kosten\b|aufwend|haushalt|\bansatz|\betat\b|budget|"
    r"\bsoll\b|veranschlagt|eingeplant|\bmio\b|million|\beuro\b|\bbringt|\bbringen|"
    r"gezahlt|mehreinnahm|gebuehr|\bgeld\b")

#: Wörter, die in Kontenbezeichnungen stehen, aber keine Einnahme- oder
#: Ausgabeart auswählen — gefaltet, als Wortanfang. „Einnahmen" fände sonst
#: nichts Bestimmtes, „sonstige" Hunderte Konten.
_KEIN_KONTO = ("einnahm", "eingenommen", "ertra", "ertrae", "aufwend", "ausgab", "ausgeb",
               "haushalt", "kosten", "betrag", "summe", "sonstig", "ansatz", "ansaetz",
               "ergebnis", "abweich", "prognos", "mehreinnahm", "mindereinnahm", "erhoeh",
               "geplant", "tatsaech", "letzt", "jaehr", "gesamt", "hoehe", "soll",
               # Gattungen, die als Wort in vielen Bezeichnungen stehen, aber
               # nach einer ANDEREN Ebene fragen: „Was kostet das Personal der
               # Feuerwehr?" meint das Produkt, nicht „Sonstige Personal- u.
               # Versorgungsaufwendungen" im Personalamt.
               "personal")

#: Ein Begriff, der mehr Konten trifft, ist kein Begriff, sondern eine Gattung
#: („Gebühren", „Zuweisungen") — er wählt nichts aus und fällt weg.
_MAX_KONTEN_JE_BEGRIFF = 12
_MAX_KONTEN = 3

_ART = {"revenue": "Ertrag", "expense": "Aufwand",
        "internal_revenue": "Ertrag aus internen Leistungen",
        "internal_expense": "Aufwand aus internen Leistungen"}


#: Wo eine dieser Facetten anschlägt, ist es eine Geldfrage — gleich, wie sie
#: formuliert ist („Wie teuer ist …", „Was gibt die Stadt für … aus?").
_ANDOCKEN = {"plan", "ansatz", "ist", "produkte", "fees", "taxes"}


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    return bool(_GELD.search(text)) or bool(facets & _ANDOCKEN)


def _begriffe(terms: list[str]) -> list[str]:
    out = []
    for t in terms:
        f = geld.falte(t)
        if len(f) < 5 or " " in f or geld.allerwelt(f) or f.startswith(_KEIN_KONTO):
            continue
        if f in ("gebuehr", "gebuehren"):
            continue
        out.append(t)
    return list(dict.fromkeys(out))


def _worte(text: str) -> list[str]:
    return geld.falte(text).split()


def _stamm(wort: str) -> str:
    """„Bußgeldern" → „bussgeld", „Mieten" → „miet" — eine Endung ab."""
    w = geld.falte(wort)
    for endung in ("ern", "en", "er", "es", "e", "n", "s"):
        if w.endswith(endung) and len(w) - len(endung) >= 4:
            return w[:-len(endung)]
    return w


def _guete(label: str, begriff: str) -> int:
    """Wie gut trifft ``begriff`` die Kontenbezeichnung? 3 = sie heißt so
    (oder beginnt so: „Parkgebühren VWG"), 2 = ein ganzes Wort darin
    („Mieten, Pachten, …"), 1 = ein Wortteil ab fünf Zeichen
    („Bußgeldern" in „Verwarn-/Bußgelder …"), 0 = nichts."""
    b = _worte(begriff)
    w = _worte(label)
    if not b or not w:
        return 0
    if w[:len(b)] == b:
        return 3
    if all(x in w for x in b) or (len(b) == 1 and _stamm(b[0]) in {_stamm(x) for x in w}):
        return 2
    stamm = _stamm(begriff)
    if len(stamm) >= 5 and any(stamm in x for x in w):
        return 1
    return 0


class Store(StoreBasis):
    """Mixin für ``CouncilStore`` — die Konten, deren Name die Frage trifft."""

    def budget_accounts_context(self, terms: list[str],
                                year: int | None = None) -> dict | None:
        begriffe = _begriffe(terms)
        if not begriffe:
            return None
        try:
            # Je Kontonummer die Bezeichnung aus dem jüngsten Plan.
            konten = [dict(r) for r in self._conn.execute(
                "SELECT account_no, label FROM council_budget_accounts a "
                "WHERE plan_year = (SELECT MAX(plan_year) FROM council_budget_accounts b "
                "WHERE b.account_no = a.account_no) GROUP BY account_no")]
        except sqlite3.OperationalError as fehler:
            if not tabelle_fehlt(fehler):
                raise
            return None
        # Je Konto: wie viele Begriffe treffen es, und wie gut? Ein Begriff,
        # der mehr als eine Handvoll Konten trifft, ist eine Gattung
        # („Unterhaltung", „Reinigung") und wählt nichts aus. Gewertet wird
        # (Zahl der Begriffe, beste Trefferstufe), und nur die beste Wertung
        # bleibt — „Parkgebühren" ist ein KONTO dieses Namens, ein Wortteil
        # anderswo daneben ist Beifang.
        wertung: dict[str, tuple[int, int]] = {}
        for b in begriffe:
            hier = [(k["account_no"], _guete(k["label"], b)) for k in konten]
            hier = [(nr, g) for nr, g in hier if g]
            if len(hier) > _MAX_KONTEN_JE_BEGRIFF:
                continue
            for nr, g in hier:
                n, q = wertung.get(nr, (0, 0))
                wertung[nr] = (n + 1, max(q, g))
        if not wertung:
            return None
        beste = max(wertung.values())
        aus = [r for r in (self._konto_reihe(nr) for nr, w in wertung.items() if w == beste) if r]
        if not aus:
            return None
        # Das größere Konto zuerst: „Parkgebühren" trifft auch „Parkgebühren
        # VWG" (0,3 Mio. €) — die Frage meint die 4,5 Mio. €.
        aus.sort(key=lambda r: -abs(r["size"]))
        return {"accounts": aus[:_MAX_KONTEN], "asked_year": year,
                "more": max(0, len(aus) - _MAX_KONTEN), "match": beste[1]}

    def _konto_reihe(self, account_no: str) -> dict | None:
        """Ein Konto über ALLE Teilhaushalte, in denen es geführt wird.

        „Strom" steht in elf Teilhaushalten mit je einem Teilbetrag; die Frage
        „Was gibt die Stadt für Strom aus?" meint die Summe. Bei den
        Parkgebühren ist es ein Teilhaushalt mit 4,5 Mio. € und einer mit
        174 € — die Summe ist dieselbe Zahl."""
        rows = [dict(r) for r in self._conn.execute(
            "SELECT plan_year, sub_budget_no, sub_budget_name, label, posten_label, kind, "
            "year, column_kind, amount, herkunft_id FROM council_budget_accounts "
            "WHERE account_no = ? ORDER BY plan_year", (account_no,))]
        if not rows:
            return None
        juengster = max(r["plan_year"] for r in rows)
        # Je (Plan, Spalte, Jahr) die Summe über die Teilhaushalte.
        summe: dict[tuple, float] = {}
        je_thh: dict[int, float] = {}
        for r in rows:
            key = (r["plan_year"], r["column_kind"], r["year"])
            summe[key] = summe.get(key, 0.0) + r["amount"]
            if r["plan_year"] == juengster and r["column_kind"] == "actual":
                je_thh[r["sub_budget_no"]] = je_thh.get(r["sub_budget_no"], 0.0) + r["amount"]
        namen = {r["sub_budget_no"]: r["sub_budget_name"] for r in rows}
        ist: dict[int, float] = {}
        entwurf: dict[int, float] = {}
        beschlossen: dict[int, float] = {}
        for (plan, art, y), v in sorted(summe.items()):   # der jüngste Plan gewinnt
            if art == "actual":
                ist[y] = v
            elif y == plan:
                entwurf[y] = v
            elif y == plan - 1:
                beschlossen[y] = v
        planung = {y: v for (plan, art, y), v in sorted(summe.items())
                   if plan == juengster and art == "budget" and y > juengster}
        # Der Ansatz eines Jahres: wie beschlossen, wo ein Folgeplan ihn
        # fortschreibt; sonst der Entwurf.
        ansatz = {y: (v, "adopted") for y, v in beschlossen.items()}
        for y, v in entwurf.items():
            ansatz.setdefault(y, (v, "draft"))
        vergleich = [{"year": y, "plan": ansatz[y][0], "plan_kind": ansatz[y][1],
                      "actual": ist[y]} for y in sorted(ist) if y in ansatz]
        werte = [v for _, v in sorted(ist.items())] or [v for _, (v, _) in sorted(ansatz.items())]
        thh = sorted(je_thh, key=lambda n: -abs(je_thh[n])) or sorted(namen)
        # Bezeichnung und Beleg vom Teilhaushalt mit dem größten Anteil — die
        # zuletzt gelesene Zeile wäre bei den Parkgebühren der THH09 (174 €).
        kopf = next((r for r in reversed(rows)
                     if r["plan_year"] == juengster and r["sub_budget_no"] == thh[0]),
                    rows[-1])
        return {"account_no": account_no, "label": kopf["label"],
                "posten_label": kopf["posten_label"], "kind": kopf["kind"],
                "sub_budgets": [{"no": n, "name": namen.get(n)} for n in thh],
                "actual": dict(sorted(ist.items())),
                "budget": {y: list(v) for y, v in sorted(ansatz.items())},
                "planning": dict(sorted(planung.items())), "planning_from": juengster,
                "comparison": vergleich,
                "size": werte[-1] if werte else 0,
                "beleg": self._beleg(kopf.get("herkunft_id"))}


def _spanne(je_jahr: dict) -> str:
    """„2017–2024" — das Jahr gehört in die Beschriftung VOR dem Doppelpunkt
    (``tests/test_geld_gliederung.py``: jede eingerückte Zahl unter ihrem
    eigenen Jahr)."""
    jahre = sorted(je_jahr)
    return str(jahre[0]) if len(jahre) == 1 else f"{jahre[0]}–{jahre[-1]}"


def _betrag(v: float) -> str:
    return geld.de_betrag(v)


def _konto_block(k: dict, asked: int | None) -> list[str]:
    art = _ART.get(k.get("kind") or "", "Konto")
    thh = k["sub_budgets"]
    wo = (f"Teilhaushalt {thh[0]['no']:02d} {thh[0]['name']}" if len(thh) == 1 else
          f"Summe über {len(thh)} Teilhaushalte, am meisten in {thh[0]['no']:02d} {thh[0]['name']}")
    zeilen = [f"- {k['label']} (Konto {k['account_no']}, {wo}; {art}"
              + (f" unter „{k['posten_label']}“" if k.get("posten_label") else "") + "):"]
    if k["actual"]:
        zeilen.append(f"  - Ist (Rechnungsergebnis) {_spanne(k['actual'])}: " + "; ".join(
            f"{y}: {_betrag(v)}" for y, v in k["actual"].items()))
    if k["budget"]:
        zeilen.append(f"  - Ansatz {_spanne(k['budget'])}: " + "; ".join(
            f"{y}: {_betrag(v)}" + (" (Entwurf)" if art_ == "draft" else "")
            for y, (v, art_) in k["budget"].items()))
    if k["planning"]:
        zeilen.append(f"  - Finanzplanung {_spanne(k['planning'])} (Plan {k['planning_from']}): " + "; ".join(
            f"{y}: {_betrag(v)}" for y, v in k["planning"].items()))
    vergleich = k["comparison"][-4:]
    if asked is not None and asked not in [c["year"] for c in vergleich]:
        vergleich = [c for c in k["comparison"] if c["year"] == asked] + vergleich
    if vergleich:
        teile = []
        for c in vergleich:
            diff = c["actual"] - c["plan"]
            pct = f", {'+' if diff >= 0 else '−'}{geld.de_prozent(abs(diff) / abs(c['plan']) * 100)}" \
                if c["plan"] else ""
            teile.append(f"{c['year']}: Ansatz {_betrag(c['plan'])}"
                         + (" (Entwurf)" if c["plan_kind"] == "draft" else "")
                         + f", Ist {_betrag(c['actual'])} → "
                         f"{'+' if diff >= 0 else '−'}{_betrag(abs(diff))}{pct}")
        zeilen.append(f"  - Soll und Ist {_spanne({c['year']: 0 for c in vergleich})}: "
                      + "; ".join(teile))
    return zeilen


def block(data: dict | None) -> str:
    if not data or not data.get("accounts"):
        return ""
    zeilen: list[str] = []
    for k in data["accounts"]:
        zeilen += _konto_block(k, data.get("asked_year"))
    if data.get("more"):
        zeilen.append(f"- (weitere {data['more']} Konten mit ähnlichem Namen nicht aufgeführt)")
    beleg = data["accounts"][0].get("beleg")
    return ("\nKONTENEBENE DER TEILHAUSHALTE (einzelne Einnahme- und Ausgabearten aus den\n"
            "Haushaltsplänen, Konto für Konto). Fragt jemand nach einer einzelnen Einnahme oder\n"
            "Ausgabe (Parkgebühren, Mieten, Straßenunterhaltung …) und nennt die Bezeichnung\n"
            "unten genau diese Sache, ist DAS die Antwort — Steuer- und Gesamthaushalts-Zahlen\n"
            "betreffen andere Konten, nie auf sie ausweichen. Meint die Bezeichnung etwas\n"
            "anderes als die Frage, lass den Baustein weg.\n"
            "„Ist“ ist das Rechnungsergebnis; „Ansatz“ ist der beschlossene Plan (wie ihn der\n"
            "Plan des Folgejahres fortschreibt), „(Entwurf)“ der eingebrachte, noch nicht\n"
            "fortgeschriebene Ansatz; „Finanzplanung“ sind Planzahlen künftiger Jahre. Nenne zu\n"
            "jeder Zahl Jahr und Art. Ein Jahr ohne Ist hat noch keinen Abschluss — sag das,\n"
            "statt eine Planzahl als Ergebnis auszugeben. Nie mit [id]"
            + geld.beleg_text(beleg) + ":\n" + "\n".join(zeilen) + "\n")


FACETTE = geld.Facette(
    name=NAME, methode="budget_accounts_context", erkennen=recognize, block=block,
    mixin=Store, rang=12, grenze=2600,
    probefrage="Wie hoch sind die Einnahmen der Stadt Oldenburg durch Parkgebühren im Jahr?")
