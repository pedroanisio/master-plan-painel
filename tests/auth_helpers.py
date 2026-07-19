"""Shared helpers for authenticating a TestClient in resource API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def register(
    client: TestClient,
    *,
    username: str = "alice",
    email: str | None = None,
    password: str = "sup3rsecret",
) -> dict:
    """Register a user and return the parsed AuthResponse (user + token)."""
    email = email or f"{username}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password_confirm": password,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_header(token: str) -> dict[str, str]:
    """Build an Authorization header for a bearer ``token``."""
    return {"Authorization": f"Bearer {token}"}


def authenticate(client: TestClient, **kwargs: object) -> str:
    """Register a user and set the bearer token as the client's default header.

    Returns the access token. Subsequent client calls are authenticated.
    """
    body = register(client, **kwargs)  # type: ignore[arg-type]
    token = body["token"]["access_token"]
    client.headers.update(auth_header(token))
    return token
