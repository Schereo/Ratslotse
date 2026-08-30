"""Die Antwortformen der API — der Vertrag zwischen Backend und den Clients.

**Wozu diese Datei.** Es gibt zwei Frontends (Next.js-Web und die iOS-App), die
featuregleich bleiben sollen. Ein Handler mit ``-> dict`` erzeugt im OpenAPI
wörtlich ``{"additionalProperties": true, "type": "object"}`` — „irgendein
Objekt". Daraus kann kein Generator Swift- oder TypeScript-Typen ableiten, und
kein PR-Diff zeigt, dass sich ein Feld geändert hat. Steht die Form hier, trägt
``/openapi.json`` echte Felder, beide Clients leiten daraus ab, und eine
Änderung an der Schnittstelle ist im Diff dieser Datei sichtbar.

**Warum TypedDict und nicht BaseModel.** Die Handler bauen ohnehin ``dict``s.
Ein ``TypedDict`` als Rückgabe-Annotation liefert dasselbe benannte Schema und
dieselbe Feld-Filterung wie ein ``response_model``, ohne dass ein Handler
umgeschrieben werden muss — und misst sich messbar günstiger (2000 Zeilen:
2,7 ms statt 3,5 ms, roh 2,2 ms). Echte ``BaseModel`` bleiben dort richtig, wo
zusätzlich validiert oder mit Defaults gefüllt wird (siehe ``schemas.py``).

**Zwei Regeln, die man beim Ergänzen kennen muss:**

1. **Ein fehlender Pflichtschlüssel ist ein 500.** FastAPI validiert die
   Antwort gegen die Form; fehlt ein deklariertes Feld, wirft es einen
   ``ResponseValidationError``. Alles, was nur manchmal dabei ist, gehört
   deshalb in ``NotRequired[...]``, und alles, was ``None`` sein kann, braucht
   ``| None``. Im Zweifel großzügig — eine zu strenge Form ist ein
   Produktionsfehler, eine zu lockere nur ein schwächerer Vertrag.
2. **Nicht deklarierte Felder werden ENTFERNT, nicht gemeldet.** Wer eine Form
   unvollständig aufschreibt, schneidet der API stillschweigend Felder ab. Für
   Nutzlasten, die aus ``SELECT *`` stammen und mit der Tabelle wachsen, steht
   deshalb bewusst ``dict[str, Any]`` (reicht alles unverändert durch) statt
   einer Aufzählung, die beim nächsten ``ALTER TABLE`` still Daten verliert.
"""
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

# --------------------------------------------------------------------------
# Bausteine, die überall vorkommen
# --------------------------------------------------------------------------


class Ok(TypedDict):
    """Die häufigste Antwort im Haus (22×): „hat geklappt"."""
    ok: bool


class OkMitId(TypedDict):
    ok: bool
    id: int


# Roh-Zeilen aus den Stores. Sie stammen aus ``SELECT *`` bzw. breiten Joins
# und wachsen mit ihren Tabellen — hier absichtlich durchgereicht statt
# aufgezählt (siehe Regel 2 im Modul-Docstring). Die Aliase sind trotzdem
# sprechend, damit im Schema steht, WAS für ein Objekt gemeint ist.
Sitzungszeile = dict[str, Any]
Beschlusszeile = dict[str, Any]
Tagesordnungszeile = dict[str, Any]


# --------------------------------------------------------------------------
# Onboarding & Einrichtung
# --------------------------------------------------------------------------


class OnboardingStand(TypedDict):
    steps: list[str]
    celebrated: bool


class SetupStand(TypedDict):
    step: int
    started_at: str | None
    done_at: str | None


# --------------------------------------------------------------------------
# Lotsen-Abzeichen (RL-U12)
# --------------------------------------------------------------------------


class AbzeichenFortschritt(TypedDict):
    current: int
    target: int


class Abzeichen(TypedDict):
    id: str
    title: str
    hint: str
    earned: bool
    progress: AbzeichenFortschritt | None


class AbzeichenKurz(TypedDict):
    """Für ``newly_earned`` — der Konfetti-Moment braucht nur Name und Id."""
    id: str
    title: str


class AbzeichenNaechstes(TypedDict):
    id: str
    title: str
    hint: str


class AbzeichenStand(TypedDict):
    badges: list[Abzeichen]
    earned_count: int
    total: int
    next: AbzeichenNaechstes | None
    newly_earned: list[AbzeichenKurz]


