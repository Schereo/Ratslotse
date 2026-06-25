"""Question answering over council decisions ("Frag den Stadtrat").

Retrieval is keyword-based (German nouns from the question), then the LLM answers
*only* from the retrieved decisions and cites them by id. Honest by construction:
if the retrieved decisions don't answer the question, the model says so. Semantic
embedding retrieval is the planned upgrade (see council-ai-roadmap).
"""
from __future__ import annotations

import os
import re

from nwz import llm
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


_PROMPT = """Beantworte die Frage NUR anhand der folgenden Beschlüsse des Oldenburger Stadtrats.
Wenn die Beschlüsse die Frage nicht beantworten, sage das ehrlich und rate nicht.
Zitiere jeden genutzten Beschluss mit seiner id in eckigen Klammern, z. B. [123].

FRAGE: {question}

BESCHLÜSSE:
{context}

Antworte knapp (2–5 Sätze) auf Deutsch, mit id-Zitaten."""


def answer_question(question: str, candidates: list[dict], model: str = MODEL):
    """Synthesise an answer from retrieved candidates. Returns ``(answer, cited_ids)``."""
    context = "\n".join(
        f"[{c['id']}] {(c.get('title') or '').strip()} ({c.get('session_date')}): "
        f"{(c.get('summary') or c.get('beschluss') or '').strip()[:200]}"
        for c in candidates
    ) or "(keine passenden Beschlüsse gefunden)"
    prompt = _PROMPT.format(question=question.strip()[:300], context=context)
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    resp = llm.chat_complete(
        model=model, temperature=0.2, max_tokens=600,
        messages=[{"role": "user", "content": prompt}], **extra,
    )
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


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
