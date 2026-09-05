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

from fastapi.responses import Response, FileResponse, StreamingResponse

# --------------------------------------------------------------------------
# Bausteine, die überall vorkommen
# --------------------------------------------------------------------------


class Ok(TypedDict):
    """Die häufigste Antwort im Haus (22×): „hat geklappt"."""
    ok: bool


class OkWithId(TypedDict):
    ok: bool
    id: int


class AgendaAttachment(TypedDict):
    """Eine Anlage an einem Tagesordnungspunkt."""
    label: str
    url: str


class AgendaItemRow(TypedDict):
    """Ein Tagesordnungspunkt, wie ``CouncilStore.agenda_items`` ihn liefert.

    Die ersten fünf Felder sind die Spalten, die die Abfrage ausdrücklich
    nennt — kein ``SELECT *``, die Aufzählung ist also vollständig. Die vier
    darunter hängt dieselbe Methode an: die Anlagen des Punktes, die
    LLM-Kurzfassung, den besseren Kartentext, wo es ihn gibt, und das
    abgeleitete Dringlichkeits-Flag.

    Beide Aufrufer (die Sitzungs-Seite und die Merkliste über
    ``council.bookmarks``) holen ihre Punkte aus derselben Methode; deshalb
    reicht eine Form für beide.
    """
    item_number: str
    title: str
    template_number: str | None
    kvonr: int | None
    is_public: int
    anlagen: list[AgendaAttachment]
    summary: str | None
    #: Der Kartentext aus ``agenda_item_social`` — kennt Vorlage UND Anlagen
    #: und ist deshalb der bessere der beiden Texte, wo es ihn gibt.
    social_text: str | None
    #: Abgeleitet (``council.dringlichkeit``), kein amtliches Feld. Es
    #: entscheidet hier und nicht im Frontend, damit Web und App denselben
    #: Punkt hervorheben.
    dringlich: bool


class Attendance(TypedDict):
    """Eine Zeile der Anwesenheitsliste (``CouncilStore.get_attendance``)."""
    name: str | None
    party: str | None
    role: str | None
    note: str | None


class VideoResult(TypedDict):
    """Ein vorläufiges Ergebnis aus der Videoaufzeichnung.

    ACHTUNG: Quelle ist ein ``SELECT *`` auf ``council_video_results``. Eine
    neue Spalte dort fiele ohne Eintrag hier still aus der Antwort — dagegen
    steht ``test_api_vertrag.py::test_zeilen_typen_kennen_alle_spalten_ihrer_tabelle``.
    """
    id: int
    ksinr: int
    item_number: str
    outcome: Beschlussergebnis
    vote: str | None
    no_votes: int | None
    abstentions: int | None
    quote: str
    video_id: str
    video_seconds: int | None
    model: str
    created_at: str


class MyTopicItem(TypedDict):
    """„n TOPs zu deinen Themen" — Treffer der Tagesordnungs-Klassifikation."""
    item_number: str
    topic_name: str


class MatchedAgendaItem(TypedDict):
    """Ein Tagesordnungspunkt, der einen Suchbegriff getroffen hat.

    Weniger Felder als ``AgendaItemRow``: Die Suche liest nur die Spalten der
    Trefferzeile und lässt Anlagen, Kurzfassung und Kartentext weg. ``ksinr``
    steht nicht dabei — die Punkte hängen schon an ihrer Sitzung.
    """
    item_number: str
    title: str
    template_number: str | None
    kvonr: int | None
    is_public: int


class WeekPreviewItem(TypedDict):
    """Ein Tagesordnungspunkt in „Diese Woche im Rat".

    Zwei Listen tragen diese Form: ``items`` (die hervorgehobenen Punkte, mit
    allen Feldern) und die Einträge in ``further_per_session`` — dort baut der
    Store die Punkte Feld für Feld neu zusammen und lässt fünf davon weg.
    Deshalb stehen genau diese fünf als ``NotRequired``.

    Der Store warnt an dieser Stelle selbst: „Wer hier ein Feld ergänzt, muss
    es an BEIDEN Stellen tun." Genau das ist zweimal schiefgegangen — einmal
    fehlte die Kurzfassung, einmal der Kartentext, und die Instagram-Karten
    standen ohne Erklärung da.

    ACHTUNG, Namensfalle: ``applicants`` ist hier EINE Zeichenkette (der aus
    dem Titel herausgetrennte Antragsteller). Das gleichnamige Feld an
    ``TemplateAttachment`` ist eine Liste von Fraktionsnamen.
    """
    ksinr: int
    item_number: str
    title: str
    titel_kurz: str
    applicants: str | None
    topic_name: str | None
    summary: str | None
    social_text: str | None
    dringlich: bool
    wichtig: int
    wichtig_grund: str | None
    template_number: str | None
    kvonr: int | None
    committee: str
    session_date: str
    #: Der Punkt, unter dem eine mehrstufige Sache gebündelt wird.
    gruppe_nr: str
    gruppe_titel: str | None
    gruppe_stationen: int
    #: Nur in ``items``, nicht in ``further_per_session``:
    kind: NotRequired[str | None]
    behandlung: NotRequired[str | None]
    vorgeschichte: NotRequired[int]
    wichtig_quelle: NotRequired[str]
    top: NotRequired[bool]


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
    my_topic_items: NotRequired[list[MyTopicItem]]
    #: Bei einer Textsuche: die Tagesordnungspunkte, die den Suchbegriff
    #: getroffen haben. Fehlt bei jeder anderen Abfrage.
    matched_items: NotRequired[list[MatchedAgendaItem]]
    # Ende des „läuft gerade"-Fensters (``council.live``), nur an Sitzungen
    # von HEUTE — für alle anderen fehlt das Feld.
    live_until: NotRequired[str | None]
    #: Die wichtigsten Punkte der Sitzung (``CouncilStore.sitzungs_highlights``,
    #: dieselbe Bewertung wie ``items`` der Wochenvorschau). Fehlt, wenn kein
    #: Punkt über der Schwelle liegt — und an Sitzungen ohne Tagesordnung.
    highlights: NotRequired[list[WeekPreviewItem]]


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
    outcome: NotRequired[Beschlussergebnis | None]
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


#: Was aus einem Tagesordnungspunkt geworden ist.
#:
#: Die fünf Werte stehen als Literal und nicht als ``str``, damit die
#: Aufzählung im Vertrag ankommt: Beide Clients führten sie sonst von Hand,
#: und eine Abschrift veraltet. Die Quelle sind die beiden Tupel
#: ``CouncilStore._VOTE_OUTCOMES`` und ``_REPORT_OUTCOMES``; ein Wächter in
#: ``tests/test_api_vertrag.py`` hält beide zusammen.
Beschlussergebnis = Literal["accepted", "rejected", "postponed", "noted", "no_decision"]


# --------------------------------------------------------------------------
# Belege: woher eine Zahl stammt
# --------------------------------------------------------------------------
#
# `provenance` steht in zwölf Antwortformen und war in allen zwölf ein
# `dict[str, Any]`. Damit war es für beide Clients eine geschlossene Kiste:
# Der Vertrag sagte „irgendein Objekt", und jedes Feld darin — `probe`,
# `document_id`, `official_text` — musste auf beiden Seiten von Hand
# abgeschrieben werden. Zwei der fünf Abschriften im Frontend kannten
# `document_id` nicht, obwohl der Beleg-Chip daran hängt.
#
# Beschrieben ist es eine Abbildung `{herkunft_id: Herkunft}` — im Schema
# `additionalProperties: {$ref: Herkunft}` und damit generierbar.


class Ratsvorgang(TypedDict):
    """Der Beschluss, der ein Beleg-Dokument verabschiedet hat.

    Wird in ``CouncilStore.beschluesse_zu_dokumenten`` Feld für Feld gebaut,
    nicht aus einem ``SELECT *`` — die Aufzählung hier ist deshalb vollständig
    und bleibt es.

    ``outcome`` kommt ungefiltert, auch ``vertagt`` oder ``abgelehnt``: Eine
    Zahl, deren Vorgang noch läuft, ist keine Zahl ohne Beleg.
    """
    id: int
    ksinr: int
    kvonr: int | None
    top: str | None
    title: str | None
    outcome: Beschlussergebnis | None
    vote: str | None
    template_number: str | None
    committee: str | None
    date: str | None


