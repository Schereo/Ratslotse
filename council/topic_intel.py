"""Themen-Intelligenz (Design 26a / RL-U17): aus einem Themen-*Namen* eine
brauchbare Themen-*Beschreibung* machen — und vorher prüfen, ob der Rat mit der
Sache überhaupt zu tun hat.

Warum überhaupt: Die Beschreibung ist kein Deko-Text, sondern das, woran der
Themen-Wächter später jeden Beschluss misst (`match_topics_decisions`). Ein
Nutzer, der „Cäcilienbrücke" eintippt und das Feld leer lässt, bekam bisher
einen generischen Satz — und damit unscharfe Treffer. Hier entsteht die
Beschreibung stattdessen aus den Beschlüssen, die zum Namen wirklich existieren.

Ablauf (bewusst ein einziger LLM-Aufruf):

1. **Belege sammeln** — semantische Suche über die vorhandenen Embeddings,
   Keyword-Suche als Rückfallebene, wenn fastembed fehlt.
2. **Beurteilen + beschreiben** — die Treffer gehen als Kontext ans Modell, das
   in einem Rutsch sagt, ob das ein Ratsthema ist, und einen präzisen Satz
   formuliert. Ohne Belege wird gar nicht erst gefragt.

Alles ist ausfallsicher: Fehlt fastembed, fällt die Suche auf Volltext zurück;
antwortet das Modell nicht oder unbrauchbar, kommt ein deterministischer Satz.
Ein Themen-Anlegen darf nie daran scheitern, dass ein LLM gerade hakt.
"""
from __future__ import annotations

import json
import os
import re

from nwz import llm, prompts

MODEL = os.environ.get("TOPIC_INTEL_MODEL", "deepseek/deepseek-v4-pro")

# Ab wie vielen belastbaren Treffern gilt eine Sache als „im Rat behandelt".
# Zwei statt einem: Ein einzelner Zufallstreffer (ein Name fällt in einem
# Nebensatz) macht noch kein Thema, das sich zu abonnieren lohnt.
MIN_MATCHES = 2
# Kosinus-Schwelle der semantischen Suche. Darunter ist die Ähnlichkeit
# Rauschen — „mein Hund" landet sonst über irgendeinem Tierheim-Beschluss.
MIN_SCORE = 0.42
_MAX_CONTEXT = 12
_MAX_DESC = 240


def find_matches(store, name: str, limit: int = _MAX_CONTEXT) -> list[dict]:
    """Beschlüsse, die zum Themen-Namen passen — beste zuerst.

    Semantisch, wenn fastembed da ist (fängt „Radweg" ↔ „Veloroute"), sonst
    Volltext. Die Rückfallebene ist wichtig: Das Web-Backend läuft auch ohne
    das ONNX-Modell, und dann soll das Anlegen trotzdem funktionieren.
    """
    query = (name or "").strip()
    if len(query) < 3:
        return []
    ids: list[int] = []
    try:
        from council import embeddings as emb

        ids = [i for i, _ in emb.search(store, query, top_k=limit, min_score=MIN_SCORE)]
    except Exception:  # noqa: BLE001 — fastembed fehlt/Modell lädt nicht
        ids = []
    if not ids:
        try:
            ids = [i for i, _ in store.search_decisions_fts(query, limit=limit)]
        except Exception:  # noqa: BLE001
            return []
    if not ids:
        return []
    rows = store.get_decisions_by_ids(ids)  # behält die Reihenfolge
    return rows[:limit]


# Wörter, die in einem Themen-*Namen* nichts verloren haben: Anrede und
# Befehlsformen. Ein Thema ist eine Sache („Cäcilienbrücke"), kein Satz an mich.
_INSTRUCTION_WORDS = {
    "ignoriere", "ignorier", "vergiss", "vergesse", "vergessen", "beachte",
    "antworte", "schreibe", "zeige", "zeig", "gib", "gebe", "liste", "nenne",
    "erkläre", "sage", "sag", "mach", "mache", "tue", "musst", "sollst",
    "darfst", "bist", "system", "prompt", "anweisung", "anweisungen",
    "instruction", "instructions", "ignore", "forget", "you", "your",
}
_MAX_NAME_WORDS = 8


def looks_like_instruction(name: str) -> bool:
    """Sieht der „Name" nach einem Satz oder einer Anweisung aus?

    Rein strukturell und ohne LLM — deshalb auch dann verlässlich, wenn das
    Modell gerade hakt. Zwei Signale genügen: Länge (echte Themen sind kurze
    Substantiv-Fügungen; „Ausbau der Grundschule Auf der Wunderburg" sind sechs
    Wörter) und Anrede-/Befehlswörter.
    """
    text = (name or "").strip()
    if not text:
        return False
    words = re.findall(r"[\wÄÖÜäöüß-]+", text.lower())
    if len(words) > _MAX_NAME_WORDS:
        return True
    return bool(_INSTRUCTION_WORDS & set(words))