# --------------------------------------------------------------------------
# Merkliste
# --------------------------------------------------------------------------


class Merkeintrag(TypedDict):
    """Gebaut in ``council.bookmarks.serialize_bookmark`` — festes Literal,
    deshalb hier vollständig aufgeschrieben. Die drei eingebetteten Objekte
    sind Roh-Zeilen und bleiben offen."""
    id: int
    kind: str
    target_key: str
    title: str
    subtitle: str
    created_at: str
    notify_result: bool
    result_notified_at: str | None
    state: str
    url: str
    ksinr: int | None
    item_number: str | None
    session: Sitzungszeile | None
    agenda_item: Tagesordnungszeile | None
    decision: Beschlusszeile | None
    is_group: bool


class Merkliste(TypedDict):
    bookmarks: list[Merkeintrag]


# --------------------------------------------------------------------------
# „Frag den Rat" — gespeicherte Gespräche
# --------------------------------------------------------------------------


class GespraechZeile(TypedDict):
    id: int
    titel: str
    updated: str
    n_turns: int


class GespraecheListe(TypedDict):
    """`gesamt` ist der Bestand des Kontos, `treffer` gilt zur Suche, `weitere`
    sagt, ob „Ältere anzeigen" noch etwas nachliefert."""
    einstellung: int | None
    gespraeche: list[GespraechZeile]
    gesamt: int
    treffer: int
    weitere: bool


class GespraechEinstellung(TypedDict):
    einstellung: int


class GespraechTurn(TypedDict):
    frage: str
    antwort: str
    quellen: dict[str, Any] | None


class GespraechDetail(TypedDict):
    id: int
    titel: str
    updated: str
    turns: list[GespraechTurn]


class GespraecheGeloescht(TypedDict):
    geloescht: int


# --------------------------------------------------------------------------
# Konto: Benachrichtigungs-Einstellungen
# --------------------------------------------------------------------------


class MeldeArt(TypedDict):
    """Ein Anlass samt Beschriftung — die Oberfläche soll keine zweite Liste
    pflegen müssen. ``parent`` ist gesetzt, wenn der Anlass eine Unter-Option
    eines anderen ist."""
    key: str
    label: str
    hint: str
    default: bool
    enabled: bool
    parent: str | None


class MeldeGrenzen(TypedDict):
    per_day: int
    quiet_from: int
    quiet_to: int


class MeldeEinstellungen(TypedDict):
    kinds: list[MeldeArt]
    limits: MeldeGrenzen


class TestZustellung(TypedDict):
    """``sent`` nennt die Kanäle, über die es rausging (``deliver_message``)."""
    sent: list[str]


# --------------------------------------------------------------------------
# Themen
# --------------------------------------------------------------------------


class ThemenVorschlag(TypedDict):
    name: str
    description: str
    n: int


class ThemenVorschlaege(TypedDict):
    suggestions: list[ThemenVorschlag]


class ThemenBeschreibung(TypedDict):
    """``analyse`` liefert die ersten acht Felder, ``check_vagueness`` die drei
    letzten (sie werden per ``**`` daruntergemischt)."""
    name: str
    description: str
    matches: int
    matches_capped: bool
    examples: list[str]
    verdict: str
    is_council_topic: bool
    reason: str
    vague: bool
    hint: str
    suggestion: str


class UngeleseneThemenTreffer(TypedDict):
    total: int


class MarkierteTreffer(TypedDict):
    marked: int


class ThemenTreffer(TypedDict):
    topic_name: str
    id: int
    title: str
    committee: str
    session_date: str | None


class ThemenTrefferListe(TypedDict):
    hits: list[ThemenTreffer]


class ThemenBeschluss(TypedDict):
    id: int
    title: str
    committee: str
    session_date: str | None
    policy_field: str | None
    outcome: str | None
    score: float


class ThemenBeschluesse(TypedDict):
    decisions: list[ThemenBeschluss]


class Abonnements(TypedDict):
    subscriptions: list[str]


class AboGesetzt(TypedDict):
    subscribed: bool
    committee_name: str


class AboGeloescht(TypedDict):
    unsubscribed: bool
    committee_name: str


# --------------------------------------------------------------------------
# Betrieb & öffentliche Schnittstellen
# --------------------------------------------------------------------------


class Gesundheit(TypedDict):
    status: str


class QuellenPruefung(TypedDict):
    status: str
    geprueft_vor_sekunden: int


