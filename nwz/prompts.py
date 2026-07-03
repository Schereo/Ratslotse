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

            RELEVANZREGELN:
            - Nur TOPs aufnehmen, die das Nutzerthema *konkret* betreffen.
            - Niemals zuordnen: Beschlussfähigkeit, Tagesordnung/Protokoll genehmigen,
              Einwohnerfragestunde, Anfragen, Berichte ohne inhaltlichen Bezug.
            - "Annahme von Zuwendungen" ist Routine-Finanzadministration — kein
              Wirtschafts- oder Handelsbezug.
            - Haushaltsmittel für Infrastruktur (z. B. "Sondervermögen Straßensanierung")
              gehören zum Infrastruktur-Thema (Verkehr), nicht zu allgemeinen Finanzthemen.
            - Wenn Unter-TOPs (z. B. Ö 5.1, Ö 5.2) einem Thema zugeordnet werden,
              auch den übergeordneten TOP (z. B. Ö 5) aufnehmen.

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
    "qa_suchbegriffe": {
        "title": "Frag den Rat – Suchbegriffe",
        "description": "Übersetzt die Nutzerfrage in Suchbegriffe für die semantische Beschluss-Suche.",
        "template": (
            "Wandle die Frage in 4–8 deutsche Suchbegriffe um (Substantive und nahe Synonyme "
            "zum Thema) für eine semantische Suche in Stadtrats-Beschlüssen. KEINE Floskeln wie "
            '"Was wurde", "beschlossen", "Stadtrat". Nur die Begriffe, durch Leerzeichen getrennt.\n\n'
            "FRAGE: {question}\n"
            "SUCHBEGRIFFE:"
        ),
    },
    "recap_themenfeld": {
        "title": "Themenfeld-Rückblick",
        "description": "Wöchentliche Kurzfassung je Themenfeld: eine Kernaussage + Stichpunkte. Platzhalter: {field}, {items}.",
        "template": (
            "Du schreibst einen kurzen, neutralen Rückblick für die Bürger:innen Oldenburgs:\n"
            "Was hat den Stadtrat im Themenfeld „{field}“ zuletzt beschäftigt?\n\n"
            "Hier die jüngsten Beschlüsse/Berichte in diesem Feld (neueste zuerst):\n"
            "{items}\n\n"
            "Antworte in GENAU diesem Format (kein Markdown außer den Spiegelstrichen):\n"
            "Zeile 1: die EINE Kernaussage des Feldes — ein prägnanter Satz, max. 90 Zeichen, ohne Einleitung.\n"
            'Danach 3 bis 4 Zeilen, jede beginnt mit "- ": je EIN konkreter Punkt '
            "(Vorhaben, Ort, Entscheidung mit Ergebnis), max. 140 Zeichen pro Punkt.\n\n"
            "Regeln:\n"
            "- Nenne konkrete Vorhaben/Orte/Zahlen, wenn sie in den Einträgen vorkommen.\n"
            "- Neutral und sachlich: keine Wertung, keine Partei-Bewertung, keine Empfehlungen.\n"
            "- Erfinde nichts; stütze dich ausschließlich auf die vorgelegten Einträge."
        ),
    },
    "qa_antwort": {
        "title": "Frag den Rat – Antwort",
        "description": "Formuliert die Antwort ausschließlich aus den gefundenen Beschlüssen, mit [id]-Zitaten.",
        "template": (
            "Beantworte die Frage NUR anhand der folgenden Beschlüsse des Oldenburger Stadtrats.\n"
            "Wenn die Beschlüsse die Frage nicht beantworten, sage das ehrlich und rate nicht.\n"
            "Zitiere jeden genutzten Beschluss mit seiner id in eckigen Klammern, z. B. [123].\n"
            "Passen mehrere Beschlüsse, nenne die neuesten zuerst und gib ihr Datum an.\n\n"
            "FRAGE: {question}\n\n"
            "BESCHLÜSSE:\n"
            "{context}\n\n"
            "Antworte knapp (2–5 Sätze) auf Deutsch, mit id-Zitaten."
        ),
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


def validate_template(key: str, content: str) -> str | None:
    """Validate a prompt template. Returns an error message or None if valid.

    Checks for syntax errors and for placeholder names not present in the
    original default (those would cause a KeyError at runtime when the bot
    calls ``render()``).
    """
    import string as _string

    try:
        fields = [(name, fmt) for _, name, fmt, _ in _string.Formatter().parse(content) if name is not None]
    except ValueError as e:
        return f"Syntaxfehler im Template: {e}"

    if key in DEFAULTS:
        default_template = DEFAULTS[key]["template"]
        try:
            expected = {name for _, name, _, _ in _string.Formatter().parse(default_template) if name is not None}
        except ValueError:
            expected = set()
        new_fields = {name for name, _ in fields if name and name not in expected}
        if new_fields:
            sorted_expected = ", ".join(sorted(expected)) or "(keine)"
            return (
                f"Unbekannte Platzhalter: {{{', '.join(sorted(new_fields))}}}. "
                f"Erlaubt: {sorted_expected}."
            )

    dummy = {name: "BEISPIEL" for name, _ in fields if name}
    try:
        content.format(**dummy)
    except (KeyError, ValueError, IndexError) as e:
        return f"Template-Fehler beim Ausfüllen: {e}"

    return None
