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

# Beschlossene Haushaltspläne der Stadt Oldenburg (aktuelles Jahr + Archiv).
# 2024 fehlt bewusst: Die Übersichtsseite dieses PDFs hat eine defekte
# Text-Kodierung (Zeichensalat statt Text) und ist ohne OCR nicht lesbar.
_ARCHIV = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "20_Controlling_und_Finanzen/200_Finanzen/Archiv_Haushaltsplaene/")
HAUSHALT_URLS: dict[int, str] = {
    2020: _ARCHIV + "Haushaltsplan_2020_-_Stadt_Oldenburg_Gesamt.pdf",
    2021: _ARCHIV + "Haushaltsplan_2021_-_Stadt_Oldenburg_Gesamt.pdf",
    2022: _ARCHIV + "Haushaltsplan_2022_-_Stadt_Oldenburg_Gesamt.pdf",
    2023: _ARCHIV + "Haushaltsplan_2023_-_Stadt_Oldenburg_Gesamt.pdf",
    2025: _ARCHIV + "Haushaltsplan_2025-_Stadt_Oldenburg-Gesamt.pdf",
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
        # Kopf-Toleranz: In den Archiv-Gesamt-PDFs steht der Titel nicht immer
        # in der ersten Zeile. Inhaltsverzeichnis-Seiten fallen unten raus
        # (keine parsebare Summenzeile).
        if "Übersicht Ergebnishaushalt" not in text.strip()[:300]:
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


def _chart(parts: list[dict], year: int, highlight: str | None = None,
           col: str = "aufwendungen") -> str:
    """Balken-Serie je Teilhaushalt (absteigend, Mio. Euro) als JSON für die
    Auflösung; `highlight` hebt den gefragten Bereich hervor."""
    word = "Aufwendungen" if col == "aufwendungen" else "Erträge"
    items = [{"label": r["bereich"], "value": _mio(r[col]),
              **({"highlight": True} if r["bereich"] == highlight else {})}
             for r in sorted(parts, key=lambda r: -r[col])]
    return json.dumps({
        "type": "bars",
        "title": f"Geplante {word} {year} nach Teilhaushalt",
        "unit": "Mio. Euro",
        "items": items,
    }, ensure_ascii=False)


def _share_chart(bereich: str, anteil_prozent: int, year: int) -> str:
    """Donut „Anteil eines Bereichs an den Gesamtausgaben" (Rest = übrige)."""
    return json.dumps({
        "type": "share",
        "title": f"Anteil an den geplanten Gesamtausgaben {year}",
        "unit": "Prozent",
        "items": [
            {"label": bereich, "value": anteil_prozent, "highlight": True},
            {"label": "Übrige Bereiche", "value": 100 - anteil_prozent},
        ],
    }, ensure_ascii=False)


def _trend_chart(series: list[tuple[int, float]], title: str) -> str:
    """Trendlinie über Haushaltsjahre (Mio. Euro), letzter Punkt hervorgehoben."""
    items = [{"label": str(y), "value": _mio(v)} for y, v in series]
    if items:
        items[-1]["highlight"] = True
    return json.dumps({"type": "trend", "title": title, "unit": "Mio. Euro",
                       "items": items}, ensure_ascii=False)


def _estimate(question: str, answer_mio: int, lo: int, hi: int, *, year: int,
              source_url: str, chart_json: str, detail: str, hint: str | None = None,
              difficulty: str = "mittel", unit: str = "Mio. Euro") -> dict:
    from council import quiz  # content_hash — zirkular-import-frei zur Laufzeit
    assert lo < answer_mio < hi
    return {
        "area_type": "thema", "area_key": "haushalt", "category": "schaetzen",
        "difficulty": difficulty, "question": question,
        "options": [], "correct_index": 0, "qtype": "estimate",
        "answer_value": float(answer_mio), "answer_unit": unit,
        "range_min": float(lo), "range_max": float(hi),
        "explanation": f"Laut beschlossenem Haushaltsplan {year} sind es rund {answer_mio} {unit}.",
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
        "chart": _chart(parts, year, highlight=e_top["bereich"], col="ertraege"),
        "content_hash": quiz._content_hash("thema", "haushalt", f"top-ertrag-{year}"),
    })

    # 8) Anteils-Frage mit Donut: Wie groß ist der Batzen „größter Bereich"?
    anteil = round(top["aufwendungen"] / summe["aufwendungen"] * 100)
    if 5 <= anteil <= 75:
        qs.append(_estimate(
            f"Wie viel Prozent seiner geplanten Gesamtausgaben {year} entfallen in Oldenburg "
            f"auf „{top['bereich']}“?",
            anteil, lo=max(2, round(anteil * 0.2)), hi=min(95, round(anteil * 2.4)),
            year=year, source_url=source_url,
            chart_json=_share_chart(top["bereich"], anteil, year),
            detail=(f"Rund {anteil} von 100 Euro fließen in „{top['bereich']}“ — ein Großteil davon "
                    "sind gesetzliche Pflichtaufgaben, die die Stadt erfüllen muss. "
                    + zusammensetzung),
            unit="Prozent",
        ))

    # 9) Erträge gesamt (Gegenstück zur Ausgaben-Frage).
    qs.append(_estimate(
        f"Wie viel Geld plant die Stadt Oldenburg {year} einzunehmen (ordentliche Erträge)?",
        ertraege, lo=max(50, round(ertraege * 0.25, -1)), hi=round(ertraege * 2.2, -2),
        year=year, source_url=source_url,
        chart_json=_chart(parts, year, col="ertraege"),
        detail=("Die Erträge speisen sich vor allem aus Steuern (z. B. Gewerbesteuer und dem "
                "Anteil an der Einkommensteuer), Schlüsselzuweisungen des Landes sowie Gebühren "
                "und Entgelten. " + zusammensetzung),
        hint="Etwas weniger, als die Stadt ausgibt — deshalb gibt es ein Defizit.",
    ))

    # 10) MC: Welcher dieser Bereiche kostet am WENIGSTEN? (mittleres Feld,
    # damit die Antwort nicht offensichtlich ist; deterministische Auswahl)
    mid = [r for r in by_aufw[4:12] if _mio(r["aufwendungen"]) >= 1]
    if len(mid) >= 4:
        pick = [mid[0], mid[2], mid[-2], mid[-1]]
        kleinster = min(pick, key=lambda r: r["aufwendungen"])
        k_opts = [r["bereich"] for r in pick]
        rng.shuffle(k_opts)
        qs.append({
            "area_type": "thema", "area_key": "haushalt", "category": "ratspolitik",
            "difficulty": "schwer", "qtype": "mc",
            "question": f"Welcher dieser Bereiche kostet die Stadt Oldenburg {year} am wenigsten?",
            "options": k_opts, "correct_index": k_opts.index(kleinster["bereich"]),
            "explanation": (f"„{kleinster['bereich']}“ ist mit rund {_mio(kleinster['aufwendungen'])} Mio. Euro "
                            "der kleinste der vier — das Diagramm zeigt die Größenordnungen."),
            "detail": zusammensetzung, "topic": "Haushalt",
            "source_type": "stadt", "source_ref": source_url,
            "chart": _chart(parts, year, highlight=kleinster["bereich"]),
            "content_hash": quiz._content_hash("thema", "haushalt", f"kleinster-{year}"),
        })

    return qs


