"""Änderungsanträge lesen: was ein Antrag an welcher Stelle will, alt gegen
neu, mit Belegen (docs/plan-vorlagen-aufbereiten.md, § 5, PR 9).

Tims Wunsch (12.11.2026): „bei Änderungsanträgen wäre es super, wenn man die
Änderungen zusammenfassen könnte und ohne die Unterlagen öffnen zu müssen zu
sehen."

Ein Modellaufruf je Antrag (``motion_extract``), sobald er eintrifft. Die Basis
löst der Code auf, wo er kann:

- **§-Anker:** Nennt der Antrag „§ 24 Absatz 2" und liegt das Regelwerk am
  Punkt, holt der Code den geltenden Wortlaut selbst — ``before`` ist dann
  kein Modelltext, und der Wortdiff zeigt die Änderung Wort für Wort
  („zwei Tage" → „eine Woche").
- **Beschlussvorschlag:** Ersetzt der Antrag ihn, steht er als Quelle ``V1``
  daneben.
- **Fassung:** Nennt der Antrag eine andere Vorlagennummer als die des Punkts,
  ist sie die Basis; das steht im Ergebnis (``base_template``).

Alles, was das Modell als Aussage liefert, geht durch ``council/evidence.py``.
Was nicht wörtlich belegt ist, fällt weg — lieber ein leeres Feld als ein
falsches alt/neu-Paar.
"""
from __future__ import annotations

import difflib
import json
import logging
import os
import re

from council import evidence, kontaktdaten
from council.parties import parties_in_text
from kern import llm, prompts

_log = logging.getLogger(__name__)

MODEL = os.environ.get("COUNCIL_MOTIONS_MODEL", "openai/gpt-6-luna")
#: Steigt, wenn sich Prompt oder Prüfung so ändern, dass alte Auszüge neu gehören.
PROMPT_VERSION = 1
FEATURE = "motion_extract"
ANTRAG_ZEICHEN = 12_000
BASIS_ZEICHEN = 6_000
PATTERNS = ("replace", "delete", "add", "rewrite", "counter")
#: Alt und neu zeigen Wortlaut, und ein Absatz ist länger als ein Belegzitat.
WORTLAUT_MAX = 900


# ---- Basis auflösen (ohne Modell) --------------------------------------------

_PARAGRAF_RE = re.compile(r"§\s*(\d+[a-z]?)\s*(?:Abs(?:atz|\.)?\s*\(?(\d+)\)?|\((\d+)\))?", re.I)


def paragraph_refs(text: str) -> list[tuple[str, str | None]]:
    """„§ 24 Absatz 2", „§ 18 (4)", „§ 18 Abs. 4" → [("24", "2"), ("18", "4")], in Reihenfolge, ohne Dubletten."""
    out: list[tuple[str, str | None]] = []
    for m in _PARAGRAF_RE.finditer(text or ""):
        ref = (m.group(1), m.group(2) or m.group(3))
        if ref not in out:
            out.append(ref)
    return out


def paragraph_text(statute: str, section: str, paragraph: str | None) -> str | None:
    """Der Wortlaut von § ``section`` (Abs. ``paragraph``) in einem Regelwerk.

    Das Inhaltsverzeichnis führt dieselben Überschriften — genommen wird die
    Stelle, auf die ein „(1)" folgt."""
    t = statute or ""
    kopf = None
    for m in re.finditer(rf"^[^\S\n]*§[^\S\n]*{re.escape(section)}[^\S\n]*$", t, re.M):
        if re.search(r"^\s*\(1\)", t[m.end():m.end() + 400], re.M):
            kopf = m
    if not kopf:
        return None
    ende = re.search(r"^[^\S\n]*§[^\S\n]*\d+[a-z]?[^\S\n]*$", t[kopf.end():], re.M)
    abschnitt = t[kopf.end(): kopf.end() + ende.start()] if ende else t[kopf.end():]
    if not paragraph:
        return evidence.squash(abschnitt) or None
    m = re.search(rf"^[^\S\n]*\({re.escape(paragraph)}\)[^\S\n]*\n?", abschnitt, re.M)
    if not m:
        return None
    rest = abschnitt[m.end():]
    weiter = re.search(r"^[^\S\n]*\(\d+\)[^\S\n]*$", rest, re.M)
    return evidence.squash(rest[: weiter.start()] if weiter else rest) or None


