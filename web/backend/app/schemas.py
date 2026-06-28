"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# ---- auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


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
    telegram_chat_id: int | None = None
    linked: bool = False
    delivery_channel: str = "telegram"
    nwz_fulltext_allowed: bool = False
    email_verified: bool = False


# ---- linking ----
class LinkCodeOut(BaseModel):
    code: str
    bot_username: str
    expires_in_minutes: int


class LinkStatusOut(BaseModel):
    linked: bool
    telegram_chat_id: int | None = None


# ---- topics ----
class TopicIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class TopicOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    match_count: int = 0
    decision_count: int = 0


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
    telegram_chat_id: int | None = None
    nwz_fulltext_allowed: bool = False
    email_verified: bool = False
    created_at: str


class RoleUpdate(BaseModel):
    role: str  # 'user' | 'admin'


class StatusUpdate(BaseModel):
    status: str  # 'active' | 'pending'


class NwzFulltextUpdate(BaseModel):
    allowed: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---- delivery channel ----
class DeliveryUpdate(BaseModel):
    delivery_channel: str = Field(pattern="^(telegram|email|both)$")


# ---- feedback ----
class FeedbackIn(BaseModel):
    kind: str = Field(pattern="^(feature|bug|other)$")
    message: str = Field(min_length=3, max_length=4000)
