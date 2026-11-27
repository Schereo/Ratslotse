"""Die KI-Pipelines, ihre Benchmarks und das Format eines Messlaufs.

**Wozu.** Bis 11/2026 lagen die Messungen an vier Orten in sechs Formaten:
``eval/results/`` (je Suite ein anderes JSON), ``docs/gold-messbuch.md``
(von Hand geführte Tabelle), ``data/eval_gold/`` auf den Servern und ein
paar Markdown-Berichte. Welche Pipeline gerade wie gut ist, mit welchem
Modell, gegen welche Fälle und auf welchem Datenstand gemessen — das ließ
sich nur aus Commits zusammensuchen (Tim, 26.11.2026: „ich sehe auch nicht,
unter welchen Bedingungen, mit welchen Pipelines, mit welchen Daten die
erstellt worden sind").

Diese Datei ist die eine Stelle dafür, wie ``jobs.py`` für die Cron-Jobs:

- :data:`PIPELINES` — jedes KI-Feature des Produkts, zerlegt in seine Stufen
  (je Stufe die ``_feature``-Namen aus ``llm_usage`` und woher das Modell
  kommt). ``tests/test_benchmarks.py`` hält fest, dass jeder Feature-Name im
  Code genau einer Pipeline gehört — ein neues KI-Feature taucht damit im
  Admin-Panel auf, auch wenn es noch keinen Benchmark hat. Gerade dann.
- :data:`BENCHMARKS` — jede Messung, die es gibt: was sie misst, woraus die
  Erwartung kommt, ob ein Modell richtet, wo sie läuft, wie stark sie streut.
- **Der Messlauf** (:func:`new_run`) — ein kleines JSON je Lauf unter
  ``eval/runs/<benchmark>/``, mit allem, was man braucht, um ihn später
  einzuordnen: Code-Stand, Modelle je Stufe, Fälle samt Prüfsumme,
  Datenstand, Kennzahlen, Kosten, Zweck und Fazit. Das Rohergebnis bleibt, wo
  es ist (``raw`` zeigt darauf); der Lauf ist die Karteikarte dazu.

**Warum eine Prüfsumme der Fälle und die Modelle je Stufe.** Die Lehre aus dem
Gold-Messbuch: Die Belegnotizen brachten im Oktober „+5 Pp" und im November
nichts — dazwischen hatte das Modell unter dem Schritt gewechselt. „Wechselt
das Modell unter einem Schritt, gilt seine alte Messung nicht mehr." Mit
beidem im Lauf kann :func:`assess` das selbst sagen, statt dass es jemand
wissen muss.

**Wohin ein Lauf geschrieben wird.** Lokale Läufe nach ``eval/runs/`` (ins
Repo, mit dem PR). Läufe auf einem Server (Gold-Fälle, die Embeddings
brauchen) nach ``data/eval_runs/`` — ``eval/`` räumt der Deploy mit
``rsync --delete`` weg, ``data/`` überlebt ihn. Das Admin-Panel liest beide.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: Läufe im Repo — sie fahren mit dem Code auf jeden Server.
REPO_RUNS = ROOT / "eval" / "runs"
#: Läufe, die auf DIESEM Server entstanden sind (``data/`` überlebt den Deploy).
SERVER_RUNS = ROOT / "data" / "eval_runs"

SCHEMA = 1
#: ``unknown`` nur für nachgetragene Läufe, deren Umgebung nirgends steht.
ENVIRONMENTS = ("local", "dev", "prod", "ci", "unknown")
#: Ab wie vielen Tagen ein Lauf als alt gilt, auch wenn sich sonst nichts
#: geändert hat — der Datenbestand wächst, die Suche ändert sich mit.
STALE_AFTER_DAYS = 90
GITHUB = "https://github.com/Schereo/Ratslotse"

# --------------------------------------------------------------------------- #
# Katalog
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Step:
    """Eine Stufe einer Pipeline — meist ein Modellaufruf, manchmal keiner."""

    key: str
    label: str
    #: Die ``_feature``-Namen dieser Stufe in ``llm_usage``. Leer = die Stufe
    #: ruft kein Sprachmodell (Suche, Reranker, Regeln).
    features: tuple[str, ...] = ()
    #: Woher das Modell kommt: ``"modul:ATTRIBUT"`` (so, wie das Modul es beim
    #: Import gebunden hat) oder ``"cities:<annotator>"``. Aufgelöst wird im
    #: Backend — ``kern`` importiert ``council`` nicht.
    model: str | None = None


@dataclass(frozen=True)
class Pipeline:
    key: str
    title: str
    summary: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    #: ``share`` (0–1, als % gezeigt), ``count``, ``seconds``, ``ratio`` (0–1
    #: ohne %, etwa Spearman ρ oder MRR), ``none`` (keine Zahl: ein Lauf zum
    #: Lesen, etwa eine Gegenüberstellung, die eine Hand prüft)
    unit: str = "share"
    higher_is_better: bool = True


QUALITY = "quality"
HARD = "hard_findings"


@dataclass(frozen=True)
class Benchmark:
    key: str
    pipeline: str
    title: str
    #: Was gemessen wird, in einem Satz.
    measures: str
    metric: Metric
    secondary: tuple[Metric, ...] = ()
    #: Welche Stufen der Pipeline der Benchmark berührt (``Step.key``). Nur
    #: diese zählen beim Modellvergleich in :func:`assess`.
    steps: tuple[str, ...] = ()
    #: Weitere Pipelines, deren Stufen er mitmisst (die Fakten-Evals fragen
    #: Lotti UND Frag den Rat).
    also: tuple[str, ...] = ()
    cases: tuple[str, ...] = ()
    #: Woher die Erwartung kommt.
    truth: str = ""
    #: Ein Modell als Richter — dann misst der Lauf auch den Richter mit.
    judge: str | None = None
    #: ``local`` (Notebook mit dem Abzug), ``server`` (braucht Embeddings oder
    #: den laufenden Dienst), ``both``
    runs_on: str = "local"
    command: str = ""
    #: Was man über die Streuung weiß — ohne das ist ein Unterschied nicht lesbar.
    noise: str | None = None
    #: Was als harter Befund zählt (``metrics["hard_findings"]``).
    hard: str | None = None
    #: Ein Dokument mit der Geschichte der Läufe und den Entscheidungen.
    log: str | None = None


def _q(label: str) -> Metric:
    return Metric(QUALITY, label)


def _hard() -> Metric:
    return Metric(HARD, "harte Befunde", "count", higher_is_better=False)


def _p(suite: str, *extra: str) -> str:
    """Der Prüfstand-Aufruf einer Suite."""
    return " ".join(("python eval/pruefstand.py --suite", suite, "--laeufe 2", *extra))


_QA = "council.qa:MODEL"
_EXPAND = "council.qa:EXPAND_MODEL"

PIPELINES: tuple[Pipeline, ...] = (
    Pipeline(
        key="ask", title="Frag den Rat",
        summary="Beantwortet Fragen zum Rat mit Belegen aus Beschlüssen, Debatten und Haushalt.",
        steps=(
            Step("qa_analysis", "Analyse & Routing", ("qa_analysis",), _EXPAND),
            Step("qa_query_expansion", "Suchbegriffe", ("qa_query_expansion",), _EXPAND),
            Step("retrieval", "Suche (Vektor, BM25, Reranker)", (), "council.embeddings:RERANK_MODEL"),
            Step("qa_nachrecherche", "Nachrecherche", ("qa_nachrecherche",), _EXPAND),
            Step("party_opinions", "Haltungen der Fraktionen", ("party_opinions",), _QA),
            Step("qa_answer", "Antwort", ("qa_answer",), _QA),
            Step("qa_simple", "Verständlicher erklärt", ("qa_simple",), _QA),
        ),
    ),
    Pipeline(
        key="deep", title="Gründliche Recherche",
        summary="Zerlegt eine Frage, sucht je Teilfrage und schreibt einen langen Bericht.",
        steps=(
            Step("deep_decomposition", "Zerlegung", ("deep_decomposition",), _EXPAND),
            Step("retrieval", "Suche je Teilfrage", (), "council.embeddings:RERANK_MODEL"),
            Step("deep_report", "Bericht", ("deep_report",), "council.qa:DEEP_MODEL"),
        ),
    ),
    Pipeline(
        key="lotti", title="Lotti erklärt",
        summary="Erklärt Seiten, Begriffe und Zahlen und reicht Ratsfragen weiter.",
        steps=(
            Step("assistant_explain", "Erklärung", ("assistant_explain",), "council.assistant:MODEL"),
            Step("assistant_check", "Selbstprüfung", ("assistant_check",), "council.self_check:MODEL"),
        ),
    ),
    Pipeline(
        key="notify", title="Benachrichtigungen",
        summary="Ordnet Tagesordnungen den Themen zu und fasst Ausschüsse für Mails zusammen.",
        steps=(
            Step("council_watcher", "Themen-Wächter", ("council_watcher",), "council.watcher:MODEL"),
            Step("committee_summary", "Ausschuss-Zusammenfassung", ("committee_summary",),
                 "council.committee_summary:MODEL"),
            Step("impact_rating_agenda", "Tragweite je Tagesordnungspunkt", ("impact_rating_agenda",),
                 "council.impact:MODEL"),
        ),
    ),
    Pipeline(
        key="decisions", title="Beschlüsse aufbereiten",
        summary="Liest Protokolle und Anträge, schreibt Kurzfassungen und bewertet Beschlüsse.",
        steps=(
            Step("minutes_extraction", "Protokoll lesen", ("minutes_extraction",), "council.protocols:MODEL"),
            Step("motion_extract", "Änderungsanträge", ("motion_extract",), "council.motions:MODEL"),
            Step("simple_summary", "Kurzfassung", ("simple_summary",), "council.simple_summary:MODEL"),
            Step("impact_rating", "Tragweite", ("impact_rating",), "council.impact:MODEL"),
            Step("interest_rating", "Gesprächswert", ("interest_rating",), "council.interest:MODEL"),
            Step("topic_classification", "Themenfeld", ("topic_classification",), "council.topics:MODEL"),
        ),
    ),
    Pipeline(
        key="places", title="Orte & Mein Viertel",
        summary="Findet die Orte eines Beschlusses und entscheidet, was in ein Viertel gehört.",
        steps=(
            Step("decision_places", "Orte eines Beschlusses", ("decision_places",), "council.locations:MODEL"),
            Step("district_projects", "Mein Viertel", ("district_projects",), "council.viertel:MODEL"),
        ),
    ),
    Pipeline(
        key="debates", title="Wortbeiträge & Argumente",
        summary="Liest aus Niederschriften, wer was gesagt hat, und bündelt die Argumente je Punkt.",
        steps=(
            Step("speeches", "Wortbeiträge", ("speeches",), "council.wortbeitraege:MODEL"),
            Step("item_arguments", "Argumente zum Punkt", ("item_arguments",), "council.arguments:MODEL"),
        ),
    ),
    Pipeline(
        key="live", title="Live-Sitzung",
        summary="Schreibt den Livestream mit, verfolgt den laufenden Punkt und liest Ergebnisse.",
        steps=(
            Step("livestream_transcript", "Transkription", ("livestream_transcript",),
                 "council.livestream:STT_MODEL"),
            Step("live_top_tracker", "Welcher Punkt läuft", ("live_top_tracker",),
                 "council.livetracker:TRACKER_MODEL"),
            Step("video_results", "Ergebnisse aus dem Video", ("video_results",), "council.videos:MODEL"),
        ),
    ),
    Pipeline(
        key="templates", title="Vorlagen & Sitzungen",
        summary="Bereitet Vorlagen auf: Texterkennung, Dossier, Fachwörter, Wahlprogramme, Sitzungssatz.",
        steps=(
            Step("attachment_ocr", "Texterkennung der Anlagen", ("attachment_ocr",), "council.ocr:MODEL"),
            Step("template_dossier", "Dossier je Vorlage", ("template_dossier", "template_dossier_abruf"),
                 "council.template_dossier:MODEL"),
            Step("template_terms", "Fachwörter", ("template_terms", "template_terms_verify"),
                 "council.vorlage_begriffe:MODEL"),
            Step("program_stance", "Wahlprogramme zum Punkt", ("program_stance", "program_stance_verify"),
                 "council.programm_bezug:MODEL"),
            Step("session_summary", "Satz zur Sitzung", ("session_summary",), "council.session_summary:MODEL"),
            Step("page_questions", "Vorschlagsfragen", ("page_questions",), "council.vorschlagsfragen:MODEL"),
        ),
    ),
    Pipeline(
        key="social", title="Social-Karten",
        summary="Schreibt den Text der Instagram-Karten und prüft jeden Satz gegen die Vorlage.",
        steps=(
            Step("social_card_text", "Kartentext", ("social_card_text",), "council.social_text:MODEL"),
            Step("social_critic", "Kritiker", ("social_critic",), "council.kritiker:MODEL"),
        ),
    ),
    Pipeline(
        key="cities", title="Städtevergleich",
        summary="Ordnet Vorlagen anderer Städte ein und prüft, ob Oldenburg die Idee schon hat.",
        steps=(
            Step("cities_classify", "Taugt die Vorlage?", ("cities_classify",), "cities:classify"),
            Step("cities_stance", "Wollte der Rat die Idee?", ("cities_stance",), "cities:stance"),
            Step("cities_reason", "Warum ging es so aus?", ("cities_reason",), "cities:reason"),
            Step("cities_effort", "Was kostet die Idee?", ("cities_effort",), "cities:effort"),
            Step("cities_cluster_check", "Gehört das zusammen?", ("cities_cluster_check",), "cities:cluster_check"),
            Step("cities_evidence_terms", "Oldenburger Suchwörter", ("cities_evidence_terms",),
                 "council.cities.evidence:TERMS_MODEL"),
            Step("cities_fit", "Hat Oldenburg das schon?", ("cities_fit",), "cities:fit"),
            Step("cities_idea_fit", "… je Idee", ("cities_idea_fit",), "cities:idea_fit"),
        ),
    ),
    Pipeline(
        key="plans", title="Pläne der Stadt",
        summary="Liest Fachpläne und Berichte und verfolgt, was aus Maßnahmen und Aufträgen wurde.",
        steps=(
            Step("plan_key_points", "Was im Plan steht", ("plan_key_points",), "council.plan_judge:MODEL"),
            Step("plan_reports", "Berichte in einem Satz", ("plan_reports",), "council.plan_judge:MODEL"),
            Step("plan_measure_status", "Stand je Maßnahme", ("plan_measure_status",), "council.plan_judge:MODEL"),
            Step("plan_link_judgement", "Bezug einer Vorlage", ("plan_link_judgement",), "council.plan_judge:MODEL"),
            Step("plan_mandate_check", "Folge eines Ratsauftrags", ("plan_mandate_check",),
                 "council.plan_judge:MODEL"),
            Step("plan_plain", "Einfache Sprache und Fragen", ("plan_plain",), "council.plan_judge:MODEL"),
        ),
    ),
    Pipeline(
        key="budget", title="Haushaltsentwurf",
        summary="Liest Befunde aus dem Haushaltsentwurf und prüft jeden gegen die Zahlen.",
        steps=(
            Step("budget_findings", "Befunde", ("budget_findings",), "council.budget_findings:MODEL"),
            Step("budget_findings_verify", "Prüfung", ("budget_findings_verify",),
                 "council.budget_findings:VERIFY_MODEL"),
        ),
    ),
    Pipeline(
        key="topics", title="Themen & Rückblicke",
        summary="Erkennt Themen und Akteure, beschreibt sie und schreibt Themenfeld-Rückblicke.",
        steps=(
            Step("entity_ner", "Entitäten erkennen", ("entity_ner",), "council.entities:MODEL"),
            Step("entity_description", "Entitäten beschreiben", ("entity_description",), "council.entities:MODEL"),
            Step("entity_duplicates", "Dubletten", ("entity_duplicates",), "council.aliases:MODEL"),
            Step("topic_auto_description", "Themen beschreiben", ("topic_auto_description",),
                 "council.topic_intel:MODEL"),
            Step("vagueness_check", "Vagheit eines Themas", ("vagueness_check",), "council.topic_intel:MODEL"),
            Step("field_recap", "Themenfeld-Rückblick", ("field_recap",), "council.recaps:MODEL"),
            Step("goal_rating", "Ziel-Bewertung", ("goal_rating",), "council.goals:MODEL"),
        ),
    ),
    Pipeline(
        key="quiz", title="Quiz",
        summary="Erzeugt Quizfragen aus Beschlüssen, prüft sie und benotet Einsprüche.",
        steps=(
            Step("quiz_generation", "Fragen erzeugen", ("quiz_generation",), "council.quiz:MODEL"),
            Step("quiz_verify", "Fragen prüfen", ("quiz_verify",), "council.quiz:VERIFY_MODEL"),
            Step("quiz_motion_context", "Anträge beschreiben", ("quiz_motion_context",),
                 "council.quiz_formats:MOTION_MODEL"),
            Step("quiz_appeal", "Einsprüche benoten", ("quiz_appeal",), "council.quiz:APPEAL_MODEL"),
        ),
    ),
    Pipeline(
        key="stories", title="Fundstück & Zahl der Woche",
        summary="Schreibt die Karten „Fundstück des Tages“ und „Zahl der Woche“.",
        steps=(
            Step("daily_find_story", "Fundstück des Tages", ("daily_find_story",), "council.fundstueck:MODEL"),
            Step("week_number", "Zahl der Woche", ("week_number",), "council.week_number:MODEL"),
        ),
    ),
)

#: Feature-Namen, die zu keiner Pipeline des Produkts gehören — mit Grund.
OUTSIDE_PIPELINES: dict[str, str] = {
    "quality_judge": "der Richter der Gold-Läufe (scripts/eval_deep_gold.py), kein Produkt-Feature",
}

_FAKTEN_KZ = (Metric("kontextfehler", "Kontextfehler", "count", False),
              Metric("modellfehler", "Modellfehler", "count", False))

BENCHMARKS: tuple[Benchmark, ...] = (
    # ---- Frag den Rat ----------------------------------------------------- #
    Benchmark(
        key="ask-gold", pipeline="ask", title="Gold-Fälle",
        measures="Wie viele Pflichtfakten die Antwort trifft — über den echten Weg, gegen die echten Daten.",
        metric=Metric("coverage", "Abdeckung"),
        secondary=(Metric("passed", "bestanden", "count"),
                   Metric("context_recall", "Kontext-Recall"),
                   Metric("omitted", "weggelassen", "count", False),
                   Metric("median_s", "Dauer (Median)", "seconds", False)),
        steps=("qa_analysis", "qa_query_expansion", "retrieval", "qa_nachrecherche", "qa_answer"),
        cases=("eval/cases_deep_gold.json",),
        truth="Pflichtfakten und verbotene Behauptungen je Frage, von Hand aus Beschlüssen und Debatten belegt",
        judge="anthropic/claude-opus-5.5", runs_on="server",
        command="gh workflow run ops-gold.yml -f umgebung=prod -f weg=ask -f label=<name>",
        noise="Derselbe Code ergab 51 % und 45 % (17.10.2026); unter ~5 Pp braucht es zwei Läufe je "
              "Seite. Der Kontext-Recall braucht keinen Richter und streut nicht.",
        log="docs/gold-messbuch.md",
    ),
    Benchmark(
        key="ki-frage", pipeline="ask", title="Suche & Zitate",
        measures="Ob die Antwort mindestens einen erwarteten Beschluss zitiert — die ganze Kette samt Suche.",
        metric=_q("zitiert Erwartetes"),
        secondary=(Metric("retrieval_hit_rate", "Suche: Treffer"), Metric("mrr", "Suche: MRR", "ratio"), _hard()),
        steps=("qa_analysis", "qa_query_expansion", "retrieval", "qa_answer"),
        cases=("eval/cases_qa.json",), truth="erwartete Beschlüsse je Frage, von Hand gelabelt",
        runs_on="server", command="python eval/run_qa.py --rate-missing --save",
        hard="Antworten, die mit einer Formalie (Tragweite ≤ 15) anfangen",
    ),
    Benchmark(
        key="ki-frage-antwort", pipeline="ask", title="Antwort bei festem Kontext",
        measures="Wie viele der erwarteten Beschlüsse im Kontext die Antwort zitiert — nur das Antwortmodell.",
        metric=_q("Abdeckung"), secondary=(_hard(),), steps=("qa_answer",),
        cases=("eval/cases_qa.json",), truth="erwartete Beschlüsse je Frage, Kontext mit BM25-Ablenkern",
        command=_p("ki-frage-antwort"),
        hard="erfundene Zahl oder eine Quelle, die nicht im Kontext stand",
    ),
    Benchmark(
        key="ki-frage-routing", pipeline="ask", title="Analyse & Routing",
        measures="Ob Fragetyp, Plan, Kanäle, Haushaltsfacetten und Klarheitsurteil zugleich stimmen.",
        metric=_q("alles richtig"), secondary=(_hard(),), steps=("qa_analysis",),
        cases=("eval/cases_qa_routing.json",), truth="erlaubte Typen und Kanäle je Frage, von Hand",
        command=_p("ki-frage-routing"), hard="beantwortbare Fragen, die mit einer Rückfrage abgewiesen wurden",
    ),
    Benchmark(
        key="fakten-rat", pipeline="ask", also=("lotti",), title="Fakten: Ratsfragen",
        measures="Ob der Goldfakt im Prompt stand (unter dem richtigen Jahr) und in der Antwort steht.",
        metric=_q("ok"), secondary=(*_FAKTEN_KZ, _hard()), steps=("qa_answer", "assistant_explain"),
        cases=("eval/cases_fakten_rat.json",), truth="Goldwerte aus SQL (eval/build_fakten_rat.py), nie aus einer Antwort",
        command=_p("fakten-rat"), hard="Zahl, die weder im Prompt steht noch sich daraus rechnen lässt",
        log="docs/fakten-eval.md",
    ),
    Benchmark(
        key="fakten-haushalt", pipeline="ask", also=("lotti",), title="Fakten: Haushaltsfragen",
        measures="Ob der Goldfakt im Prompt stand (unter dem richtigen Jahr) und in der Antwort steht.",
        metric=_q("ok"), secondary=(*_FAKTEN_KZ, _hard()), steps=("qa_answer", "assistant_explain"),
        cases=("eval/cases_fakten_haushalt.json",),
        truth="Goldwerte aus SQL (eval/build_fakten_haushalt.py), nie aus einer Antwort",
        command=_p("fakten-haushalt"), hard="Zahl, die weder im Prompt steht noch sich daraus rechnen lässt",
        log="docs/fakten-eval.md",
    ),
    Benchmark(
        key="punkt-bezug", pipeline="ask", title="Bezug auf den Tagesordnungspunkt",
        measures="Ob Fragen ohne Gegenstand („Und was kostet das?“) mit Bezug-Chip den richtigen Punkt beantworten.",
        metric=Metric("with_ref", "mit Bezug richtig"), secondary=(Metric("without_ref", "ohne Bezug richtig"),),
        steps=("qa_analysis", "qa_answer"), truth="der Punkt, von dem aus gefragt wird",
        command="python eval/run_punkt_bezug.py",
    ),
    Benchmark(
        key="qualitaet-vorher-nachher", pipeline="ask", title="Ganze Antworten: vorher gegen nachher",
        measures="Welcher von zwei Code-Ständen die bessere Antwort schreibt — blind, je Frage.",
        metric=Metric("win_rate", "nachher besser"), secondary=(Metric("ties", "gleich", "count"),),
        steps=("qa_analysis", "retrieval", "qa_answer"),
        truth="ein Richter-Modell vergleicht zwei eingefrorene Antworten", judge="google/gemini-3.5-flash",
        runs_on="server", command="python eval/quality_qa.py --erzeugen vorher|nachher, dann --vergleichen",
    ),
    Benchmark(
        key="akten", pipeline="ask", title="Akten-Abdeckung",
        measures="Ob jeder Beleg eines Gold-Falls in derselben Akte liegt wie sein Kernbeschluss — ohne Modell.",
        metric=Metric("coverage", "Belege in der Akte"), steps=("retrieval",),
        cases=("eval/cases_deep_gold.json",), truth="die Belege der Gold-Fälle",
        command="python eval/run_akten.py",
    ),
    Benchmark(
        key="ortserkennung", pipeline="ask", title="Ortserkennung in Fragen",
        measures="Ob eine Frage den gemeinten Ort bekommt — und eine Frage ohne Ort keinen.",
        metric=Metric("accuracy", "richtig"), steps=("qa_analysis",),
        cases=("eval/cases_ortserkennung.json",), truth="Alltagssprache, Teilwörter, Tippfehler, von Hand",
        command="python eval/run_ortserkennung.py",
    ),
    # ---- Gründliche Recherche --------------------------------------------- #
    Benchmark(
        key="deep-gold", pipeline="deep", title="Gold-Fälle",
        measures="Wie viele Pflichtfakten der Bericht trifft — dieselben Fälle wie Frag den Rat.",
        metric=Metric("coverage", "Abdeckung"), secondary=(Metric("passed", "bestanden", "count"),),
        steps=("deep_decomposition", "retrieval", "deep_report"), cases=("eval/cases_deep_gold.json",),
        truth="Pflichtfakten und verbotene Behauptungen je Frage, von Hand belegt",
        judge="anthropic/claude-opus-5.5", runs_on="server",
        command="gh workflow run ops-gold.yml -f umgebung=prod -f weg=deep -f label=<name>",
    ),
    Benchmark(
        key="fakten-deep", pipeline="deep", title="Fakten: Bericht",
        measures="Ob der Goldfakt im Prompt des Berichts stand und im Bericht steht.",
        metric=_q("ok"), secondary=(*_FAKTEN_KZ, _hard()), steps=("deep_report",),
        cases=("eval/cases_fakten_haushalt.json",), truth="Goldwerte aus SQL, nie aus einer Antwort",
        command="python eval/run_fakten.py --kanal deep", log="docs/fakten-eval.md",
    ),
    # ---- Lotti ------------------------------------------------------------ #
    Benchmark(
        key="lotti", pipeline="lotti", title="Erklärungen",
        measures="Anteil der Erklärungen ganz ohne Befund: Weg, Weiterreichung, Zusagen, Zahlen, Länge.",
        metric=_q("ohne Befund"), secondary=(_hard(),), steps=("assistant_explain",),
        cases=("eval/cases_assistant.json",), truth="Erwartungen je Fall, deterministisch geprüft — kein Richter",
        command=_p("lotti"), hard="erfundene Zahl, befolgte Injektion, verletzte Zusage, falscher Weg",
        log="docs/modell-pruefstand.md",
    ),
    Benchmark(
        key="lotti-selbstpruefung", pipeline="lotti", title="Selbstprüfung",
        measures="Wie oft der Prüfer bekannte Mängel findet und wie oft er gute Antworten beanstandet.",
        metric=Metric("hit_rate", "Mängel gefunden"),
        secondary=(Metric("false_alarms", "Fehlalarme", "count", False),), steps=("assistant_check",),
        cases=("eval/cases_selbstpruefung_laien.json",), truth="Antworten mit bekanntem Urteil",
        command="python eval/run_selbstpruefung.py", log="docs/lotti-selbstpruefung.md",
    ),
    # ---- Benachrichtigungen ------------------------------------------------ #
    Benchmark(
        key="watcher", pipeline="notify", title="Themen-Wächter",
        measures="F1 über die Paare Thema ↔ Tagesordnungspunkt — zu viel und zu wenig zugleich.",
        metric=_q("F1"), secondary=(_hard(),), steps=("council_watcher",),
        cases=("eval/cases_watcher.json",), truth="erwartete Paare je Sitzung, von Hand",
        command=_p("watcher"), hard="Fehlalarme: jemand würde grundlos benachrichtigt",
    ),
    Benchmark(
        key="ausschuss", pipeline="notify", title="Routine-Filter der Ausschuss-Mail",
        measures="Ob eine Tagesordnung echten Inhalt hat oder nur Routine — beide Fehler kosten.",
        metric=_q("Trefferquote"), secondary=(_hard(),), steps=("committee_summary",),
        cases=("eval/cases_committee.json",), truth="ja/nein je Tagesordnung, von Hand",
        command=_p("ausschuss"), hard="Sitzungen mit Inhalt, die als Routine verschluckt wurden",
    ),
    Benchmark(
        key="tragweite-tagesordnung", pipeline="notify", title="Tragweite je Tagesordnungspunkt",
        measures="Kosten und Latenz an echten Wochen und die Spitzenpunkte zum Nebeneinanderlegen — ohne Goldwerte.",
        metric=Metric(QUALITY, "zum Lesen", "none"), steps=("impact_rating_agenda",),
        truth="keine — die Suite zeigt die Spitzenpunkte zum Vergleich", command=_p("tragweite-tagesordnung"),
    ),
    # ---- Beschlüsse aufbereiten -------------------------------------------- #
    Benchmark(
        key="tragweite", pipeline="decisions", title="Tragweite eines Beschlusses",
        measures="Ob die Bewertung im richtigen Band liegt — gegen 30 handbewertete Beschlüsse.",
        metric=_q("Band getroffen"), secondary=(Metric("rho", "Spearman ρ", "ratio"),), steps=("impact_rating",),
        cases=("scripts/golden_impact.json",), truth="30 Beschlüsse, von Hand bewertet",
        command=_p("tragweite"),
    ),
    Benchmark(
        key="ergebnis-texte", pipeline="decisions", title="Kurzfassung kennt das Ergebnis",
        measures="Ob die Kurzfassung eines abgelehnten Antrags ihn nicht als gefassten Beschluss erklärt.",
        metric=Metric("passed_share", "bestanden"), steps=("simple_summary",),
        truth="Ergebnis aus der Niederschrift, buchstäblich geprüft", command="python eval/run_ergebnis_texte.py",
    ),
    Benchmark(
        key="antraege", pipeline="decisions", title="Änderungsanträge lesen",
        measures="Antragsteller, Ziel, Muster, alt/neu und Fassungsbezug je Antrag.",
        metric=Metric("accuracy", "richtig"), steps=("motion_extract",), cases=("eval/motions_gold.json",),
        truth="von Hand gelesene Anträge", command="python eval/run_motions.py",
    ),
    Benchmark(
        key="zuordnung", pipeline="decisions", title="Antrag ↔ Teilabstimmung",
        measures="Ob jeder Antrag der richtigen Teilabstimmung zugeordnet wird — ohne Modell.",
        metric=Metric("accuracy", "richtig"), steps=("minutes_extraction",),
        truth="Handprüfung Label gegen Titel", command="python eval/run_zuordnung.py",
    ),
    # ---- Orte & Viertel ---------------------------------------------------- #
    Benchmark(
        key="orte", pipeline="places", title="Ortszuordnung",
        measures="F1 über die Orte je Beschluss (Regeln + Modell, wie im Backfill).",
        metric=_q("F1"), secondary=(_hard(),), steps=("decision_places",),
        cases=("eval/cases_locations.json",), truth="positive und negative Goldfälle, von Hand",
        command=_p("orte"), hard="Orte, die im Beschluss nicht vorkommen",
    ),
    Benchmark(
        key="viertel", pipeline="places", title="Mein Viertel",
        measures="Ob ein Beschluss wirklich im Viertel liegt (Richter-Stufe).",
        metric=_q("richtig"), secondary=(_hard(),), steps=("district_projects",),
        cases=("eval/cases_district.json",), truth="gespeichertes Urteil, jeder Fall von Hand nachgelesen",
        command=_p("viertel"), hard="„im Viertel“ für einen Beschluss, der woanders liegt",
    ),
    # ---- Wortbeiträge ------------------------------------------------------ #
    Benchmark(
        key="wortbeitraege", pipeline="debates", title="Wortbeiträge aus Abschnitten",
        measures="F1 über die Beiträge je Person (Name und Anzahl) in Protokollabschnitten.",
        metric=_q("F1"), secondary=(_hard(),), steps=("speeches",), cases=("eval/cases_speeches.json",),
        truth="Beitrags-Einleitungen im Protokoll ∩ gespeicherte Extraktion", command=_p("wortbeitraege"),
        hard="Redner*innen, deren Name im Abschnitt gar nicht vorkommt",
    ),
    Benchmark(
        key="wortbeitraege-protokolle", pipeline="debates", title="Wortbeiträge aus ganzen Niederschriften",
        measures="F1 über die Wortmeldungen je Person in ganzen Protokollen, Fenster wie im Cron.",
        metric=_q("F1"), secondary=(_hard(),), steps=("speeches",),
        cases=("eval/cases_speeches_protokolle.json",), truth="von Hand nachgelesene Niederschriften",
        command=_p("wortbeitraege-protokolle"), hard="Redner*innen, deren Name im Protokoll nicht vorkommt",
    ),
    Benchmark(
        key="punkt-argumente", pipeline="debates", title="Argumente zum Punkt",
        measures="Streitpunkte und Argumente je Punkt zum Nachlesen — bei einer Leerprobe darf nichts entstehen.",
        metric=Metric("reading", "zum Lesen", "none"), secondary=(Metric("shown", "Reiter sichtbar"),),
        steps=("item_arguments",),
        cases=("eval/punkt_argumente_gold.json",), truth="20 feste Punkte mit Debatte, von Hand gelesen",
        command="python eval/run_punkt_argumente.py", log="docs/plan-punkt-argumente.md",
    ),
    # ---- Live ------------------------------------------------------------- #
    Benchmark(
        key="transkription", pipeline="live", title="Transkription",
        measures="Wort-F1 gegen einen Referenztext je Audio-Stück.",
        metric=_q("Wort-F1"), secondary=(_hard(),), steps=("livestream_transcript",),
        truth="Referenztexte je Audio-Stück — gibt es noch nicht", command=_p("transkription"),
        hard="Stücke ohne Rede, zu denen Text durch die Wächter kommt",
    ),
    Benchmark(
        key="live-verfolgung", pipeline="live", title="Welcher Punkt läuft",
        measures="Anteil der Fenster mit dem richtigen Tagesordnungspunkt am Fensterende.",
        metric=_q("richtig"), secondary=(_hard(),), steps=("live_top_tracker",),
        cases=("eval/cases_live_tracker.json",), truth="30 Fenster aus zwei Ratssitzungen, von Hand gelesen",
        command=_p("live-verfolgung"), hard="ein Punkt, den es auf der Tagesordnung nicht gibt",
    ),
    Benchmark(
        key="video-ergebnisse", pipeline="live", title="Ergebnisse aus dem Video",
        measures="Anteil der protokollierten Ergebnisse, die der strenge Weg richtig ausgibt.",
        metric=_q("richtig"), secondary=(_hard(),), steps=("video_results",), cases=("eval/cases_video.json",),
        truth="die Niederschrift", command=_p("video-ergebnisse"),
        hard="falsche Ergebnisse — die Zusage des Features ist null",
    ),
    # ---- Vorlagen & Sitzungen --------------------------------------------- #
    Benchmark(
        key="dossier", pipeline="templates", title="Dossier je Vorlage",
        measures="Pflichtfakten im richtigen Abschnitt, Status leerer Felder, keine verbotenen Inhalte.",
        metric=Metric("required_facts", "Pflichtfakten"), steps=("template_dossier",),
        cases=("eval/dossier_gold.json",), truth="von Hand aus den Vorlagen", command="python eval/run_dossier.py",
        log="docs/plan-vorlagen-aufbereiten.md",
    ),
    Benchmark(
        key="spezialleser", pipeline="templates", title="Spezialleser",
        measures="Ob die Leser für Sonderformate die erwarteten Felder aus den PDFs holen — ohne Modell.",
        metric=Metric("accuracy", "richtig"), steps=("attachment_ocr",), cases=("eval/spezialleser_gold.json",),
        truth="von Hand aus den PDFs", command="python eval/run_spezialleser.py",
    ),
    Benchmark(
        key="sitzung-satz", pipeline="templates", title="Satz zur Sitzung",
        measures="Gerechneter gegen geschriebenen Satz an echten Sitzungen — zum Lesen, ohne Kennzahl.",
        metric=Metric("reading", "zum Lesen", "none"), steps=("session_summary",),
        truth="Gegenüberstellung zum Lesen", command="python eval/run_sitzung_satz.py",
    ),
    # ---- Social ----------------------------------------------------------- #
    Benchmark(
        key="social-text", pipeline="social", title="Kartentext",
        measures="Anteil der Punkte, deren erster Entwurf die Netze des Betriebs besteht.",
        metric=_q("erster Entwurf sauber"), secondary=(_hard(),), steps=("social_card_text",),
        cases=("eval/cases_social.json",), truth="die Netze des Betriebs (kritiker.pruefe)",
        command=_p("social-text"), hard="Zahl ohne Beleg, Wertung, vorweggenommenes Ergebnis",
    ),
    Benchmark(
        key="kritiker", pipeline="social", title="Kritiker",
        measures="Ob der Kritiker belegte Sätze durchlässt und verfälschte verwirft.",
        metric=_q("richtig"), secondary=(_hard(),), steps=("social_critic",), cases=("eval/cases_critic.json",),
        truth="9 belegte, 9 gezielt verfälschte Sätze", command=_p("kritiker"),
        hard="verfälschte Sätze, die als gedeckt durchgehen",
    ),
    # ---- Städtevergleich -------------------------------------------------- #
    Benchmark(
        key="cities-einordnung", pipeline="cities", title="Taugt die Vorlage?",
        measures="„Taugt / taugt nicht“ richtig — die eine Entscheidung, die das Produkt trifft.",
        metric=_q("richtig"), steps=("cities_classify",), cases=("eval/cases_cities_transfer.json",),
        truth="45 Vorlagen aus vier Städten, von Hand eingeordnet", command=_p("cities-einordnung"),
    ),
    Benchmark(
        key="cities-fit", pipeline="cities", title="Hat Oldenburg das schon?",
        measures="Status (drei Klassen) richtig, Belege nicht erfunden.",
        metric=_q("Status richtig"), secondary=(_hard(),), steps=("cities_fit",),
        cases=("eval/cases_cities_fit.json",), truth="40 Fälle mit Belegen, von Hand", command=_p("cities-fit"),
        hard="erfundene Beleg-Kennungen + „vorhanden“ für etwas, das fehlt",
    ),
    Benchmark(
        key="cities-idee", pipeline="cities", title="Hat Oldenburg die Idee schon?",
        measures="Stand Oldenburgs je Idee statt je Vorlage.",
        metric=Metric("accuracy", "richtig"), steps=("cities_idea_fit",), cases=("eval/cases_cities_idea_fit.json",),
        truth="von Hand", runs_on="server", command="python eval/run_cities_idea_fit.py",
    ),
    Benchmark(
        key="cities-aufwand", pipeline="cities", title="Was kostet die Idee?",
        measures="Aufwandsklasse richtig.", metric=_q("richtig"), secondary=(_hard(),), steps=("cities_effort",),
        cases=("eval/cases_cities_effort.json",), truth="von Hand", command=_p("cities-aufwand"),
        hard="Adressat genannt, wo die Stadt selbst entscheidet",
    ),
    Benchmark(
        key="cities-richtung", pipeline="cities", title="Wollte der Rat die Idee?",
        measures="Richtung (dafür, dagegen, prüfen) richtig.", metric=_q("richtig"), secondary=(_hard(),),
        steps=("cities_stance",), cases=("eval/cases_cities_stance.json",), truth="von Hand",
        command=_p("cities-richtung"), hard="verfehlte „dagegen“-Fälle",
    ),
    Benchmark(
        key="cities-begruendung", pipeline="cities", title="Warum ging es so aus?",
        measures="Abstimmungsergebnis richtig wiedergegeben, keine erfundene Begründung.",
        metric=_q("Ergebnis richtig"), secondary=(_hard(),), steps=("cities_reason",),
        cases=("eval/cases_cities_reason.json",), truth="36 echte Abschnitte", command=_p("cities-begruendung"),
        hard="erfundene Begründungen + Personennamen",
    ),
    Benchmark(
        key="cities-belege", pipeline="cities", title="Belegsuche",
        measures="Ob die Belegsuche findet, was ein Mensch als Beleg bezeichnet hat — ohne Modell.",
        metric=Metric("recall", "gefunden"), steps=("cities_evidence_terms",),
        cases=("eval/cases_cities_fit.json",), truth="die Belege der Fit-Fälle",
        command="python eval/run_cities_evidence.py",
    ),
    Benchmark(
        key="cities-liste", pipeline="cities", title="Die Liste oben",
        measures="Ob die zwanzig obersten Einträge zwanzig sind, die jemand sehen will.",
        metric=Metric("precision", "gewollt"), steps=("cities_fit", "cities_idea_fit"),
        cases=("eval/cases_cities_list.json",), truth="von Hand bewertete Einträge",
        command="python eval/run_cities_list.py",
    ),
    # ---- Pläne ------------------------------------------------------------ #
    Benchmark(
        key="plaene-golden", pipeline="plans", title="Golden-Sets der Pläne",
        measures="Ob Maßnahmen, Nennungen und Bezüge mit wörtlichem Zitat gefunden werden.",
        metric=Metric("accuracy", "richtig"),
        steps=("plan_measure_status", "plan_link_judgement", "plan_mandate_check"),
        cases=("eval/cases_plan_mobility.json", "eval/cases_plan_mandates.json", "eval/cases_plan_links.json"),
        truth="von Hand aus den Berichten", command="python scripts/plan_modell.py <plan> --golden",
    ),
)

_PIPELINES: dict[str, Pipeline] = {p.key: p for p in PIPELINES}
_BENCHMARKS: dict[str, Benchmark] = {b.key: b for b in BENCHMARKS}


def pipeline(key: str) -> Pipeline:
    return _PIPELINES[key]


def benchmark(key: str) -> Benchmark:
    return _BENCHMARKS[key]


def benchmarks_of(pipeline_key: str) -> list[Benchmark]:
    """Die Benchmarks einer Pipeline — eigene zuerst, mitmessende danach."""
    own = [b for b in BENCHMARKS if b.pipeline == pipeline_key]
    return own + [b for b in BENCHMARKS if pipeline_key in b.also]


def feature_owner() -> dict[str, str]:
    """Feature-Name → Pipeline. Doppelte Zuordnung fängt der Test."""
    return {f: p.key for p in PIPELINES for s in p.steps for f in s.features}


def step_of_feature(pipeline_key: str | None = None) -> dict[str, str]:
    """Feature-Name → Stufen-Schlüssel (für Läufe, die Modelle je Feature kennen)."""
    return {f: s.key for p in PIPELINES if pipeline_key in (None, p.key) for s in p.steps for f in s.features}


# --------------------------------------------------------------------------- #
# Der Lauf
# --------------------------------------------------------------------------- #

def dataset_state(path: str, root: Path = ROOT) -> dict[str, Any] | None:
    """Prüfsumme und Fallzahl einer Falldatei — ``None``, wenn es sie nicht gibt.

    Die Prüfsumme steht im Lauf; ändert sich die Datei danach, sagt
    :func:`assess` „Fälle seither geändert". Die Fallzahl ist die Länge der
    Liste (oder von ``cases``/``faelle``, falls die Datei ein Objekt ist).
    """
    datei = root / path
    if not datei.is_file():
        return None
    roh = datei.read_bytes()
    n: int | None = None
    try:
        inhalt: Any = json.loads(roh)
        if isinstance(inhalt, dict):
            inhalt = next((inhalt[k] for k in ("cases", "faelle", "golden") if isinstance(inhalt.get(k), list)), None)
        if isinstance(inhalt, list):
            n = len(inhalt)  # pyright: ignore[reportUnknownArgumentType]
    except ValueError:
        pass
    return {"path": path, "sha256": hashlib.sha256(roh).hexdigest()[:12], "cases": n}


def code_state(root: Path = ROOT) -> dict[str, Any] | None:
    """Commit, Zweig und ob der Arbeitsbaum Änderungen trug — ``None`` ohne Git.

    Auf den Servern gibt es kein ``.git`` (der Deploy schickt es nicht mit);
    dort setzt der Aufrufer ``code`` selbst oder lässt es leer.
    """
    def git(*args: str) -> str | None:
        try:
            aus = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        return aus.stdout.strip() if aus.returncode == 0 else None

    commit = git("rev-parse", "--short=9", "HEAD")
    if not commit:
        return None
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dirty": bool(status)}


def detect_environment() -> str:
    """``prod``/``dev`` auf den Servern (aus ``APP_BASE_URL``), ``ci`` in Actions, sonst ``local``."""
    if os.environ.get("GITHUB_ACTIONS"):
        return "ci"
    basis = os.environ.get("APP_BASE_URL", "")
    if "dev.ratslotse.de" in basis:
        return "dev"
    if re.search(r"//(www\.)?ratslotse\.de", basis):
        return "prod"
    return "local"


def new_run(benchmark_key: str, *, metrics: dict[str, Any], started_at: datetime | None = None,
            label: str | None = None, environment: str | None = None,
            models: dict[str, str] | None = None, judge: str | None = None, variant: str | None = None,
            flags: list[str] | None = None, cases: str | None = None, sample: int | None = None,
            data: str | None = None, cost_usd: float | None = None, duration_s: float | None = None,
            latency_ms: dict[str, int | None] | None = None, purpose: str | None = None,
            conclusion: str | None = None, comparable: bool = True, note: str | None = None,
            raw: str | None = None, raw_extra: list[str] | None = None, source: str = "",
            code: dict[str, Any] | None = None, root: Path = ROOT) -> dict[str, Any]:
    """Ein Lauf im Format :data:`SCHEMA` — Code-Stand und Fälle füllt die Funktion selbst.

    ``models``: Stufe (``Step.key``) → Modell, das dort wirklich geantwortet hat.
    ``purpose``: warum gemessen wurde (die Frage, die der Lauf beantworten soll).
    ``conclusion``: was daraus folgt — auch „kein Unterschied“ ist ein Fazit.
    ``comparable=False``: ältere Fälle oder Regeln, nicht mit heutigen Läufen
    zu vergleichen (die Prüfstand-Unterordner wie ``vor-p4a/``).
    ``raw``: das Rohergebnis — ein Pfad im Repo oder ``server:<umgebung>:<pfad>``
    für Dateien, die nur auf einem Server liegen. ``raw_extra``: weitere Dateien
    des Laufs (Berichte, Eingaben).
    """
    b = benchmark(benchmark_key)
    pfad = cases or (b.cases[0] if b.cases else None)
    dataset = dataset_state(pfad, root) if pfad else None
    if sample:
        dataset = {**(dataset or {"path": None, "sha256": None, "cases": None}), "sample": sample}
    return {
        "schema": SCHEMA,
        "benchmark": benchmark_key,
        "label": label,
        "started_at": (started_at or datetime.now()).isoformat(timespec="seconds"),
        "environment": environment or detect_environment(),
        "code": code if code is not None else code_state(root),
        "models": models or {},
        "judge": judge,
        "variant": variant,
        "flags": flags,
        "dataset": dataset,
        "data": data,
        "metrics": metrics,
        "cost_usd": None if cost_usd is None else round(cost_usd, 6),
        "duration_s": duration_s,
        "latency_ms": latency_ms,
        "purpose": purpose,
        "conclusion": conclusion,
        "comparable": comparable,
        "note": note,
        "raw": raw,
        "raw_extra": raw_extra,
        "source": source,
    }


_REQUIRED = ("schema", "benchmark", "started_at", "environment", "models", "metrics", "comparable")


def problems(record: dict[str, Any]) -> list[str]:
    """Was an einem Lauf nicht stimmt — leer heißt: gültig."""
    aus = [f"Feld fehlt: {k}" for k in _REQUIRED if k not in record]
    if aus:
        return aus
    if record["schema"] != SCHEMA:
        aus.append(f"schema {record['schema']!r}, erwartet {SCHEMA}")
    b = _BENCHMARKS.get(record["benchmark"])
    if b is None:
        return [*aus, f"unbekannter Benchmark {record['benchmark']!r} (kern/benchmarks.py::BENCHMARKS)"]
    try:
        datetime.fromisoformat(record["started_at"])
    except (TypeError, ValueError):
        aus.append(f"started_at ist kein ISO-Zeitpunkt: {record['started_at']!r}")
    if record["environment"] not in ENVIRONMENTS:
        aus.append(f"environment {record['environment']!r} nicht in {ENVIRONMENTS}")
    metrics = record["metrics"]
    if not isinstance(metrics, dict):
        aus.append("metrics ist kein Objekt")
    elif b.metric.unit != "none" and b.metric.key not in metrics:
        aus.append(f"Hauptkennzahl {b.metric.key!r} fehlt in metrics")
    steps = {s.key for p in (b.pipeline, *b.also) for s in pipeline(p).steps}
    models = record["models"]
    if not isinstance(models, dict):
        aus.append("models ist kein Objekt")
    else:
        aus += [f"models: unbekannte Stufe {k!r}" for k in models if k not in steps]  # pyright: ignore[reportUnknownVariableType]
    return aus


def run_filename(record: dict[str, Any]) -> str:
    stempel = datetime.fromisoformat(record["started_at"]).strftime("%Y%m%d-%H%M%S")
    modelle = list((record.get("models") or {}).values())
    teile = ([record["label"]] if record.get("label") else
             [modelle[-1] if modelle else "", record.get("variant") or ""])
    slug = re.sub(r"[^a-z0-9]+", "-", " ".join(t for t in teile if t).lower()).strip("-")[:60]
    return f"{stempel}{'-' + slug if slug else ''}.json"


def write_run(record: dict[str, Any], directory: Path | None = None) -> Path:
    """Den Lauf ablegen — lokal nach ``eval/runs/``, auf einem Server nach ``data/eval_runs/``."""
    fehler = problems(record)
    if fehler:
        raise ValueError("Lauf ungültig: " + "; ".join(fehler))
    if directory is None:
        directory = REPO_RUNS if record["environment"] in ("local", "ci") else SERVER_RUNS
    ziel = directory / record["benchmark"] / run_filename(record)
    n = 2
    while ziel.exists():
        ziel = ziel.with_name(f"{ziel.stem.rsplit('~', 1)[0]}~{n}.json")
        n += 1
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ziel


def load_runs(directory: Path, origin: str = "repo") -> list[dict[str, Any]]:
    """Alle Läufe unter ``directory``; jeder trägt ``id`` und ``origin`` dazu.

    Ein kaputter oder ungültiger Lauf wird nicht verschwiegen: Er kommt mit
    ``problems`` zurück, das Panel zeigt ihn an, und der Test wird rot.
    """
    aus: list[dict[str, Any]] = []
    if not directory.is_dir():
        return aus
    for pfad in sorted(directory.glob("*/*.json")):
        rel = pfad.relative_to(directory).as_posix()
        try:
            rec: Any = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            aus.append({"id": rel, "origin": origin, "problems": [f"nicht lesbar: {e}"]})
            continue
        if not isinstance(rec, dict):
            aus.append({"id": rel, "origin": origin, "problems": ["kein JSON-Objekt"]})
            continue
        rec = dict(rec)  # pyright: ignore[reportUnknownArgumentType]
        rec["id"], rec["origin"] = rel.removesuffix(".json"), origin
        fehler = problems(rec)
        if fehler:
            rec["problems"] = fehler
        aus.append(rec)
    return aus


# --------------------------------------------------------------------------- #
# Wie aktuell ist eine Messung?
# --------------------------------------------------------------------------- #

@dataclass
class Assessment:
    #: ``ok`` · ``stale`` (Messung da, aber überholt) · ``none`` (nie gemessen)
    status: str
    latest: dict[str, Any] | None = None
    previous: dict[str, Any] | None = None
    #: Gründe, warum die jüngste Messung nicht mehr für heute spricht.
    reasons: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


def _value(run: dict[str, Any], key: str) -> Any:
    return (run.get("metrics") or {}).get(key)


def assess(b: Benchmark, runs: list[dict[str, Any]], *, current_models: dict[str, str | None],
           current_cases: dict[str, str | None], today: date | None = None) -> Assessment:
    """Status eines Benchmarks aus seinen Läufen und dem heutigen Stand.

    **Maßgeblich ist der jüngste Lauf mit der heutigen Besetzung** — nicht
    einfach der jüngste: Der Prüfstand misst Kandidaten (Haiku 5.5 gegen
    Luna), und deren Lauf sagt nichts darüber, wie gut die Pipeline gerade
    IST. Heutige Besetzung heißt: vergleichbar, ohne ``variant`` (Denkstufe,
    Tarif, A/B-Arm), und jede gemessene Stufe mit bekanntem Modell hat das
    Modell von heute.

    Gibt es keinen solchen Lauf, ist die Messung überholt (``model``: zuletzt
    mit X gemessen, heute Y). Gibt es einen, ist er trotzdem überholt, wenn
    sich die Falldatei seither geändert hat (``cases``, nur mit Prüfsumme)
    oder er älter als :data:`STALE_AFTER_DAYS` ist (``age``).

    ``current_models``: Stufe → heutiges Modell (``None`` = unbekannt, zählt
    nicht). ``current_cases``: Pfad → heutige Prüfsumme.
    """
    heute = today or date.today()
    eigene = sorted((r for r in runs if r.get("benchmark") == b.key and not r.get("problems")),
                    key=lambda r: r["started_at"])
    if not eigene:
        return Assessment("none")
    mit_wert = [r for r in eigene if r.get("comparable", True)
                and (b.metric.unit == "none" or _value(r, b.metric.key) is not None)]
    if not mit_wert:
        return Assessment("stale", latest=eigene[-1], reasons=[{"kind": "not_comparable"}])

    def abweichungen(r: dict[str, Any]) -> list[dict[str, Any]]:
        aus: list[dict[str, Any]] = []
        for stufe, modell in (r.get("models") or {}).items():
            jetzt = current_models.get(stufe)
            if stufe in b.steps and jetzt and modell and jetzt != modell:
                aus.append({"kind": "model", "step": stufe, "then": modell, "now": jetzt})
        return aus

    heutig = [r for r in mit_wert if not r.get("variant") and not abweichungen(r)]
    gruende: list[dict[str, Any]] = []
    if heutig:
        latest = heutig[-1]
        previous = heutig[-2] if len(heutig) > 1 else None
    else:
        ohne_variante = [r for r in mit_wert if not r.get("variant")] or mit_wert
        latest, previous = ohne_variante[-1], None
        gruende = abweichungen(latest) or [{"kind": "variant", "variant": latest.get("variant")}]
    ds = latest.get("dataset") or {}
    if ds.get("sha256") and ds.get("path") in current_cases:
        jetzt_sha = current_cases[ds["path"]]
        if jetzt_sha and jetzt_sha != ds["sha256"]:
            gruende.append({"kind": "cases", "path": ds["path"]})
    alter = (heute - datetime.fromisoformat(latest["started_at"]).date()).days
    if alter > STALE_AFTER_DAYS:
        gruende.append({"kind": "age", "days": alter})
    return Assessment("stale" if gruende else "ok", latest=latest, previous=previous, reasons=gruende)


# --------------------------------------------------------------------------- #
# Die Übersicht fürs Admin-Panel
# --------------------------------------------------------------------------- #

def _metric(m: Metric) -> dict[str, Any]:
    return {"key": m.key, "label": m.label, "unit": m.unit, "higher_is_better": m.higher_is_better}


def _main_model(run: dict[str, Any], b: Benchmark) -> str | None:
    """Das Modell der Stufe, um die es dem Benchmark vor allem geht (die letzte gemessene)."""
    models: dict[str, Any] = run.get("models") or {}
    for stufe in reversed(b.steps):
        if models.get(stufe):
            return str(models[stufe])
    return next((str(v) for v in models.values() if v), None)


def is_current(run: dict[str, Any], b: Benchmark, current_models: dict[str, str | None]) -> bool:
    """Lief der Lauf mit der heutigen Besetzung (s. :func:`assess`)?"""
    if run.get("variant") or not run.get("comparable", True):
        return False
    for stufe, modell in (run.get("models") or {}).items():
        jetzt = current_models.get(stufe)
        if stufe in b.steps and jetzt and modell and jetzt != modell:
            return False
    return True


def run_row(run: dict[str, Any], b: Benchmark, current_models: dict[str, str | None]) -> dict[str, Any]:
    """Die Kurzform eines Laufs für Tabellen und Verläufe."""
    metrics: dict[str, Any] = run.get("metrics") or {}
    ds: dict[str, Any] = run.get("dataset") or {}
    return {
        "id": run["id"], "benchmark": b.key, "origin": run.get("origin", "repo"),
        "started_at": run["started_at"], "environment": run["environment"],
        "label": run.get("label"), "variant": run.get("variant"),
        "model": _main_model(run, b), "value": metrics.get(b.metric.key),
        "hard": metrics.get(HARD), "cases": ds.get("cases") or metrics.get("cases"),
        "sample": ds.get("sample"), "cost_usd": run.get("cost_usd"),
        "comparable": bool(run.get("comparable", True)), "current": is_current(run, b, current_models),
        "has_conclusion": bool(run.get("conclusion")),
    }


def overview(runs: list[dict[str, Any]], *, current_models: dict[str, dict[str, str | None]],
             usage: dict[str, dict[str, Any]], root: Path = ROOT,
             today: date | None = None) -> dict[str, Any]:
    """Alles, was der Benchmark-Bereich auf einen Blick braucht.

    ``current_models``: Pipeline → Stufe → heutiges Modell (das Backend löst
    die ``Step.model``-Verweise auf). ``usage``: :func:`kern.usage.per_feature`.
    """
    gueltig = [r for r in runs if not r.get("problems")]
    faelle = {p: dataset_state(p, root) for b in BENCHMARKS for p in b.cases}
    shas = {p: (d or {}).get("sha256") for p, d in faelle.items()}

    def modelle_fuer(b: Benchmark) -> dict[str, str | None]:
        aus: dict[str, str | None] = {}
        for p in (b.pipeline, *b.also):
            aus.update(current_models.get(p, {}))
        return aus

    bench_out: list[dict[str, Any]] = []
    status_of: dict[str, str] = {}
    gruende_of: dict[str, list[dict[str, Any]]] = {}
    for b in BENCHMARKS:
        jetzt = modelle_fuer(b)
        eigene = sorted((r for r in gueltig if r.get("benchmark") == b.key), key=lambda r: r["started_at"])
        a = assess(b, eigene, current_models=jetzt, current_cases=shas, today=today)
        status_of[b.key] = a.status
        gruende_of[b.key] = a.reasons
        bench_out.append({
            "key": b.key, "pipeline": b.pipeline, "also": list(b.also), "title": b.title,
            "measures": b.measures, "metric": _metric(b.metric),
            "secondary": [_metric(m) for m in b.secondary], "steps": list(b.steps),
            "cases": [faelle[p] or {"path": p, "sha256": None, "cases": None} for p in b.cases],
            "truth": b.truth, "judge": b.judge, "runs_on": b.runs_on, "command": b.command,
            "noise": b.noise, "hard": b.hard, "log": b.log,
            "status": a.status, "reasons": a.reasons,
            "latest": run_row(a.latest, b, jetzt) if a.latest else None,
            "previous": run_row(a.previous, b, jetzt) if a.previous else None,
            "runs": [run_row(r, b, jetzt) for r in eigene],
        })

    pipe_out: list[dict[str, Any]] = []
    for p in PIPELINES:
        eigene_b = benchmarks_of(p.key)
        gemessen = [b for b in eigene_b if status_of[b.key] != "none"]
        steps: list[dict[str, Any]] = []
        for s in p.steps:
            nutzung = [usage[f] for f in s.features if f in usage]
            im_betrieb: list[str] = []
            for n in nutzung:
                im_betrieb += [m for m in n.get("models", []) if m not in im_betrieb]
            steps.append({
                "key": s.key, "label": s.label, "features": list(s.features),
                "model": current_models.get(p.key, {}).get(s.key),
                "llm": bool(s.features),
                "calls_30d": sum(int(n.get("calls", 0)) for n in nutzung),
                "cost_30d": round(sum(float(n.get("cost", 0.0)) for n in nutzung), 4),
                "models_30d": im_betrieb,
                "benchmarks": [b.key for b in eigene_b if s.key in b.steps],
            })
        # Der Kopf der Karte: der wichtigste Benchmark (Katalog-Reihenfolge) mit
        # einer vergleichbaren Zahl — ein Teillauf über einen Fall oder ein
        # Lauf zum Lesen sagt nicht, wie gut die Pipeline ist.
        brauchbar = [b for b in gemessen if b.metric.unit != "none"
                     and not any(g["kind"] == "not_comparable" for g in gruende_of[b.key])]
        kopf = (brauchbar or gemessen or eigene_b or [None])[0]
        pipe_out.append({
            "key": p.key, "title": p.title, "summary": p.summary, "steps": steps,
            "benchmarks": [b.key for b in eigene_b],
            "headline": kopf.key if kopf else None,
            "status": status_of[kopf.key] if kopf else "none",
            "measured_steps": sum(1 for s in steps if s["benchmarks"]),
        })
    return {
        "pipelines": pipe_out,
        "benchmarks": bench_out,
        "runs_total": len(gueltig),
        "invalid": [{"id": r["id"], "origin": r.get("origin", "repo"), "problems": r["problems"]}
                    for r in runs if r.get("problems")],
        "stale_after_days": STALE_AFTER_DAYS,
        "github": GITHUB,
    }