# --------------------------------------------------------------------------
# Social-Schnittstelle (Instagram-Bot, eigenes Repo)
# --------------------------------------------------------------------------


class Wochenvorschau(TypedDict):
    """``CouncilStore.wochenvorschau`` hat ZWEI Rückgabeformen: ohne Treffer
    nur fünf Schlüssel, mit Treffern elf. Die sechs Kennzahlen sind deshalb
    ``NotRequired`` — ein Pflichtfeld wäre hier ein 500 an einer ruhigen
    Woche. ``kommende`` hängt der Router an."""
    found: bool
    von: str
    bis: str
    sitzungen: list[Sitzungszeile]
    punkte: list[dict[str, Any]]
    kommende: list[Sitzungszeile]
    inhaltlich_gesamt: NotRequired[Any]
    inhaltlich_je_sitzung: NotRequired[Any]
    relevant_je_sitzung: NotRequired[Any]
    treffer_gesamt: NotRequired[Any]
    treffer_je_sitzung: NotRequired[Any]
    weitere_je_sitzung: NotRequired[Any]


class Fundstueck(TypedDict):
    day: str
    kicker: str
    story: str
    decision_id: int
    title: str | None
    outcome: str | None
    vote: str | None
    committee: str | None
    session_date: str | None


class SocialBeschluss(TypedDict):
    """Fester SELECT im Router plus ``votes`` — deshalb hier vollständig."""
    id: int
    title: str | None
    beschluss: str | None
    outcome: str | None
    vote: str | None
    simple_summary: str | None
    importance: int | None
    item_number: str | None
    committee: str | None
    session_date: str | None
    votes: list[dict[str, Any]]


class HoechsteBeschlussId(TypedDict):
    hoechste_id: int


class MedienAblage(TypedDict):
    tag: str
    anzahl: int
    urls: list[str]


# --------------------------------------------------------------------------
# Quiz
# --------------------------------------------------------------------------


class QuizFrage(TypedDict):
    """Gebaut in ``CouncilStore._quiz_row(with_answer=False)`` — die Lösung ist
    bewusst NICHT dabei. ``source_*`` sind ``NotRequired``, weil die eigenen
    Übungsfragen (``/own/round``) ohne Quelle gebaut werden; ``unit`` und die
    Slider-Grenzen gibt es nur bei Schätzfragen."""
    id: int
    area_type: str
    area_key: str
    category: str | None
    difficulty: str | None
    question: str
    options: list[str]
    qtype: str
    source_type: NotRequired[str | None]
    source_ref: NotRequired[str | None]
    hint: NotRequired[str | None]
    unit: NotRequired[str | None]
    range_min: NotRequired[float | None]
    range_max: NotRequired[float | None]


class QuizRunde(TypedDict):
    questions: list[QuizFrage]


class QuizAuswertung(TypedDict):
    """Antwort auf ``/answer`` und ``/own/answer``. Was nur ein Zweig setzt,
    ist ``NotRequired``: Schätzfragen liefern ``answer_value``/``unit``, die
    Übungsrunde kennt weder Detail noch Diagramm."""
    correct: bool
    correct_index: int
    points: int
    explanation: str | None
    source_type: str | None
    source_ref: str | None
    detail: NotRequired[Any]
    topic: NotRequired[Any]
    map: NotRequired[Any]
    image: NotRequired[Any]
    chart: NotRequired[Any]
    answer_value: NotRequired[float | None]
    unit: NotRequired[str | None]


class QuizGebiet(TypedDict):
    """Ein Eintrag im Gebiets-Katalog. Die drei Listen (Wahlbereiche,
    Ortsbereiche, Themen) teilen sich diese Form — was nur eine davon trägt,
    ist ``NotRequired``. Vollständig aufgeschrieben, weil ein fehlendes Feld
    hier still aus der Antwort verschwindet."""
    key: str
    label: str
    questions: int
    points: int
    place_id: NotRequired[str]        # Slug („osternburg"), keine Zahl
    kind: NotRequired[str | None]
    kind_label: NotRequired[str | None]
    aliases: NotRequired[list[str]]
    parent_ids: NotRequired[list[str]]
    wahlbereiche: NotRequired[list[int]]
    stadtteil: NotRequired[str | None]
    stadtteile: NotRequired[list[str]]


