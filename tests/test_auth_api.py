"""End-to-end tests for the authentication API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from master_plan.api.main import create_app
from master_plan.api.security import create_token
from master_plan.api.user_repository import UserRepository


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    users = UserRepository(tmp_path / "users.json")
    return TestClient(create_app(user_repository=users))


def _registration(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "email": "ada@example.com",
        "username": "ada",
        "password": "correcthorse",
        "password_confirm": "correcthorse",
    }
    body.update(overrides)
    return body


def _register(client: TestClient, **overrides: object):
    return client.post("/api/auth/register", json=_registration(**overrides))


class TestRegister:
    def test_register_returns_user_and_token(self, client: TestClient) -> None:
        resp = _register(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["user"]["email"] == "ada@example.com"
        assert body["user"]["role"] == "viewer"
        assert body["token"]["token_type"] == "bearer"
        assert body["token"]["access_token"]

    def test_password_hash_never_leaves_the_server(self, client: TestClient) -> None:
        body = _register(client).json()
        assert "hashed_password" not in body["user"]
        assert "password" not in body["user"]

    def test_duplicate_email_is_409(self, client: TestClient) -> None:
        _register(client)
        resp = _register(client, username="ada2")
        assert resp.status_code == 409
        error = resp.json()["error"]
        assert error["code"] == "duplicate_user"
        assert "email" in error["message"]

    def test_duplicate_username_is_409(self, client: TestClient) -> None:
        _register(client)
        resp = _register(client, email="other@example.com")
        assert resp.status_code == 409
        error = resp.json()["error"]
        assert error["code"] == "duplicate_user"
        assert "username" in error["message"]

    def test_mismatched_passwords_is_422(self, client: TestClient) -> None:
        resp = _register(client, password_confirm="different!")
        assert resp.status_code == 422

    def test_short_password_is_422(self, client: TestClient) -> None:
        resp = _register(client, password="short", password_confirm="short")
        assert resp.status_code == 422


class TestLogin:
    def test_login_with_email(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/auth/login",
            json={"identifier": "ada@example.com", "password": "correcthorse"},
        )
        assert resp.status_code == 200
        assert resp.json()["token"]["access_token"]

    def test_login_with_username(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/auth/login",
            json={"identifier": "ada", "password": "correcthorse"},
        )
        assert resp.status_code == 200

    def test_wrong_password_is_401(self, client: TestClient) -> None:
        _register(client)
        resp = client.post(
            "/api/auth/login",
            json={"identifier": "ada", "password": "wrong-password"},
        )
        assert resp.status_code == 401

    def test_unknown_user_is_401(self, client: TestClient) -> None:
        resp = client.post(
            "/api/auth/login",
            json={"identifier": "ghost", "password": "whatever12"},
        )
        assert resp.status_code == 401


class TestMe:
    def test_me_with_valid_token(self, client: TestClient) -> None:
        token = _register(client).json()["token"]["access_token"]
        resp = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "ada"

    def test_me_without_token_is_401(self, client: TestClient) -> None:
        assert client.get("/api/auth/me").status_code == 401

    def test_me_with_garbage_token_is_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not.a.token"}
        )
        assert resp.status_code == 401

    def test_me_with_token_for_unknown_user_is_401(self, client: TestClient) -> None:
        # Validly-signed token, but no such user in the store.
        token, _ = create_token(subject="does-not-exist", role="viewer")
        resp = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401


class TestPersistence:
    def test_accounts_survive_a_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "users.json"
        UserRepository(path)  # ensure directory setup path is exercised
        client = TestClient(create_app(user_repository=UserRepository(path)))
        _register(client)

        # A fresh repository over the same file must still authenticate.
        reloaded = TestClient(create_app(user_repository=UserRepository(path)))
        resp = reloaded.post(
            "/api/auth/login",
            json={"identifier": "ada", "password": "correcthorse"},
        )
        assert resp.status_code == 200
