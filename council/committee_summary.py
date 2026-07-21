from __future__ import annotations

import json

from nwz import llm, prompts
from .scraper import AgendaItem

MODEL = "openai/gpt-4o-mini"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def summarize_agenda(
    committee: str,
    session_date: str,
    session_time: str,
    location: str,
    agenda_items: list[AgendaItem],
    session_url: str,
) -> str | None:
    """Return HTML summary of a committee session, or '' if only routine items.

    Returns ``None`` when the LLM response could not be parsed (auch nach
    Retry) — der Aufrufer schickt dann eine Benachrichtigung ohne
    Zusammenfassung und darf das Ergebnis NICHT cachen, damit der nächste
    Lauf es erneut versucht ('' dagegen ist ein gültiger Cache-Treffer).
    """
    if not agenda_items:
        return ""

    _fragestunde_keywords = ("einwohnerfragestunde", "bürgerfragestunde", "fragestunde")

    items_text = "\n".join(
        f"{i.item_number}: {i.title}" + (f" [{i.vorlage_nr}]" if i.vorlage_nr else "")
        for i in agenda_items
        if i.is_public and not any(kw in i.title.lower() for kw in _fragestunde_keywords)
    )
    if not items_text.strip():
        return ""

    system = prompts.get("committee_summary_system")
    prompt = prompts.render("committee_summary_user", committee=committee, items_text=items_text)

    # Trotz response_format=json_object liefern Modelle vereinzelt kein valides
    # JSON (leerer Content, Markdown-Zaun, Prosa) — das crashte den ganzen
    # Cron-Lauf. Daher: Zaun abstreifen + ein frischer Versuch, sonst None.
    data: dict | None = None
    for _attempt in range(2):
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            _feature="committee_summary",
        )
        content = (resp.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content[content.find("{"):]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            data = parsed
            break
    if data is None:
        print(f"  committee_summary: kein valides JSON für {committee} am {session_date} "
              f"— Benachrichtigung geht ohne Zusammenfassung raus")
        return None

    if not data.get("has_content") or not data.get("items"):
        return ""

    # Format date as DD.MM.YYYY
    date_parts = session_date.split("-")
    if len(date_parts) == 3:
        display_date = f"{date_parts[2]}.{date_parts[1]}.{date_parts[0]}"
    else:
        display_date = session_date

    lines = [
        f"<b>{_esc(committee)}</b>",
        f"📅 {display_date}  {session_time} Uhr",
        f"📍 {_esc(location)}",
        "",
    ]
    for item in data["items"]:
        number = _esc(str(item.get("number", "")))
        summary = _esc(str(item.get("summary", "")))
        lines.append(f"• <b>{number}</b>: {summary}")

    lines.append("")
    lines.append(f'<a href="{session_url}">Vollständige Tagesordnung →</a>')
    return "\n".join(lines)
