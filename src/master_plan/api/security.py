"""Password hashing and bearer-token issuance, using only the stdlib.

Two independent primitives live here, both dependency-free (honoring the "no
unnecessary dependencies" rule in ``CLAUDE.md``):

* **Password hashing** — PBKDF2-HMAC-SHA256 with a per-password random salt.
  Hashes are stored as ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`` and
  verified in constant time via :func:`hmac.compare_digest`.
* **Bearer tokens** — a compact ``<payload>.<signature>`` token where the
  payload is base64url-encoded JSON and the signature is HMAC-SHA256 over the
  payload. This is *not* JWT (no external library, no alg negotiation); it is a
  minimal signed token sufficient for a single-service local tool.

⚠ ARCHITECTURAL CONTRACT: a token presented by a client is untrusted input.
:func:`decode_token` verifies the signature and expiry before returning claims;
callers must treat a raised :class:`TokenError` as an authentication failure.

The signing secret is read from ``MASTER_PLAN_SECRET``. A process-wide random
fallback is generated when the env var is absent so the app still runs locally —
but tokens then do not survive a restart. Set the env var in any real
deployment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

__all__ = [
    "hash_password",
    "verify_password",
    "create_token",
    "decode_token",
    "TokenError",
    "API_KEY_PREFIX",
    "generate_api_key",
    "hash_api_key",
]

# -- password hashing ------------------------------------------------------

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 hash string for ``password``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    )
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Return ``True`` iff ``password`` matches the ``stored`` hash string.

    Malformed hash strings return ``False`` rather than raising, so a corrupt
    record can never be mistaken for a successful authentication.
    """
    try:
        algorithm, iterations_s, salt_hex, expected_hex = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(digest, expected)


# -- bearer tokens ---------------------------------------------------------


class TokenError(ValueError):
    """Raised when a token is malformed, forged, or expired."""


def _secret() -> bytes:
    configured = os.environ.get("MASTER_PLAN_SECRET")
    if configured:
        return configured.encode("utf-8")
    return _EPHEMERAL_SECRET


# Generated once per process; used only when MASTER_PLAN_SECRET is unset.
_EPHEMERAL_SECRET = secrets.token_bytes(32)


def is_production() -> bool:
    """True when the service is configured to run in a production environment."""
    return os.environ.get("MASTER_PLAN_ENV", "").strip().lower() in {"production", "prod"}


def verify_signing_secret() -> None:
    """Fail fast at boot if production is missing a stable signing secret.

    The ephemeral fallback is fine for local dev, but in production it would
    silently invalidate every session on each restart and differ between
    workers — so refuse to start instead of degrading security quietly.
    """
    if is_production() and not os.environ.get("MASTER_PLAN_SECRET"):
        raise RuntimeError(
            "MASTER_PLAN_SECRET must be set when MASTER_PLAN_ENV=production; "
            "refusing to start with an ephemeral signing key that would drop "
            "all sessions on restart."
        )


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload_b64: str) -> str:
    signature = hmac.new(
        _secret(), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64url_encode(signature)


def create_token(
    *, subject: str, role: str, expires_in: int = 3600
) -> tuple[str, int]:
    """Issue a signed token for ``subject``; return ``(token, expires_in)``.

    ``expires_in`` is the token lifetime in seconds. The returned expiry echoes
    the input so a caller can populate a response without recomputing it.
    """
    if expires_in <= 0:
        raise ValueError("expires_in must be positive")
    claims = {
        "sub": subject,
        "role": role,
        "exp": int(time.time()) + expires_in,
    }
    payload_b64 = _b64url_encode(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    )
    return f"{payload_b64}.{_sign(payload_b64)}", expires_in


def decode_token(token: str) -> dict[str, object]:
    """Verify ``token`` and return its claims, or raise :class:`TokenError`."""
    try:
        payload_b64, signature = token.split(".")
    except (ValueError, AttributeError) as exc:
        raise TokenError("malformed token") from exc

    expected = _sign(payload_b64)
    if not hmac.compare_digest(signature, expected):
        raise TokenError("bad token signature")

    try:
        claims = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("unreadable token payload") from exc

    exp = claims.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise TokenError("token expired")
    return claims


# -- API keys --------------------------------------------------------------
#
# Unlike passwords, API keys are high-entropy random secrets, so a single fast
# SHA-256 is the correct store (GitHub-style) — a slow KDF buys nothing against
# a ~256-bit random token and would make the per-request lookup expensive. The
# stored hash enables an O(1) exact-match lookup; the plaintext is shown once.

API_KEY_PREFIX = "mpk_"


def generate_api_key() -> tuple[str, str, str]:
    """Mint a new API key.

    Returns ``(token, prefix, token_sha256)`` where ``token`` is the plaintext
    to hand to the user exactly once, ``prefix`` is a non-secret display id
    (safe to store and show in a UI), and ``token_sha256`` is what to persist.
    """
    token = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    prefix = token[: len(API_KEY_PREFIX) + 7]  # e.g. "mpk_a1b2c3d"
    return token, prefix, hash_api_key(token)


def hash_api_key(token: str) -> str:
    """Return the SHA-256 hex digest used to look up / verify an API key."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
