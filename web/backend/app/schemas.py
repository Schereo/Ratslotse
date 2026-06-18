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


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    status: str = "pending"
    telegram_chat_id: int | None = None
    linked: bool = False
    nwz_verified: bool = False
    nwz_username: str | None = None


# ---- NWZ credentials ----
class NwzCredentialsIn(BaseModel):
    nwz_username: str = Field(min_length=1)
    nwz_password: str = Field(min_length=1)


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
    nwz_username: str | None = None
    nwz_verified_at: str | None = None
    created_at: str


class RoleUpdate(BaseModel):
    role: str  # 'user' | 'admin'


class StatusUpdate(BaseModel):
    status: str  # 'active' | 'pending'


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
