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


class OkWithId(TypedDict):
    ok: bool
    id: int


# Roh-Zeilen aus den Stores. Sie stammen aus ``SELECT *`` bzw. breiten Joins
# und wachsen mit ihren Tabellen — hier absichtlich durchgereicht statt
# aufgezählt (siehe Regel 2 im Modul-Docstring). Die Aliase sind trotzdem
# sprechend, damit im Schema steht, WAS für ein Objekt gemeint ist.
AgendaItemRow = dict[str, Any]


class SessionRow(TypedDict):
    """Eine Sitzung, wie ``CouncilStore.get_session`` sie liefert. Die sechs
    Felder sind die Spalten von ``council_sessions`` — ein Wächter-Test
    (``test_api_vertrag``) schlägt an, wenn die Tabelle wächst, damit hier
    nichts still abgeschnitten wird."""
    # NULL für terminierte Sitzungen OHNE veröffentlichte Tagesordnung: Die
    # liefert `upcoming_sessions` mit, und im Ratsinformationssystem gibt es
    # sie noch nicht als Sitzung mit Nummer (s. `social.wochenvorschau`).
    # Als `int` deklariert war das ein 500 an genau den Wochen, in denen die
    # nächste Ratssitzung noch keine Tagesordnung hat.
    ksinr: int | None
    committee: str
    session_date: str
    session_time: NotRequired[str | None]
    location: NotRequired[str | None]
    fetched_at: NotRequired[str | None]
    # Zahl der öffentlichen Tagesordnungspunkte. `upcoming_sessions` /
    # `recent_sessions` / `search_sessions` liefern sie, `get_session` nicht —
    # deshalb NotRequired. Sie hat hier GEFEHLT, und weil nicht deklarierte
    # Felder still ENTFERNT werden (s. Modulkopf), zeigten beide Frontends
    # „0 TOPs" bzw. eine leere Zahl vor „TOPs". Aufgefallen erst an echten
    # Daten — die Testfixtures beider Seiten setzen `n_items` selbst.
    n_items: NotRequired[int]
    # Vom Sitzungs-Endpunkt angereichert: die TOPs dieser Sitzung, die zu
    # einem Thema des Kontos passen.
    my_topic_items: NotRequired[list[dict[str, Any]]]
    # Ende des „läuft gerade"-Fensters (``council.live``), nur an Sitzungen
    # von HEUTE — für alle anderen fehlt das Feld.
    live_until: NotRequired[str | None]


class DecisionRow(TypedDict):
    """Ein Beschluss aus ``CouncilStore._decision_row``.

    Die Felder sind die 27 Spalten von ``council_decisions`` plus das, was die
    Abfragen dazujoinen (``committee``, ``session_date``, ``protocol_url``) und
    was der Router anreichert. Bis auf ``id`` ist alles ``NotRequired``: Welche
    Spalten dabei sind, hängt an der jeweiligen Abfrage — ein Pflichtfeld wäre
    hier ein 500, sobald ein Aufrufer schmaler selektiert.

    ``factions``/``policy_tags`` kommen als JSON-Spalte und werden geparst,
    ``parties`` rechnet der Store aus den Fraktionen aus.
    """
    id: int
    ksinr: NotRequired[int | None]
    position: NotRequired[int | None]
    kind: NotRequired[str | None]
    parent_item: NotRequired[str | None]
    item_number: NotRequired[str | None]
    title: NotRequired[str | None]
    official_text: NotRequired[str | None]
    outcome: NotRequired[str | None]
    vote: NotRequired[str | None]
    no_votes: NotRequired[int | None]
    abstentions: NotRequired[int | None]
    factions: NotRequired[list[str]]
    template_number: NotRequired[str | None]
    kvonr: NotRequired[int | None]
    raw_result: NotRequired[str | None]
    policy_field: NotRequired[str | None]
    policy_tags: NotRequired[list[str]]
    summary: NotRequired[str | None]
    amount_eur: NotRequired[float | None]
    importance: NotRequired[int | None]
    simple_summary: NotRequired[str | None]
    interest: NotRequired[int | None]
    interest_reason: NotRequired[str | None]
    impact: NotRequired[int | None]
    impact_reason: NotRequired[str | None]
    deviation: NotRequired[str | None]
    # aus den Joins bzw. vom Router angereichert
    parties: NotRequired[list[str]]
    committee: NotRequired[str | None]
    session_date: NotRequired[str | None]
    protocol_url: NotRequired[str | None]
    n_beratungen: NotRequired[int | None]
    location_matches: NotRequired[list[Any]]
    subvote_summary: NotRequired[Any]


