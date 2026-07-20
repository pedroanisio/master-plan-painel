"""CLI to register (and list) work-log entries via the HTTP API using an API key.

This talks to the running API over HTTP and authenticates with an **API key**
(``X-API-Key: mpk_…``) — the same credential the app issues under
*Settings → API keys*. Going through the API (rather than writing the JSON
stores directly) means the owner is resolved from the key, every write is
validated and serialised by the server, and a read-only key is correctly
rejected on ``add``.

Provide the key and (optionally) the base URL via flags or environment:

* ``--api-key`` / ``MASTER_PLAN_API_KEY`` — a ``mpk_…`` key with the ``write`` scope.
* ``--url`` / ``MASTER_PLAN_API_URL`` — API base URL (default ``http://localhost:8000``).

Usage::

    export MASTER_PLAN_API_KEY=mpk_xxx
    python -m master_plan.worklog_cli add --project alpha --minutes 45 \\
        --kind feature --summary "wire up the report endpoint" --tags api,reports

    python -m master_plan.worklog_cli add -p alpha -m 30 --when 2026-07-19T09:00:00Z
    python -m master_plan.worklog_cli list --project alpha
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from master_plan.models.work_log import Complexity, WorkKind

__all__ = ["main"]

_DEFAULT_URL = "http://localhost:8000"


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


def _base_url(arg: str | None) -> str:
    return (arg or os.environ.get("MASTER_PLAN_API_URL", _DEFAULT_URL)).rstrip("/")


def _api_key(arg: str | None) -> str:
    key = arg or os.environ.get("MASTER_PLAN_API_KEY")
    if not key:
        raise SystemExit(
            _fail("no API key — pass --api-key or set MASTER_PLAN_API_KEY")
        )
    return key


# -- HTTP seam (monkeypatched in tests) ------------------------------------- #
def _send(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, object | None]:
    """Send one request; return (status, parsed-json-or-None). Raises on network."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 — fixed scheme/host by config
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = None
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise SystemExit(
            _fail(f"cannot reach {url}: {exc.reason} — is the API running?")
        ) from exc


def _call(
    method: str, base: str, path: str, key: str, body: object | None = None
) -> tuple[int, object | None]:
    headers = {"X-API-Key": key, "Accept": "application/json"}
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return _send(method, f"{base}{path}", headers, data)


def _api_error(status: int, payload: object) -> int:
    """Render the server error envelope and return a non-zero exit code."""
    message = f"HTTP {status}"
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        err = payload["error"]
        code = err.get("code")
        message = err.get("message") or message
        if code:
            message = f"{message} [{code}]"
        details = err.get("details")
        if isinstance(details, list) and details:
            joined = "; ".join(
                f"{d.get('field')}: {d.get('message')}" for d in details
            )
            message = f"{message} ({joined})"
    return _fail(message)


def _parse_when(value: str | None) -> str:
    """ISO timestamp (tz-aware UTC). Default now. Server re-validates."""
    if not value:
        return datetime.now(timezone.utc).isoformat()
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(_fail(f"invalid --when {value!r}: {exc}")) from exc
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.isoformat()


def _split_tags(value: str | None) -> list[str]:
    return [t.strip() for t in (value or "").split(",") if t.strip()]


# -- commands --------------------------------------------------------------- #
def _cmd_add(args: argparse.Namespace) -> int:
    base, key = _base_url(args.url), _api_key(args.api_key)
    body = {
        "project": args.project,
        "performed_at": _parse_when(args.when),
        "minutes": args.minutes,
        "kind": args.kind,
        "summary": args.summary or None,
        "complexity": args.complexity or None,
        "tags": _split_tags(args.tags),
    }
    status, payload = _call("POST", base, "/api/work-entries", key, body)
    if status == 201 and isinstance(payload, dict):
        print(
            f"logged {payload['minutes']}m of {payload['kind']} on "
            f"{payload['project']} @ {payload['performed_at']}  "
            f"(id {str(payload['id'])[:8]})"
        )
        return 0
    return _api_error(status, payload)


def _cmd_list(args: argparse.Namespace) -> int:
    base, key = _base_url(args.url), _api_key(args.api_key)
    path = "/api/work-entries"
    if args.project:
        path += f"?project={urllib.parse.quote(args.project)}"
    status, payload = _call("GET", base, path, key)
    if status != 200 or not isinstance(payload, list):
        return _api_error(status, payload)
    rows = payload[: args.limit]
    if not rows:
        print("(no entries)")
        return 0
    for e in rows:
        print(
            f"{e['performed_at']}  {e['minutes']:>4}m  {e['kind']:<11} "
            f"{e['project']:<20} {e.get('summary') or ''}"
        )
    return 0


def _cmd_projects_list(args: argparse.Namespace) -> int:
    base, key = _base_url(args.url), _api_key(args.api_key)
    status, payload = _call("GET", base, "/api/projects", key)
    if status != 200 or not isinstance(payload, list):
        return _api_error(status, payload)
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    if not payload:
        print("(no projects)")
        return 0
    rows = sorted(payload, key=lambda p: str(p.get("name", "")).lower())
    print(f"{'COLOR':>5}  {'NAME':<28} {'DOMAIN':<24} {'LANGUAGES':<26} PKGS")
    for p in rows:
        domain = str(p.get("domain", ""))
        if p.get("sub_domain"):
            domain = f"{domain}/{p['sub_domain']}"
        langs = ",".join(p.get("languages") or [])
        print(
            f"{p.get('color_id', ''):>5}  {str(p.get('name', ''))[:28]:<28} "
            f"{domain[:24]:<24} {langs[:26]:<26} {len(p.get('packages') or [])}"
        )
    print(f"\n{len(rows)} project{'' if len(rows) == 1 else 's'}")
    return 0


def _add_conn_flags(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--api-key", help="API key (mpk_…); or set MASTER_PLAN_API_KEY.")
    sub.add_argument("--url", help=f"API base URL (default: {_DEFAULT_URL}).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="master-plan-worklog",
        description="Register and list work-log entries via the API (API-key auth).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Register a work-log entry.")
    add.add_argument("-p", "--project", required=True, help="Project name to log against.")
    add.add_argument("-m", "--minutes", type=int, required=True, help="Minutes worked (> 0).")
    add.add_argument(
        "-k", "--kind", default="feature", choices=[k.value for k in WorkKind],
        help="Kind of work (default: feature).",
    )
    add.add_argument("--when", help="ISO timestamp (default: now, sent as UTC).")
    add.add_argument("-s", "--summary", help="Short summary of the work.")
    add.add_argument(
        "--complexity", choices=[c.value for c in Complexity], help="Optional XS–XL size.",
    )
    add.add_argument("--tags", help="Comma-separated tags.")
    _add_conn_flags(add)
    add.set_defaults(func=_cmd_add)

    lst = sub.add_parser("list", help="List work-log entries (newest first).")
    lst.add_argument("-p", "--project", help="Filter to one project.")
    lst.add_argument("-n", "--limit", type=int, default=20, help="Max rows (default: 20).")
    _add_conn_flags(lst)
    lst.set_defaults(func=_cmd_list)

    # Project catalogue commands: `... projects list`
    proj = sub.add_parser("projects", help="Project catalogue commands.")
    proj_sub = proj.add_subparsers(dest="projects_command", required=True)
    proj_list = proj_sub.add_parser("list", help="List all projects you own.")
    proj_list.add_argument("--json", action="store_true", help="Emit raw JSON records.")
    _add_conn_flags(proj_list)
    proj_list.set_defaults(func=_cmd_projects_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
