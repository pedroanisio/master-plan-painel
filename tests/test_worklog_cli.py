"""Tests for the work-log CLI (HTTP client, API-key auth).

The CLI's single HTTP seam (`worklog_cli._send`) is redirected to an in-process
FastAPI TestClient, so the tests exercise the real API + API-key auth path
without a live server or network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from master_plan import worklog_cli
from master_plan.api.main import create_app
from master_plan.api.api_key_repository import ApiKeyRepository
from master_plan.api.repository import ProjectRepository
from master_plan.api.user_repository import UserRepository
from master_plan.api.work_repository import WorkLogRepository

_BASE = "http://testserver"


@pytest.fixture
def api(tmp_path: Path, monkeypatch) -> dict:
    """Wire the CLI to an in-process app and return a write-scoped API key."""
    client = TestClient(
        create_app(
            ProjectRepository(tmp_path / "p.json"),
            WorkLogRepository(tmp_path / "w.json"),
            UserRepository(tmp_path / "u.json"),
            ApiKeyRepository(tmp_path / "k.json"),
        )
    )

    reg = {
        "username": "ada",
        "email": "ada@example.com",
        "password": "sup3rsecret",
        "password_confirm": "sup3rsecret",
    }
    token = client.post("/api/auth/register", json=reg).json()["token"]["access_token"]
    created = client.post(
        "/api/auth/api-keys",
        json={"name": "cli", "scopes": ["write"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    key = created.json()["token"]
    assert key.startswith("mpk_")

    # Redirect the CLI's HTTP calls to the TestClient.
    def fake_send(method, url, headers, body):
        path = url.split(_BASE, 1)[1] if url.startswith(_BASE) else url
        content = body if body is not None else None
        resp = client.request(method, path, headers=headers, content=content)
        try:
            payload = resp.json()
        except json.JSONDecodeError:
            payload = None
        return resp.status_code, payload

    monkeypatch.setattr(worklog_cli, "_send", fake_send)
    return {"client": client, "key": key}


def _base_args() -> list[str]:
    return ["--url", _BASE]


def test_add_via_api_key(api: dict, capsys) -> None:
    rc = worklog_cli.main([
        "add", "-p", "alpha", "-m", "45", "-k", "feature", "-s", "hi",
        "--tags", "api, reports", "--api-key", api["key"], *_base_args(),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "45m of feature on alpha" in out
    # It really persisted through the API:
    listed = api["client"].get(
        "/api/work-entries", headers={"X-API-Key": api["key"]}
    ).json()
    assert len(listed) == 1 and listed[0]["tags"] == ["api", "reports"]


def test_add_reads_key_from_env(api: dict, monkeypatch) -> None:
    monkeypatch.setenv("MASTER_PLAN_API_KEY", api["key"])
    monkeypatch.setenv("MASTER_PLAN_API_URL", _BASE)
    assert worklog_cli.main(["add", "-p", "beta", "-m", "30"]) == 0


def test_missing_api_key_errors(monkeypatch) -> None:
    monkeypatch.delenv("MASTER_PLAN_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        worklog_cli.main(["add", "-p", "a", "-m", "5", "--url", _BASE])
    assert exc.value.code == 2


def test_invalid_minutes_surfaces_api_error(api: dict, capsys) -> None:
    rc = worklog_cli.main([
        "add", "-p", "alpha", "-m", "0", "--api-key", api["key"], *_base_args(),
    ])
    assert rc != 0
    assert "error:" in capsys.readouterr().err  # server 422 envelope rendered


def test_read_only_key_is_rejected_on_add(api: dict, capsys) -> None:
    # Mint a read-only key and confirm the write is refused with a clear message.
    client = api["client"]
    token = client.post("/api/auth/login", json={
        "identifier": "ada", "password": "sup3rsecret",
    }).json()["token"]["access_token"]
    ro = client.post(
        "/api/auth/api-keys",
        json={"name": "ro", "scopes": ["read"]},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["token"]

    rc = worklog_cli.main(["add", "-p", "alpha", "-m", "10", "--api-key", ro, *_base_args()])
    assert rc != 0
    assert "read-only" in capsys.readouterr().err.lower()


def test_list_via_api_key(api: dict, capsys) -> None:
    worklog_cli.main(["add", "-p", "alpha", "-m", "30", "--api-key", api["key"], *_base_args()])
    capsys.readouterr()
    rc = worklog_cli.main(["list", "--api-key", api["key"], *_base_args()])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha" in out and "30m" in out
