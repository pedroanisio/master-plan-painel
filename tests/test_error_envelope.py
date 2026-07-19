"""Tests for the unified error envelope contract.

Every error response the API emits — validation, auth, domain conflict, not
found, and unexpected server faults — must share one JSON shape::

    {"error": {"code": str, "message": str, "request_id": str, "details"?: [...]}}

and carry an ``X-Request-ID`` header for correlation. These tests pin that
contract so no route can regress to FastAPI's bare ``{"detail": ...}`` shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from master_plan.api.main import create_app, get_repository
from master_plan.api.repository import ProjectRepository
from master_plan.api.user_repository import UserRepository

from tests.auth_helpers import authenticate


def _build_client(tmp_path: Path) -> TestClient:
    projects = ProjectRepository(tmp_path / "projects.json")
    users = UserRepository(tmp_path / "users.json")
    # raise_server_exceptions=False so the 500 handler runs instead of the
    # exception bubbling into the test as a raw Python error.
    return TestClient(
        create_app(projects, user_repository=users),
        raise_server_exceptions=False,
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    c = _build_client(tmp_path)
    authenticate(c)
    return c


def _assert_envelope(body: object) -> dict:
    """Assert ``body`` is a well-formed error envelope and return the inner error."""
    assert isinstance(body, dict), body
    assert set(body) == {"error"}, body
    error = body["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["request_id"], str) and error["request_id"]
    return error


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "alpha",
        "color_id": 7,
        "domain": "developer-tooling",
        "purpose": "Track codebases.",
        "languages": ["python"],
        "packages": [{"name": "pydantic", "version": "2.12.5"}],
    }
    body.update(overrides)
    return body


# -- shape + correlation header -------------------------------------------
def test_not_found_uses_envelope(client: TestClient) -> None:
    resp = client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404
    error = _assert_envelope(resp.json())
    assert error["code"] == "not_found"
    assert resp.headers["X-Request-ID"] == error["request_id"]


def test_unauthenticated_uses_envelope() -> None:
    # No auth header at all.
    from master_plan.api.main import create_app as _ca

    c = TestClient(_ca())
    resp = c.get("/api/projects")
    assert resp.status_code == 401
    error = _assert_envelope(resp.json())
    assert error["code"] == "unauthorized"
    # Auth challenge header is preserved through the envelope handler.
    assert resp.headers["WWW-Authenticate"] == "Bearer"


# -- domain conflicts carry specific, stable codes ------------------------
def test_duplicate_name_code(client: TestClient) -> None:
    client.post("/api/projects", json=_payload())
    resp = client.post("/api/projects", json=_payload(name="Alpha"))
    assert resp.status_code == 409
    error = _assert_envelope(resp.json())
    assert error["code"] == "duplicate_name"


def test_duplicate_color_code(client: TestClient) -> None:
    client.post("/api/projects", json=_payload(name="alpha", color_id=7))
    resp = client.post("/api/projects", json=_payload(name="beta", color_id=7))
    assert resp.status_code == 409
    error = _assert_envelope(resp.json())
    assert error["code"] == "duplicate_color"


def test_duplicate_user_code(tmp_path: Path) -> None:
    c = _build_client(tmp_path)
    from tests.auth_helpers import register

    register(c, username="alice", email="alice@example.com")
    resp = c.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "other@example.com",
            "password": "sup3rsecret",
            "password_confirm": "sup3rsecret",
        },
    )
    assert resp.status_code == 409
    error = _assert_envelope(resp.json())
    assert error["code"] == "duplicate_user"


# -- validation surfaces field-level details ------------------------------
def test_request_body_validation_details(client: TestClient) -> None:
    resp = client.post("/api/projects", json=_payload(name=""))  # min_length=1
    assert resp.status_code == 422
    error = _assert_envelope(resp.json())
    assert error["code"] == "validation_error"
    assert isinstance(error["details"], list) and error["details"]
    assert any(d.get("field") == "name" for d in error["details"])


def test_patch_validation_details(client: TestClient) -> None:
    created = client.post("/api/projects", json=_payload()).json()
    resp = client.patch(
        f"/api/projects/{created['id']}", json={"name": ""}
    )
    assert resp.status_code == 422
    error = _assert_envelope(resp.json())
    assert error["code"] == "validation_error"
    assert any(d.get("field") == "name" for d in error["details"])


# -- unexpected server faults are caught, envelope'd, and do not leak ------
def test_internal_error_is_enveloped(tmp_path: Path) -> None:
    class ExplodingRepository(ProjectRepository):
        def list(self, owner_id: str):  # type: ignore[override]
            raise RuntimeError("disk on fire: /secret/path leaked?")

    users = UserRepository(tmp_path / "users.json")
    app = create_app(user_repository=users)
    app.dependency_overrides[get_repository] = lambda: ExplodingRepository(
        tmp_path / "projects.json"
    )
    c = TestClient(app, raise_server_exceptions=False)
    authenticate(c)

    resp = c.get("/api/projects")
    assert resp.status_code == 500
    error = _assert_envelope(resp.json())
    assert error["code"] == "internal_error"
    # The internal exception text must never reach the client.
    assert "disk on fire" not in resp.text
    assert "secret" not in resp.text
    assert resp.headers["X-Request-ID"] == error["request_id"]
