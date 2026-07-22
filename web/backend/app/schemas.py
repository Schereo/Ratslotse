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


class TopicIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class TopicOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    decision_count: int = 0
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


class PromptUpdate(BaseModel):
    content: str


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
    delivery_channel: str = Field(pattern="^(email|both|push)$")


# ---- feedback ----
class FeedbackIn(BaseModel):
    kind: str = Field(pattern="^(feature|bug|other)$")
    message: str = Field(min_length=3, max_length=4000)


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


# Eigene Quizfragen (RL-U14): privat je Konto, 2–4 Antworten.
class UserQuizQuestionIn(BaseModel):
    question: str = Field(min_length=5, max_length=300)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    stadtteil: str | None = Field(default=None, max_length=60)
    category: str = Field(max_length=30)
    explanation: str | None = Field(default=None, max_length=500)


class UserQuizAnswerIn(BaseModel):
    question_id: int
    selected_index: int = Field(ge=0, le=3)


class QuizMapIn(BaseModel):
    target: str = Field(min_length=1, max_length=60)   # gefragter Stadtteil
    clicked: str = Field(min_length=1, max_length=60)   # angeklickter Stadtteil


# ---- push notifications (native app) ----
class PushRegisterRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    platform: str = Field(pattern="^(ios|android)$")


class PushUnregisterRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
