"""End-to-end tests for the work-log API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from master_plan.api.main import create_app
from master_plan.api.repository import ProjectRepository
from master_plan.api.user_repository import UserRepository
from master_plan.api.work_repository import WorkLogRepository

from tests.auth_helpers import authenticate


def _build_client(tmp_path: Path) -> TestClient:
    projects = ProjectRepository(tmp_path / "projects.json")
    work = WorkLogRepository(tmp_path / "work.json")
    users = UserRepository(tmp_path / "users.json")
    return TestClient(create_app(projects, work, users))


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    c = _build_client(tmp_path)
    authenticate(c)  # every work-log route requires a bearer token
    return c


def _entry(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "project": "alpha",
        "performed_at": "2026-01-01T09:00:00+00:00",
        "minutes": 60,
        "kind": "feature",
    }
    body.update(overrides)
    return body


def test_list_empty(client: TestClient) -> None:
    resp = client.get("/api/work-entries")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_returns_201_with_id(client: TestClient) -> None:
    resp = client.post("/api/work-entries", json=_entry())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["project"] == "alpha"
    assert body["minutes"] == 60


def test_create_rejects_non_positive_minutes(client: TestClient) -> None:
    assert client.post("/api/work-entries", json=_entry(minutes=0)).status_code == 422


def test_read_roundtrip(client: TestClient) -> None:
    created = client.post("/api/work-entries", json=_entry()).json()
    resp = client.get(f"/api/work-entries/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_read_missing_is_404(client: TestClient) -> None:
    assert client.get("/api/work-entries/nope").status_code == 404


def test_list_is_sorted_newest_first(client: TestClient) -> None:
    client.post("/api/work-entries", json=_entry(performed_at="2026-01-01T09:00:00+00:00"))
    client.post("/api/work-entries", json=_entry(performed_at="2026-01-03T09:00:00+00:00"))
    client.post("/api/work-entries", json=_entry(performed_at="2026-01-02T09:00:00+00:00"))
    dates = [e["performed_at"] for e in client.get("/api/work-entries").json()]
    assert dates == sorted(dates, reverse=True)


def test_list_filter_by_project(client: TestClient) -> None:
    client.post("/api/work-entries", json=_entry(project="alpha"))
    client.post("/api/work-entries", json=_entry(project="beta"))
    resp = client.get("/api/work-entries", params={"project": "beta"})
    assert [e["project"] for e in resp.json()] == ["beta"]


def test_put_replaces(client: TestClient) -> None:
    created = client.post("/api/work-entries", json=_entry()).json()
    resp = client.put(
        f"/api/work-entries/{created['id']}",
        json=_entry(minutes=120, kind="bugfix", summary="fixed it"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["minutes"] == 120
    assert body["kind"] == "bugfix"


def test_patch_partial_update(client: TestClient) -> None:
    created = client.post("/api/work-entries", json=_entry()).json()
    resp = client.patch(
        f"/api/work-entries/{created['id']}", json={"minutes": 45}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["minutes"] == 45
    assert body["project"] == "alpha"  # untouched


def test_patch_invalid_returns_422(client: TestClient) -> None:
    created = client.post("/api/work-entries", json=_entry()).json()
    resp = client.patch(
        f"/api/work-entries/{created['id']}", json={"minutes": -5}
    )
    assert resp.status_code == 422


def test_delete_then_gone(client: TestClient) -> None:
    created = client.post("/api/work-entries", json=_entry()).json()
    assert client.delete(f"/api/work-entries/{created['id']}").status_code == 204
    assert client.get(f"/api/work-entries/{created['id']}").status_code == 404


def test_delete_missing_is_404(client: TestClient) -> None:
    assert client.delete("/api/work-entries/nope").status_code == 404


def test_summary_aggregates(client: TestClient) -> None:
    client.post("/api/work-entries", json=_entry(project="alpha", minutes=60))
    client.post("/api/work-entries", json=_entry(project="alpha", minutes=30))
    client.post("/api/work-entries", json=_entry(project="beta", minutes=120))
    summary = client.get("/api/work-summary").json()
    assert summary["total_minutes"] == 210
    assert summary["by_project"] == {"alpha": 90, "beta": 120}
    assert summary["busiest_project"] == "beta"


def test_summary_by_day(client: TestClient) -> None:
    client.post("/api/work-entries", json=_entry(performed_at="2026-01-01T09:00:00Z", minutes=60))
    client.post("/api/work-entries", json=_entry(performed_at="2026-01-01T15:00:00Z", minutes=30))
    client.post("/api/work-entries", json=_entry(performed_at="2026-01-02T10:00:00Z", minutes=45))
    summary = client.get("/api/work-summary").json()
    assert summary["by_day"] == {"2026-01-01": 90, "2026-01-02": 45}


def test_report_all_time_endpoint(client: TestClient) -> None:
    client.post("/api/work-entries", json=_entry(project="alpha", performed_at="2026-01-01T09:00:00Z", minutes=60))
    client.post("/api/work-entries", json=_entry(project="beta", performed_at="2026-01-02T09:00:00Z", minutes=30))
    report = client.get("/api/work-report").json()  # no days → all-time
    assert report["days"] is None
    assert report["from_date"] is None
    assert report["total_minutes"] == 90
    assert report["entry_count"] == 2
    assert report["active_days"] == 2
    assert report["avg_minutes_per_active_day"] == 45.0
    assert report["by_project"] == {"alpha": 60, "beta": 30}
    assert report["busiest_project"] == "alpha"


def test_report_rejects_non_positive_days(client: TestClient) -> None:
    assert client.get("/api/work-report", params={"days": 0}).status_code == 422


def test_report_window_and_project_scope() -> None:
    # Repository-level unit test with an injected 'now' → deterministic window.
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile

    from master_plan.api.work_repository import WorkLogRepository
    from master_plan.models.work_log import WorkEntry

    tmp = Path(tempfile.mkdtemp()) / "w.json"
    repo = WorkLogRepository(tmp)
    now = datetime(2026, 3, 31, 12, 0, tzinfo=timezone.utc)

    def at(day: int) -> datetime:
        return datetime(2026, 3, day, 9, 0, tzinfo=timezone.utc)

    repo.create(WorkEntry(project="alpha", performed_at=at(30), minutes=60), "u1")  # within 7d
    repo.create(WorkEntry(project="beta", performed_at=at(28), minutes=30), "u1")   # within 7d
    repo.create(WorkEntry(project="alpha", performed_at=at(1), minutes=120), "u1")  # outside 7d
    repo.create(WorkEntry(project="alpha", performed_at=at(29), minutes=15), "u2")  # other user

    last7 = repo.report("u1", now=now, days=7)
    assert last7.total_minutes == 90  # only the two recent u1 entries
    assert last7.from_date == "2026-03-25"
    assert last7.to_date == "2026-03-31"

    all_time = repo.report("u1", now=now)
    assert all_time.total_minutes == 210
    assert all_time.by_project == {"alpha": 180, "beta": 30}

    scoped = repo.report("u1", now=now, project="alpha")
    assert scoped.total_minutes == 180
    assert scoped.by_project == {"alpha": 180}
    assert scoped.project == "alpha"


def test_requires_authentication(tmp_path: Path) -> None:
    anon = _build_client(tmp_path)
    assert anon.get("/api/work-entries").status_code == 401
    assert anon.post("/api/work-entries", json=_entry()).status_code == 401
    assert anon.get("/api/work-summary").status_code == 401


def test_entries_are_isolated_per_user(tmp_path: Path) -> None:
    from tests.auth_helpers import auth_header, register

    c = _build_client(tmp_path)
    alice = register(c, username="alice")["token"]["access_token"]
    bob = register(c, username="bob")["token"]["access_token"]

    c.post("/api/work-entries", json=_entry(minutes=60), headers=auth_header(alice))

    # Bob sees neither the entry nor its minutes in his summary.
    assert c.get("/api/work-entries", headers=auth_header(bob)).json() == []
    bob_summary = c.get("/api/work-summary", headers=auth_header(bob)).json()
    assert bob_summary["total_minutes"] == 0
    alice_summary = c.get("/api/work-summary", headers=auth_header(alice)).json()
    assert alice_summary["total_minutes"] == 60


def test_persistence_across_repository_instances(tmp_path: Path) -> None:
    from tests.auth_helpers import auth_header

    db = tmp_path / "work.json"
    udb = tmp_path / "users.json"
    first = TestClient(
        create_app(work_repository=WorkLogRepository(db), user_repository=UserRepository(udb))
    )
    token = authenticate(first)
    created = first.post("/api/work-entries", json=_entry()).json()

    second = TestClient(
        create_app(work_repository=WorkLogRepository(db), user_repository=UserRepository(udb))
    )
    resp = second.get(f"/api/work-entries/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["project"] == "alpha"