# --------------------------------------------------------------------------
# Onboarding & Einrichtung
# --------------------------------------------------------------------------


class OnboardingState(TypedDict):
    steps: list[str]
    celebrated: bool


class SetupState(TypedDict):
    step: int
    started_at: str | None
    done_at: str | None
    #: Soll der Assistent gezeigt werden? Serverseitig entschieden, damit Web
    #: und App dieselbe Regel benutzen — siehe ``Store.get_setup``.
    pending: bool


# --------------------------------------------------------------------------
# Lotsen-Abzeichen (RL-U12)
# --------------------------------------------------------------------------


class BadgeProgress(TypedDict):
    current: int
    target: int


class Badge(TypedDict):
    id: str
    title: str
    hint: str
    earned: bool
    progress: BadgeProgress | None


class BadgeShort(TypedDict):
    """Für ``newly_earned`` — der Konfetti-Moment braucht nur Name und Id."""
    id: str
    title: str


class BadgeNext(TypedDict):
    id: str
    title: str
    hint: str


class BadgeState(TypedDict):
    badges: list[Badge]
    earned_count: int
    total: int
    next: BadgeNext | None
    newly_earned: list[BadgeShort]


# --------------------------------------------------------------------------
# Merkliste
# --------------------------------------------------------------------------


class BookmarkEntry(TypedDict):
    """Gebaut in ``council.bookmarks.serialize_bookmark`` — festes Literal,
    deshalb hier vollständig aufgeschrieben. Die drei eingebetteten Objekte
    sind Roh-Zeilen und bleiben offen."""
    id: int
    kind: Literal["session", "agenda_item", "decision"]
    target_key: str
    title: str
    subtitle: str
    created_at: str
    notify_result: bool
    result_notified_at: str | None
    state: Literal["upcoming", "waiting", "protocol", "decided", "saved",
                   "unavailable", "group"]
    url: str
    ksinr: int | None
    item_number: str | None
    session: SessionRow | None
    agenda_item: AgendaItemRow | None
    decision: DecisionRow | None
    is_group: bool


class BookmarkList(TypedDict):
    bookmarks: list[BookmarkEntry]


# --------------------------------------------------------------------------
# „Frag den Rat" — gespeicherte Gespräche
# --------------------------------------------------------------------------


class ConversationRow(TypedDict):
    id: int
    title: str
    updated: str
    n_turns: int


class ConversationList(TypedDict):
    """`total` ist der Bestand des Kontos, `matches` gilt zur Suche, `has_more`
    sagt, ob „Ältere anzeigen" noch etwas nachliefert."""
    saves_conversations: int | None
    conversations: list[ConversationRow]
    total: int
    matches: int
    has_more: bool


class ConversationSetting(TypedDict):
    saves_conversations: int


class ConversationTurn(TypedDict):
    question: str
    answer: str
    sources: dict[str, Any] | None


class ConversationDetail(TypedDict):
    id: int
    title: str
    updated: str
    turns: list[ConversationTurn]


class ConversationsDeleted(TypedDict):
    deleted: int


# --------------------------------------------------------------------------
# Konto: Benachrichtigungs-Einstellungen
# --------------------------------------------------------------------------


class NotifyKind(TypedDict):
    """Ein Anlass samt Beschriftung — die Oberfläche soll keine zweite Liste
    pflegen müssen. ``parent`` ist gesetzt, wenn der Anlass eine Unter-Option
    eines anderen ist."""
    key: str
    label: str
    hint: str
    default: bool
    enabled: bool
    parent: str | None


