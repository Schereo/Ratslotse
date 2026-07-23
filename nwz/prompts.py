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
            "In den Klammern steht AUSSCHLIESSLICH die Zahl — Datum, Tragweite oder sonstige\n"
            "Angaben gehören in den Satz, niemals in die Klammer.\n"
            "Passen mehrere Beschlüsse, nenne die neuesten zuerst und ihr Datum im Satztext.\n"
            "Ist eine Tragweite angegeben, führe mit den folgenreichen Beschlüssen (Tragweite: hoch)\n"
            "und behandle sie ausführlicher; Formalien (Tragweite: gering) erwähne nur, wenn die\n"
            "Frage direkt danach fragt.\n\n"
            "FRAGE: {question}\n\n"
            "BESCHLÜSSE:\n"
            "{context}\n\n"
            "Antworte knapp (2–5 Sätze) auf Deutsch, mit id-Zitaten.\n\n"
            "Hänge danach GENAU EINE letzte Zeile an, die so beginnt:\n"
            'FOLGEFRAGEN: ["…", "…", "…"]\n'
            "Darin 3 kurze Anschlussfragen (je max. 70 Zeichen), die sich aus den oben "
            "gefundenen Beschlüssen belegen lassen — nichts, wofür die Beschlüsse keine "
            "Grundlage geben. Jede Frage muss FÜR SICH verständlich sein (sie startet eine "
            "neue, eigenständige Suche ohne Kenntnis dieser Antwort): also keine Rückbezüge "
            "wie „dazu“, „dabei“ oder „dieser Beschluss“, sondern die Sache beim Namen nennen."
        ),
    },
    "simple_summary_system": {
        "title": "Einfach erklärt – System (RL-904)",
        "description": "Übersetzt einen Beschlusstext in 2–3 bürgernahe Sätze („Lotti erklärt's einfach“).",
        "template": (
            "Du erklärst Beschlüsse des Oldenburger Stadtrats in einfacher Sprache — für Menschen "
            "ohne Verwaltungs-Vorwissen.\n"
            "Regeln:\n"
            "- 2–3 kurze Sätze, aktiv formuliert, kein Konjunktiv, keine Floskeln.\n"
            "- Erkläre, WAS entschieden wurde und was es für die Stadt konkret bedeutet.\n"
            "- Erfinde NICHTS: keine Zahlen, Daten, Orte oder Folgen, die nicht im Text stehen.\n"
            "- Übersetze Fachbegriffe (z. B. 'Aufstellungsbeschluss' → 'die Stadt beginnt offiziell "
            "mit der Planung'), statt sie zu wiederholen.\n"
            "- Keine Bewertung, keine Meinung.\n"
            'Antworte NUR als JSON: {"einfach": "..."} — leerer String, wenn der Text keine '
            "verständliche Erklärung hergibt."
        ),
    },
    "simple_summary_user": {
        "title": "Einfach erklärt – Auftrag (RL-904)",
        "description": "Der zu erklärende Beschluss (Titel, Gremium, Datum, Beschlusstext).",
        "template": (
            "Beschluss: {title}\n"
            "Gremium: {committee} · Sitzung vom {session_date}\n\n"
            "Beschlusstext:\n{beschluss}"
        ),
    },
    "impact_bewertung_system": {
        "title": "Tragweite – System (RL-U16)",
        "description": "Bewertet Beschlüsse nach Tragweite/Folgenschwere (0–100) — speist den Wichtig-Wert.",
        "template": (
            "Du bewertest Beschlüsse des Oldenburger Stadtrats nach ihrer TRAGWEITE — wie "
            "folgenreich sind sie für die Stadt? Vergib je Rubrik 0–25 Punkte und addiere:\n"
            "① BETROFFENE: Wie viele Menschen, wie direkt? (ganze Stadt > Quartier > Einzelfall)\n"
            "② GELD: absolut und relativ zum städtischen Haushalt (Millionen > Zehntausende).\n"
            "③ BINDUNGSWIRKUNG: Satzung/Grundsatzbeschluss/Vertrag mit langer Laufzeit > "
            "einmalige Maßnahme > bloße Kenntnisnahme.\n"
            "④ PRÄZEDENZ/STRATEGIE: Stellt der Beschluss Weichen für viele Folgeentscheidungen?\n"
            "AUSDRÜCKLICH NICHT bewerten: Kuriosität, lustige Namen, Unterhaltungswert, "
            "Medienecho — dafür gibt es einen anderen Score.\n"
            "Kalibrier-Anker (Gesamtwert):\n"
            "- Gremienbesetzung, Protokollgenehmigung, Formalie ≈ 5\n"
            "- Kenntnisnahme eines Berichts ohne Beschlusswirkung ≈ 20\n"
            "- Maßnahme an einer einzelnen Straße/Einrichtung ≈ 35\n"
            "- Bebauungsplan für ein Quartier, mehrjährige Förderprogramme ≈ 70\n"
            "- Haushaltssatzung, stadtweite Grundsatzentscheidung ≈ 95\n"
            "Nutze die mitgelieferten Signale (Art, Ergebnis, Gremium, Betrag, Textlänge) — "
            "abgelehnte oder vertagte Anträge binden nichts (Bindung nahe 0, Präzedenz ggf. > 0).\n"
            "Antworte als JSON: {\"ratings\": [{\"id\": <id>, \"score\": <0-100>, "
            "\"grund\": \"<max. 1 kurzer Satz, benennt die stärkste Rubrik>\"}]} — "
            "genau ein Eintrag je vorgelegtem Beschluss."
        ),
    },
    "impact_bewertung_user": {
        "title": "Tragweite – Auftrag (RL-U16)",
        "description": "Batch zu bewertender Beschlüsse (id, Titel, Signale, Auszug).",
        "template": "Bewerte die Tragweite dieser Beschlüsse:\n\n{batch}",
    },
    "interest_bewertung_system": {
        "title": "Interessantheit – System (RL-U11)",
        "description": "Bewertet Beschlüsse nach Gesprächswert fürs „Fundstück des Tages“ (0–100).",
        "template": (
            "Du bewertest Beschlüsse des Oldenburger Stadtrats danach, wie INTERESSANT sie für "
            "normale Stadtbewohner:innen sind — als tägliches „Fundstück“ in einer Bürger-App.\n"
            "Interessant heißt hier ausdrücklich NICHT wichtig (Budget, Tragweite), sondern:\n"
            "- Gesprächswert: Würde man es beim Abendessen erzählen? („Wusstest du, dass der Rat …“)\n"
            "- Alltagsnähe: Merkt man es beim Radfahren, Einkaufen, im Park, am Badesee?\n"
            "- Kuriosität/Überraschung: ungewöhnlicher Gegenstand, überraschende Wendung, "
            "sehr knappe oder einstimmige Entscheidung zu einem emotionalen Thema.\n"
            "- Konkretheit: ein Ort, ein Ding, ein Datum — keine abstrakten Verwaltungsvorgänge.\n"
            "Niedrig (0–25): Geschäftsordnung, Gremienbesetzung, Satzungs-Formalien, reine "
            "Kenntnisnahmen. Mittel (30–55): solide Sachbeschlüsse ohne Erzählwert. Hoch (60–85): "
            "konkret, alltagsnah, erzählbar. Sehr hoch (90–100): kurios oder stadtbekannt.\n"
            "Antworte als JSON: {\"ratings\": [{\"id\": <id>, \"score\": <0-100>, "
            "\"grund\": \"<max. 1 kurzer Satz>\"}]} — genau ein Eintrag je vorgelegtem Beschluss."
        ),
    },
    "interest_bewertung_user": {
        "title": "Interessantheit – Auftrag (RL-U11)",
        "description": "Batch zu bewertender Beschlüsse (id, Titel, Auszug).",
        "template": "Bewerte diese Beschlüsse:\n\n{batch}",
    },
    "fundstueck_story_system": {
        "title": "Fundstück-Story – System (RL-U11)",
        "description": "Schreibt den einen Satz der Fundstück-Karte („Heute vor N Jahren …“).",
        "template": (
            "Du schreibst die Mini-Story für das „Fundstück des Tages“ einer Oldenburger "
            "Bürger-App: EIN Satz über einen echten Ratsbeschluss.\n"
            "Regeln:\n"
            "- Genau ein Satz, höchstens 200 Zeichen, aktiv, konkret, kein Ausrufezeichen.\n"
            "- Beginne mit „Der Rat beschloss {jahr}, …“ oder einer ähnlich konkreten Formulierung "
            "(beim zuständigen Ausschuss entsprechend).\n"
            "- Nur Fakten aus den vorgelegten Daten — nichts dazuerfinden, keine Folgen behaupten, "
            "die nicht im Text stehen.\n"
            "- Ton: neugierig machend, aber nüchtern — kein Marketing, keine Wertung.\n"
            "Antworte als JSON: {\"story\": \"...\"}"
        ),
    },
    "fundstueck_story_user": {
        "title": "Fundstück-Story – Auftrag (RL-U11)",
        "description": "Der Beschluss, zu dem die Story entsteht.",
        "template": (
            "Beschluss vom {session_date} ({committee}), Ergebnis: {outcome}.\n"
            "Titel: {title}\n"
            "Warum interessant: {interest_reason}\n\n"
            "Beschlusstext (Auszug):\n{beschluss}"
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
               updated_at TEXT NOT NULL,
               updated_by TEXT
           )"""
    )
    # Bestandsdaten: updated_by (Admin-E-Mail) nachrüsten (Design 21a).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(prompts)").fetchall()}
    if "updated_by" not in cols:
        conn.execute("ALTER TABLE prompts ADD COLUMN updated_by TEXT")
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
        r["key"]: r for r in conn.execute("SELECT key, content, updated_at, updated_by FROM prompts").fetchall()
    }
    conn.close()
    result = []
    for key, meta in DEFAULTS.items():
        ov = overrides.get(key)
        result.append(
            {
                "key": key,
                "title": meta["title"],
                "description": meta["description"],
                "default": meta["template"],
                "content": ov["content"] if ov else meta["template"],
                "is_overridden": ov is not None,
                "updated_at": ov["updated_at"] if ov else None,
                "updated_by": (ov["updated_by"] if ov else None),
            }
        )
    return result


def set_content(key: str, content: str, by: str | None = None) -> None:
    if key not in DEFAULTS:
        raise KeyError(f"Unknown prompt key: {key}")
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO prompts (key, content, updated_at, updated_by) VALUES (?, ?, ?, ?)",
            (key, content, now, by),
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
