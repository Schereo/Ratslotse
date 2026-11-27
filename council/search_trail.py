"""The search trail of a question: what "Frag den Rat" is doing, step by step.

Until 11/2026 the ask stream reported three bare phases (``expand → search →
answer``) and the page showed one line for the current one. Potsdam's council
chatbot (risbot.potsdam.de) lists every step with its result — "Suche:
„Fahrradwege“ ↳ 12 Drucksachen gefunden" — and Tim wanted the same: the person
waiting sees what is being searched and what came back, not a spinner.

The texts are built HERE, not in the clients: both the web and the iOS app
show them as they arrive, and a new step needs no client release.

Wire format (still the ``step`` frame, so older clients keep working — they
read ``step`` and ignore the rest):

* ``{"type": "step", "step": <phase>, "text": "…"}`` starts a new entry.
* ``{"type": "step", "step": <phase>, "detail": "…"}`` is the result line of
  the entry started last.

``step`` stays one of the three phases; the entry text says what happens
within it. Texts are infinitives ("Beschlüsse durchsuchen"), like the progress
card of the long research: they read right both while running and when done.
"""
from __future__ import annotations

from typing import Any

#: How many titles a "found" line names before "und N weitere".
TITLES_SHOWN = 2
#: Characters per title in a "found" line — the line is one row on a phone.
TITLE_MAX = 50
#: Search terms shown after the analysis.
TERMS_SHOWN = 6


def start(phase: str, text: str) -> dict[str, Any]:
    """Frame that opens a new entry of the trail."""
    return {"type": "step", "step": phase, "text": text}


def result(phase: str, detail: str) -> dict[str, Any]:
    """Frame with the result line of the entry opened last."""
    return {"type": "step", "step": phase, "detail": detail}


def _short(title: str, limit: int = TITLE_MAX) -> str:
    title = " ".join((title or "").split())
    if len(title) <= limit:
        return title
    cut = title[:limit].rsplit(" ", 1)[0] or title[:limit]
    return cut.rstrip(" ,;:–-") + " …"


def _german_date(iso: str | None) -> str:
    """``2026-11-24`` → ``24.11.2026``; anything else unchanged."""
    if iso and len(iso) >= 10 and iso[4] == "-" and iso[7] == "-":
        return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}"
    return iso or ""


def count(n: int, singular: str, plural: str) -> str:
    """``1 Wortbeitrag`` / ``12 Wortbeiträge`` / ``keine Wortbeiträge``."""
    if n == 0:
        return f"keine {plural}"
    return f"{n} {singular if n == 1 else plural}"


def analysis_detail(*, terms: str, question: str, place: dict | None = None,
                    person: dict | None = None, sessions: list[dict] | None = None,
                    party: str | None = None, procedure: bool = False) -> str | None:
    """What the analysis made of the question, as one line.

    The search terms only when the analysis produced its own: on a provider
    error ``terms`` falls back to the question itself, and repeating the
    question word by word says nothing.
    """
    parts: list[str] = []
    words = (terms or "").split()
    if words and " ".join(words) != " ".join((question or "").split()):
        parts.append("Suchbegriffe: " + ", ".join(dict.fromkeys(words[:TERMS_SHOWN])))
    if place and place.get("name"):
        parts.append(f"Ort: {place['name']}")
    if person and person.get("name"):
        parts.append(f"Person: {person['name']}")
    if party:
        parts.append(f"Fraktion: {party}")
    for s in (sessions or [])[:2]:
        label = " ".join(x for x in (s.get("committee"), _german_date(s.get("session_date"))) if x)
        if label:
            parts.append(f"Sitzung: {label}")
    if procedure:
        parts.append("Geschäftsordnung")
    return " · ".join(parts) or None


def found_detail(decisions: list[dict]) -> str:
    """``12 Beschlüsse gefunden: A · B · C und 9 weitere``."""
    n = len(decisions)
    if n == 0:
        return "Keine passenden Beschlüsse gefunden"
    titles = [_short(d.get("title") or "") for d in decisions[:TITLES_SHOWN]]
    titles = [t for t in titles if t]
    head = f"{count(n, 'Beschluss', 'Beschlüsse')} gefunden"
    if not titles:
        return head
    rest = n - len(titles)
    return f"{head}: {' · '.join(titles)}" + (f" und {rest} weitere" if rest > 0 else "")


def follow_up_detail(queries: list[str], added: int) -> str:
    """Result of the follow-up search (switch ``nachrecherche``).

    The number first: on a phone the line is cut after three rows, and the
    queries are what may go.
    """
    if not queries:
        return "Keine Lücke gefunden"
    asked = ", ".join(f"„{q}“" for q in queries)
    found = (count(added, "weiterer Beschluss", "weitere Beschlüsse") if added
             else "Nichts Neues")
    return f"{found} · nachgesucht: {asked}"


def dossier_detail(decisions: int, speeches: int) -> str:
    """What the dossier (switch ``akten-suche``) added beyond the search."""
    parts = [count(decisions, "weiterer Beschluss", "weitere Beschlüsse") if decisions else "",
             count(speeches, "weiterer Wortbeitrag", "weitere Wortbeiträge") if speeches else ""]
    return " · ".join(p for p in parts if p) or "Nichts Neues dazu"


def search_text(*, latest_place: bool, overview: bool, place: dict | None) -> str:
    """Entry text of the main search — it differs by how candidates are chosen."""
    name = (place or {}).get("name")
    if latest_place and name:
        return f"Neueste Beschlüsse zu {name} laden"
    if overview and name:
        return f"Beschlüsse zu {name} sichten"
    return "Beschlüsse durchsuchen"
