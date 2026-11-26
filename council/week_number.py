"""Die Zahl der Woche für „Heute“ — ein Lauf, alle Quellen, ein einfacher Satz.

Tim, 25.11.2026: „59.000 € — beschlossen für: Überplanmäßige Bewilligung …
Teilhaushalt 02, Budget 10“ sage niemandem etwas, und in der Woche, in der der
Haushaltsentwurf vorgestellt wird, sei eine Zahl daraus spannend. Befund-Sätze
(„Laut Plan bleibt das Jahresergebnis bis 2030 negativ“) waren ihm ebenso
„keine Alltagssprache“. Statt je Quelle eine eigene Lösung gibt es deshalb
EINEN Lauf (Cron ``zahl_der_woche``, täglich):

1. **Kandidaten sammeln** (ohne Modell): die größten angenommenen
   Beschluss-Beträge der letzten sieben Tage (sonst 30), mit Schalter
   ``haushaltsentwurf-befunde`` die geprüften Befunde, Eckzahlen und Sätze
   eines Haushaltsentwurfs, der gerade beraten wird, und die Zahl der
   Beschlüsse als Rückfall.
2. **Wählen und schreiben** (``MODEL``): eine Zahl, ein Satz, der mit „So
   viel …“ beginnt.
3. **Prüfen im Code**: Die Zahl steht beim Kandidaten, die Einheit stimmt,
   ein genanntes Jahr steht dort auch, keine Ziffer im Satz, kein
   Verwaltungswort. Fällt der Vorschlag, gibt es einen zweiten Anlauf; fällt
   auch der, bleibt die Karte vom letzten Mal stehen (oder „Heute“ rechnet
   den größten Betrag selbst aus).

Neu gewählt wird nur, wenn ein Kandidat dazukam oder der gewählte wegfiel —
sonst bleibt die Zahl über die Woche stehen und der Lauf kostet nichts.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, timedelta

from council.plan_judge import cost_usd
from kern import features, llm, prompts

_log = logging.getLogger(__name__)

#: Sol, weil Luna in der Probe (25.11.2026, Vorbericht 2027) dreimal drei
#: verschiedene Zahlen nahm (Kitas 2030, Gesamtausgaben, Defizit) und die Sätze
#: teils nicht sagten, was die Zahl misst; Sol nahm dreimal das Defizit 2027.
MODEL = os.environ.get("COUNCIL_WEEK_NUMBER_MODEL", "openai/gpt-6-sol")
WINDOW_DAYS = 7
MAX_CHARS = 100
MAX_DECISIONS = 8
#: Verwaltungswörter, die im Satz durchfallen — Tims Beispiele und ihre Nachbarn.
JARGON_RE = re.compile(
    r"Jahresergebnis|Fehlbedarf|Saldo|Aufwend|Ertr[äa]g|Finanzplan|Haushaltssicherung|Konsolidierung"
    r"|Liquidit|ordentlich|Ergebnishaushalt|Finanzhaushalt|Verwaltungstätigkeit|Kernhaushalt|Defizit"
    r"|überplanmäßig|außerplanmäßig|Bewilligung|Teilhaushalt|Kostenstelle|Deckung|Mehraufwand", re.I)
_YEAR_RE = re.compile(r"(?:19|20)\d\d")
#: Eine Zahl im Satz, die kein Jahr ist („59.000“, „0,9“, „300“).
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def _numbers(text: str) -> list[float]:
    """Die Zahlen eines Satzes ohne Jahre, deutsch geschrieben."""
    out = []
    for t in _NUMBER_RE.findall(text or ""):
        if _YEAR_RE.fullmatch(t):
            continue
        t = t.replace(".", "").replace(",", ".") if "," in t or re.fullmatch(r"\d{1,3}(?:\.\d{3})+", t) else t
        try:
            out.append(float(t))
        except ValueError:
            pass
    return out
_EURO = {"€", "euro", "eur"}


# ---- Kandidaten ------------------------------------------------------------------

def _budget(store, today: date) -> list[dict]:
    """Die geprüften Angaben des Haushaltsentwurfs, der gerade beraten wird
    (Sitzung höchstens sieben Tage entfernt) — nur mit dem Schalter."""
    if not features.an("haushaltsentwurf-befunde"):
        return []
    for p in store.budget_report_items((today - timedelta(days=WINDOW_DAYS)).isoformat(),
                                       (today + timedelta(days=WINDOW_DAYS)).isoformat()):
        befunde = store.item_budget_findings(p["ksinr"], p["item_number"])
        if not befunde:
            continue
        stored = store.budget_draft_findings(befunde["document_id"]) or {}
        payload = stored.get("payload") or {}
        year = payload.get("budget_year")
        base = {"kind": "budget", "context": f"Haushaltsentwurf {year}" if year else "Haushaltsentwurf",
                "budget_year": year, "ksinr": p["ksinr"], "item_number": p["item_number"],
                "session_date": p["session_date"], "committee": p["committee"]}
        did = befunde["document_id"]
        out = []
        for i, f in enumerate(payload.get("findings") or []):
            k = f["key_figure"]
            out.append({**base, "id": f"h{did}b{i}", "value": k["value"], "unit": k["unit"],
                        "label": k["label"], "title": f["title"], "text": f["text"]})
        gesamt = payload.get("overview") or {}
        for i, f in enumerate(gesamt.get("facts") or []):
            out.append({**base, "id": f"h{did}e{i}", "value": f["value"], "unit": f["unit"],
                        "label": f["label"], "quote": f.get("quote")})
        for i, x in enumerate(gesamt.get("statements") or []):
            out.append({**base, "id": f"h{did}s{i}", "text": x["text"], "quote": x["quote"]})
        return out
    return []


def candidates(store, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out = _budget(store, today)
    for days in (WINDOW_DAYS, 30):
        seit = (today - timedelta(days=days)).isoformat()
        rows, gesehen = [], set()
        # Derselbe Beschluss steht oft zweimal da (Verwaltungsausschuss, dann Rat).
        for r in store.top_amount_decisions(seit, today.isoformat(), MAX_DECISIONS * 2):
            if (r["title"], r["amount_eur"]) not in gesehen and len(rows) < MAX_DECISIONS:
                gesehen.add((r["title"], r["amount_eur"]))
                rows.append(r)
        if rows:
            out += [{"id": f"d{r['id']}", "kind": "decision", "value": r["amount_eur"], "unit": "€",
                     "title": r["title"], "summary": r["simple_summary"], "committee": r["committee"],
                     "session_date": r["session_date"], "decision_id": r["id"], "window_days": days}
                    for r in rows]
            break
    for days in (WINDOW_DAYS, 30, 90):
        seit = (today - timedelta(days=days)).isoformat()
        if n := store.count_decisions_since(seit):
            out.append({"id": f"c{days}", "kind": "count", "value": n, "unit": "Beschlüsse",
                        "text": f"Abstimmungen in Rat und Ausschüssen in den letzten {days} Tagen",
                        "date_from": seit, "window_days": days})
            break
    return out


_PROMPT_FIELDS = ("id", "kind", "value", "unit", "label", "title", "text", "quote", "summary", "committee",
                  "session_date", "context")


def _prompt_view(c: dict) -> dict:
    return {k: c[k] for k in _PROMPT_FIELDS if c.get(k) not in (None, "")}


# ---- Prüfen ----------------------------------------------------------------------

def _source_text(c: dict) -> str:
    # Das Sitzungsdatum zählt mit: „So viel darf das Sozialamt 2026 zusätzlich
    # ausgeben“ nennt das Jahr des Beschlusses, nicht eines aus dem Text.
    return " ".join(str(c.get(k) or "") for k in ("label", "title", "text", "quote", "summary", "context",
                                                  "session_date"))


def _unit(u: str) -> str:
    u = " ".join(str(u or "").split())
    return "€" if u.lower() in _EURO else u


def check(raw: dict, cands: list[dict]) -> tuple[dict | None, str | None]:
    """Die fertige Karte — oder der Grund, warum der Vorschlag fällt."""
    raw = raw if isinstance(raw, dict) else {}
    c = next((x for x in cands if x["id"] == raw.get("id")), None)
    if c is None:
        return None, "unbekannter Kandidat"
    v = raw.get("value")
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None, "Zahl fehlt"
    value, unit = abs(float(v)), _unit(raw.get("unit"))
    pool = [abs(float(c["value"]))] if "value" in c else [abs(x) for x in _numbers(c["text"])]
    if not any(abs(value - x) <= max(0.051, x * 0.005) for x in pool):
        return None, f"Zahl {value} steht nicht beim Kandidaten"
    quelle = _source_text(c)
    if "value" in c and unit != _unit(c["unit"]):
        return None, f"Einheit {unit!r} statt {c['unit']!r}"
    if "value" not in c and (not unit or unit not in quelle):
        return None, f"Einheit {unit!r} steht nicht beim Kandidaten"
    satz = " ".join(str(raw.get("sentence") or "").split())
    if not re.match(r"So viele?\b", satz) or len(satz) > MAX_CHARS:
        return None, "Satz beginnt nicht mit „So viel“ oder ist zu lang"
    # Die große Zahl steht schon da; eine andere Zahl darf es nur geben, wenn
    # sie beim Kandidaten steht („in den letzten 90 Tagen“, Prod 26.11.2026).
    erlaubt = _numbers(quelle)
    for x in _numbers(satz):
        if any(abs(x - y) <= max(0.051, y * 0.005) for y in pool):
            return None, "Satz wiederholt die Zahl"
        if x not in erlaubt:
            return None, f"Zahl {x} im Satz steht nicht beim Kandidaten"
    if m := JARGON_RE.search(satz):
        return None, f"Fachwort {m.group(0)!r}"
    jahre = set(_YEAR_RE.findall(satz))
    if not jahre <= set(_YEAR_RE.findall(quelle)):
        return None, "Jahr steht nicht beim Kandidaten"
    if c["kind"] == "budget" and not jahre:
        return None, "Jahr fehlt"
    return card(c, value, unit, satz), None


def card(c: dict, value: float, unit: str, sentence: str) -> dict:
    """Die Antwort für „Heute“ in der Form des Vertrags (``NumberOfTheWeek``).
    Beschluss und Anzahl behalten ihre Arten von vorher — die ausgelieferte
    App kennt sie und zeigt sie weiter."""
    if c["kind"] == "decision":
        return {"kind": "amount", "amount_eur": float(c["value"]), "decision_id": c["decision_id"],
                "title": c["title"], "sentence": sentence, "session_date": c["session_date"],
                "window_days": c["window_days"]}
    if c["kind"] == "count":
        return {"kind": "count", "count": int(c["value"]), "window_days": c["window_days"],
                "date_from": c["date_from"], "sentence": sentence}
    return {"kind": "budget_draft", "value": value, "unit": unit, "sentence": sentence,
            "budget_year": c["budget_year"], "ksinr": c["ksinr"], "item_number": c["item_number"],
            "session_date": c["session_date"], "committee": c["committee"], "window_days": WINDOW_DAYS}


# ---- Lauf ------------------------------------------------------------------------

def _json(resp) -> dict:
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except (AttributeError, IndexError, TypeError, ValueError):
        return {}


def choose(cands: list[dict]) -> tuple[dict | None, str | None, float]:
    """Wählen lassen und prüfen, zwei Anläufe. ``(karte, kandidat, kosten)``."""
    cost = 0.0
    view = [_prompt_view(c) for c in cands]
    for _ in range(2):
        resp = llm.chat_complete(
            model=MODEL, response_format={"type": "json_object"}, max_tokens=3_000,
            messages=[{"role": "system", "content": prompts.get("week_number_system")},
                      {"role": "user", "content": "KANDIDATEN:\n" + json.dumps(view, ensure_ascii=False)}],
            _feature="week_number", _geduld=True)
        cost += cost_usd(resp, MODEL)
        raw = _json(resp)
        result, reason = check(raw, cands)
        if result:
            return result, raw["id"], cost
        _log.info("Zahl der Woche verworfen: %s", reason)
    return None, None, cost


def needs_new(last: dict | None, cands: list[dict]) -> bool:
    """Neu wählen, wenn es noch keine Karte gibt, ein Kandidat dazukam, der
    gewählte wegfiel oder seine Zahl sich änderte (die Anzahl wächst)."""
    if not last:
        return True
    ids = {c["id"] for c in cands}
    source = next((c for c in cands if c["id"] == last["source_id"]), None)
    if source is None or not ids <= set(last["candidate_ids"]):
        return True
    return source["kind"] == "count" and last["payload"].get("count") != source["value"]


def run(store, today: date | None = None, *, force: bool = False) -> dict:
    """Der tägliche Lauf. Gibt Kennzahlen für ``job_runs`` zurück."""
    today = today or date.today()
    cands = candidates(store, today)
    if not cands:
        return {"kandidaten": 0, "neu": 0}
    last = store.latest_week_number((today - timedelta(days=WINDOW_DAYS - 1)).isoformat())
    if not force and not needs_new(last, cands):
        return {"kandidaten": len(cands), "neu": 0}
    result, source, cost = choose(cands)
    if result is None:
        return {"kandidaten": len(cands), "neu": 0, "verworfen": 1, "kosten_usd": round(cost, 4)}
    store.save_week_number(today.isoformat(), sorted(c["id"] for c in cands), source or "", result,
                           MODEL, round(cost, 5))
    return {"kandidaten": len(cands), "neu": 1, "quelle": result["kind"], "kosten_usd": round(cost, 4)}