_VORLAGE_NR_RE = re.compile(r"\b(\d{2}/\d{4}(?:/\d+)?)\b")


def base_reference(motion_text: str, item_template: str | None) -> str | None:
    """Eine andere Vorlagennummer als die des Punkts, auf die der Antrag sich bezieht."""
    eigene = "/".join((item_template or "").split("/")[:2])
    for m in _VORLAGE_NR_RE.finditer(motion_text[:4000]):
        nr = m.group(1)
        if nr != item_template and not (nr == eigene and not item_template):
            if nr.startswith(eigene + "/") or nr == eigene:
                if nr != item_template:
                    return nr
            elif item_template:
                return nr
    return None


def word_diff(before: str, after: str) -> list[list[str]]:
    """Wortdiff ohne Modell: [["=", "Die Ladungsfrist beträgt"], ["-", "zwei Tage."], ["+", "eine Woche."], …]."""
    a, b = before.split(), after.split()
    out: list[list[str]] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(["=", " ".join(a[i1:i2])])
        if op in ("replace", "delete"):
            out.append(["-", " ".join(a[i1:i2])])
        if op in ("replace", "insert"):
            out.append(["+", " ".join(b[j1:j2])])
    return out


def neufassung(motion_text: str, quote: str) -> str | None:
    """Der ganze neue Wortlaut, beginnend beim Zitat bis zur Begründung —
    ``None``, wenn das Zitat nicht wörtlich im Antrag steht."""
    flach = motion_text or ""
    anfang = evidence.squash(quote)[:40]
    i = evidence.squash(flach).find(anfang)
    if i < 0:
        return None
    rest = evidence.squash(flach)[i:]
    m = re.search(r"\s(?:Begründung|Mit freundlichen Grüßen|Sachverhalt)\b", rest)
    return (rest[: m.start()] if m else rest[:2000]).strip() or None


def clean_motion_text(text: str) -> str:
    """Briefkopf in gesperrter Schrift zusammenziehen, Kontaktdaten maskieren."""
    return kontaktdaten.maskieren(evidence.zusammenziehen(text or ""))


# ---- Modellaufruf und Prüfung --------------------------------------------------

def build_input(motion: dict, template: dict | None, statutes: list[dict]) -> tuple[str, dict[str, dict], dict]:
    """Nutzertext für den Aufruf, die Quellen für die Prüfung, die vom Code
    aufgelöste Basis (``anchor``)."""
    antrag = clean_motion_text(motion["text"])[:ANTRAG_ZEICHEN]
    quellen: dict[str, dict] = {"A1": {"text": antrag, "pages": motion.get("pages"), "document_id": motion.get("document_id")}}
    teile = [f"[A1] Antrag „{motion.get('label') or 'Antrag'}“:\n{antrag}"]
    if template and (template.get("proposed_decision") or template.get("raw_text")):
        vorschlag = template.get("proposed_decision") or ""
        quellen["V1"] = {"text": template.get("raw_text") or vorschlag, "pages": template.get("pages"),
                         "document_id": template.get("document_id")}
        teile.append(f"[V1] Vorlage {template.get('template_number') or ''}, Beschlussvorschlag:\n{vorschlag[:BASIS_ZEICHEN]}")
    anchor = None
    refs = paragraph_refs(antrag[:3000])
    for i, st in enumerate(statutes, 2):
        for sec, par in refs:
            wortlaut = paragraph_text(st.get("text") or "", sec, par)
            if wortlaut:
                key = f"A{i}"
                quellen[key] = {"text": st["text"], "pages": st.get("pages"), "document_id": st.get("document_id")}
                anchor = {"source": key, "section": sec, "paragraph": par, "text": wortlaut}
                teile.append(f"[{key}] Geltender Wortlaut § {sec}{f' Abs. {par}' if par else ''} aus „{st.get('label')}“:\n{wortlaut[:BASIS_ZEICHEN]}")
                break
        if anchor:
            break
    return "\n\n".join(teile), quellen, anchor or {}


