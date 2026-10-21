"""Suchtext der Beschluss-Liste → SQL-Bedingung.

Bis 10/2026 suchte die Liste die ganze Eingabe als EINE Zeichenkette
(``LIKE '%<Eingabe>%'``). „PAK-Belastung“ fand den Ratsbeschluss vom
31.08.2026, „PAK Belastung“ fand nichts — und ein Nutzer schloss daraus, der
Beschluss fehle. Jetzt wird jedes Wort einzeln verlangt (UND), egal in welchem
der drei Felder es steht; Bindestrich, Leerzeichen und Satzzeichen trennen
gleichermaßen. Wer einen Wortlaut braucht, setzt ihn in Anführungszeichen.

Warum LIKE und nicht die FTS-Tabelle ``council_decisions_fts``: Die indiziert
auch den Vorlagen-Volltext, die Liste hat aber immer nur Titel, Beschlusstext
und Kurzfassung durchsucht — mit FTS bekäme „Radweg“ plötzlich jeden Beschluss,
dessen Vorlage das Wort irgendwo auf Seite 12 erwähnt, und die Zählung im Kopf
der Liste spränge. FTS findet außerdem nur ganze Wörter (bzw. Präfixe); das
Deutsche verlangt aber Teilwörter: „Straße“ muss „Fliegerhorststraße“ finden.
Die MCP-Suche nimmt bewusst FTS (Relevanz-Ranking, ODER) — dort sortiert die
Relevanz, hier das Datum.
"""
from __future__ import annotations

import itertools
import math
import re

# Wörter, unter denen ein Gegenstand in den Unterlagen anders heißt als im
# Sprachgebrauch. Jede Gruppe gilt in beide Richtungen; Schreibung wie nach
# fold() (klein, ss statt ß).
SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    # Die Stadt führt die Straße seit dem B-Plan N-777 G als
    # „Entlastungsstraße“ (gemessen 21.10.2026: alle 33 Beschlüsse mit dem
    # Wort betreffen den Fliegerhorst); gesprochen und in Anfragen von 2023/24
    # heißt sie „Fliegerhorststraße“. Ohne die Gruppe endete die Suche nach
    # dem gängigen Namen 2024.
    frozenset({"fliegerhorststrasse", "entlastungsstrasse"}),
)

_PHRASE = re.compile(r'"([^"]+)"')
_WORD = re.compile(r"[^\W_]+")
_EDGE = re.compile(r"^[^\w]+|[^\w]+$")
# Füllwörter, die der Rückfall (``relaxed``) überspringt. Kommen sie aus einem
# eingefügten Titel, zählen sie sonst als Begriffe mit — und „der“ steckt als
# Teilwort in fast jedem Text.
_STOPWORDS = frozenset(
    "der die das des dem den ein eine einer eines einem einen und oder in im am an "
    "auf aus bei mit nach von vom zu zum zur für über unter vor bis ist sind wird "
    "werden wurde sowie als auch nicht".split())
# Endungen, die der Rückfall abschneidet: „Schießstandes“ findet dann
# „Schießstand“, „festgestellten“ „festgestellt“. Nur an langen Wörtern, und
# weil LIKE ein Teilwort sucht, findet der Stamm die längere Form weiter.
_SUFFIXES = ("es", "en", "er", "em", "e", "s", "n")
_STEM_MIN = 7
# Die TOP-Nummer vorn an einem eingefügten Tagesordnungspunkt: „Ö 10.5“,
# „TOP 7“, „DZT 1“, „N 3.1“. Sie steht in keinem durchsuchten Feld.
_AGENDA_NUMBER = re.compile(r"^\s*(?:(?:top|ö|n|dzt)\s*)?\d+(?:\.\d+)*\.?(?=\s)", re.IGNORECASE)
# Der Rückfall verlangt drei Viertel der Begriffe.
_RELAXED_SHARE = 0.75
# Ab so vielen „ss“ in einem Wort nur noch die zwei reinen Schreibungen statt
# aller Mischungen — sonst wüchse die Abfrage mit 2^n.
_MAX_SS_MIX = 3


def fold(text: str) -> str:
    """Die Schreibung, in der Suchbegriffe verglichen werden."""
    return text.lower().replace("ß", "ss")


