"""Register der Pläne der Stadt Oldenburg (docs/plan-ziele-plaene.md).

Ein Plan ist hier ein eigenes Objekt: Quelle, Beschlussart, Laufzeit,
Vorgänger und Nachfolger, Berichtsreihe. Maßnahmen, Status und Kennzahlen
kommen in späteren Phasen dazu (``council/plans/<key>.json``, abgeleitete
Tabellen in ``council.sqlite``).

**Warum Code und keine Tabelle.** Das Register ist Handarbeit, jede Zeile ist
eine Behauptung über die Stadt. Eine Änderung soll deshalb im Pull Request
stehen, mit Diff und Historie — wie bei den Prompts (``kern/prompts.py``).

**Was als Plan zählt** (Tims Entscheidung 09.11.2026, Plan § 8.1):

- ``action``: Pläne mit Maßnahmen und Ratsbeschluss (Klasse 1),
- ``framework``: Rahmenpläne und Strategien (Klasse 2),
- ``statutory``: Pflicht- und Fachpläne mit fester Laufzeit (Klasse 3),
- ``reference``: Pläne Dritter und Steuerungskonzepte, nur als Verweis.

**„Zur Kenntnis genommen“ ist nicht „beschlossen“** (§ 3.4 Regel 7). Wo der
Rat einen Plan nur zur Kenntnis genommen hat, steht ``mode="noted"`` — auch
wenn das Ergebnis im Ratsinformationssystem „ungeändert beschlossen“ heißt,
weil der Beschlusstext einen Auftrag an die Verwaltung enthält
(Schulentwicklungsplan 2018, Integrationskonzept 2020).

Daten sind ISO-Zeichenketten in der Genauigkeit, die der Beleg hergibt:
``"2035"``, ``"2026-06"`` oder ``"2026-06-01"``. Ein Jahr als Ende heißt
„bis Ende dieses Jahres“.

Wächter: ``tests/test_plaene_register.py`` (Form, ohne Datenbank) und
``scripts/pruefe_plaene.py`` (gegen den Bestand).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

PlanKind = Literal["action", "framework", "statutory", "reference"]
DecisionMode = Literal["adopted", "noted"]

KIND_LABELS: dict[str, str] = {
    "action": "Maßnahmenplan",
    "framework": "Rahmenplan oder Strategie",
    "statutory": "Pflicht- oder Fachplan",
    "reference": "Verweis",
}

COUNCIL = "Rat"


@dataclass(frozen=True)
class Decision:
    """Ein Beschluss über den Plan selbst: aufstellen, fortschreiben, zur Kenntnis nehmen."""

    #: Sitzungsdatum, so genau wie belegt.
    date: str
    #: Vorlagennummer samt Fassung (``"23/0211/2"``). ``None`` heißt: vor dem
    #: Bestand des Ratsinformationssystems (Sitzungen ab 01/2018).
    template: str | None
    mode: DecisionMode = "adopted"
    committee: str = COUNCIL
    #: Was dieser Beschluss am Plan tut, für Menschen: „4. Fortschreibung“.
    label: str | None = None


@dataclass(frozen=True)
class Plan:
    key: str
    title: str
    kind: PlanKind
    #: Schlüssel aus ``council.topics.POLICY_FIELDS``.
    policy_field: str
    #: Federführendes Amt laut Planvorlage.
    office: str | None
    #: Der Beschluss, der den Plan in Kraft setzt. ``None`` = noch in Arbeit.
    adopted: Decision | None
    #: Weitere Beschlüsse über den Plan selbst (Ziel, Fortschreibung,
    #: Priorisierung) — Beziehung „beschließt oder ändert den Plan“.
    decisions: tuple[Decision, ...] = ()
    #: Bei Plänen in Arbeit: die Vorlage, mit der die Arbeit begann oder
    #: zuletzt vorgestellt wurde.
    commissioned: str | None = None
    start: str | None = None
    end: str | None = None
    #: Laufzeit in den Worten des Plans, wo sie sich nicht als Datum fassen
    #: lässt („15 bis 20 Jahre“).
    horizon_note: str | None = None
    #: Nächste vorgesehene Überprüfung oder Fortschreibung.
    review_due: str | None = None
    predecessor: str | None = None
    successor: str | None = None
    #: Vorlage, die den Plan auswertet oder abschließt (Evaluation,
    #: Abschlussbericht, der Folgeplan).
    concluded: str | None = None
    #: Titelmuster (Regex, ohne Groß/klein) der Tagesordnungspunkte und
    #: Vorlagen, die zum Plan gehören: Berichte, Anträge, Beschlüsse.
    report_patterns: tuple[str, ...] = ()
    #: Titelmuster, die trotz Treffer oben NICHT dazugehören.
    exclude_patterns: tuple[str, ...] = ()
    #: Titelmuster einer Reihe, die den Plan umsetzt (Kita-Maßnahmenplanung).
    implementation_patterns: tuple[str, ...] = ()
    #: Plan eines Dritten (Zweckverband), nur bei ``kind="reference"``.
    owner: str | None = None
    #: ``"council"``: aus dem Ratsinformationssystem; ``"website"``: nur von
    #: oldenburg.de (Phase 5b) — Kicker „VERÖFFENTLICHT“, nicht „BESCHLOSSEN“.
    source: Literal["council", "website"] = "council"
    #: Schlüssel in ``council.goals.GOALS``, solange die alte Ziel-Seite läuft.
    goal: str | None = None
    #: Fußnote, die jede Anzeige mitführen muss.
    note: str | None = None


_AKTIONSPLAN_GEWALT = (r"Aktionsplan(e?s)?\W*(gegen )?Gewalt",)
_INTEGRATIONSKONZEPT = (r"Integrationskonzept",)
_GLEICHSTELLUNGSPLAN = (r"Gleichstellungsplan",)

PLANS: dict[str, Plan] = {p.key: p for p in (
    # ── A. Laufend, mit Maßnahmenliste und Berichtsreihe ───────────────────
    Plan(
        key="klimaschutzplan_2035",
        title="Klimaschutzplan Oldenburg 2035",
        kind="action", policy_field="klima_umwelt",
        office="Amt für Klimaschutz und Mobilität",
        adopted=Decision("2022-12-19", "22/0910"),
        decisions=(Decision("2021-04-26", "21/0249/2", label="Klimaziel: klimaneutral bis 2035"),),
        start="2022-12", end="2035",
        review_due="2027",
        predecessor="aktionsplan_energie",
        report_patterns=(r"Klimaschutz-Aktivit",),
        goal="klima_2035",
        note="Eine Fortschreibung ist für 2027 angekündigt (26/0750).",
    ),
    Plan(
        key="waermeplan",
        title="Oldenburger Wärmeplan",
        kind="action", policy_field="klima_umwelt",
        office="Amt für Klimaschutz und Mobilität",
        adopted=Decision("2026-06-01", "26/0236"),
        start="2026-06",
        horizon_note="Überprüfung spätestens nach fünf Jahren (§ 25 WPG)",
        review_due="2031-06",
        report_patterns=(r"Kommunale[nr]? Wärmeplanung", r"Oldenburger Wärmeplan"),
        goal="klima_2035",
    ),
    Plan(
        key="mobilitaetsplan_2030",
        title="Mobilitätsplan Oldenburg 2030",
        kind="action", policy_field="verkehr",
        office="Amt für Klimaschutz und Mobilität",
        adopted=Decision("2023-06-26", "23/0211/2"),
        decisions=(
            Decision("2023-11-27", "23/0867", label="Weiteres Vorgehen"),
            Decision("2024-05-27", "24/0216", label="Maßnahmenpriorisierung und Umsetzungsplanung"),
        ),
        start="2023-06", end="2030",
        predecessor="smv2025",
        report_patterns=(r"Mobilitätsplan(es)? (Oldenburg )?2030",),
        goal="verkehrswende",
        note="Über 250 Einzelmaßnahmen, rund 70 davon priorisiert (24/0216).",
    ),
    Plan(
        key="aktionsplan_gewalt_2020",
        title="Aktionsplan gegen Gewalt an Frauen* und Häusliche Gewalt 2020–2025",
        kind="action", policy_field="soziales_gesundheit",
        office="Gleichstellungsbüro",
        adopted=Decision("2020-09-28", "20/0564"),
        start="2020", end="2025",
        successor="aktionsplan_gewalt_2026",
        concluded="26/0681/1",
        report_patterns=_AKTIONSPLAN_GEWALT,
        note="87 Empfehlungen: 8 übergreifend, 56 zu Gewalt gegen Frauen*, 23 zu Häuslicher "
             "Gewalt. Sieben Berichte im Ausschuss waren mündlich, ohne Text.",
    ),
    Plan(
        key="aktionsplan_gewalt_2026",
        title="Aktionsplan gegen Gewalt an Frauen* und Häusliche Gewalt (Fortschreibung 2026)",
        kind="action", policy_field="soziales_gesundheit",
        office="Gleichstellungsbüro",
        adopted=Decision("2026-09-28", "26/0681/1", label="Evaluation und Fortschreibung"),
        start="2026-09",
        horizon_note="ohne Enddatum, „für die kommenden Jahre“; jährlicher Bericht angekündigt",
        predecessor="aktionsplan_gewalt_2020",
        report_patterns=_AKTIONSPLAN_GEWALT,
        note="Sechs Fokusthemen mit je fünf Empfehlungen.",
    ),
    Plan(
        key="ernaehrungsstrategie",
        title="Ernährungsstrategie",
        kind="action", policy_field="klima_umwelt",
        office="Amt für Klimaschutz und Mobilität",
        adopted=Decision("2025-02-24", "24/0810"),
        decisions=(Decision("2025-02-24", "24/0811", label="Umsetzung von fünf Handlungsansätzen"),),
        start="2025-02",
        report_patterns=(r"Ernährungsstrategie",),
        note="9 Ziele und 68 Handlungsansätze; den Umsetzungsstand je Ansatz schätzt die Stadt "
             "selbst in Stufen von 0 bis 100 % ein.",
    ),
    Plan(
        key="laermaktionsplan",
        title="Lärmaktionsplan (Fortschreibung 2024)",
        kind="action", policy_field="klima_umwelt",
        office="Amt für Umweltschutz und Bauordnung",
        adopted=Decision("2024-09-30", "24/0293/1", label="Fortschreibung"),
        start="2024-09",
        horizon_note="Überprüfung alle fünf Jahre (§ 47d Abs. 5 BImSchG)",
        review_due="2029-09",
        report_patterns=(r"Lärmaktionsplan",),
        exclude_patterns=(r"Eisenbahn-?\s?[bB]undesamt",),
        goal="verkehrswende",
        note="Tempo 30 auf neun Straßen: Stufe 1 seit 14.12.2025, Stufe 2 geplant Ende 2027.",
    ),
    Plan(
        key="digitalisierungsstrategie",
        title="Digitalisierungsstrategie",
        kind="action", policy_field="verwaltung_digital",
        office="Büro des Oberbürgermeisters",
        adopted=Decision("2023-12-18", "23/0708"),
        decisions=(Decision("2024-12-16", "24/0574", label="Umsetzungsplan, erste Phase 2025–2027"),),
        start="2023-12", end="2045",
        horizon_note="Vision bis 2045; erste Phase des Umsetzungsplans 2025–2027",
        review_due="2027",
        report_patterns=(r"Digitalisierungsstrategie", r"Umsetzungsplan(s)? Digitalisierung"),
        goal="digitalisierung",
    ),
    Plan(
        key="kita_ausbau",
        title="Konzept zum Ausbau der Kindertagesbetreuung",
        kind="action", policy_field="bildung",
        office="Amt für Jugend und Familie",
        adopted=Decision("2008-06-30", None, label="Grundkonzept"),
        decisions=(
            Decision("2018-06-25", "18/0308", label="4. Fortschreibung"),
            Decision("2022-09-26", "22/0620", label="5. Fortschreibung"),
        ),
        start="2008-06", end="2030",
        report_patterns=(r"Umsetzung der beschlossenen Maßnahmen zum Ausbau",),
        implementation_patterns=(
            r"Maßnahmen?planung für den weiteren Ausbau der Kindertagesbetreuung",
            r"Weitere Maßnahme für den Ausbau der Kindertagesbetreuung",
        ),
        goal="bildung_betreuung",
        note="Zielquoten: 55 % Krippe, 10 % Kindertagespflege, 99,5 % Kindergarten.",
    ),
    Plan(
        key="agenda_2025_alter",
        title="Agenda 2025 „Selbstbestimmt und mittendrin!“ – altersgerechtes Oldenburg",
        kind="action", policy_field="soziales_gesundheit",
        office="Amt für Teilhabe und Soziales",
        adopted=Decision("2025-06-30", "25/0403"),
        start="2025-06",
        review_due="2028",
        report_patterns=(r"Agenda 2025", r"altersgerechte[sn]? Oldenburg"),
    ),
    Plan(
        key="kinder_jugendbeteiligung",
        title="Handlungskonzept Kinder- und Jugendbeteiligung",
        kind="action", policy_field="soziales_gesundheit",
        office="Amt für Jugend und Familie",
        adopted=Decision("2026-09-28", "26/0710/1"),
        start="2026-09", end="2029-09",
        horizon_note="drei Jahre, danach Evaluation",
        report_patterns=(r"Kinder- und Jugendbeteiligung",),
    ),
    Plan(
        key="thg_neutrale_verwaltung",
        title="Konzept für eine treibhausgasneutrale Verwaltung",
        kind="action", policy_field="klima_umwelt",
        office="Amt für Klimaschutz und Mobilität",
        adopted=Decision("2026-02-23", "25/0896"),
        start="2026-02", end="2035",
        report_patterns=(r"treibhausgasneutrale[n]? Verwaltung",),
        goal="klima_2035",
        note="Gesetzlich gilt 2040; das Konzept entspricht der Klimaschutzplan-Maßnahme "
             "Gebäude_05.",
    ),
    # ── B. Rahmenpläne und Strategien ──────────────────────────────────────
    Plan(
        key="isek_2035",
        title="Integriertes Stadtentwicklungskonzept ISEK Oldenburg 2035 / Zukunft 2050",
        kind="framework", policy_field="bauen_wohnen",
        office="Stadtplanungsamt",
        adopted=Decision("2024-09-30", "24/0425", label="Ebene 1: Zukunft 2050"),
        start="2024-09", end="2035",
        horizon_note="ISEK bis 2035, Zukunft 2050; Ebene 3 (Fokusräume) in Arbeit bis 2027",
        predecessor="step2025",
        report_patterns=(r"^Integriertes Stadtentwicklungskonzept", r"ISEK Oldenburg"),
    ),
    Plan(
        key="masterplan_stadtgruen",
        title="Masterplan Stadtgrün",
        kind="framework", policy_field="klima_umwelt",
        office="Amt für Umweltschutz und Bauordnung",
        adopted=Decision("2022-09-26", "22/0642"),
        start="2022-09",
        horizon_note="für die nächsten 15 bis 20 Jahre",
        report_patterns=(r"Masterplan (Stadt)?gr[üu]n",),
    ),
    Plan(
        key="baumstrategie",
        title="Baumerhalt- und Entwicklungsstrategie",
        kind="framework", policy_field="klima_umwelt",
        office="Amt für Umweltschutz und Bauordnung",
        adopted=Decision("2025-06-30", "25/0388"),
        start="2025-06",
        horizon_note="regelmäßige Fortschreibung",
        report_patterns=(r"Baumerhalt",),
    ),
    Plan(
        key="spielleitplanung",
        title="Spielleitplanung 2026",
        kind="framework", policy_field="kultur_sport",
        office="Amt für Umweltschutz und Bauordnung",
        adopted=Decision("2026-06-01", "26/0255"),
        start="2026-06",
        horizon_note="15 bis 20 Jahre, mit jährlichem Arbeitsprogramm",
        report_patterns=(r"Spielleitplanung",),
    ),
    Plan(
        key="eek",
        title="Einzelhandelsentwicklungskonzept (EEK)",
        kind="reference", policy_field="wirtschaft",
        office="Stadtplanungsamt",
        adopted=Decision("2024-12-16", "24/0717/1", label="Evaluation und Fortschreibung"),
        start="2024-12",
        report_patterns=(r"Einzelhandelsentwicklungskonzept",),
        note="Ein Steuerungsinstrument für Bebauungspläne, kein Maßnahmenplan.",
    ),
    Plan(
        key="nachhaltigkeitsleitbild",
        title="Nachhaltigkeitsleitbild",
        kind="framework", policy_field="klima_umwelt",
        office="Büro des Oberbürgermeisters",
        adopted=Decision("2022-05-30", "22/0240/1"),
        start="2022-05",
        report_patterns=(r"Nachhaltigkeitsleitbild", r"Nachhaltigkeitsbericht"),
    ),
    Plan(
        key="integrationskonzept_2020",
        title="Integrationskonzept (Fortschreibung 2020)",
        kind="framework", policy_field="migration_integration",
        office="Amt für Zuwanderung und Integration",
        adopted=Decision("2020-02-24", "19/0697/2", mode="noted",
                         label="zur Kenntnis genommen, mit Auftrag für Schwerpunktjahre"),
        decisions=(Decision("2021-06-08", "21/0287", committee="Ausschuss für Integration und Migration",
                            label="Maßnahmenkatalog Handlungsfeld Bildung und Arbeit"),),
        start="2020", end="2025",
        successor="integrationskonzept_2026",
        report_patterns=_INTEGRATIONSKONZEPT,
    ),
    Plan(
        key="integrationskonzept_2026",
        title="Integrationskonzept 2026",
        kind="framework", policy_field="migration_integration",
        office="Amt für Zuwanderung und Integration",
        adopted=None,
        commissioned="26/0191",
        predecessor="integrationskonzept_2020",
        report_patterns=_INTEGRATIONSKONZEPT,
        note="Am 11.03.2026 im Ausschuss vorgestellt und zur Kenntnis genommen; einen "
             "Ratsbeschluss gibt es im Bestand nicht.",
    ),
    Plan(
        key="wohnungslosen_suchthilfe",
        title="Gesamtkonzept niedrigschwellige Wohnungslosen- und Suchthilfe",
        kind="framework", policy_field="soziales_gesundheit",
        office="Amt für Teilhabe und Soziales",
        adopted=Decision("2019-05-27", "19/0239"),
        start="2019-05",
        report_patterns=(r"Wohnungslosen- und Suchthilfe", r"Wohnungslosenhilfe und Suchthilfe"),
    ),
    Plan(
        key="orte_fuer_alle",
        title="Gesamtkonzept „Orte für Alle“",
        kind="framework", policy_field="soziales_gesundheit",
        office="Amt für Teilhabe und Soziales",
        adopted=Decision("2021-06-28", "21/0478/1"),
        start="2021-06",
        report_patterns=(r"Orte f[üu]r Alle",),
    ),
    Plan(
        key="inklusion_stadt_fuer_alle",
        title="„Oldenburg – eine Stadt für alle“ (Inklusion)",
        kind="framework", policy_field="soziales_gesundheit",
        office="Amt für Teilhabe und Soziales",
        adopted=Decision("2023-04-24", "23/0189",
                         label="Erneuerung des Ratsbeschlusses „Oldenburg will Inklusion“"),
        start="2023-04", end="2025",
        horizon_note="Fokusthemen bis Ende 2025",
        predecessor="kai_2015",
        report_patterns=(r"Eine Stadt für alle", r"Oldenburg will Inklusion"),
    ),
    Plan(
        key="demografiestrategie",
        title="Demografiestrategie",
        kind="framework", policy_field="soziales_gesundheit",
        office="Amt für Teilhabe und Soziales",
        adopted=Decision("2020-09-28", "20/0371/1", mode="noted"),
        start="2020-09",
        report_patterns=(r"Demografiestrategie",),
    ),
    # ── C. Pflicht- und Fachpläne ──────────────────────────────────────────
    Plan(
        key="gleichstellungsplan_2024",
        title="Gleichstellungsplan 2024–2026",
        kind="statutory", policy_field="verwaltung_digital",
        office="Amt für Personal- und Verwaltungsmanagement",
        adopted=Decision("2024-06-17", "24/0362", mode="noted"),
        start="2024", end="2026",
        # Der Plan sieht keinen Zwischenbericht vor: Ausgewertet wird er im Folgeplan,
        # nach Ablauf. Ohne diese Frist stünde er zwei Jahre nach der Kenntnisnahme
        # unter „Kein Bericht gefunden“ — ein Vorwurf, den der Plan selbst nicht trägt (§ 3.3a).
        review_due="2026",
        predecessor="gleichstellungsplan_2021",
        report_patterns=_GLEICHSTELLUNGSPLAN,
        note="Pflichtplan nach dem Niedersächsischen Gleichberechtigungsgesetz für das "
             "Personal der Verwaltung; jeder Plan wertet den vorigen aus.",
    ),
    Plan(
        key="gleichstellungsplan_2021",
        title="Gleichstellungsplan 2021–2023",
        kind="statutory", policy_field="verwaltung_digital",
        office="Amt für Personal- und Verwaltungsmanagement",
        adopted=Decision("2021-06-28", "21/0399", mode="noted"),
        start="2021", end="2023",
        predecessor="gleichstellungsplan_2018", successor="gleichstellungsplan_2024",
        concluded="24/0362",
        report_patterns=_GLEICHSTELLUNGSPLAN,
    ),
    Plan(
        key="gleichstellungsplan_2018",
        title="Gleichstellungsplan 2018–2020",
        kind="statutory", policy_field="verwaltung_digital",
        office="Amt für Personal- und Verwaltungsmanagement",
        adopted=Decision("2018-05-28", "18/0406", mode="noted"),
        start="2018", end="2020",
        successor="gleichstellungsplan_2021",
        concluded="21/0399",
        report_patterns=_GLEICHSTELLUNGSPLAN,
    ),
    Plan(
        key="abfallwirtschaftskonzept",
        title="Abfallwirtschaftskonzept 2022–2027",
        kind="statutory", policy_field="klima_umwelt",
        office="Abfallwirtschaftsbetrieb Stadt Oldenburg",
        adopted=Decision("2021-09-27", "21/0668"),
        start="2022", end="2027",
        report_patterns=(r"Abfallwirtschaftskonzept",),
    ),
    Plan(
        key="brandschutzbedarfsplan",
        title="Brandschutzbedarfsplan",
        kind="statutory", policy_field="sicherheit_ordnung",
        office="Feuerwehr",
        adopted=Decision("2025-12-15", "25/0833"),
        start="2025-12",
        report_patterns=(r"Brandschutzbedarfsplan",),
        note="Schreibt den Plan von 2007 fort.",
    ),
    Plan(
        key="nahverkehrsplan",
        title="Nahverkehrsplan (Teilfortschreibung VBN-Tarifgebiet 3 Oldenburg)",
        kind="reference", policy_field="verkehr",
        office="Amt für Klimaschutz und Mobilität",
        adopted=Decision("2026-06-01", "26/0223", label="Teilfortschreibung durch den ZVBN"),
        owner="Zweckverband Verkehrsverbund Bremen/Niedersachsen (ZVBN)",
        report_patterns=(r"Nahverkehrsplan",),
        note="Ein Plan des Zweckverbands, nicht der Stadt.",
    ),
    Plan(
        key="schulverpflegung",
        title="Rahmenkonzept „Schulverpflegung in Oldenburg“",
        kind="statutory", policy_field="bildung",
        office="Amt für Schule und Bildung",
        adopted=Decision("2019-12-16", "19/0943"),
        decisions=(
            Decision("2022-11-28", "22/0811/1", label="Anteil Bio-Lebensmittel"),
            Decision("2023-12-18", "23/0856", label="Anteil Bio-Lebensmittel 2024/2025"),
            Decision("2024-12-16", "24/0687", label="Bio-Monitoring bei Neuvergaben"),
            Decision("2024-12-16", "24/0688", label="Anteil Bio-Lebensmittel 2025/2026"),
            Decision("2025-12-01", "25/0634", label="Anteil Bio-Lebensmittel 2026/2027"),
        ),
        start="2019-12",
        report_patterns=(r"Schulverpflegung in Oldenburg",),
        note="Zugleich Handlungsansatz A1 der Ernährungsstrategie.",
    ),
    Plan(
        key="kitaverpflegung",
        title="Rahmenkonzept Verpflegung in den Kindertagesstätten",
        kind="statutory", policy_field="bildung",
        office="Amt für Jugend und Familie",
        adopted=Decision("2021-06-28", "21/0459"),
        start="2021-06",
        report_patterns=(r"Kitaverpflegung", r"Verpflegung in den Kindertagesst"),
        note="Zugleich Handlungsansatz A2 der Ernährungsstrategie.",
    ),
    # ── D. In Arbeit oder Stand offen ──────────────────────────────────────
    Plan(
        key="klimaanpassungskonzept",
        title="Integriertes Klimaanpassungskonzept (KLAK)",
        kind="framework", policy_field="klima_umwelt",
        office="Stadtplanungsamt",
        adopted=None,
        commissioned="24/0830",
        report_patterns=(r"Klimaanpassungskonzept", r"\(KLAK\)"),
        note="Von sieben Arbeitspaketen waren laut 25/0863 vier abgeschlossen; Maßnahmenkatalog "
             "und Controlling stehen noch aus.",
    ),
    Plan(
        key="luftreinhalteplan",
        title="Luftreinhalteplan (Fortschreibung)",
        kind="statutory", policy_field="klima_umwelt",
        office="Amt für Umweltschutz und Bauordnung",
        adopted=Decision("2018-01-22", "17/0844", label="Maßnahmen für den Fortschreibungsentwurf"),
        decisions=(Decision("2018-04-16", "18/0264", committee="Verkehrsausschuss",
                            label="Öffentliche Auslegung"),),
        start="2018-01",
        report_patterns=(r"Luftreinhalteplan",),
        note="Ob die Fortschreibung abgeschlossen wurde, ist im Bestand nicht festzustellen; "
             "der letzte Sachstand ist 19/0636 (08/2019).",
    ),
    Plan(
        key="wohnraumversorgungskonzept",
        title="Wohnraumversorgungskonzept (Teilfortschreibung des Wohnkonzepts)",
        kind="framework", policy_field="bauen_wohnen",
        office="Stadtplanungsamt",
        adopted=Decision("2022-11-17", "22/0755", mode="noted",
                         committee="Ausschuss für Stadtplanung und Bauen",
                         label="Teilfortschreibung „Bedarf an bezahlbarem Wohnraum“"),
        start="2022-11",
        report_patterns=(r"Wohnraumversorgungskonzept", r"Wohnkonzept"),
        goal="wohnungsbau",
        note="Das Wohnkonzept 2025 (Rat 2013/2014, vor dem Bestand) gilt laut 22/0755 bei der "
             "NBank als veraltet; eine neue Gesamtfassung ist im Bestand nicht zu finden.",
    ),
    # ── E. Abgeschlossen oder abgelöst ─────────────────────────────────────
    Plan(
        key="schulentwicklungsplan_2018",
        title="Schulentwicklungsplan 2018",
        kind="action", policy_field="bildung",
        office="Amt für Schule und Bildung",
        adopted=Decision("2018-06-25", "18/0420/1", mode="noted",
                         label="zur Kenntnis genommen, mit Auftrag zu Beschlussvorschlägen"),
        start="2018-06",
        concluded="19/0942",
        report_patterns=(r"Schulentwicklungsplan",),
        implementation_patterns=(r"Umsetzung der Empfehlungen des Gutachtens zur Schulentwicklung",),
        goal="bildung_betreuung",
        note="Zehn Empfehlungen führten zu zwölf Vorlagen. Im Abschlussbericht 19/0942 steht: "
             "„Alle Beschlussvorschläge wurden angenommen.“",
    ),
    Plan(
        key="step2025",
        title="Stadtentwicklungsprogramm step2025",
        kind="framework", policy_field="bauen_wohnen",
        office="Stadtplanungsamt",
        adopted=Decision("2014-03-31", None),
        start="2014-03", end="2025",
        successor="isek_2035",
        concluded="21/0217",
        report_patterns=(r"step ?2025", r"Stadtentwicklungsprogramm"),
    ),
    Plan(
        key="smv2025",
        title="Strategieplan Mobilität und Verkehr smv2025",
        kind="framework", policy_field="verkehr",
        office="Amt für Verkehr und Straßenbau",
        adopted=Decision("2018-08-27", "18/0254", label="Fortschreibung"),
        start="2018-08", end="2025",
        successor="mobilitaetsplan_2030",
        report_patterns=(r"smv ?2025", r"Strategieplan(s)? Mobilität"),
        goal="verkehrswende",
    ),
    Plan(
        key="rad_fussverkehrsprogramm",
        title="Rad- und Fußverkehrsprogramm",
        kind="action", policy_field="verkehr",
        office="Amt für Verkehr und Straßenbau",
        adopted=Decision("2018-02-19", "18/0056", label="Programm 2018"),
        start="2018",
        horizon_note="jährliches Programm",
        report_patterns=(r"Rad- und Fußverkehrsprogramm",),
        goal="verkehrswende",
        note="Nach dem Programm 2022 (22/0072) im Bestand nicht mehr zu finden.",
    ),
    Plan(
        key="aktionsplan_energie",
        title="Aktionsplan Energie 2019/2020",
        kind="action", policy_field="klima_umwelt",
        office="Amt für Umweltschutz und Bauordnung",
        adopted=Decision("2018-12-13", "18/0516", mode="noted",
                         committee="Ausschuss für Stadtgrün, Umwelt und Klima", label="Aktionsplan 2019"),
        decisions=(Decision("2019-11-14", "19/0836", mode="noted",
                            committee="Ausschuss für Stadtgrün, Umwelt und Klima",
                            label="Aktionsplan 2020"),),
        start="2019", end="2020",
        successor="klimaschutzplan_2035",
        report_patterns=(r"Aktionsplan Energie",),
        goal="klima_2035",
    ),
    Plan(
        key="kai_2015",
        title="Kommunaler Aktionsplan Inklusion (KAI)",
        kind="action", policy_field="soziales_gesundheit",
        office="Amt für Teilhabe und Soziales",
        adopted=Decision("2015", None),
        start="2015",
        successor="inklusion_stadt_fuer_alle",
        report_patterns=(r"Aktionsplan Inklusion", r"Inklusionsprozess"),
        note="71 Haupt- und 236 Untermaßnahmen. Der Stand vom 31.12.2020 (21/0355) zählt die "
             "35 Maßnahmen der schulischen Inklusion nicht mit.",
    ),
    Plan(
        key="innenstadtstrategie",
        title="Innenstadtstrategie / Bündnis Innenstadt",
        kind="framework", policy_field="wirtschaft",
        office="Stadtplanungsamt",
        adopted=Decision("2020-12-07", "20/0820", mode="noted",
                         committee="Ausschuss für Wirtschaftsförderung und internationale Zusammenarbeit",
                         label="Grundsatzvereinbarung"),
        start="2018",
        report_patterns=(r"Innenstadtstrategie", r"Bündnis Innenstadt",
                         r"Monitoring zur Innenstadtentwicklung", r"Bericht des Innenstadtmanagements"),
        goal="innenstadt",
        note="Laut 23/0173 „vom Rat im Dezember 2020 verabschiedet“ und später nach einer weiteren "
             "Beteiligung aktualisiert (24/0124). Im Bestand steht nur die Kenntnisnahme im "
             "Wirtschaftsausschuss am 07.12.2020; der Verwaltungsausschuss tagt nicht öffentlich.",
    ),
    Plan(
        key="gewerbeflaechenkonzept",
        title="Gewerbeflächenentwicklungskonzept 2018",
        kind="framework", policy_field="wirtschaft",
        office="Amt für Wirtschaftsförderung",
        adopted=Decision("2019-03-25", "19/0132/1", label="Umsetzung der Handlungsempfehlungen"),
        start="2019-03",
        report_patterns=(r"Gewerbeflächenentwicklungskonzept",),
    ),
    Plan(
        key="baederstrategie",
        title="Strategie für die Entwicklung der Bäderlandschaft",
        kind="framework", policy_field="kultur_sport",
        office="Amt für Controlling und Finanzen",
        adopted=Decision("2019-01-14", "18/0889/1"),
        decisions=(Decision("2019-11-25", "19/0832/1", label="Sport- und Gesundheitsbad am Flötenteich"),),
        start="2019-01",
        report_patterns=(r"Bäderstrategie", r"Bäderlandschaft"),
    ),
    Plan(
        key="sportentwicklungsplan_2009",
        title="Sportentwicklungsplan 2009",
        kind="framework", policy_field="kultur_sport",
        office="Amt für Kultur, Museen und Sport",
        adopted=Decision("2009-06-22", None),
        start="2009-06",
        report_patterns=(r"Sportentwicklungsplan",),
        note="Vor dem Bestand beschlossen; zitiert in 18/0192 und 18/0917. Eine Fortschreibung "
             "ist im Bestand nicht zu finden.",
    ),
)}


#: Die geprüften Maßnahmenlisten (Phase 2): eine JSON-Datei je Plan, gebaut von
#: ``scripts/plan_massnahmen.py`` aus den Dokumenten der Stadt und im PR geprüft.
#: Die Seite der Stadt zum Plan (Phase 5b). Aus der Seitenübersicht von oldenburg.de und
#: dem Klimaportal, jede Adresse einzeln abgerufen und gegen ihre Überschrift geprüft
#: (09.11.2026; ``robots.txt`` beider Seiten erlaubt den Abruf). Nur der Verweis —
#: Texte und Dokumente der Seiten übernimmt Ratslotse nicht.
PLAN_WEBSITES: dict[str, str] = {
    "eek": "https://www.oldenburg.de/startseite/stadtraum/planen-bauen/stadtentwicklungsplanung/konzepte/einzelhandelsentwicklungskonzept.html",
    "step2025": "https://www.oldenburg.de/startseite/stadtraum/planen-bauen/stadtentwicklungsplanung/konzepte/stadtentwicklungsprogramm-step2025.html",
    "innenstadtstrategie": "https://www.oldenburg.de/startseite/stadtraum/planen-bauen/stadtentwicklungsplanung/konzepte/innenstadtstrategie.html",
    "integrationskonzept_2020": "https://www.oldenburg.de/startseite/leben-in-oldenburg/gesellschaft-soziales/zuwanderung-integration/amt-fuer-zuwanderung-und-integration/integrationskonzept.html",
    "mobilitaetsplan_2030": "https://www.oldenburg.de/startseite/leben-umwelt/verkehr-mobilitaet/mobilitaetsplan-oldenburg-2030.html",
    "masterplan_stadtgruen": "https://www.oldenburg.de/startseite/stadtraum/umwelt/gruenes-oldenburg/masterplan-stadtgruen.html",
    "isek_2035": "https://www.oldenburg.de/startseite/stadtraum/planen-bauen/isek-oldenburg-2050-2035.html",
    "demografiestrategie": "https://www.oldenburg.de/startseite/leben-in-oldenburg/gesellschaft-soziales/strategische-sozialplanung/themen-und-projekte/demografiestrategie.html",
    "digitalisierungsstrategie": "https://www.oldenburg.de/startseite/rathaus/digitalisierung/digitalisierungsstrategie.html",
    "nachhaltigkeitsleitbild": "https://www.oldenburg.de/startseite/stadtraum/umwelt/nachhaltigkeit/nachhaltigkeitsleitbild.html",
    "klimaanpassungskonzept": "https://www.oldenburg.de/startseite/stadtraum/umwelt/klima/klimaanpassung/klimaanpassungskonzept.html",
    "kita_ausbau": "https://www.oldenburg.de/startseite/wissenschaft-bildung/kindertagesbetreuung/kita-ausbau.html",
    "baumstrategie": "https://www.oldenburg.de/startseite/stadtraum/umwelt/naturschutz-und-landschaftspflege/baum-und-gehoelzschutz/baumerhalt-und-entwicklungsstrategie.html",
    "agenda_2025_alter": "https://www.oldenburg.de/startseite/leben-in-oldenburg/gesellschaft-soziales/strategische-sozialplanung/themen-und-projekte/agenda-2025.html",
    "smv2025": "https://www.oldenburg.de/startseite/stadtraum/verkehr-mobilitaet/strategieplan-mobilitaet-und-verkehr.html",
    "wohnraumversorgungskonzept": "https://www.oldenburg.de/startseite/leben-in-oldenburg/wohnen/wohnkonzept.html",
    "sportentwicklungsplan_2009": "https://www.oldenburg.de/startseite/leben-in-oldenburg/sport-freizeit/sport/sportbuero/sportentwicklungsplanung.html",
    "inklusion_stadt_fuer_alle": "https://www.oldenburg.de/startseite/leben-in-oldenburg/gesellschaft-soziales/strategische-sozialplanung/politischer-auftrag/inklusion-und-teilhabe-in-oldenburg.html",
    "klimaschutzplan_2035": "https://klimaportal.oldenburg.de/massnahmen",
    "waermeplan": "https://klimaportal.oldenburg.de/kwp",
    "kai_2015": "https://www.oldenburg.de/startseite/leben-in-oldenburg/gesellschaft-soziales/strategische-sozialplanung/politischer-auftrag/inklusion-und-teilhabe-in-oldenburg.html",
}


def website(key: str) -> str | None:
    """Adresse der Seite, auf der die Stadt den Plan selbst vorstellt — oder ``None``."""
    return PLAN_WEBSITES.get(key)


MEASURES_DIR = Path(__file__).resolve().parent / "plan_measures"


def measures(key: str) -> dict | None:
    """Die Maßnahmenliste eines Plans samt Quelle — oder ``None``, wenn es keine gibt."""
    pfad = MEASURES_DIR / f"{key}.json"
    if not pfad.exists():
        return None
    return json.loads(pfad.read_text(encoding="utf-8"))


TEMPLATE_RE = re.compile(r"^\d{2}/\d{4}(/\d+)?$")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


@cache
def _compiled(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


def matches_title(plan: Plan, title: str | None) -> bool:
    """Gehört ein Tagesordnungspunkt oder eine Vorlage dem Titel nach zum Plan?"""
    if not title:
        return False
    if not any(rx.search(title) for rx in _compiled(plan.report_patterns + plan.implementation_patterns)):
        return False
    return not any(rx.search(title) for rx in _compiled(plan.exclude_patterns))


def template_stem(number: str) -> str:
    """``"23/0211/2"`` → ``"23/0211"``: alle Fassungen einer Vorlage."""
    return "/".join(number.split("/")[:2])


def all_templates(plan: Plan) -> list[str]:
    """Jede Vorlagennummer, die das Register für diesen Plan nennt."""
    out: list[str] = []
    for d in ((plan.adopted,) if plan.adopted else ()) + plan.decisions:
        if d.template:
            out.append(d.template)
    for t in (plan.commissioned, plan.concluded):
        if t:
            out.append(t)
    return out
