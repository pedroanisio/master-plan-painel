"""End-to-end tests for per-user API keys and scope enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from master_plan.api.api_key_repository import ApiKeyRepository
from master_plan.api.main import create_app
from master_plan.api.repository import ProjectRepository
from master_plan.api.user_repository import UserRepository


@pytest.fixture
def ctx(tmp_path: Path):
    app = create_app(
        repository=ProjectRepository(tmp_path / "p.json"),
        user_repository=UserRepository(tmp_path / "u.json"),
        api_key_repository=ApiKeyRepository(tmp_path / "k.json"),
    )
    client = TestClient(app)
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "ada@example.com", "username": "ada",
            "password": "correcthorse", "password_confirm": "correcthorse",
        },
    )
    token = resp.json()["token"]["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def _project(**over):
    body = {
        "name": "alpha", "color_id": 1, "domain": "dev",
        "purpose": "p", "languages": ["python"],
    }
    body.update(over)
    return body


def _make_key(client, session, **over):
    body = {"name": "k", "scopes": ["read"]}
    body.update(over)
    return client.post("/api/auth/api-keys", headers=session, json=body)


class TestCreate:
    def test_create_returns_token_once(self, ctx) -> None:
        client, session = ctx
        resp = _make_key(client, session, name="ci")
        assert resp.status_code == 201
        body = resp.json()
        assert body["token"].startswith("mpk_")
        assert body["prefix"].startswith("mpk_")
        assert body["name"] == "ci"
        assert body["scopes"] == ["read"]

    def test_secret_never_returned_by_list(self, ctx) -> None:
        client, session = ctx
        _make_key(client, session)
        rows = client.get("/api/auth/api-keys", headers=session).json()
        assert len(rows) == 1
        assert "token" not in rows[0]
        assert "token_sha256" not in rows[0]

    def test_empty_scopes_rejected(self, ctx) -> None:
        client, session = ctx
        assert _make_key(client, session, scopes=[]).status_code == 422

    def test_bad_scope_rejected(self, ctx) -> None:
        client, session = ctx
        assert _make_key(client, session, scopes=["admin"]).status_code == 422


class TestAuthWithKey:
    def test_read_key_can_read(self, ctx) -> None:
        client, session = ctx
        key = _make_key(client, session, scopes=["read"]).json()["token"]
        assert client.get("/api/projects", headers={"X-API-Key": key}).status_code == 200

    def test_bearer_mpk_prefix_also_works(self, ctx) -> None:
        client, session = ctx
        key = _make_key(client, session).json()["token"]
        r = client.get("/api/projects", headers={"Authorization": f"Bearer {key}"})
        assert r.status_code == 200

    def test_read_key_cannot_write(self, ctx) -> None:
        client, session = ctx
        key = _make_key(client, session, scopes=["read"]).json()["token"]
        r = client.post("/api/projects", headers={"X-API-Key": key}, json=_project())
        assert r.status_code == 403

    def test_write_key_can_write_and_read(self, ctx) -> None:
        client, session = ctx
        key = _make_key(client, session, scopes=["write"]).json()["token"]
        assert client.post(
            "/api/projects", headers={"X-API-Key": key}, json=_project()
        ).status_code == 201
        assert client.get(
            "/api/projects", headers={"X-API-Key": key}
        ).status_code == 200  # write implies read

    def test_key_acts_as_its_owner(self, ctx) -> None:
        client, session = ctx
        client.post("/api/projects", headers=session, json=_project(name="owned"))
        key = _make_key(client, session).json()["token"]
        rows = client.get("/api/projects", headers={"X-API-Key": key}).json()
        assert [p["name"] for p in rows] == ["owned"]

    def test_garbage_key_rejected(self, ctx) -> None:
        client, _ = ctx
        assert client.get(
            "/api/projects", headers={"X-API-Key": "mpk_not-real"}
        ).status_code == 401

    def test_revoked_key_rejected(self, ctx) -> None:
        client, session = ctx
        created = _make_key(client, session).json()
        key, key_id = created["token"], created["id"]
        assert client.delete(
            f"/api/auth/api-keys/{key_id}", headers=session
        ).status_code == 204
        assert client.get(
            "/api/projects", headers={"X-API-Key": key}
        ).status_code == 401

    def test_expired_key_rejected(self, ctx, tmp_path: Path) -> None:
        # Mint a key, then rewrite its stored expiry into the past.
        client, session = ctx
        created = _make_key(client, session, expires_in_days=1).json()
        key, key_id = created["token"], created["id"]
        repo = ApiKeyRepository(tmp_path / "k.json")
        rec = repo._records[key_id]
        from datetime import datetime, timezone
        past = datetime(2000, 1, 1, tzinfo=timezone.utc)
        repo._records[key_id] = rec.model_copy(update={"expires_at": past})
        repo._persist()
        # A fresh app over the same file must reject the expired key.
        app2 = create_app(
            repository=ProjectRepository(tmp_path / "p.json"),
            user_repository=UserRepository(tmp_path / "u.json"),
            api_key_repository=ApiKeyRepository(tmp_path / "k.json"),
        )
        assert TestClient(app2).get(
            "/api/projects", headers={"X-API-Key": key}
        ).status_code == 401


class TestManagementIsSessionOnly:
    def test_key_cannot_list_keys(self, ctx) -> None:
        client, session = ctx
        key = _make_key(client, session, scopes=["write"]).json()["token"]
        assert client.get(
            "/api/auth/api-keys", headers={"X-API-Key": key}
        ).status_code == 403

    def test_key_cannot_create_keys(self, ctx) -> None:
        client, session = ctx
        key = _make_key(client, session, scopes=["write"]).json()["token"]
        r = client.post(
            "/api/auth/api-keys", headers={"X-API-Key": key}, json={"name": "x"}
        )
        assert r.status_code == 403

    def test_revoke_unknown_is_404(self, ctx) -> None:
        client, session = ctx
        assert client.delete(
            "/api/auth/api-keys/nope", headers=session
        ).status_code == 404


class TestSessionUnaffected:
    def test_session_still_reads_and_writes(self, ctx) -> None:
        client, session = ctx
        assert client.post(
            "/api/projects", headers=session, json=_project()
        ).status_code == 201
        assert client.get("/api/projects", headers=session).status_code == 200

    def test_no_credential_is_401(self, ctx) -> None:
        client, _ = ctx
        assert client.get("/api/projects").status_code == 401