class QuizGebiete(TypedDict):
    wahlbereiche: list[QuizGebiet]
    stadtteile: list[QuizGebiet]
    themen: list[QuizGebiet]
    categories: list[str]


class QuizTagesergebnis(TypedDict):
    day: str
    correct: int
    total: int
    points: int
    completed_at: str | None


class QuizTagesrunde(TypedDict):
    """``done`` ist KEIN Flag, sondern das Ergebnis des Tages — oder ``None``,
    solange die Challenge offen ist."""
    day: str
    done: QuizTagesergebnis | None
    questions: list[QuizFrage]


class QuizTagAbgeschlossen(TypedDict):
    ok: bool
    day: str
    streak: int


class QuizKartenfrage(TypedDict):
    target: str
    question: str


class QuizKartenrunde(TypedDict):
    questions: list[QuizKartenfrage]


class QuizKartenAuswertung(TypedDict):
    correct: bool
    target: str
    points: int


class QuizEigeneFragen(TypedDict):
    questions: list[dict[str, Any]]


class QuizGesamt(TypedDict):
    points: int
    answered: int
    correct: int


class QuizGebietsstand(TypedDict):
    area_type: str
    area_key: str
    points: int
    answered: int
    correct: int
    last_at: str | None


class QuizStand(TypedDict):
    """``Store.quiz_stats`` liefert ``by_area``/``total``, der Router hängt
    Serie, Abzeichen, Fehlerzahl und Tages-Status an."""
    by_area: list[QuizGebietsstand]
    total: QuizGesamt
    wrong: int
    streak: int
    badges: list[Any]
    daily_done: bool


class QuizGemeldeteFrage(TypedDict):
    """Bewertungs-Zeile aus ``quiz_flagged_questions`` plus Fragentext. Die
    Zeile selbst ist ``SELECT``-geformt, deshalb sind ihre Felder offen."""
    question_id: int
    question: str
    area_type: str
    area_key: str
    options: list[str]
    correct_index: int
    bad: int
    good: int
    comments: str | None


class QuizGemeldet(TypedDict):
    flagged: list[QuizGemeldeteFrage]


# --------------------------------------------------------------------------
# Admin-Panel
#
# Die Nutzlasten hier sind breit und kommen großenteils direkt aus
# ``SELECT``-Zeilen. Wo der Router selbst ein Literal baut, steht die Form
# vollständig; wo eine Store-Zeile durchgereicht wird, steht ein benannter
# offener Typ — er reicht alles unverändert durch, statt beim nächsten
# ``ALTER TABLE`` still Felder zu schlucken (siehe Regel 2 oben).
# --------------------------------------------------------------------------

AdminNutzerDetail = dict[str, Any]
AdminFeedbackZeile = dict[str, Any]
AdminOrtsKandidat = dict[str, Any]
AdminLlmVerbrauch = dict[str, Any]
AdminEntitaetsAlias = dict[str, Any]


class AdminVerlauf(TypedDict):
    total: int
    series: list[int]
    delta: int
    days: list[str]


class AdminRatsStatistik(TypedDict):
    sessions: int
    upcoming: int
    agenda_items: int
    committees: int
    decisions: int
    decisions_with_ki: int
    fetched_today: int
    hours_since_fetch: float | None
    last_fetch: str | None
    last_session_import: str | None
    next_session: str | None


class AdminWachstum(TypedDict):
    users: AdminVerlauf
    topics: AdminVerlauf
    wau: list[int]
    wau_days: list[str]
    council: AdminRatsStatistik


class AdminQuizGebiet(TypedDict):
    area_type: str
    area_key: str
    n: int


class AdminQuizStatistik(TypedDict):
    fragen_aktiv: int
    avg_accuracy: float | None
    gemeldet: int
    gebiete_niedrig: list[AdminQuizGebiet]


class AdminJobLauf(TypedDict):
    started_at: str
    status: str
    duration_s: float | None


class AdminJob(TypedDict):
    """``state`` ist eine geschlossene Menge — der Router rechnet sie aus, sie
    kommt nicht aus der Datenbank, deshalb ist die Verengung hier sicher.
    ``last`` dagegen ist eine ``SELECT *``-Zeile aus ``job_runs`` und bleibt
    offen; das Frontend darf sie enger sehen als der Vertrag."""
    key: str
    label: str
    description: str
    schedule: str
    state: Literal["ok", "stale", "error", "unknown"]
    age_h: float | None
    last: dict[str, Any] | None
    history: list[AdminJobLauf]