def _stem(word: str) -> str:
    if len(word) < _STEM_MIN:
        return word
    for suffix in _SUFFIXES:
        if word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def search_terms(query: str, relaxed: bool = False) -> list[tuple[str, ...]]:
    """Die Begriffe einer Eingabe; jeder ist ein Tupel von Alternativen
    (ein Synonym erweitert ihn), und jeder Begriff muss vorkommen.

    - ``"…"`` bleibt ein Wortlaut.
    - Ein Stück mit Ziffer bleibt ganz: „26/0459“, „31.08.“, „N-777“ —
      zerlegt träfe „26“ jeden Beschluss von 2026.
    - Einzelne Buchstaben fallen weg, solange etwas anderes übrig bleibt;
      aus „N-777 G“ würde sonst ein „g“, das fast alles trifft.
    """
    if relaxed:
        query = _AGENDA_NUMBER.sub("", query)
    raw: list[str] = [fold(p).strip() for p in _PHRASE.findall(query)]
    words: list[str] = []
    for chunk in _PHRASE.sub(" ", query).split():
        chunk = fold(chunk)
        if any(ch.isdigit() for ch in chunk):
            literal = _EDGE.sub("", chunk)
            if literal:
                raw.append(literal)
        else:
            words += _WORD.findall(chunk)
    longer = [w for w in words if len(w) > 1]
    words = longer if (longer or raw) else words
    if relaxed:
        content = [w for w in words if w not in _STOPWORDS]
        words = [_stem(w) for w in (content or words)]
    raw += words
    terms: list[tuple[str, ...]] = []
    for term in raw:
        if not term:
            continue
        group = next((g for g in SYNONYM_GROUPS
                      if term in g or (relaxed and term in {_stem(x) for x in g})), None)
        alternatives = (term, *sorted(group - {term})) if group else (term,)
        if alternatives not in terms:
            terms.append(alternatives)
    return terms


def spellings(term: str) -> list[str]:
    """Die Schreibungen, unter denen ein gefalteter Begriff im Text stehen
    kann. SQLite-LIKE faltet nur ASCII — „änderung“ fände „Änderung“ nicht,
    „strasse“ nicht „Straße“. Statt den Text in SQL umzuschreiben (gemessen
    dreimal so langsam: ``replace`` über jeden Beschlusstext), bekommt der
    Begriff seine Varianten: jedes „ss“ auch als „ß“, ein Umlaut am Anfang
    auch groß."""
    parts = term.split("ss")
    if len(parts) == 1:
        forms = [term]
    elif len(parts) - 1 <= _MAX_SS_MIX:
        forms = ["".join(itertools.chain.from_iterable(zip(parts, seps))) + parts[-1]
                 for seps in itertools.product(("ss", "ß"), repeat=len(parts) - 1)]
    else:
        forms = [term, term.replace("ss", "ß")]
    if term[:1] in "äöü":
        forms += [f[0].upper() + f[1:] for f in forms]
    return forms


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Die Vorlagennummer gehört dazu: „22/0257“ ist eine der Eingaben, mit der
# Leute einen Beschluss suchen, und sie steht oft in keinem der Texte.
_FIELDS = ("d.title", "d.official_text", "d.summary", "d.template_number")


def text_filter(query: str, relaxed: bool = False) -> tuple[str, list[str]] | None:
    """SQL-Bedingung (auf Alias ``d`` = council_decisions) samt Parametern,
    oder None, wenn die Eingabe keinen Suchbegriff enthält.

    Jeder Begriff darf in einem anderen Feld stehen als der
    nächste — gesucht wird je Begriff in allen.

    ``relaxed`` ist der Rückfall, wenn die strenge Suche nichts findet: Wer
    einen TOP aus dem Protokoll einfügt, bringt Wörter mit, die bei uns nicht
    stehen — „Ö 10.5“, „- Beschlussantrag“, oder der Titel ist bei uns kürzer
    (gemessen am 21.10.2026: der PAK-Beschluss endet auf Prod „… im Bereich“,
    im Protokoll geht er weiter). Dann reichen drei Viertel der Begriffe, ohne
    Füllwörter und mit abgeschnittenen Endungen."""
    terms = search_terms(query, relaxed=relaxed)
    if not terms:
        return None
    clauses: list[str] = []
    params: list[str] = []
    for alternatives in terms:
        likes = [f"%{_escape_like(s)}%" for a in alternatives for s in spellings(a)]
        clauses.append("(" + " OR ".join(
            f"{field} LIKE ? ESCAPE '\\'" for _ in likes for field in _FIELDS) + ")")
        params += [like for like in likes for _ in _FIELDS]
    if relaxed and len(clauses) > 2:
        # Ein erfüllter Begriff zählt in SQLite als 1 — die Summe ist die
        # Zahl der getroffenen Begriffe. coalesce, weil ein leeres Feld
        # (summary, template_number) den Vergleich zu NULL macht, und NULL in
        # einer Summe macht die ganze Summe NULL: Der Rückfall fand so nichts.
        need = math.ceil(_RELAXED_SHARE * len(clauses))
        return "(" + " + ".join(f"coalesce({c}, 0)" for c in clauses) + f") >= {need}", params
    return "(" + " AND ".join(clauses) + ")", params


def has_relaxed_fallback(query: str) -> bool:
    """Ob der Rückfall etwas anderes suchen würde als die strenge Suche."""
    if not query:
        return False
    relaxed = text_filter(query, relaxed=True)
    return relaxed is not None and relaxed != text_filter(query)


def count_rows(conn, where: str, params: list) -> int:
    """Zahl der Beschlüsse zu einer WHERE-Klausel aus ``_decision_where``."""
    row = conn.execute(
        f"""SELECT COUNT(*) FROM council_decisions d
            JOIN council_sessions cs ON cs.ksinr = d.ksinr {where}""",
        params,
    ).fetchone()
    return row[0] if row else 0
