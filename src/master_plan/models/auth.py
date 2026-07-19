"""Pydantic models for user registration and authentication.

This module is the authentication counterpart to the catalogue models. It
separates three concerns that are easy to conflate:

* :class:`UserRegistration` — the *input* a client submits to create an
  account: contact identity (``email``, ``username``), a ``password`` and its
  confirmation. Secrets are held in :class:`~pydantic.SecretStr` so they do not
  leak through ``repr``/logs, and the two password fields must match.
* :class:`Credentials` — the *input* for a login attempt: an ``identifier``
  (email or username) plus a ``password``.
* :class:`User` — the *domain* representation of an account with no secret
  material at all. It is safe to serialize and return to clients.

Password *hashes* are a persistence concern and deliberately live one layer
out, on the API record type — never on the domain :class:`User`.

Email is validated with a conservative regex rather than pulling in the
optional ``email-validator`` dependency, keeping the package dependency-free
(see the "No unnecessary dependencies" rule in ``CLAUDE.md``).

All models target Pydantic v2.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

__all__ = [
    "Role",
    "MIN_PASSWORD_LENGTH",
    "MIN_USERNAME_LENGTH",
    "MAX_USERNAME_LENGTH",
    "User",
    "UserRegistration",
    "Credentials",
]

# Password policy: a single source of truth used by every password field.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Username policy.
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32

# Conservative, dependency-free email shape check. Deliberately permissive:
# it rejects the obviously-malformed (no ``@``, spaces, empty parts) without
# claiming to fully implement RFC 5322 — real deliverability is verified out of
# band, not by a regex.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Usernames: a leading letter, then letters/digits and single separators
# (``_``, ``-``, ``.``). Length is enforced separately via Field constraints.
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*([._-][A-Za-z0-9]+)*$")


class Role(str, Enum):
    """Access level granted to a user.

    Ordered from least to most privileged. ``VIEWER`` is the safe default so a
    freshly registered account cannot mutate the catalogue until promoted.
    """

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


def _normalize_email(value: str) -> str:
    """Lower-case and validate an email address, or raise ``ValueError``."""
    cleaned = value.strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise ValueError(f"invalid email address: {value!r}")
    return cleaned


def _normalize_username(value: str) -> str:
    """Validate a username's character shape, or raise ``ValueError``.

    Length bounds are enforced by the field; this checks composition only.
    """
    cleaned = value.strip()
    if not _USERNAME_RE.match(cleaned):
        raise ValueError(
            "username must start with a letter and contain only letters, "
            "digits, and single '.', '_', or '-' separators"
        )
    return cleaned


def _validate_password(secret: SecretStr) -> SecretStr:
    """Enforce the length-based password policy on a :class:`SecretStr`."""
    raw = secret.get_secret_value()
    if len(raw) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    if len(raw) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"password must be at most {MAX_PASSWORD_LENGTH} characters"
        )
    return secret


class User(BaseModel):
    """A registered account, free of any secret material.

    This is the domain representation returned to clients. Password hashes are
    a persistence concern and live on the API record type, never here.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    email: str = Field(..., description="Contact email; unique, lower-cased.")
    username: str = Field(
        ...,
        min_length=MIN_USERNAME_LENGTH,
        max_length=MAX_USERNAME_LENGTH,
        description="Unique handle used to reference the account.",
    )
    full_name: str | None = Field(
        default=None,
        description="Optional human-readable display name.",
    )
    role: Role = Field(
        default=Role.VIEWER,
        description="Access level; defaults to the least-privileged viewer.",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the account may authenticate.",
    )

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        return _normalize_username(value)


class UserRegistration(BaseModel):
    """The body a client submits to create an account.

    Passwords are held as :class:`SecretStr` so they are redacted in ``repr``
    and structured logs. ``password`` and ``password_confirm`` must match; the
    strength policy is enforced on both.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    email: str = Field(..., description="Contact email; unique, lower-cased.")
    username: str = Field(
        ...,
        min_length=MIN_USERNAME_LENGTH,
        max_length=MAX_USERNAME_LENGTH,
        description="Requested unique handle.",
    )
    full_name: str | None = Field(
        default=None,
        description="Optional human-readable display name.",
    )
    password: SecretStr = Field(
        ...,
        description=f"Account password (min {MIN_PASSWORD_LENGTH} characters).",
    )
    password_confirm: SecretStr = Field(
        ...,
        description="Repeat of ``password``; must match exactly.",
    )

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: SecretStr) -> SecretStr:
        return _validate_password(value)

    @model_validator(mode="after")
    def _passwords_match(self) -> "UserRegistration":
        if (
            self.password.get_secret_value()
            != self.password_confirm.get_secret_value()
        ):
            raise ValueError("password and password_confirm do not match")
        return self

    def to_user(self, *, role: Role = Role.VIEWER) -> User:
        """Project the registration into a secret-free :class:`User`.

        The password is intentionally dropped — hashing and storage of the
        secret is the caller's (persistence layer's) responsibility.
        """
        return User(
            email=self.email,
            username=self.username,
            full_name=self.full_name,
            role=role,
        )


class Credentials(BaseModel):
    """A login attempt: an identifier plus a password.

    ``identifier`` accepts either the account email or username, so the login
    form needs a single field. The password is a :class:`SecretStr` for the
    same redaction reasons as registration.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    identifier: str = Field(
        ...,
        min_length=1,
        description="Account email or username.",
    )
    password: SecretStr = Field(..., description="Account password to verify.")
