"""Quizfragen, die aus den eigenen Daten entstehen statt aus einem Modell.

Zwei Formen, beide mit zwei Antworten und schnell gespielt:

- **verdict** (Angenommen oder abgelehnt?): ein echter Antrag einer Fraktion
  oder Gruppe, man tippt auf den Ausgang. Quelle sind die Beschlüsse mit
  ihrem Ergebnis; der Antragsteller kommt aus dem **Titel**, den das
  Ratsinformationssystem setzt („… (Fraktion WFO-LKR vom 28.12.2018)“),
  nicht aus der Spalte ``factions`` — die füllt ein Modell beim
  Protokoll-Lesen, und dort stand beim Stadion-Rechtsgutachten, einer
  Vorlage der Verwaltung, „CDU, Bündnis 90/Die Grünen“.
- **compare** (Wofür gibt Oldenburg mehr aus?): zwei Haushaltsprodukte aus
  ``council_products`` nebeneinander. Die Produkte sind von Hand ausgesucht
  und benannt — „BgA Rettungsdienst“ oder „Unterh. von öffentlichem Grün“
  versteht niemand, und Paare wie Asylbewerberleistungen gegen Sportförderung
  gehören nicht in ein Spiel.

Beide sind deterministisch: kein Modell, keine Kosten, stabile Schlüssel. Ein
zweiter Lauf legt nichts doppelt an und frischt Texte und Zahlen auf
(``refresh_quiz_payloads``), wenn ein neues Haushaltsjahr kommt.

Die ausgelieferte iOS-App kennt ``format`` nicht und zeigt die Fragen als
Multiple Choice mit zwei Antworten — das trägt, weil beide Formen genau das
sind.
"""
from __future__ import annotations

import hashlib
import json
import re

#: Gebiet der Antrags-Fragen (``_THEMA_LABELS`` in ``store_quiz`` kennt es).
VERDICT_AREA = ("topic", "antraege")
#: Die Vergleichsfragen stehen beim Haushalt, wo man sie sucht.
COMPARE_AREA = ("topic", "haushalt")

VERDICT_OPTIONS = ["Angenommen", "Abgelehnt"]

# --- Angenommen oder abgelehnt? ---------------------------------------------

#: Ab diesem Gesprächswert (``interest``, 0–100) taugt ein Antrag als Frage.
VERDICT_MIN_INTEREST = 40
#: Höchstens so viele angenommene je abgelehntem Antrag. Im Bestand werden
#: vier von fünf Anträgen angenommen (81 zu 20 ab Gesprächswert 40); wer immer
#: „angenommen“ tippt, gewönne sonst fast jede Runde.
VERDICT_ACCEPTED_PER_REJECTED = 1.5

# „(Fraktion WFO-LKR vom 28.12.2018)“, „(Antrag der Fraktion Die Linke. vom …)“,
# „(Gruppe Die Linke./Piratenpartei vom 08.01.2018, Verweisung aus Rat …)“
_PROPOSER_PAREN = re.compile(
    r"\s*\((?:Antrag (?:der |des )?)?"
    r"((?:Fraktion|Fraktionen|Gruppe|Gruppen)\b[^()]*?)"
    r"(?:,?\s+vom\s+(\d{1,2}\.\d{1,2}\.(\d{4}))[^()]*)?\)")
# „Antrag der Fraktion BSW: Einführung eines Schulfachs …“
_PROPOSER_PREFIX = re.compile(r"^Antrag (?:der |des )?((?:Fraktion|Fraktionen|Gruppe)\b[^:]*?):\s*")
# Anhängsel des RIS-Titels, die nichts über den Inhalt sagen.
_TAIL = re.compile(r"\s*[-–]\s*(Beschluss(?:antrag)?|Beschlussvorschlag|Antrag)\s*$")
_TAIL_DATED = re.compile(r"\s*[-–]\s*[^-–]{0,40}\d{1,2}\.\d{1,2}\.\d{4}\s*$")
#: Kein Spiel: Berichte zu einem Antrag (der Ausgang ist dort Kenntnisnahme),
#: Resolutionen und Solidaritätsbekundungen (die nimmt der Rat fast immer an).
_SKIP = re.compile(r"Bericht|Resolution|Solidarit|Dringlichkeitsantrag", re.IGNORECASE)


