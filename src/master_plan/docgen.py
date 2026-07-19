"""Automatic documentation generator for the master-plan tooling (CLI).

Introspects the codebase and renders a single Markdown reference so the docs
cannot drift from the code:

* **HTTP API** — every route is read from the live FastAPI app (method, path,
  whether it requires authentication, and its summary).
* **Configuration** — every ``MASTER_PLAN_*`` environment variable the API
  actually reads (name + default) is discovered by scanning ``api/*.py``.
* **CLI scripts** — each script under ``scripts/`` is described from its module
  docstring (parsed with ``ast``; the script is never executed).

Run it::

    python -m master_plan.docgen                 # write docs/TOOLING.md
    python -m master_plan.docgen --stdout         # print instead
    python -m master_plan.docgen --check          # CI drift guard (non-zero if stale)

Because the output is derived from source it is reproducible: no volatile
timestamp is emitted, so ``--check`` is a meaningful "docs are up to date" gate.
Requires the ``api`` extra (FastAPI) to introspect the app.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["generate", "main"]

# Dependency callables (in api/main.py) that gate a route behind authentication.
# `get_principal` is the shared ancestor of them all, so its presence in a
# route's dependency tree is the definitive "requires auth" signal.
_AUTH_GATES = (
    "require_write",
    "require_session_user",
    "require_user",
    "require_admin",
    "require_role",
)
_AUTH_ROOT = "get_principal"

_ENV_RE = re.compile(
    r"""os\.(?:environ\.get|getenv)\(\s*['"](MASTER_PLAN_[A-Z0-9_]+)['"]"""
    r"""\s*(?:,\s*(['"][^'"]*['"]|[^),]+))?""",
)


def repo_root() -> Path:
    """Return the repository root (this file is src/master_plan/docgen.py)."""
    return Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Introspection
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RouteDoc:
    method: str
    path: str
    summary: str
    auth: str | None  # None = public; else the gate name / "authenticated"


@dataclass
class EnvVar:
    name: str
    default: str | None
    sources: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ScriptDoc:
    name: str
    summary: str
    usage: str


def _first_doc_line(func: object) -> str:
    doc = (getattr(func, "__doc__", None) or "").strip()
    return doc.split("\n", 1)[0].strip() if doc else ""


def _auth_gate(route) -> str | None:
    """Return the auth gate protecting ``route``, or ``None`` if it is public."""
    found: set[str] = set()

    def walk(dependant) -> None:
        for sub in dependant.dependencies:
            name = getattr(sub.call, "__name__", None)
            if name:
                found.add(name)
            walk(sub)

    walk(route.dependant)
    for gate in _AUTH_GATES:
        if gate in found:
            return gate
    if _AUTH_ROOT in found:
        return "authenticated"
    # Routes that authenticate by reading the Authorization header directly
    # (rather than via a dependency) still require a token — detect them so the
    # doc doesn't mislabel them as public (e.g. GET /api/auth/me).
    for header in route.dependant.header_params:
        alias = getattr(header.field_info, "alias", None) or header.name
        if alias.lower() == "authorization":
            return "bearer"
    return None


def discover_routes(app) -> list[RouteDoc]:
    """Read every API route from a built FastAPI app."""
    from fastapi.routing import APIRoute

    out: list[RouteDoc] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        summary = route.summary or _first_doc_line(route.endpoint)
        gate = _auth_gate(route)
        for method in sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"}):
            out.append(RouteDoc(method, route.path, summary, gate))
    out.sort(key=lambda d: (d.path, d.method))
    return out


def _clean_default(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if (raw[0], raw[-1]) in {('"', '"'), ("'", "'")}:
        return raw[1:-1]
    return raw  # a non-literal default (expression) — show verbatim


def discover_env_vars(api_dir: Path) -> list[EnvVar]:
    """Find every MASTER_PLAN_* env var the API reads, with its default."""
    found: dict[str, EnvVar] = {}
    for path in sorted(api_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _ENV_RE.finditer(text):
            name = match.group(1)
            default = _clean_default(match.group(2))
            if name not in found:
                found[name] = EnvVar(name, default, {path.name})
            else:
                found[name].sources.add(path.name)
                if found[name].default is None and default is not None:
                    found[name].default = default
    return sorted(found.values(), key=lambda e: e.name)


def _extract_usage(docstring: str) -> str:
    """Pull the indented block under a 'Usage:' line out of a module docstring."""
    lines = docstring.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("usage"):
            block = []
            for follow in lines[i + 1 :]:
                if follow.strip() == "" and not block:
                    continue
                if follow.strip() == "":
                    break
                block.append(follow.strip())
            return "\n".join(block).strip()
    return ""


def discover_scripts(scripts_dir: Path) -> list[ScriptDoc]:
    """Describe each scripts/*.py from its module docstring (never executed)."""
    out: list[ScriptDoc] = []
    if not scripts_dir.exists():
        return out
    for path in sorted(scripts_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
        summary = doc.split("\n\n", 1)[0].replace("\n", " ").strip()
        out.append(ScriptDoc(path.name, summary, _extract_usage(doc)))
    return out


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _auth_label(gate: str | None) -> str:
    if gate is None:
        return "public"
    return f"🔒 {gate.removeprefix('require_')}"


def render(
    routes: list[RouteDoc],
    env_vars: list[EnvVar],
    scripts: list[ScriptDoc],
    *,
    date: str | None = None,
) -> str:
    lines: list[str] = []

    # Mandatory disclaimer frontmatter (CLAUDE.md rule 5). No volatile date by
    # default so the output stays reproducible for `--check`.
    lines.append("---")
    lines.append("disclaimer:")
    lines.append("  notice: >-")
    lines.append("    No information within this document should be taken for granted.")
    lines.append("    Any statement or premise not backed by a real logical definition")
    lines.append("    or verifiable reference may be invalid, erroneous, or a hallucination.")
    lines.append('  generated_by: "master_plan.docgen"')
    if date:
        lines.append(f'  date: "{date}"')
    lines.append("---")
    lines.append("")
    lines.append("# Tooling & API reference")
    lines.append("")
    lines.append(
        "> **Generated file — do not edit by hand.** Produced from source by "
        "`python -m master_plan.docgen`. Re-run after changing routes, env vars, "
        "or scripts; CI can enforce freshness with `--check`."
    )
    lines.append("")

    # -- Commands ----------------------------------------------------------
    lines.append("## Run it")
    lines.append("")
    lines.append("| Command | What it does |")
    lines.append("|---|---|")
    lines.append(
        "| `pip install -e \".[api]\"` | Install the backend + tooling. |"
    )
    lines.append(
        "| `uvicorn master_plan.api.main:app --host 0.0.0.0 --port 8000` | "
        "Run the API. |"
    )
    lines.append(
        "| `python -m master_plan.docgen` | Regenerate this document. |"
    )
    lines.append(
        "| `docker compose up` | Run the full stack (API + frontend + nginx). |"
    )
    lines.append("")

    # -- HTTP API ----------------------------------------------------------
    lines.append(f"## HTTP API ({len(routes)} routes)")
    lines.append("")
    lines.append(
        "`🔒` = requires a bearer token (owner-scoped); `public` = no auth. "
        "The gate name is the FastAPI dependency enforcing it."
    )
    lines.append("")
    lines.append("| Method | Path | Access | Summary |")
    lines.append("|---|---|---|---|")
    for r in routes:
        lines.append(
            f"| `{r.method}` | `{_cell(r.path)}` | {_auth_label(r.auth)} "
            f"| {_cell(r.summary) or '—'} |"
        )
    lines.append("")

    # -- Configuration -----------------------------------------------------
    lines.append(f"## Configuration ({len(env_vars)} environment variables)")
    lines.append("")
    lines.append("Every `MASTER_PLAN_*` variable the API reads, discovered from source.")
    lines.append("")
    lines.append("| Variable | Default | Read in |")
    lines.append("|---|---|---|")
    for e in env_vars:
        default = f"`{e.default}`" if e.default is not None else "*(unset)*"
        srcs = ", ".join(f"`{s}`" for s in sorted(e.sources))
        lines.append(f"| `{e.name}` | {default} | {srcs} |")
    lines.append("")

    # -- CLI scripts -------------------------------------------------------
    lines.append(f"## CLI scripts ({len(scripts)})")
    lines.append("")
    if not scripts:
        lines.append("*(none)*")
        lines.append("")
    for s in scripts:
        lines.append(f"### `scripts/{s.name}`")
        lines.append("")
        if s.summary:
            lines.append(s.summary)
            lines.append("")
        if s.usage:
            lines.append("```")
            lines.append(s.usage)
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate(root: Path | None = None, *, date: str | None = None) -> str:
    """Build the full Markdown reference from the codebase at ``root``."""
    root = root or repo_root()
    from master_plan.api.main import create_app

    app = create_app()
    routes = discover_routes(app)
    env_vars = discover_env_vars(root / "src" / "master_plan" / "api")
    scripts = discover_scripts(root / "scripts")
    return render(routes, env_vars, scripts, date=date)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="master-plan-docgen",
        description="Generate the tooling & API reference from source.",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output path (default: docs/TOOLING.md).",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Print to stdout instead of writing a file.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Exit non-zero if the on-disk doc differs from freshly generated (CI guard).",
    )
    parser.add_argument(
        "--date", default=None,
        help="Optional YYYY-MM-DD stamp for the frontmatter (omit for reproducible output).",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    markdown = generate(root, date=args.date)

    if args.stdout:
        sys.stdout.write(markdown)
        return 0

    out = Path(args.output) if args.output else root / "docs" / "TOOLING.md"

    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != markdown:
            print(
                f"docs out of date: {out}\n"
                "  run `python -m master_plan.docgen` to regenerate.",
                file=sys.stderr,
            )
            return 1
        print(f"docs up to date: {out}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"wrote {out} ({markdown.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