class Herkunft(TypedDict):
    """Ein Datensatz aus ``council_provenance``, wie ihn ``get_herkunft`` ausgibt.

    ACHTUNG: Die Quelle ist ein ``SELECT *``. Jede neue Spalte der Tabelle ist
    sofort Teil der Antwort — und fiele ohne Eintrag hier genauso still wieder
    heraus, weil ein TypedDict entfernt, was es nicht kennt. Dagegen steht
    ``tests/test_api_vertrag.py::test_zeilen_typen_kennen_alle_spalten_ihrer_tabelle``.

    ``key`` fehlt bewusst: Der interne Fingerabdruck wird vor der Ausgabe
    entfernt, er ist kein Lesestoff.
    """
    id: int
    #: ``ris`` = Anlage im Ratsinformationssystem, ``city`` = Download von
    #: oldenburg.de, ``lsn`` = Tabelle des Landesamts für Statistik.
    kind: str
    #: Die RIS-Dokumentnummer — der Anker, über den der Ratsvorgang gefunden
    #: wird. ``None`` bei ``city``/``lsn``.
    document_id: int | None
    label: str | None
    url: str | None
    citation: str | None
    page: int | None
    #: Die bestandenen Rechenproben als Schlüssel, kommagetrennt. In der
    #: Datenbank NOT NULL: eine Zahl ohne Probe kommt nicht in den Bestand.
    probe: str
    probe_result: str | None
    as_of: str | None
    #: „Zuletzt bestätigt", nicht „zuerst gesehen".
    fetched_at: str
    #: Die Erklärsätze zu den Proben — aus ``herkunft.PROBEN``, nicht aus der
    #: Datenbank. Namensfalle: ``Herkunft.probes`` in Python liefert die
    #: Proben-NAMEN, dieses Feld die ausformulierten Sätze.
    probes: list[str]
    #: ``None``, wo keine Vorlage im Bestand steht. Ein erfundener Vorgang
    #: wäre der schlimmere Fehler.
    official_text: Ratsvorgang | None


#: Je ``herkunft_id`` (als Zeichenkette, weil JSON keine Zahlen als Schlüssel
#: kennt) der zugehörige Beleg.
Provenance = dict[str, Herkunft]


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


class QuizBadge(TypedDict):
    """Ein Abzeichen im Quiz-Fortschritt (``routers.quiz._badges``).

    Nicht zu verwechseln mit ``Badge`` darunter: Das sind die Lotsen-Abzeichen
    des Kontos, dieses hier ist der Punkte-, Serien- oder Gebiets-Meilenstein
    auf der Quiz-Seite.
    """
    key: str
    label: str
    tier: Literal["bronze", "silber", "gold"]


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
    #: Kurze Einordnung für die Anzeige — bei einer Plannummer der Ortsbezug
    #: aus der Klammer des Beschlusstitels („Quartier am Krusenbusch"), sonst
    #: der erste Satz der Beschreibung. MUSS hier stehen: Die Antwortform ist
    #: ein festes Literal, und was fehlt, schneidet FastAPI ab. Genau so kam
    #: „Bebauungsplan 862" ohne jede Erklärung im Browser an, obwohl der
    #: Endpunkt sie berechnet hatte (Tims Bild, 02.09.2026).
    context: str | None


class LocalSuggestion(TopicSuggestion):
    """Ein Vorschlag, der an einem Ortsbereich hängt."""
    #: Warum er dort hängt — der Titel des jüngsten Beschlusses, der beide
    #: verbindet, von Verfahrensschritten und Herkunftsklammern befreit
    #: („Maßnahme Machbarkeitsstudien" für die Kommunale Wärmeplanung unter
    #: Kreyenbrück). ``None``, wenn nichts übrig bleibt, was mehr sagt als der
    #: Name selbst. Beantwortet die Frage, die ein stadtweites Thema unter
    #: einem Stadtteil sonst aufwirft (Tim, 03.09.2026).
    place_reason: str | None


class NearbySuggestion(LocalSuggestion):
    #: Aus welchem Ortsbereich dieser Vorschlag stammt. Muss mit — ihn unter der
    #: Überschrift des Nachbarn zu zeigen wäre schlicht falsch.
    place: str


class DistrictSuggestions(TypedDict):
    """Vorschläge aus EINEM Ortsbereich, mitsamt dem Ort, für den sie gelten."""
    place_id: str
    name: str
    suggestions: list[LocalSuggestion]
    #: Aus den nächstgelegenen Ortsbereichen, nur wenn der eigene keine sechs
    #: hergibt (15 von 31 tun das nicht). Getrennt, damit die Oberfläche es
    #: getrennt beschriften kann.
    nearby: list[NearbySuggestion]
    #: Wie weit zurück gesucht wurde (Monate). In lebhaften Stadtteilen reicht
    #: ein Jahr, in ruhigen braucht es zwei oder drei — die Oberfläche schreibt
    #: den Zeitraum dazu, statt stillschweigend Aktualität zu behaupten.
    months: int


class CityTopicSuggestion(TopicSuggestion):
    """Ein kuratiertes Stadtthema (``council.city_topics``): Radverkehr, Kitas,
    Wohnungsbau — Interessen statt Straßennamen. Gleiche Kachel wie die
    Entitäts-Vorschläge, plus Schlüssel und Zeitraum der Zählung."""
    #: Stabiler Schlüssel des Eintrags in der Registry (``cycling``, ``childcare``).
    key: str
    #: Zeitraum der Zahl ``n`` in Monaten — die Oberfläche schreibt ihn dazu.
    months: int


class TopicSuggestions(TypedDict):
    #: Kuratierte Stadtthemen mit Substanz, die aktivsten zuerst. Anders als
    #: die übrigen Listen NICHT um die eigenen Themen bereinigt: Die Liste ist
    #: stabil, die Oberfläche markiert, was schon angelegt ist. Leer bei
    #: ``?city=0``.
    city: list[CityTopicSuggestion]
    #: Stadtweit — was gerade überhaupt im Rat läuft (Entitäten).
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
    outcome: Beschlussergebnis | None
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


class CouncilWeekPreview(TypedDict):
    """``CouncilStore.wochenvorschau`` hat ZWEI Rückgabeformen: ohne Treffer
    nur fünf Schlüssel, mit Treffern elf. Die sechs Kennzahlen sind deshalb
    ``NotRequired`` — ein Pflichtfeld wäre hier ein 500 an einer ruhigen Woche.

    Das ist die Fassung, die ``/api/council/week-preview`` liefert; die
    Social-Schnittstelle hängt zusätzlich ``upcoming`` an (s. ``WeekPreview``).
    """
    found: bool
    from_date: str
    to_date: str
    sessions: list[SessionRow]
    items: list[WeekPreviewItem]
    substantive_total: NotRequired[Any]
    substantive_per_session: NotRequired[Any]
    relevant_per_session: NotRequired[Any]
    matches_total: NotRequired[Any]
    matches_per_session: NotRequired[Any]
    further_per_session: NotRequired[Any]


class WeekPreview(CouncilWeekPreview):
    """Die Fassung für den Instagram-Bot: ``upcoming`` hängt der Router an —
    die terminierten Sitzungen ohne veröffentlichte Tagesordnung."""
    upcoming: list[SessionRow]


class Discovery(TypedDict):
    day: str
    kicker: str
    story: str
    decision_id: int
    title: str | None
    outcome: Beschlussergebnis | None
    vote: str | None
    committee: str | None
    session_date: str | None


class DecisionVote(TypedDict):
    """Wie eine Fraktion zu einem Beschluss stand
    (``CouncilStore.decision_votes_for``)."""
    faction: str
    stance: str


class SocialDecision(TypedDict):
    """Fester SELECT im Router plus ``votes`` — deshalb hier vollständig."""
    id: int
    title: str | None
    official_text: str | None
    outcome: Beschlussergebnis | None
    vote: str | None
    simple_summary: str | None
    importance: int | None
    item_number: str | None
    committee: str | None
    session_date: str | None
    votes: list[DecisionVote]


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


class UserQuizQuestion(TypedDict):
    """Eine selbst angelegte Quizfrage (``Store._user_quiz_row``).

    Die Quelle ist zwar ein ``SELECT *``, die Methode baut daraus aber eine
    ausdrückliche Projektion — die Aufzählung hier ist deshalb vollständig und
    bleibt es. ``owner_id`` fehlt bewusst (die Zeile gehört dem Abrufenden),
    und ``unit`` heißt in der Datenbank ``answer_unit``.
    """
    id: int
    question: str
    options: list[str]
    correct_index: int
    district: str | None
    category: str
    explanation: str | None
    practiced: int
    correct_count: int
    created_at: str
    #: ``mc`` = Multiple Choice, ``estimate`` = Schätzfrage. Als Literal, damit
    #: die Aufzählung im Vertrag steht statt in jedem Client noch einmal.
    qtype: Literal["mc", "estimate"]
    answer_value: float | None
    unit: str | None
    range_min: float | None
    range_max: float | None


class QuizOwnQuestions(TypedDict):
    questions: list[UserQuizQuestion]


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
    badges: list[QuizBadge]
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

