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
# 2024 fehlt hier bewusst: Die Übersichtsseite dieses PDFs hat eine defekte
# Text-Kodierung (Zeichensalat statt Text) — der Jahrgang kommt stattdessen
# aus dem Open-Data-CSV (OPENDATA_CSV_URLS unten).
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

# --- Open-Data-CSV (opendata.oldenburg.de, Lizenz dl-de/by-2-0) ---------------
# Die Stadt veröffentlicht die Plan-Ergebnishaushalte 2020–2025 zusätzlich
# maschinenlesbar. Für 2024 ist das die EINZIGE nutzbare Quelle — die
# Übersichtsseite des Plan-PDFs hat eine defekte Text-Kodierung (s. o.).
# Die übrigen Jahre bleiben beim PDF-Parser: Er läuft produktiv, und ein
# Quellenwechsel änderte Bereichsnamen rückwirkend (Trend-Fragen matchen Namen).
OPENDATA_CSV_URLS: dict[int, str] = {
    2024: ("https://opendata.oldenburg.de/sites/default/files/"
           "1101_Haushaltsplan_StadtOL_2024_Ergebnishaushalt.csv"),
}

# Das Portal transliteriert Umlaute („Verwaltungsfuehrung"). Bekannte Namen
# werden auf die PDF-Schreibweise zurückgeführt, damit Jahre vergleichbar
# bleiben; unbekannte Namen laufen unverändert durch (neue THH-Zuschnitte
# sollen den Import nicht stoppen). KEIN generisches ue→ü — „Steuer" u. ä.
# würden zerschossen.
_CSV_NAMEN = {
    "Verwaltungsfuehrung": "Verwaltungsführung",
    "Wirtschaftsfoerderung, Liegenschaften": "Wirtschaftsförderung, Liegenschaften",
    "Verkehr und Strassenbau": "Verkehr und Straßenbau",
    "Umwelt, Bauordnung, Gruen und Friedhoefe": "Umwelt, Bauordnung, Grün und Friedhöfe",
    "Nicht rechtsfaehige Stiftungen": "nicht rechtsfähige Stiftungen",
}


def _csv_num(s: str) -> float | None:
    """Deutsche Zahl aus dem Portal-CSV („ 446.540,00 ") → float, None bei leer."""
    s = s.strip()
    if not s:
        return None
    return float(s.replace(".", "").replace(",", "."))


def parse_opendata_ergebnishaushalt(csv_text: str) -> list[dict]:
    """Ergebnishaushalt-CSV des Open-Data-Portals → dieselbe Zeilenform wie
    ``parse_ergebnishaushalt`` (bereich, ertraege, aufwendungen, ergebnis,
    is_summe; Summenzeile heißt wie im PDF „Summe"). Validiert wie der
    PDF-Parser gegen die Gesamtzeile (±1 %) — liefert [] statt Müll.

    Das CSV kennt kein eigenes Ergebnis je Teilhaushalt; es ergibt sich als
    Erträge − Aufwendungen (so rechnet auch die PDF-Übersicht). Die Zeile
    „Ordentliches Ergebnis (Fehlbedarf)" ist redundant und fällt weg."""
    rows: list[dict] = []
    for line in csv_text.splitlines()[1:]:  # Kopfzeile weg
        parts = line.split(";")
        if len(parts) < 4:
            continue
        code, name = parts[0].strip(), " ".join(parts[1].split())
        revenues, expenses = _csv_num(parts[2]), _csv_num(parts[3])
        if revenues is None or expenses is None:
            continue  # z. B. die Fehlbedarf-Zeile (leere Erträge-Spalte)
        is_total = code.startswith("Gesamtergebnishaushalt")
        rows.append({
            "area": "Summe" if is_total else _CSV_NAMEN.get(name, name),
            "revenues": revenues, "expenses": expenses,
            "result": revenues - expenses,
            "is_total": 1 if is_total else 0,
        })
    parts_ = [r for r in rows if not r["is_total"]]
    summe = next((r for r in rows if r["is_total"]), None)
    if not summe or len(parts_) < 5:
        return []
    for col in ("revenues", "expenses"):
        total = sum(r[col] for r in parts_)
        if abs(total - summe[col]) > 0.01 * max(summe[col], 1):
            return []  # Layout-Drift → lieber nichts als falsche Zahlen
    return rows


# Weitere Finanz-Datensätze desselben Portals (jährlich fortgeschrieben):
STEUERN_CSV_URL = ("https://opendata.oldenburg.de/sites/default/files/"
                   "1104_Steuereinnahmen_0.csv")
STEUERKRAFT_CSV_URL = ("https://opendata.oldenburg.de/sites/default/files/"
                       "1106_Steuerkraftmesszahlen-Schl%C3%BCsselzuweisung_0.csv")
# Hier steht die Einwohnerzahl je Haushaltsjahr (Spalte klar beschriftet).
#
# Die Aufwendungs-Spalte derselben Datei lag bis 08/2026 bewusst liegen, mit
# dieser Begründung: „Sie weicht vom beschlossenen Plan ab (2024: 764,7 statt
# 728,2 Mio.), ist aber nirgends als Ist oder Nachtrag gekennzeichnet — als
# ‚Ist‘ ausgewiesen wäre sie eine Behauptung."
#
# Die Beschriftung ist inzwischen gefunden — sie steht nicht im CSV, sondern im
# PDF derselben Tabelle 1102 („Ordentliche Aufwendungen des Ergebnishaushalts
# — Gesamtergebnisrechnung —"), und der Abgleich gegen die Jahresabschlüsse
# geht auf den Tausender genau auf. Die Spalte wird deshalb jetzt gelesen, aber
# NICHT hier: `council/expense_series.py` liest sie zusammen mit dem PDF und mit
# der älteren CSV desselben Datensatzes (Verwaltungshaushalt 1972–2009), weil
# erst die zweite Quelle die Proben liefert, an denen der Wert hängt. Was `Ist`
# hier heißt und wo der Versatz von 0,03–0,05 % gegen `council_income_statement`
# herkommt, steht im Kopf jenes Moduls.
EINWOHNER_CSV_URL = ("https://opendata.oldenburg.de/sites/default/files/"
                     "1102-Ordentliche_Aufwendungen_des_Ergebnishaushaltes_seit_2010.csv")

# Das zweite Tabellenblatt desselben Datensatzes 1101: der **Finanzhaushalt**,
# aus dem die Investitionen kommen (council/investitionen.py). Anders als beim
# Ergebnishaushalt oben ist das Portal hier die einzige maschinenlesbare
# Quelle — und die einzige Portal-CSV des Bereichs mit einer Rechenprobe in der
# Datei selbst.
#
# Die Jahrgänge stehen einzeln da und nicht als Muster: Das Portal liefert sie
# im Folgejahr nach (2025 erschien am 14.07.2026), und ein geratener Dateiname
# für ein Jahr, das es noch nicht gibt, ergäbe bei jedem Lauf einen 404. Ein
# neuer Jahrgang ist eine Zeile hier.
INVESTITIONEN_CSV_URLS: dict[int, str] = {
    year: ("https://opendata.oldenburg.de/sites/default/files/"
           f"1101_Haushaltsplan_StadtOL_{year}_Finanzhaushalt.csv")
    for year in (2022, 2023, 2024, 2025)
}

