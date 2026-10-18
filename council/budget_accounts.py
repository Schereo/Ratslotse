"""Die Kontenebene der Teilhaushalte — was die Stadt mit Parkgebühren einnimmt.

Die Haushalts-Tabellen kannten bis 10/2026 drei Ebenen: den Gesamthaushalt
(Posten 1–25), die Teilhaushalte (THH01–13) und die Produkte. Eine
Bürgerfrage wie „Wie viel nimmt die Stadt mit Parkgebühren ein?" traf keine
davon: Parkgebühren sind ein **Sachkonto** (33211000), und Sachkonten standen
nirgends. Die KI-Frage fand die Zahl nur zufällig über den Anlagentext, für
den falschen Jahrgang und ohne zu wissen, welche Spalte welches Jahr ist —
und bog bei der Frage nach Soll und Ist auf die Gewerbesteuer ab (Auswertung
der echten Fragen vom 11.10.2026).

Die Zahlen stehen in denselben Anlagen, aus denen die Produktebene kommt
(``finanzquellen.lies_teilhaushalte``): Jeder Teilhaushalts-Plan beginnt mit
dem Teilergebnishaushalt des ganzen THH, Konto für Konto::

    Teilergebnishaushalt  THH08: Verkehr und Straßenbau
    Erträge und Aufwendungen Ergebnis 2024 | Ansatz 2025 | … | Ansatz 2029
    33211000 Parkgebühren 4.482.612,19 4.394.100 4.394.100 5.228.979 5.228.979 5.228.979
    33211004 Parkgebühren VWG 310.149,12 354.000 354.000 354.000 354.000 354.000
    33219000 Sonstige
    Benutzungsgebühren
    347.330,96 450.000 450.000 450.000 450.000 450.000
    …
    05. öffentlich-rechtliche Entgelte 5.244.578,59 5.198.100 …

**Die Probe ist die Postensumme.** Die Konten stehen VOR der Zeile ihres
Postens, und die Postenzeile ist ihre Summe — Spalte für Spalte, bis auf die
Rundung der Ansätze (volle Euro je Konto). Was diese Rechnung nicht besteht, kommt nicht in die Datenbank.

**Die Falle sind Teilzeilen.** Ein Konto ohne Wert in einer Spalte hat dort
keine Null, sondern nichts: „31400000 Zuweisungen … Bund 80.000" (Plan 2019)
sagt nicht, in welcher der fünf Ansatzspalten die 80.000 stehen. Zwei Regeln
grenzen das ein — das Ergebnis trägt immer Cent („19.373,23"), die Ansätze
nie —, den Rest entscheidet die Postensumme: Für jede Teilzeile werden die
möglichen Spaltenlagen durchprobiert, und übernommen wird ein Posten nur,
wenn **genau eine** Kombination alle Spalten aufgehen lässt. Bei 80.000 ist
das eindeutig: 104.493 − 24.493 in der Spalte 2019 und sonst nirgends.

Gelesen wird nur die THH-Tabelle, nicht die Produkt-Tabellen dahinter: Ein
Konto steht dort ein zweites Mal je Produkt, und die Summe über den THH ist
die Zahl, nach der gefragt wird.
"""
from __future__ import annotations

import itertools
import re

from council.finanzberichte import thh_kopfspalten

#: Name der Probe in der Herkunft.
POSTEN_SUM = "budget_accounts_posten_sum"
CITATION = ("Teilergebnishaushalt des Teilhaushalts, Kontenzeilen — jede mit der "
            "Summenzeile ihres Postens nachgerechnet")

#: Beginn eines Kontos: achtstellige Kontonummer, dahinter (meist) die Bezeichnung.
_ACCOUNT = re.compile(r"^[ \t]*(\d{8})(?:[ \t]+(.*))?$")
#: Eine Postenzeile: „05. öffentlich-rechtliche Entgelte …", „20. = Summe …".
#: ``(?!\d)`` — sonst gälte „38.949.730,76" als Posten 38.
_POSTEN = re.compile(r"^[ \t]*(\d\d)\.(?!\d)[ \t]*(.*)$")
_AMOUNT = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")
#: Zahlen am Zeilenende — die Bezeichnung davor ist Text.
_TRAILING = re.compile(r"((?:[ \t]+|^)-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?)+[ \t]*$")
_PAGE_HEADER = re.compile(r"^[ \t]*Teil(?:ergebnis|finanz)haushalt\b")
_HEADER_REST = re.compile(r"^[ \t]*(?:Erträge und Aufwendungen|Ergebnis 20\d\d|Ansatz 20\d\d|"
                          r"- Euro -|Ordentliche (?:Erträge|Aufwendungen)|Außerordentliche)\b")
