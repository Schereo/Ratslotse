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
import os
import re
from datetime import date

from council.impact import vorlagen_kern
from council.locations import affects_whole_city
from council.store_viertel import PROJECT_MIN_CONFIDENCE
from council import modell_json
from kern import llm, prompts

#: Tims Entscheidung 23.09.2026 (P5, docs/plan-modellwechsel.md): GPT-6 Luna
#: ersetzt 5.6, im Flex-Tarif (kein Nutzereingabe-Feature). Prüfstand
#: 23.09.2026 (`viertel`, 30 Fälle × 2 Läufe): 5.6 95,0 % ± 3,3 (0,090–
#: 0,132 ct/Aufruf) — 6-Luna normal 93,3 % ± 0,0 (0,036–0,054 ct) — 6-Luna
#: flex 95,0 % ± 3,3 (0,017–0,028 ct). Beide im Rauschen, Flex zu einem
#: Fünftel bis Achtel des heutigen Preises.
MODEL = os.environ.get("COUNCIL_DISTRICT_MODEL", "openai/gpt-6-luna")
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



def _prompt_stand() -> str:
    """Fingerabdruck des Richter-Prompts. Ändert sich der Prompt, sind die
    gecachten Urteile nach der alten Regel gefällt — der Hash der Eingabe
    muss das wissen, sonst wirkt eine Regeländerung nur auf neue Beschlüsse."""
    return hashlib.sha256(prompts.render("district_review_system").encode("utf-8")).hexdigest()[:8]


def source_hash(k: dict) -> str:
    """Hash der Eingabe eines Kandidaten — ändert sich, wenn Text, Orte oder
    der Richter-Prompt sich ändern."""
    teile = [str(k.get("title")), str(k.get("summary")), str(k.get("official_text"))[:LIMITS["official_text"]],
             str(k.get("template_text"))[:LIMITS["template"]],
             ",".join(sorted(loc["slug"] for loc in k.get("locations") or [])),
             ",".join(sorted(k.get("other_districts") or [])), _prompt_stand()]
    return hashlib.sha256("\x1f".join(teile).encode("utf-8", "replace")).hexdigest()[:24]


def ortsregel(k: dict, place) -> str | None:
    """Ein Kandidat, der nach festen Regeln NICHT in dieses Viertel gehört —
    mit dem Grund; sonst ``None``. Er geht gar nicht erst an den Richter.

    1. **Der Bebauungsplan liegt woanders.** Nennt der Titel einen Plan mit
       Umring (``store._plan_shares``), entscheidet dessen Fläche: unter
       ``BPLAN_MIN_SHARE`` hier → nicht hier. Eine Straße am Rand des Plans,
       die ins Nachbarviertel reicht, zieht den Plan nicht mit.
    2. **Der Titel nennt einen anderen Ortsbereich als Standort** („Neue
       Grundschule auf dem Gelände des ehemaligen Fliegerhorstes"), dieses
       Viertel aber nicht, und kein Ort aus dem Titel liegt hier. Dass die
       Vorlage nebenbei Dietrichsfeld erwähnt, macht die Schule nicht zu
       einem Dietrichsfelder Vorhaben. Ein Ort AUS dem Titel, der hier
       liegt, hebt die Regel auf: „Sportpark Osternburg" liegt in Tweelbäke.
    """
    from council.store_viertel import ViertelMixin
    plan = k.get("plan")
    if plan and plan.get("shares"):
        anteil = plan["shares"].get(place.name, 0)
        if anteil < ViertelMixin.BPLAN_MIN_SHARE:
            wo = max(plan["shares"].items(), key=lambda kv: kv[1])[0]
            return f"{plan['label']} liegt in {wo}"
        return None
    genannt = k.get("title_districts") or []
    fremd = [d for d in genannt if d != place.name]
    if fremd and place.name not in genannt:
        aus_titel_hier = any(loc.get("source") == "title" and loc.get("kind") != "district"
                             for loc in k.get("locations") or [])
        if not aus_titel_hier:
            return f"Titel nennt {', '.join(fremd)}"
    return None


