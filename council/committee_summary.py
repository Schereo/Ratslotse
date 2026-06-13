from __future__ import annotations

import json
import os
import textwrap

from openai import OpenAI

from .scraper import AgendaItem

MODEL = "gpt-4o"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def summarize_agenda(
    committee: str,
    session_date: str,
    session_time: str,
    location: str,
    agenda_items: list[AgendaItem],
    session_url: str,
) -> str:
    """Return Telegram HTML summary of a committee session, or '' if only routine items."""
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

    system = textwrap.dedent("""\
        Du analysierst Tagesordnungen (TOPs) von Ausschusssitzungen der Stadt Oldenburg.
        Filtere Routine-TOPs heraus: Genehmigung der Tagesordnung, Protokollgenehmigung,
        Mitteilungen, Anfragen, Bekanntgaben, Verschiedenes und sonstige Formalia.
        Ignoriere außerdem Tagesordnungspunkte die 'Einwohnerfragestunde', 'Bürgerfragestunde'
        oder ähnliche Bürgerbeteiligungs-Formate betreffen — diese sind Routine und nicht zusammenfassungsrelevant.
        Fasse die verbleibenden inhaltlichen TOPs jeweils in 1-2 Sätzen zusammen.
        Antworte ausschließlich als JSON.
    """)

    prompt = textwrap.dedent(f"""\
        Ausschuss: {committee}
        Tagesordnungspunkte:
        {items_text}

        Format:
        {{
          "has_content": true,
          "items": [
            {{"number": "Ö 5", "summary": "Kurze Zusammenfassung in 1-2 Sätzen."}},
            ...
          ]
        }}
        Gib has_content: false zurück, wenn nur Routine-TOPs übrig bleiben.
    """)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
    )
    data = json.loads(resp.choices[0].message.content)

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