class AdminFeedbackRow(TypedDict):
    """Eine Rückmeldung aus dem Kontaktformular (``Store.list_feedback``).

    Der SELECT nennt seine sieben Spalten ausdrücklich, die Aufzählung ist
    also vollständig. ``read_at`` ist absichtlich global und nicht je Admin:
    Wer eine Meldung abgearbeitet hat, hat sie für alle abgearbeitet.
    """
    id: int
    owner_id: int
    email: str | None
    kind: str
    message: str
    created_at: str
    read_at: str | None


class AdminEntityAlias(TypedDict):
    """Eine zusammengelegte Entität (``CouncilStore.list_entity_aliases``).

    ``canonical_slug`` ist das AUFGELÖSTE Ziel: Eine Kette A→B→C wird bis zum
    Ende verfolgt, damit in der Liste nicht das leere Mittelglied steht.
    """
    slug: str
    canonical_slug: str
    source: str | None
    reason: str | None
    created_at: str
    #: Der Anzeigename des Alias — aus den Rohbeobachtungen, weil der Alias
    #: selbst nach dem Neubau nicht mehr in ``council_entities`` steht.
    alias_name: str | None
    canonical_name: str | None
    canonical_n: int | None


class AdminUserFeatures(TypedDict):
    """Feature-Nutzung eines Kontos. Die Schlüssel sind API-Namen und nicht die
    gespeicherten Werte — ``ki_frage`` zählt ``user_activity.feature =
    'ai_question'``, ``research`` zählt ``research`` (s.
    ``Store.admin_user_detail``).

    Wer dort einen Zähler ergänzt, ergänzt ihn HIER mit: Ein nicht deklariertes
    Feld verschwindet still aus der Antwort, und das Admin-Panel zeigte dann
    eine Spalte weniger, ohne dass irgendwo etwas rot würde.
    """
    ki_frage: int
    research: int
    suche: int
    quiz: int
    analyse: int
    karte: int


class AdminUserDetail(TypedDict):
    """``Store.admin_user_detail`` — ein festes Literal, deshalb vollständig
    aufgeschrieben und ohne ``NotRequired``. ``history`` ist die 30-Tage-Reihe
    der Aktivität, ``history_days`` nennt die zugehörigen Tage."""
    id: int
    email: str
    role: str
    roles: list[str]
    status: str
    created_at: str | None
    last_seen: str | None
    apple_linked: bool
    has_password: bool
    delivery_channel: str
    # None = die Einwilligungsfrage wurde nie beantwortet, 1 = an, 0 = aus.
    saves_conversations: int | None
    deep_limit: int | None
    limits_unlocked: bool
    features: AdminUserFeatures
    topics: list[str]
    subscriptions: list[str]
    history: list[int]
    history_days: list[str]
    #: Womit das Konto angelegt wurde: web | ios | android | app. ``None`` =
    #: vor Einführung der Messung registriert.
    signup_client: str | None
    #: Zugriffe je Client — {"web": 42, "ios": 7}. Muss HIER stehen, nicht nur
    #: im Store: Die Antwortform ist ein festes Literal, und was nicht drinsteht,
    #: schneidet FastAPI aus der Antwort. Genau das ist beim Zusammenführen mit
    #: der Typisierung aus #916 passiert — der Store lieferte weiter, die
    #: Antwort trug es nicht mehr.
    clients: dict[str, int]


class AdminPlaceCandidateEvidence(TypedDict):
    """Bis zu drei Belegbeschlüsse je Ortskandidat (fester SELECT)."""
    id: int
    title: str | None
    session_date: str | None
    evidence: str | None
    method: str | None
    confidence: float | None


class AdminPlaceCandidate(TypedDict):
    """Ein Ortskandidat aus ``CouncilStore.location_candidates`` — dieselbe
    Zeile liefert auch das PUT auf ``/place-candidates/{location_slug}``.

    Die ersten elf Felder sind die Spalten von ``council_locations``
    (``SELECT l.*``); ein Wächter-Test (``test_api_vertrag``) schlägt an, wenn
    die Tabelle wächst, damit hier nichts still abgeschnitten wird. Darunter
    stehen die Spalten der Prüf-Tabelle (mit ``review_``-Präfix, wo der Name
    sonst kollidierte) und das, was die Abfrage ausrechnet.

    ``status`` ist der aufgelöste Prüfstand (``review_status`` oder
    ``"pending"``), ``aliases`` die geparste JSON-Spalte.
    """
    slug: str
    name: str
    kind: str
    lat: float | None
    lon: float | None
    geojson: str | None
    district: str | None
    place_id: str | None
    # Deutscher Spaltenname aus `council_locations` — der Bestand trägt ihn
    # noch, deshalb steht er hier unverändert (kein stiller Umbenennen-Beifang).
    local_area_id: str | None
    geo_tried: int
    updated_at: str | None
    review_status: str | None
    review_place_id: str | None
    review_name: str | None
    review_kind: str | None
    parent_id: str | None
    aliases: list[str]
    description: str | None
    source_url: str | None
    quiz_enabled: int | None
    canonical_place_id: str | None
    note: str | None
    updated_by: str | None
    reviewed_at: str | None
    decision_count: int
    last_date: str | None
    avg_confidence: float | None
    status: str
    evidence: list[AdminPlaceCandidateEvidence]


class AdminLlmUsageFeature(TypedDict):
    """Kosten und Verbrauch eines Features (``kern.usage.summary``)."""
    feature: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    models: list[str]
    first: str | None
    last: str | None


class AdminLlmUsageDay(TypedDict):
    """Ein Tag der 30-Tage-Reihe (``kern.usage.cost_timeseries``) — lückenlos,
    fehlende Tage stehen mit 0 drin."""
    date: str
    cost: float
    calls: int


class AdminLlmUsage(TypedDict):
    """``kern.usage.dashboard`` — festes Literal aus ``summary()`` plus der
    Hochrechnung. Auch der Fehlerzweig von ``summary()`` liefert die ersten
    drei Felder, hier fehlt also nie eines."""
    features: list[AdminLlmUsageFeature]
    total_cost: float
    total_calls: int
    series: list[AdminLlmUsageDay]
    cost_month: float
    projected_month: float
    calls_30d: int
    avg_cost_per_call: float
    budget_monthly: float
    budget_pct: int
    # „ok" < 80 % < „warn" < 100 % ≤ „over" — der Router rechnet die Ampel aus.
    budget_level: Literal["ok", "warn", "over"]


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


class AdminClientShare(TypedDict):
    client: str
    n: int
    #: Nur bei der Nutzung gefüllt (verschiedene Konten); bei der Registrierung
    #: wäre die Zahl mit ``n`` identisch und steht deshalb auf 0.
    users: int


class AdminGrowth(TypedDict):
    users: AdminSeries
    topics: AdminSeries
    wau: list[int]
    wau_days: list[str]
    council: AdminCouncilStats
    #: Zugriffe je Client, letzte 30 Tage — „App oder Web?". ``users`` zählt
    #: jedes Konto genau einmal, unter seinem meistgenutzten Client.
    clients: list[AdminClientShare]
    #: Wie viele Konten in dem Zeitraum MEHRERE Clients benutzt haben. Die Zahl
    #: gehört dazu: Ohne sie liest sich die Aufteilung so, als benutzte jede:r
    #: genau eins.
    clients_both: int
    #: Womit die vorhandenen Konten angelegt wurden (gesamter Bestand).
    signup_clients: list[AdminClientShare]


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


class AdminJobStep(TypedDict):
    """Ein Unterschritt eines Sammel-Jobs (heute nur ``weekly_enrich``).

    Sie stehen hier als eigenes Feld und nicht als weiterer Eintrag in
    ``last["stats"]``: Das Panel rendert die Kennzahlen als Chips mit einer
    Zahl darin — eine Liste darunter ergäbe „[object Object]".
    """
    name: str
    script: str
    status: Literal["ok", "error"]
    duration_s: float | None


class AdminFehlerTag(TypedDict):
    tag: str
    n: int


