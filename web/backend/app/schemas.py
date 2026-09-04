"""Pydantic request/response models."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Anzeigename für die persönliche Ansprache — serverseitig optional
    # (Apple-Konten und Alt-Bestand haben keinen).
    display_name: str | None = Field(default=None, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1)


#: Die Rolle eines Kontos. Steht als Literal und nicht als ``str``, damit die
#: Aufzählung im Vertrag ankommt — sonst muss jeder Client sie abschreiben,
#: und genau das ist passiert: Das Web führte die Vereinigung von Hand, und
#: sie war unvollständig (``blocked`` fehlte).
Rolle = Literal["user", "admin"]

#: Der Zustand eines Kontos. ``blocked`` kann nur über ein Skript entstehen —
#: die Admin-Oberfläche setzt nur ``active`` und ``pending``. Es steht hier
#: trotzdem: Eine Antwortform, die einen vorhandenen Wert verschweigt, ist ein
#: 500er in dem Moment, in dem er auftaucht.
Kontostand = Literal["pending", "active", "blocked"]

#: Wohin Benachrichtigungen gehen — ``off`` heißt: gar nicht.
Zustellweg = Literal["email", "push", "both", "off"]

#: Was aus einem Tagesordnungspunkt geworden ist. Dieselbe Aufzählung wie
#: ``antworten.Beschlussergebnis``; ein Wächter hält beide zusammen.
Beschlussergebnis = Literal["accepted", "rejected", "postponed", "noted", "no_decision"]


class UserOut(BaseModel):
    # Die Felder unten tragen bewusst KEINEN Vorgabewert mehr. Ein Vorgabewert
    # macht das Feld im Schema optional — obwohl FastAPI es beim Serialisieren
    # immer mitschickt. Der Vertrag sagte damit „darf fehlen" über etwas, das nie
    # fehlt, und die Clients mussten einen Fall behandeln, den es nicht gibt (die
    # App las sie zu Recht als Pflichtfelder, siehe tests/test_ios_vertrag.py).
    # Alle Erzeugungsstellen übergeben sie ohnehin ausdrücklich.
    id: int
    email: str
    role: Rolle
    status: Kontostand
    delivery_channel: Zustellweg
    email_verified: bool
    # Sign in with Apple (RL-1002): verknüpft? Und hat das Konto (noch) ein
    # selbst gesetztes Passwort? Steuert Konto-Chip + Passwort-Karte.
    apple_linked: bool
    has_password: bool
    # Populated only for native-app clients (which send `X-Client: app`) on
    # login/register/verify-email. Web clients authenticate via the httpOnly
    # cookie and leave this null.
    access_token: str | None = None
    display_name: str | None = None
    # Einwilligung „Gespräche merken" (null = nie gefragt). Reist mit dem
    # Konto mit, damit die Frage-Seite beim Öffnen sofort weiß, ob die
    # Erstnutzungs-Karte steht — sonst erscheint sie erst nach der Antwort von
    # /council/conversations und schiebt den halben Bildschirm nach unten
    # (gemessen: ein Sprung mit CLS 0,196 bei 600 ms Antwortzeit).
    saves_conversations: int | None = None


class AppConfigOut(BaseModel):
    """Compatibility contract consumed before a native app starts loading data."""

    min_build: int
    note: str | None = None


class TopicIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class TopicDescribeIn(BaseModel):
    """RL-U17: Name reicht — die Beschreibung entsteht aus den Beschlüssen.
    ``description`` ist optional und nur dafür da, einen selbst getippten Text
    zusätzlich auf Vagheit prüfen zu lassen."""

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class TopicSeenIn(BaseModel):
    """Was als gesehen gilt: ohne ``decision_id`` alle Treffer des Themas, mit
    ihr genau dieser eine. Optional, damit ältere App-Versionen, die nur
    ``{}`` senden, weiterhin alles markieren."""

    decision_id: int | None = None


class TopicHitOut(BaseModel):
    """Ein Beschluss-Treffer, wie ihn die Themen-Karte zeigt.

    Bewusst schlank: Titel, Herkunft, Ergebnis. Die Karte listet seit dem
    Umbau vom 28.08.2026 die jüngsten Treffer direkt, statt nur den letzten
    zu nennen — „Meine Themen" soll man durchsehen können, ohne erst jedes
    Thema einzeln zu öffnen.
    """

    id: int
    title: str
    committee: str
    session_date: str
    outcome: Beschlussergebnis | None = None
    # Noch nicht gesehen (dieselbe Menge, die das „n neue"-Abzeichen zählt).
    is_new: bool


class TopicOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    decision_count: int = 0
    # True, wenn der Matching-Lauf mehr relevante Beschlüsse gefunden hat, als
    # er speichern durfte. Die Karte schreibt dann „40+" — vorher stand dort
    # eine glatte Endzahl, die in Wahrheit der Deckel war (Tim, 15.08.2026:
    # „warum sind hier überall 25?").
    decision_count_capped: bool = False
    # Wurde für dieses Thema überhaupt schon einmal abgeglichen? Trennt die
    # zwei Nullen, die auf der Karte gleich aussahen: „gerechnet, der Rat hat
    # dazu wirklich nichts entschieden" und „noch nicht gerechnet". Für beides
    # stand dort „Noch keine Treffer — wir melden uns, sobald der Rat dazu
    # entscheidet", und bei einem frisch angelegten Thema war das eine
    # Falschaussage über den Rat (Tim, 28.08.2026: „fühlt sich so an, als wären
    # die Themen erst dann aufgekommen").
    matched: bool = False
    # Jüngster Beschluss-Treffer (RL-701: „letzter Treffer"-Zeile der Themen-Karte)
    last_hit_id: int | None = None
    last_hit_title: str | None = None
    last_hit_date: str | None = None
    unread_count: int = 0
    # Die jüngsten Treffer selbst (neueste zuerst, höchstens fünf) — der Kern
    # des Umbaus vom 28.08.2026: Die Karte trug bisher eine Zahl und einen
    # einzigen Titel, man musste also jedes Thema öffnen, um zu sehen, was
    # drinsteht.
    recent_hits: list[TopicHitOut] = []
    # Treffer des letzten halben Jahres — die zweite Hälfte der Zeile
    # „12 gesamt · 3 in 6 Monaten". Sie sagt, ob ein Thema gerade läuft oder
    # ruht; die Gesamtzahl allein kann beides bedeuten. Bis zum 28.08.2026
    # waren es 30 Tage, was bei fast jedem Thema eine 0 ergab: Die Gremien
    # tagen monatlich, im Sommer gar nicht, und Protokolle kommen mit Verzug.
    hits_6m: int = 0


# ---- subscriptions ----
class SubscriptionIn(BaseModel):
    committee_name: str


class EntityAliasIn(BaseModel):
    """Zwei Themen von Hand zusammenführen (Admin)."""
    slug: str
    canonical_slug: str
    reason: str | None = None


class EntityAliasOut(BaseModel):
    """Eine Zusammenführung. ``alias_name`` stammt aus den Roh-Beobachtungen —
    das Thema selbst existiert nach dem Zusammenführen nicht mehr eigenständig."""
    slug: str
    canonical_slug: str
    source: str
    reason: str | None = None
    created_at: str
    alias_name: str | None = None
    canonical_name: str | None = None
    canonical_n: int | None = None


class PlaceReviewIn(BaseModel):
    """Redaktionelles Urteil zu einem automatisch gefundenen Ortsnamen."""
    status: str
    place_id: str | None = None
    name: str | None = None
    kind: str | None = None
    parent_id: str | None = None
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    source_url: str | None = None
    quiz_enabled: bool = False
    canonical_place_id: str | None = None
    note: str | None = None


# ---- admin: web users ----
class WebUserOut(BaseModel):
    id: int
    email: str
    role: Rolle
    status: Kontostand = "pending"
    email_verified: bool = False
    created_at: str


class RoleUpdate(BaseModel):
    role: str  # 'user' | 'admin'


class StatusUpdate(BaseModel):
    status: str  # 'active' | 'pending'


class LimitsUpdate(BaseModel):
    """Admin-steuerbare Frage-Limits je Konto: Recherchen/Tag (None = Standard,
    0 = unbegrenzt, sonst eigenes Tageslimit) + Rate-Limit-Befreiung."""
    deep_limit: int | None = Field(default=None, ge=0, le=999)
    limits_unlocked: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    """Konto-Löschung verlangt eine frische Bestätigung — eine (evtl. offen
    liegende) Session allein darf das Konto nicht zerstören können. Konten mit
    Passwort bestätigen mit dem Passwort; Apple-only-Konten mit einem frischen
    Apple-Identity-Token (Re-Auth in der App, RL-1002)."""
    current_password: str = Field(default="", max_length=128)
    apple_identity_token: str = Field(default="", max_length=4096)
    apple_authorization_code: str = Field(default="", max_length=2048)


# ---- delivery channel ----
class DeliveryUpdate(BaseModel):
    #: ``off`` ist ein vollwertiger Zustellweg: gar nicht. Ohne ihn ließen sich
    #: Benachrichtigungen nur einzeln über die sechs Anlass-Schalter stumm
    #: stellen — sechs Handgriffe für etwas, das eine Person als einen denkt.
    delivery_channel: str = Field(pattern="^(email|both|push|off)$")


class NotifyPrefsIn(BaseModel):
    """Die sechs Anlass-Schalter aus Design 30a/E. Unbekannte Schlüssel wirft
    der Store weg — hier bleibt es bewusst offen, damit ein neu dazugekommener
    Anlass keinen 422 auslöst."""
    prefs: dict[str, bool]


# ---- Bürgerportal: private Meldeentwürfe ----
Problemkategorie = Literal[
    "mobility",
    "public_space",
    "education",
    "childcare",
    "housing",
    "environment",
    "accessibility",
    "administration",
    "other",
]
Ortsbezug = Literal["point", "facility", "route", "area", "citywide"]


class PrivateDraftContentIn(BaseModel):
    """Eng begrenzter privater Inhalt; die Store-Grenze prüft ihn erneut."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    category: Problemkategorie
    scope_kind: Ortsbezug
    observed_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    location_label: str = Field(default="", max_length=200)
    latitude: float | None = Field(default=None, ge=53.05, le=53.24)
    longitude: float | None = Field(default=None, ge=8.08, le=8.33)