class AdminFeedbackListe(TypedDict):
    items: list[AdminFeedbackZeile]
    unread: int


class AdminUngelesen(TypedDict):
    total: int


class AdminFeedbackGelesen(TypedDict):
    ok: bool
    unread: int


class AdminNutzerZeile(TypedDict):
    id: int
    email: str
    role: str
    status: str
    created_at: str | None
    apple_linked: bool
    n_topics: int
    n_abos: int
    n_quiz: int
    n_ki: int
    last_seen: str | None


class AdminGrenzen(TypedDict):
    deep_limit: int | None
    limits_frei: bool


class AdminAliasListe(TypedDict):
    aliases: list[AdminEntitaetsAlias]


class AdminAliasGeloescht(TypedDict):
    ok: bool
    entities: int


class AdminOrtsKandidaten(TypedDict):
    candidates: list[AdminOrtsKandidat]
    status: str


# --------------------------------------------------------------------------
# Stadtrat, Haushalt, KI-Frage
#
# Die Hüllen sind aus den Rückgabe-Literalen der Handler abgeleitet, also
# vollständig — kein Feld kann hier unbemerkt herausfallen. Die Werte bleiben
# überwiegend ``Any``: Was drinsteht, kommt aus breiten Store-Abfragen, und
# eine geratene Verengung (etwa ``list[int]`` statt ``Any``) würde Pydantic
# dazu bringen, Werte zu KONVERTIEREN — aus „2026" würde 2026, die Antwort
# änderte sich still. Enger wird hier nur, was belegt ist.
# --------------------------------------------------------------------------

# Nutzlasten, die der Handler nicht selbst zusammensetzt, sondern aus dem
# Store durchreicht: benannt, damit im Schema steht, worum es geht, aber offen.
OrtsKatalog = dict[str, Any]
Sitzungspause = dict[str, Any]
HeuteBriefing = dict[str, Any]
WochenvorschauIntern = dict[str, Any]
HaushaltUebersicht = dict[str, Any]
SitzungsDetail = dict[str, Any]
BeschlussDetail = dict[str, Any]
QaShare = dict[str, Any]
RechercheSnapshot = dict[str, Any]
AnalyseDaten = dict[str, Any]
TrendDaten = dict[str, Any]
OeffentlicheZahlen = dict[str, Any]
EntitaetsDetail = dict[str, Any]
PersonenDetail = dict[str, Any]
Wortbeitraege = dict[str, Any]


class Gremien(TypedDict):
    committees: Any
    details: Any


class Themenfelder(TypedDict):
    fields: Any


class ParteienFilter(TypedDict):
    parties: Any


class Stadtteile(TypedDict):
    catalog: dict[str, Any]
    districts: Any


class OrtsDetail(TypedDict):
    children: Any
    decision_count: Any
    decisions: Any
    place: Any


class SitzungsListe(TypedDict):
    count: int
    sessions: Any
    total: Any


class DieseWocheOhne(TypedDict):
    found: Literal[False]


class DieseWocheMit(TypedDict):
    found: Literal[True]
    decision_id: int
    title: str
    outcome: str | None
    committee: str | None
    session_date: str | None
    interest_reason: str


# Eine echte Union statt einer Form mit lauter NotRequired: `found` unterscheidet
# die beiden Fälle, und beide Clients bekommen daraus einen Typ, bei dem der
# Zugriff auf `title` erst NACH der Prüfung auf `found` erlaubt ist.
DieseWoche = DieseWocheMit | DieseWocheOhne


class FundstueckDesTages(TypedDict):
    """2 Rückgabe-Zweige — was nicht in jedem steht, ist NotRequired."""
    committee: NotRequired[Any]
    decision_id: NotRequired[Any]
    found: bool
    kicker: NotRequired[Any]
    outcome: NotRequired[Any]
    session_date: NotRequired[Any]
    story: NotRequired[Any]
    title: NotRequired[Any]
    vote: NotRequired[Any]


class ZahlDerWocheBetrag(TypedDict):
    kind: Literal["betrag"]
    amount_eur: float
    decision_id: int
    title: str
    session_date: str | None
    window_days: int


class ZahlDerWocheAnzahl(TypedDict):
    kind: Literal["anzahl"]
    count: int
    window_days: int


ZahlDerWoche = ZahlDerWocheBetrag | ZahlDerWocheAnzahl


