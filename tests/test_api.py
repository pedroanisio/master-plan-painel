"""End-to-end tests for the Project CRUDL API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from master_plan.api.main import create_app
from master_plan.api.repository import ProjectRepository
from master_plan.api.user_repository import UserRepository

from tests.auth_helpers import authenticate


def _build_client(tmp_path: Path) -> TestClient:
    projects = ProjectRepository(tmp_path / "projects.json")
    users = UserRepository(tmp_path / "users.json")
    return TestClient(create_app(projects, user_repository=users))


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    c = _build_client(tmp_path)
    authenticate(c)  # every resource route requires a bearer token
    return c


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


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_is_empty_initially(client: TestClient) -> None:
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_returns_201_with_id(client: TestClient) -> None:
    resp = client.post("/api/projects", json=_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["name"] == "alpha"
    assert body["primary_language"] == "python"  # defaulted server-side


def test_create_duplicate_name_conflicts(client: TestClient) -> None:
    client.post("/api/projects", json=_payload())
    resp = client.post("/api/projects", json=_payload(name="Alpha"))  # case-insensitive
    assert resp.status_code == 409


def test_create_duplicate_color_id_conflicts(client: TestClient) -> None:
    client.post("/api/projects", json=_payload(name="alpha", color_id=7))
    resp = client.post("/api/projects", json=_payload(name="beta", color_id=7))
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "duplicate_color"
    assert "color_id" in error["message"]


def test_distinct_colors_coexist(client: TestClient) -> None:
    assert client.post("/api/projects", json=_payload(name="alpha", color_id=7)).status_code == 201
    assert client.post("/api/projects", json=_payload(name="beta", color_id=8)).status_code == 201


def test_create_rejects_out_of_range_color(client: TestClient) -> None:
    assert client.post("/api/projects", json=_payload(color_id=0)).status_code == 422
    assert client.post("/api/projects", json=_payload(color_id=1024)).status_code == 422


def test_patch_color_conflict_returns_409(client: TestClient) -> None:
    client.post("/api/projects", json=_payload(name="alpha", color_id=7))
    other = client.post("/api/projects", json=_payload(name="beta", color_id=8)).json()
    resp = client.patch(f"/api/projects/{other['id']}", json={"color_id": 7})
    assert resp.status_code == 409


def test_create_rejects_invalid_body(client: TestClient) -> None:
    resp = client.post("/api/projects", json=_payload(languages=[]))
    assert resp.status_code == 422


def test_read_roundtrip(client: TestClient) -> None:
    created = client.post("/api/projects", json=_payload()).json()
    resp = client.get(f"/api/projects/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_read_missing_is_404(client: TestClient) -> None:
    assert client.get("/api/projects/does-not-exist").status_code == 404


def test_put_replaces(client: TestClient) -> None:
    created = client.post("/api/projects", json=_payload()).json()
    resp = client.put(
        f"/api/projects/{created['id']}",
        json=_payload(name="alpha", purpose="Updated purpose.", tags=["core"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["purpose"] == "Updated purpose."
    assert body["tags"] == ["core"]


def test_put_missing_is_404(client: TestClient) -> None:
    assert client.put("/api/projects/nope", json=_payload()).status_code == 404


def test_patch_partial_update(client: TestClient) -> None:
    created = client.post("/api/projects", json=_payload()).json()
    resp = client.patch(
        f"/api/projects/{created['id']}",
        json={"sub_domain": "cataloguing"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sub_domain"] == "cataloguing"
    assert body["name"] == "alpha"  # untouched


def test_patch_enforcing_invariant_returns_422(client: TestClient) -> None:
    created = client.post("/api/projects", json=_payload()).json()
    # primary_language must be within languages
    resp = client.patch(
        f"/api/projects/{created['id']}",
        json={"primary_language": "rust"},
    )
    assert resp.status_code == 422


def test_delete_then_gone(client: TestClient) -> None:
    created = client.post("/api/projects", json=_payload()).json()
    assert client.delete(f"/api/projects/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{created['id']}").status_code == 404


def test_delete_missing_is_404(client: TestClient) -> None:
    assert client.delete("/api/projects/nope").status_code == 404


def test_requires_authentication(tmp_path: Path) -> None:
    # No Authorization header → every resource route is 401.
    anon = _build_client(tmp_path)
    assert anon.get("/api/projects").status_code == 401
    assert anon.post("/api/projects", json=_payload()).status_code == 401
    assert anon.get("/api/projects/anything").status_code == 401


def test_projects_are_isolated_per_user(tmp_path: Path) -> None:
    # Two users share one backend; neither sees the other's projects.
    from tests.auth_helpers import auth_header, register

    c = _build_client(tmp_path)
    alice = register(c, username="alice")["token"]["access_token"]
    bob = register(c, username="bob")["token"]["access_token"]

    created = c.post(
        "/api/projects", json=_payload(name="alice-proj"), headers=auth_header(alice)
    ).json()

    # Bob's list is empty and he cannot read Alice's project by id.
    assert c.get("/api/projects", headers=auth_header(bob)).json() == []
    assert c.get(
        f"/api/projects/{created['id']}", headers=auth_header(bob)
    ).status_code == 404
    # Bob may reuse the same name and color id (uniqueness is per-owner).
    assert c.post(
        "/api/projects", json=_payload(name="alice-proj"), headers=auth_header(bob)
    ).status_code == 201


def test_persistence_across_repository_instances(tmp_path: Path) -> None:
    from tests.auth_helpers import auth_header

    db = tmp_path / "projects.json"
    udb = tmp_path / "users.json"
    first = TestClient(create_app(ProjectRepository(db), user_repository=UserRepository(udb)))
    token = authenticate(first)
    created = first.post("/api/projects", json=_payload()).json()

    # A fresh app reading the same files sees the persisted record for its owner.
    second = TestClient(create_app(ProjectRepository(db), user_repository=UserRepository(udb)))
    resp = second.get(f"/api/projects/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "alpha"


def test_legacy_records_without_color_or_owner_are_migrated(tmp_path: Path) -> None:
    import json

    # Two legacy records written before color_id / owner_id existed.
    db = tmp_path / "projects.json"
    db.write_text(
        json.dumps([
            {"id": "a", "name": "one", "domain": "d", "purpose": "p", "languages": ["python"]},
            {"id": "b", "name": "two", "domain": "d", "purpose": "p", "languages": ["go"]},
        ])
    )
    # Loading must not crash; it back-fills color_id and owner_id and persists.
    TestClient(create_app(ProjectRepository(db), user_repository=UserRepository(tmp_path / "u.json")))
    persisted = json.loads(db.read_text())
    assert sorted(r["color_id"] for r in persisted) == [1, 2]  # smallest free, unique
    assert all(r["owner_id"] == "" for r in persisted)  # orphaned, owned by nobody

    # An authenticated user sees none of the orphaned legacy records.
    c = _build_client(tmp_path)
    authenticate(c)
    assert c.get("/api/projects").json() == []
