"""Question answering over council decisions ("Frag den Stadtrat").

Retrieval is keyword-based (German nouns from the question), then the LLM answers
*only* from the retrieved decisions and cites them by id. Honest by construction:
if the retrieved decisions don't answer the question, the model says so. Semantic
embedding retrieval is the planned upgrade (see council-ai-roadmap).
"""
from __future__ import annotations

import json
import os
import re

from nwz import llm, prompts
from council.topics import _strip_fences  # noqa: F401  (kept for symmetry / future use)

MODEL = os.environ.get("COUNCIL_QA_MODEL", "deepseek/deepseek-v4-pro")

_STOP = {
    "wurde", "wurden", "wird", "werden", "beschlossen", "beschluss", "stadt", "stadtrat",
    "oldenburg", "welche", "welcher", "welches", "wann", "warum", "wieso", "wofür",
    "haben", "hat", "gibt", "über", "zum", "zur", "eine", "einen", "einer", "nicht",
}


def extract_keywords(question: str) -> list[str]:
    """German nouns (capitalised words) are the best query terms; fall back to long words.
    Hyphenated compounds are also split so "Photovoltaik-Projekte" still matches "Photovoltaik"."""
    nouns = re.findall(r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß-]{3,}\b", question)
    terms = [w.lower() for w in nouns] if nouns else re.findall(r"[a-zäöüß-]{4,}", question.lower())
    out: list[str] = []
    for t in terms:
        for part in [t, *t.split("-")]:
            if len(part) >= 4 and part not in _STOP and part not in out:
                out.append(part)
    return out[:8]


# Die Prompt-Templates leben in nwz/prompts.py („qa_antwort" / „qa_suchbegriffe")
# und sind — wie alle anderen — über das Admin-UI live editierbar.


def expand_query(question: str, model: str = MODEL) -> str:
    """Turn a question into focused topical search terms. The raw question's
    boilerplate ("Was wurde zum … beschlossen?") dilutes the topic and retrieves
    generic decisions; expanded terms (e.g. "Radverkehr Fahrrad Radweg Fahrradstraße")
    retrieve far better. Falls back to the question on any error."""
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    try:
        prompt = prompts.render("qa_suchbegriffe", question=question.strip()[:300])
        resp = llm.chat_complete(
            model=model, _feature="qa_query_expansion", temperature=0, max_tokens=60,
            messages=[{"role": "user", "content": prompt}], **extra,
        )
        terms = " ".join((resp.choices[0].message.content or "").split())
        return terms or question
    except Exception:  # noqa: BLE001
        return question


def _build_context(candidates: list[dict]) -> str:
    """Eine Zeile pro Beschluss: id, Titel, Gremium, Datum, Ergebnis + Kern des
    Beschlusstexts. 450 Zeichen statt 200 und die Metadaten machen die Antworten
    spürbar konkreter — bei ~20 Kandidaten immer noch nur wenige Cent. Wenn der
    Aufrufer einen Vorlagen-Auszug (Sachverhalt/Begründung) beigelegt hat, kommt
    der mit — das ist das *Warum* hinter dem Beschluss. Der Tragweite-Score
    (RL-U16) wird als Hinweis angehängt, aber NUR an den Enden der Skala: „hoch"
    samt Begründung lässt die Antwort mit dem Folgenreichen führen, „gering"
    lässt sie Formalien (Berufungen, Kenntnisnahmen) überspringen — das
    Relevanz-Ranking selbst bleibt davon unberührt."""
    lines = []
    for c in candidates:
        meta = " · ".join(p for p in (c.get("committee"), c.get("session_date"), c.get("outcome")) if p)
        body = (c.get("summary") or c.get("beschluss") or "").strip()[:450]
        vorlage = (c.get("vorlage_excerpt") or "").strip()
        suffix = f" — Aus der Vorlage: {vorlage}" if vorlage else ""
        impact = c.get("impact")
        if impact is not None and impact >= 70:
            reason = (c.get("impact_reason") or "").strip()
            suffix += f" — Tragweite: hoch{f' ({reason})' if reason else ''}"
        elif impact is not None and impact <= 15:
            suffix += " — Tragweite: gering (Formalie)"
        lines.append(f"[{c['id']}] {(c.get('title') or '').strip()} ({meta}): {body}{suffix}")
    return "\n".join(lines) or "(keine passenden Beschlüsse gefunden)"


def _answer_messages(question: str, candidates: list[dict]) -> tuple[list[dict], dict]:
    prompt = prompts.render("qa_antwort", question=question.strip()[:300], context=_build_context(candidates))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in MODEL else {}
    return [{"role": "user", "content": prompt}], extra


def answer_question(question: str, candidates: list[dict], model: str = MODEL):
    """Synthesise an answer from retrieved candidates. Returns ``(answer, cited_ids)``."""
    messages, extra = _answer_messages(question, candidates)
    resp = llm.chat_complete(model=model, _feature="qa_antwort", temperature=0.2, max_tokens=600, messages=messages, **extra)
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