class HaushaltProdukte(TypedDict):
    abdeckung_prozent: Any
    alle_jahre: Any
    facetten: Any
    jahr: Any
    plan_aufwendungen: Any
    produkt: Any
    produkte: Any
    treffer: int


class HaushaltStellenplan(TypedDict):
    fehlend: Any
    gruppen: Any
    herkunft: dict[str, Any]
    jahrgaenge: Any
    summen: Any
    teile: Any
    zeilen: Any


class HaushaltPruefberichte(TypedDict):
    feststellungen: list[Any]
    jahre: Any
    legende: Any
    ohne_bericht: list[Any]


class HaushaltKonzern(TypedDict):
    gegenprobe: Any
    herkunft: dict[str, Any]
    jahre: Any
    konzern: list[Any]
    posten: Any
    traeger: list[Any]


class HaushaltBeteiligungen(TypedDict):
    berichtsjahre: Any
    eigentuemer: Any
    gesellschaften: list[Any]
    herkunft: dict[str, Any]
    jahre: list[Any]
    kennzahlen: Any
    konzernvergleich: Any
    personen: list[Any]
    texte: Any


class HaushaltInvestitionen(TypedDict):
    finanzhaushalt: list[Any]
    gesamt: list[Any]
    herkunft: dict[str, Any]
    jahre: Any
    teilhaushalte: list[Any]


class HaushaltInvestitionsprogramm(TypedDict):
    gesamt: list[Any]
    herkunft: dict[str, Any]
    jahre: Any
    massnahmen: list[Any]
    teilhaushalte: list[Any]


class HaushaltDatenstand(TypedDict):
    heute: Any
    schichten: Any


class HaushaltDokumente(TypedDict):
    dokumente: Any
    jahrgaenge: Any


class HaushaltWeg(TypedDict):
    runden: Any


class HaushaltStreit(TypedDict):
    runden: Any


class HaushaltAenderungslisten(TypedDict):
    herkunft: dict[str, Any]
    summen: Any
    zeilen: Any


class BeschlussListe(TypedDict):
    decisions: Any
    total: Any


class ParteiMeinungen(TypedDict):
    ohne_beitraege: Any
    parteien: Any


class QaShareToken(TypedDict):
    token: Any


class RechercheGestartet(TypedDict):
    frei: Any
    job_id: Any


class RechercheAktuell(TypedDict):
    frei: Any
    job: Any


class RechercheGestoppt(TypedDict):
    facetten_fertig: Any
    facetten_gesamt: Any
    teilbericht_moeglich: bool


class QaBeispiele(TypedDict):
    sitzungen: Any


class VorlagenFolgen(TypedDict):
    follows: Any


class VorlageGefolgt(TypedDict):
    following: bool
    kvonr: Any


class VorlageEntfolgt(TypedDict):
    following: bool
    kvonr: Any


class Finanzen(TypedDict):
    by_field: Any
    decisions: Any
    field_labels: dict[str, Any]


class ThemenfeldRueckblicke(TypedDict):
    recaps: Any


class Entitaeten(TypedDict):
    entities: Any


class EntitaetenKarte(TypedDict):
    entities: Any


class PersonenLexikon(TypedDict):
    personen: Any


class Vorschau(TypedDict):
    """5 Rückgabe-Zweige — was nicht in jedem steht, ist NotRequired."""
    description: Any
    title: Any


class Ratsmitglieder(TypedDict):
    members: Any


class Ziele(TypedDict):
    goals: Any


class ZielDetail(TypedDict):
    decisions: Any
    description: Any
    key: Any
    label: Any
    summary: Any


class HaushaltVergleich(TypedDict):
    beleg: Any
    herkunft: dict[str, Any]
    jahre: Any
    staedte: Any
    werte: Any


class HaushaltGebaut(TypedDict):
    abgrenzung: Any
    anlagen: dict[str, Any]
    fehlend: Any
    herkunft: dict[str, Any]
    jahre: list[Any]
    regelwerke: list[Any]
    reihe: Any


class HaushaltBilanz(TypedDict):
    erlaeuterungen: Any
    herkunft: dict[str, Any]
    jahre: Any
    posten: Any


class HaushaltSchulden(TypedDict):
    abgrenzung: Any
    arten: list[Any]
    buergschaften: dict[str, Any]
    herkunft: dict[str, Any]
    integrierte_schulden: Any
    jahre: list[Any]
    reihe: Any
    zinslast: Any