class PrivateDraftCreateIn(PrivateDraftContentIn):
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class PrivateDraftUpdateIn(PrivateDraftContentIn):
    expected_revision: int = Field(ge=0, le=2**31 - 1)


class PrivateSubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0, le=2**31 - 1)
    confirmed_text: str = Field(min_length=1, max_length=4000)


# ---- feedback ----
class FeedbackIn(BaseModel):
    kind: str = Field(pattern="^(feature|bug|other)$")
    message: str = Field(min_length=3, max_length=4000)


class SupportIn(BaseModel):
    """Kontaktformular auf /hilfe — bewusst ohne Konto absendbar. Apples
    Richtlinie 1.5 verlangt einen Kontaktweg für *alle* Nutzer; der
    Feedback-Dialog in der App hilft genau dem nicht, der sich nicht anmelden
    kann. Die Adresse ist deshalb Pflicht: ohne sie gibt es keine Antwort."""
    kind: str = Field(pattern="^(konto|bug|feature|other)$")
    email: EmailStr
    message: str = Field(min_length=3, max_length=4000)
    # Honigtopf: für Menschen unsichtbar (off-screen + aria-hidden), einfache
    # Formular-Bots füllen jedes Feld aus. Gefüllt ⇒ still verwerfen.
    website: str = Field(default="", max_length=200)