def parse_motion(title: str) -> dict | None:
    """Antragsteller, Antragsjahr und Kern aus einem RIS-Titel — oder ``None``,
    wenn der Titel keinen Antrag einer Fraktion oder Gruppe nennt."""
    if not title or _SKIP.search(title):
        return None
    year = None
    m = _PROPOSER_PAREN.search(title)
    if m:
        proposer = m.group(1).strip().rstrip(",")
        year = int(m.group(3)) if m.group(3) else None
        core = (title[:m.start()] + title[m.end():]).strip()
    else:
        m = _PROPOSER_PREFIX.match(title)
        if not m:
            return None
        proposer = m.group(1).strip()
        core = title[m.end():].strip()
    # Ein Nachsatz wie „, Verweisung aus Rat am 22.01.2018“ bleibt sonst am
    # Namen hängen.
    proposer = re.split(r",\s*(?:Verweisung|Änderung|Ergänzung)", proposer)[0].strip()
    proposer = re.sub(r"\s*/\s*", "/", proposer)  # „Bündnis 90/ Die Grünen“
    core = _TAIL.sub("", core)
    core = _TAIL_DATED.sub("", core)
    core = core.strip(" \"„“”'").strip()
    if len(core) < 12 or len(proposer) < 6:
        return None
    return {"proposer": proposer, "year": year, "core": core}


def _plural(proposer: str) -> bool:
    return bool(re.match(r"(Fraktionen|Gruppen)\b", proposer)) or " und " in proposer or "," in proposer


def _body(committee: str) -> str:
    """„der Rat“, „der Kulturausschuss“ — mit dem Artikel, den der Satz braucht."""
    if committee == "Rat":
        return "der Rat"
    if re.search(r"(kommission|konferenz|versammlung)$", committee, re.IGNORECASE):
        return f"die {committee}"
    return f"der {committee}"