class NotifyLimits(TypedDict):
    per_day: int
    quiet_from: int
    quiet_to: int


class NotifySettings(TypedDict):
    kinds: list[NotifyKind]
    limits: NotifyLimits


class TestDelivery(TypedDict):
    """``sent`` nennt die Kanäle, über die es rausging (``deliver_message``)."""
    sent: list[str]


# --------------------------------------------------------------------------
# Themen
# --------------------------------------------------------------------------


class TopicSuggestion(TypedDict):
    name: str
    description: str
    n: int


class NearbySuggestion(TopicSuggestion):
    #: Aus welchem Ortsbereich dieser Vorschlag stammt. Muss mit — ihn unter der
    #: Überschrift des Nachbarn zu zeigen wäre schlicht falsch.
    place: str


class DistrictSuggestions(TypedDict):
    """Vorschläge aus EINEM Ortsbereich, mitsamt dem Ort, für den sie gelten."""
    place_id: str
    name: str
    suggestions: list[TopicSuggestion]
    #: Aus den nächstgelegenen Ortsbereichen, nur wenn der eigene keine sechs
    #: hergibt (15 von 31 tun das nicht). Getrennt, damit die Oberfläche es
    #: getrennt beschriften kann.
    nearby: list[NearbySuggestion]
    #: Wie weit zurück gesucht wurde (Monate). In lebhaften Stadtteilen reicht
    #: ein Jahr, in ruhigen braucht es zwei oder drei — die Oberfläche schreibt
    #: den Zeitraum dazu, statt stillschweigend Aktualität zu behaupten.
    months: int


class TopicSuggestions(TypedDict):
    #: Stadtweit — was gerade überhaupt im Rat läuft.
    suggestions: list[TopicSuggestion]
    #: Je mitgegebenem ``?district=`` eine Gruppe, in derselben Reihenfolge.
    #: Keine der Listen überschneidet sich mit einer anderen oder mit
    #: ``suggestions`` — jeder Vorschlag steht genau einmal.
    districts: list[DistrictSuggestions]


class TopicDescription(TypedDict):
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


class UnreadTopicHits(TypedDict):
    total: int


class MarkedHits(TypedDict):
    marked: int


class TopicHit(TypedDict):
    topic_name: str
    id: int
    title: str
    committee: str
    session_date: str


class TopicHitList(TypedDict):
    hits: list[TopicHit]


class TopicDecision(TypedDict):
    id: int
    title: str
    committee: str
    session_date: str | None
    policy_field: str | None
    outcome: str | None
    score: float


class TopicDecisions(TypedDict):
    decisions: list[TopicDecision]


class Subscriptions(TypedDict):
    subscriptions: list[str]


class SubscriptionSet(TypedDict):
    subscribed: bool
    committee_name: str


class SubscriptionRemoved(TypedDict):
    unsubscribed: bool
    committee_name: str


# --------------------------------------------------------------------------
# Betrieb & öffentliche Schnittstellen
# --------------------------------------------------------------------------


class Health(TypedDict):
    status: str


class SourceCheck(TypedDict):
    status: str
    checked_seconds_ago: int


# --------------------------------------------------------------------------
# Social-Schnittstelle (Instagram-Bot, eigenes Repo)
# --------------------------------------------------------------------------


class WeekPreview(TypedDict):
    """``CouncilStore.wochenvorschau`` hat ZWEI Rückgabeformen: ohne Treffer
    nur fünf Schlüssel, mit Treffern elf. Die sechs Kennzahlen sind deshalb
    ``NotRequired`` — ein Pflichtfeld wäre hier ein 500 an einer ruhigen
    Woche. ``upcoming`` hängt der Router an."""
    found: bool
    from_date: str
    to_date: str
    sessions: list[SessionRow]
    items: list[dict[str, Any]]
    upcoming: list[SessionRow]
    substantive_total: NotRequired[Any]
    substantive_per_session: NotRequired[Any]
    relevant_per_session: NotRequired[Any]
    matches_total: NotRequired[Any]
    matches_per_session: NotRequired[Any]
    further_per_session: NotRequired[Any]


