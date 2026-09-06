"""„Mein Viertel": Was ändert sich in einem Ortsbereich in den nächsten Jahren?

Der Register-Lauf hinter ``/api/districts/{id}/projects``. Drei Stufen:

1. **Kandidaten** aus der Orts-Pipeline (``store.district_candidates``): alle
   Beschlüsse der letzten 24 Monate, deren erkannte Orte zu mindestens der
   Hälfte im Ortsbereich liegen.
2. **Richter** (LLM, fünf Beschlüsse je Aufruf): Liegt der Gegenstand wirklich
   hier, ändert sich etwas Spürbares, was, wann, welcher Stand. Gecacht über
   einen Hash der Eingabe — ein Wochenlauf schickt nur Neues.
3. **Bündelung** (LLM, ein Aufruf je Ortsbereich): Alle Viertel-Treffer werden
   zu Vorhaben mit Stand. Ausschuss + Rat, Aufstellungs- + Satzungsbeschluss,
   Bericht + Antrag zum selben Gegenstand sind EINE Karte.

**Warum zwei LLM-Stufen und nicht die Orts-Pipeline allein.** Gemessen am
05.09.2026 (Kreyenbrück, Osternburg, Eversten, 163 Kandidaten): Die Hälfte
gehörte nicht ins Viertel — stadtweite Berichte mit Beispielort, das Klinikum,
Gedenktitel mit Straßennamen, lange Straßen. Nach Richter und Bündelung
blieben 31 Vorhaben, 30 davon im richtigen Viertel. Der eine Fehler war eine
Namensgleichheit (Schießstand in Eversten vs. Schießstand/Fliegerhorst); die
Namensvettern anderer Viertel gehen deshalb mit in den Prompt, und ein
Vorhaben mit Namensvetter ohne Vorlagenbeleg fällt unter die Schwelle.

Nichts hier meldet etwas — das Register ist Lesestoff für die Tafel. Wer
einmal Benachrichtigungen daraus baut, geht über ``notify.einreihen``.
"""
from __future__ import annotations

import hashlib
import json
import os

from council.impact import vorlagen_kern
from council.locations import affects_whole_city
from council.store_viertel import PROJECT_MIN_CONFIDENCE
from kern import llm, prompts

MODEL = os.environ.get("COUNCIL_DISTRICT_MODEL", "openai/gpt-5.6-luna")
#: Kurzes Nachdenken reicht (wie bei der Tragweite): identische Urteile bei
#: der Hälfte der Denk-Tokens.
REASONING = {"reasoning": {"effort": "low"}}
BATCH_SIZE = 5
#: Zeichen je Textquelle im Prompt — die Vorlage trägt den Termin, deshalb
#: bekommt sie den meisten Platz.
LIMITS = {"summary": 700, "official_text": 900, "template": 2600}

#: Werte, die das Modell liefern darf. Anderes wird verworfen, nicht geraten.
RELATIONS = ("district", "citywide", "elsewhere", "mentioned")
STAGES = ("idea", "planning", "decided", "building", "done", "rejected")
CATEGORIES = ("housing", "traffic", "school_childcare", "green", "culture_sport_social", "other")

#: Was ein Vorhaben mit Namensvetter höchstens an Sicherheit bekommt, wenn
#: kein Vorlagentext den Ort belegt — knapp unter der Tafel-Schwelle.
NAMESAKE_CAP = PROJECT_MIN_CONFIDENCE - 1

def source_hash(k: dict) -> str:
    """Hash der Eingabe eines Kandidaten — ändert sich, wenn Text oder Orte sich ändern."""
    teile = [str(k.get("title")), str(k.get("summary")), str(k.get("official_text"))[:LIMITS["official_text"]],
             str(k.get("template_text"))[:LIMITS["template"]],
             ",".join(sorted(loc["slug"] for loc in k.get("locations") or [])),
             ",".join(sorted(k.get("other_districts") or []))]
    return hashlib.sha256("\x1f".join(teile).encode("utf-8", "replace")).hexdigest()[:24]