def _candidate_text(k: dict) -> str:
    orte = []
    for loc in k["locations"]:
        s = (f"{loc['name']} ({loc['kind']}, Anteil im Viertel {loc['share']}, "
             f"erkannt aus {loc['source']}/{loc['method']})")
        orte.append(s)
    namesakes = ", ".join(f"{n['name']} in {n['district']}" for n in k.get("namesakes") or [])
    plan = k.get("plan")
    teile = [
        f"id {k['id']}: {k['title']}",
        f"  Sitzung: {k['date']} · {k['committee']} · Ergebnis: {k.get('outcome') or '?'} · Art: {k.get('kind')}",
        f"  Erkannte Orte: {'; '.join(orte)}",
        f"  Dieselben Orte berühren auch: {', '.join(k.get('other_districts') or []) or 'keine'}",
    ]
    if namesakes:
        teile.append(f"  Namensgleich anderswo: {namesakes}")
    if plan and plan.get("shares"):
        flaeche = ", ".join(f"{n} {round(a * 100)} %" for n, a in
                            sorted(plan["shares"].items(), key=lambda kv: -kv[1]) if a >= 0.05)
        teile.append(f"  Geltungsbereich {plan['label']} (amtlicher Umring): {flaeche}")
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
        _tarif="flex",
    )
    data = modell_json.objekt(resp.choices[0].message.content)
    valid = {k["id"] for k in batch}
    out: dict[int, dict] = {}
    for r in modell_json.eintraege(data, "reviews"):
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
        if k.get("excluded"):
            continue
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
            f"  Kurz: {u.get('what')} (Stand: {u.get('stage')}, wann: {u.get('when')}, "
            f"Veränderung vor Ort: {'ja' if u.get('changes') else 'nein'})\n"
            f"  Zusammenfassung: {(k.get('summary') or '')[:400]}")
    return "\n\n".join(zeilen)


def bundle_projects(place, hits: list[dict], *, today: date | None = None) -> list[dict]:
    """Ein Bündelungs-Aufruf je Ortsbereich → Vorhaben mit Beschluss-IDs.

    Das heutige Datum geht mit: Das Modell schreibt „wird bis Januar 2026
    gebaut" sonst auch im Oktober 2026 in die Zukunftsform. Ob der Zeitraum
    vorbei ist, entscheidet trotzdem nicht das Modell, sondern
    ``council/viertel_zeitplan.py`` beim Lesen.
    """
    if not hits:
        return []
    heute = (today or date.today()).strftime("%d.%m.%Y")
    user = prompts.render("district_projects_user", district=place.name, count=len(hits),
                          batch=_project_text(hits), today=heute)
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": prompts.render("district_projects_system")},
                  {"role": "user", "content": user}],
        max_tokens=4000, temperature=0, extra_body=dict(REASONING),
        _feature="district_projects", _geduld=True, _ersatz=llm.ersatz_fuer(MODEL),
        _tarif="flex",
    )
    data = modell_json.objekt(resp.choices[0].message.content)
    by_id = {k["id"]: k for k in hits}
    out = []
    for p in modell_json.eintraege(data, "projects"):
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
        # Die Sicherheit eines Vorhabens ist die des sichersten Richter-
        # Spruchs über seine Beschlüsse — NICHT die, die die Bündelung angibt.
        # Der Richter sieht Orte, Anteile und Umringe und urteilt über die
        # Lage; die Bündelung sieht nur Texte. Bis 10/2026 zählte ihre Zahl,
        # und sie hob Vorhaben auf die Tafel, bei denen der Richter an jedem
        # Beschluss gezweifelt hatte („Schulwegsicherheit Hermann-Ehlers-
        # Schule" in Osternburg: 82, die Kampstraße stand nur als Vergleich;
        # „Kulturplattform Bloherfel.de": 82; B-Plan 858 in Bürgeresch: 78) —
        # und senkte im lokalen Neulauf ebenso grundlos sichere (Alte Fleiwa:
        # Richter 98, Bündelung 82; Lebensquartier Schützenweg: 99 gegen 76).
        confidence = max(int(by_id[i]["review"].get("confidence") or 0) for i in ids)
        # Namensvetter-Regel: Trägt einer der Beschlüsse einen Ortsnamen, den
        # es auch anderswo gibt, und belegt kein Vorlagentext den Ort, bleibt
        # das Vorhaben unter der Tafel-Schwelle.
        if any(by_id[i].get("namesakes") and not by_id[i].get("template_text") for i in ids):
            confidence = min(confidence, NAMESAKE_CAP)
        stage = p.get("stage") if p.get("stage") in STAGES else "planning"
        # Ein Vorhaben braucht einen Beschluss, mit dem sich vor Ort etwas
        # ändert. Ein Bericht über eine Plattform, eine Vorstellung allein
        # sind keins („Kulturplattform Bloherfel.de", 03.10.2026). Abgelehnte
        # und fertige Vorhaben sind die Ausnahme: Ein Ablehnungs- oder
        # Abrechnungsbeschluss ändert per Definition nichts mehr, und trotzdem
        # will man wissen, dass die Sportbox nicht kommt oder die Kreuzung
        # fertig ist.
        if stage not in ("rejected", "done") and not any(by_id[i]["review"].get("changes") for i in ids):
            confidence = min(confidence, NAMESAKE_CAP)
        out.append({
            "name": str(p["name"]).strip()[:80],
            "what": str(p.get("what") or "").strip(),
            "stage": stage,
            "when": (str(p["when"]).strip() or None) if p.get("when") else None,
            "category": p.get("category") if p.get("category") in CATEGORIES else "other",
            "decision_ids": ids,
            "confidence": confidence,
        })
    return out