class AdminRequestFehler(TypedDict):
    """Eine FEHLERART im Web-Backend, nicht ein einzelnes Vorkommen.

    Gleiche Fehler fallen über ihren Fingerabdruck zusammen (``kern/fehler.py``);
    ``count`` sagt, wie oft. Was hier NICHT steht — Anfragekörper, Kopfzeilen,
    roher Pfad, Variablenwerte —, steht dort begründet.
    """
    id: int
    exc_type: str
    message: str | None
    route: str
    method: str
    trace: str | None
    first_seen: str
    last_seen: str
    count: int
    resolved_at: str | None
    #: ``server`` (unbehandelte Ausnahme im Backend) oder ``browser``.
    quelle: str
    #: Tagesverlauf, älteste zuerst — für die Grafik im Panel. Als LISTE und
    #: nicht als Objekt: Die Grafik braucht eine Reihenfolge, ein JSON-Objekt
    #: hat keine.
    daily: list[AdminFehlerTag]


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
    #: Die Unterschritte des letzten Laufs, leer bei Jobs ohne welche. Aus
    #: ``last["stats"]`` herausgelöst, damit die Chip-Zeile Zahlen behält.
    steps: list[AdminJobStep]


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
    #: Die stärkste Rolle (Abkürzung fürs Abzeichen in der Liste).
    role: str
    #: Alle Rollen — die Wahrheit; das Detail bearbeitet diese Liste.
    roles: list[str]
    status: str
    created_at: str | None
    apple_linked: bool
    n_topics: int
    n_subscriptions: int
    n_quiz: int
    n_ki: int
    last_seen: str | None
    #: Womit das Konto angelegt wurde: web | ios | android | app. ``None`` =
    #: vor Einführung der Messung registriert.
    signup_client: str | None
    #: Zugriffe je Client — {"web": 42, "ios": 7}. Leer, solange nichts gemessen
    #: wurde; ``unknown`` steht für die Zeilen aus der Zeit davor.
    clients: dict[str, int]


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


class PlaceParent(TypedDict):
    """Ein Elternort in der Ortsangabe — nur Kennung, Name und Art."""
    id: str
    name: str
    kind: str


class PlaceSource(TypedDict):
    """Ein Beleg des Ortskatalogs (``council/oldenburg_places.json``).

    Vier Schlüssel hat jede der elf Quellen, zwei kommen nur bei manchen vor.
    """
    id: str
    type: str
    title: str
    url: str
    license: NotRequired[str]
    note: NotRequired[str]


class PlaceEntry(TypedDict):
    """Ein Ort des Katalogs (``council.places.public_place``).

    Die ersten zwölf Felder sind die des ``Place``-Dataclass, die drei letzten
    legt die API dazu. Ein Wächter-Test (``test_api_vertrag``) schlägt an, wenn
    das Dataclass wächst — ein hier fehlendes Feld verschwände sonst still.

    ``sources`` bleibt offen: Der Katalog-Eintrag trägt ``note``/``license``,
    die redaktionell geprüfte Quelle nicht.
    """
    id: str
    name: str
    kind: str
    aliases: list[str]
    # Im Katalog (``council/oldenburg_places.json``) heißt der Schlüssel noch
    # ``wahlbereiche``; ``council.places.all_places`` übersetzt beim Laden.
    electoral_districts: list[int]
    parent_ids: list[str]
    description: str | None
    source_ids: list[str]
    filterable: bool
    quiz_enabled: bool
    lat: float | None
    lon: float | None
    kind_label: str
    parents: list[PlaceParent]
    sources: list[PlaceSource]


class PlaceCatalogHead(TypedDict):
    """Der Ortskatalog OHNE seine Orte — Beschriftungen, Typen, Belege.

    Die Stadtteil-Antwort reicht genau diese acht Schlüssel durch (die Orte
    stehen dort als eigene Liste daneben), der volle Katalog erbt sie. Zwei
    Aufzählungen desselben Kopfes liefen auseinander, sobald eine wächst.
    """
    schema_version: int
    id: str
    label: str
    singular: str
    plural: str
    definition: str
    #: Ortstyp → deutsche Beschriftung.
    kinds: dict[str, str]
    sources: list[PlaceSource]


class PlaceCatalog(PlaceCatalogHead):
    """``CouncilStore.public_place_catalog`` — der gemeinsame Ortskatalog für
    Suche, Karten, Quiz und die KI-Funktionen."""
    places: list[PlaceEntry]


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


class BudgetOverview(TypedDict):
    """``/api/council/budget`` — das Datenfundament des Haushalts-Bereichs.

    **Jedes Feld ist ``NotRequired``, und zwar zwingend.** Der Endpunkt baut
    seine Antwort aus einer Bausteinliste und liefert mit ``?felder=…`` nur
    die angeforderten Blöcke (``?felder=years,population`` sind zwei Schlüssel,
    nicht sechsundzwanzig). Ein Pflichtfeld wäre hier an jedem
    zugeschnittenen Aufruf ein 500.

    Die Werte bleiben ``Any``: Was in ihnen steht, kommt aus breiten
    Store-Abfragen, und eine geratene Verengung ließe Pydantic Werte
    KONVERTIEREN (siehe Kopf dieses Abschnitts). Was die einzelnen Blöcke
    bedeuten — und welche Angabe ohne welche nicht gezeigt werden darf —
    steht im Docstring des Handlers (``routers/council.py::haushalt_uebersicht``).
    """
    years: NotRequired[Any]
    taxes: NotRequired[Any]
    tax_capacity: NotRequired[Any]
    fiscal_equalization: NotRequired[Any]
    population: NotRequired[Any]
    income_statement: NotRequired[Any]
    cash_flow_statement: NotRequired[Any]
    income_budget: NotRequired[Any]
    reserves: NotRequired[Any]
    budgeted_years: NotRequired[Any]
    fees: NotRequired[Any]
    fee_rates: NotRequired[Any]
    budget_bylaw: NotRequired[Any]
    business_plans: NotRequired[Any]
    enterprise_accounts: NotRequired[Any]
    variance_reasons: NotRequired[Any]
    audit_report_sources: NotRequired[Any]
    product_years: NotRequired[Any]
    plan_actual_years: NotRequired[Any]
    expense_series: NotRequired[Any]
    indicators: NotRequired[Any]
    supplementary_approvals: NotRequired[Any]
    donations: NotRequired[Any]
    tax_plan: NotRequired[Any]
    tax_rates: NotRequired[Any]
    trade_tax_statistics: NotRequired[Any]
    # Je `herkunft_id` das Dokument samt Fundstelle, Rechenprobe und Stichtag.
    # Die Register-Schlüssel darin (``plan``, ``jahresabschluss`` …) bleiben deutsch.
    provenance: NotRequired[Provenance]


class AgendaChangeLine(TypedDict):
    """Eine Zeile des Tagesordnungs-Diffs (``council.agenda_diff.zeilen``).

    EINE Quelle für das Mail-HTML und die App-Ansicht „Zuletzt geändert".
    Alles unescaped — wer HTML baut, escapet selbst.
    """
    #: ``new`` | ``changed`` | ``moved`` | ``template`` | ``attachments`` |
    #: ``removed`` — die App färbt danach ein.
    art: str
    #: Der fette Kopf inklusive TOP-Nummer.
    label: str
    title: str
    nichtoeffentlich: bool
    #: Die leise Zusatzzeile („vorher: …") oder nichts.
    detail: str | None


class AgendaChange(TypedDict):
    """Eine Änderung an der Tagesordnung aus der Chronik (``agenda_changes``).
    ``satz`` ist der Satz für die Meldung, ``zeilen`` die Einzelheiten."""
    changed_at: str
    satz: str
    zeilen: list[AgendaChangeLine]


class SessionDetail(SessionRow):
    """Eine Sitzung mit allem, was die Sitzungs-Seite braucht.

    Erbt die Spalten von ``SessionRow`` (das ist die Zeile aus
    ``CouncilStore.get_session``); alles darunter hängt der Router an. Die
    sieben Zusätze stehen an JEDER Antwort — der Handler setzt sie
    unbedingt, auch wenn die Listen leer bleiben.
    """
    agenda_items: list[AgendaItemRow]
    decisions: list[DecisionRow]
    attendance: list[Attendance]
    has_protocol: bool
    # Vorläufige Ergebnisse aus der Videoaufzeichnung — die Brücke, bis das
    # Protokoll kommt.
    video_results: list[VideoResult]
    url: str | None
    agenda_changes: list[AgendaChange]


class ImportanceBreakdown(TypedDict):
    """Warum ein Beschluss als wichtig gilt (``council.importance``).

    ``base_score`` ist die reine Heuristik, ``score`` der angezeigte Wert.
    Liegt eine LLM-Tragweite vor, mischt der Router beide 50/50 und legt
    ``impact`` dazu — sonst fehlen die letzten beiden Felder.
    """
    score: int
    signals: dict[str, float | None]
    #: Punkte-Beitrag je vorhandenem Signal, Summe = ``score``. Fehlende
    #: Signale stehen als ``None`` drin und fallen aus der Gewichtung.
    contributions: dict[str, int | None]
    base_score: int
    impact: NotRequired[int]
    impact_reason: NotRequired[str]


class DecisionParticipation(TypedDict):
    """Eine laufende oder beendete Bauleitplan-Beteiligung zum Beschluss."""
    title: str | None
    schritt: str | None
    valid_from: str | None
    valid_until: str | None
    url: str | None
    status: str
    beendet_am: str | None


