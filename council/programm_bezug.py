"""Was die Wahlprogramme zu einem Tagesordnungspunkt sagen.

Tim, 13.11.2026: Aussagen dazu, wie eine Partei „basierend auf dem
Wahlprogramm" zu einem Punkt steht — „dann würde man Stellen aus dem
Wahlprogramm zitieren, die man dann den Ratsmitgliedern vorlegen kann".

**Was die Seite zeigt — und was nicht.** Je Liste im Rat höchstens eine
Einordnung: Das Programm spricht für oder gegen das Anliegen des Punkts, mit
der wörtlichen Stelle und Seitenzahl. Keine Wahrscheinlichkeit und keine
Vorhersage einer Abstimmung: Die ließe sich nicht belegen, das Zitat schon.
Schweigt ein Programm, steht die Liste unter „keine Aussage".

**Vier Stufen, weil ein Zitat einer Partei ein Urteil über sie ist.**

1. *Suchen* ohne Modell: je Liste die Abschnitte, die dem Punkt am nächsten
   sind (Einbettungen), plus solche, die ein markantes Wort des Titels
   wörtlich tragen („Zweckentfremdung", „Grundsteuer C").
2. *Einordnen* (kleines Modell): dafür / dagegen / keine Aussage, je mit
   wörtlicher Stelle.
3. *Prüfen im Code*: Das Zitat steht wörtlich im Programm DIESER Liste — die
   Seitenzahl kommt aus der Fundstelle, nicht vom Modell.
4. *Prüfen mit dem größeren Modell*: Trägt die Stelle die Einordnung, und
   meint sie dieselbe Maßnahme? Gemessen an zwölf Punkten (13.11.2026):
   Zur Zweckentfremdungssatzung fand Stufe 2 vier klare Stellen (FDP
   ausdrücklich dagegen) — zu „Preiswerte Wohnungen" aber bei acht von neun
   Listen ein „dafür", weil jedes Programm günstigen Wohnraum will. Ein
   allgemeines Ziel ist keine Aussage zu einem Antrag; das siebt Stufe 4 aus.
   Durch kommt, was die Maßnahme selbst nennt (``measure``) oder einen
   ausdrücklichen Grundsatz, unter den der Punkt unmittelbar fällt
   (``principle``: „keine neuen Steuern" gegen die Grundsteuer C).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re

from council import wahlprogramme
from kern import llm, prompts

_log = logging.getLogger(__name__)

MODEL = os.environ.get("COUNCIL_PROGRAM_MODEL", "openai/gpt-6-luna")
VERIFY_MODEL = os.environ.get("COUNCIL_PROGRAM_VERIFY_MODEL", "openai/gpt-6-sol")
PROMPT_VERSION = 1
#: Abschnitte je Liste im Prompt: nächste Nachbarn plus wörtliche Treffer.
NAECHSTE = 4
WOERTLICHE = 2
WORUM_ZEICHEN = 1_400
ZITAT_ZEICHEN = 320
_VERDAECHTIG = re.compile(r"https?://|www\.|[<>{}\[\]`]|\b(ignorier|anweisung|prompt|system)", re.IGNORECASE)
_ANHANG = re.compile(r"\s+[-–—]\s+(?:Beschluss|Bericht|mündlicher Bericht|Beschlussantrag|Berichtsantrag|Antrag)\b.*$",
                     re.IGNORECASE)
#: Wörter, die in Ratstiteln überall stehen und keine Fundstelle wert sind.
_BLASS = {"oldenburg", "oldenburger", "beschluss", "bericht", "verwaltung", "fraktion", "satzung", "änderung",
          "bebauungsplan", "bebauungsplanes", "flächennutzungsplanes", "ausschuss", "sitzung", "vorlage",
          "beschlussantrag", "berichtsantrag", "städtischen", "städtische", "einführung", "umsetzung", "konzept"}


def worum(title: str, texts: list[str]) -> str:
    """Titel ohne Anhängsel plus der Anfang der Lesetexte."""
    kern = _ANHANG.sub("", title or "").strip()
    return f"{kern}. {' '.join(texts)}"[:WORUM_ZEICHEN]


def stichwoerter(title: str) -> list[str]:
    """Markante Wörter des Titels (lang, nicht blass) — für wörtliche Treffer."""
    kern = re.sub(r"\([^)]*\)", " ", _ANHANG.sub("", title or ""))
    aus = []
    for w in re.findall(r"[^\W\d_]{9,}", kern):
        if w.lower() not in _BLASS and w.lower() not in (a.lower() for a in aus):
            aus.append(w)
    return aus[:4]


def candidates(store, title: str, texts: list[str]) -> dict[str, list[dict]]:
    """Je Liste die Abschnitte, die zum Punkt gehören könnten."""
    import numpy as np  # noqa: PLC0415 — nur im Stapellauf, nie im Web-Dienst

    from council import embeddings  # noqa: PLC0415

    anfrage = embeddings.embed([worum(title, texts)])[0]
    woerter = [w.lower() for w in stichwoerter(title)]
    aus: dict[str, list[dict]] = {}
    for liste in wahlprogramme.lists():
        slug = liste["slug"]
        abschnitte = wahlprogramme.passages(slug)
        if not abschnitte:
            continue
        vektoren = store.program_vectors(slug, wahlprogramme.text_hash(slug))
        if vektoren is None or len(vektoren) != len(abschnitte):
            vektoren = embeddings.embed([a["text"] for a in abschnitte])
            store.save_program_vectors(slug, wahlprogramme.text_hash(slug), vektoren)
        naehe = vektoren @ anfrage
        gewaehlt = [int(i) for i in np.argsort(-naehe)[:NAECHSTE]]
        if woerter:
            woertlich = [a["idx"] for a in abschnitte
                         if a["idx"] not in gewaehlt and any(w in a["text"].lower() for w in woerter)]
            woertlich.sort(key=lambda i: -float(naehe[i]))
            gewaehlt += woertlich[:WOERTLICHE]
        aus[slug] = [abschnitte[i] for i in sorted(gewaehlt)]
    return aus


def sources_hash(title: str, texts: list[str]) -> str:
    grundlage = [worum(title, texts), [wahlprogramme.text_hash(liste["slug"]) for liste in wahlprogramme.lists()],
                 PROMPT_VERSION]
    return hashlib.sha256(json.dumps(grundlage, ensure_ascii=False).encode()).hexdigest()[:16]


def propose(title: str, texts: list[str], kandidaten: dict[str, list[dict]], *,
            batch: bool = True) -> tuple[str, list[dict], float]:
    """Das kleine Modell nennt das Anliegen des Punkts und ordnet je Liste ein."""
    from council.plan_judge import cost_usd  # noqa: PLC0415

    namen = {liste["slug"]: liste["label"] for liste in wahlprogramme.lists()}
    bloecke = []
    for slug, abschnitte in kandidaten.items():
        zeilen = "\n".join(f"[Seite {a['page']}] {a['text']}" if a["page"] else a["text"] for a in abschnitte)
        bloecke.append(f"### {slug} ({namen[slug]})\n{zeilen}")
    nutzer = f"PUNKT: {worum(title, texts)}\n\nWAHLPROGRAMME:\n\n" + "\n\n".join(bloecke)
    extra = {"_geduld": True, "_ersatz": llm.ersatz_fuer(MODEL), "_tarif": "flex"} if batch else {}
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"}, max_tokens=3_500,
        messages=[{"role": "system", "content": prompts.get("program_stance_system")},
                  {"role": "user", "content": nutzer}],
        _feature="program_stance", **extra)
    try:
        antwort = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        antwort = {}
    roh = antwort.get("parties") if isinstance(antwort, dict) else None
    anliegen = re.sub(r"\s+", " ", str(antwort.get("concern") or "")).strip()[:240] if isinstance(antwort, dict) else ""
    # Ohne Anliegen (reiner Bericht) keine Einordnung: „dafür" hätte keine Richtung.
    parteien = [p for p in roh if isinstance(p, dict)] if isinstance(roh, list) and anliegen else []
    return anliegen, parteien, cost_usd(resp, MODEL) or 0.0


def vereinige(erste: list[dict], zweite: list[dict]) -> list[dict]:
    """Die Vorschläge zweier Durchgänge. Je Liste bleiben bis zu drei
    verschiedene Zitate als Alternativen stehen — der Prüfer nimmt es genau:
    „lehnen jede Form von Enteignung durch eine Zweckentfremdungssatzung ab"
    ließ er nicht als Ablehnung der Satzung gelten, „Ablehnung von
    Enteignungen und einer Zweckentfremdungssatzung" eine Seite weiter schon.
    Widersprechen sich die Durchgänge in der Richtung, fällt die Liste weg."""
    je: dict[str, list[dict]] = {}
    for v in [*erste, *zweite]:
        if v.get("stance") in ("for", "against") and v.get("party"):
            je.setdefault(str(v["party"]), []).append(v)
    aus: list[dict] = []
    for vs in je.values():
        if len({v["stance"] for v in vs}) != 1:
            continue
        zitate: set[str] = set()
        for v in vs:
            schluessel = wahlprogramme.norm(str(v.get("quote") or ""))
            if schluessel and schluessel not in zitate and len(zitate) < 3:
                zitate.add(schluessel)
                aus.append(v)
    return aus


def pre_check(vorschlaege: list[dict]) -> list[dict]:
    """Nur Einordnungen mit einem Zitat, das wörtlich im Programm DIESER Liste
    steht. Seite und Umgebung kommen aus der Fundstelle. Je Liste dürfen
    mehrere Zitate als Alternativen stehen (s. ``vereinige``)."""
    gueltig = {liste["slug"] for liste in wahlprogramme.lists()}
    aus: list[dict] = []
    gesehen: set[tuple[str, str]] = set()
    for v in vorschlaege:
        slug = str(v.get("party") or "").strip()
        if slug not in gueltig or v.get("stance") not in ("for", "against"):
            continue
        zitat = re.sub(r"\s+", " ", str(v.get("quote") or "")).strip()[:ZITAT_ZEICHEN]
        grund = re.sub(r"\s+", " ", str(v.get("reason") or "")).strip()[:260]
        fund = wahlprogramme.find_quote(slug, zitat)
        if not fund or not grund or _VERDAECHTIG.search(grund) or (slug, wahlprogramme.norm(zitat)) in gesehen:
            continue
        gesehen.add((slug, wahlprogramme.norm(zitat)))
        aus.append({"party": slug, "stance": v["stance"], "quote": zitat, "page": fund["page"],
                    "reason": grund, "basis": "principle" if v.get("basis") == "principle" else "measure",
                    "_passage": fund["text"]})
    return aus


def verify(title: str, texts: list[str], anliegen: str, einordnungen: list[dict], *,
           batch: bool = True) -> tuple[list[dict], float]:
    """Das größere Modell bestätigt jede Einordnung — oder sie fällt weg. Ohne
    Urteil keine Aussage über eine Partei."""
    from council.plan_judge import cost_usd  # noqa: PLC0415

    if not einordnungen:
        return [], 0.0
    namen = {liste["slug"]: liste["label"] for liste in wahlprogramme.lists()}
    wort = {"for": "spricht dafür", "against": "spricht dagegen"}
    nutzer = f"PUNKT: {worum(title, texts)}\n\nANLIEGEN DES PUNKTS: {anliegen}\n\n" + "\n\n".join(
        f"Fall {i}\nListe: {namen[e['party']]}\nEinordnung: Das Programm {wort[e['stance']]}.\n"
        f"Zitat: „{e['quote']}“\nUmgebung im Programm: {e['_passage']}\nBegründung: {e['reason']}"
        for i, e in enumerate(einordnungen, 1))
    extra = {"_geduld": True, "_tarif": "flex"} if batch else {}   # kein Ersatzmodell für den Prüfer
    resp = llm.chat_complete(
        model=VERIFY_MODEL, response_format={"type": "json_object"}, max_tokens=2_500,
        messages=[{"role": "system", "content": prompts.get("program_stance_verify_system")},
                  {"role": "user", "content": nutzer}],
        _feature="program_stance_verify", **extra)
    try:
        urteile = json.loads(resp.choices[0].message.content or "{}").get("verdicts")
    except json.JSONDecodeError:
        urteile = None
    nach_nr = {u.get("nr"): u for u in urteile if isinstance(u, dict)} if isinstance(urteile, list) else {}
    durch = []
    bestaetigt: set[str] = set()
    for i, e in enumerate(einordnungen, 1):
        u = nach_nr.get(i) or {}
        if u.get("supported") != "yes" or u.get("specific") not in ("measure", "principle") or e["party"] in bestaetigt:
            continue
        bestaetigt.add(e["party"])   # je Liste das erste Zitat, das der Prüfer gelten lässt
        # Worauf die Einordnung fußt, sagt der Prüfer — nicht der Vorschlag.
        durch.append({**{k: v for k, v in e.items() if not k.startswith("_")}, "basis": u["specific"]})
    return durch, cost_usd(resp, VERIFY_MODEL) or 0.0


def build_for_template(store, template_number: str, *, batch: bool = True, force: bool = False,
                       stopp=None) -> dict | None:
    """Die Einordnungen zu einer Vorlage — gespeichert, solange Punkt und
    Programme gleich bleiben. ``None`` ohne Vorlagentext."""
    m = store.terms_material(template_number)
    if not m:
        return None
    h = sources_hash(m["title"], m["texts"])
    alt = store.program_stances(template_number)
    if alt and not force and alt["sources_hash"] == h and alt["prompt_version"] == PROMPT_VERSION \
            and alt["status"] == "ok":
        return alt
    kosten = 0.0
    try:
        kandidaten = candidates(store, m["title"], m["texts"])
        # Zwei Durchgänge, vereinigt: Das kleine Modell übersieht in einem
        # Durchgang gelegentlich eine klare Stelle (gemessen: die Ablehnung der
        # Zweckentfremdungssatzung im FDP-Programm fehlte in einem von vier).
        # Widersprechen sich die Durchgänge in der Richtung, fällt die Liste weg.
        anliegen, vorschlaege, k = propose(m["title"], m["texts"], kandidaten, batch=batch)
        kosten += k
        if anliegen:
            _, zweite, k = propose(m["title"], m["texts"], kandidaten, batch=batch)
            kosten += k
            vorschlaege = vereinige(vorschlaege, zweite)
        geprueft = pre_check(vorschlaege)
        bestaetigt, k = verify(m["title"], m["texts"], anliegen, geprueft, batch=batch)
        kosten += k
    except Exception:  # noqa: BLE001 — eine Vorlage kippt nicht den Lauf
        _log.exception("Programm-Bezug für %s nicht erzeugt", template_number)
        if stopp is not None and kosten:
            stopp.ausgeben(kosten)
        store.save_program_stances(template_number, h, status="failed", payload=None, model=MODEL,
                                   verify_model=VERIFY_MODEL, cost_usd=kosten or None, prompt_version=PROMPT_VERSION)
        return None
    if stopp is not None:
        stopp.ausgeben(kosten)   # sonst deckelt die Kostengrenze den Lauf nicht
    payload = {"concern": anliegen or None, "stances": bestaetigt,
               "proposed": sum(1 for v in vorschlaege if v.get("stance") in ("for", "against")), "checked": len(geprueft)}
    store.save_program_stances(template_number, h, status="ok", payload=payload, model=MODEL,
                               verify_model=VERIFY_MODEL, cost_usd=kosten, prompt_version=PROMPT_VERSION)
    return store.program_stances(template_number)


def item_view(payload: dict | None) -> dict | None:
    """Die Form der Punkt-Seite: Einordnungen in der Reihenfolge der Sitze, mit
    Namen und Quelle des Programms; dazu die Listen ohne Aussage. ``None``,
    wenn kein Programm etwas sagt — dann zeigt die Seite die Karte nicht."""
    stances = {s["party"]: s for s in (payload or {}).get("stances") or []}
    if not stances:
        return None
    parties, silent = [], []
    for liste in wahlprogramme.lists():
        s = stances.get(liste["slug"])
        if not s:
            silent.append(liste["label"])
            continue
        parties.append({"slug": liste["slug"], "label": liste["label"], "seats": liste["seats"],
                        "stance": s["stance"], "basis": s.get("basis") or "measure", "quote": s["quote"],
                        "page": s.get("page"), "reason": s["reason"],
                        "program_title": liste["title"], "program_url": liste["url"]})
    return {"concern": (payload or {}).get("concern"), "parties": parties, "silent": silent}