def _titel_kurz(titel: str) -> str:
    """Ein Beschlusstitel als Vorhaben-Name: ohne Antragsklammer, ohne
    Verfahrensschwanz („- Bericht", „- Aufstellungsbeschluss")."""
    t = re.sub(r"\s*\((?:[^()]*(?:Fraktion|Gruppe|Mitglied|vom\s+\d)[^()]*)\)", "", titel or "")
    t = re.split(r"\s+[-–]\s+", t)[0].strip()
    return t[:80] if len(t) <= 80 else t[:79].rstrip() + "…"


def verwaiste_vorhaben(hits: list[dict], projects: list[dict]) -> list[dict]:
    """Sichere Viertel-Treffer, die die Bündelung in KEIN Vorhaben gesteckt
    hat — je Vorlage ein eigenes Vorhaben aus dem Richter-Urteil.

    Die Bündelung ließ bei gleicher Eingabe von Lauf zu Lauf einzelne
    Beschlüsse einfach liegen: Im lokalen Neulauf am 03.10.2026 fehlten
    „Spielplatz auf dem Schlossplatz" (Richter 99), „Sanierung des
    Fliegerhorsts" (94) und „Dreifeldhalle Maastrichter Straße" (99), die im
    Lauf davor dastanden. Ein Beschluss, bei dem der Richter sicher ist, dass
    er hierher gehört und vor Ort etwas ändert, darf nicht am Zufall der
    Bündelung hängen. Name aus dem Titel, Satz, Stand, Termin aus dem Urteil.
    """
    gebuendelt = {i for p in projects for i in p.get("decision_ids") or []}
    je_vorlage: dict[object, list[dict]] = {}
    for k in hits:
        u = k["review"]
        if k["id"] in gebuendelt or not u.get("changes") or int(u.get("confidence") or 0) < PROJECT_MIN_CONFIDENCE:
            continue
        je_vorlage.setdefault(k.get("kvonr") or f"id:{k['id']}", []).append(k)
    out = []
    for gruppe in je_vorlage.values():
        gruppe.sort(key=lambda k: k["date"])
        juengst = gruppe[-1]
        u = juengst["review"]
        out.append({
            "name": _titel_kurz(juengst["title"]),
            "what": str(u.get("what") or "").strip(),
            "stage": u.get("stage") if u.get("stage") in STAGES else "planning",
            "when": u.get("when"),
            "category": u.get("category") if u.get("category") in CATEGORIES else "other",
            "decision_ids": [k["id"] for k in gruppe],
            "confidence": max(int(k["review"].get("confidence") or 0) for k in gruppe),
        })
    return out


def build_place(store, place, *, dry_run: bool = False) -> dict:
    """Das Register eines Ortsbereichs neu rechnen. Gibt Kennzahlen zurück."""
    candidates = store.district_candidates(place)
    for k in candidates:
        grund = ortsregel(k, place)
        if grund:
            k["excluded"] = grund
    offen = [k for k in candidates if not k.get("excluded")]
    reviews = review_candidates(store, place, offen) if offen else {}
    hits = _hits(offen, reviews)
    projects = bundle_projects(place, hits) if hits else []
    waisen = verwaiste_vorhaben(hits, projects)
    projects += waisen
    if not dry_run:
        store.replace_district_projects(place.id, projects)
    visible = sum(1 for p in projects if p["confidence"] >= PROJECT_MIN_CONFIDENCE)
    return {"place_id": place.id, "candidates": len(candidates), "excluded": len(candidates) - len(offen),
            "reviewed": len(reviews), "hits": len(hits), "projects": len(projects), "visible": visible,
            "orphans": len(waisen)}


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
            out.append({"place_id": place.id, "candidates": 0, "excluded": 0, "reviewed": 0, "hits": 0,
                        "projects": 0, "visible": 0, "failed": True,
                        "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        print(f"  {place.name}: {stats['candidates']} Kandidaten ({stats['excluded']} per Regel raus) → "
              f"{stats['hits']} im Viertel → "
              f"{stats['projects']} Vorhaben ({stats['visible']} auf der Tafel)", flush=True)
        out.append(stats)
    return out
