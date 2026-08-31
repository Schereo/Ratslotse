#!/usr/bin/env python3
"""Qualitatives Antwort-Eval (Tims Auftrag 10.08.): Vorher/Nachher-Vergleich
GANZER Antworten statt nur Retrieval-Treffern.

Zwei Modi:

    # 1) Antworten eines Code-Stands einfrieren (volle Pipeline wie /ask):
    python eval/quality_qa.py --erzeugen vorher --db data/council-prod.sqlite

    # 2) Zwei Stände blind vergleichen (LLM-Judge, A/B je Frage deterministisch
    #    über den Frage-Hash vertauscht) → Markdown-Report:
    python eval/quality_qa.py --judge vorher nachher

Der Judge bewertet je Frage vier Kriterien (Aktualität, Quellentreue,
Vollständigkeit, Klarheit) und begründet in zwei Sätzen — das macht das
„eher Subjektive" wenigstens verblindet und kriteriengebunden. Ergebnisse
liegen versioniert unter eval/results/quality/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import qa  # noqa: E402
from council import vorlagen as vorlagen_mod  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern import llm  # noqa: E402

RESULTS = ROOT / "eval" / "results" / "quality"
# flash statt pro: gemini-2.5-pro verbrennt sein max_tokens-Budget im
# Pflicht-Reasoning und liefert dann abgerissenes JSON (11/12 Fälle am
# 10.08.); flash urteilt die klar rubrizierte Aufgabe zuverlässig.
JUDGE_MODEL = os.environ.get("COUNCIL_QUALITY_JUDGE_MODEL", "google/gemini-2.5-flash")

# Das Fragenset deckt die Akkuratheits-Hebel ab: Stadion (Standing-Direktive),
# Entitäten (inkl. Umgangssprache „Cäci" für den Glossar-Anker), Sachstands-
# Formulierungen (Recency) und Beratungsfolgen (Supersedes).
FRAGEN: list[dict] = [
    {"id": "stadion-stand", "fokus": "stadion+recency",
     "frage": "Wie ist der Stand beim Stadionneubau?"},
    {"id": "stadion-kosten", "fokus": "stadion+geld",
     "frage": "Was kostet das neue Stadion und wer bezahlt es?"},
    {"id": "stadion-parteien", "fokus": "stadion+partei",
     "frage": "Wie stehen die Parteien zum Stadionneubau?"},
    {"id": "stadion-verlauf", "fokus": "stadion+verlauf",
     "frage": "Wie hat sich die Stadionplanung seit 2023 entwickelt?"},
    {"id": "caeci-was", "fokus": "entitaet",
     "frage": "Was passiert mit der Cäcilienbrücke?"},
    {"id": "caeci-slang", "fokus": "entitaet+glossar",
     "frage": "Was ist eigentlich mit der Cäci los?"},
    {"id": "floetenteich", "fokus": "entitaet",
     "frage": "Was wurde zum Flötenteich beschlossen?"},
    {"id": "fliegerhorst", "fokus": "entitaet",
     "frage": "Was ist auf dem Fliegerhorst geplant?"},
    {"id": "entlastungsstrasse-stand", "fokus": "recency",
     "frage": "Wie ist der aktuelle Stand bei der Entlastungsstraße?"},
    {"id": "bplan831", "fokus": "recency+supersedes",
     "frage": "Was gilt aktuell beim Bebauungsplan 831?"},
    {"id": "radverkehr-zuletzt", "fokus": "recency",
     "frage": "Was wurde zuletzt zum Radverkehr beschlossen?"},
    {"id": "schulen-sanierung", "fokus": "breit",
     "frage": "Welche Schulen werden saniert?"},
]


def erzeugen(label: str, db: Path) -> Path:
    """Volle /ask-Pipeline je Frage (Analyse → Retrieval inkl. Varianten →
    Presse/Debatten/Haushalt → one-shot-Antwort) — der ehrliche Stand des
    aktuellen Codes, eingefroren als JSON."""
    from council import embeddings as emb

    store = CouncilStore(db)
    cases = []
    try:
        for f in FRAGEN:
            t0 = time.perf_counter()
            analyse = qa.analyse_query(f["frage"])
            expanded, typ = analyse["terms"], analyse["kind"]
            q_suche = analyse["question"]
            hits = emb.hybrid_search(store, q_suche, expanded, top_k=40, pool=55,
                                     varianten=analyse.get("variants"),
                                     anker_ids=qa.anker_ids_fuer(store, q_suche),
                                     recency=qa.recency_intent(q_suche))
            cands = store.get_decisions_by_ids([h[0] for h in hits])
            qa.markiere_veraltete(store, cands)
            presse_rows, debatten_rows, haushalt = [], [], []
            try:
                presse_rows = store.presse_by_ids(
                    [p for p, _ in emb.search_presse(store, q_suche, expanded)])
            except Exception:  # noqa: BLE001
                pass
            try:
                debatten_rows = store.wortbeitraege_by_ids(
                    [w for w, _ in emb.search_wortbeitraege(store, q_suche, expanded)])
            except Exception:  # noqa: BLE001
                pass
            if typ == "money":
                try:
                    haushalt = store.haushalt_fuer_begriffe(expanded.split())
                except Exception:  # noqa: BLE001
                    pass
            daten = sorted(str(c.get("session_date") or "")[:4] for c in cands[:20]
                           if c.get("session_date"))
            spanne = (int(daten[-1]) - int(daten[0])) if len(daten) >= 2 and daten[0].isdigit() else 0
            gross = len(cands) >= 25 or spanne >= 3
            ctx = cands[:20]
            if typ == "history":
                ctx = qa.sort_verlauf(ctx)
            try:
                texts = store.vorlage_texts_for([c.get("template_number") or "" for c in ctx])
                for c in ctx:
                    t = texts.get((c.get("template_number") or "").strip())
                    if t:
                        c["vorlage_excerpt"] = vorlagen_mod.excerpt(t, 350)
            except Exception:  # noqa: BLE001
                pass
            answer, cited = qa.answer_question(
                f["frage"], ctx, typ=typ, presse=presse_rows,
                haushalt=haushalt, debatten=debatten_rows, gross=gross)
            cases.append({
                "id": f["id"], "fokus": f["fokus"], "frage": f["frage"], "typ": typ,
                "answer": qa.split_followups(answer)[0], "cited": cited,
                "quellen": [{"id": c["id"], "title": c.get("title"),
                             "datum": c.get("session_date")} for c in ctx],
                "debatten_n": len(debatten_rows), "presse_n": len(presse_rows),
                "ms": round((time.perf_counter() - t0) * 1000),
            })
            print(f"  · {f['id']}: {len(cands)} Kandidaten, {len(cited)} zitiert, "
                  f"{cases[-1]['ms']} ms", flush=True)
    finally:
        store.close()
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{label}.json"
    out.write_text(json.dumps({"label": label, "db": str(db), "cases": cases},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gespeichert: {out}")
    return out


JUDGE_PROMPT = """Du vergleichst zwei Antworten eines Ratsinformations-Assistenten auf dieselbe Bürgerfrage über den Oldenburger Stadtrat. Du weißt nicht, welche Antwort von welcher Systemversion stammt.