def build_trend_questions(by_year: dict[int, list[dict]], source_url: str) -> list[dict]:
    """Zeitreihen-Fragen über mehrere Haushaltsjahre (Trend-Diagramm) —
    braucht mindestens zwei geparste Jahre. Vergleiche nur über die Summenzeile
    und über Bereiche, deren Name in Anfangs- UND Endjahr identisch ist (die
    Teilhaushalts-Zuschnitte ändern sich über die Jahre)."""
    from council import quiz
    years = sorted(y for y, rows in by_year.items() if rows)
    if len(years) < 2:
        return []
    y0, y1 = years[0], years[-1]

    def summe(year: int) -> dict | None:
        return next((r for r in by_year[year] if r["is_summe"]), None)

    s0, s1 = summe(y0), summe(y1)
    if not s0 or not s1 or s0["aufwendungen"] <= 0:
        return []
    series = [(y, summe(y)["aufwendungen"]) for y in years if summe(y)]
    trend_json = _trend_chart(series, f"Geplante Gesamtausgaben {y0}–{y1}")
    wachstum = round((s1["aufwendungen"] / s0["aufwendungen"] - 1) * 100)

    qs: list[dict] = []

    # 1) Wachstum als Schätzfrage (Prozent) mit Trendlinie.
    if 5 <= wachstum <= 300:
        qs.append({
            "area_type": "thema", "area_key": "haushalt", "category": "schaetzen",
            "difficulty": "schwer", "qtype": "estimate",
            "question": (f"Um wie viel Prozent sind Oldenburgs geplante Gesamtausgaben "
                         f"von {y0} bis {y1} gewachsen?"),
            "options": [], "correct_index": 0,
            "answer_value": float(wachstum), "answer_unit": "Prozent",
            "range_min": float(max(1, round(wachstum * 0.15))),
            "range_max": float(min(400, round(wachstum * 2.6))),
            "explanation": (f"Von rund {_mio(s0['aufwendungen'])} auf rund {_mio(s1['aufwendungen'])} Mio. Euro — "
                            f"ein Plus von etwa {wachstum} Prozent."),
            "detail": (f"Die geplanten ordentlichen Aufwendungen stiegen von {_mio(s0['aufwendungen'])} Mio. Euro "
                       f"({y0}) auf {_mio(s1['aufwendungen'])} Mio. Euro ({y1}). Preissteigerungen, Tarifabschlüsse "
                       "und wachsende Pflichtaufgaben (etwa Sozialleistungen und Kinderbetreuung) treiben "
                       "die Ausgaben Jahr für Jahr — das Diagramm zeigt den Verlauf."),
            "hint": "Die Ausgaben sind kräftig gestiegen — mehr als ein Viertel.",
            "topic": "Haushalt", "source_type": "stadt", "source_ref": source_url,
            "chart": trend_json,
            "content_hash": quiz._content_hash("thema", "haushalt", f"trend-{y0}-{y1}"),
        })

    # 2) Bereich mit dem stärksten Wachstum (nur namensgleiche Bereiche).
    p0 = {r["bereich"]: r for r in by_year[y0] if not r["is_summe"]}
    p1 = {r["bereich"]: r for r in by_year[y1] if not r["is_summe"]}
    common = [b for b in p1 if b in p0 and p0[b]["aufwendungen"] > 1_000_000]
    if len(common) >= 4:
        growth = sorted(common, key=lambda b: p1[b]["aufwendungen"] - p0[b]["aufwendungen"], reverse=True)
        top_g = growth[0]
        delta = _mio(p1[top_g]["aufwendungen"] - p0[top_g]["aufwendungen"])
        opts = [top_g, *growth[len(growth) // 2:len(growth) // 2 + 2], growth[-1]][:4]
        opts = list(dict.fromkeys(opts))  # Dubletten raus (Sicherheitsnetz)
        if len(opts) == 4 and delta >= 10:
            rng = random.Random(y1)
            rng.shuffle(opts)
            qs.append({
                "area_type": "thema", "area_key": "haushalt", "category": "ratspolitik",
                "difficulty": "schwer", "qtype": "mc",
                "question": (f"Welcher Bereich ist in Oldenburgs Haushaltsplanung von {y0} bis {y1} "
                             "am stärksten gewachsen (in Euro)?"),
                "options": opts, "correct_index": opts.index(top_g),
                "explanation": (f"„{top_g}“ legte um rund {delta} Mio. Euro zu "
                                f"(von {_mio(p0[top_g]['aufwendungen'])} auf {_mio(p1[top_g]['aufwendungen'])} Mio.)."),
                "detail": ("Wachsende Pflichtaufgaben schlagen vor allem in den großen Sozial- und "
                           "Bildungsbereichen zu Buche — das Diagramm zeigt den Verlauf der Gesamtausgaben."),
                "topic": "Haushalt", "source_type": "stadt", "source_ref": source_url,
                "chart": trend_json,
                "content_hash": quiz._content_hash("thema", "haushalt", f"trend-bereich-{y0}-{y1}"),
            })

    return qs
