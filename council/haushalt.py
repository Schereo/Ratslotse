"""Oldenburger Stadt-Haushalt: offizielle Haushaltsplan-PDFs einlesen und
daraus deterministische Quizfragen MIT Diagramm bauen.

Quelle ist die „Übersicht Ergebnishaushalt" aus dem **beschlossenen**
Haushaltsplan auf oldenburg.de (genehmigte Fassung, stabile URLs) — dieselben
Unterlagen, die auch den Ratsgremien vorlagen. Eine Tabellenseite, ein
Teilhaushalt je Zeile: ordentliche Erträge, Aufwendungen, Ergebnis.

Bewusst **ohne LLM**: Die Fragen werden aus den geparsten Zahlen per Template
erzeugt — nichts ist erfunden, jede Frage trägt die PDF-URL als Quelle. Das
Diagramm (Aufwendungen je Teilhaushalt) liefert die Auflösung als JSON mit;
das Frontend rendert es als Balkenliste.
"""
from __future__ import annotations

import json
import random
import re

from pypdf import PdfReader

# Beschlossener, ministeriell genehmigter Haushalt 2026 (Stadt Oldenburg).
HAUSHALT_URLS: dict[int, str] = {
    2026: ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "20_Controlling_und_Finanzen/200_Finanzen/Haushalt_2026/"
           "Genehmigung_Haushalt_2026/04_Haushaltsplan_2026_-_UEbersichten.pdf"),
}

# Eine Tabellenzeile: Bereichsname (Buchstaben/Satzzeichen), dann 3–6 Zahlen-
# kolonnen mit deutschen Tausenderpunkten (ordentliche Erträge, Aufwendungen,
# Ergebnis [+ außerordentliche Spalten, die wir ignorieren]).
_ROW = re.compile(
    r"^(?P<name>[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß/,.\- ]*?)\s+"
    r"(?P<nums>-?\d[\d.]*(?:\s+-?\d[\d.]*){2,5})\s*$"
)


def _num(s: str) -> float:
    return float(s.replace(".", ""))


def parse_ergebnishaushalt(text: str) -> list[dict]:
    """Zeilen der „Übersicht Ergebnishaushalt" → Liste
    ``{bereich, ertraege, aufwendungen, ergebnis, is_summe}`` (Euro).
    Kopf-/Fußzeilen (Spaltennummern, Seitenzahl, „-Euro-") fallen am Regex raus."""
    rows: list[dict] = []
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        nums = [_num(x) for x in m["nums"].split()]
        name = m["name"].strip()
        rows.append({
            "bereich": name,
            "ertraege": nums[0], "aufwendungen": nums[1], "ergebnis": nums[2],
            "is_summe": 1 if name == "Summe" else 0,
        })
    return rows


def extract_from_pdf(pdf_path: str) -> list[dict]:
    """Die Seite „Übersicht Ergebnishaushalt" im PDF finden und parsen.
    Validiert gegen die Summenzeile (±1 %) — liefert [] statt Müll, wenn sich
    das PDF-Layout einmal ändern sollte."""
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        text = page.extract_text() or ""
        if not text.strip().startswith("Übersicht Ergebnishaushalt"):
            continue
        rows = parse_ergebnishaushalt(text)
        parts = [r for r in rows if not r["is_summe"]]
        summe = next((r for r in rows if r["is_summe"]), None)
        if not summe or len(parts) < 5:
            continue
        for col in ("ertraege", "aufwendungen"):
            total = sum(r[col] for r in parts)
            if abs(total - summe[col]) > 0.01 * max(summe[col], 1):
                return []  # Layout-Drift → lieber nichts als falsche Zahlen
        return rows
    return []


# --- Quizfragen (deterministisch, ohne LLM) -----------------------------------

_MIO = 1_000_000.0


def _mio(v: float) -> int:
    return round(v / _MIO)


def _chart(parts: list[dict], year: int, highlight: str | None = None) -> str:
    """Balken-Serie „Aufwendungen je Teilhaushalt" (absteigend, Mio. Euro) als
    JSON für die Auflösung; `highlight` hebt den gefragten Bereich hervor."""
    items = [{"label": r["bereich"], "value": _mio(r["aufwendungen"]),
              **({"highlight": True} if r["bereich"] == highlight else {})}
             for r in sorted(parts, key=lambda r: -r["aufwendungen"])]
    return json.dumps({
        "title": f"Geplante Aufwendungen {year} nach Teilhaushalt",
        "unit": "Mio. Euro",
        "items": items,
    }, ensure_ascii=False)


def _estimate(question: str, answer_mio: int, lo: int, hi: int, *, year: int,
              source_url: str, chart_json: str, detail: str, hint: str | None = None,
              difficulty: str = "mittel") -> dict:
    from council import quiz  # content_hash — zirkular-import-frei zur Laufzeit
    assert lo < answer_mio < hi
    return {
        "area_type": "thema", "area_key": "haushalt", "category": "schaetzen",
        "difficulty": difficulty, "question": question,
        "options": [], "correct_index": 0, "qtype": "estimate",
        "answer_value": float(answer_mio), "answer_unit": "Mio. Euro",
        "range_min": float(lo), "range_max": float(hi),
        "explanation": f"Laut beschlossenem Haushaltsplan {year} sind es rund {answer_mio} Mio. Euro.",
        "detail": detail, "hint": hint, "topic": "Haushalt",
        "source_type": "stadt", "source_ref": source_url,
        "chart": chart_json,
        "content_hash": quiz._content_hash("thema", "haushalt", question),
    }