class DecisionTemplate(TypedDict):
    """Die Vorlage hinter dem Beschluss — Sachverhalt/Begründung als Auszug,
    dazu die Regex-Ernte (federführendes Amt, Klima-Check, Kostenfolge)."""
    template_number: str | None
    title: str | None
    kind: str | None
    document_url: str | None
    n_pages: int | None
    excerpt: str | None
    office: str | None
    climate_impact: str | None
    klima_relevant: Any
    financial_impact: str | None


class DecisionFollow(TypedDict):
    """Folgt DIESES Konto dem Vorgang schon? Fehlt ohne Anmeldung ganz."""
    kvonr: int
    following: bool


class SimilarDecision(TypedDict):
    """Ein semantischer Nachbar (``CouncilStore.get_similar``)."""
    id: int
    title: str
    template_number: str | None
    summary: str | None
    policy_field: str | None
    outcome: Beschlussergebnis | None
    session_date: str | None
    committee: str
    #: Kosinus-Ähnlichkeit aus ``scripts/embed_decisions.py``.
    score: float


class DecisionEntity(TypedDict):
    """Eine im Beschluss erkannte Entität (Vorhaben, Ort, Organisation)."""
    slug: str
    name: str
    kind: str | None


class TemplateAttachment(TypedDict):
    """Eine Anlage an der Vorlage eines Beschlusses.

    ``applicants`` liegt in der Datenbank als JSON-Text und kommt hier
    ausgepackt an — eine Liste von Fraktionsnamen (``["Die Linke"]``).
    """
    document_id: int | None
    label: str | None
    url: str | None
    is_motion: int
    applicants: list[str]
    status: str
    is_image: int


class DeliberationStop(TypedDict):
    """Eine Station der Beratungsfolge, wie ``get_beratungen`` sie liefert."""
    date: str | None
    committee: str
    top: str | None
    is_public: int | None
    result: str | None
    ksinr: int | None


class DeliberationStation(DeliberationStop):
    """Dieselbe Station auf der Beschluss-Seite — dort rechnet der Router
    zusätzlich aus, ob sie noch aussteht.

    ``future`` kommt aus dem DATUM und ausdrücklich nicht aus dem
    Ergebnis-Feld. Die Folgen-Liste reicht die Stationen dagegen roh durch;
    sie benutzt deshalb ``DeliberationStop`` — was hier als Pflichtfeld stünde,
    wäre dort ein 500er (gemessen, nicht vermutet).
    """
    future: bool


class DecisionDetail(TypedDict):
    """Ein Beschluss mit allem Drum und Dran — die geteilte Detailseite.

    Die ersten zehn Felder setzt der Handler unbedingt. Alles darunter hängt
    an der Vorlage: Ohne ``template_number`` gibt es weder ``template`` noch
    ``attachments``, ``deliberation_path`` oder ``plan_image``; ``follow`` kommt
    nur dazu, wenn wirklich jemand angemeldet ist. Deshalb ``NotRequired`` —
    ein Beschluss ohne Vorlage wäre sonst ein 500 (gemessen: rund die Hälfte
    des Bestands).
    """
    decision: DecisionRow
    attendance: list[Attendance]
    present_parties: list[str]
    ratsinfo_url: str | None
    sub_votes: list[DecisionRow]
    template_journey: list[Any]
    similar: list[SimilarDecision]
    entities: list[DecisionEntity]
    participation: DecisionParticipation | None
    importance_breakdown: ImportanceBreakdown
    template: NotRequired[DecisionTemplate]
    template_url: NotRequired[str | None]
    attachments: NotRequired[list[TemplateAttachment]]
    # Zwei Formen (Nachbewilligung bzw. Bürgschaft) mit verschiedenen
    # Schlüsseln — deshalb offen statt geraten.
    budget_link: NotRequired[dict[str, Any] | None]
    plan_image: NotRequired[int | None]
    deliberation_path: NotRequired[list[DeliberationStation]]
    follow: NotRequired[DecisionFollow]


class QaShare(TypedDict):
    """Ein geteilter Antwort-Schnappschuss (``Store.qa_share_get``).

    Festes Literal, deshalb vollständig und ohne ``NotRequired``: Vor dem
    Bausteine-Nachtrag geteilte Antworten haben keine ``extras``, der Store
    setzt die vier Listen dann auf leer und ``chart`` auf ``None``.
    """
    question: str
    answer: str
    sources: list[dict[str, Any]]
    created: str
    debates: list[dict[str, Any]]
    press_releases: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    parties: list[dict[str, Any]]
    chart: dict[str, Any] | None


class ResearchSnapshot(TypedDict):
    """Persistierter Stand eines Deep-Research-Jobs (``Store.deep_job_get``,
    fester SELECT über acht Spalten). ``report`` und ``sources`` sind ``None``,
    solange der Job läuft; der Router parst ``sources`` aus der JSON-Spalte.

    ``user_id`` steht bewusst NICHT hier — der Store wählt es gar nicht erst
    aus, die Zeile gehört ohnehin dem anfragenden Konto.

    **``sources`` ist ein OBJEKT, keine Liste.** Es ist der ganze Quellen-Block
    (``deepresearch._quellen_payload``): unter ``sources`` die Beschlüsse,
    daneben ``press_releases``, ``debates``, ``planning_procedures``,
    ``attachments``, ``facets``, ``documents_read``, ``period``, ``cited`` und
    ``context`` — deckungsgleich mit dem ``sources``-Ereignis des Stroms, damit
    der Client einen fertigen Job identisch rendern kann. Der Block bleibt hier
    offen, weil er ein gewachsener JSON-Blob in der Datenbank ist: Ältere
    Zeilen tragen weniger Schlüssel, und eine Aufzählung schnitte die
    zusätzlichen still weg (dieselbe Erwägung wie bei ``ConversationTurn``).
    Als ``list`` deklariert war das ein 500 an jedem fertigen Job.
    """
    id: str
    question: str
    status: str
    report: str | None
    sources: dict[str, Any] | None
    seen: int
    created: str
    updated: str


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


class MoneyDriver(TypedDict):
    """Der größte Einzel-Euro-Beschluss eines Quartals — die Tatsache hinter
    dem Balken. Ein Quartal ohne Geldbeschluss trägt ``null``."""
    id: int
    title: str
    eur: float


class EmergingTag(TypedDict):
    """Ein Schlagwort, das in den letzten beiden Quartalen auffällig oft
    vorkam (mindestens zweimal), ohne Verfahrens-Vokabular."""
    tag: str
    n: int


class TrendData(TypedDict):
    """``CouncilStore.activity_trends`` plus die Klartext-Namen der Felder.

    Die Reihen standen hier bis 02.09.2026 als ``Any``. Das ist beim Vertrag
    nicht dasselbe wie „egal": Das Web leitet seine Typen aus diesen Formen
    ab, und was hier ``Any`` heißt, muss dort von Hand nachgetippt werden —
    mit allem, was Handarbeit an einer Schnittstelle bedeutet.
    """
    quarters: list[str]
    #: Je Themenfeld eine Zahl pro Quartal, in der Reihenfolge von ``quarters``.
    fields: list[str]
    by_field: dict[str, list[int]]
    money: list[float]
    money_drivers: list[MoneyDriver | None]
    emerging: list[EmergingTag]
    #: Klartext-Namen der Themenfelder. Die Route rechnet sie aus `POLICY_FIELDS`
    #: aus und hängt sie an — undeklariert hat FastAPI sie wieder ENTFERNT, und
    #: die App las ein Pflichtfeld, das nie ankam: Die Trend-Ansicht brach beim
    #: Decodieren ab, nicht sichtbar als Fehler, sondern als leere Seite.
    field_labels: dict[str, str]
class PublicNumbers(TypedDict):
    """Die drei Kennzahlen der öffentlichen Startseite — ohne Anmeldung,
    ohne Inhalte (``CouncilStore.public_stats``)."""
    decisions: int
    sessions: int
    entities: int


class EntityHead(TypedDict):
    """Der Kopf einer Themen-Seite: Slug, Name, Art und Beschlusszahl."""
    slug: str
    name: str
    kind: str | None
    n: int


class EntityGeo(TypedDict):
    """Verortung eines Themas — ``None``, wo keine Koordinaten vorliegen.
    ``geojson`` ist der geparste Umriss, wo einer hinterlegt ist."""
    lat: float
    lon: float
    geojson: dict[str, Any] | None


class EntityFieldCount(TypedDict):
    field: str
    n: int


class RelatedEntity(TypedDict):
    """Ein Nachbar-Thema (``CouncilStore.related_entities``).

    ``evidence`` ist die Zahl der Beschlüsse, in denen beide zusammen
    vorkommen; ``score`` gewichtet das gegen ihre Häufigkeit.
    """
    slug: str
    name: str
    kind: str
    n: int
    rel_type: str
    evidence: int
    score: float


