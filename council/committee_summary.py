from __future__ import annotations

import json
import os

from kern import llm, prompts
from .scraper import AgendaItem

# Erzeugt die TOP-Kurzfassungen (agenda_item_summaries) — die Textsorte mit
# dem höchsten Halluzinationsrisiko im System, denn das Modell sieht nur
# Titel. Per Env tauschbar, seit 28.08.26 Standard: gpt-5.6-luna (nüchterner
# und aktueller als das zwei Jahre alte 4o-mini; Vergleich in council/impact.py).
MODEL = os.environ.get("COUNCIL_COMMITTEE_MODEL", "openai/gpt-5.6-luna")


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


def summarize_agenda_items(
    committee: str,
    session_date: str,
    agenda_items: list[AgendaItem],
) -> list[dict] | None:
    """Die inhaltlichen TOPs als [{"number", "summary"}] — die strukturierte
    Fassung hinter {@link summarize_agenda}.

    Die App zeigt dieselben Sätze unter den Tagesordnungspunkten (Tims Wunsch
    12.08.), deshalb liegen sie jetzt als Daten vor und nicht mehr nur als
    fertige Mail-Zeilen. Leere Liste = nur Routine (cachebar), None = LLM
    unbrauchbar (nicht cachen)."""
    return _analyse(committee, session_date, agenda_items)


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
    punkte = _analyse(committee, session_date, agenda_items)
    if punkte is None:
        return None
    if not punkte:
        return ""
    return "\n".join(
        f"• <b>{_esc(str(p.get('number', '')))}</b>: {_esc(str(p.get('summary', '')))}"
        for p in punkte)


# Ab hier wird eine Tagesordnung in Häppchen zerlegt. Grund: Eine Ratssitzung
# mit 49 öffentlichen TOPs sprengte die Antwort (gemessen am 29.06.2026:
# finish_reason=length, JSON mitten im Satz abgeschnitten → gar keine
# Zusammenfassung). Kleinere Häppchen halten jede Antwort sicher im Rahmen.
_MAX_TOPS_PRO_LAUF = 20


def _budget(anzahl: int) -> int:
    """Token-Budget nach Anzahl der Punkte — ein Satz je TOP braucht Platz."""
    return min(4000, 400 + 130 * anzahl)


def _analyse(committee: str, session_date: str,
             agenda_items: list[AgendaItem]) -> list[dict] | None:
    if not agenda_items:
        return []

    _fragestunde_keywords = ("einwohnerfragestunde", "bürgerfragestunde", "fragestunde")
    relevant = [i for i in agenda_items
                if i.is_public and not any(kw in i.title.lower() for kw in _fragestunde_keywords)]
    if not relevant:
        return []

    # Große Tagesordnungen in Tranchen: Jede Teil-Antwort bleibt klein genug,
    # um vollständig zu sein. Scheitert EINE Tranche, gilt die ganze Sitzung
    # als unbrauchbar (None) — eine Mail mit stillschweigend fehlenden Punkten
    # wäre schlimmer als eine ohne Zusammenfassung.
    if len(relevant) > _MAX_TOPS_PRO_LAUF:
        alle: list[dict] = []
        for start in range(0, len(relevant), _MAX_TOPS_PRO_LAUF):
            teil = _analyse(committee, session_date, relevant[start:start + _MAX_TOPS_PRO_LAUF])
            if teil is None:
                return None
            alle.extend(teil)
        gesehen = set()
        return [p for p in alle if not (p["number"] in gesehen or gesehen.add(p["number"]))]

    items_text = "\n".join(
        f"{i.item_number}: {i.title}" + (f" [{i.vorlage_nr}]" if i.vorlage_nr else "")
        for i in relevant
    )
    if not items_text.strip():
        return []

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
            max_tokens=_budget(len(relevant)),
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
        return []

    # Nur Punkte, die es wirklich gibt: Das Modell erfindet gelegentlich eine
    # Nummer (siehe die Verifizierung im Watcher, #438) — hier reicht der
    # Abgleich gegen die echten Nummern.
    echte = {" ".join(str(i.item_number).split()).upper() for i in relevant}
    punkte: list[dict] = []
    for item in data["items"]:
        nummer = " ".join(str(item.get("number", "")).split()).upper()
        text = " ".join(str(item.get("summary", "")).split())
        if nummer in echte and text:
            punkte.append({"number": nummer, "summary": text})
    return punkte
