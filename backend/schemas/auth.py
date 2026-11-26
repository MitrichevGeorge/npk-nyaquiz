from datetime import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=100)
    locale: str = Field(default="ru", pattern="^(ru|en)$")
    consent_privacy: bool
    consent_terms: bool
    consent_disclaimer: bool
    consent_version: str = Field(default="1.0", max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, max_length=16)


class RecoverRequest(BaseModel):
    email: EmailStr


class UserProfile(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    locale: str
    totp_enabled: bool
    email_2fa_enabled: bool
    deletion_scheduled_at: datetime | None


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    backup_codes: list[str]


class TotpConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class QrInitResponse(BaseModel):
    token: str
    expires_in: int


class QrApproveRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)