def _key(*parts: object) -> str:
    """Stabiler content_hash — aus der Sache, nie aus dem Fragetext, damit ein
    Textfix dieselbe Zeile auffrischt statt eine zweite anzulegen."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def verdict_questions(store) -> list[dict]:
    """Die Antrags-Fragen: je Vorlage die abschließende Entscheidung (die des
    Rates, wenn es eine gibt, sonst die jüngste), ausgewogen zwischen
    angenommen und abgelehnt."""
    rows = store.quiz_motion_rows(VERDICT_MIN_INTEREST)
    finals: dict[object, tuple] = {}
    for r in rows:
        motion = parse_motion(r["title"])
        if not motion:
            continue
        key = r["template_number"] or f"id{r['id']}"
        rank = (r["committee"] == "Rat", r["session_date"] or "")
        if key not in finals or rank > finals[key][0]:
            finals[key] = (rank, r, motion)

    picked = sorted(finals.values(), key=lambda x: -(x[1]["interest"] or 0))
    rejected = [x for x in picked if x[1]["outcome"] == "rejected"]
    accepted = [x for x in picked if x[1]["outcome"] == "accepted"]
    accepted = accepted[:max(1, round(len(rejected) * VERDICT_ACCEPTED_PER_REJECTED))]

    out = []
    for _, r, motion in rejected + accepted:
        year = motion["year"] or int((r["session_date"] or "0000")[:4])
        verb = "beantragten" if _plural(motion["proposer"]) else "beantragte"
        body = _body(r["committee"])
        rejected_ = r["outcome"] == "rejected"
        how = "einstimmig" if r["vote"] == "unanimous" else "mehrheitlich"
        date = _german_date(r["session_date"])
        explanation = (f"{body[0].upper()}{body[1:]} hat den Antrag {date} {how} "
                       f"{'abgelehnt' if rejected_ else 'angenommen'}.")
        out.append({
            "area_type": VERDICT_AREA[0], "area_key": VERDICT_AREA[1],
            "category": "council_politics", "difficulty": "easy",
            "qtype": "mc", "format": "verdict",
            "question": (f"Die {motion['proposer']} {verb} {year}: „{motion['core']}“. "
                         f"Wie hat {body} entschieden?"),
            "options": list(VERDICT_OPTIONS), "correct_index": 1 if rejected_ else 0,
            "explanation": explanation,
            # Die Kurzfassung nur beim angenommenen Antrag: Bei einem
            # abgelehnten beschreibt sie womöglich den Vorschlag, als gälte er
            # (council/CLAUDE.md, „Ein Text über einen Beschluss kennt dessen
            # Ergebnis").
            "detail": None if rejected_ else ((r["simple_summary"] or "").strip()[:600] or None),
            "source_type": "ratsinfo", "source_ref": f"/council/decision?id={r['id']}",
            "content_hash": _key("verdict", r["template_number"] or r["id"]),
        })
    return out


def _german_date(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return ""
    y, m, d = iso[:10].split("-")
    return f"am {int(d)}.{int(m)}.{y}"


# --- Wofür gibt Oldenburg mehr aus? -----------------------------------------

#: Haushaltsprodukt → wie man es im Gespräch nennt. Bewusst eine Auswahl: nur
#: Leistungen, unter denen sich jede*r etwas vorstellen kann, und keine Paare,
#: die Hilfen für Menschen in Not gegen Freizeitangebote ausspielen.
PRODUCTS: dict[str, tuple[str, str]] = {
    # Produkt: (Antwort auf der Karte, „bei …“ für den Nachsatz)
    "P10.360001": ("Kitas und Kindertagespflege", "bei den Kitas"),
    "P10.210000": ("Betrieb der Schulen", "beim Schulbetrieb"),
    "P10.540002": ("Straßen, Wege und Plätze", "bei Straßen, Wegen und Plätzen"),
    "P10.126001": ("Feuerwehr", "bei der Feuerwehr"),
    "P10.127000": ("Rettungsdienst", "beim Rettungsdienst"),
    "P10.420000": ("Sportförderung", "bei der Sportförderung"),
    "P10.281002": ("Kulturförderung", "bei der Kulturförderung"),
    "P10.551200": ("Pflege von Parks und Grünflächen", "bei der Grünpflege"),
    "P10.122004": ("Melde- und Passwesen", "beim Melde- und Passwesen"),
    "P10.111011": ("Ratsarbeit", "bei der Ratsarbeit"),
    "P10.561100": ("Klimaschutz", "beim Klimaschutz"),
    "P10.272001": ("Stadtbibliothek", "bei der Stadtbibliothek"),
    "P10.263001": ("Musikschule", "bei der Musikschule"),
    "P10.541100": ("Verkehrsplanung", "bei der Verkehrsplanung"),
    "P10.553000": ("Friedhöfe", "bei den Friedhöfen"),
    "P10.573000": ("Wochenmärkte und Volksfeste", "bei Märkten und Volksfesten"),
    "P10.523000": ("Denkmalschutz", "beim Denkmalschutz"),
    "P10.571001": ("Wirtschaftsförderung", "bei der Wirtschaftsförderung"),
    "P10.522000": ("Förderung von Sozialwohnungen", "bei der Wohnraumförderung"),
}

#: Ein Paar taugt, wenn der größere Posten mindestens so viel mal größer ist —
#: darunter ist es Münzwurf — und höchstens so viel, sonst ist es geschenkt.
COMPARE_RATIO = (1.4, 8.0)
#: So viele Paare höchstens, und jedes Produkt in höchstens so vielen.
COMPARE_MAX = 24
COMPARE_PER_PRODUCT = 4


def _euro(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}".replace(".", ",") + " Mio. €"
    return f"{round(v / 1000) * 1000:,.0f}".replace(",", ".") + " €"


def _times(r: float) -> str:
    if r < 1.9:
        return f"rund {r:.1f}-mal so viel".replace(".", ",")
    return f"rund {round(r)}-mal so viel"


def compare_questions(store) -> list[dict]:
    """Paare von Haushaltsprodukten aus dem jüngsten Planjahr. Der Schlüssel
    kennt das Jahr nicht: Kommt ein neues, frischt der nächste Lauf dieselbe
    Frage mit den neuen Zahlen auf."""
    year, rows = store.quiz_product_rows(list(PRODUCTS))
    if year is None:
        return []
    by_no = {r["product_no"]: r for r in rows}
    nos = sorted(by_no)

    pairs = []
    for i, a in enumerate(nos):
        for b in nos[i + 1:]:
            hi, lo = sorted((by_no[a]["expenses"], by_no[b]["expenses"]), reverse=True)
            if COMPARE_RATIO[0] <= hi / lo <= COMPARE_RATIO[1]:
                pairs.append((a, b))
    # Deterministisch gemischt, damit nicht immer die ersten Produkte dran sind.
    pairs.sort(key=lambda p: _key("compare-order", *p))

    used: dict[str, int] = {}
    out = []
    for a, b in pairs:
        if len(out) >= COMPARE_MAX:
            break
        if used.get(a, 0) >= COMPARE_PER_PRODUCT or used.get(b, 0) >= COMPARE_PER_PRODUCT:
            continue
        used[a] = used.get(a, 0) + 1
        used[b] = used.get(b, 0) + 1
        # Die Reihenfolge der Antworten hängt am Paar, nicht an der Größe —
        # sonst stünde die richtige immer links.
        first, second = (a, b) if int(_key("side", a, b), 16) % 2 else (b, a)
        ra, rb = by_no[first], by_no[second]
        big, small = (ra, rb) if ra["expenses"] >= rb["expenses"] else (rb, ra)
        name = {no: PRODUCTS[no][0] for no in (first, second)}
        explanation = (f"{name[big['product_no']]}: {_euro(big['expenses'])}, "
                       f"{name[small['product_no']]}: {_euro(small['expenses'])} — "
                       f"{_times(big['expenses'] / small['expenses'])}.")
        # Ein Posten, der sich über Gebühren und Erstattungen zu großen Teilen
        # selbst trägt, verdient den Nachsatz — sonst wirkt der Rettungsdienst
        # wie ein Loch im Haushalt.
        for r in (big, small):
            rev = r["revenues"] or 0
            if rev >= 0.5 * r["expenses"]:
                explanation += (f" {_cap(PRODUCTS[r['product_no']][1])} kommen davon "
                                f"{_euro(rev)} über Gebühren und Erstattungen wieder herein.")
        chart = {"type": "bars", "title": f"Geplante Ausgaben {year}", "unit": "Mio. Euro",
                 "items": [{"label": name[r["product_no"]],
                            "value": round(r["expenses"] / 1_000_000, 1),
                            **({"highlight": True} if r is big else {})}
                           for r in (big, small)]}
        out.append({
            "area_type": COMPARE_AREA[0], "area_key": COMPARE_AREA[1],
            "category": "estimation", "difficulty": "easy",
            "qtype": "mc", "format": "compare",
            "question": f"Wofür plant Oldenburg {year} mehr Geld ein?",
            "options": [name[first], name[second]],
            "correct_index": 0 if big is ra else 1,
            "explanation": explanation,
            "chart": json.dumps(chart, ensure_ascii=False),
            "source_type": "city", "source_ref": ra["source_url"],
            "content_hash": _key("compare", a, b),
        })
    return out


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def build_all(store) -> list[dict]:
    return verdict_questions(store) + compare_questions(store)