class EntityDetail(TypedDict):
    """Eine Themen-Seite mit allen ihren Beschlüssen und den Aggregaten.

    Festes Literal aus ``CouncilStore.entity_detail``, um ``field_labels`` und
    ``related`` vom Router ergänzt — deshalb vollständig und ohne
    ``NotRequired``. ``merged_from`` trägt den alten Slug, wenn die Seite über
    ein zusammengeführtes Alias erreicht wurde (das Frontend leitet dann um).
    """
    entity: EntityHead
    description: str | None
    geo: EntityGeo | None
    decisions: list[DecisionRow]
    # Entdoppelte Summe der erkannten Beträge, 0 wenn nichts erkannt wurde.
    money: int
    parties: list[str]
    fields: list[EntityFieldCount]
    merged_from: str | None
    # legt der Router dazu
    field_labels: dict[str, str]
    related: list[RelatedEntity]


class Speech(TypedDict):
    """Ein Wortbeitrag aus einem Protokoll."""
    committee: str | None
    session_date: str | None
    agenda_item: str | None
    kind: str | None
    text: str


class SpeechCommittee(TypedDict):
    committee: str
    n: int


class Speeches(TypedDict):
    """Wortbeiträge einer Person (``CouncilStore.wortbeitraege_person``).

    Zwei Zahlen, weil es zwei Dinge sind: ``total`` gilt zum gesetzten
    Gremien-Filter, ``overall`` ist der Bestand der Person über alle Gremien —
    daran hängt die Zeile „N Wortbeiträge" auf der Personen-Seite.
    """
    items: list[Speech]
    total: int
    overall: int
    committees: list[SpeechCommittee]


class PersonCommittee(TypedDict):
    committee: str
    n: int
    chair: bool


class PersonSession(TypedDict):
    ksinr: int
    committee: str
    session_date: str


class FactionPhase(TypedDict):
    """Eine Phase der Fraktions-/Gruppenzugehörigkeit aus den
    Anwesenheitslisten — die einzige echte Zeitreihe, denn das
    Ratsinformationssystem überschreibt Fraktionen rückwirkend."""
    label: str
    kind: str
    parties: list[str]
    first: str
    last: str
    n: int


class Affiliation(TypedDict):
    """Die aktuelle Zugehörigkeit eines Mitglieds.

    Genau drei Schlüssel, nicht die sechs der Zeitreihe daneben: Der Kopf der
    Seite nennt die AUFGELÖSTE Zugehörigkeit („FDP/Volt" → FDP), die Zeitreihe
    darunter bleibt quellentreu und erzählt, was die Protokolle damals
    schrieben.
    """
    label: str
    kind: str
    parties: list[str]


class PersonCouncil(TypedDict):
    """Das Profil eines Mandats- oder beratenden Mitglieds
    (``CouncilStore.member_detail``, ``type`` legt der Router dazu).

    ``kind`` unterscheidet innerhalb dieses Zweigs noch einmal: ``council`` ist
    ein Ratsmandat, ``advisory`` eine beratende Mitwirkung — für die ist die
    Fraktions-Zeitreihe gegenstandslos, ``party``/``current_affiliation``
    bleiben dann leer und ``organisation`` nennt die entsendende Stelle.
    """
    type: Literal["council"]
    name: str
    slug: str
    party: str | None
    current_affiliation: Affiliation | None
    kind: Literal["council", "advisory"]
    organisation: str | None
    n_sessions: int
    active_from: str | None
    active_to: str | None
    faction_timeline: list[FactionPhase]
    ris: Any
    committees: list[PersonCommittee]
    recent: list[PersonSession]
    speeches: list[Speech]
    speeches_total: int
    speeches_committees: list[SpeechCommittee]


class PersonAdministration(TypedDict):
    """Der schmale Steckbrief einer Verwaltungsperson mit erkanntem Amt
    (``CouncilStore.verwaltung_detail``). ``von``/``bis`` sind die Jahres-Spanne
    der Protokoll-Erwähnungen, KEINE amtliche Amtszeit."""
    type: Literal["administration"]
    name: str
    slug: str
    role: str
    aktiv: bool
    von: str | None
    bis: str | None
    speeches: list[Speech]
    speeches_total: int
    speeches_committees: list[SpeechCommittee]


# Zwei Zustände, unterscheidbar an `type` — als echte Union statt einer Form mit
# lauter NotRequired: Das Frontend rendert zwei verschiedene Ansichten, und
# beide Clients sollen erst nach der Prüfung auf `type` an die Felder kommen.
PersonDetail = PersonCouncil | PersonAdministration


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
    catalog: PlaceCatalogHead
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
    outcome: Beschlussergebnis | None
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
    provenance: Provenance
    editions: Any
    totals: Any
    #: {"A": "Beamtinnen und Beamte", "B": …} aus ``council.stellenplan``.
    part_names: dict[str, str]
    rows: Any


class BudgetExecution(TypedDict):
    scope_note: Any
    #: Drei feste Nachschlagewerke aus ``council.budget_execution``:
    #: der Erklärsatz je Plan-Grundlage, die Namen der Haushalte und die
    #: der Ergebnisarten. Alle drei sind dort ``dict[str, str]``.
    plan_basis_note: dict[str, str]
    budget_names: dict[str, str]
    kind_names: dict[str, str]
    editions: Any
    reporting_dates: list[Any]
    totals: Any
    rows: Any
    provenance: Provenance


class BudgetAuditReports(TypedDict):
    findings: list[Any]
    years: Any
    legend: Any
    without_report: list[Any]


class BudgetGroup(TypedDict):
    cross_check: Any
    provenance: Provenance
    years: Any
    consolidated: list[Any]
    items: Any
    entity: list[Any]


class BudgetHoldings(TypedDict):
    report_years: Any
    owners: Any
    companies: list[Any]
    provenance: Provenance
    years: list[Any]
    indicators: Any
    group_comparison: Any
    people: list[Any]
    texts: Any


class BudgetInvestments(TypedDict):
    financial_budget: list[Any]
    investments: list[Any]
    provenance: Provenance
    years: Any
    sub_budgets: list[Any]


class BudgetInvestmentProgram(TypedDict):
    totals: list[Any]
    provenance: Provenance
    years: Any
    measures: list[Any]
    sub_budgets: list[Any]


class DataLayer(TypedDict):
    """Eine Datenschicht des Haushalts und ihr Stand (``finanzquellen.datenstand``).

    Die Werte kommen aus dem Bestand, nicht aus einer gepflegten Liste — eine
    Angabe, die jemand von Hand nachziehen müsste, wäre genau die, die
    veraltet.

    ``unit`` und ``einheiten_voll`` sind ``None``, wo eine Schicht gar nicht in
    Einheiten zerfällt (am echten Bestand nachgemessen, nicht geraten).
    """
    key: str
    label: str
    was: str
    tabelle: str
    #: Woher die Zahlen stammen (``city``, ``ris``, ``lsn``) …
    herkunft: str
    #: … und dasselbe als Klartext für die Seite.
    source: str
    #: Holt ein Cron die Schicht von selbst, oder muss jemand nachhelfen?
    automatisch: bool
    jahrgaenge: list[int]
    luecken: list[int]
    #: Wie die Einheiten heißen, in die ein Jahrgang zerfällt (Teilhaushalte,
    #: Ebenen) — ``None``, wo es keine gibt.
    unit: str | None
    #: Je Jahrgang die Zahl der Einheiten. Schlüssel ist das Jahr als Text,
    #: weil JSON keine Zahlen als Schlüssel kennt.
    einheiten: dict[str, int]
    einheiten_voll: int | None
    teilweise: list[int]
    neuester: int | None
    #: Jahrgänge, die noch fehlen, und die davon schon überfällig sind.
    offen: list[int]
    ueberfaellig: list[int]
    naechster_jahrgang: int
    naechster_ab: str
    erwarteter_monat: int
    #: Der Monatsname dazu — hängt der Router an.
    month_name: str


class BudgetDataState(TypedDict):
    today: str
    layers: list[DataLayer]


class BudgetDocuments(TypedDict):
    documents: Any
    editions: Any


class BudgetPath(TypedDict):
    rounds: Any


class BudgetDispute(TypedDict):
    rounds: Any


class BudgetAmendmentLists(TypedDict):
    provenance: Provenance
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


