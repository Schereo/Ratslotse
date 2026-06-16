"""Admin-editable prompt store.

All LLM prompts used by the bot and the cron jobs live here as named templates
with sensible defaults. An admin can override any of them at runtime via the web
frontend; overrides are persisted in the ``prompts`` table of ``nwz.sqlite`` and
take effect on the next call (no restart needed).

Templates use ``str.format()`` placeholders. Literal braces (e.g. in JSON
examples) must be escaped as ``{{`` / ``}}``.
"""
from __future__ import annotations

import sqlite3
import textwrap
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nwz.sqlite"

# --- Default prompt templates -------------------------------------------------
# Each entry: key -> (title, description, template). Title/description are shown
# in the admin UI. The template is what the model receives after .format().

DEFAULTS: dict[str, dict[str, str]] = {
    "nwz_digest_system": {
        "title": "NWZ-Digest – System",
        "description": "Rolle des Modells beim täglichen Abgleich von Artikeln mit Themen. Platzhalter: {pub_date}.",
        "template": textwrap.dedent("""\
            Du bist ein Redaktionsassistent, der Zeitungsartikel der Nordwest-Zeitung (NWZ)
            nach thematischen Interessen des Lesers filtert und zusammenfasst.
            Ausgabe: kompaktes Deutsch, präzise, ohne Floskeln.
            Heute: {pub_date}.
        """),
    },
    "nwz_digest_user": {
        "title": "NWZ-Digest – Aufgabe",
        "description": (
            "Die eigentliche Klassifizierungs-Aufgabe inkl. Relevanzkriterien und JSON-Format. "
            "Platzhalter: {topics_list}, {context_block}, {pub_date}, {articles_block}, {continuation_instruction}."
        ),
        "template": textwrap.dedent("""\
            Hier sind die Themen des Lesers:
            {topics_list}

            {context_block}Und hier die Artikel der NWZ-Ausgabe ({pub_date}):

            {articles_block}

            Aufgabe:
            Für jedes Thema: finde passende Artikel (0–5 Stück).

            STRENGES Relevanzkriterium — ein Artikel passt NUR, wenn er das Thema
            konkret behandelt ODER eine konkrete, faktische Information zum Thema
            liefert (z. B. das Abstimmungsverhalten, eine Aussage oder Handlung
            einer genannten Partei/Person). Das Thema muss NICHT der Hauptgegenstand
            des Artikels sein — eine beiläufige, aber konkrete Nennung des im Thema
            verfolgten Akteurs (z. B. "Volt stimmte dafür") genügt. Der Bezug muss
            explizit im Artikeltext stehen, nicht erschlossen oder vermutet werden.

            Ein Artikel passt NICHT, wenn:
            - er nur THEMATISCH VERWANDT ist (z. B. allgemein Kultur/Politik/Sport
              in Oldenburg), das konkrete Thema aber nicht behandelt;
            - der Bezug nur SPEKULATIV ist ("könnte für X interessant sein",
              "X könnte sich damit beschäftigen", "illustriert Engagement, das
              politisch relevant sein könnte"). Solche Vermutungen sind verboten;
            - es sich nur um eine STICHWORT-Überschneidung handelt (z. B. das Wort
              "grün") oder um einen bundesweiten Bezug, obwohl das Thema einen
              lokalen Bezug (Oldenburg) verlangt;
            - das Thema eine Organisation/Partei/Person ist und diese im Artikel
              gar nicht VORKOMMT — eine bloße inhaltliche Nähe genügt nicht.

            Im Zweifel: NICHT aufnehmen. Lieber kein Treffer als ein falscher.
            Die Zusammenfassung muss belegen, WO im Artikel das Thema vorkommt;
            wenn du das nicht ohne Spekulation kannst, ist es kein Treffer.
            Schreibe keine Zusammenfassung für Themen ohne passende Artikel.
            {continuation_instruction}Gib die Antwort als JSON zurück:

            {{
              "digest": [
                {{
                  "topic": "Themenname",
                  "articles": [
                    {{
                      "refid": "...",
                      "title": "...",
                      "summary": "1–2 Sätze auf Deutsch",
                      "is_continuation": false
                    }}
                  ]
                }}
              ]
            }}

            Nur JSON, kein weiterer Text.
        """),
    },
    "nwz_verify_system": {
        "title": "NWZ-Verifikation (2. Pass)",
        "description": "Günstiger Einzelcheck pro (Thema, Artikel)-Paar, der False Positives aus dem ersten Pass aussortiert.",
        "template": (
            "Du prüfst, ob ein Zeitungsartikel eine konkrete, faktische Information zum "
            "angegebenen Thema enthält. RELEVANT ist ein Artikel, wenn er das Thema behandelt "
            "ODER eine konkrete Tatsache zum verfolgten Akteur liefert — z.B. wie eine Partei/"
            "Person abgestimmt hat, was sie gesagt oder getan hat. Das Thema muss NICHT der "
            "zentrale Gegenstand sein; eine beiläufige, aber konkrete Nennung (z.B. die Partei "
            "in einer Abstimmungsliste) genügt und ist relevant. "
            "NICHT relevant ist: bloße Stichwort-Überschneidung (z.B. das Wort 'grün'), reine "
            "thematische Verwandtschaft ohne Nennung des Akteurs, oder ein bundesweiter Bezug, "
            "obwohl das Thema einen lokalen Bezug (Oldenburg) verlangt. "
            "Beachte die Themen-Beschreibung: erfüllt sie einen geforderten lokalen/konkreten "
            'Bezug? Antworte nur als JSON: {"relevant": true/false}.'
        ),
    },
    "weekly_highlights_system": {
        "title": "Wochenrückblick – System",
        "description": "Rolle des Modells beim wöchentlichen Highlights-Ranking.",
        "template": "Du bist ein politischer Redakteur für Oldenburger Lokalpolitik.",
    },
    "weekly_highlights_user": {
        "title": "Wochenrückblick – Aufgabe",
        "description": "Auswahl der wichtigsten Artikel der Woche. Platzhalter: {date_from}, {date_to}, {articles_block}.",
        "template": textwrap.dedent("""\
            Hier sind alle Artikel der NWZ-Ausgaben der Woche ({date_from} bis {date_to}):

            {articles_block}

            Wähle die 3–5 Artikel, die für die Oldenburger Lokalpolitik diese Woche am bedeutsamsten waren. Begründe in einem knappen Satz, warum jeder wichtig ist.

            Ausgabe als JSON:
            {{
              "highlights": [
                {{"title": "...", "reason": "1 Satz"}}
              ]
            }}

            Nur JSON, kein weiterer Text.
        """),
    },
    "vagueness_check_system": {
        "title": "Vagheits-Prüfung bei neuem Thema",
        "description": "Prüft, ob eine Themen-Beschreibung präzise genug ist, und schlägt eine bessere vor.",
        "template": (
            "Du prüfst ob eine Themen-Beschreibung für einen Nachrichten-Bot präzise genug ist, "
            "um zuverlässig NUR die wirklich gewünschten Artikel (aus einer Lokalzeitung für "
            "Oldenburg) herauszufiltern. Sei streng: im Zweifel ist die Beschreibung zu vage.\n"
            "Eine Beschreibung ist zu vage wenn sie:\n"
            "- allgemeine Absichten statt konkreter Inhalte beschreibt (z.B. 'interessante Themen', 'etwas Spannendes')\n"
            "- keine eingrenzbaren Kriterien enthält\n"
            "- so breit ist, dass viele themenfremde Artikel matchen würden\n"
            "- eine Partei, Organisation, Person oder Institution nennt, OHNE den Bezug klar "
            "einzugrenzen: Es muss ausdrücklich auf Oldenburg/lokal beschränkt sein UND klarstellen, "
            "was NICHT gemeint ist (z.B. keine bundesweiten Partei-/Politiknews). 'Die Grünen – Partei "
            "in Oldenburg' ist z.B. ZU VAGE, weil dadurch auch bundesweite Grünen-Nachrichten matchen.\n"
            "- ein breites Schlagwort ohne konkrete Akteure/Vorhaben/Orte nutzt "
            "(z.B. 'Kommunalwahl in Oldenburg' ohne Eingrenzung auf Kandidaten, Listen, Termine, Ergebnisse)\n\n"
            "Antworte NUR mit einem JSON-Objekt: "
            '{"vague": true/false, "hint": "...", "suggestion": "..."}.\n'
            "- hint: kurze Erklärung auf Deutsch, warum die Beschreibung zu vage ist (max. 2 Sätze). Leer wenn nicht vage.\n"
            "- suggestion: eine konkrete, sofort verwendbare präzisere Beschreibung (1 Satz), die den erkennbaren "
            "Wunsch des Nutzers aufgreift und sinnvoll eingrenzt (z.B. Ortsbezug Oldenburg, konkrete Akteure/Vorhaben, "
            "Ausschluss themenfremder Treffer). Leer wenn nicht vage."
        ),
    },
    "committee_summary_system": {
        "title": "Ausschuss-Zusammenfassung – System",
        "description": "Filtert Routine-TOPs und fasst inhaltliche Tagesordnungspunkte zusammen.",
        "template": textwrap.dedent("""\
            Du analysierst Tagesordnungen (TOPs) von Ausschusssitzungen der Stadt Oldenburg.
            Filtere Routine-TOPs heraus: Genehmigung der Tagesordnung, Protokollgenehmigung,
            Mitteilungen, Anfragen, Bekanntgaben, Verschiedenes und sonstige Formalia.
            Ignoriere außerdem Tagesordnungspunkte die 'Einwohnerfragestunde', 'Bürgerfragestunde'
            oder ähnliche Bürgerbeteiligungs-Formate betreffen — diese sind Routine und nicht zusammenfassungsrelevant.
            Fasse die verbleibenden inhaltlichen TOPs jeweils in 1-2 Sätzen zusammen.
            Antworte ausschließlich als JSON.
        """),
    },
    "committee_summary_user": {
        "title": "Ausschuss-Zusammenfassung – Aufgabe",
        "description": "Tagesordnung + JSON-Format. Platzhalter: {committee}, {items_text}.",
        "template": textwrap.dedent("""\
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
        """),
    },
    "council_watcher_system": {
        "title": "Stadtrat-Watcher – System",
        "description": "Ordnet Tagesordnungspunkte den Interessengebieten der Nutzer zu.",
        "template": textwrap.dedent("""\
            Du analysierst Tagesordnungspunkte (TOP) der Oldenburger Stadtratssitzungen
            und ordnest sie den Interessengebieten des Nutzers zu.
            Antworte ausschließlich als JSON.
        """),
    },
    "council_watcher_user": {
        "title": "Stadtrat-Watcher – Aufgabe",
        "description": "TOP-Matching + JSON-Format. Platzhalter: {committee}, {session_date}, {items_text}, {topics_text}.",
        "template": textwrap.dedent("""\
            Sitzung: {committee}, {session_date}

            Öffentliche Tagesordnungspunkte:
            {items_text}

            Themen des Nutzers:
            {topics_text}

            Gib für jedes Thema an, welche TOP-Nummern passen (leer wenn keiner passt).
            Format:
            {{
              "matches": [
                {{"topic_index": 1, "item_numbers": ["Ö 6.1", "Ö 6.2"]}},
                {{"topic_index": 2, "item_numbers": []}}
              ]
            }}
        """),
    },
}


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS prompts (
               key        TEXT PRIMARY KEY,
               content    TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    conn.commit()
    return conn


def get(key: str) -> str:
    """Return the active template for ``key`` (admin override or default)."""
    if key not in DEFAULTS:
        raise KeyError(f"Unknown prompt key: {key}")
    try:
        conn = _connect()
        row = conn.execute("SELECT content FROM prompts WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row is not None:
            return row[0]
    except sqlite3.Error:
        pass
    return DEFAULTS[key]["template"]


def render(key: str, **kwargs) -> str:
    """Return the active template formatted with the given keyword arguments."""
    return get(key).format(**kwargs)


def is_overridden(key: str) -> bool:
    try:
        conn = _connect()
        row = conn.execute("SELECT 1 FROM prompts WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row is not None
    except sqlite3.Error:
        return False


def list_all() -> list[dict]:
    """Return every known prompt with its current and default content for the admin UI."""
    conn = _connect()
    overrides = {
        r["key"]: r["content"]
        for r in conn.execute("SELECT key, content FROM prompts").fetchall()
    }
    conn.close()
    result = []
    for key, meta in DEFAULTS.items():
        result.append(
            {
                "key": key,
                "title": meta["title"],
                "description": meta["description"],
                "default": meta["template"],
                "content": overrides.get(key, meta["template"]),
                "is_overridden": key in overrides,
            }
        )
    return result


def set_content(key: str, content: str) -> None:
    if key not in DEFAULTS:
        raise KeyError(f"Unknown prompt key: {key}")
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO prompts (key, content, updated_at) VALUES (?, ?, ?)",
            (key, content, now),
        )
    conn.close()


def reset(key: str) -> None:
    """Remove an override so the default takes effect again."""
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM prompts WHERE key = ?", (key,))
    conn.close()
