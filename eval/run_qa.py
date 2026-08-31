#!/usr/bin/env python3
"""Eval-Suite fuer die KI-Frage ("Frag den Stadtrat").

Misst drei Dinge gegen handgelabelte Fragen (``cases_qa.json``):

1. **Retrieval** — findet die Hybrid-Suche (Vektor + BM25 + Reranker) die
   erwarteten Beschluesse? Metriken: Trefferquote (>= 1 expected id in den
   Quellen) und MRR (mittlerer Kehrwert des Rangs des ersten Treffers).
2. **Antwort-A/B** — dieselben Kandidaten, zwei Antwort-Laeufe: einmal MIT
   Tragweite-Hinweis im Kontext (#258) und einmal OHNE (impact-Felder vor dem
   Prompt entfernt = Stand vor #258). Je Arm: zitiert die Antwort >= 1
   erwarteten Beschluss, wie oft zitiert sie Formalien (impact <= 15), und
   fuehrt sie mit einer Formalie an?
3. **Latenz** — Millisekunden je Pipeline-Schritt (Expansion, Vektor, BM25,
   Rerank, Kontext, Antwort), als Mittel/p50/p95 ueber alle Faelle. Der
   Kaltstart (erstes Laden von Embedding- und Reranker-Modell) wird getrennt
   ausgewiesen, weil der laufende Dienst ihn nur einmal zahlt.

Gold-Cases gibt es in zwei Formen: ``expected_ids`` sind an die ids der
Prod-Datenbank gebunden; ``expected_keys`` beschreiben die Beschluesse ueber
natuerliche Schluessel (template_number, session_date, title_like, committee) und
laufen damit gegen jede DB-Kopie — Prod, dev oder eine lokal gescrapte
Teil-DB. Faelle, die sich in der aktuellen DB nicht aufloesen lassen (Teil-DB
ohne den Zeitraum), werden sichtbar uebersprungen statt falsch gemessen.

Braucht die echte ``council.sqlite`` (Embeddings + FTS + Reranker-Modell) und
``OPENROUTER_API_KEY`` — praktisch: auf dem Server laufen lassen::

    python eval/run_qa.py --rate-missing --save

Schnelle Iteration ohne Antwort-LLM (misst nur Retrieval + Latenz)::

    python eval/run_qa.py --nur-retrieval

Einmalige Migration alter id-gebundener Faelle (auf der Prod-DB)::

    python eval/run_qa.py --emit-keys

``--rate-missing`` bewertet vorab die Tragweite der Antwort-Kandidaten ohne
Score (solange der grosse Backfill laeuft), damit der MIT-Arm echte Hinweise
sieht. Die Metrik-Logik ist offline testbar (``evaluate`` bekommt injizierte
Funktionen, siehe tests/test_qa_eval.py).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from eval import harness  # noqa: E402

# Gleiche Groessen wie der /council/ask-Endpoint (web/backend/app/routers/council.py).
TOP_K = 40
ANSWER_N = 20
FORMALITY_MAX = 15  # deckungsgleich mit dem "Tragweite: gering"-Marker in council/qa.py

# Schluessel, die ein expected_keys-Eintrag tragen darf (= Filter von
# CouncilStore.find_decision_ids). Alles andere ist ein Tippfehler im Case und
# soll laut scheitern statt still nichts zu finden.
KEY_FIELDS = ("template_number", "committee", "session_date", "title_like")


# --------------------------------------------------------------------------- #
# Gold-Case-Aufloesung — portable Schluessel vor prod-ids
# --------------------------------------------------------------------------- #

def resolve_expected(find_ids: Callable[..., list[int]], case: dict) -> list[int]:
    """Erwartete Beschluss-ids eines Falls in der GERADE geoeffneten DB.

    ``expected_keys`` (portabel) schlaegt ``expected_ids`` (prod-gebunden).
    Liefert [], wenn der Fall in dieser DB-Kopie nicht aufloesbar ist — der
    Runner ueberspringt ihn dann sichtbar, statt gegen fremde ids zu messen.
    ``find_ids`` ist injiziert (CouncilStore.find_decision_ids), damit die
    Logik offline testbar bleibt."""
    keys = case.get("expected_keys")
    if not keys:
        return list(case.get("expected_ids") or [])
    out: list[int] = []
    for spec in keys:
        unknown = set(spec) - set(KEY_FIELDS)
        if unknown:
            raise ValueError(f"Fall {case.get('id')}: unbekannte Schluessel {sorted(unknown)}")
        for did in find_ids(**spec):
            if did not in out:
                out.append(did)
    return out


def emit_keys(store, cases: list[dict]) -> None:
    """Alte id-gebundene Faelle in die portable Schluesselform uebersetzen.

    Auf der Datenbank laufen lassen, zu der die ids gehoeren (Prod). Druckt je
    Fall einen ``expected_keys``-Vorschlag zum Einpflegen in cases_qa.json —
    bevorzugt (template_number, committee), sonst (session_date, title_like)."""
    for case in cases:
        if case.get("expected_keys"):
            continue
        rows = store.get_decisions_by_ids(list(case.get("expected_ids") or []))
        missing = set(case.get("expected_ids") or []) - {r["id"] for r in rows}
        specs = []
        for r in rows:
            if r.get("template_number"):
                spec: dict = {"template_number": r["template_number"]}
                if r.get("committee"):
                    spec["committee"] = r["committee"]
            else:
                title_frag = " ".join((r.get("title") or "").split()[:6])
                spec = {"session_date": r.get("session_date"), "title_like": title_frag}
            if spec not in specs:
                specs.append(spec)
        print(f'  "{case["id"]}":')
        print('    "expected_keys": ' + json.dumps(specs, ensure_ascii=False))
        if missing:
            print(f"    // NICHT in dieser DB: {sorted(missing)}")


# --------------------------------------------------------------------------- #
# Metrik-Kern — pure Funktionen, offline testbar
# --------------------------------------------------------------------------- #

DEBATTE_FIELDS = ("sprecher", "session_date", "text_like")


def debatten_treffer(specs: list[dict], rows: list[dict]) -> list[bool]:
    """Je erwartetem Wortbeitrag: liegt er in den gefundenen Debatten?

    Ein Spec beschreibt den Beitrag über natürliche Merkmale (``sprecher``,
    ``session_date``, ``text_like``) statt über eine id — dieselbe Portabilität
    wie bei ``expected_keys``. Alle angegebenen Felder müssen passen;
    ``text_like`` prüft Teilstring in Beitrag ODER Verwaltungsantwort."""
    out: list[bool] = []
    for spec in specs:
        unknown = set(spec) - set(DEBATTE_FIELDS)
        if unknown:
            raise ValueError(f"unbekannte Debatten-Schluessel {sorted(unknown)}")
        hit = False
        for r in rows:
            if spec.get("sprecher") and spec["sprecher"].lower() not in (r.get("sprecher") or "").lower():
                continue
            if spec.get("session_date") and spec["session_date"] != (r.get("session_date") or ""):
                continue
            if spec.get("text_like"):
                heu = f"{r.get('text') or ''} {r.get('antwort') or ''}".lower()
                if spec["text_like"].lower() not in heu:
                    continue
            hit = True
            break
        out.append(hit)
    return out


def _first_rank(retrieved: list[int], expected: set[int]) -> int | None:
    for i, rid in enumerate(retrieved, start=1):
        if rid in expected:
            return i
    return None


def _is_formality(impact_map: dict[int, int | None], rid: int) -> bool:
    v = impact_map.get(rid)  # impact 0 ist eine echte Formalie — kein `or`-Falsy!
    return v is not None and v <= FORMALITY_MAX


def _arm_stats(per_case: list[dict], arm: str) -> dict:
    cited_lists = [c[f"cited_{arm}"] for c in per_case]
    impacts = [c["impact_of"] for c in per_case]
    cite_expected = sum(1 for c, cl in zip(per_case, cited_lists)
                        if set(cl) & set(c["expected"]))
    formality = sum(1 for cl, imp in zip(cited_lists, impacts)
                    for rid in cl if _is_formality(imp, rid))
    lead_formality = sum(1 for cl, imp in zip(cited_lists, impacts)
                         if cl and _is_formality(imp, cl[0]))
    n_cited = sum(len(cl) for cl in cited_lists)
    return {
        "cite_expected_rate": round(cite_expected / len(per_case), 4) if per_case else 0.0,
        "citations": n_cited,
        "formality_citations": formality,
        "lead_formality_cases": lead_formality,
    }


def aggregate_latency(per_case_ms: list[dict]) -> dict:
    """Mittel/p50/p95 je Zeit-/Kostenschluessel ueber alle Faelle (fehlende
    Werte werden ignoriert — z. B. antwort_ms bei --nur-retrieval).
    Millisekunden ganzzahlig; ``*_ct``-Schluessel (Kosten in Cent) behalten
    zwei Nachkommastellen — eine Frage kostet Bruchteile eines Cents."""
    out: dict = {}
    keys = {k for t in per_case_ms for k in t}
    for key in sorted(keys):
        vals = [t[key] for t in per_case_ms if isinstance(t.get(key), (int, float))]
        if not vals:
            continue
        vals.sort()
        nd = 2 if key.endswith("_ct") else None
        out[key] = {
            "mean": round(statistics.fmean(vals), nd),
            "p50": round(vals[len(vals) // 2], nd),
            "p95": round(vals[min(len(vals) - 1, int(len(vals) * 0.95))], nd),
        }
    return out


def evaluate(
    cases: list[dict],
    retrieve: Callable[[dict], list[int]],
    answer: Callable[[dict, bool], list[int]],
    impact_of: Callable[[dict], dict[int, int | None]],
    expected_of: Callable[[dict], list[int]] | None = None,
    debatten_of: Callable[[dict], list[dict]] | None = None,
) -> dict:
    """Kern-Auswertung mit injizierten Funktionen.

    ``retrieve(case)``   -> Kandidaten-ids in Relevanz-Reihenfolge.
    ``answer(case, with_impact)`` -> zitierte ids in Zitier-Reihenfolge.
    ``impact_of(case)``  -> {id: impact | None} fuer die Kandidaten des Falls.
    ``expected_of(case)`` -> erwartete ids (Default: case["expected_ids"]).
    ``debatten_of(case)`` -> gefundene Wortbeitraege; nur noetig fuer Faelle
    mit ``expected_debatten`` (Beschluesse allein beantworten manche Frage
    nicht — die Substanz steht im Protokoll).
    """
    expected_of = expected_of or (lambda c: c["expected_ids"])
    per_case: list[dict] = []
    for case in cases:
        expected = list(expected_of(case))
        retrieved = retrieve(case)
        rank = _first_rank(retrieved, set(expected))
        eintrag = {
            "id": case["id"],
            "expected": expected,
            "retrieved_n": len(retrieved),
            "first_expected_rank": rank,
            "cited_mit": answer(case, True),
            "cited_ohne": answer(case, False),
            "impact_of": impact_of(case),
        }
        specs = case.get("expected_debatten")
        if specs and debatten_of:
            treffer = debatten_treffer(specs, debatten_of(case))
            eintrag["debatten"] = {
                "erwartet": len(specs), "gefunden": sum(treffer),
                "fehlend": [s for s, ok in zip(specs, treffer) if not ok],
            }
        per_case.append(eintrag)

    hits = [c for c in per_case if c["first_expected_rank"] is not None]
    mrr = sum(1.0 / c["first_expected_rank"] for c in hits) / len(per_case) if per_case else 0.0
    mit_deb = [c for c in per_case if c.get("debatten")]
    result = {
        "suite": "qa",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "cases": len(per_case),
        "retrieval": {
            "hit_rate": round(len(hits) / len(per_case), 4) if per_case else 0.0,
            "mrr": round(mrr, 4),
        },
        "arms": {
            "mit_tragweite": _arm_stats(per_case, "mit"),
            "ohne_tragweite": _arm_stats(per_case, "ohne"),
        },
        "details": [
            {k: v for k, v in c.items() if k != "impact_of"} for c in per_case
        ],
    }
    if mit_deb:
        erwartet = sum(c["debatten"]["erwartet"] for c in mit_deb)
        gefunden = sum(c["debatten"]["gefunden"] for c in mit_deb)
        result["debatten"] = {
            "cases": len(mit_deb), "erwartet": erwartet, "gefunden": gefunden,
            "recall": round(gefunden / erwartet, 4) if erwartet else 0.0,
        }
    return result


def print_qa_report(result: dict) -> None:
    line = "-" * 60
    r = result["retrieval"]
    print(f"\n{line}")
    print(f"  Suite     : qa  ({result['cases']} Fragen"
          + (f", {result['skipped']} uebersprungen" if result.get("skipped") else "") + ")")
    print(f"  Retrieval : Trefferquote {r['hit_rate']:.0%} · MRR {r['mrr']:.2f}")
    if result.get("debatten"):
        d = result["debatten"]
        print(f"  Debatten  : {d['gefunden']}/{d['erwartet']} erwartete Wortbeiträge "
              f"({d['recall']:.0%}) in {d['cases']} Fall/Fällen")
    if result.get("arms"):
        print(f"  {'Antwort-Arm':18} {'zitiert erwartet':>17} {'Zitate':>7} {'Formalie zitiert':>17} {'fuehrt m. Formalie':>19}")
        for name, a in result["arms"].items():
            print(f"  {name:18} {a['cite_expected_rate']:>16.0%} {a['citations']:>7} "
                  f"{a['formality_citations']:>17} {a['lead_formality_cases']:>19}")
    if result.get("latency"):
        print(f"  {'Latenz (ms)':18} {'mean':>7} {'p50':>7} {'p95':>7}")
        for key, v in result["latency"].items():
            if key.endswith("_ct"):
                continue  # Kosten stehen unten in Cent, nicht in der ms-Tabelle
            print(f"  {key:18} {v['mean']:>7} {v['p50']:>7} {v['p95']:>7}")
        if result.get("cold_start_ms") is not None:
            print(f"  Kaltstart (Modelle laden, einmal je Prozess): {result['cold_start_ms']} ms")
    if result.get("kosten") is not None:
        lat = result.get("latency") or {}
        teile = " + ".join(
            f"{name} {lat[key]['mean']:.2f}"
            for key, name in (("analyse_ct", "Analyse"), ("antwort_ct", "Antwort")) if key in lat)
        je_frage = f" (Ø ¢/Frage: {teile})" if teile else ""
        k = result["kosten"]
        ohne = f" · {k['calls_ohne_cost']} Aufrufe ohne Kostenwert (Summe = Untergrenze)" if k["calls_ohne_cost"] else ""
        print(f"  Kosten     : Lauf gesamt {k['lauf_usd']:.4f} ${je_frage}{ohne}")
    print(line)
    for d in result["details"]:
        rank = d["first_expected_rank"]
        mark = "ok " if rank else "MISS"
        deb = ""
        if d.get("debatten"):
            db = d["debatten"]
            deb = f"  debatten={db['gefunden']}/{db['erwartet']}"
            if db["fehlend"]:
                deb += f" fehlt: {db['fehlend']}"
        print(f"  [{mark}] {d['id']:22} rank={rank if rank else '-':>3}  "
              f"mit={d['cited_mit']}  ohne={d['cited_ohne']}{deb}")
    for name in result.get("skipped_ids", []):
        print(f"  [skip] {name:22} (in dieser DB nicht aufloesbar)")


def print_latency_compare(result: dict, prev: dict, prev_name: str) -> None:
    """Latenz-Deltas gegen den letzten gespeicherten Lauf — macht sichtbar, was
    ein neues Feature die Antwortzeit kostet."""
    if not (result.get("latency") and prev.get("latency")):
        return
    print(f"\n  Latenz-/Kosten-Delta vs. {prev_name} (mean; ms bzw. ¢):")
    for key in result["latency"]:
        if key in prev["latency"]:
            a, b = prev["latency"][key]["mean"], result["latency"][key]["mean"]
            arrow = "↑" if b > a else ("↓" if b < a else "→")
            delta = round(b - a, 2 if key.endswith("_ct") else None)
            print(f"    {key:14}: {a:>7} {arrow} {b:>7}  ({'+' if delta >= 0 else ''}{delta})")


# --------------------------------------------------------------------------- #
# Echte Verdrahtung (Server: council.sqlite + fastembed + API-Key)
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="KI-Frage gegen das QA-Golden-Set messen")
    ap.add_argument("--save", action="store_true", help="Ergebnis nach eval/results/qa/ schreiben")
    ap.add_argument("--rate-missing", action="store_true",
                    help="Tragweite der unbewerteten Antwort-Kandidaten vorab per LLM bewerten")
    ap.add_argument("--nur-retrieval", action="store_true",
                    help="Antwort-Arme ueberspringen: misst Retrieval + Latenz ohne Antwort-LLM")
    ap.add_argument("--nur-portable", action="store_true",
                    help="Nur Faelle mit expected_keys (fuer lokale/dev-DB-Kopien mit fremden ids)")
    ap.add_argument("--emit-keys", action="store_true",
                    help="expected_keys-Vorschlaege fuer id-gebundene Faelle drucken (auf Prod laufen lassen)")
    ap.add_argument("--db", default=None, help="Pfad zur council.sqlite (Default: data/council.sqlite)")
    args = ap.parse_args()

    import os

    from council import qa
    from council import vorlagen as vorlagen_mod
    from council import embeddings as emb
    from council.store import CouncilStore
    from kern import llm

    def kosten_ct_seit(usd_start: float) -> float:
        """Echte LLM-Kosten (OpenRouter usage.cost) seit ``usd_start``, in Cent."""
        return round((llm.session_cost()["usd"] - usd_start) * 100, 3)

    root = Path(__file__).parent.parent
    store = CouncilStore(Path(args.db or os.environ.get("COUNCIL_DB") or root / "data" / "council.sqlite"))
    cases = harness.load_cases("cases_qa.json")

    if args.emit_keys:
        emit_keys(store, cases)
        store.close()
        return 0

    if args.nur_portable:
        cases = [c for c in cases if c.get("expected_keys")]

    # Erwartete ids je Fall in DIESER DB aufloesen; Unaufloesbares faellt raus.
    resolved: dict[str, list[int]] = {c["id"]: resolve_expected(store.find_decision_ids, c) for c in cases}
    skipped = [cid for cid, ids in resolved.items() if not ids]
    cases = [c for c in cases if resolved[c["id"]]]
    if skipped:
        print(f"{len(skipped)} Fall/Faelle in dieser DB nicht aufloesbar: {', '.join(skipped)}", flush=True)

    # Kaltstart einmal vorab zahlen (Embedding- + Reranker-Modell laden), damit
    # die Latenzwerte je Fall den laufenden Dienst abbilden, nicht den Start.
    t0 = time.perf_counter()
    try:
        emb.hybrid_search(store, "Radverkehr", "Radverkehr Fahrrad", top_k=1, pool=5)
        cold_start_ms: int | None = round((time.perf_counter() - t0) * 1000)
    except Exception:  # noqa: BLE001 — ohne fastembed misst der Lauf nichts Sinnvolles
        print("fastembed/Reranker nicht verfuegbar — Hybrid-Retrieval ist Pflicht fuer die Eval.", file=sys.stderr)
        store.close()
        return 1

    # Ein Retrieval je Fall, von beiden Armen geteilt (identische Kandidaten,
    # nur der Kontext unterscheidet sich) — sonst misst man Retrieval-Rauschen.
    # Der Pfad spiegelt den /ask-Endpoint inklusive Fragetyp-Routing (Analyse,
    # Partei-Anreicherung, Verlaufs-Sortierung).
    cache: dict[str, list[dict]] = {}
    typen: dict[str, str] = {}
    analysen: dict[str, dict] = {}
    latenz: dict[str, dict] = {}

    def candidates_of(case: dict) -> list[dict]:
        if case["id"] not in cache:
            q = case["question"]
            t = latenz.setdefault(case["id"], {})
            t_exp, c_exp = time.perf_counter(), llm.session_cost()["usd"]
            # Ketten-Faelle (Chat): case["verlauf"] traegt die Vorrunden — die
            # Analyse muss daraus eine eigenstaendige Suchfrage kondensieren.
            analyse = qa.analyse_query(q, verlauf=case.get("verlauf"))
            expanded, typ = analyse["terms"], analyse["kind"]
            typen[case["id"]] = typ
            analysen[case["id"]] = analyse
            t["expand_ms"] = round((time.perf_counter() - t_exp) * 1000)
            t["analyse_ct"] = kosten_ct_seit(c_exp)
            t_ret = time.perf_counter()
            hits = emb.hybrid_search(store, analyse["question"], expanded, top_k=TOP_K, pool=55, timings=t,
                                     varianten=analyse.get("variants"),
                                     anker_ids=qa.anker_ids_fuer(store, analyse["question"]),
                                     recency=qa.recency_intent(analyse["question"]))
            cands = store.get_decisions_by_ids([h[0] for h in hits])
            qa.markiere_veraltete(store, cands)
            if typ == "party" and analyse.get("party"):
                try:
                    extra_ids = store.antrag_decision_ids(analyse["party"], expanded)
                    have = {c["id"] for c in cands}
                    cands += store.get_decisions_by_ids([i for i in extra_ids if i not in have])
                except Exception:  # noqa: BLE001
                    pass
            t["retrieve_ms"] = round((time.perf_counter() - t_ret) * 1000)
            t_ctx = time.perf_counter()
            ctx = cands[:ANSWER_N]
            try:  # Vorlagen-Auszuege wie im /ask-Endpoint
                texts = store.vorlage_texts_for([c.get("template_number") or "" for c in ctx])
                for c in ctx:
                    txt = texts.get((c.get("template_number") or "").strip())
                    if txt:
                        c["vorlage_excerpt"] = vorlagen_mod.excerpt(txt, 350)
            except Exception:  # noqa: BLE001
                pass
            t["kontext_ms"] = round((time.perf_counter() - t_ctx) * 1000)
            cache[case["id"]] = cands
            print(f"  · {case['id']}: {len(cands)} Kandidaten (typ={typ})", flush=True)
        return cache[case["id"]]

    if args.rate_missing:
        from council.impact import rate_batch
        todo: set[int] = set()
        for case in cases:
            todo.update(c["id"] for c in candidates_of(case)[:ANSWER_N] if c.get("impact") is None)
        # Volle Zeilen laden — get_decisions_by_ids ist die schlanke QA-Query
        # ohne kind, das würde die Struktur-Signale der Rubrik schwächen.
        missing = [d for d in (store.get_decision(i) for i in sorted(todo)) if d]
        print(f"Tragweite vorab: {len(missing)} unbewertete Kandidaten", flush=True)
        for i in range(0, len(missing), 20):
            for did, score, reason in rate_batch(missing[i:i + 20]):
                store.save_impact(did, score, reason)
        for cands in cache.values():  # frische Werte in die gecachten Kandidaten ziehen
            fresh = {d["id"]: d for d in store.get_decisions_by_ids([c["id"] for c in cands])}
            for c in cands:
                c["impact"] = fresh[c["id"]].get("impact")
                c["impact_reason"] = fresh[c["id"]].get("impact_reason")

    def retrieve(case: dict) -> list[int]:
        return [c["id"] for c in candidates_of(case)]

    def answer(case: dict, with_impact: bool) -> list[int]:
        if args.nur_retrieval:
            return []
        ctx = [dict(c) for c in candidates_of(case)[:ANSWER_N]]
        typ = typen.get(case["id"], "topic")
        if typ == "history":
            ctx = qa.sort_verlauf(ctx)
        if not with_impact:
            for c in ctx:
                c.pop("impact", None)
                c.pop("impact_reason", None)
        t_ans, c_ans = time.perf_counter(), llm.session_cost()["usd"]
        _, cited = qa.answer_question(case["question"], ctx, typ=typ)
        t = latenz.setdefault(case["id"], {})
        # Beide Arme laufen nacheinander — das Mittel ist die realistische
        # Zeit (und der realistische Preis) EINER Antwort.
        ms = round((time.perf_counter() - t_ans) * 1000)
        t["antwort_ms"] = round((t["antwort_ms"] + ms) / 2) if "antwort_ms" in t else ms
        ct = kosten_ct_seit(c_ans)
        t["antwort_ct"] = round((t["antwort_ct"] + ct) / 2, 3) if "antwort_ct" in t else ct
        return cited

    def impact_of(case: dict) -> dict[int, int | None]:
        return {c["id"]: c.get("impact") for c in candidates_of(case)}

    debatten_cache: dict[str, list[dict]] = {}

    def debatten_of(case: dict) -> list[dict]:
        """Wortbeiträge wie im /ask-Endpoint: Ähnlichkeitssuche PLUS die
        Aussprache zu den Top-Kandidaten (Stations-Kopplung)."""
        if case["id"] not in debatten_cache:
            cands = candidates_of(case)          # füllt analysen[…] mit
            analyse = analysen[case["id"]]       # kein zweiter Analyse-Call
            rows: list[dict] = []
            try:
                hits = emb.search_wortbeitraege(store, analyse["question"], analyse["terms"])
                rows = store.wortbeitraege_by_ids([wid for wid, _ in hits])
            except Exception:  # noqa: BLE001 — Debatten sind Zusatz, nie Blocker
                pass
            have = {r["id"] for r in rows}
            rows += [w for w in store.wortbeitraege_zu_beschluessen(cands[:8])
                     if w["id"] not in have]
            debatten_cache[case["id"]] = rows
        return debatten_cache[case["id"]]

    try:
        result = evaluate(cases, retrieve, answer, impact_of,
                          expected_of=lambda c: resolved[c["id"]],
                          debatten_of=debatten_of)
    finally:
        store.close()

    if args.nur_retrieval:
        result.pop("arms", None)
    per_case_t = [latenz[c["id"]] for c in cases if c["id"] in latenz]
    for t in per_case_t:
        # vektor/bm25/rerank stecken bereits in retrieve_ms — nicht doppelt zaehlen.
        t["total_ms"] = sum(t.get(k, 0) for k in ("expand_ms", "retrieve_ms", "kontext_ms", "antwort_ms"))
        # Preis EINER echten Frage: Analyse + eine Antwort (antwort_ct ist das Arm-Mittel).
        t["kosten_ct"] = round(t.get("analyse_ct", 0) + t.get("antwort_ct", 0), 3)
    result["latency"] = aggregate_latency(per_case_t)
    result["cold_start_ms"] = cold_start_ms
    sc = llm.session_cost()
    result["kosten"] = {"lauf_usd": round(sc["usd"], 4), "calls_ohne_cost": sc["calls_ohne"]}
    result["skipped"] = len(skipped)
    result["skipped_ids"] = skipped

    prev, prev_path = harness.load_last("qa")
    print_qa_report(result)
    if prev:
        print_latency_compare(result, prev, prev_path.name)
    if args.save:
        out = harness.save_result(result)
        print(f"\n  gespeichert -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