# ---- onboarding ----
class OnboardingUpdate(BaseModel):
    """Fortschritts-Patch: erledigte Schritte (Whitelist im Router) und/oder
    das „Kurs abgeschlossen"-Flag."""
    steps: list[str] = Field(default_factory=list, max_length=16)
    celebrated: bool | None = None


# ---- quiz ----
class QuizAnswerIn(BaseModel):
    question_id: int
    selected_index: int | None = Field(default=None, ge=0, le=3)  # Multiple Choice
    value: float | None = None                                    # Schätzfrage (Slider)
    time_ms: int | None = Field(default=None, ge=0)


class QuizRateIn(BaseModel):
    question_id: int
    verdict: str = Field(pattern="^(gut|schlecht)$")
    comment: str | None = Field(default=None, max_length=500)


class QuizDailyIn(BaseModel):
    correct: int = Field(ge=0, le=50)
    total: int = Field(ge=1, le=50)
    points: int = Field(ge=0, le=500)


# Eigene Quizfragen (RL-U14): privat je Konto. Multiple-Choice (2–4 Antworten)
# ODER Schätzfrage (category "estimation": Zahl + Slider-Bereich statt Optionen).
class UserQuizQuestionIn(BaseModel):
    question: str = Field(min_length=5, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    correct_index: int = Field(default=0, ge=0, le=3)
    district: str | None = Field(default=None, max_length=60)
    category: str = Field(max_length=30)
    explanation: str | None = Field(default=None, max_length=500)
    # Schätzfrage: richtige Zahl, Einheit und (optionale) Slider-Grenzen.
    answer_value: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    range_min: float | None = None
    range_max: float | None = None


class UserQuizAnswerIn(BaseModel):
    question_id: int
    selected_index: int | None = Field(default=None, ge=0, le=3)  # Multiple Choice
    value: float | None = None                                    # Schätzfrage (Slider)


class QuizMapIn(BaseModel):
    target: str = Field(min_length=1, max_length=60)   # gefragter Stadtteil
    clicked: str = Field(min_length=1, max_length=60)   # angeklickter Stadtteil


# ---- push notifications (native app) ----
class PushRegisterRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    platform: str = Field(pattern="^(ios|android)$")


class PushUnregisterRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class SetupUpdate(BaseModel):
    """Design 26a: erreichter Schritt des Einrichtungs-Assistenten (0–3)."""

    step: int = Field(ge=0, le=3)
    done: bool = False