_PAGE_NO = re.compile(r"\d{1,4}")
_THH = re.compile(r"Teilergebnishaushalt\s+THH\s?(\d+)\s*:\s*([^\n]+)")

#: Ab so vielen Kombinationen wird ein Posten nicht durchprobiert, sondern
#: verworfen. Der größte echte Posten (Plan 2026, THH02, Posten 7: sieben
#: Teilzeilen) hat 78.125; alle 115 Pläne zusammen lesen sich in 2–3 Sekunden.
_MAX_COMBINATIONS = 200_000

#: Postennummer → Art. 01–11 Erträge, 13–19 Aufwendungen, 22/23 die
#: außerordentlichen, 26/27 die internen Leistungsbeziehungen.
_KIND = {**{n: "revenue" for n in range(1, 12)}, **{n: "expense" for n in range(13, 20)},
         22: "revenue", 23: "expense", 26: "internal_revenue", 27: "internal_expense"}


def _cents(s: str) -> int:
    """„1.450.790,37" → 145079037 — gerechnet wird in Cent, nie in float."""
    negative = s.startswith("-")
    euros, _, cents = s.lstrip("-").replace(".", "").partition(",")
    v = int(euros) * 100 + int((cents or "0").ljust(2, "0")[:2])
    return -v if negative else v


def _split(line: str) -> tuple[str, list[str]]:
    """Eine Zeile in (Text, Zahlen am Ende)."""
    m = _TRAILING.search(line)
    if not m:
        return line.strip(), []
    return line[:m.start()].strip(), _AMOUNT.findall(m.group(0))


def _positions(values: list[str], columns: int) -> list[tuple[int, ...]]:
    """Alle Spaltenlagen, in denen diese Werte stehen können.

    Das Ergebnis (Spalte 0) trägt Cent, die Ansätze (1 …) nie — das ist im
    Bestand ausnahmslos so und schließt die meisten Lagen schon aus."""
    if len(values) > columns:
        return []
    return [pos for pos in itertools.combinations(range(columns), len(values))
            if all(("," in v) == (i == 0) for i, v in zip(pos, values))]


def _table_lines(text: str) -> list[str]:
    """Die Zeilen der THH-Tabelle, ohne Seitenköpfe und Seitenzahlen.

    Die Tabelle beginnt am ersten „Teilergebnishaushalt THHnn: …" ohne
    Produktzeile und endet am Teilfinanzhaushalt oder am ersten Produkt."""
    raw = text.split("\n")
    start = None
    for i, line in enumerate(raw):
        if _THH.search(line):
            following = [x.strip() for x in raw[i + 1:i + 3] if x.strip()]
            if following and following[0].startswith("Erträge und Aufwendungen"):
                start = i
                break
    if start is None:
        return []
    out: list[str] = []
    i = start
    while i < len(raw):
        line = raw[i]
        s = line.strip()
        if s.startswith("Teilfinanzhaushalt"):
            break
        if _PAGE_HEADER.match(line):
            after = [x.strip() for x in raw[i + 1:i + 3] if x.strip()]
            if after and after[0].startswith("Produkt:"):
                break     # ein Produkt beginnt: Ende der THH-Tabelle
            # Seitenkopf: er selbst und die Spaltenbeschriftung fallen, die
            # Seitenzahl davor auch.
            while out and _PAGE_NO.fullmatch(out[-1]):
                out.pop()
            i += 1
            while i < len(raw) and (not raw[i].strip() or _HEADER_REST.match(raw[i])):
                i += 1
            continue
        if s and not _HEADER_REST.match(line):
            out.append(s)
        i += 1
    while out and _PAGE_NO.fullmatch(out[-1]):
        out.pop()
    return out


def _entries(lines: list[str]) -> list[dict]:
    """Zeilen zu Einträgen bündeln: Konto oder Posten, mit der Bezeichnung
    über mehrere Zeilen und den Zahlen, wo immer sie stehen."""
    entries: list[dict] = []
    current: dict | None = None
    for line in lines:
        m = _ACCOUNT.match(line) or _POSTEN.match(line)
        if m:
            if current:
                entries.append(current)
            label, values = _split(m.group(2) or "")
            account = m.re is _ACCOUNT
            current = {"type": "account" if account else "posten",
                       "nr": m.group(1) if account else int(m.group(1)),
                       "label": label, "values": values}
            continue
        if current is None:
            continue
        if current["values"]:
            # Nach den Zahlen kommt nichts mehr zu diesem Eintrag.
            entries.append(current)
            current = None
            continue
        label, values = _split(line)
        if label:
            current["label"] = f"{current['label']} {label}".strip()
        current["values"] = values
    if current:
        entries.append(current)
    return entries