class Discovery(TypedDict):
    day: str
    kicker: str
    story: str
    decision_id: int
    title: str | None
    outcome: str | None
    vote: str | None
    committee: str | None
    session_date: str | None


class SocialDecision(TypedDict):
    """Fester SELECT im Router plus ``votes`` — deshalb hier vollständig."""
    id: int
    title: str | None
    official_text: str | None
    outcome: str | None
    vote: str | None
    simple_summary: str | None
    importance: int | None
    item_number: str | None
    committee: str | None
    session_date: str | None
    votes: list[dict[str, Any]]


class HighestDecisionId(TypedDict):
    highest_id: int


class MediaUpload(TypedDict):
    day: str
    count: int
    urls: list[str]


# --------------------------------------------------------------------------
# Quiz
# --------------------------------------------------------------------------


class QuizQuestion(TypedDict):
    """Gebaut in ``CouncilStore._quiz_row(with_answer=False)`` — die Lösung ist
    bewusst NICHT dabei. ``source_*`` sind ``NotRequired``, weil die eigenen
    Übungsfragen (``/own/round``) ohne Quelle gebaut werden; ``unit`` und die
    Slider-Grenzen gibt es nur bei Schätzfragen."""
    id: int
    area_type: str
    area_key: str
    category: str
    difficulty: str
    question: str
    options: list[str]
    # Geschrieben ausschließlich von unserem eigenen Code („mc" beim Anlegen
    # eigener Fragen, „mc"/„estimate" bei den amtlichen) — deshalb benennbar.
    qtype: Literal["mc", "estimate"]
    source_type: NotRequired[str | None]
    source_ref: NotRequired[str | None]
    hint: NotRequired[str | None]
    unit: NotRequired[str | None]
    range_min: NotRequired[float | None]
    range_max: NotRequired[float | None]


class QuizRound(TypedDict):
    questions: list[QuizQuestion]


class QuizResult(TypedDict):
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


class QuizArea(TypedDict):
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
    electoral_districts: NotRequired[list[int]]
    district: NotRequired[str | None]
    districts: NotRequired[list[str]]


class QuizAreas(TypedDict):
    electoral_districts: list[QuizArea]
    districts: list[QuizArea]
    topics: list[QuizArea]
    categories: list[str]


class QuizDailyResult(TypedDict):
    day: str
    correct: int
    total: int
    points: int
    completed_at: str | None


class QuizDailyRound(TypedDict):
    """``done`` ist KEIN Flag, sondern das Ergebnis des Tages — oder ``None``,
    solange die Challenge offen ist."""
    day: str
    done: QuizDailyResult | None
    questions: list[QuizQuestion]


class QuizDayCompleted(TypedDict):
    ok: bool
    day: str
    streak: int


class QuizMapQuestion(TypedDict):
    target: str
    question: str


class QuizMapRound(TypedDict):
    questions: list[QuizMapQuestion]


class QuizMapResult(TypedDict):
    correct: bool
    target: str
    points: int


class QuizOwnQuestions(TypedDict):
    questions: list[dict[str, Any]]


class QuizTotal(TypedDict):
    points: int
    answered: int
    correct: int


class QuizAreaScore(TypedDict):
    area_type: str
    area_key: str
    points: int
    answered: int
    correct: int
    last_at: str | None


class QuizScore(TypedDict):
    """``Store.quiz_stats`` liefert ``by_area``/``total``, der Router hängt
    Serie, Abzeichen, Fehlerzahl und Tages-Status an."""
    by_area: list[QuizAreaScore]
    total: QuizTotal
    wrong: int
    streak: int
    badges: list[Any]
    daily_done: bool


class QuizFlaggedQuestion(TypedDict):
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


