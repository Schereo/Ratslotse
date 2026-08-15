"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


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


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    status: str = "pending"
    delivery_channel: str = "email"
    email_verified: bool = False
    # Sign in with Apple (RL-1002): verknüpft? Und hat das Konto (noch) ein
    # selbst gesetztes Passwort? Steuert Konto-Chip + Passwort-Karte.
    apple_linked: bool = False
    has_password: bool = True
    # Populated only for native-app clients (which send `X-Client: app`) on
    # login/register/verify-email. Web clients authenticate via the httpOnly
    # cookie and leave this null.
    access_token: str | None = None
    display_name: str | None = None
    # Einwilligung „Gespräche merken" (null = nie gefragt). Reist mit dem
    # Konto mit, damit die Frage-Seite beim Öffnen sofort weiß, ob die
    # Erstnutzungs-Karte steht — sonst erscheint sie erst nach der Antwort von
    # /council/gespraeche und schiebt den halben Bildschirm nach unten
    # (gemessen: ein Sprung mit CLS 0,196 bei 600 ms Antwortzeit).
    qa_speichern: int | None = None


class TopicIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class TopicDescribeIn(BaseModel):
    """RL-U17: Name reicht — die Beschreibung entsteht aus den Beschlüssen.
    ``description`` ist optional und nur dafür da, einen selbst getippten Text
    zusätzlich auf Vagheit prüfen zu lassen."""

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


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
    # Jüngster Beschluss-Treffer (RL-701: „letzter Treffer"-Zeile der Themen-Karte)
    last_hit_id: int | None = None
    last_hit_title: str | None = None
    last_hit_date: str | None = None
    unread_count: int = 0


# ---- subscriptions ----
class SubscriptionIn(BaseModel):
    committee_name: str


# ---- admin: prompts ----
class PromptOut(BaseModel):
    key: str
    title: str
    description: str
    content: str
    default: str
    is_overridden: bool
    # Design 21a: „geändert von … · wann“.
    updated_at: str | None = None
    updated_by: str | None = None


class PromptUpdate(BaseModel):
    content: str


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


# ---- admin: web users ----
class WebUserOut(BaseModel):
    id: int
    email: str
    role: str
    status: str = "pending"
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
    limits_frei: bool = False


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
# ODER Schätzfrage (category "schaetzen": Zahl + Slider-Bereich statt Optionen).
class UserQuizQuestionIn(BaseModel):
    question: str = Field(min_length=5, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    correct_index: int = Field(default=0, ge=0, le=3)
    stadtteil: str | None = Field(default=None, max_length=60)
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