# Steuerarten-Spalten wie im Portal, nur Umlaute restauriert.
_STEUERART_NAMEN = {
    "Getraenkesteuer": "Getränkesteuer",
    "Vergnuegungssteuer": "Vergnügungssteuer",
}


def parse_steuereinnahmen(csv_text: str) -> list[dict]:
    """Ist-Steuereinnahmen-CSV (eine Zeile je Jahr, Spalten je Steuerart) →
    Langformat ``{year, art, amount}``. Beträge sind ganze Euro ohne
    Tausenderzeichen; leere Zellen fallen weg."""
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if not lines:
        return []
    kopf = [c.strip() for c in lines[0].split(";")]
    arten = [_STEUERART_NAMEN.get(c, c) for c in kopf[1:]]
    rows: list[dict] = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(";")]
        if not cells[0].isdigit():
            continue  # Fußnoten-/Leerzeilen
        year = int(cells[0])
        for art, cell in zip(arten, cells[1:]):
            if cell:
                rows.append({"year": year, "kind": art, "amount": float(cell)})
    return rows


def parse_einwohner(csv_text: str) -> list[dict]:
    """Einwohnerzahlen je Haushaltsjahr (Stichtag 31.12. des Vorjahres) →
    ``{year, population}``. Basis für Pro-Kopf-Einordnungen; die
    Aufwendungs-Spalten desselben CSV liest ``council/expense_series.py``
    (s. o.)."""
    rows: list[dict] = []
    for line in csv_text.splitlines()[1:]:
        cells = [c.strip() for c in line.split(";")]
        if len(cells) < 2 or not cells[0].isdigit() or not cells[1].isdigit():
            continue
        rows.append({"year": int(cells[0]), "population": int(cells[1])})
    return rows


#: Der Datensatz 1106 beschriftet seine Zeilen um ein Jahr zu früh — wir
#: rücken sie beim Einlesen auf das Ausgleichsjahr, das die Beträge meinen.
#:
#: Der Befund (16.08.2026), an drei unabhängigen Strängen geprüft:
#:
#: 1. **Landesamt für Statistik Niedersachsen (LSN).** Die KFA-Tabellen
#:    (Blatt ``ST_KR_MESS_VGL``, Schlüssel-Nr. 403000) führen dieselben
#:    Beträge auf den Euro genau — aber ein Jahr später. Geprüft über die
#:    Jahrgänge KFA 2016–2026, also elf Jahre am Stück: **12 von 12**
#:    Steuerkraftmesszahlen decken sich mit der CSV-Zeile ``Jahr−1``,
#:    **keine einzige** mit der gleichnamigen. Für die Schlüsselzuweisungen
#:    (Blatt ``9a``, Gemeinde- + Kreisaufgaben) gilt dasselbe; die wenigen
#:    Ausreißer sind durchweg vorläufige Jahrgänge oder Nachtragsstände,
#:    die das LSN später selbst korrigiert hat.
#: 2. **Die Bücher der Stadt.** Das entscheidet die Frage, weil es kein
#:    Beschriftungs-, sondern ein Kassenfakt ist: In welchem Haushaltsjahr
#:    ist das Geld geflossen? Der Ergebnishaushalt des Haushaltsplans 2026
#:    weist als **Ist 2024** 99.569.132 € Schlüsselzuweisungen aus
#:    (Konten 31111000 + 31112000), der Haushaltsplan 2025 als **Ist 2023**
#:    100.319.768 € — beide stehen in der CSV eine Zeile zu früh (unter
#:    2023 bzw. 2022). Der Jahresabschluss 2024 nennt im Fließtext
#:    „rund 109,5 Millionen Euro" und trifft damit den LSN-Nettobetrag des
#:    Ausgleichsjahrs 2024 (109.498 TEUR).
#: 3. **Die Metadaten widersprechen sich selbst.** Die Spalte heißt
#:    „Ausgleichsjahr", die Datensatzbeschreibung auf opendata.oldenburg.de
#:    spricht von „für jedes Haushaltsjahr". Das LSN definiert den Begriff
#:    und liefert die Zahlen — seine Beschriftung ist die amtliche.
#:
#: Direkt belegt ist der Versatz für die CSV-Jahre 2015–2025 (weiter zurück
#: stellt das LSN nichts mehr online). Dass die Reihe *durchgehend* derselben
#: Konvention folgt, zeigt die Pro-Kopf-Spalte: Sie geht 16 von 16 Mal
#: (CSV 2010–2025) mit der Einwohnerzahl auf, die Datensatz 1102 dem
#: gleichnamigen Jahr zuordnet — auch in den Jahren vor dem Prüffenster.
#: Ein Bruch mitten in der Reihe müsste sich dort zeigen und tut es nicht,
#: deshalb rücken wir alle Jahrgänge.
_STEUERKRAFT_VERSATZ = 1


