"""Domain types for per-user API keys.

An API key is an *alternate credential* a user mints so a third-party app can
call the REST API **as that user** — always owner-scoped, optionally narrowed
by :class:`ApiKeyScope` and bounded by an expiry. A key never widens access
beyond what its owner already has, and (by design, enforced in the API layer)
cannot manage keys or the account.

All models target Pydantic v2.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["ApiKeyScope", "ApiKeyCreate", "MAX_KEY_NAME_LENGTH", "MAX_EXPIRY_DAYS"]

MAX_KEY_NAME_LENGTH = 60
MAX_EXPIRY_DAYS = 3650  # ~10 years


class ApiKeyScope(str, Enum):
    """What a key may do. ``write`` implies read (enforced in the API layer)."""

    READ = "read"
    WRITE = "write"


class ApiKeyCreate(BaseModel):
    """The body a client submits to mint a key."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_KEY_NAME_LENGTH,
        description="Human label, e.g. 'Zapier production'.",
    )
    scopes: list[ApiKeyScope] = Field(
        default_factory=lambda: [ApiKeyScope.READ],
        description="Permissions granted to the key (at least one).",
    )
    expires_in_days: int | None = Field(
        default=None,
        gt=0,
        le=MAX_EXPIRY_DAYS,
        description="Optional lifetime in days; omit for a non-expiring key.",
    )

    @field_validator("scopes")
    @classmethod
    def _dedupe_nonempty(cls, value: list[ApiKeyScope]) -> list[ApiKeyScope]:
        """Require at least one scope; drop duplicates preserving order."""
        seen: list[ApiKeyScope] = []
        for scope in value:
            if scope not in seen:
                seen.append(scope)
        if not seen:
            raise ValueError("at least one scope is required")
        return seen
