"""Was die Clients lesen, muss im Vertrag stehen — und der Rest darf nicht wachsen.

**Der Fehler, gegen den das steht.** Am 02.09.2026 zeigte die iOS-App unter
jedem Thema „0 in 30 Tagen". Das Feld hieß seit #826 ``hits_6m`` und zählte
sechs Monate; die App las weiter ``hits_30d``, bekam es nie und setzte ihre
Vorgabe 0 ein. Kein Fehler, keine Meldung, nur eine falsche Zahl neben einem
falschen Zeitraum — und das auf Prod.

Solche Drift sieht **keine** der bestehenden Prüfungen: Der Vertragstest
prüft, dass jeder Endpunkt eine Antwortform hat; der Frontend-Wächter prüft,
dass jeder aufgerufene *Pfad* existiert. Beide sagen nichts über die
*Feldnamen*, die ein Client aus der Antwort herausliest.

**Warum das keine Liste ist, die man einmal leert.** Die meisten Felder, die
hier stehen, sind völlig in Ordnung — sie existieren, das Backend liefert sie,
nur beschreibt der Vertrag sie nicht: Sie stecken in einer der Nutzlasten, die
irgendwo ein offenes ``additionalProperties`` tragen (Stand heute 28 von 229
Schemata). Solange das so ist, kann niemand maschinell zwischen „Feld, das der
Vertrag verschweigt" und „Feld, das es nicht mehr gibt" unterscheiden.

Deshalb eine **Sperrklinke statt eines Verbots**: Die drei Listen unten sind
der Stand vom 02.09.2026. Sie dürfen schrumpfen und nicht wachsen. Wer ein
Schema vertieft, streicht seine Zeile — und ab da ist jedes Feld darin
maschinell geprüft. Genau so ist die Liste ``OFFEN`` in
``test_api_vertrag.py`` von 19 auf 0 gegangen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
VERTRAG = WURZEL / "api" / "openapi.json"
#: Die beiden Dateien, die sich selbst als Wire-Format verstehen: die
#: gemeinsamen Antworttypen und das Beleg-Format aller Haushalts-Schichten.
#: Die übrigen `lib/*.ts` bleiben bewusst draußen — dort hängen 900 Felder an
#: den offenen Budget-Nutzlasten, und eine Liste dieser Länge ist keine
#: Sperrklinke mehr, sondern eine Mauer. Sie kommen dazu, sobald die
#: zugehörigen Schemata beschrieben sind.
TYPEN_DATEIEN = (
    WURZEL / "web" / "frontend" / "lib" / "types.ts",
    WURZEL / "web" / "frontend" / "lib" / "herkunft.ts",
)
MODELS_SWIFT = (WURZEL / "ios" / "Packages" / "RatslotseAPI" / "Sources"
                / "RatslotseAPI" / "Models.swift")


def _vertragsfelder() -> set[str]:
    """Jeder Feldname, den der Vertrag irgendwo beschreibt."""
    spec = json.loads(VERTRAG.read_text())
    gefunden: set[str] = set()

    def laufen(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "properties" and isinstance(v, dict):
                    gefunden.update(v.keys())
                laufen(v)
        elif isinstance(o, list):
            for x in o:
                laufen(x)

    laufen(spec)
    return gefunden


def _web_felder() -> list[tuple[str, str]]:
    """``[(Typname, Feldname)]`` aus den handgeschriebenen Typen des Frontends."""
    aus: list[tuple[str, str]] = []
    for datei in TYPEN_DATEIEN:
        text = datei.read_text()
        aktuell: str | None = None
        for teil in re.split(r"^(export (?:interface|type) \w+)", text, flags=re.M):
            kopf = re.match(r"export (?:interface|type) (\w+)", teil)
            if kopf:
                aktuell = kopf.group(1)
                continue
            if aktuell:
                for feld in sorted(set(re.findall(
                        r"^\s+([a-zA-Z_][a-zA-Z0-9_]*)\??:\s", teil, re.M))):
                    aus.append((aktuell, feld))
                aktuell = None
    return aus


def _app_schluessel() -> set[str]:
    """Die JSON-Schlüssel, die ``Models.swift`` aus Antworten liest.

    Beide Schreibweisen: ``case x = "json_name"`` und die Kurzform
    ``case a, b, c`` (dort ist der Swift-Name zugleich der JSON-Name).
    """
    text = MODELS_SWIFT.read_text()
    schluessel = set(re.findall(r'case\s+\w+\s*=\s*"([a-zA-Z_0-9]+)"', text))
    for gruppe in re.findall(r"^\s+case ([a-z][a-zA-Z0-9]*(?:,\s*[a-z][a-zA-Z0-9]*)*)\s*$",
                             text, re.M):
        schluessel.update(x.strip() for x in gruppe.split(","))
    return schluessel


def _offene_schemata() -> set[str]:
    """Schemata mit einer wirklich offenen Stelle.

    Offen heißt ``additionalProperties: true`` — „irgendein Objekt", aus dem
    kein Generator etwas ableiten kann. Ein ``additionalProperties`` MIT Typ
    (``dict[str, Herkunft]`` etwa) ist das Gegenteil: eine beschriebene
    Abbildung, und die zählt hier nicht mit.
    """
    spec = json.loads(VERTRAG.read_text())

    def offen(o) -> bool:
        if isinstance(o, dict):
            zusatz = o.get("additionalProperties")
            if zusatz is True or zusatz == {}:
                return True
            return any(offen(v) for v in o.values())
        if isinstance(o, list):
            return any(offen(x) for x in o)
        return False

    return {name for name, schema in spec["components"]["schemas"].items()
            if offen(schema)}


#: Schemata mit einer offenen Stelle (``additionalProperties``). Genau hier
#: hört die maschinelle Prüfung auf: Was in einer solchen Nutzlast steckt,
#: kann niemand gegen den Vertrag halten. Die Liste ist die Arbeitsliste —
#: sie darf schrumpfen und nicht wachsen.
OFFENE_SCHEMATA = {
    "AdminAliasList",
    "AdminFeedbackList",
    "AdminJob",
    "AnalysisData",
    "BookmarkEntry",
    "BudgetDataState",
    "BudgetDebt",
    "BudgetFixedAssets",
    "ConversationTurn",
    "CouncilWeekPreview",
    "DecisionDetail",
    "Districts",
    "EntityDetail",
    "EntityGeo",
    "GoalDetail",
    "PersonCouncil",
    "PlaceCatalog",
    "PlaceEntry",
    "QaShare",
    "QaShareBody",
    "QuizOwnQuestions",
    "ResearchCurrent",
    "ResearchSnapshot",
    "SessionDetail",
    "SessionRow",
    "SocialDecision",
    "TrendData",
    "WeekPreview",
}

#: Felder der handgeschriebenen Frontend-Typen, die der Vertrag nicht kennt.
#: Stand 02.09.2026 nachgeprüft: Es gibt sie alle, das Backend liefert sie —
#: sie stecken in einer der offenen Nutzlasten oben.
WEB_OHNE_VERTRAG = {
    ("AdminFeedback", "owner_id"),
    ("AdminFeedback", "read_at"),
    ("AdminStats", "web_users"),
    ("AgendaAenderungZeile", "art"),
    ("AgendaAenderungZeile", "nichtoeffentlich"),
    ("AgendaItem", "anlagen"),
    ("AgendaItem", "dringlich"),
    ("AgendaItem", "is_public"),
    ("AgendaItem", "social_text"),
    ("Beratung", "future"),
    ("Beratung", "is_public"),
    ("Beratung", "result"),
    ("CouncilSession", "matched_items"),
    ("DecisionDetail", "amount"),
    ("DecisionDetail", "anlagen"),
    ("DecisionDetail", "applicants"),
    ("DecisionDetail", "art"),
    ("DecisionDetail", "bild"),
    ("DecisionDetail", "href"),
    ("DecisionDetail", "is_motion"),
    ("Entity", "n_recent"),
    ("EntityMapPoint", "location_slug"),
    ("FieldRecap", "field_label"),
    ("FieldRecap", "generated_at"),
    ("FieldRecap", "n_decisions"),
    ("FieldRecap", "period_from"),
    ("FieldRecap", "period_to"),
    ("Member", "art"),
    ("Member", "filter_parteien"),
    ("Member", "formen"),
    ("MemberDetail", "current_faction"),
    ("MemberDetail", "kpenr"),
    ("MemberDetail", "memberships"),
    ("PartyAnalysis", "accepted"),
    ("PartyAnalysis", "matrix"),
    ("PartyAnalysis", "n_antraege"),
    ("PartyAnalysis", "n_mit_beschluss"),
    ("QaAnswer", "mode"),
    ("QaSource", "ort_name"),
    ("QuizBadge", "tier"),
    ("QuizImageCredit", "author"),
    ("QuizImageCredit", "license"),
    ("QuizImageCredit", "license_url"),
    ("RelatedEntity", "rel_type"),
    ("UserQuizQuestion", "correct_count"),
    ("UserQuizQuestion", "practiced"),
    ("VideoResult", "quote"),
    ("VideoResult", "video_id"),
    ("VideoResult", "video_seconds"),
}

#: Dasselbe für die iOS-App. Zwei Einträge sind hier anders als der Rest:
#: ``calendar_id`` schickt das Backend NIRGENDS — der Schlüssel dient in
#: ``SessionRow`` als Ersatz-Identität für Kalendertermine ohne ``ksinr`` und
#: ist damit immer leer. Was dort stattdessen stehen sollte, ist offen.
#: (Der dritte tote Schlüssel, ``hits_30d``, ist am 02.09.2026 behoben
#: worden: Er hieß seit #826 ``hits_6m``, und die App zeigte deshalb bei
#: jedem Thema eine 0.)
APP_OHNE_VERTRAG = {
    "applicants",
    "art",
    "calendar_id",
    "future",
    "is_motion",
    "is_public",
    "letzte",
    "location_slug",
    "n_stationen",
    "naechste",
    "nichtoeffentlich",
    "ort_name",
    "rest",
    "result",
    "titel_kurz",
    "wichtig_grund",
}

def test_der_leser_findet_ueberhaupt_etwas():
    """Damit die Sperrklinke nicht stumm aufhört zu greifen.

    Alle drei Listen unten wären leer, wenn eine der Ausleseregeln nicht mehr
    passt — und ein leerer Vergleich ist immer grün. Das hier ist die
    Untergrenze, unter der der Test sich selbst für kaputt erklärt.
    """
    assert len(_vertragsfelder()) > 400
    assert len(_web_felder()) > 200
    assert len(_app_schluessel()) > 100
    assert len(_offene_schemata()) > 0


def test_der_vertrag_bekommt_keine_neue_offene_stelle():
    """Eine offene Nutzlast ist eine Stelle, an der niemand mehr prüfen kann."""
    ist = _offene_schemata()
    neu = sorted(ist - OFFENE_SCHEMATA)
    assert not neu, (
        "Diese Schemata haben neuerdings eine offene Stelle "
        "(`additionalProperties`):\n  " + "\n  ".join(neu)
        + "\n\nDamit ist ihr Inhalt für beide Clients ungeprüft. Beschreib die "
          "Felder in web/backend/app/antworten.py — oder trag das Schema hier "
          "ein, wenn es wirklich eine offene Nutzlast bleiben soll."
    )
    geschlossen = sorted(OFFENE_SCHEMATA - ist)
    assert not geschlossen, (
        "Diese Schemata sind inzwischen vollständig beschrieben — bitte aus "
        "OFFENE_SCHEMATA streichen, sonst schrumpft die Liste nie:\n  "
        + "\n  ".join(geschlossen)
    )


def test_das_web_liest_kein_neues_unbekanntes_feld():
    felder = _vertragsfelder()
    ist = {(typ, feld) for typ, feld in _web_felder() if feld not in felder}
    neu = sorted(f"{typ}.{feld}" for typ, feld in ist - WEB_OHNE_VERTRAG)
    assert not neu, (
        "Diese Felder liest das Frontend, der Vertrag kennt sie nicht:\n  "
        + "\n  ".join(neu)
        + "\n\nEntweder wurde im Backend umbenannt und das Frontend hinkt nach "
          "— oder das Feld gehört in die Antwortform (antworten.py) und der "
          "Vertrag muss neu geschnitten werden."
    )
    weg = sorted(f"{typ}.{feld}" for typ, feld in WEB_OHNE_VERTRAG - ist)
    assert not weg, (
        "Diese Einträge stehen in WEB_OHNE_VERTRAG, treffen aber nicht mehr zu "
        "— bitte streichen:\n  " + "\n  ".join(weg)
    )


def test_die_app_liest_keinen_neuen_unbekannten_schluessel():
    """Der Wächter, der `hits_30d` gefunden hätte.

    Die App ist der Client, den die Testsuite des Backends nicht erreicht: Ihr
    Workflow läuft nur bei Änderungen unter ``ios/``, ihre Modelle sind von
    Hand geschrieben, und ihre Decode-Tests schreiben ihr JSON selbst. Eine
    Umbenennung im Backend kommt dort auf keinem Weg an — außer über diesen
    Vergleich.
    """
    felder = _vertragsfelder()
    ist = {k for k in _app_schluessel() if k not in felder}
    neu = sorted(ist - APP_OHNE_VERTRAG)
    assert not neu, (
        "Diese JSON-Schlüssel liest die App, der Vertrag kennt sie nicht:\n  "
        + "\n  ".join(neu)
        + "\n\nWeil Models.swift mit `decodeIfPresent` liest, gibt das keinen "
          "Fehler: Das Feld wird still leer und der Screen zeigt eine Vorgabe. "
          "Prüf, ob das Backend den Namen geändert hat."
    )
    weg = sorted(APP_OHNE_VERTRAG - ist)
    assert not weg, (
        "Diese Einträge stehen in APP_OHNE_VERTRAG, treffen aber nicht mehr zu "
        "— bitte streichen:\n  " + "\n  ".join(weg)
    )
