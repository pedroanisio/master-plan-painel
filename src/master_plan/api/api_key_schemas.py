"""API request/response schemas for API-key management.

* :class:`ApiKeyRecord` — the persisted key: metadata plus ``token_sha256``
  (the verification hash; **never** emitted to a client).
* :class:`ApiKeyPublic` — the safe view returned by list endpoints (no hash,
  no plaintext).
* :class:`ApiKeyCreated` — returned once at creation: the public view plus the
  plaintext ``token``, which the server cannot show again.

⚠ ARCHITECTURAL NOTE: the plaintext token exists in a response exactly once
(creation). Everywhere else only the non-secret ``prefix`` identifies a key.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from master_plan.models.api_key import ApiKeyCreate, ApiKeyScope

__all__ = [
    "ApiKeyCreate",
    "ApiKeyRecord",
    "ApiKeyPublic",
    "ApiKeyCreated",
]


class ApiKeyPublic(BaseModel):
    """Secret-free view of a key, safe to return to its owner."""

    id: str
    name: str
    prefix: str = Field(..., description="Non-secret display id, e.g. 'mpk_a1b2c3d'.")
    scopes: list[ApiKeyScope]
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyCreated(ApiKeyPublic):
    """Creation response — carries the plaintext ``token`` exactly once."""

    token: str = Field(..., description="Plaintext key; shown only here, never again.")


class ApiKeyRecord(BaseModel):
    """A persisted API key. ``token_sha256`` is a hash, never a plaintext."""

    model_config = ConfigDict(extra="forbid")

    id: str
    owner_id: str
    name: str
    prefix: str
    token_sha256: str
    scopes: list[ApiKeyScope]
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        """True iff the key is neither revoked nor past its expiry at ``now``."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def public(self) -> ApiKeyPublic:
        """Project to the secret-free view (drops ``token_sha256``)."""
        return ApiKeyPublic(
            id=self.id,
            name=self.name,
            prefix=self.prefix,
            scopes=self.scopes,
            created_at=self.created_at,
            expires_at=self.expires_at,
            last_used_at=self.last_used_at,
            revoked_at=self.revoked_at,
        )