def _aussage(payload: dict, key: str, quellen: dict, dropped: list[dict], *, zitat_aus: list | None = None,
             zusatz: list[str] | None = None) -> dict | None:
    e = payload.get(key)
    if not e:
        return None
    if isinstance(e, str):
        # Ein bloßer Satz ohne Zitat: belegt wird er gegen die Zitate der
        # anderen Felder — das erste, das ihn trägt, gilt; sonst fällt er.
        satz, grund = e, "Satz ohne Zitat"
        for kandidat in [k for k in (zitat_aus or []) if isinstance(k, dict) and k.get("quote")]:
            ok, grund = evidence.check_statement({**kandidat, "text": satz}, quellen, zusatz_zitate=zusatz)
            if ok:
                return ok
        dropped.append({"field": key, "reason": grund, "entry": e})
        return None
    if key in ("before", "after") and isinstance(e, dict) and e.get("quote"):
        # Alt und neu zeigen den Wortlaut selbst; ein Umschreibsatz daneben
        # wäre nur eine zweite, ungeprüfte Fassung.
        e = {**e, "text": str(e["quote"])[:WORTLAUT_MAX]}
    wortlaut = key in ("before", "after")
    ok, grund = evidence.check_statement(e, quellen, limit=WORTLAUT_MAX if wortlaut else evidence.SATZ_MAX,
                                         zusatz_zitate=zusatz, quote_max=WORTLAUT_MAX if wortlaut else evidence.QUOTE_MAX)
    if not ok:
        dropped.append({"field": key, "reason": grund, "entry": e})
    return ok


def verify(payload: dict, quellen: dict, anchor: dict, motion: dict, item_template: str | None) -> dict:
    """Die geprüfte Fassung eines Auszugs — was nicht belegt ist, fällt weg."""
    dropped: list[dict] = []
    muster = payload.get("pattern") if payload.get("pattern") in PATTERNS else None
    before = _aussage(payload, "before", quellen, dropped)
    after = _aussage(payload, "after", quellen, dropped)
    # Alt und neu als derselbe Satz ist kein Paar, sondern die Änderungsanweisung
    # zweimal („… wird durch … ersetzt") — dann gibt es kein belegtes Alt.
    if before and after and evidence.tight(before["quote"]) == evidence.tight(after["quote"]):
        dropped.append({"field": "before", "reason": "alt gleich neu", "entry": before})
        before = None
    # §-Anker: Den geltenden Wortlaut kennt der Code — er gewinnt über das Modell.
    diff = None
    if anchor:
        before = {"text": anchor["text"][:WORTLAUT_MAX], "quote": anchor["text"][:WORTLAUT_MAX],
                  "source": anchor["source"], "page": None}
        if after:
            # Das Modell zitiert oft nur den Anfang der Neufassung. Der Wortdiff
            # braucht sie ganz — sonst sähe der Rest wie gestrichen aus.
            neu = neufassung(quellen["A1"]["text"], after["quote"])
            if neu:
                diff = word_diff(anchor["text"], neu)
    out = {
        "applicants": parties_in_text(motion.get("label")) or parties_in_text(motion["text"][:4000]),
        "target": evidence.squash(str(payload.get("target") or ""))[:80] or None,
        "pattern": muster,
        "before": before,
        "after": after,
        "diff": diff,
        "meaning": _aussage(payload, "meaning", quellen, dropped,
                            zitat_aus=[payload.get("after"), payload.get("reason"), payload.get("before")],
                            zusatz=[x["quote"] for x in (before, after) if x]),
        "reason": _aussage(payload, "reason", quellen, dropped),
        "base_template": base_reference(motion["text"], item_template),
        "base_missing": bool(payload.get("base_missing")) and not before,
        "anchor": {k: anchor[k] for k in ("section", "paragraph")} if anchor else None,
        "dropped": dropped,
    }
    if out["target"] and evidence.satz_sauber(out["target"]):
        out["target"] = None
    return out