class QuizFlagged(TypedDict):
    flagged: list[QuizFlaggedQuestion]


# --------------------------------------------------------------------------
# Admin-Panel
#
# Die Nutzlasten hier sind breit und kommen großenteils direkt aus
# ``SELECT``-Zeilen. Wo der Router selbst ein Literal baut, steht die Form
# vollständig; wo eine Store-Zeile durchgereicht wird, steht ein benannter
# offener Typ — er reicht alles unverändert durch, statt beim nächsten
# ``ALTER TABLE`` still Felder zu schlucken (siehe Regel 2 oben).
# --------------------------------------------------------------------------

AdminUserDetail = dict[str, Any]
AdminFeedbackRow = dict[str, Any]
AdminPlaceCandidate = dict[str, Any]
AdminLlmUsage = dict[str, Any]
AdminEntityAlias = dict[str, Any]


class AdminSeries(TypedDict):
    total: int
    series: list[int]
    delta: int
    days: list[str]


class AdminCouncilStats(TypedDict):
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


class AdminGrowth(TypedDict):
    users: AdminSeries
    topics: AdminSeries
    wau: list[int]
    wau_days: list[str]
    council: AdminCouncilStats


class AdminQuizArea(TypedDict):
    area_type: str
    area_key: str
    n: int


class AdminQuizStats(TypedDict):
    questions_active: int
    avg_accuracy: float | None
    reported: int
    weak_categories: list[AdminQuizArea]


class AdminJobRun(TypedDict):
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
    history: list[AdminJobRun]


class AdminFeedbackList(TypedDict):
    items: list[AdminFeedbackRow]
    unread: int


class AdminUnread(TypedDict):
    total: int


class AdminFeedbackRead(TypedDict):
    ok: bool
    unread: int


class AdminUserRow(TypedDict):
    id: int
    email: str
    role: str
    status: str
    created_at: str | None
    apple_linked: bool
    n_topics: int
    n_subscriptions: int
    n_quiz: int
    n_ki: int
    last_seen: str | None


class AdminLimits(TypedDict):
    deep_limit: int | None
    limits_unlocked: bool


class AdminAliasList(TypedDict):
    aliases: list[AdminEntityAlias]


class AdminAliasDeleted(TypedDict):
    ok: bool
    entities: int


class AdminPlaceCandidates(TypedDict):
    candidates: list[AdminPlaceCandidate]
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
PlaceCatalog = dict[str, Any]
class CouncilRecess(TypedDict):
    """Ob gerade Ratspause ist — immer dieselben fünf Felder
    (``council/sitzungspause.py``)."""
    active: bool
    label: str | None
    until: str | None
    note: str | None
    next_session_date: str | None


class TodaySession(TypedDict):
    """Eine Sitzung des heutigen Tages im „Heute im Rat"-Briefing."""
    committee: str
    session_time: str
    # Ende des „läuft gerade"-Fensters (``council.live``): die Startzeit der
    # nächsten Sitzung desselben Tages, sonst ein Deckel ab Beginn.
    live_until: str | None
    tops: list[str]
    remaining: int


class BriefingToday(TypedDict):
    state: Literal["heute"]
    # Die Felder der ERSTEN Sitzung des Tages, flach — so lasen ältere
    # App-Installationen das Briefing, bevor es ``sessions`` gab.
    committee: str
    session_time: str
    live_until: str | None
    tops: list[str]
    remaining: int
    n_sessions_today: int
    # Alle Sitzungen des Tages: An Ratstagen tagen drei Gremien nacheinander,
    # und erst mit der ganzen Liste kann die Leiste auf die laufende
    # umschalten. Ohne diese Zeile schnitte die Antwort sie still ab.
    sessions: list[TodaySession]


class BriefingNext(TypedDict):
    state: Literal["naechste"]
    committee: str
    session_date: str
    session_time: str


class BriefingBreak(TypedDict):
    state: Literal["pause"]
    label: str | None
    until: str | None


