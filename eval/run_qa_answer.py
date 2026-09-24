#!/usr/bin/env python3
"""KI-Frage: nur das ANTWORT-Modell, mit festem Kontext — lokal lauffähig.

**Warum es diese Suite gibt.** Die Suite ``ki-frage`` (``eval/run_qa.py``)
misst die ganze Kette: Analyse, Hybrid-Retrieval, Reranker, Antwort. Das
Retrieval braucht die Embeddings, und die fehlen im lokalen Abzug
(``scripts/lokale_daten.py`` lässt sie weg) — die Suite läuft deshalb nur auf
dem Server. Für die Frage „kann Modell X die Antwort schreiben?“ ist das
Retrieval aber gar nicht die Messgröße, sondern Rauschen: Zwei Modelle, die
verschiedene Kandidaten bekommen, vergleicht man nicht.

**Der Kontext ist deshalb fest**, und zwar ohne Modell und ohne Embeddings:
die erwarteten Beschlüsse des Falls (``expected_keys`` aus
``eval/cases_qa.json``, portabel über natürliche Schlüssel) plus die besten
BM25-Treffer der Volltextsuche zu den Fragewörtern als Ablenkung, zusammen
:data:`KONTEXT_N`, nach Sitzungsdatum absteigend. Jedes Modell bekommt
zeichengleich denselben Prompt (``qa._answer_messages``, wie der Endpunkt).

**Was geprüft wird**, buchstäblich und ohne Modell als Richter:

* ``zitiert_erwartet`` — die Antwort zitiert mindestens einen erwarteten
  Beschluss (``[id]``). Das ist die Kennzahl der Server-Suite, hier bei
  festem Kontext.
* ``erfundene_zahl`` (hart) — ein Betrag oder Prozentwert in der Antwort,
  der im Prompt nicht steht (dieselbe Prüfung wie bei Lotti,
  ``run_assistant.erfundene_zahlen``, gerundete Beträge zählen als belegt).
* ``erfundene_quelle`` (hart) — ein ``[id]``, das nicht im Kontext stand.
  ``resolve_citations`` wirft es im Betrieb still hinaus; die Antwort hat
  dann einen Satz ohne Beleg, und genau das soll hier sichtbar werden.

``qualitaet`` = mittlere **Abdeckung**: je Fall der Anteil der erwarteten
Beschlüsse im Kontext, die die Antwort zitiert — ein Fall mit hartem Befund
zählt 0. Die erste Fassung zählte nur „mindestens einer zitiert“ und stand
mit Gemini 2.5 Flash sofort bei 20/20 (23.09.2026): Eine gesättigte Suite
sagt „kein Rückschritt“, aber nie „besser“. Die Abdeckung trennt ein Modell,
das die Kette eines Vorgangs nachzeichnet, von einem, das den ersten Treffer
nennt und aufhört. „Mindestens einer“ steht als Nebenkennzahl daneben.

**Was sie NICHT misst:** ob das Retrieval die richtigen Beschlüsse findet,
und ob die Antwort mit der Server-Kette gleich gut ist. Für eine Umstellung
von ``COUNCIL_QA_MODEL`` ist sie der lokale Vorlauf; die Suite ``ki-frage``
auf dem Server bleibt die Abnahme.

Aufruf::

    python eval/run_qa_answer.py                     # heutiges COUNCIL_QA_MODEL
    python eval/run_qa_answer.py --modell google/gemini-3-flash-preview
    python eval/pruefstand.py --suite ki-frage-antwort --modell <id> --laeufe 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

from council import qa  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from eval import harness  # noqa: E402
from eval.run_assistant import erfundene_zahlen  # noqa: E402
from eval.run_qa import resolve_expected  # noqa: E402
from kern import llm  # noqa: E402

#: So viele Beschlüsse bekommt das Modell. Kleiner als ``QA_ANSWER_N`` (20)
#: im Endpunkt: Ohne Reranker sind die BM25-Ablenker schwächer als die echten,
#: und zwölf reichen, um das Modell zwischen Treffern wählen zu lassen.
KONTEXT_N = 12


def faelle() -> list[dict]:
    """Die portablen Einzelfragen aus ``cases_qa.json`` — ohne Chat-Ketten.

    Eine Anschlussfrage („Und wer ist dafür zuständig?“) braucht die Analyse,
    die den Rückbezug auflöst — also ein zweites Modell im Lauf. Das misst
    dann beide, und genau das soll diese Suite nicht.
    """
    return [c for c in harness.load_cases("cases_qa.json")
            if c.get("expected_keys") and c.get("question") and not c.get("verlauf")]


def kontext(store: CouncilStore, fall: dict, erwartet: list[int]) -> list[dict]:
    """Erwartete Beschlüsse plus BM25-Ablenker — deterministisch."""
    begriffe = " ".join(qa.extract_keywords(fall["question"]))
    ids = list(erwartet[:KONTEXT_N // 2])
    for did, _score, _snip in store.search_decisions_fts(begriffe, limit=KONTEXT_N * 2):
        if len(ids) >= KONTEXT_N:
            break
        if did not in ids:
            ids.append(did)
    rows = store.get_decisions_by_ids(ids)
    return sorted(rows, key=lambda d: (str(d.get("session_date") or ""), d["id"]), reverse=True)


def pruefen(text: str, prompt: str, zitiert: list[int], roh_ids: list[int],
            erwartet: set[int], kontext_ids: set[int]) -> dict:
    erfunden = erfundene_zahlen(text, prompt)
    fremd = sorted({i for i in roh_ids if i not in kontext_ids})
    return {
        "zitiert_erwartet": bool(set(zitiert) & erwartet),
        "abdeckung": round(len(set(zitiert) & erwartet & kontext_ids)
                           / max(1, len(erwartet & kontext_ids)), 4),
        "erfundene_zahlen": erfunden,
        "erfundene_quellen": fremd,
        "hart": bool(erfunden or fremd),
    }


def lauf(store: CouncilStore, model: str = qa.MODEL) -> dict:
    zeilen = []
    for fall in faelle():
        erwartet = resolve_expected(store.find_decision_ids, fall)
        if not erwartet:
            zeilen.append({"id": fall["id"], "uebersprungen": "nicht auflösbar"})
            continue
        ctx = kontext(store, fall, erwartet)
        typ = "history" if fall.get("typ") == "verlauf" else "topic"
        messages, extra = qa._answer_messages(fall["question"], ctx, typ, model)
        t0 = time.perf_counter()
        resp = llm.chat_complete(model=model, _feature="qa_answer", temperature=0.2,
                                 max_tokens=qa._answer_tokens(typ, False, False),
                                 messages=messages, **extra)
        ms = round((time.perf_counter() - t0) * 1000)
        roh = (resp.choices[0].message.content or "").strip()
        roh_ids = [v for m in qa._CITE_RE.finditer(roh) for v in qa.citation_ids(m.group(1))]
        text, zitiert = qa.resolve_citations(roh, {c["id"] for c in ctx})
        befund = pruefen(text, "\n".join(str(m["content"]) for m in messages),
                         zitiert, roh_ids, set(erwartet), {c["id"] for c in ctx})
        zeilen.append({"id": fall["id"], "ms": ms, "zitiert": zitiert,
                       "erwartet": erwartet, "text": text, **befund})
    gemessen = [z for z in zeilen if "ms" in z]
    gut = [z for z in gemessen if z["zitiert_erwartet"] and not z["hart"]]
    return {
        "faelle": zeilen,
        "cases": len(gemessen),
        "qualitaet": (round(sum(0 if z["hart"] else z["abdeckung"] for z in gemessen)
                            / len(gemessen), 4) if gemessen else None),
        "mindestens_einer": round(len(gut) / len(gemessen), 4) if gemessen else None,
        "hart": sum(1 for z in gemessen if z["hart"]),
        "zitiert_erwartet": sum(1 for z in gemessen if z["zitiert_erwartet"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modell", default=qa.MODEL)
    ap.add_argument("--db", help="Pfad zur council.sqlite (sonst COUNCIL_DB/.env)")
    args = ap.parse_args()
    store = CouncilStore(Path(args.db or os.environ.get("COUNCIL_DB")
                              or Path(__file__).parent.parent / "data" / "council.sqlite"))
    try:
        erg = lauf(store, args.modell)
    finally:
        store.close()
    for z in erg["faelle"]:
        if "uebersprungen" in z:
            print(f"  – {z['id']:32s} übersprungen: {z['uebersprungen']}")
            continue
        zeichen = "✓" if z["zitiert_erwartet"] and not z["hart"] else "✗"
        print(f"  {zeichen} {z['id']:32s} {z['ms']:5d} ms  zitiert {len(z['zitiert'])}"
              f"  Abdeckung {z['abdeckung']:.2f}"
              + (f"  Zahl erfunden: {z['erfundene_zahlen']}" if z["erfundene_zahlen"] else "")
              + (f"  Quelle erfunden: {z['erfundene_quellen']}" if z["erfundene_quellen"] else "")
              + ("" if z["zitiert_erwartet"] else "  kein erwarteter Beschluss zitiert"))
    print(json.dumps({k: v for k, v in erg.items() if k != "faelle"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