def _solve(accounts: list[dict], total: list[str], columns: int) -> list[tuple | None] | None:
    """Die Spaltenlage je Konto, mit der die Postensumme aufgeht.

    ``None``, wenn keine Kombination aufgeht. Gehen mehrere auf, bekommt ein
    Konto seine Lage nur, wenn sie in ALLEN Lösungen dieselbe ist; sonst
    steht an seiner Stelle ``None`` (gemessen: zwei Konten mit identischer
    Teilzeile „50 50 50 50", Plan 2026 THH02 — vertauschbar, also nicht zu
    entscheiden, die übrigen fünfzehn Konten des Postens aber schon)."""
    total_positions = _positions(total, columns)
    account_positions = [_positions(a["values"], columns) for a in accounts]
    if not total_positions or any(not p for p in account_positions):
        return None
    n = len(total_positions)
    for p in account_positions:
        n *= len(p)
        if n > _MAX_COMBINATIONS:
            return None
    account_cents = [[_cents(v) for v in a["values"]] for a in accounts]
    total_cents = [_cents(v) for v in total]
    # Das Ergebnis steht auf den Cent; die Ansätze sind je Konto auf volle
    # Euro gerundet, die Postensumme aus den ungerundeten Werten gebildet:
    # 10.181.036 gegen 10.181.037 (Plan 2026, THH08, Posten 3). Dort ein
    # halber Euro je Konto plus ein Euro.
    tolerance = [2] + [100 + 50 * len(accounts)] * (columns - 1)
    solutions: list[tuple] = []
    for t_pos in total_positions:
        expected = [0] * columns
        for i, v in zip(t_pos, total_cents):
            expected[i] = v
        for combo in itertools.product(*account_positions):
            got = [0] * columns
            for pos, cents in zip(combo, account_cents):
                for i, v in zip(pos, cents):
                    got[i] += v
            if all(abs(g - x) <= t for g, x, t in zip(got, expected, tolerance)):
                solutions.append(combo)
    if not solutions:
        return None
    return [pos if all(s[k] == pos for s in solutions) else None
            for k, pos in enumerate(solutions[0])]


def parse(text: str) -> dict | None:
    """Ein Teilhaushalts-Plan → seine Konten.

    Rückgabe ``{"sub_budget_no", "sub_budget_name", "columns", "accounts",
    "posten_ok", "posten_rejected"}`` oder ``None``, wenn das Dokument keine
    THH-Tabelle mit lesbarem Kopf trägt. ``accounts``: je Konto
    ``account_no``, ``label``, ``posten_nr``, ``posten_label``, ``kind`` und
    ``values`` — ``{(art, jahr): euro}`` nur für die Spalten, in denen das
    Dokument einen Wert druckt (``art`` ist „Ergebnis" oder „Ansatz")."""
    header = thh_kopfspalten(text)
    m = _THH.search(text or "")
    if len(header) < 3 or not m:
        return None
    columns = len(header)
    accounts: list[dict] = []
    posten_ok: list[int] = []
    rejected: list[dict] = []
    pending: list[dict] = []
    for e in _entries(_table_lines(text)):
        if e["type"] == "account":
            pending.append(e)
            continue
        if not pending:
            continue     # Summen- und Ergebniszeilen, leere Posten
        if not e["values"]:
            # Ein Posten ohne Zahl, aber mit Konten davor: Die Zuordnung
            # stimmt nicht — nichts übernehmen.
            rejected.append({"posten": e["nr"], "reason": "Postenzeile ohne Betrag"})
            pending = []
            continue
        solved = _solve(pending, e["values"], columns)
        if solved is None:
            rejected.append({"posten": e["nr"], "label": e["label"],
                             "reason": "Postensumme geht nicht eindeutig auf"})
        else:
            unclear = [a["nr"] for a, pos in zip(pending, solved) if pos is None]
            if unclear:
                rejected.append({"posten": e["nr"], "accounts": unclear,
                                 "reason": "Spaltenlage nicht eindeutig"})
            for a, pos in zip(pending, solved):
                if pos is None:
                    continue
                accounts.append({
                    "account_no": a["nr"],
                    "label": re.sub(r"\s+", " ", a["label"]).strip(),
                    "posten_nr": e["nr"],
                    "posten_label": re.sub(r"\s+", " ", e["label"]).lstrip("= ").strip(),
                    "kind": _KIND.get(e["nr"]),
                    "values": {header[i]: _cents(v) / 100 for i, v in zip(pos, a["values"])},
                })
            posten_ok.append(e["nr"])
        pending = []
    return {"sub_budget_no": int(m.group(1)), "sub_budget_name": m.group(2).strip(),
            "columns": header, "accounts": accounts,
            "posten_ok": posten_ok, "posten_rejected": rejected}