class ResearchJobHead(TypedDict):
    """Der jüngste Recherche-Job eines Kontos — sechs Spalten, fester SELECT.

    Damit findet der Client nach einer Navigation oder einem App-Neustart
    einen laufenden Job wieder, ohne sich die ID gemerkt zu haben. Der volle
    Stand kommt danach über ``ResearchSnapshot``.

    ``id`` ist eine ZEICHENKETTE, kein Zähler: ein unerratbares Token, weil
    die Adresse eines Berichts sonst zu raten wäre.
    """
    id: str
    question: str
    status: str
    seen: int
    created: str
    updated: str


class ResearchCurrent(TypedDict):
    remaining: int | None
    job: ResearchJobHead | None


class ResearchStopped(TypedDict):
    facets_done: int
    facets_total: int
    partial_report_possible: bool


class QaExamples(TypedDict):
    sessions: Any


class TemplateFollow(TypedDict):
    """Ein verfolgter Vorgang samt Stand seiner Beratungsfolge.

    Die ersten sechs Felder sind die Spalten aus ``template_follows``, die
    drei darunter rechnet der Router je Vorgang aus. ``naechste`` und
    ``letzte`` heißen bewusst weiter deutsch: Die App liest sie so, und ein
    Umbenennen ohne Nachzug dort wäre ein stiller Ausfall.
    """
    id: int
    kvonr: int
    template_number: str | None
    title: str | None
    created_at: str
    notified_at: str | None
    url: str
    n_stationen: int
    #: Die nächste Station mit Datum in der Zukunft — ``None``, wenn keine
    #: mehr aussteht.
    naechste: DeliberationStop | None
    #: Die jüngste Station bis heute.
    letzte: DeliberationStop | None


class TemplateFollows(TypedDict):
    follows: list[TemplateFollow]


class TemplateFollowed(TypedDict):
    following: bool
    kvonr: int


class TemplateUnfollowed(TypedDict):
    following: bool
    kvonr: int


class MoneyByField(TypedDict):
    """Erkanntes Volumen je Themenfeld (``CouncilStore.money_by_field``)."""
    field: str
    n: int
    total: int


class Finances(TypedDict):
    by_field: list[MoneyByField]
    decisions: list[DecisionRow]
    #: {Themenfeld-Schlüssel: Klartext} aus ``council.topics.POLICY_FIELDS``.
    field_labels: dict[str, str]


class PolicyFieldRecaps(TypedDict):
    recaps: Any


class Entities(TypedDict):
    entities: Any


class CityMapPoint(TypedDict):
    """Ein Punkt der Stadtkarte (``CouncilStore.city_map_points``).

    Zwei Herkünfte in einer Liste, und sie tragen NICHT dieselben Felder:

    * ``kind="beschlussort"`` — aus dem Ortskatalog, mit Katalog-Bezug und
      Datum des jüngsten Beschlusses (gemessen 02.09.2026: 523 Punkte).
    * ``kind="place"`` / ``"organisation"`` — geocodierte Themen. Sie kennen
      weder Katalog noch Beschlussdatum; die fünf Felder unten fehlen dort
      **ganz**, sie stehen nicht auf ``null`` (121 Punkte).

    Deshalb ``NotRequired``. Als Pflichtfelder deklariert war das ein 500er auf
    der ganzen Karte: Ein fehlender Pflichtschlüssel ist für FastAPI ein
    ``ResponseValidationError``, nicht ein leeres Feld — 605 auf einmal, und
    die Antwort kam gar nicht erst heraus.

    ``target`` sagt, wohin ein Tippen führt.
    """
    slug: str
    name: str
    kind: str
    n: int
    lat: float
    lon: float
    target: str
    n_recent: NotRequired[int]
    last_date: NotRequired[str]
    #: Der Ort aus dem Katalog, wo einer zugeordnet ist.
    place_id: NotRequired[str | None]
    location_slug: NotRequired[str]
    local_area_id: NotRequired[str]


class EntitiesMap(TypedDict):
    entities: list[CityMapPoint]


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


class GoalDecision(TypedDict):
    """Ein Beschluss, der auf ein Nachhaltigkeitsziel einzahlt.

    ``stance`` und ``rationale`` kommen aus der LLM-Bewertung, alles andere
    aus dem Beschluss selbst. Am Bestand nachgemessen: keins der Felder ist
    je leer.
    """
    id: int
    title: str
    summary: str
    committee: str
    session_date: str
    outcome: Beschlussergebnis
    policy_field: str
    stance: str
    rationale: str


class GoalDetail(TypedDict):
    key: str
    label: str
    description: str
    summary: GoalMetrics
    decisions: list[GoalDecision]


class BudgetComparison(TypedDict):
    citation: Any
    provenance: Provenance
    years: Any
    cities: Any
    values: Any


class BalanceItem(TypedDict):
    """Ein Posten der Bilanz (``CouncilStore.get_bilanz_posten``).

    ``role`` ist unsere Zuordnung („wofür steht diese Zeile"), ``nr`` und
    ``label`` stehen so im Dokument, ``level`` sagt, wie tief der Posten
    eingerückt ist.
    """
    year: int
    nr: str
    label: str
    level: int
    value: float
    role: str
    page: str
    herkunft_id: int
    fetched_at: str


class AssetRow(TypedDict):
    """Eine Zeile des Anlagenspiegels — die Bewegung eines Anlagenpostens.

    Anfangsstand plus Zugänge minus Abgänge plus Umbuchungen ergibt den
    Endstand; ``probes`` nennt die Rechenproben, die diese Zeile bestanden
    hat. ``n_columns`` hält fest, wie viele Spalten das Dokument des Jahrgangs
    hatte — ältere Jahrgänge führen weniger.
    """
    year: int
    nr: str
    label: str
    cost_opening: float
    additions: float
    disposals: float
    transfers: float
    write_ups: float
    cost_closing: float
    depreciation_opening: float
    depreciation: float
    depreciation_releases: float
    depreciation_transfers: float
    depreciation_closing: float
    book_value: float
    book_value_prior_year: float
    n_columns: int
    probes: list[str]
    herkunft_id: int
    fetched_at: str


class AssetGroup(TypedDict):
    """Die Untergliederung des Infrastrukturvermögens (Straßen, Brücken,
    Gleisanlagen). Sie steht in einer ANDEREN Tabelle desselben Dokuments und
    gibt es erst ab 2022 — deshalb ein eigener Block und keine Spalte."""
    year: int
    group_name: str
    book_value: float
    book_value_prior_year: float
    herkunft_id: int
    fetched_at: str


class FixedAssets(TypedDict):
    """Der Anlagenspiegel als Block."""
    series: list[AssetRow]
    years: list[int]
    groups: list[AssetGroup]
    group_years: list[int]
    #: Rechenprobe → Erklärsatz für Leser*innen.
    probes: dict[str, str]


class BudgetFixedAssets(TypedDict):
    scope_note: Any
    fixed_assets: FixedAssets
    missing: Any
    provenance: Provenance
    years: list[Any]
    accounting_systems: list[Any]
    series: Any


class BudgetBalanceSheet(TypedDict):
    explanations: Any
    provenance: Provenance
    years: Any
    items: Any


class LoanNotice(TypedDict):
    """Eine Unterrichtung des Rates (``council_loan_notices``)."""
    template_number: str
    year: int
    period_from: str
    period_to: str
    document_date: str | None
    none_reported: int
    items: int
    interest_saving: float | None
    saving_from: str | None
    saving_to: str | None
    document_id: int | None
    document_url: str | None
class LiquidityMonth(TypedDict):
    """Ein Monatsende (``council_liquidity``)."""
    month: str
    year: int
    amount: float
    as_of: str
    confirmations: int
    revised_from: float | None
    document_id: int | None
    url: str | None
    template_number: str | None
    probes: list[str]
    herkunft_id: int | None
    fetched_at: str


class LoanItem(TypedDict):
    """Ein Posten einer Unterrichtung (``council_loan_items``) samt dem
    Berichtszeitraum seiner Vorlage."""
    template_number: str
    seq: int
    year: int
    #: loan | refinancing | prolongation | disbursement | lending | other
    kind: str
    borrower: str | None
    heading: str
    amount: float | None
    rate_pct: float | None
    fixed_years: int | None
    fixed_until: str | None
    decided_at: str | None
    summary: str | None
    herkunft_id: int | None
    fetched_at: str
    period_from: str
    period_to: str


# ``from`` ist ein Schlüsselwort — deshalb die funktionale Form.
LoanGap = TypedDict("LoanGap", {"from": int, "to": int})
LoanCoverage = TypedDict("LoanCoverage", {
    "from": str | None, "to": str | None, "gaps": list[LoanGap],
    "notices": int, "none_reported": int})


class LoanYear(TypedDict):
    year: int
    amount: float
    count: int
    saving: float
    saving_notices: int


