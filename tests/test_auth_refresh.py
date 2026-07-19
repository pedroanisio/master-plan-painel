"""Regression tests for the token refresh flow — POST /api/auth/refresh.

The refresh endpoint exchanges a still-valid session token for a fresh one
(sliding session). It is session-only, exactly like /api/auth/me: expired,
forged, or API-key credentials must be rejected with 401.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from master_plan.api.api_key_repository import ApiKeyRepository
from master_plan.api.main import create_app
from master_plan.api.repository import ProjectRepository
from master_plan.api.security import decode_token
from master_plan.api.user_repository import UserRepository


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(
        repository=ProjectRepository(tmp_path / "p.json"),
        user_repository=UserRepository(tmp_path / "u.json"),
        api_key_repository=ApiKeyRepository(tmp_path / "k.json"),
    )
    return TestClient(app)


def _register(client: TestClient, **over: object) -> dict:
    body: dict[str, object] = {
        "email": "ada@example.com",
        "username": "ada",
        "password": "correcthorse",
        "password_confirm": "correcthorse",
    }
    body.update(over)
    resp = client.post("/api/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRefreshHappyPath:
    def test_refresh_returns_a_working_session(self, client: TestClient) -> None:
        token = _register(client)["token"]["access_token"]

        resp = client.post("/api/auth/refresh", headers=_hdr(token))
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["user"]["username"] == "ada"
        assert body["token"]["expires_in"] > 0

        # The freshly minted token must itself authenticate.
        new_token = body["token"]["access_token"]
        me = client.get("/api/auth/me", headers=_hdr(new_token))
        assert me.status_code == 200
        assert me.json()["username"] == "ada"

    def test_refresh_extends_the_expiry(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Control the clock so the new token provably expires later.
        import master_plan.api.security as security

        now = [1_000_000]
        monkeypatch.setattr(security.time, "time", lambda: now[0])

        token = _register(client)["token"]["access_token"]
        old_exp = decode_token(token)["exp"]

        now[0] += 1800  # 30 min later — still inside the 1h TTL
        refreshed = client.post("/api/auth/refresh", headers=_hdr(token))
        assert refreshed.status_code == 200
        new_token = refreshed.json()["token"]["access_token"]
        new_exp = decode_token(new_token)["exp"]

        assert new_exp == now[0] + 3600
        assert new_exp > old_exp

    def test_public_route_advertises_refresh(self, client: TestClient) -> None:
        routes = client.get("/api/public").json()["authenticated_routes"]
        assert "POST /api/auth/refresh" in routes


class TestRefreshRejections:
    def test_missing_token_is_401(self, client: TestClient) -> None:
        assert client.post("/api/auth/refresh").status_code == 401

    def test_garbage_token_is_401(self, client: TestClient) -> None:
        resp = client.post("/api/auth/refresh", headers=_hdr("not.a.valid.token"))
        assert resp.status_code == 401

    def test_expired_token_is_401(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import master_plan.api.security as security

        now = [2_000_000]
        monkeypatch.setattr(security.time, "time", lambda: now[0])

        token = _register(client)["token"]["access_token"]
        now[0] += 3600 + 1  # jump just past the TTL
        assert client.post("/api/auth/refresh", headers=_hdr(token)).status_code == 401

    def test_api_key_cannot_refresh(self, client: TestClient) -> None:
        # An API key authenticates resource routes but must NOT refresh a
        # session — refresh is session-only, like /api/auth/me.
        token = _register(client)["token"]["access_token"]
        key = client.post(
            "/api/auth/api-keys",
            headers=_hdr(token),
            json={"name": "ci", "scopes": ["read"]},
        ).json()["token"]

        # Sanity: the key works on a resource route as a bearer credential.
        assert client.get("/api/projects", headers=_hdr(key)).status_code == 200
        # ...but it is rejected by refresh.
        assert client.post("/api/auth/refresh", headers=_hdr(key)).status_code == 401
