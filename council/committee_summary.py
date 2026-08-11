from __future__ import annotations

import json

from nwz import llm, prompts
from .scraper import AgendaItem

MODEL = "openai/gpt-4o-mini"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def datum_deutsch(session_date: str) -> str:
    """ISO-Datum als TT.MM.JJJJ; unbekannte Formate bleiben, wie sie sind."""
    teile = str(session_date or "").split("-")
    if len(teile) == 3:
        return f"{teile[2]}.{teile[1]}.{teile[0]}"
    return str(session_date or "")


def sitzungskopf(committee: str, session_date: str, session_time: str, location: str) -> str:
    """Gremium, Termin und Ort über der Zusammenfassung.

    Gehört zum Aufrufer und nicht in die gecachte Zusammenfassung (siehe
    ``summarize_agenda``). Die Ortszeile entfällt, solange kein Ort bekannt
    ist — eine Ortsmarke ohne Ort sagt weniger als gar keine.
    """
    zeilen = [f"<b>{_esc(committee)}</b>",
              f"📅 {datum_deutsch(session_date)}"
              + (f"  {_esc(session_time)} Uhr" if session_time else "")]
    if location:
        zeilen.append(f"📍 {_esc(location)}")
    return "\n".join(zeilen)


def summarize_agenda(
    committee: str,
    session_date: str,
    agenda_items: list[AgendaItem],
) -> str | None:
    """Die inhaltlichen Tagesordnungspunkte als Zeilen, oder '' bei nur Routine.

    Bewusst OHNE Kopfzeile (Gremium, Termin, Ort): Die Zusammenfassung wird pro
    Tagesordnung gecacht, der Kopf gehört aber zur Sitzung und ändert sich
    unabhängig davon. Als er hier drinsteckte, konservierte der Cache einen
    Kopf mit leerem Ort — die Mail zeigte eine Ortsmarke ohne Ort. Den Kopf
    baut jetzt der Aufrufer aus frischen Sitzungsdaten, wie schon den Link.

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
    prompt = prompts.render("committee_summary_user", committee=committee,
                            datum=datum_deutsch(session_date), items_text=items_text)

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

    lines = []
    for item in data["items"]:
        number = _esc(str(item.get("number", "")))
        summary = _esc(str(item.get("summary", "")))
        lines.append(f"• <b>{number}</b>: {summary}")

    # Bewusst OHNE Link: Wohin die Meldung führt, entscheidet der Aufrufer —
    # er kennt den Kanal (Mail-Knopf vs. Push-Pfad) und hängt Haupt- und
    # Nebenlink einheitlich an. Früher stand hier ein Ratsinfo-Link fest
    # verdrahtet, und die Zusammenfassung bestimmte damit die Navigation mit.
    return "\n".join(lines)
