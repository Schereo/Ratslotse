"""Sperrklinke: Die Swift-Modelle dürfen nicht weiter vom Vertrag abdriften.

Die Messung selbst steht in ``scripts/ios_vertrag.py`` — dort steht auch,
warum es sie gibt und welche drei Fehlerklassen sie findet. Hier steht nur,
was am Stand vom 02.09.2026 offen bleiben **darf**.

Die Liste darf schrumpfen und nicht wachsen. Ein Eintrag, den es nicht mehr
gibt, muss raus: Eine Ausnahme, die nichts mehr abdeckt, sieht aus wie eine
gültige Erlaubnis und ist keine.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ios_vertrag import befunde  # noqa: E402

#: ``(Swift-Typ, Schema): [Feld, …]`` — jede Gruppe mit ihrem Grund.
BEWUSST_OFFEN: dict[tuple[str, str], list[str]] = {
    # ── Die App liest eine Form, die WEITER ist als dieses eine Schema ──────
    #
    # `DecisionSummary` decodiert Beschlüsse aus vier Quellen: der Liste, den
    # Lesezeichen, den semantischen Nachbarn — und dem Quellen-Block der
    # KI-Antwort. Der letzte ist ein Ereignis-Strom und steht ausdrücklich
    # NICHT im Vertrag (`SSE_FRAGE`); dort reisen Ortsangaben mit, die die
    # Beschluss-Liste selbst nie trägt. Alle drei sind in Swift optional, die
    # App bekommt also je nach Quelle etwas oder nichts.
    ("DecisionSummary", "DecisionRow"): ["lat", "lon", "ort_name"],
    ("DecisionSummary", "BookmarkEntry.decision"): ["lat", "lon", "ort_name"],
    # Die semantischen Nachbarn sind bewusst eine SCHMALE Karte: Titel,
    # Gremium, Datum, Ergebnis. Die App wirft denselben Typ darauf, statt
    # einen zweiten zu pflegen — die 23 Felder bleiben leer, und genau so ist
    # die Karte gebaut.
    ("DecisionSummary", "SimilarDecision"): [
        "abstentions", "amount_eur", "deviation", "factions", "impact",
        "impact_reason", "importance", "interest", "interest_reason",
        "item_number", "kind", "ksinr", "lat", "lon", "no_votes",
        "official_text", "ort_name", "parties", "policy_tags", "protocol_url",
        "raw_result", "simple_summary", "vote",
    ],
    # `/deep-research/current` schickt nur den KOPF des Auftrags (Frage,
    # Status, Zeiten). Bericht und Quellen holt die App danach einzeln über
    # `/deep-research/{id}`; beide sind optional und bleiben hier leer.
    ("ResearchSnapshot", "ResearchCurrent.job"): ["report", "sources"],
    # `future` rechnet die Beschluss-Seite je Station aus. Die Folgen-Liste
    # reicht die Stationen roh durch — dort ist die Frage auch beantwortet,
    # bevor sie gestellt wird: `naechste` ist künftig, `letzte` war es nie.
    ("CouncilConsultationStop", "TemplateFollow.letzte"): ["future"],
    ("CouncilConsultationStop", "TemplateFollow.naechste"): ["future"],

    # ── Der Vertrag UNTERTREIBT: Feld ist immer da, steht aber nicht in
    #    `required` ───────────────────────────────────────────────────────────
    #
    # Alle folgenden Felder haben im Pydantic-Modell bzw. im TypedDict einen
    # Vorgabewert. FastAPI serialisiert sie deshalb IMMER, trägt sie aber
    # nicht in `required` ein — der Vertrag erlaubt also formal ein Weglassen,
    # das es nicht gibt. Die App liest sie zu Recht als Pflichtfelder.
    #
    # Das sauber zu machen heißt, die Vorgabewerte aus den Modellen zu nehmen
    # und sie an jeder Erzeugungsstelle zu übergeben. Das ist eine eigene
    # Runde und gehört nicht in dieselbe wie das Werkzeug, das es findet.
    ("User", "UserOut"): [
        "apple_linked", "delivery_channel", "email_verified", "has_password",
        "status",
    ],
    ("AppConfiguration", "AppConfigOut"): ["min_build"],
    ("TopicHit", "TopicHitOut"): ["is_new"],
    ("FollowEntry", "TemplateFollow"): ["template_number", "title"],
    ("CouncilParticipation", "DecisionDetail.participation"): ["title", "url"],
}

ERLAUBT = {
    (typ, schema, feld)
    for (typ, schema), felder in BEWUSST_OFFEN.items()
    for feld in felder
}


def test_keine_neue_abweichung_zwischen_app_und_vertrag():
    gefunden = {(typ, schema, feld) for typ, schema, feld, _ in befunde()}
    neu = sorted(gefunden - ERLAUBT)
    assert not neu, (
        "Die App liest Felder, die der Vertrag so nicht beschreibt:\n"
        + "\n".join(f"  {t} → {s}.{f}" for t, s, f in neu)
        + "\n\nEntweder ist das Feld im Backend umbenannt worden (dann zieht "
          "die App nach), oder die Antwortform beschreibt es noch nicht "
          "(dann gehört es in web/backend/app/antworten.py). "
          "Einzelheiten: python scripts/ios_vertrag.py"
    )


def test_ausnahmeliste_traegt_keine_leichen():
    gefunden = {(typ, schema, feld) for typ, schema, feld, _ in befunde()}
    veraltet = sorted(ERLAUBT - gefunden)
    assert not veraltet, (
        "Diese Ausnahmen decken nichts mehr ab und gehören gestrichen:\n"
        + "\n".join(f"  {t} → {s}.{f}" for t, s, f in veraltet)
    )