def build_questions(rows: list[dict], year: int, source_url: str) -> list[dict]:
    """Speicherfertige Quizfragen aus der Ergebnishaushalt-Übersicht: Gesamt-
    Aufwendungen, Defizit, die großen Ausgabenblöcke (Schätzfragen) plus zwei
    Multiple-Choice-Fragen (größter Ausgaben-/Ertragsbereich)."""
    from council import quiz
    parts = [r for r in rows if not r["is_summe"]]
    summe = next((r for r in rows if r["is_summe"]), None)
    if not summe or len(parts) < 5:
        return []
    rng = random.Random(year)  # deterministisch je Jahr (Optionen mischen)
    by_aufw = sorted(parts, key=lambda r: -r["aufwendungen"])
    top = by_aufw[0]
    chart_all = _chart(parts, year)

    gesamt = _mio(summe["aufwendungen"])
    ertraege = _mio(summe["ertraege"])
    defizit = _mio(summe["ertraege"] - summe["aufwendungen"]) * -1
    top3 = ", ".join(f"{r['bereich']} ({_mio(r['aufwendungen'])} Mio.)" for r in by_aufw[:3])
    zusammensetzung = (
        f"Der Ergebnishaushalt {year} plant Aufwendungen von rund {gesamt} Mio. Euro bei "
        f"Erträgen von rund {ertraege} Mio. Euro. Die größten Ausgabenblöcke: {top3}. "
        "Ein großer Teil davon sind gesetzliche Pflichtaufgaben (etwa Sozialleistungen nach "
        "Bundes- und Landesrecht) — frei gestalten kann der Rat vor allem die freiwilligen "
        "Leistungen, z. B. in Kultur und Sportförderung."
    )

    qs: list[dict] = []

    # 1) Gesamt-Aufwendungen (die eine Zahl, die man kennen sollte).
    qs.append(_estimate(
        f"Wie viel Geld plant die Stadt Oldenburg {year} insgesamt auszugeben (ordentliche Aufwendungen)?",
        gesamt, lo=max(50, round(gesamt * 0.28, -1)), hi=round(gesamt * 2.1, -2),
        year=year, source_url=source_url, chart_json=chart_all, detail=zusammensetzung,
        hint="Denk in Hunderten von Millionen — Oldenburg ist eine Großstadt mit rund 175.000 Menschen.",
    ))

    # 2) Defizit (Erträge vs. Aufwendungen).
    if defizit > 5:
        qs.append(_estimate(
            f"Um wie viel übersteigen die geplanten Ausgaben {year} die Erträge (geplantes Defizit)?",
            defizit, lo=max(1, round(defizit * 0.15)), hi=round(defizit * 4.5, -1),
            year=year, source_url=source_url, chart_json=chart_all,
            detail=zusammensetzung, difficulty="schwer",
            hint="Die Lücke wird aus der Rücklage der Stadt ausgeglichen.",
        ))

    # 3–5) Die drei größten Ausgabenblöcke einzeln.
    for r in by_aufw[:3]:
        m = _mio(r["aufwendungen"])
        if m < 10:
            continue
        qs.append(_estimate(
            f"Wie viel plant Oldenburg {year} für den Bereich „{r['bereich']}“ auszugeben?",
            m, lo=max(5, round(m * 0.2)), hi=round(m * 2.4, -1),
            year=year, source_url=source_url,
            chart_json=_chart(parts, year, highlight=r["bereich"]),
            detail=(f"„{r['bereich']}“ ist mit rund {m} Mio. Euro einer der größten Posten im "
                    f"Ergebnishaushalt {year} — das Diagramm zeigt, wie sich die Aufwendungen "
                    "auf die Teilhaushalte verteilen."),
        ))

    # 6) MC: größter Ausgabenbereich.
    distractors = [r["bereich"] for r in by_aufw[1:8]]
    rng.shuffle(distractors)
    opts = [top["bereich"], *distractors[:3]]
    rng.shuffle(opts)
    qs.append({
        "area_type": "thema", "area_key": "haushalt", "category": "ratspolitik",
        "difficulty": "leicht", "qtype": "mc",
        "question": f"Wofür gibt die Stadt Oldenburg {year} am meisten Geld aus?",
        "options": opts, "correct_index": opts.index(top["bereich"]),
        "explanation": (f"Mit rund {_mio(top['aufwendungen'])} Mio. Euro ist "
                        f"„{top['bereich']}“ der größte Ausgabenblock."),
        "detail": zusammensetzung, "topic": "Haushalt",
        "source_type": "stadt", "source_ref": source_url,
        "chart": _chart(parts, year, highlight=top["bereich"]),
        "content_hash": quiz._content_hash("thema", "haushalt", f"top-aufwand-{year}"),
    })

    # 7) MC: größter Ertragsbereich (dort landen Steuern & Zuweisungen).
    by_ertrag = sorted(parts, key=lambda r: -r["ertraege"])
    e_top = by_ertrag[0]
    e_opts = [e_top["bereich"], *[r["bereich"] for r in by_ertrag[1:4]]]
    rng.shuffle(e_opts)
    qs.append({
        "area_type": "thema", "area_key": "haushalt", "category": "ratspolitik",
        "difficulty": "mittel", "qtype": "mc",
        "question": f"In welchem Teilhaushalt verbucht Oldenburg {year} die höchsten Erträge?",
        "options": e_opts, "correct_index": e_opts.index(e_top["bereich"]),
        "explanation": (f"„{e_top['bereich']}“ verbucht rund {_mio(e_top['ertraege'])} Mio. Euro — "
                        "hier laufen zentrale Einnahmen wie Steuern und Zuweisungen von Land und Bund auf."),
        "detail": zusammensetzung, "topic": "Haushalt",
        "source_type": "stadt", "source_ref": source_url,
        "chart": chart_all,
        "content_hash": quiz._content_hash("thema", "haushalt", f"top-ertrag-{year}"),
    })

    return qs