# Drei Zustände, unterscheidbar an `state` — als echte Union statt einer Form
# mit lauter NotRequired, damit beide Clients erst nach der Prüfung auf die
# jeweiligen Felder kommen.
TodayBriefing = BriefingToday | BriefingNext | BriefingBreak
WeekPreviewInternal = dict[str, Any]
BudgetOverview = dict[str, Any]
SessionDetail = dict[str, Any]
DecisionDetail = dict[str, Any]
QaShare = dict[str, Any]
ResearchSnapshot = dict[str, Any]
class AnalysisCoverage(TypedDict):
    with_factions: int
    total: int


class AnalysisData(TypedDict):
    """``CouncilStore.party_analysis`` — die Hülle steht, die Innereien sind
    verschachtelte Auswertungen und bleiben offen."""
    coverage: AnalysisCoverage
    topic_matrix: dict[str, Any]
    success_rates: Any
    contention: Any
    alliances: Any
    # legt der Router dazu
    field_labels: dict[str, str]
    antrag_stats: Any


class TrendData(TypedDict):
    """``CouncilStore.activity_trends`` — Hülle beschrieben, Reihen offen."""
    quarters: list[str]
    fields: list[str]
    by_field: dict[str, Any]
    money: list[float]
    money_drivers: list[Any]
    emerging: Any
PublicNumbers = dict[str, Any]
EntityDetail = dict[str, Any]
PersonDetail = dict[str, Any]
Speeches = dict[str, Any]


class CommitteeDetail(TypedDict):
    name: str
    next_date: str | None
    next_time: str | None
    decisions_year: int


class Committees(TypedDict):
    committees: list[str]
    details: list[CommitteeDetail]


class PolicyField(TypedDict):
    key: str
    label: str
    count: int


class PolicyFields(TypedDict):
    fields: list[PolicyField]


class PartyFilter(TypedDict):
    parties: Any


class Districts(TypedDict):
    catalog: dict[str, Any]
    districts: Any


class PlaceDetail(TypedDict):
    children: Any
    decision_count: Any
    decisions: Any
    place: Any


class SessionList(TypedDict):
    count: int
    sessions: list[SessionRow]
    total: int


class ThisWeekNone(TypedDict):
    found: Literal[False]


class ThisWeekFound(TypedDict):
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
ThisWeek = ThisWeekFound | ThisWeekNone


class DiscoveryOfTheDay(TypedDict):
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


class NumberOfTheWeekAmount(TypedDict):
    kind: Literal["amount"]
    amount_eur: float
    decision_id: int
    title: str
    session_date: str | None
    window_days: int


class NumberOfTheWeekCount(TypedDict):
    kind: Literal["count"]
    count: int
    window_days: int


NumberOfTheWeek = NumberOfTheWeekAmount | NumberOfTheWeekCount


class BudgetProducts(TypedDict):
    coverage_percent: Any
    all_years: Any
    facets: Any
    year: Any
    plan_expenses: Any
    product: Any
    products: Any
    matches: int


class BudgetStaffPlan(TypedDict):
    missing: Any
    groups: Any
    herkunft: dict[str, Any]
    editions: Any
    totals: Any
    part_names: Any
    rows: Any


class BudgetAuditReports(TypedDict):
    findings: list[Any]
    years: Any
    legend: Any
    without_report: list[Any]


class BudgetGroup(TypedDict):
    cross_check: Any
    herkunft: dict[str, Any]
    years: Any
    consolidated: list[Any]
    items: Any
    entity: list[Any]


class BudgetHoldings(TypedDict):
    report_years: Any
    owners: Any
    companies: list[Any]
    herkunft: dict[str, Any]
    years: list[Any]
    indicators: Any
    group_comparison: Any
    people: list[Any]
    texts: Any


class BudgetInvestments(TypedDict):
    financial_budget: list[Any]
    investments: list[Any]
    herkunft: dict[str, Any]
    years: Any
    sub_budgets: list[Any]


class BudgetInvestmentProgram(TypedDict):
    totals: list[Any]
    herkunft: dict[str, Any]
    years: Any
    measures: list[Any]
    sub_budgets: list[Any]