def extract(motion: dict, template: dict | None, statutes: list[dict], item_template: str | None,
            *, batch: bool = True) -> tuple[dict, float]:
    """Ein Antrag → geprüfter Auszug und Kosten. ``batch``: Cron (Flex, Geduld)."""
    nutzer, quellen, anchor = build_input(motion, template, statutes)
    extra = {"_geduld": True, "_ersatz": llm.ersatz_fuer(MODEL, lange_ausgabe=True), "_tarif": "flex"} if batch else {}
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": prompts.get("motion_extract_system")},
                  {"role": "user", "content": nutzer}],
        max_tokens=4_000, _feature="motion_extract", **extra)
    try:
        payload = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        payload = {}
    from council.plan_judge import cost_usd  # noqa: PLC0415 — dieselbe Rechnung wie die Pläne

    kosten = cost_usd(resp, MODEL)
    return verify(payload if isinstance(payload, dict) else {}, quellen, anchor, motion, item_template), kosten


# ---- Lauf ----------------------------------------------------------------------

def _hash(text: str | None) -> str:
    from council.unterlagen_seiten import text_hash  # noqa: PLC0415
    return text_hash(text or "")


def extract_one(store, document_id: int, ksinr: int, item_number: str, *, batch: bool = True,
                force: bool = False) -> dict | None:
    """Einen Antrag lesen und speichern — oder den gespeicherten Auszug, wenn
    Text, Basis und Prompt-Fassung gleich geblieben sind."""
    m = store.motion_material(document_id, ksinr, item_number)
    if not m:
        return None
    th = _hash(m["motion"]["text"])
    bh = _hash((m["template"] or {}).get("proposed_decision"))
    alt = store.motion_extract(document_id)
    if alt and not force and alt["text_hash"] == th and alt["base_hash"] == bh \
            and alt["prompt_version"] == PROMPT_VERSION and alt["status"] == "ok":
        return alt["payload"]
    try:
        payload, kosten = extract(m["motion"], m["template"], m["statutes"], m["item_template"], batch=batch)
    except Exception:  # noqa: BLE001 — ein Antrag kippt nicht den Lauf
        _log.exception("Antrag %s nicht gelesen", document_id)
        store.save_motion_extract(document_id, base_subject_key=m["base_subject_key"], base_hash=bh, text_hash=th,
                                  status="failed", payload=None, prompt_version=PROMPT_VERSION, model=MODEL,
                                  cost_usd=None)
        return None
    store.save_motion_extract(document_id, base_subject_key=m["base_subject_key"], base_hash=bh, text_hash=th,
                              status="ok", payload=payload, prompt_version=PROMPT_VERSION, model=MODEL, cost_usd=kosten)
    return payload


def nachziehen(store, *, tage_zurueck: int = 2, tage_voraus: int = 21, limit: int = 20, stopp=None) -> dict:
    """Anträge an Punkten kommender (und gerade vergangener) Sitzungen lesen."""
    from datetime import date, timedelta  # noqa: PLC0415

    heute = date.today()
    kandidaten = store.antraege_kommender_punkte((heute - timedelta(days=tage_zurueck)).isoformat(),
                                                 (heute + timedelta(days=tage_voraus)).isoformat())
    gelesen = 0
    for k in kandidaten:
        if gelesen >= limit or (stopp is not None and stopp.grund() is not None):
            break
        alt = store.motion_extract(k["document_id"])
        vorher = (alt or {}).get("created_at")
        extract_one(store, k["document_id"], k["ksinr"], k["item_number"])
        neu = store.motion_extract(k["document_id"])
        frisch = bool(neu and neu.get("created_at") != vorher)
        gelesen += frisch
        if frisch and stopp is not None and neu and neu.get("cost_usd"):
            stopp.ausgeben(float(neu["cost_usd"]))  # sonst deckelt die Kostengrenze den Lauf nicht
    return {"antraege": len(kandidaten), "gelesen": gelesen}