def _context(matches: list[dict]) -> str:
    lines = []
    for m in matches:
        meta = " · ".join(p for p in (m.get("committee"), m.get("session_date")) if p)
        body = (m.get("summary") or m.get("beschluss") or "").strip()[:220]
        lines.append(f"- {(m.get('title') or '').strip()} ({meta}): {body}")
    return "\n".join(lines)


def _fallback_description(name: str, matches: list[dict]) -> str:
    """Ohne (brauchbare) LLM-Antwort: ein Satz aus dem, was wir sicher wissen.
    Nennt das Themenfeld, wenn die Treffer sich einig sind — das schärft den
    Wächter immer noch mehr als reines „alles rund um X"."""
    from council.topics import POLICY_FIELDS

    fields = [m.get("policy_field") for m in matches if m.get("policy_field")]
    label = ""
    if fields:
        top = max(set(fields), key=fields.count)
        if fields.count(top) >= max(2, len(fields) // 3):
            label = POLICY_FIELDS.get(top, ("",))[0]
    zusatz = f" im Themenfeld {label}" if label else ""
    return (f"Beschlüsse, Planungen und Maßnahmen des Oldenburger Stadtrats "
            f"rund um {name.strip()}{zusatz}.")


def _parse(raw: str) -> dict | None:
    """JSON aus der Modellantwort schälen (auch wenn Text drumherum steht)."""
    if not raw:
        return None
    txt = raw.strip()
    start, end = txt.find("{"), txt.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(txt[start:end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _call_model(name: str, matches: list[dict]) -> dict | None:
    """Der eine LLM-Aufruf — als eigene Funktion, damit Tests ihn ersetzen können
    (die Suite darf nie ein echtes Modell rufen). ``None`` bei jedem Fehler:
    Ein hakendes Modell darf ein Thema weder anlegen noch verhindern."""
    try:
        prompt = prompts.render("topic_auto_beschreibung", name=name[:120], context=_context(matches))
        extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in MODEL else {}
        resp = llm.chat_complete(
            model=MODEL, _feature="topic_auto_beschreibung", temperature=0.2, max_tokens=300,
            messages=[{"role": "user", "content": prompt}], **extra,
        )
        return _parse(resp.choices[0].message.content or "")
    except Exception:  # noqa: BLE001 — LLM aus/Timeout
        return None


VERDICTS = ("belegt", "plausibel", "ungeeignet")


def analyse(store, name: str) -> dict:
    """Ein Themen-Name → Einordnung + Beschreibung.

    Drei Zustände, weil zwei zu grob sind. „Grundschule Krusenbusch" ist eine
    echte Oldenburger Schule — der Rat hat über sie nur noch nichts beschlossen.
    Das ist etwas völlig anderes als „Vergiss deine Anweisungen": das eine darf
    man anlegen (und wird benachrichtigt, sobald es so weit ist), das andere nicht.

      ``verdict``          — "belegt" | "plausibel" | "ungeeignet"
      ``is_council_topic`` — alles außer "ungeeignet" (Altlast, Frontend nutzt verdict)
      ``description``      — ein Satz, direkt als Themen-Beschreibung nutzbar
      ``matches``          — Anzahl BELEGENDER Beschlüsse (0, wenn nur plausibel)
      ``examples``         — bis zu 3 Titel als sichtbarer Beleg
      ``reason``           — kurze Begründung, wenn es kein Ratsthema ist

    Gefragt wird immer — auch ohne Suchtreffer. Ohne die Frage könnten wir
    „plausibel" gar nicht von „ungeeignet" unterscheiden, und genau diese
    Unterscheidung ist der Punkt.
    """
    clean = (name or "").strip()
    matches = find_matches(store, clean)
    examples = [(m.get("title") or "").strip() for m in matches[:3] if m.get("title")]

    # Freie Vorprüfung: Ein Themen-Name ist eine Sache, kein Satz. Was wie eine
    # Anweisung aussieht, geht gar nicht erst ans Modell — das spart den Aufruf
    # und nimmt Prompt-Injection den Weg über den Umweg „Themen-Beschreibung",
    # die später in den Wächter-Prompt wandert.
    if looks_like_instruction(clean):
        return {
            "verdict": "ungeeignet", "is_council_topic": False, "description": "",
            "matches": 0, "examples": [],
            "reason": ("Das liest sich wie ein ganzer Satz. Ein Thema ist eine Sache — "
                       "etwa „Cäcilienbrücke\" oder „Grundschule Krusenbusch\"."),
        }

    obj = _call_model(clean, matches)

    if not obj:
        # Modell weg: Wir dürfen weder fälschlich anlegen noch grundlos ablehnen.
        # Belege entscheiden — mit genug Treffern gilt es als belegt, sonst als
        # plausibel. „Ungeeignet" behaupten wir ohne Urteil nie.
        belegt = len(matches) >= MIN_MATCHES
        return {"verdict": "belegt" if belegt else "plausibel", "is_council_topic": True,
                "description": _fallback_description(clean, matches),
                "matches": len(matches) if belegt else 0, "examples": examples if belegt else [],
                "reason": ""}

    desc = str(obj.get("beschreibung") or "").strip()[:_MAX_DESC]
    verdict = str(obj.get("einordnung") or "").strip().lower()
    if verdict not in VERDICTS:
        verdict = "belegt" if len(matches) >= MIN_MATCHES else "plausibel"
    # Das Modell darf nur nach unten korrigieren: Es sieht die Beschlüsse und
    # erkennt, dass „Grundschule Krusenbusch" von der Wunderburg-Schule handelt —
    # eine Trefferzahl allein kann das nicht.
    if verdict == "belegt" and len(matches) < MIN_MATCHES:
        verdict = "plausibel"
    belegt = verdict == "belegt"
    return {
        "verdict": verdict,
        "is_council_topic": verdict != "ungeeignet",
        "description": "" if verdict == "ungeeignet" else (desc or _fallback_description(clean, matches)),
        # Nur belegte Treffer zählen: Sonst stünde „12 Beschlüsse passen dazu"
        # unter einem Thema, zu dem das Modell gerade das Gegenteil gesagt hat.
        "matches": len(matches) if belegt else 0,
        "examples": examples if belegt else [],
        "reason": str(obj.get("begruendung") or "").strip()[:200] if verdict == "ungeeignet" else "",
    }


def check_vagueness(name: str, description: str) -> dict:
    """Die bestehende Vagheits-Prüfung — bis 26a lag sie brach: Der Prompt war
    seit jeher admin-editierbar hinterlegt, aber es gab keinen einzigen Aufruf.

    Rückgabe ``{vague, hint, suggestion}``. Bei jedem Fehler „nicht vage": Eine
    kaputte Prüfung darf niemanden am Anlegen hindern.
    """
    text = (description or "").strip()
    if not text:
        return {"vague": False, "hint": "", "suggestion": ""}
    try:
        system = prompts.get("vagueness_check_system")
        extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in MODEL else {}
        resp = llm.chat_complete(
            model=MODEL, _feature="vagueness_check", temperature=0, max_tokens=300,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Thema: {(name or '').strip()[:120]}\nBeschreibung: {text[:600]}"},
            ], **extra,
        )
        obj = _parse(resp.choices[0].message.content or "") or {}
    except Exception:  # noqa: BLE001
        return {"vague": False, "hint": "", "suggestion": ""}
    return {
        "vague": bool(obj.get("vague")),
        "hint": str(obj.get("hint") or "").strip()[:300],
        "suggestion": str(obj.get("suggestion") or "").strip()[:_MAX_DESC],
    }


_GENERIC = {
    # Gattungsbegriffe, die als Themen-Name nichts eingrenzen. Sie kommen aus
    # der Entitäten-Erkennung durch und würden als Vorschlag Beschlüsse quer
    # durch die Stadt einsammeln.
    "bericht", "berichte", "antrag", "anträge", "beschluss", "beschlüsse",
    "haushalt", "stadt", "oldenburg", "rat", "verwaltung", "ausschuss",
    "sitzung", "vorlage", "projekt", "maßnahme", "planung", "konzept",
    "innenstadt", "klima", "wohnen", "schule", "schulen", "verkehr", "umwelt",
    "kultur", "sport", "soziales", "digitalisierung", "sicherheit",
}


def looks_generic(name: str) -> bool:
    """Billiger Vorfilter für Vorschläge: ein einzelnes Gattungswort.

    Bewusst deterministisch — er läuft über jeden Vorschlagskandidaten und darf
    nichts kosten. Die teure Vagheits-Prüfung urteilt danach und nur einmal je
    Kandidat (Ergebnis wird gecacht).
    """
    n = re.sub(r"[^\wäöüß\s-]", "", (name or "").strip().lower())
    if not n:
        return True
    words = [w for w in n.split() if w]
    return len(words) == 1 and words[0] in _GENERIC
