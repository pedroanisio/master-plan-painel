"""API request/response schemas for authentication endpoints.

Mirrors the project/work-log schema split:

* :class:`UserRegistration` and :class:`Credentials` (from the domain layer)
  are the POST bodies for register and login, re-exported here for symmetry.
* :class:`UserRecord` — a persisted user: the domain :class:`User` plus a
  server-assigned ``id`` and the stored ``hashed_password``. The hash lives
  only on the record (persistence) type, never on the domain model.
* :class:`UserUpdate` — a partial patch where every field is optional.
* :class:`Token` / :class:`TokenPayload` — the bearer token returned on a
  successful login and its decoded claim set.

⚠ ARCHITECTURAL NOTE: ``hashed_password`` is a hash, never a plaintext or
reversible secret. Producing it (choice of KDF, salt, work factor) is the
responsibility of the auth service that constructs the record — this schema
only carries the already-hashed value and excludes it from responses.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from master_plan.models.auth import (
    MAX_USERNAME_LENGTH,
    MIN_USERNAME_LENGTH,
    Credentials,
    Role,
    User,
    UserRegistration,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "UserRecord",
    "UserUpdate",
    "Token",
    "TokenPayload",
    "AuthResponse",
    "Role",
    "User",
]

# Registration and login take the domain input models directly as their body.
RegisterRequest = UserRegistration
LoginRequest = Credentials


class UserRecord(User):
    """A persisted user: the domain model plus its id and stored password hash.

    ``hashed_password`` is excluded from serialization by default so it is
    never emitted in an API response; call ``model_dump(mode="json")`` and it
    stays hidden. Use :meth:`public` to obtain the secret-free domain view
    explicitly.
    """

    id: str = Field(..., description="Server-assigned unique identifier.")
    hashed_password: str = Field(
        ...,
        exclude=True,
        description="Salted password hash; never a plaintext secret.",
    )

    @classmethod
    def from_user(
        cls, id: str, user: User, *, hashed_password: str
    ) -> "UserRecord":
        """Combine an ``id`` and ``hashed_password`` with a domain :class:`User`."""
        return cls(id=id, hashed_password=hashed_password, **user.model_dump())

    def public(self) -> User:
        """Return the secret-free :class:`User` view (drops id and hash)."""
        return User.model_validate(
            self.model_dump(exclude={"id", "hashed_password"})
        )


class UserUpdate(BaseModel):
    """Partial update for a user; only provided fields are changed.

    Deliberately excludes ``email`` and password material: identity changes and
    credential rotation are distinct, security-sensitive flows that should not
    ride on a generic PATCH.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str | None = Field(
        default=None,
        min_length=MIN_USERNAME_LENGTH,
        max_length=MAX_USERNAME_LENGTH,
    )
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None

    def apply_to(self, user: User) -> User:
        """Return a new ``User`` with this patch's set fields overlaid."""
        patch = self.model_dump(exclude_unset=True)
        merged = {**user.model_dump(), **patch}
        return User.model_validate(merged)


class Token(BaseModel):
    """The bearer token issued on a successful login."""

    access_token: str = Field(..., description="Opaque or signed access token.")
    token_type: str = Field(
        default="bearer",
        description="Token scheme, per RFC 6750.",
    )
    expires_in: int | None = Field(
        default=None,
        gt=0,
        description="Token lifetime in seconds, if bounded.",
    )


class TokenPayload(BaseModel):
    """Decoded claims carried by an access token.

    ⚠ ARCHITECTURAL CONTRACT: a decoded token is untrusted input. Signature
    verification and expiry checks are the verifier's job before these claims
    are trusted — this model only shapes the payload, it does not authenticate.
    """

    model_config = ConfigDict(extra="ignore")

    sub: str = Field(..., description="Subject: the user id the token is for.")
    role: Role = Field(..., description="Access level asserted by the token.")
    exp: int | None = Field(
        default=None,
        description="Expiry as a Unix timestamp (seconds), if present.",
    )


class AuthResponse(BaseModel):
    """Returned on successful register/login: the token plus the public user.

    Bundling both lets the client store the session and render the signed-in
    identity from a single round-trip, without a follow-up ``/me`` call.
    """

    user: User = Field(..., description="The authenticated user (secret-free).")
    token: Token = Field(..., description="Bearer token for subsequent calls.")
