"""Production-hardening behaviour: atomic persistence, fail-closed secret,
configurable CORS.

These guard the refinements that make the service safe to deploy:
* JSON stores rewrite atomically, so a crash mid-write cannot corrupt them.
* The API refuses to boot in production without a stable signing secret.
* CORS origins are resolved from the environment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import io

from master_plan.api import spaces
from master_plan.api._io import (
    atomic_write_text,
    clear_post_write_hooks,
    register_post_write_hook,
)
from master_plan.api.main import _cors_origins, create_app
from master_plan.api.repository import ProjectRepository
from master_plan.api.security import is_production, verify_signing_secret
from master_plan.api.spaces import SpacesMirror


class TestAtomicWrite:
    def test_writes_content(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "data.json"
        atomic_write_text(target, '{"a": 1}')
        assert target.read_text(encoding="utf-8") == '{"a": 1}'

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "f.json"
        atomic_write_text(target, "x")
        assert target.exists()

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "f.json"
        atomic_write_text(target, "old")
        atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_leaves_no_temp_files(self, tmp_path: Path) -> None:
        target = tmp_path / "f.json"
        atomic_write_text(target, "hello")
        # Only the target remains — no stray ".f.json.*.tmp" siblings.
        assert [p.name for p in tmp_path.iterdir()] == ["f.json"]

    def test_repository_persist_is_clean(self, tmp_path: Path) -> None:
        # A repository write goes through atomic_write_text; the store is valid
        # JSON and no temp file is left behind.
        repo = ProjectRepository(tmp_path / "projects.json")
        from master_plan.models.project import Project

        repo.create(
            Project(name="demo", color_id=1, domain="d", purpose="p", languages=["python"]),
            owner_id="o1",
        )
        data = json.loads((tmp_path / "projects.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert not list(tmp_path.glob(".projects.json.*"))


class TestSigningSecretGate:
    def test_production_without_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASTER_PLAN_ENV", "production")
        monkeypatch.delenv("MASTER_PLAN_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="MASTER_PLAN_SECRET"):
            verify_signing_secret()

    def test_production_with_secret_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASTER_PLAN_ENV", "production")
        monkeypatch.setenv("MASTER_PLAN_SECRET", "s3cret")
        verify_signing_secret()  # does not raise

    def test_development_without_secret_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MASTER_PLAN_ENV", raising=False)
        monkeypatch.delenv("MASTER_PLAN_SECRET", raising=False)
        verify_signing_secret()  # dev keeps the ephemeral fallback

    def test_create_app_blocks_in_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASTER_PLAN_ENV", "prod")
        monkeypatch.delenv("MASTER_PLAN_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            create_app()

    @pytest.mark.parametrize("value,expected", [("production", True), ("prod", True), ("dev", False), ("", False)])
    def test_is_production(self, monkeypatch: pytest.MonkeyPatch, value: str, expected: bool) -> None:
        monkeypatch.setenv("MASTER_PLAN_ENV", value)
        assert is_production() is expected


class TestCorsOrigins:
    def test_unset_defaults_to_dev_origins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MASTER_PLAN_CORS_ORIGINS", raising=False)
        assert _cors_origins() == ["http://localhost:5173", "http://127.0.0.1:5173"]

    def test_empty_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASTER_PLAN_CORS_ORIGINS", "")
        assert _cors_origins() == []

    def test_comma_separated_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MASTER_PLAN_CORS_ORIGINS", "https://a.example, https://b.example ")
        assert _cors_origins() == ["https://a.example", "https://b.example"]


class _NotFound(Exception):
    """Mimics a boto3 ClientError for a missing key."""

    response = {"Error": {"Code": "NoSuchKey"}}


class _FakeS3:
    """In-memory stand-in for a boto3 S3/Spaces client."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.puts: list[str] = []

    def get_object(self, Bucket: str, Key: str) -> dict:  # noqa: N803 (boto3 kwargs)
        if Key not in self.store:
            raise _NotFound()
        return {"Body": io.BytesIO(self.store[Key])}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str = "") -> None:  # noqa: N803
        self.store[Key] = Body
        self.puts.append(Key)


class TestSpacesMirror:
    def test_disabled_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "MASTER_PLAN_SPACES_BUCKET",
            "MASTER_PLAN_SPACES_ENDPOINT",
            "MASTER_PLAN_SPACES_KEY",
            "MASTER_PLAN_SPACES_SECRET",
        ):
            monkeypatch.delenv(key, raising=False)
        assert spaces.is_configured() is False
        assert spaces.configure_from_env() is None

    def test_sync_down_restores_existing_object(self, tmp_path: Path) -> None:
        client = _FakeS3()
        client.store["projects.json"] = b'[{"x": 1}]'
        mirror = SpacesMirror(client, bucket="b")
        local = tmp_path / "projects.json"
        mirror.add(local)
        mirror.sync_down()
        assert local.read_bytes() == b'[{"x": 1}]'

    def test_sync_down_missing_object_is_noop(self, tmp_path: Path) -> None:
        mirror = SpacesMirror(_FakeS3(), bucket="b")
        local = tmp_path / "projects.json"
        mirror.add(local)
        mirror.sync_down()  # object absent → no error
        assert not local.exists()

    def test_on_write_uploads_registered_path(self, tmp_path: Path) -> None:
        client = _FakeS3()
        mirror = SpacesMirror(client, bucket="b", prefix="mp/")
        local = tmp_path / "users.json"
        local.write_bytes(b"[]")
        mirror.add(local)
        mirror.on_write(local)
        assert client.store["mp/users.json"] == b"[]"

    def test_on_write_ignores_unregistered_path(self, tmp_path: Path) -> None:
        client = _FakeS3()
        mirror = SpacesMirror(client, bucket="b")
        mirror.on_write(tmp_path / "not-registered.json")
        assert client.puts == []

    def test_hook_mirrors_repository_writes(self, tmp_path: Path) -> None:
        # End-to-end: a repository write triggers the post-write hook → upload.
        from master_plan.models.project import Project

        client = _FakeS3()
        mirror = SpacesMirror(client, bucket="b")
        local = tmp_path / "projects.json"
        mirror.add(local)
        clear_post_write_hooks()
        register_post_write_hook(mirror.on_write)
        try:
            repo = ProjectRepository(local)
            repo.create(
                Project(name="p", color_id=1, domain="d", purpose="x", languages=["python"]),
                owner_id="o1",
            )
            assert "projects.json" in client.store
            assert b'"name": "p"' in client.store["projects.json"]
        finally:
            clear_post_write_hooks()