def _candidate_text(k: dict) -> str:
    orte = []
    for loc in k["locations"]:
        s = (f"{loc['name']} ({loc['kind']}, Anteil im Viertel {loc['share']}, "
             f"erkannt aus {loc['source']}/{loc['method']})")
        orte.append(s)
    namesakes = ", ".join(f"{n['name']} in {n['district']}" for n in k.get("namesakes") or [])
    teile = [
        f"id {k['id']}: {k['title']}",
        f"  Sitzung: {k['date']} · {k['committee']} · Ergebnis: {k.get('outcome') or '?'} · Art: {k.get('kind')}",
        f"  Erkannte Orte: {'; '.join(orte)}",
        f"  Dieselben Orte berühren auch: {', '.join(k.get('other_districts') or []) or 'keine'}",
    ]
    if namesakes:
        teile.append(f"  Namensgleich anderswo: {namesakes}")
    if k.get("summary"):
        teile.append(f"  Kurzfassung: {k['summary'][:LIMITS['summary']]}")
    if k.get("official_text"):
        teile.append(f"  Beschlusstext: {k['official_text'][:LIMITS['official_text']]}")
    if k.get("proposed_decision"):
        teile.append(f"  Beschlussvorschlag: {k['proposed_decision']}")
    if k.get("financial_impact"):
        teile.append(f"  Finanzen: {k['financial_impact']}")
    if k.get("template_text"):
        teile.append(f"  Vorlage (Auszug): {vorlagen_kern(k['template_text'])[:LIMITS['template']]}")
    return "\n".join(teile)


def review_batch(place, batch: list[dict]) -> dict[int, dict]:
    """Ein Richter-Aufruf → ``{decision_id: urteil}``; halluzinierte IDs und
    unbekannte Werte fallen weg."""
    user = prompts.render("district_review_user", district=place.name,
                          batch="\n\n".join(_candidate_text(k) for k in batch))
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": prompts.render("district_review_system")},
                  {"role": "user", "content": user}],
        max_tokens=6000, temperature=0, extra_body=dict(REASONING),
        _feature="district_projects", _geduld=True, _ersatz=llm.ersatz_fuer(MODEL),
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    valid = {k["id"] for k in batch}
    out: dict[int, dict] = {}
    for r in data.get("reviews") or []:
        try:
            did = int(r.get("id"))
        except (TypeError, ValueError):
            continue
        if did not in valid or r.get("relation") not in RELATIONS:
            continue
        out[did] = {
            "decision_id": did,
            "relation": r["relation"],
            "changes": bool(r.get("changes")),
            "what": str(r.get("what") or "").strip(),
            "when": (str(r["when"]).strip() or None) if r.get("when") else None,
            "stage": r.get("stage") if r.get("stage") in STAGES else None,
            "category": r.get("category") if r.get("category") in CATEGORIES else "other",
            "confidence": max(0, min(100, int(r.get("confidence") or 0))),
            "reason": str(r.get("reason") or "").strip(),
        }
    return out


def _review_nachgefasst(place, batch: list[dict], tiefe: int = 0) -> dict[int, dict]:
    """Ein Batch, und bei Fehlern in Hälften nachgefasst (wie ``council.impact``).

    Gemessen am 06.09.2026: Ein Fünfer-Batch mit langen Vorlagentexten lief
    ins Token-Limit, die Antwort brach mitten im JSON ab — und mit ihr fielen
    vier gute Urteile weg. Halbieren rettet die, die nichts dafür konnten.
    """
    try:
        return review_batch(place, batch)
    except Exception as exc:  # noqa: BLE001 — ein Batch, nicht der Lauf
        if len(batch) <= 1 or tiefe >= 3:
            print(f"  ⚠️ Richter für {place.name} ({[k['id'] for k in batch]}) fehlgeschlagen: {exc!r}",
                  flush=True)
            return {}
        print(f"  ⚠️ Richter-Batch für {place.name} ({len(batch)}) fehlgeschlagen: {exc!r} — fasse in Hälften nach",
              flush=True)
        mitte = len(batch) // 2
        out = _review_nachgefasst(place, batch[:mitte], tiefe + 1)
        out.update(_review_nachgefasst(place, batch[mitte:], tiefe + 1))
        return out


def review_candidates(store, place, candidates: list[dict]) -> dict[int, dict]:
    """Alle Kandidaten beurteilen — aus dem Cache, wo die Eingabe unverändert ist."""
    cached = store.district_reviews(place.id)
    todo: list[dict] = []
    result: dict[int, dict] = {}
    for k in candidates:
        k["source_hash"] = source_hash(k)
        alt = cached.get(k["id"])
        if alt and alt.get("source_hash") == k["source_hash"]:
            result[k["id"]] = {**alt, "changes": bool(alt["changes"]), "when": alt.get("when_text")}
        else:
            todo.append(k)
    by_id = {k["id"]: k for k in candidates}
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        urteile = _review_nachgefasst(place, batch)
        rows = []
        for did, u in urteile.items():
            u["source_hash"] = by_id[did]["source_hash"]
            rows.append(u)
            result[did] = u
        if rows:
            store.save_district_reviews(place.id, rows, MODEL)
    return result


