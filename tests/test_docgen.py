"""Tests for the automatic tooling/API documentation generator."""

from __future__ import annotations

from pathlib import Path

from master_plan import docgen


def test_generate_has_all_sections() -> None:
    md = docgen.generate()
    assert md.startswith("---\n")  # disclaimer frontmatter
    assert "# Tooling & API reference" in md
    assert "## Run it" in md
    assert "## HTTP API" in md
    assert "## Configuration" in md
    assert "## CLI scripts" in md


def test_api_routes_are_documented_with_auth() -> None:
    md = docgen.generate()
    # A public route and a protected route, correctly classified.
    assert "`GET` | `/api/health`" in md.replace("| ", "| ").replace("  ", " ") or "/api/health" in md
    lines = md.splitlines()
    health = next(line for line in lines if "/api/health`" in line)
    projects = next(line for line in lines if "`/api/projects`" in line and "`GET`" in line)
    assert "public" in health
    assert "🔒" in projects  # requires auth


def test_env_vars_discovered_with_defaults() -> None:
    md = docgen.generate()
    assert "`MASTER_PLAN_DB`" in md
    assert "`./data/projects.json`" in md
    assert "`MASTER_PLAN_SECRET`" in md  # the one without a default
    assert "*(unset)*" in md


def test_scripts_documented() -> None:
    md = docgen.generate()
    assert "scripts/seed.py`" in md


def test_output_is_reproducible() -> None:
    # No volatile timestamp → two runs are byte-identical (so --check is meaningful).
    assert docgen.generate() == docgen.generate()


def test_discover_routes_directly() -> None:
    from master_plan.api.main import create_app

    routes = docgen.discover_routes(create_app())
    assert len(routes) >= 15
    health = [r for r in routes if r.path == "/api/health"]
    assert health and health[0].auth is None
    proj = [r for r in routes if r.path == "/api/projects" and r.method == "POST"]
    assert proj and proj[0].auth is not None


def test_main_stdout(capsys) -> None:
    rc = docgen.main(["--stdout"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Tooling & API reference" in out


def test_main_write_and_check(tmp_path: Path) -> None:
    out = tmp_path / "TOOLING.md"
    assert docgen.main(["--output", str(out)]) == 0
    assert out.exists()

    # Freshly written → check passes.
    assert docgen.main(["--output", str(out), "--check"]) == 0

    # Tamper → check fails.
    out.write_text(out.read_text() + "\nstale\n", encoding="utf-8")
    assert docgen.main(["--output", str(out), "--check"]) == 1