def parse_steuerkraft(csv_text: str) -> list[dict]:
    """Steuerkraftmesszahl/Schlüsselzuweisungen-CSV → je Jahr ein dict
    ``{year, tax_index, tax_capacity_per_capita, allocations, allocations_per_capita}``.

    ``year`` ist das **Ausgleichsjahr** — die CSV-Jahreszahl plus
    :data:`_STEUERKRAFT_VERSATZ`; die Begründung steht dort.

    Die beiden Pro-Kopf-Spalten kommen bewusst **nicht** mit. Die Stadt
    rechnet sie gegen die Einwohnerzahl ihrer eigenen (verschobenen)
    Jahresangabe — nach dem Rücken stünde eine Ausgleichsjahr-Zahl über
    einer Einwohnerzahl, die ein Jahr zu früh ist. Es gilt hier wie überall im
    Bereich: lieber keine Zahl als eine, deren Beschriftung nicht trägt. Wer
    sie braucht, teilt den Absolutwert durch ``council_einwohner``.
    """
    rows: list[dict] = []
    for line in csv_text.splitlines()[1:]:
        cells = [c.strip() for c in line.split(";")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        vals = [float(c) if c else None for c in cells[1:5]]
        rows.append({"year": int(cells[0]) + _STEUERKRAFT_VERSATZ,
                     "tax_index": vals[0], "tax_capacity_per_capita": None,
                     "allocations": vals[2], "allocations_per_capita": None})
    return rows


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
    ``{area, revenues, expenses, result, is_total}`` (Euro).
    Kopf-/Fußzeilen (Spaltennummern, Seitenzahl, „-Euro-") fallen am Regex raus."""
    rows: list[dict] = []
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        nums = [_num(x) for x in m["nums"].split()]
        name = m["name"].strip()
        rows.append({
            "area": name,
            "revenues": nums[0], "expenses": nums[1], "result": nums[2],
            "is_total": 1 if name == "Summe" else 0,
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
        parts = [r for r in rows if not r["is_total"]]
        summe = next((r for r in rows if r["is_total"]), None)
        if not summe or len(parts) < 5:
            continue
        for col in ("revenues", "expenses"):
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
           col: str = "expenses") -> str:
    """Balken-Serie je Teilhaushalt (absteigend, Mio. Euro) als JSON für die
    Auflösung; `highlight` hebt den gefragten Bereich hervor."""
    word = "Aufwendungen" if col == "expenses" else "Erträge"
    items = [{"label": r["area"], "value": _mio(r[col]),
              **({"highlight": True} if r["area"] == highlight else {})}
             for r in sorted(parts, key=lambda r: -r[col])]
    return json.dumps({
        "type": "bars",
        "title": f"Geplante {word} {year} nach Teilhaushalt",
        "unit": "Mio. Euro",
        "items": items,
    }, ensure_ascii=False)


def _share_chart(area: str, share_pct: int, year: int) -> str:
    """Donut „Anteil eines Bereichs an den Gesamtausgaben" (Rest = übrige)."""
    return json.dumps({
        "type": "share",
        "title": f"Anteil an den geplanten Gesamtausgaben {year}",
        "unit": "Prozent",
        "items": [
            {"label": area, "value": share_pct, "highlight": True},
            {"label": "Übrige Bereiche", "value": 100 - share_pct},
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
              difficulty: str = "medium", unit: str = "Mio. Euro") -> dict:
    from council import quiz  # content_hash — zirkular-import-frei zur Laufzeit
    assert lo < answer_mio < hi
    return {
        "area_type": "topic", "area_key": "haushalt", "category": "estimation",
        "difficulty": difficulty, "question": question,
        "options": [], "correct_index": 0, "qtype": "estimate",
        "answer_value": float(answer_mio), "answer_unit": unit,
        "range_min": float(lo), "range_max": float(hi),
        "explanation": f"Laut beschlossenem Haushaltsplan {year} sind es rund {answer_mio} {unit}.",
        "detail": detail, "hint": hint, "topic": "Haushalt",
        "source_type": "city", "source_ref": source_url,
        "chart": chart_json,
        "content_hash": quiz._content_hash("topic", "haushalt", question),
    }


# Kuratierte Kurzbeschreibungen der Teilhaushalte — redaktionell gepflegt, bei
# neuen Jahrgängen prüfen (allgemeines Verwaltungswissen, keine Planzahlen).
# Spiegel zu web/frontend/lib/haushalt-bereiche.ts; die Fragmente stehen im
# Satz hinter „… umfasst".
#
# Geschlüsselt auf den kanonischen Teilhaushalt, NICHT auf den Namen: Die
# Stadt benennt ihre Teilhaushalte um, ohne den Zuschnitt zu ändern (THH 9
# heißt in sieben Jahrgängen viererlei). Eine Map auf den exakten Namen
# verliert beim nächsten Jahrgang stillschweigend Einträge.
def _norm_bereich(name: str) -> str:
    """Vergleichsform eines Bereichsnamens: fängt Groß-/Kleinschreibung,
    doppelte Leerzeichen („Grün  u. Friedhöfe"), „u." gegen „und" und den
    Jahres-Präfix der Ergebnisrechnung („_2019 Stadtplanung") ab."""
    n = re.sub(r"^_\d{4}\s+", "", name or "")
    n = re.sub(r"\s+", " ", n).strip().lower()
    return re.sub(r"(^|\s)u\.(\s|$)", r"\1und\2", n)


_BEREICH_ALIASE = {
    "verwaltungsfuehrung": ("Verwaltungsführung",),
    "personal": ("Personal/Organisation/Digitalisierung/IT",
                 "Personal- und Verwaltungsmanagement",
                 "Personal- u. Verwaltungsmanagement"),
    "wirtschaft": ("Wirtschaftsförderung, Liegenschaften",),
    "finanzen": ("Finanzmanagement und Recht",),
    "sicherheit": ("Sicherheit und Ordnung",),
    "kultur": ("Kultur, Museen, Sport",),
    "stadtplanung": ("Stadtplanung",),
    "verkehr": ("Verkehr und Straßenbau",),
    "umwelt": ("Klima/Umwelt/Mobilität/Bau/Grün/Friedh.",
               "Umwelt, Bauordnung, Grün und Friedhöfe",
               "Klima, Umwelt, Bauordnung, Grün",
               "Umwelt, Bauordnung, Grün  u. Friedhöfe"),
    "soziales": ("Soziales und Gesundheit",),
    "jugend": ("Jugend und Familie",),
    "schule": ("Schule und Bildung",),
    "stiftungen": ("nicht rechtsfähige Stiftungen",),
}

_BEREICH_INFO = {
    # Reihenfolge nach den Produktzeilen 2023: Die Eingliederungshilfe ist über
    # ihre drei Produkte zusammen der größte Block (rund 77 Mio. €) — „vor allem
    # Hilfen zur Pflege" wäre falsch herum.
    "soziales": "gesetzliche Sozialleistungen — Grundsicherung, Eingliederungshilfe, Hilfe zur Pflege — und den öffentlichen Gesundheitsdienst",
    "jugend": "vor allem Kitas, Kindertagespflege und Jugendhilfe",
    "schule": "Schulgebäude, Ausstattung und Ganztagsangebote der Stadt als Schulträgerin",
    # NICHT „Steuern und Zuweisungen": Die Steuern liegen zu 100 % hier, die
    # Zuwendungen nur zu rund zwei Dritteln (2024: 115,4 von 179,1 Mio. €).
    "finanzen": "die zentrale Finanzwirtschaft — hier werden alle Steuern und die allgemeinen Zuweisungen des Landes für die ganze Stadt verbucht",
    "kultur": "Museen, Bibliotheken sowie Kultur- und Sportförderung",
    "verkehr": "Straßen, Radwege, Brücken und den Nahverkehr",
    "sicherheit": "Feuerwehr, Rettungsdienst, Ordnungsverwaltung und die Bürgerdienste vom Einwohnermeldeamt bis zum Standesamt",
    "stadtplanung": "Bauleitplanung und Stadtentwicklung",
    # Gegen den Vorbericht gelesen (H2-13): Sitzungsdienst und Presse- und
    # Öffentlichkeitsarbeit gehören ebenfalls hierher.
    "verwaltungsfuehrung": "Oberbürgermeister und Dezernate, Ratsbüro und Sitzungsdienst, Presse- und Öffentlichkeitsarbeit, dazu Rechnungsprüfung und Gleichstellungsstelle",
    # Der Nachsatz ist die wichtigste Auskunft (H2-13): Der Betrag liest sich
    # sonst wie die Lohnsumme der ganzen Stadt.
    "personal": "Personal, Organisation und IT der gesamten Verwaltung samt der Versorgung der Pensionär*innen — nicht aber die Gehälter aller Beschäftigten, die in ihren jeweiligen Teilhaushalten stehen",
    "wirtschaft": "Wirtschaftsförderung und Standortmarketing sowie die Grundstücke und Beteiligungen der Stadt",
    "umwelt": "Grünflächen und Friedhöfe, Bauordnung sowie Natur- und Klimaschutz",
    "stiftungen": "treuhänderisch verwaltetes Stiftungsvermögen — zweckgebunden, kein frei verfügbares Geld der Stadt",
}

_BEREICH_NACH_ALIAS = {
    _norm_bereich(alias): key
    for key, aliase in _BEREICH_ALIASE.items()
    for alias in aliase
}


def bereich_info(name: str) -> str | None:
    """Kurzbeschreibung eines Teilhaushalts, unabhängig von seiner Schreibweise
    im jeweiligen Jahrgang. Unbekannter Name → None (nie geraten)."""
    return _BEREICH_INFO.get(_BEREICH_NACH_ALIAS.get(_norm_bereich(name), ""))

_PFLICHT_SATZ = (
    "Ein großer Teil davon sind gesetzliche Pflichtaufgaben nach Bundes- und "
    "Landesrecht — frei gestalten kann der Rat vor allem die freiwilligen "
    "Leistungen, etwa in der Kultur- und Sportförderung."
)


def _netto_chart(parts: list[dict], year: int, highlight: str) -> str:
    """Balken „Zuschussbedarf je Teilhaushalt" (Aufwendungen minus eigene
    Erträge; nur Bereiche mit Fehlbetrag, absteigend)."""
    neg = [r for r in parts if r["result"] < 0]
    items = [{"label": r["area"], "value": _mio(-r["result"]),
              **({"highlight": True} if r["area"] == highlight else {})}
             for r in sorted(neg, key=lambda r: r["result"])]
    return json.dumps({
        "type": "bars",
        "title": f"Zuschussbedarf {year} je Teilhaushalt (Ausgaben minus eigene Erträge)",
        "unit": "Mio. Euro",
        "items": items,
    }, ensure_ascii=False)


def _eigen_chart(parts: list[dict], year: int, highlight: str) -> str:
    """Balken „eigene Einnahmen je Fachbereich" (ordentliche Erträge, Mio. €).

    Gezeigt werden dieselben Bereiche, aus denen die Frage ihre Optionen zieht
    (``_fachbereiche``) — der zentrale Finanzhaushalt bleibt draußen, sonst
    stünde neben 170 Mio. ein Balken von 529 Mio., der etwas ganz anderes misst
    (die Steuern der ganzen Stadt). Die Auslassung steht im Titel."""
    items = [{"label": r["area"], "value": _mio(r["revenues"]),
              **({"highlight": True} if r["area"] == highlight else {})}
             for r in sorted(parts, key=lambda r: -r["revenues"])]
    return json.dumps({
        "type": "bars",
        "title": f"Eigene Einnahmen {year} je Bereich — ohne den zentralen Finanzhaushalt",
        "unit": "Mio. Euro",
        "items": items,
    }, ensure_ascii=False)


def _fachbereiche(parts: list[dict]) -> list[dict]:
    """Die Bereiche, die tatsächlich einen Zuschuss brauchen — absteigend nach
    eigenen Erträgen.

    Der Filter ist gemessen, nicht benannt: Wer mehr einnimmt als ausgibt, ist
    kein Fachbereich, sondern die zentrale Finanzwirtschaft (dort stehen alle
    Steuern) bzw. das treuhänderische Stiftungsvermögen. Eine Namensliste ginge
    beim nächsten Jahrgang still kaputt — die Stadt benennt ihre Teilhaushalte
    um, ohne den Zuschnitt zu ändern (s. `_BEREICH_ALIASE`)."""
    eigen = [r for r in parts
             if r["expenses"] > 5_000_000 and 0 < r["revenues"] < r["expenses"]]
    return sorted(eigen, key=lambda r: -r["revenues"])


def build_questions(rows: list[dict], year: int, source_url: str) -> list[dict]:
    """Speicherfertige Quizfragen aus der Ergebnishaushalt-Übersicht — Gesamt,
    Defizit, große Ausgabenblöcke, Anteil (Donut), Erträge, Netto-Sicht und
    eigene Einnahmen. Alle content_hashes sind STABILE Schlüssel (nicht der
    Fragetext), damit spätere Textfixes per refresh_quiz_payloads dieselbe
    Frage aktualisieren statt Dubletten anzulegen."""
    from council import quiz
    parts = [r for r in rows if not r["is_total"]]
    summe = next((r for r in rows if r["is_total"]), None)
    if not summe or len(parts) < 5:
        return []
    rng = random.Random(year)  # deterministisch je Jahr (Optionen mischen)
    by_aufw = sorted(parts, key=lambda r: -r["expenses"])
    top = by_aufw[0]
    chart_all = _chart(parts, year)

    def key(name: str) -> str:
        return quiz._content_hash("topic", "haushalt", f"{name}-{year}")

    gesamt = _mio(summe["expenses"])
    revenues = _mio(summe["revenues"])
    defizit = _mio(summe["revenues"] - summe["expenses"]) * -1
    top3 = ", ".join(f"{r['area']} ({_mio(r['expenses'])} Mio.)" for r in by_aufw[:3])
    zusammensetzung = (
        f"Der Haushalt {year} plant laufende Ausgaben von rund {gesamt} Mio. Euro bei "
        f"Einnahmen von rund {revenues} Mio. Euro. Die größten Ausgabenblöcke: {top3}. "
        + _PFLICHT_SATZ +
        " Fachlich heißen die laufenden Ausgaben im Ergebnishaushalt „ordentliche "
        "Aufwendungen“ — Investitionen (z. B. Neubauten) zählen extra."
    )

    qs: list[dict] = []

    # 1) Gesamt-Ausgaben — die eine Zahl, die man kennen sollte (entjargonisiert).
    q1 = _estimate(
        f"Wie viel Geld plant die Stadt Oldenburg {year} insgesamt auszugeben — "
        "alle laufenden Ausgaben von Personal bis Sozialleistungen?",
        gesamt, lo=max(50, round(gesamt * 0.28, -1)), hi=round(gesamt * 2.1, -2),
        year=year, source_url=source_url, chart_json=chart_all, detail=zusammensetzung,
        hint="Denk in Hunderten von Millionen.",
    )
    q1["content_hash"] = key("gesamt")
    qs.append(q1)

    # 2) Defizit — mit eigenem Detail (Rücklage) statt Überblicks-Kopie.
    if defizit > 5:
        q2 = _estimate(
            f"Um wie viel übersteigen die geplanten Ausgaben der Stadt Oldenburg {year} "
            "die geplanten Einnahmen (das geplante Defizit)?",
            defizit, lo=max(1, round(defizit * 0.15)), hi=round(defizit * 4.5, -1),
            year=year, source_url=source_url, chart_json=chart_all,
            difficulty="hard",
            detail=(f"Geplant sind Einnahmen von rund {revenues} Mio. und Ausgaben von rund "
                    f"{gesamt} Mio. Euro. Solche Fehlbeträge muss eine Stadt aus ihrer Rücklage "
                    "decken — ist die aufgebraucht, muss gekürzt werden. Im Haushalt heißen "
                    "Einnahmen und Ausgaben „Erträge“ und „Aufwendungen“."),
            hint="Fehlbeträge deckt die Stadt aus ihrer Rücklage — noch reicht sie dafür.",
        )
        q2["content_hash"] = key("defizit")
        qs.append(q2)

    # 3–5) Die drei größten Ausgabenblöcke — mit kuratierter Bereichs-Erklärung
    # und gestreuten Slider-Positionen (sonst liegt die Antwort immer bei 36 %).
    span_pairs = ((0.2, 2.4), (0.5, 1.15), (0.15, 2.9))
    for i, r in enumerate(by_aufw[:3]):
        m = _mio(r["expenses"])
        if m < 10:
            continue
        lo_f, hi_f = span_pairs[i % len(span_pairs)]
        info = bereich_info(r["area"])
        rang = "der größte Posten" if i == 0 else "einer der größten Posten"
        detail = (f"„{r['area']}“ umfasst {info} — mit rund {m} Mio. Euro {rang} "
                  f"im Haushalt {year}. " + _PFLICHT_SATZ) if info else (
                  f"„{r['area']}“ ist mit rund {m} Mio. Euro {rang} im Haushalt {year} — "
                  "das Diagramm zeigt die Größenordnungen aller Bereiche.")
        qi = _estimate(
            f"Wie viel plant Oldenburg {year} für den Bereich „{r['area']}“ auszugeben?",
            m, lo=max(5, round(m * lo_f)), hi=round(m * hi_f, -1),
            year=year, source_url=source_url,
            chart_json=_chart(parts, year, highlight=r["area"]),
            detail=detail,
        )
        qi["content_hash"] = key(f"area-{i}")
        qs.append(qi)

    # 6) MC: größter Ausgabenbereich.
    distractors = [r["area"] for r in by_aufw[1:8]]
    rng.shuffle(distractors)
    opts = [top["area"], *distractors[:3]]
    rng.shuffle(opts)
    top_info = bereich_info(top["area"]) or "zentrale Aufgaben der Stadt"
    qs.append({
        "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
        "difficulty": "easy", "qtype": "mc",
        "question": f"Wofür gibt die Stadt Oldenburg {year} am meisten Geld aus?",
        "options": opts, "correct_index": opts.index(top["area"]),
        "explanation": (f"Mit rund {_mio(top['expenses'])} Mio. Euro ist "
                        f"„{top['area']}“ der größte Ausgabenblock — dahinter stehen "
                        f"{top_info}."),
        "detail": _PFLICHT_SATZ, "topic": "Haushalt",
        "source_type": "city", "source_ref": source_url,
        "chart": _chart(parts, year, highlight=top["area"]),
        "content_hash": key("top-expense"),
    })

    # 7) MC: größter Ertragsbereich (dort landen Steuern & Zuweisungen).
    by_revenue = sorted(parts, key=lambda r: -r["revenues"])
    e_top = by_revenue[0]
    e_anteil = round(e_top["revenues"] / max(summe["revenues"], 1) * 100)
    e_opts = [e_top["area"], *[r["area"] for r in by_revenue[1:4]]]
    rng.shuffle(e_opts)
    qs.append({
        "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
        "difficulty": "medium", "qtype": "mc",
        "question": f"In welchem Bereich des städtischen Haushalts landen {year} die höchsten Einnahmen?",
        "options": e_opts, "correct_index": e_opts.index(e_top["area"]),
        "explanation": (f"„{e_top['area']}“ verbucht rund {_mio(e_top['revenues'])} Mio. Euro "
                        "an Erträgen — hier laufen zentrale Einnahmen wie Steuern und "
                        "Zuweisungen von Land und Bund auf."),
        "detail": (f"Rund {e_anteil} von 100 Euro aller Einnahmen laufen zentral in "
                   f"„{e_top['area']}“ auf. Die Fachbereiche decken ihre Ausgaben nur zum "
                   "Teil selbst — den Rest verteilt die Stadt aus diesem Topf."),
        "topic": "Haushalt",
        "source_type": "city", "source_ref": source_url,
        "chart": _chart(parts, year, highlight=e_top["area"], col="revenues"),
        "content_hash": key("top-revenue"),
    })

    # 8) Anteils-Frage mit Donut: Wie groß ist der Batzen „größter Bereich"?
    anteil = round(top["expenses"] / summe["expenses"] * 100)
    if 5 <= anteil <= 75 and abs(anteil - 50) > 10:
        top3_anteil = round(sum(r["expenses"] for r in by_aufw[:3]) / summe["expenses"] * 100)
        q8 = _estimate(
            f"Wie viel Prozent seiner geplanten Gesamtausgaben {year} entfallen in Oldenburg "
            f"auf „{top['area']}“?",
            anteil, lo=max(2, round(anteil * 0.2)), hi=min(95, round(anteil * 2.4)),
            year=year, source_url=source_url,
            chart_json=_share_chart(top["area"], anteil, year),
            detail=(f"Rund {anteil} von 100 Euro fließen in „{top['area']}“ — die drei "
                    f"größten Bereiche zusammen kommen auf rund {top3_anteil} von 100 Euro. "
                    + _PFLICHT_SATZ),
            unit="Prozent",
        )
        q8["content_hash"] = key("anteil")
        qs.append(q8)

    # 9) Einnahmen gesamt (Gegenstück zur Ausgaben-Frage).
    q9 = _estimate(
        f"Wie viel Geld plant die Stadt Oldenburg {year} einzunehmen — Steuern, "
        "Zuweisungen, Gebühren und mehr?",
        revenues, lo=max(50, round(revenues * 0.25, -1)), hi=round(revenues * 2.2, -2),
        year=year, source_url=source_url,
        chart_json=_chart(parts, year, col="revenues"),
        detail=("Die Einnahmen speisen sich vor allem aus Steuern (z. B. Gewerbesteuer und dem "
                "Anteil an der Einkommensteuer), Schlüsselzuweisungen des Landes sowie Gebühren "
                "und Entgelten — fachlich heißen sie im Ergebnishaushalt „ordentliche Erträge“."),
        hint=("Etwas weniger, als die Stadt ausgibt — deshalb gibt es ein Defizit."
              if defizit > 5 else None),
    )
    q9["content_hash"] = key("revenues")
    qs.append(q9)

    # 10) MC: Welcher dieser Bereiche kostet am WENIGSTEN? (mittleres Feld,
    # damit die Antwort nicht offensichtlich ist; deterministische Auswahl)
    mid = [r for r in by_aufw[4:12] if _mio(r["expenses"]) >= 1]
    if len(mid) >= 4:
        pick = [mid[0], mid[2], mid[-2], mid[-1]]
        kleinster = min(pick, key=lambda r: r["expenses"])
        k_info = bereich_info(kleinster["area"])
        k_opts = [r["area"] for r in pick]
        rng.shuffle(k_opts)
        qs.append({
            "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
            "difficulty": "hard", "qtype": "mc",
            "question": f"Welcher dieser Bereiche kostet die Stadt Oldenburg {year} am wenigsten?",
            "options": k_opts, "correct_index": k_opts.index(kleinster["area"]),
            "explanation": (f"„{kleinster['area']}“ ist mit rund {_mio(kleinster['expenses'])} Mio. Euro "
                            "der kleinste der vier — das Diagramm zeigt die Größenordnungen."),
            "detail": (f"„{kleinster['area']}“ umfasst {k_info}." if k_info else None),
            "topic": "Haushalt",
            "source_type": "city", "source_ref": source_url,
            "chart": _chart(parts, year, highlight=kleinster["area"]),
            "content_hash": key("kleinster"),
        })

    # 11) Netto-Sicht: Brutto ≠ Netto — der stärkste Aha der Ergebnis-Spalte.
    by_netto = sorted(parts, key=lambda r: r["result"])
    n_top = by_netto[0]
    if n_top["result"] < 0 and n_top["area"] != top["area"]:
        # Brutto-Spitzenreiter ist Pflicht-Distraktor (der Aha!), Rest aus der
        # Netto-Rangfolge auffüllen — ohne Dubletten.
        n_opts = [n_top["area"], top["area"]]
        n_opts += [r["area"] for r in by_netto[1:6] if r["area"] not in n_opts][:2]
        if len(n_opts) == 4:
            rng.shuffle(n_opts)
            qs.append({
                "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
                "difficulty": "medium", "qtype": "mc",
                "question": (f"Welcher Bereich kostet die Stadt Oldenburg {year} unterm Strich "
                             "am meisten — nach Abzug eigener Einnahmen?"),
                "options": n_opts, "correct_index": n_opts.index(n_top["area"]),
                "explanation": (f"„{n_top['area']}“ hat mit rund {_mio(-n_top['result'])} Mio. Euro "
                                "den größten Zuschussbedarf — die eigenen Einnahmen decken dort nur "
                                "einen kleinen Teil der Ausgaben."),
                "detail": (f"Brutto gibt die Stadt für „{top['area']}“ am meisten aus — dort stehen "
                           f"aber auch hohe eigene Einnahmen (z. B. Erstattungen) gegenüber. Unterm "
                           f"Strich kostet „{n_top['area']}“ am meisten."),
                "topic": "Haushalt",
                "source_type": "city", "source_ref": source_url,
                "chart": _netto_chart(parts, year, n_top["area"]),
                "content_hash": key("netto"),
            })

    # 12) Eigene Einnahmen der Fachbereiche — in Millionen, NICHT als Quote.
    #
    # Diese Frage hieß bis 08/2026 „Welcher Bereich deckt den größten Teil
    # seiner Ausgaben durch eigene Einnahmen?" und antwortete in Prozent. Eine
    # Deckungsquote behauptet aber ein Ziel, das es nicht gibt: Straßen, Kultur
    # und Grünflächen sollen sich nicht selbst finanzieren, das ist
    # Daseinsvorsorge. Der Haushalts-Bereich hat die Kennzahl deshalb überall
    # abgeräumt — der Kostendeckungsgrad-Ring ist weg (Kopf von
    # `web/frontend/app/(app)/haushalt/bereich/page.tsx`, Punkt 1), und die
    # Bereichstabelle formuliert absolut („Ein Prozentwert wäre hier ein
    # Maßstab, den es nicht gibt", `components/haushalt/bereichstabelle.tsx`).
    # Hier steht dieselbe Auskunft nun genauso in Millionen: Wer bringt am
    # meisten mit — nicht, wer „trägt sich am besten".
    #
    # DER SCHLÜSSEL BLEIBT `deckung`. Er benennt den SLOT, nicht den Text: Ein
    # neuer content_hash legte per save_quiz_questions eine zweite Frage an und
    # ließe die alte aktiv im Bestand liegen — refresh_quiz_payloads findet sie
    # nur über genau diesen Schlüssel. Aus demselben Grund bleibt es eine
    # MC-Frage in `schwer`: qtype und difficulty frischt der Refresh nicht auf.
    #
    # WAS DIE ÜBERSICHT NICHT HERGIBT: eine Aufteilung der Erträge nach Arten.
    # Ob ein Bereich sein Geld von Bund und Land oder aus Gebühren bekommt,
    # steht erst in der Ergebnisrechnung je Teilhaushalt
    # (`council_income_statement`) — und die gibt es nur für Jahre mit
    # Jahresabschluss. Frage und Erklärung behaupten die Aufteilung deshalb
    # nicht, sie zählen die Quellen auf und sagen im Detail, was offen bleibt.
    fach = _fachbereiche(parts)
    # Bei nahezu gleichem Spitzenwert wäre die Frage nicht fair beantwortbar —
    # `_mio` rundet, zwei Bereiche stünden im Diagramm auf demselben Balken.
    if len(fach) >= 4 and fach[0]["revenues"] > fach[1]["revenues"] * 1.15:
        e_top = fach[0]
        # Die vier stärksten — ein Feld aus Spitze und Schlusslicht machte die
        # Antwort zur Größenschätzung, nicht zur Frage nach den Einnahmen.
        f_opts = [r["area"] for r in fach[:4]]
        rng.shuffle(f_opts)
        qs.append({
            "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
            "difficulty": "hard", "qtype": "mc",
            "question": (f"Welcher dieser Bereiche nimmt {year} selbst am meisten ein — "
                         "durch Erstattungen und Zuweisungen von Bund und Land, "
                         "Gebühren und Entgelte?"),
            "options": f_opts,
            "correct_index": f_opts.index(e_top["area"]),
            "explanation": (f"„{e_top['area']}“ bringt rund {_mio(e_top['revenues'])} Mio. Euro "
                            "eigene Erträge mit — mehr als jeder andere Fachbereich. Ausgeben "
                            f"tut der Bereich mit rund {_mio(e_top['expenses'])} Mio. Euro "
                            "deutlich mehr; die Differenz trägt die Allgemeinheit."),
            "detail": ("Hohe eigene Einnahmen sind kein Zeugnis: Wo Bund und Land gesetzliche "
                       "Leistungen mitfinanzieren, fließt viel Geld in den Haushalt — Straßen, "
                       "Grünflächen und Kultur haben solche Quellen kaum und sollen sich auch "
                       "nicht selbst tragen. Wie viel der Summe von Bund und Land kommt und wie "
                       "viel aus Gebühren, schlüsselt die Übersicht des Haushaltsplans nicht "
                       "auf; sie nennt je Teilhaushalt eine Ertragssumme."),
            "topic": "Haushalt",
            "source_type": "city", "source_ref": source_url,
            "chart": _eigen_chart(fach, year, e_top["area"]),
            "content_hash": key("deckung"),
        })

    return qs


def _komma(value: float, stellen: int = 1) -> str:
    """Eine Zahl deutsch schreiben — NUR die Zahl.

    Es gibt in dieser Datei zwei Stellen, an denen ein `.replace(".", ",")`
    über einen fertigen Satz lief und dabei „Mio." und den Satzpunkt mit
    erwischte. Deshalb geht die Umstellung hier durch eine Funktion, der man
    nichts anderes als eine Zahl übergeben kann.
    """
    return f"{value:.{stellen}f}".replace(".", ",")


def build_abschluss_questions(store) -> list[dict]:
    """Drei Fragen aus dem Jahresabschluss — nicht aus dem Haushaltsplan.

    Die übrigen Haushalts-Fragen kommen aus dem PLAN: was die Stadt ausgeben
    will. Diese drei kommen aus dem ABSCHLUSS und den Anlagen dazu, und sie
    beantworten Fragen, die der Plan gar nicht stellt.

    Jede hat einen stabilen ``content_hash`` ohne Jahreszahl. Das ist Absicht
    und der Unterschied zu ``build_questions``: Dort gehört das Jahr in den
    Schlüssel, weil „der Haushalt 2025" eine andere Frage ist als „der
    Haushalt 2026". Hier ist es immer dieselbe Frage — sie soll mit dem
    nächsten Abschluss **aktualisiert** werden (``refresh_quiz_payloads``) und
    nicht ein zweites Mal danebenstehen.

    Liefert nur, was belegt ist: Fehlt eine Quelle, fehlt ihre Frage.
    """
    from council import quiz

    def key(name: str) -> str:
        return quiz._content_hash("topic", "haushalt", f"abschluss-{name}")

    ris = "https://buergerinfo.oldenburg.de"
    qs: list[dict] = []

    # 1) Die drei Schuldenzahlen. Die Frage sieht aus wie eine Zahlenfrage und
    #    ist eine Verständnisfrage — genau das ist der Punkt: „Die Schulden der
    #    Stadt" gibt es dreimal, und alle drei sind richtig.
    schulden = store.schulden_kontext()
    weitere = {w["art"]: w for w in (schulden or {}).get("weitere") or []}
    kern = weitere.get("Kernhaushalt (nur Geldschulden)")
    konzern = weitere.get("Konzern Stadt (anteilig, mit Beteiligungen)")
    if schulden and kern and konzern:
        # DAS JAHR GEHÖRT AN JEDE ZAHL, und hier besonders: Die drei Stände
        # kommen aus drei Quellen mit drei Erscheinungsterminen, also nicht
        # zwangsläufig aus demselben Jahr (das Jahrbuch war 08/2026 schon bei
        # 2025, Bilanz und Konzern-Tabellenband noch bei 2024). Ohne Jahr
        # nebeneinandergestellt wäre die Frage angreifbar — zu Recht.
        richtig = "Alle drei — je nachdem, was mitgezählt wird"
        opts = [f"{_mio(kern['amount'])} Mio. Euro ({kern['year']})",
                f"{_mio(schulden['total'])} Mio. Euro ({schulden['year']})",
                f"{_mio(konzern['amount'])} Mio. Euro ({konzern['year']})",
                richtig]
        years = {kern["year"], schulden["year"], konzern["year"]}
        nachsatz = ("" if len(years) == 1 else
                    " Die drei Stände sind nicht aus demselben Jahr: Jede Quelle "
                    "erscheint zu ihrer eigenen Zeit, und die jüngste ist immer "
                    "die, die vorliegt.")
        qs.append({
            "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
            "difficulty": "hard", "qtype": "mc",
            "question": "Wie hoch sind die Schulden der Stadt Oldenburg?",
            "options": opts, "correct_index": opts.index(richtig),
            "explanation": (
                f"Alle drei Zahlen stimmen — sie zählen Verschiedenes. "
                f"{_mio(kern['amount'])} Mio. Euro ({kern['year']}) sind die "
                f"Geldschulden des Kernhaushalts, "
                f"{_mio(schulden['total'])} Mio. Euro ({schulden['year']}) die "
                f"der Stadt samt ihren Eigenbetrieben, und "
                f"{_mio(konzern['amount'])} Mio. Euro ({konzern['year']}) die des "
                f"ganzen Konzerns mit allen Beteiligungen." + nachsatz),
            "detail": ("Wer eine Schuldenzahl nennt, muss die Abgrenzung dazusagen. "
                       "Addieren darf man sie nie: Die größere enthält die kleinere."),
            "hint": "Es kommt darauf an, wen man mitzählt.",
            "topic": "Haushalt", "source_type": "city", "source_ref": ris,
            "content_hash": key("drei-schuldenzahlen"),
        })

    # 2) Die Bürgschaften — eine Zahl, die in keiner Schuldenreihe steht.
    buerg = (schulden or {}).get("buergschaften")
    if buerg and buerg.get("balance"):
        amount = _mio(buerg["balance"])
        eigene = _mio(kern["amount"]) if kern else None
        vergleich = (f" Das ist rund das {buerg['balance'] / kern['amount']:.0f}-Fache "
                     f"der {eigene} Mio. Euro, die der Kernhaushalt selbst schuldet."
                     if kern and kern["amount"] else "")
        qs.append(_estimate(
            "Die Stadt Oldenburg steht für Kredite ihrer eigenen Gesellschaften "
            "gerade — für wie viele Millionen Euro?",
            amount, lo=max(5, round(amount * 0.15)), hi=round(amount * 3.2, -1),
            year=buerg["year"], source_url=ris, chart_json="",
            difficulty="hard",
            detail=("Eine Bürgschaft kostet nichts, solange sie nicht gezogen wird — "
                    "deshalb taucht sie in keiner Schuldenzahl auf. Sie steht im "
                    "Anhang des Jahresabschlusses unter „Eventualverbindlichkeiten“."
                    + vergleich),
            hint="Mehr als die Stadt selbst an Krediten offen hat.",
        ))
        # Jede Zahl wird EINZELN formatiert. Ein `.replace(".", ",")` über den
        # fertigen Satz erwischt die Punkte in „Mio." und am Satzende gleich mit
        # („1,30 Mio, Euro zurück,“) — zweimal hineingelaufen.
        zusatz = ""
        if buerg.get("rueckstellung"):
            rueck = _komma(buerg["rueckstellung"] / 1e6, 2)
            anteil = _komma(buerg["rueckstellung"] / buerg["balance"] * 100, 2)
            zusatz = (f" Für den erwarteten Ausfall hält die Stadt {rueck} Mio. Euro "
                      f"zurück — {anteil} Prozent des Bestands.")
        qs[-1]["explanation"] = (
            f"Zum 31.12.{buerg['year']} waren es {amount} Mio. Euro." + zusatz)
        qs[-1]["content_hash"] = key("buergschaften")

    # 3) Der Substanzverlust: Was die Stadt jährlich abschreibt, gegen das, was
    #    sie zubaut. Die Zahl kommt aus dem Anlagenspiegel und ist die Antwort
    #    auf „Baut die Stadt schneller auf, als ihr Bestand verfällt?".
    zeilen = [z for z in store.get_anlagenspiegel() if z.get("nr") == "2"]
    if zeilen:
        z = max(zeilen, key=lambda r: r["year"])
        zubau, verzehr = z.get("additions") or 0, abs(z.get("depreciation") or 0)
        if zubau > 0 and verzehr > 0:
            faktor = verzehr / zubau
            richtig = _komma(faktor) + " Euro"
            opts = sorted({richtig,
                           _komma(max(0.2, faktor / 3)) + " Euro",
                           _komma(faktor / 1.8) + " Euro",
                           _komma(faktor * 2) + " Euro"})
            qs.append({
                "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
                "difficulty": "hard", "qtype": "mc",
                "question": (f"Auf jeden Euro, den die Stadt {z['year']} in ihr "
                             f"Sachvermögen — Gebäude, Straßen, Fahrzeuge — "
                             f"investiert hat: Wie viel Wert hat im selben Jahr "
                             f"die Abnutzung aufgezehrt?"),
                "options": opts, "correct_index": opts.index(richtig),
                "explanation": (
                    f"{z['year']} kamen {_mio(zubau)} Mio. Euro dazu, und "
                    f"{_mio(verzehr)} Mio. Euro wurden abgeschrieben — auf jeden "
                    f"investierten Euro also {richtig} Wertverlust."),
                "detail": ("Abschreibung ist der gebuchte Wertverlust einer "
                           "Anschaffung über ihre Nutzungsdauer. Liegt sie über den "
                           "Zugängen, verzehrt die Stadt Substanz — das ist weder "
                           "gut noch schlecht, sondern eine Frage, wie lange es so "
                           "weitergehen soll."),
                "hint": "Mehr als einer.",
                "topic": "Haushalt", "source_type": "city", "source_ref": ris,
                "content_hash": key("substanzverlust"),
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
        return next((r for r in by_year[year] if r["is_total"]), None)

    s0, s1 = summe(y0), summe(y1)
    if not s0 or not s1 or s0["expenses"] <= 0:
        return []
    series = [(y, summe(y)["expenses"]) for y in years if summe(y)]
    trend_json = _trend_chart(series, f"Geplante Gesamtausgaben {y0}–{y1}")
    wachstum = round((s1["expenses"] / s0["expenses"] - 1) * 100)

    qs: list[dict] = []

    # 1) Wachstum als Schätzfrage (Prozent) mit Trendlinie.
    if 5 <= wachstum <= 300:
        qs.append({
            "area_type": "topic", "area_key": "haushalt", "category": "estimation",
            "difficulty": "hard", "qtype": "estimate",
            "question": (f"Um wie viel Prozent sind Oldenburgs geplante Gesamtausgaben "
                         f"von {y0} bis {y1} gewachsen?"),
            "options": [], "correct_index": 0,
            "answer_value": float(wachstum), "answer_unit": "Prozent",
            "range_min": float(max(1, round(wachstum * 0.15))),
            "range_max": float(min(400, round(wachstum * 2.6))),
            "explanation": (f"Von rund {_mio(s0['expenses'])} auf rund {_mio(s1['expenses'])} Mio. Euro — "
                            f"ein Plus von etwa {wachstum} Prozent."),
            "detail": (f"Die geplanten ordentlichen Aufwendungen stiegen von {_mio(s0['expenses'])} Mio. Euro "
                       f"({y0}) auf {_mio(s1['expenses'])} Mio. Euro ({y1}). Preissteigerungen, Tarifabschlüsse "
                       "und wachsende Pflichtaufgaben (etwa Sozialleistungen und Kinderbetreuung) treiben "
                       "die Ausgaben Jahr für Jahr — das Diagramm zeigt den Verlauf."),
            "hint": "Die Ausgaben sind kräftig gestiegen — mehr als ein Viertel.",
            "topic": "Haushalt", "source_type": "city", "source_ref": source_url,
            "chart": trend_json,
            "content_hash": quiz._content_hash("topic", "haushalt", f"trend-{y0}-{y1}"),
        })

    # 2) Bereich mit dem stärksten Wachstum (nur namensgleiche Bereiche).
    p0 = {r["area"]: r for r in by_year[y0] if not r["is_total"]}
    p1 = {r["area"]: r for r in by_year[y1] if not r["is_total"]}
    common = [b for b in p1 if b in p0 and p0[b]["expenses"] > 1_000_000]
    if len(common) >= 4:
        growth = sorted(common, key=lambda b: p1[b]["expenses"] - p0[b]["expenses"], reverse=True)
        top_g = growth[0]
        delta = _mio(p1[top_g]["expenses"] - p0[top_g]["expenses"])
        opts = [top_g, *growth[len(growth) // 2:len(growth) // 2 + 2], growth[-1]][:4]
        opts = list(dict.fromkeys(opts))  # Dubletten raus (Sicherheitsnetz)
        if len(opts) == 4 and delta >= 10:
            rng = random.Random(y1)
            rng.shuffle(opts)
            qs.append({
                "area_type": "topic", "area_key": "haushalt", "category": "council_politics",
                "difficulty": "hard", "qtype": "mc",
                "question": (f"Welcher Bereich ist in Oldenburgs Haushaltsplanung von {y0} bis {y1} "
                             "am stärksten gewachsen (in Euro)?"),
                "options": opts, "correct_index": opts.index(top_g),
                "explanation": (f"„{top_g}“ legte um rund {delta} Mio. Euro zu "
                                f"(von {_mio(p0[top_g]['expenses'])} auf {_mio(p1[top_g]['expenses'])} Mio.)."),
                "detail": ("Wachsende Pflichtaufgaben schlagen vor allem in den großen Sozial- und "
                           "Bildungsbereichen zu Buche — das Diagramm zeigt den Verlauf der Gesamtausgaben."),
                "topic": "Haushalt", "source_type": "city", "source_ref": source_url,
                "chart": trend_json,
                "content_hash": quiz._content_hash("topic", "haushalt", f"trend-area-{y0}-{y1}"),
            })

    return qs