def answer_stream(question: str, candidates: list[dict], model: str = MODEL):
    """Stream the answer text deltas (same prompt/context as answer_question) so the
    UI can render the answer as it is written. Citation resolution is the caller's
    job once the full text is assembled (see resolve_citations)."""
    messages, extra = _answer_messages(question, candidates)
    yield from llm.chat_stream(model=model, _feature="qa_antwort", temperature=0.2, max_tokens=600, messages=messages, **extra)


# --- Folgefragen (Design 24a / RL-U06) --------------------------------------
# Das Antwort-LLM hängt seine Vorschläge als letzte Zeile an (siehe Prompt
# „qa_antwort"). Der Marker trennt sie vom Antworttext — der Router streamt
# alles davor als Token und schneidet ab hier ab.
FOLLOWUP_MARKER = "FOLGEFRAGEN:"
_MAX_FOLLOWUPS = 3
_MAX_FOLLOWUP_LEN = 90


def split_followups(text: str) -> tuple[str, list[str]]:
    """Antworttext und die vom Modell angehängten Folgefragen trennen.

    Robust gegen ein Modell, das den Marker weglässt oder kaputtes JSON liefert:
    dann kommt die Antwort unverändert zurück und die Fragenliste ist leer (der
    Aufrufer nimmt dann den deterministischen Fallback).
    """
    idx = text.find(FOLLOWUP_MARKER)
    if idx == -1:
        return text.strip(), []
    answer = text[:idx].strip()
    tail = text[idx + len(FOLLOWUP_MARKER):].strip()
    questions: list[str] = []
    try:
        start, end = tail.find("["), tail.rfind("]")
        if start != -1 and end > start:
            for item in json.loads(tail[start:end + 1]):
                q = str(item).strip()
                if q and len(q) <= _MAX_FOLLOWUP_LEN and q not in questions:
                    questions.append(q)
    except (ValueError, TypeError):
        pass
    if not questions:
        # Kein (brauchbares) JSON — zeilenweise als Notnagel (»- Frage?«).
        for line in tail.splitlines():
            q = line.strip().lstrip("-•*\" ").rstrip("\",")
            if q.endswith("?") and len(q) <= _MAX_FOLLOWUP_LEN and q not in questions:
                questions.append(q)
    return answer, questions[:_MAX_FOLLOWUPS]


def fallback_followups(candidates: list[dict]) -> list[str]:
    """Variante B: Folgefragen ohne LLM aus den gefundenen Beschlüssen ableiten.

    Greift, wenn das Modell keine brauchbare Liste geliefert hat. Per
    Konstruktion sackgassenfrei — jede Frage zielt auf etwas, das im gefundenen
    Bestand nachweislich vorkommt.
    """
    from .topics import POLICY_FIELDS

    out: list[str] = []

    def add(q: str) -> None:
        if q not in out and len(out) < _MAX_FOLLOWUPS:
            out.append(q)

    # 1) Umstritten? Dann ist die Abstimmung die naheliegendste Anschlussfrage.
    for c in candidates:
        if (c.get("gegenstimmen") or 0) > 0 and (c.get("title") or "").strip():
            add(f"Wer stimmte gegen {_short_subject(c['title'])}?")
            break
    # 2) Themenfeld des Treffers — führt zu benachbarten Beschlüssen.
    for c in candidates:
        label = POLICY_FIELDS.get(c.get("policy_field") or "", ("",))[0]
        if label:
            add(f"Was wurde zuletzt zum Thema {label} beschlossen?")
            break
    # 3) Geld — nur wenn im Bestand tatsächlich ein Betrag steht.
    for c in candidates:
        if c.get("amount_eur"):
            label = POLICY_FIELDS.get(c.get("policy_field") or "", ("",))[0]
            add(f"Welche Beträge beschloss der Rat für {label or 'dieses Vorhaben'}?"
                if label else "Welche größeren Beträge hat der Rat zuletzt beschlossen?")
            break
    # 4) Gremium als letzter Auffüller.
    for c in candidates:
        if (c.get("committee") or "").strip():
            add(f"Was hat der {c['committee']} zuletzt entschieden?")
            break
    return out


def _short_subject(title: str) -> str:
    """Titel auf ein zitierfähiges Subjekt kürzen (vor dem ersten Gedankenstrich/
    Doppelpunkt), damit die Frage nicht zur Bandwurmzeile wird."""
    t = re.split(r"\s+[—–-]\s+|:\s+", title.strip())[0].strip()
    return (t[:60].rstrip() + "…") if len(t) > 60 else t


def resolve_citations(answer: str, valid: set[int]):
    """Parse `[id]` / `[id, id, …]` citations → ``(cleaned_answer, cited_ids)``.
    Keeps only ids we actually retrieved (``valid``), preserving order, and strips
    any invalid citation numbers from the text so no dangling [N] is shown."""
    cited: list[int] = []
    for group in re.findall(r"\[([\d,\s]+)\]", answer):
        for num in re.findall(r"\d+", group):
            v = int(num)
            if v in valid and v not in cited:
                cited.append(v)

    def _clean(m: "re.Match") -> str:
        nums = [n for n in re.findall(r"\d+", m.group(1)) if int(n) in valid]
        return f" [{', '.join(nums)}]" if nums else ""

    cleaned = re.sub(r"\s*\[([\d,\s]+)\]", _clean, answer).strip()
    return cleaned, cited