def _hits(candidates: list[dict], reviews: dict[int, dict]) -> list[dict]:
    """Die Viertel-Treffer: relation=district, nicht stadtweit per Regel, mit Urteil."""
    out = []
    for k in candidates:
        u = reviews.get(k["id"])
        if not u or u["relation"] != "district":
            continue
        if affects_whole_city(k.get("title")):
            continue
        out.append({**k, "review": u})
    return out


def _project_text(hits: list[dict]) -> str:
    zeilen = []
    for k in sorted(hits, key=lambda k: k["date"]):
        u = k["review"]
        zeilen.append(
            f"id {k['id']} · {k['date']} · {k['committee']} · Ergebnis {k.get('outcome') or '?'}\n"
            f"  Titel: {k['title']}\n"
            f"  Kurz: {u.get('what')} (Stand: {u.get('stage')}, wann: {u.get('when')})\n"
            f"  Zusammenfassung: {(k.get('summary') or '')[:400]}")
    return "\n\n".join(zeilen)


def bundle_projects(place, hits: list[dict]) -> list[dict]:
    """Ein Bündelungs-Aufruf je Ortsbereich → Vorhaben mit Beschluss-IDs."""
    if not hits:
        return []
    user = prompts.render("district_projects_user", district=place.name, count=len(hits),
                          batch=_project_text(hits))
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": prompts.render("district_projects_system")},
                  {"role": "user", "content": user}],
        max_tokens=4000, temperature=0, extra_body=dict(REASONING),
        _feature="district_projects", _geduld=True, _ersatz=llm.ersatz_fuer(MODEL),
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    by_id = {k["id"]: k for k in hits}
    out = []
    for p in data.get("projects") or []:
        ids = []
        for i in p.get("decision_ids") or []:
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if i in by_id and i not in ids:
                ids.append(i)
        if not ids or not p.get("name"):
            continue
        confidence = max(0, min(100, int(p.get("confidence") or 0)))
        # Namensvetter-Regel: Trägt einer der Beschlüsse einen Ortsnamen, den
        # es auch anderswo gibt, und belegt kein Vorlagentext den Ort, bleibt
        # das Vorhaben unter der Tafel-Schwelle.
        if any(by_id[i].get("namesakes") and not by_id[i].get("template_text") for i in ids):
            confidence = min(confidence, NAMESAKE_CAP)
        out.append({
            "name": str(p["name"]).strip()[:80],
            "what": str(p.get("what") or "").strip(),
            "stage": p.get("stage") if p.get("stage") in STAGES else "planning",
            "when": (str(p["when"]).strip() or None) if p.get("when") else None,
            "category": p.get("category") if p.get("category") in CATEGORIES else "other",
            "decision_ids": ids,
            "confidence": confidence,
        })
    return out


def build_place(store, place, *, dry_run: bool = False) -> dict:
    """Das Register eines Ortsbereichs neu rechnen. Gibt Kennzahlen zurück."""
    candidates = store.district_candidates(place)
    reviews = review_candidates(store, place, candidates) if candidates else {}
    hits = _hits(candidates, reviews)
    projects = bundle_projects(place, hits) if hits else []
    if not dry_run:
        store.replace_district_projects(place.id, projects)
    visible = sum(1 for p in projects if p["confidence"] >= PROJECT_MIN_CONFIDENCE)
    return {"place_id": place.id, "candidates": len(candidates), "reviewed": len(reviews),
            "hits": len(hits), "projects": len(projects), "visible": visible}


def build_all(store, place_ids: list[str] | None = None, *, dry_run: bool = False) -> list[dict]:
    """Alle 31 Ortsbereiche (oder die genannten), einer nach dem anderen.

    Ein Ortsbereich, der trotz Geduld scheitert, wird übersprungen und im
    Ergebnis als ``failed`` markiert — die übrigen 30 sollen nicht mit ihm
    sterben. Sein Register bleibt, wie es war (Urteile sind gecacht, der
    nächste Lauf holt nur die Bündelung nach).
    """
    out = []
    for place in store.all_places():
        if not place.is_primary:
            continue
        if place_ids and place.id not in place_ids:
            continue
        try:
            stats = build_place(store, place, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001 — ein Ortsbereich, nicht der Lauf
            print(f"  ⚠️ {place.name} übersprungen: {exc!r}", flush=True)
            out.append({"place_id": place.id, "candidates": 0, "reviewed": 0, "hits": 0,
                        "projects": 0, "visible": 0, "failed": True})
            continue
        print(f"  {place.name}: {stats['candidates']} Kandidaten → {stats['hits']} im Viertel → "
              f"{stats['projects']} Vorhaben ({stats['visible']} auf der Tafel)", flush=True)
        out.append(stats)
    return out