# ---- Zuordnung zur Teilabstimmung (ohne Modell) --------------------------------

_WORT_RE = re.compile(r"[a-zäöüß]{4,}")
_FUELL = {"änderungsantrag", "antrag", "fraktion", "fraktionen", "beschlussvorschlag", "oldenburg", "stadt",
          "wird", "werden", "sollen", "einer", "eines", "dieser", "durch", "sowie", "zur", "der", "die", "das"}


def _woerter(text: str | None) -> set[str]:
    return {w for w in _WORT_RE.findall((text or "").lower()) if w not in _FUELL}


_VERFAHREN_RE = re.compile(r"geschäftsordnung|vertag|verweis|zurückstell|zurückverwei|absetz|nichtbefassung|"
                           r"schluss\s+der\s+(?:debatte|aussprache|rednerliste)|unterbrech|als\s+behandelt", re.I)
_EINZELPERSON_RE = re.compile(r"\b(?:Rats(?:herr|frau|mitglied(?:s|es)?)|Bürgermeister(?:in)?|Oberbürgermeister(?:in)?)\b")


def match_subvote(motion: dict, subvotes: list[dict]) -> int | None:
    """Die Teilabstimmung im Protokoll, über die über diesen Antrag abgestimmt
    wurde — nur wenn eindeutig, lieber keine Zuordnung als eine falsche.

    ``motion``: ``{"applicants", "label", "target", "meaning"}``; ``subvotes``:
    Teilabstimmungen desselben Punkts (``title``, ``factions``, ``id``)."""
    from council.parties import normalize_party as normalize  # noqa: PLC0415

    eigene = {normalize(p) for p in motion.get("applicants") or []}
    kandidaten = []
    for sv in subvotes:
        titel = sv.get("title") or ""
        # Verfahrensanträge (Vertagung, Verweisung, „als behandelt") sind keine
        # Anträge zur Sache — am 13.11.2026 hingen so zwei Vertagungsanträge an
        # Hauptanträgen (eval/run_zuordnung.py).
        if not re.search(r"antrag", titel, re.I) or _VERFAHREN_RE.search(titel):
            continue
        titel_parteien = {normalize(p) for p in parties_in_text(titel)}
        if _EINZELPERSON_RE.search(titel):
            # „Änderungsantrag von Ratsherr …": `factions` sind dann die Fraktionen,
            # die abgestimmt haben, nicht die Antragsteller — nur der Titel zählt.
            parteien = titel_parteien
            if eigene and not (eigene & parteien):
                continue
        else:
            parteien = {normalize(p) for p in (sv.get("factions") or [])} | titel_parteien
        if eigene and parteien and not (eigene & parteien):
            continue
        kandidaten.append((sv, parteien))
    if not kandidaten:
        return None
    if len(kandidaten) == 1 and eigene and kandidaten[0][1] & eigene:
        return kandidaten[0][0]["id"]
    inhalt = _woerter(" ".join(filter(None, [motion.get("label"), motion.get("target"), motion.get("meaning")])))
    wertung = sorted(((len(inhalt & _woerter(sv.get("title"))), sv["id"]) for sv, _ in kandidaten), reverse=True)
    if wertung[0][0] >= 2 and (len(wertung) == 1 or wertung[0][0] >= wertung[1][0] + 2):
        return wertung[0][1]
    return None
