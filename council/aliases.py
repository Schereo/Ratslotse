"""Themen-Dubletten erkennen und zusammenführen (``council_entity_aliases``).

Die Entitäten-Extraktion entscheidet je Beschluss-Batch neu, wie sie eine Sache
benennt. Über Jahre entstehen so mehrere Themen-Seiten für denselben Gegenstand —
gemessen am Produktionsbestand (23.07.2026): **23 Gruppen, 50 Entitäten, 453
betroffene Beschlüsse**. Der Bäderbetrieb hat vier Namen, die Gebäudewirtschaft
drei plus Abkürzung.

Der Prompt in :mod:`council.entities` verlangt bereits die "kürzeste kanonische
Form". Das kann nicht greifen, weil jeder Batch für sich entscheidet und den
Bestand nicht kennt — die Zusammenführung braucht deshalb einen Durchlauf über
den *Gesamtbestand*, und der findet hier statt.

Erkennungsmerkmal aus der Messung: **echte Dubletten haben eine Beschluss-
überlappung von 0,00 bei sehr hoher Embedding-Nähe.** Das ist zunächst
kontraintuitiv, folgt aber direkt aus der Ursache — nennt die Extraktion in einem
Beschluss "Bäderbetrieb Oldenburg", nennt sie dort nicht zusätzlich "Bäderbetrieb
der Stadt Oldenburg". Zwei Namen desselben Gegenstands treten daher nie gemeinsam
auf, behandeln aber dieselben Inhalte.

Zwei Stufen, weil Namensähnlichkeit allein nicht reicht:

1. :func:`candidates` findet Paare über Normalisierung (Rechtsform, Ortszusatz,
   Präfix, Abkürzung, Teilstring) — billig, aber unscharf.
2. :func:`decide` legt jedes Paar mit Beschlusstiteln dem LLM vor. Nötig, weil die
   Kandidaten legitime Unterschiede enthalten: "Alexanderstraße"/"Alexanderstraße
   Nord" sind zwei Gegenstände, "IBIS"/"IBIS e.V." ist einer.

Die Zusammenführung ist **reversibel**: Geschrieben wird nur die Alias-Tabelle. Die
Roh-Beobachtungen (``council_entity_obs``) bleiben unangetastet, und
``rebuild_entities_from_obs`` leitet die Themen bei jedem Lauf neu daraus ab.
Eine Alias-Zeile löschen und neu ableiten stellt den vorherigen Stand her.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter, defaultdict

from nwz import llm, prompts

MODEL = os.environ.get("COUNCIL_ALIAS_MODEL", "deepseek/deepseek-v4-pro")

logger = logging.getLogger("council.aliases")

BATCH = 20            # Paare je LLM-Aufruf
MIN_EMB = 0.55        # darunter lohnt die LLM-Prüfung nicht (aus der Messung)

# Rechtsformen. Punkt-Abkürzungen ("e. V.", "a. ö. R.") brauchen ein eigenes
# Muster — hinter einem Punkt greift \b nicht, "IBIS e. V." bliebe sonst stehen.
_LEGAL = (r"e\.\s*v\.?|a\.\s*ö\.\s*r\.?|ggmbh|gmbh|mbh|aör|ag|kg|gbr|"
          r"gemeinnützige|stiftung des öffentlichen rechts")
_CITY = r"der stadt oldenburg|stadt oldenburg|oldenburger|oldenburg"
_PREFIX = r"^(eigenbetrieb|sanierungsgebiet|vorhabenbezogener|neue[sr]?|ehemalige[sr]?|geplante[sr]?)\s+"
_STOPWORDS = {"und", "der", "die", "das", "des", "für", "von", "zur", "zum", "am", "im", "an"}


def strip_legal(name: str) -> str:
    """Rechtsform entfernen: „Deutsche Bahn AG" → „Deutsche Bahn", „IBIS e. V." → „IBIS"."""
    out = re.sub(r"(?<![a-zäöüß])(" + _LEGAL + r")(?![a-zäöüß])", " ", name or "", flags=re.I)
    return re.sub(r"\s+", " ", out).strip(" -,.")


def strip_city(name: str) -> str:
    """Ortszusatz entfernen: „Bäderbetrieb der Stadt Oldenburg" → „Bäderbetrieb"."""
    out = re.sub(r"\b(" + _CITY + r")\b", " ", name or "", flags=re.I)
    return re.sub(r"\s+", " ", out).strip(" -,.")


def strip_prefix(name: str) -> str:
    """Vorangestellte Gattung entfernen: „Eigenbetrieb Hafen" → „Hafen"."""
    return re.sub(_PREFIX, "", name, flags=re.I).strip()


def core(name: str) -> str:
    """Vergleichsschlüssel: ohne Rechtsform, Ortszusatz, Satz- und Leerzeichen."""
    return re.sub(r"[^a-zäöüß0-9]", "", strip_city(strip_legal(name or "")).lower())


def initials(name: str) -> str:
    """Anfangsbuchstaben der bedeutungstragenden Wörter („Verkehr und Wasser" → „vw")."""
    words = [w for w in re.split(r"[\s\-/]+", name or "") if w and w.lower() not in _STOPWORDS]
    return "".join(w[0] for w in words if w[:1].isalpha()).lower()


def candidates(entities: list[dict], ent_decs: dict[int, set],
               centroids: dict | None = None, min_emb: float = MIN_EMB) -> list[dict]:
    """Mögliche Dubletten-Paare, jeweils mit Art und Signalen.

    ``entities`` = [{id, slug, name, kind, n}], ``ent_decs`` = {entity_id: {decision_id}}.
    ``centroids`` (optional) = {entity_id: normalisierter Vektor} zum Vorfiltern.
    """
    by_id = {e["id"]: e for e in entities}
    out: dict[tuple, dict] = {}

    def add(a: int, b: int, kind: str) -> None:
        key = (min(a, b), max(a, b))
        out.setdefault(key, {"a": key[0], "b": key[1], "art": kind})

    # A) gleicher Kern nach Entfernen von Rechtsform + Ortszusatz
    buckets: dict[str, list[int]] = defaultdict(list)
    for i, e in by_id.items():
        c = core(e["name"])
        if len(c) >= 4:
            buckets[c].append(i)
    for ids in buckets.values():
        for idx, a in enumerate(ids):
            for b in ids[idx + 1:]:
                add(a, b, "rechtsform_ort")

    # B) Abkürzung ↔ Langform
    for i, e in by_id.items():
        nm = (e["name"] or "").strip()
        if not (2 <= len(nm) <= 6 and nm.isupper()):
            continue
        target = nm.lower()
        for j, f in by_id.items():
            if i == j or len(f["name"] or "") < 8:
                continue
            if target in (initials(f["name"]), initials(strip_legal(f["name"]))):
                add(i, j, "abkuerzung")

    # C) vorangestellte Gattung ("Eigenbetrieb X" ↔ "X")
    by_core = {}
    for i, e in by_id.items():
        by_core.setdefault(core(e["name"]), i)
    for i, e in by_id.items():
        stripped = strip_prefix(e["name"] or "")
        if stripped != e["name"] and len(stripped) >= 5:
            j = by_core.get(core(stripped))
            if j is not None and j != i:
                add(i, j, "praefix")

    # D) reiner Teilstring — die unschärfste Art, deshalb zuletzt und nur mit
    #    Embedding-Rückhalt (sonst 190 Paare, davon die meisten keine Dubletten).
    keys = {i: re.sub(r"[^a-zäöüß0-9]", "", (e["name"] or "").lower()) for i, e in by_id.items()}
    ids = sorted(by_id)
    for idx, a in enumerate(ids):
        ka = keys[a]
        if len(ka) < 5:
            continue
        for b in ids[idx + 1:]:
            kb = keys[b]
            if len(kb) < 5 or ka == kb or (min(a, b), max(a, b)) in out:
                continue
            if ka in kb or kb in ka:
                add(a, b, "teilstring")

    rows = []
    for (a, b), row in out.items():
        union = ent_decs.get(a, set()) | ent_decs.get(b, set())
        row["overlap"] = (len(ent_decs.get(a, set()) & ent_decs.get(b, set())) / len(union)
                          if union else 0.0)
        row["emb"] = None
        if centroids and a in centroids and b in centroids:
            row["emb"] = float(centroids[a] @ centroids[b])
        # Der Teilstring-Topf braucht den Embedding-Rückhalt; die gezielten Arten
        # (Rechtsform/Abkürzung/Präfix) gehen auch ohne Vektor zur Prüfung.
        if row["art"] == "teilstring" and (row["emb"] is None or row["emb"] < min_emb):
            continue
        rows.append(row)
    rows.sort(key=lambda r: -(by_id[r["a"]]["n"] + by_id[r["b"]]["n"]))
    return rows


def _render(pairs: list[dict], by_id: dict, titles: dict[int, list[str]]) -> str:
    lines = []
    for idx, p in enumerate(pairs):
        a, b = by_id[p["a"]], by_id[p["b"]]
        lines.append(f"- id {idx}:")
        for e in (a, b):
            ts = "; ".join(t[:80] for t in titles.get(e["id"], [])[:3])
            lines.append(f'    "{e["name"]}" ({e.get("kind") or "?"}, {e["n"]} Beschlüsse)'
                         + (f" — z.B. {ts}" if ts else ""))
    return "\n".join(lines)


def _strip_fences(content: str) -> str:
    c = (content or "").strip()
    if c.startswith("```"):
        c = c.strip("`").strip()
        if c.lower().startswith("json"):
            c = c[4:].strip()
    return c


def decide(pairs: list[dict], entities: list[dict], titles: dict[int, list[str]],
           model: str = MODEL) -> list[dict]:
    """Legt die Kandidaten dem LLM vor. Gibt die bestätigten Paare zurück,
    ergänzt um ``canonical`` (entity_id) und ``reason``."""
    by_id = {e["id"]: e for e in entities}
    confirmed: list[dict] = []
    for start in range(0, len(pairs), BATCH):
        chunk = pairs[start:start + BATCH]
        try:
            resp = llm.chat_complete(
                model=model,
                messages=[
                    {"role": "system", "content": prompts.get("entity_dubletten_system")},
                    {"role": "user", "content": prompts.render(
                        "entity_dubletten_user", paare=_render(chunk, by_id, titles))},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                _feature="entity_dubletten",
            )
            data = json.loads(_strip_fences(resp.choices[0].message.content))
        except Exception as exc:  # noqa: BLE001 — ein Batch darf den Lauf nicht kippen
            logger.warning("Dubletten-Batch %d übersprungen: %r", start // BATCH, exc)
            continue
        for item in data.get("paare", []):
            try:
                idx = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if not (0 <= idx < len(chunk)) or not item.get("gleich"):
                continue
            pair = dict(chunk[idx])
            a, b = by_id[pair["a"]], by_id[pair["b"]]
            wanted = (item.get("kanonisch") or "").strip().lower()
            # Kanon: die LLM-Wahl, sonst der Name mit den meisten Beschlüssen.
            if wanted == (a["name"] or "").lower():
                canon, alias = a, b
            elif wanted == (b["name"] or "").lower():
                canon, alias = b, a
            else:
                canon, alias = (a, b) if a["n"] >= b["n"] else (b, a)
            # Bei Abkürzungen gewinnt immer die Langform, auch gegen die LLM-Wahl:
            # eine Themen-Seite "EGH" sagt niemandem etwas, und wer nach der
            # Abkürzung sucht, landet über den Alias ohnehin richtig. ("kürzeste
            # kanonische Form" im Prompt wird sonst als "Abkürzung" gelesen.)
            if pair["art"] == "abkuerzung" and len(canon["name"] or "") < len(alias["name"] or ""):
                canon, alias = alias, canon
            pair["canonical"] = canon["id"]
            pair["alias"] = alias["id"]
            pair["reason"] = (item.get("grund") or "").strip()[:200]
            confirmed.append(pair)
    return confirmed


def resolve_chains(mapping: dict[str, str]) -> dict[str, str]:
    """Ketten auflösen und Zyklen brechen: A→B, B→C wird zu A→C, B→C.

    Ohne das würde eine nachträglich bestätigte Zusammenführung eine tote
    Zwischenstufe hinterlassen (A zeigt auf B, das es als Thema nicht mehr gibt).
    """
    out: dict[str, str] = {}
    for src in mapping:
        seen = {src}
        cur = mapping[src]
        while cur in mapping and cur not in seen:
            seen.add(cur)
            cur = mapping[cur]
        if cur != src:          # Zyklus → Zuordnung verwerfen
            out[src] = cur
    return out