class BudgetDataState(TypedDict):
    today: str
    layers: list[dict[str, Any]]


class BudgetDocuments(TypedDict):
    documents: Any
    editions: Any


class BudgetPath(TypedDict):
    rounds: Any


class BudgetDispute(TypedDict):
    rounds: Any


class BudgetAmendmentLists(TypedDict):
    herkunft: dict[str, Any]
    totals: Any
    rows: Any
    # Der FINANZhaushalt, seit 08/2026. Eigene Schlüssel statt einer
    # gemeinsamen Liste mit Marke: Die Zeilen haben eine andere Form (fünf
    # Betragsspalten statt zwei, dazu der Investitionscode).
    #
    # Wer hier einen Schlüssel vergisst, merkt es nicht am Fehler, sondern am
    # LEEREN Feld: Die Antwortform ist zugleich das Response-Model, und
    # FastAPI schneidet weg, was nicht darinsteht. Genau so verschwanden diese
    # beiden beim ersten Anlauf lautlos aus einer sonst korrekten Antwort.
    cash_budget_totals: Any
    cash_budget_rows: Any


class DecisionList(TypedDict):
    decisions: list[DecisionRow]
    total: int


class PartyOpinions(TypedDict):
    without_speeches: Any
    parties: Any


class QaShareToken(TypedDict):
    token: str


class ResearchStarted(TypedDict):
    # None heißt: unbegrenzt, der Client zeigt dann keinen Zähler.
    remaining: int | None
    job_id: str


class ResearchCurrent(TypedDict):
    remaining: int | None
    job: dict[str, Any] | None


class ResearchStopped(TypedDict):
    facets_done: int
    facets_total: int
    partial_report_possible: bool


class QaExamples(TypedDict):
    sessions: Any


class TemplateFollows(TypedDict):
    follows: Any


class TemplateFollowed(TypedDict):
    following: bool
    kvonr: int


class TemplateUnfollowed(TypedDict):
    following: bool
    kvonr: int


class Finances(TypedDict):
    by_field: Any
    decisions: Any
    field_labels: dict[str, Any]


class PolicyFieldRecaps(TypedDict):
    recaps: Any


class Entities(TypedDict):
    entities: Any


class EntitiesMap(TypedDict):
    entities: Any


class PeopleDirectory(TypedDict):
    people: Any


class SharePreview(TypedDict):
    """Titel und Beschreibung für die Vorschau-Karte beim Teilen — fünf
    Zweige (Beschluss, Person, Ort, Entität, Sitzung), alle mit denselben
    zwei Feldern."""
    description: str
    title: str


class CouncilMembers(TypedDict):
    members: Any


class GoalMetrics(TypedDict):
    """Wie viele Beschlüsse das Ziel voranbringen, bremsen oder nicht berühren."""
    advances: int
    hinders: int
    neutral: int
    total: int


class Goal(GoalMetrics):
    key: str
    label: str
    description: str


class Goals(TypedDict):
    goals: list[Goal]


class GoalDetail(TypedDict):
    key: str
    label: str
    description: str
    summary: GoalMetrics
    decisions: list[dict[str, Any]]


class BudgetComparison(TypedDict):
    citation: Any
    herkunft: dict[str, Any]
    years: Any
    cities: Any
    values: Any


class BudgetFixedAssets(TypedDict):
    scope_note: Any
    fixed_assets: dict[str, Any]
    missing: Any
    herkunft: dict[str, Any]
    years: list[Any]
    accounting_systems: list[Any]
    series: Any


class BudgetBalanceSheet(TypedDict):
    explanations: Any
    herkunft: dict[str, Any]
    years: Any
    items: Any


class BudgetDebt(TypedDict):
    scope_note: Any
    column_kinds: list[Any]
    guarantees: dict[str, Any]
    herkunft: dict[str, Any]
    integrated_debt: Any
    years: list[Any]
    series: Any
    interest_expense: Any