class BudgetLoans(TypedDict):
    scope_note: str
    #: {"loan": "Kreditaufnahme", …} aus ``council.loans.ART_NAMEN``.
    kind_names: dict[str, str]
    notices: list[LoanNotice]
    items: list[LoanItem]
    coverage: LoanCoverage
    rates: list[LoanItem]
    refinancing_by_year: list[LoanYear]
    latest_refinancing: LoanItem | None
    #: Herkunft je ``herkunft_id`` der Unterrichtungen und Geschäfte — ohne
    #: sie stürzt der Kredite-Block ab (er liest ``provenance[id]``).
    provenance: Provenance


class LiquidityWindow(TypedDict):
    months: int
    min: LiquidityMonth | None
    max: LiquidityMonth | None


LiquidityCoverage = TypedDict("LiquidityCoverage", {
    "from": str | None, "to": str | None, "missing": list[str], "months": int})


class BudgetLiquidity(TypedDict):
    scope_note: str
    series: list[LiquidityMonth]
    latest: LiquidityMonth | None
    last_12: LiquidityWindow
    year_ends: list[LiquidityMonth]
    coverage: LiquidityCoverage
    provenance: Provenance


class GuaranteeRow(TypedDict):
    """Der Bürgschaftsbestand eines Jahrgangs.

    ``exact`` und ``out_next_year`` sind Angaben über den BELEG, nicht über
    die Zahl: Manche Jahrgänge stehen auf den Cent im Dokument, ab 2022 rundet
    die Quelle selbst auf Zehntel-Millionen, und einer steht überhaupt nur im
    Abschluss des Folgejahres. Wer alle gleich formatiert, behauptet eine
    Genauigkeit, die es nicht für alle gibt.
    """
    year: int
    balance: float
    exact: bool
    out_next_year: bool
    single_amount: float | None
    reason: str | None
    source: str
    probes: list[str]
    herkunft_id: int
    fetched_at: str


class GuaranteeTemplate(TypedDict):
    """Eine Ratsvorlage zu einer Bürgschaft — als Geschichte, nicht als Summe.

    Unter den Vorlagen sind Verlängerungen und Anpassungen derselben
    Bürgschaft; addiert zählte man dieselbe Zusage mehrfach. Was der Bestand
    ist, sagt allein der Jahresabschluss.
    """
    template_number: str
    title: str
    document_url: str
    decision_id: int | None
    date: str | None


class Guarantees(TypedDict):
    """Die Bürgschaften als Block."""
    series: list[GuaranteeRow]
    provision: list[BalanceItem]
    financial_debt: list[BalanceItem]
    #: Der Satz, der erklärt, warum eine Bürgschaft keine Schuld ist.
    scope_note: str
    templates: list[GuaranteeTemplate]


class BudgetDebt(TypedDict):
    scope_note: Any
    column_kinds: list[Any]
    guarantees: Guarantees
    provenance: Provenance
    integrated_debt: Any
    years: list[Any]
    series: Any
    interest_expense: Any


class CalendarSubscription(TypedDict):
    """Die Kalender-Adresse eines Kontos (``/api/calendar/subscription``).

    ``url`` ist die https-Adresse zum Kopieren, ``webcal_url`` dieselbe mit
    dem Schema, das auf dem Telefon direkt den Abo-Dialog öffnet.
    """
    url: str
    webcal_url: str
    subscribed_committees: int


# --------------------------------------------------------------------------
# Antworten, die kein JSON sind
#
# Drei Endpunkte liefern keinen JSON-Körper: zwei Server-Sent-Event-Ströme und
# eine Bilddatei. Ein ``TypedDict`` wäre dort schlicht falsch — es behauptete
# ein Objekt, wo ein Strom bzw. ein JPEG kommt, und beide Generatoren bauten
# daraus einen Typ, den nie jemand bekommt. Stattdessen steht hier je eine
# ``responses=``-Angabe für den Dekorator: richtiger Medientyp, und in der
# Beschreibung, was tatsächlich über die Leitung geht.
#
# Die Ereignis-Arten sind aufgezählt, weil sie der eigentliche Vertrag sind:
# Wer einen Client gegen diese Ströme baut, muss wissen, welche ``type``-Werte
# vorkommen können. Sie stehen als Text und nicht als Schema, weil ein
# SSE-Rahmen Text IST — die JSON-Nutzlast steckt in seiner ``data:``-Zeile.
#
# **Die ``response_class`` gehört dazu und ist nicht optional.** FastAPI leitet
# den Medientyp der 200er-Antwort aus ihr ab; ohne sie steht neben unserer
# ``responses=``-Angabe weiterhin ein leeres ``application/json``-Schema, und
# die Doku behauptete wieder ein JSON-Objekt. Zur Laufzeit ändert sich nichts:
# Die Handler bauen ihre Antwort weiter selbst.
# --------------------------------------------------------------------------


class EventStreamResponse(StreamingResponse):
    """``StreamingResponse`` mit festem SSE-Medientyp — nur fürs Schema."""
    media_type = "text/event-stream"


class JpegResponse(FileResponse):
    """``FileResponse`` mit festem JPEG-Medientyp — nur fürs Schema."""
    media_type = "image/jpeg"


class CalendarResponse(Response):
    """``Response`` mit festem ICS-Medientyp — nur fürs Schema."""
    media_type = "text/calendar"

#: ``POST /api/council/ask`` — die KI-Frage, Token für Token.
SSE_FRAGE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "Server-Sent Events (`text/event-stream`). Jeder Rahmen ist eine "
            "`data:`-Zeile mit einem JSON-Objekt, das ein Feld `type` trägt:\n\n"
            "- `step` — Fortschritt, `step` ist `expand`, `search` oder `answer`\n"
            "- `sources` — die gefundenen Beschlüsse samt `mode` und `qtype`, "
            "sobald Retrieval und Rerank fertig sind\n"
            "- `token` — ein Stück Antworttext (`text`)\n"
            "- `replace` — ersetzt den bisher gesendeten Text vollständig\n"
            "- `suggestions` — Anschlussfragen (`questions`)\n"
            "- `abbruch` — die Antwort wurde abgebrochen\n"
            "- `done` — Schluss-Ereignis mit `cited`, `timings` und "
            "`conversation_id`\n"
            "- `error` — die Frage ist fehlgeschlagen (`message`)\n\n"
            "Ein Verbindungsabriss ist folgenlos: Der Client kann die Frage "
            "neu stellen."
        ),
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    },
}

#: ``GET /api/council/deep-research/{job_id}/events`` — die tiefe Recherche.
SSE_RECHERCHE: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "Server-Sent Events (`text/event-stream`). Erst ein Replay aller "
            "Ereignisse ab `ab`, dann live weiter. Jeder Rahmen ist eine "
            "`data:`-Zeile mit einem JSON-Objekt und einem Feld `type`:\n\n"
            "- `phase` — `zerlegen`, `lesen` (mit `dokumente`) oder `schreiben`\n"
            "- `facets` — die Namen der Facetten, in die die Frage zerfällt\n"
            "- `facette` — eine Facette ist fertig (`name`, `treffer`)\n"
            "- `sources` — die Quellen der Recherche\n"
            "- `token` — ein Stück Berichtstext (`text`)\n"
            "- `replace` — ersetzt den bisher gesendeten Text vollständig\n"
            "- `done` — Schluss-Ereignis mit `cited` und `documents_read`\n"
            "- `gestoppt` — auf Wunsch abgebrochen (`facets_done`)\n"
            "- `fehler` — die Recherche ist fehlgeschlagen\n\n"
            "Ein Verbindungsabriss ist folgenlos — der Job läuft im Backend "
            "weiter, der Client verbindet sich einfach neu."
        ),
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    },
    410: {"description": "Die Recherche ist nicht mehr aktiv — den Snapshot "
                         "über `GET /api/council/deep-research/{job_id}` laden."},
}

#: ``GET /api/council/plan-bild/{document_id}`` — die gerenderte Planzeichnung.
CALENDAR_ICS: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "Der Kalender des Kontos als ICS (RFC 5545): die Sitzungen der "
            "abonnierten Ausschüsse und zu den eigenen Themen, je Termin die "
            "wichtigsten Punkte und der Link zur Sitzungsseite. Für Kalender-"
            "Apps gedacht, die die Adresse alle paar Stunden abrufen."
        ),
        "content": {"text/calendar": {"schema": {"type": "string"}}},
    },
    404: {"description": "Unbekannte oder erneuerte Kalender-Adresse."},
}


PLANZEICHNUNG_JPEG: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "Die gerenderte Planzeichnung als JPEG. `?thumb=true` liefert die "
            "Vorschaugröße. Ein gerendertes Blatt ändert sich nie, die Antwort "
            "ist deshalb `immutable` und dreißig Tage cachebar."
        ),
        "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
    },
    404: {"description": "Zu dieser Anlage gibt es kein gerendertes Bild."},
}
