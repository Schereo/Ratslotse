"""Fachwörter aus der Vorlage: Was das geprüfte Glossar nicht kennt.

Tim, 13.11.2026: „können wir Fachbegriffe erkennen, die man nicht kennen
könnte und dann einfache Erklärungen vorschlagen?" Das Glossar
(``kern/glossar.py``) deckt, was oft vorkommt. Was nur in EINER Vorlage steht
— „Rotor-out-Planung", „nachrichtlich", „Komplementärin" — steht dort nie.

**Zwei Modelle, weil eines nicht reicht.** Gemessen an 20 Vorlagen (49
Begriffe): Das kleine Modell findet die richtigen Wörter, aber jede 25.
Erklärung ist falsch (4 %; „Einnahmen und Ausgaben" statt „Erträge und
Aufwendungen") und jeder neunte Begriff allgemein bekannt
(„Wasserschutzgebiet"). Deshalb schlägt das kleine vor, und ein größeres
lässt nur durch, was fachlich stimmt UND erklärungsbedürftig ist. Dazwischen
prüft Code, was sich ohne Modell prüfen lässt: Das Wort steht wörtlich in den
Lesetexten, das Zitat wörtlich in der Vorlage.

Gespeichert je Vorlage (``template_terms``), neu nur bei geänderter
Quellenlage. Kosten: rund 0,004 $ je Vorlage.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re

from kern import glossar, llm, prompts

_log = logging.getLogger(__name__)

MODEL = os.environ.get("COUNCIL_TERMS_MODEL", "openai/gpt-6-luna")
VERIFY_MODEL = os.environ.get("COUNCIL_TERMS_VERIFY_MODEL", "openai/gpt-6-sol")
PROMPT_VERSION = 1
MAX_BEGRIFFE = 3
SEITE_ZEICHEN = 6_000
VORLAGE_ZEICHEN = 9_000
ERKLAERUNG_ZEICHEN = 320

#: Fremde Dokumente: Stünde in einer Vorlage eine Anweisung, soll ihr Echo
#: nicht als Erklärung auf der Seite landen.
_VERDAECHTIG = re.compile(r"https?://|www\.|@|[<>{}\[\]`]|\b(ignorier|anweisung|prompt|system)", re.IGNORECASE)
_BUCHSTABE = r"[^\W\d_]"


def _norm(text: str | None) -> str:
    """Für den Zitat-Vergleich: Leerraum und Silbentrennung des PDFs egal."""
    return re.sub(r"\s+", " ", (text or "").replace("-\n", "")).replace("- ", "").lower()


def _steht_als_wort(begriff: str, text: str) -> bool:
    return re.search(rf"(?<!{_BUCHSTABE}){re.escape(begriff)}(?!{_BUCHSTABE})", text) is not None


def sources_hash(texte: list[str], vorlage_text: str) -> str:
    grundlage = [texte, vorlage_text[:VORLAGE_ZEICHEN], PROMPT_VERSION]
    return hashlib.sha256(json.dumps(grundlage, ensure_ascii=False).encode()).hexdigest()[:16]


def propose(titel: str, texte: list[str], vorlage_text: str, *, batch: bool = True) -> tuple[list[dict], float]:
    """Das kleine Modell schlägt bis zu drei Begriffe mit Erklärung vor."""
    from council.plan_judge import cost_usd  # noqa: PLC0415 — dieselbe Rechnung wie Pläne und Anträge

    seite = "\n".join(texte)[:SEITE_ZEICHEN]
    schon = [t["term"] for t in glossar.fuer_seite(texte, max_n=20)]
    nutzer = (f"TITEL: {titel}\n\nSCHON ERKLÄRT: {', '.join(schon) or '–'}\n\nLESETEXTE:\n{seite}\n\n"
              f"VORLAGE:\n{vorlage_text[:VORLAGE_ZEICHEN]}")
    extra = {"_geduld": True, "_ersatz": llm.ersatz_fuer(MODEL), "_tarif": "flex"} if batch else {}
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"}, max_tokens=2_500,
        messages=[{"role": "system", "content": prompts.get("template_terms_system")},
                  {"role": "user", "content": nutzer}],
        _feature="template_terms", **extra)
    try:
        roh = json.loads(resp.choices[0].message.content or "{}").get("terms")
    except json.JSONDecodeError:
        roh = None
    return [t for t in roh if isinstance(t, dict)] if isinstance(roh, list) else [], cost_usd(resp, MODEL) or 0.0


def pre_check(vorschlaege: list[dict], texte: list[str], vorlage_text: str) -> list[dict]:
    """Was sich ohne Modell prüfen lässt — und nur, was das besteht, geht zum
    Prüf-Modell: wörtlich auf der Seite, nicht schon im Glossar, Zitat wörtlich
    in der Vorlage, nichts Verdächtiges im Text."""
    seite = "\n".join(texte)
    vorlage = _norm(vorlage_text)
    bekannt = {b.lower() for b in glossar.BEGRIFFE}
    aus: list[dict] = []
    gesehen: set[str] = set()
    for v in vorschlaege:
        begriff = str(v.get("term") or "").strip()
        erklaerung = re.sub(r"\s+", " ", str(v.get("explanation") or "")).strip()
        if not (2 < len(begriff) <= 80) or not (20 <= len(erklaerung) <= ERKLAERUNG_ZEICHEN):
            continue
        if begriff.lower() in gesehen or begriff.lower() in bekannt or glossar.finde(begriff, max_n=1):
            continue
        if _VERDAECHTIG.search(erklaerung) or not _steht_als_wort(begriff, seite):
            continue
        zitat = re.sub(r"\s+", " ", str(v.get("quote") or "")).strip()[:300]
        basis = "template" if v.get("basis") == "vorlage" else "general"
        if basis == "template" and not (zitat and _norm(zitat) in vorlage):
            # Ein Beleg, den es nicht gibt, ist schlimmer als keiner.
            continue
        gesehen.add(begriff.lower())
        aus.append({"term": begriff, "explanation": erklaerung, "basis": basis,
                    "quote": zitat if basis == "template" else None})
        if len(aus) >= MAX_BEGRIFFE:
            break
    return aus


def _ausschnitt(begriff: str, seite: str) -> str:
    i = seite.find(begriff)
    return re.sub(r"\s+", " ", seite[max(0, i - 160): i + len(begriff) + 140]) if i >= 0 else ""


def verify(titel: str, begriffe: list[dict], texte: list[str], *, batch: bool = True) -> tuple[list[dict], float]:
    """Das größere Modell prüft jede Erklärung streng. Durch kommt nur, was
    fachlich stimmt („ja", nicht „teils") und erklärungsbedürftig ist. Ohne
    Urteil kein Begriff: Antwortet der Prüfer nicht, bleibt die Liste leer."""
    from council.plan_judge import cost_usd  # noqa: PLC0415

    if not begriffe:
        return [], 0.0
    seite = "\n".join(texte)
    nutzer = "\n\n".join(
        f"Fall {i}\nPunkt: {titel[:160]}\nAusschnitt: …{_ausschnitt(b['term'], seite)}…\nWort: {b['term']}\n"
        f"Erklärung: {b['explanation']}" + (f"\nStelle in der Vorlage: „{b['quote']}“" if b.get("quote") else "")
        for i, b in enumerate(begriffe, 1))
    # Kein Ersatzmodell: Ein Prüfer, der das Tor nicht hält, ist schlechter als keiner.
    extra = {"_geduld": True, "_tarif": "flex"} if batch else {}
    resp = llm.chat_complete(
        model=VERIFY_MODEL, response_format={"type": "json_object"}, max_tokens=2_500,
        messages=[{"role": "system", "content": prompts.get("template_terms_verify_system")},
                  {"role": "user", "content": nutzer}],
        _feature="template_terms_verify", **extra)
    try:
        urteile = json.loads(resp.choices[0].message.content or "{}").get("verdicts")
    except json.JSONDecodeError:
        urteile = None
    nach_nr = {u.get("nr"): u for u in urteile if isinstance(u, dict)} if isinstance(urteile, list) else {}
    durch = [b for i, b in enumerate(begriffe, 1)
             if (u := nach_nr.get(i)) and u.get("correct") == "yes" and u.get("needed") == "yes"]
    return durch, cost_usd(resp, VERIFY_MODEL) or 0.0


def build_for_template(store, template_number: str, *, batch: bool = True, force: bool = False,
                       stopp=None) -> dict | None:
    """Die Begriffe einer Vorlage — gespeichert, wenn die Quellenlage gleich
    blieb, sonst neu erzeugt und geprüft. ``None`` ohne Vorlagentext."""
    m = store.terms_material(template_number)
    if not m:
        return None
    h = sources_hash(m["texts"], m["template_text"])
    alt = store.template_terms(template_number)
    if alt and not force and alt["sources_hash"] == h and alt["prompt_version"] == PROMPT_VERSION \
            and alt["status"] == "ok":
        return alt
    kosten = 0.0
    try:
        vorschlaege, k = propose(m["title"], m["texts"], m["template_text"], batch=batch)
        kosten += k
        kandidaten = pre_check(vorschlaege, m["texts"], m["template_text"])
        geprueft, k = verify(m["title"], kandidaten, m["texts"], batch=batch)
        kosten += k
    except Exception:  # noqa: BLE001 — eine Vorlage kippt nicht den Lauf
        _log.exception("Begriffe für %s nicht erzeugt", template_number)
        if stopp is not None and kosten:
            stopp.ausgeben(kosten)
        store.save_template_terms(template_number, h, status="failed", payload=None, model=MODEL,
                                  verify_model=VERIFY_MODEL, cost_usd=kosten or None, prompt_version=PROMPT_VERSION)
        return None
    if stopp is not None:
        stopp.ausgeben(kosten)   # sonst deckelt die Kostengrenze den Lauf nicht
    payload = {"terms": geprueft, "proposed": len(vorschlaege), "checked": len(kandidaten)}
    store.save_template_terms(template_number, h, status="ok", payload=payload, model=MODEL,
                              verify_model=VERIFY_MODEL, cost_usd=kosten, prompt_version=PROMPT_VERSION)
    return store.template_terms(template_number)