FRAGE: {frage}

ANTWORT A:
{a}

QUELLEN VON A (Titel · Sitzungsdatum): {qa}

ANTWORT B:
{b}

QUELLEN VON B (Titel · Sitzungsdatum): {qb}

Bewerte vier Kriterien. Je Kriterium: "A", "B" oder "gleich".
1. aktualitaet — Stellt die Antwort den NEUESTEN Stand als geltend dar (statt veraltete Zwischenstände als aktuell zu verkaufen)? Nutze die Sitzungsdaten der Quellen.
2. quellentreue — Wirken die Aussagen von den zitierten Quellen gedeckt (Titel/Daten plausibel, keine erkennbaren Übertreibungen)?
3. vollstaendigkeit — Deckt die Antwort die naheliegenden Aspekte der Frage ab?
4. klarheit — Struktur, Verständlichkeit, angemessene Länge.

Antworte NUR als JSON:
{{"aktualitaet": "A|B|gleich", "quellentreue": "A|B|gleich", "vollstaendigkeit": "A|B|gleich", "klarheit": "A|B|gleich", "gesamt": "A|B|gleich", "begruendung": "2 Sätze, konkret, mit dem entscheidenden Unterschied"}}"""


def judge(label_a: str, label_b: str) -> Path:
    """Blind-Vergleich: Seiten je Frage deterministisch vertauscht (Hash der
    Frage), damit weder Reihenfolge noch Label durchsickern."""
    a_data = json.loads((RESULTS / f"{label_a}.json").read_text(encoding="utf-8"))
    b_data = json.loads((RESULTS / f"{label_b}.json").read_text(encoding="utf-8"))
    b_by_id = {f["id"]: f for f in b_data["cases"]}
    zeilen, urteile = [], []
    for fa in a_data["cases"]:
        fb = b_by_id.get(fa["id"])
        if not fb:
            continue
        getauscht = int(hashlib.sha1(fa["frage"].encode()).hexdigest(), 16) % 2 == 1
        links, rechts = (fb, fa) if getauscht else (fa, fb)

        def qliste(f):
            return "; ".join(f"{q['title']} · {q['datum']}" for q in f["quellen"][:8])

        raw = None
        for versuch in range(2):
            resp = llm.chat_complete(
                model=JUDGE_MODEL, _feature="quality_judge", temperature=0,
                max_tokens=2500, timeout=120.0, response_format={"type": "json_object"},
                messages=[{"role": "user", "content": JUDGE_PROMPT.format(
                    frage=fa["frage"], a=links["answer"][:5000], b=rechts["answer"][:5000],
                    qa=qliste(links), qb=qliste(rechts))}])
            try:
                raw = json.loads((resp.choices[0].message.content or "{}").strip())
                break
            except (ValueError, IndexError):
                if versuch == 1:
                    print(f"  !! {fa['id']}: Judge lieferte kein JSON — übersprungen", flush=True)
        if raw is None:
            continue

        def entblinden(value: str) -> str:
            if value not in ("A", "B"):
                return "gleich"
            ist_a_links = not getauscht
            return (label_a if (value == "A") == ist_a_links else label_b)

        urteil = {k: entblinden(raw.get(k, "gleich"))
                  for k in ("aktualitaet", "quellentreue", "vollstaendigkeit", "klarheit", "gesamt")}
        # Die Begründung spricht verblindet von „A"/„B" — ohne die Zuordnung
        # je Frage liest sie sich im Report irreführend.
        zuordnung = (f"A={label_b}, B={label_a}" if getauscht else f"A={label_a}, B={label_b}")
        urteil.update({"id": fa["id"], "fokus": fa["fokus"], "zuordnung": zuordnung,
                       "begruendung": raw.get("begruendung", "")})
        urteile.append(urteil)
        zeilen.append(f"| {fa['id']} | {urteil['aktualitaet']} | {urteil['quellentreue']} | "
                      f"{urteil['vollstaendigkeit']} | {urteil['klarheit']} | **{urteil['gesamt']}** |")
        print(f"  · {fa['id']}: gesamt={urteil['gesamt']}", flush=True)

    def zaehle(krit: str) -> str:
        w = [u[krit] for u in urteile]
        return f"{label_b} {w.count(label_b)} · {label_a} {w.count(label_a)} · gleich {w.count('gleich')}"

    # Objektive Ergänzung zum LLM-Urteil: wie frisch ist die JÜNGSTE Quelle im
    # Kandidatenset? Deterministisch messbar und unabhängig davon, wie das
    # Antwortmodell im Einzelfall formuliert.
    frische = []
    for fa in a_data["cases"]:
        fb = b_by_id.get(fa["id"])
        if not fb:
            continue
        ja = max((q["datum"] or "" for q in fa["quellen"]), default="")
        jb = max((q["datum"] or "" for q in fb["quellen"]), default="")
        sieger = label_b if jb > ja else (label_a if ja > jb else "gleich")
        frische.append((fa["id"], ja, jb, sieger))

    report = [
        f"# Qualitäts-Vergleich: {label_a} vs. {label_b}",
        "",
        f"Blind-Judge: `{JUDGE_MODEL}`, Seiten je Frage per Frage-Hash vertauscht.",
        "",
        "| Frage | Aktualität | Quellentreue | Vollständigkeit | Klarheit | Gesamt |",
        "|---|---|---|---|---|---|",
        *zeilen,
        "",
        "## Bilanz je Kriterium",
        *[f"- **{k}**: {zaehle(k)}" for k in
          ("aktualitaet", "quellentreue", "vollstaendigkeit", "klarheit", "gesamt")],
        "",
        "## Jüngste Quelle im Kandidatenset (deterministisch)",
        f"| Frage | {label_a} | {label_b} | frischer |",
        "|---|---|---|---|",
        *[f"| {fid} | {ja or '—'} | {jb or '—'} | **{s}** |" for fid, ja, jb, s in frische],
        "",
        "## Begründungen (A/B = verblindete Seiten, Zuordnung je Frage)",
        *[f"- **{u['id']}** ({u['fokus']}, gesamt {u['gesamt']}; {u['zuordnung']}): {u['begruendung']}"
          for u in urteile],
        "",
    ]
    out = RESULTS / f"report-{label_a}-vs-{label_b}.md"
    out.write_text("\n".join(report), encoding="utf-8")
    (RESULTS / f"urteile-{label_a}-vs-{label_b}.json").write_text(
        json.dumps(urteile, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Report: {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Qualitatives Antwort-Eval (Vorher/Nachher + Blind-Judge)")
    ap.add_argument("--erzeugen", metavar="LABEL", help="Antworten des aktuellen Codes einfrieren")
    ap.add_argument("--judge", nargs=2, metavar=("LABEL_A", "LABEL_B"), help="zwei Stände blind vergleichen")
    ap.add_argument("--db", default=str(ROOT / "data" / "council.sqlite"))
    args = ap.parse_args()
    if args.erzeugen:
        erzeugen(args.erzeugen, Path(args.db))
    if args.judge:
        judge(args.judge[0], args.judge[1])
    if not args.erzeugen and not args.judge:
        ap.print_help()


if __name__ == "__main__":
    main()
