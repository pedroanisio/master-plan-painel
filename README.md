---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-07-18"
---

# master-plan-painel

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](./DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Pydantic v2 models for cataloguing projects (codebases) along four axes:
**domain / sub-domain**, **purpose**, **languages**, and **packages**.

## Model

| Model | Purpose |
|---|---|
| `Project` | A tracked codebase: name, domain, sub-domain, purpose, languages, packages, and light metadata. |
| `Package` | A single third-party dependency: name, ecosystem, version, scope, extras. |
| `Language` | Enum of programming languages (`OTHER` as explicit escape hatch). |
| `PackageEcosystem` | Enum of registries (`pypi`, `npm`, `cargo`, ...). |
| `DependencyScope` | Enum of dependency scopes (`runtime`, `dev`, `test`, `build`, `optional`). |
| `WorkEntry` | One logged unit of work on a codebase: which project, when, how many minutes, what kind. |
| `WorkLog` | Ordered collection of `WorkEntry` records with aggregation helpers (total time, per project, per kind, date ranges). |
| `WorkKind` | Enum of work categories (`feature`, `bugfix`, `refactor`, `docs`, ...). |
| `Complexity` | Optional XS–XL qualitative size label. |

Validation guarantees enforced by `Project`:

- `color_id` is a required integer in `[1, 1023]` (> 0, < 1024); the repository enforces that no two projects share one (409 on collision).
- `languages` has at least one entry and is de-duplicated (order preserved).
- `primary_language` defaults to the first language and must be one of `languages`.
- `packages` may not contain two entries sharing the same `(ecosystem, name)` identity.
- Unknown fields are rejected (`extra="forbid"`); strings are whitespace-stripped; assignment is re-validated.

> **Migration:** records persisted before `color_id` existed are back-filled with
> the smallest free color on load (once), so upgrading never crashes on old data.

## Usage

```python
from master_plan import (
    Project, Package, Language, PackageEcosystem, DependencyScope,
)

project = Project(
    name="master-plan-painel",
    color_id=42,
    domain="developer-tooling",
    sub_domain="cataloguing",
    purpose="Catalogue and track codebases by domain, purpose, language, and packages.",
    languages=[Language.PYTHON],
    packages=[
        Package(name="pydantic", version=">=2.11,<3"),
        Package(name="pytest", scope=DependencyScope.TEST),
    ],
    tags=["internal"],
)

project.runtime_packages                       # [Package(name='pydantic', ...)]
project.packages_in(PackageEcosystem.PYPI)     # both packages
Project.model_validate_json(project.model_dump_json()) == project  # True
```

## Tracking work

`WorkLog` records **how much** work went into **which** codebase and **when**.
Effort is a measured actual `duration` (minutes), not an estimate; `complexity`
(XS–XL) is an optional secondary label.

```python
from datetime import datetime, timezone
from master_plan import WorkLog, WorkKind

log = WorkLog()
log.log("master-plan-painel", datetime(2026, 7, 18, 9, tzinfo=timezone.utc),
        minutes=90, kind=WorkKind.FEATURE, summary="WorkLog model")
log.log("master-plan-painel", datetime(2026, 7, 18, 14, tzinfo=timezone.utc),
        minutes=30, kind=WorkKind.TEST)

log.total("master-plan-painel")          # timedelta(hours=2)
log.minutes_by_project()                 # {'master-plan-painel': 120}
log.minutes_by_kind("master-plan-painel")  # {WorkKind.FEATURE: 90, WorkKind.TEST: 30}
log.busiest_project()                    # 'master-plan-painel'
log.entries_between(start, end)          # inclusive date-range filter
```

Entries reference a project by `Project.name` (string), keeping the log
decoupled from the catalogue so it can be stored and queried independently.

## Projects API + UI (CRUDL)

A FastAPI backend exposes full CRUDL over projects, reusing the `Project`
Pydantic model as its request/response schema; a Svelte SPA consumes it.

**Authentication & ownership.** All `/api/projects` and `/api/work-*` routes
require a bearer token (`Authorization: Bearer <token>`) and are **scoped to the
authenticated user** — each caller only sees and mutates their own resources,
and `name`/`color_id` uniqueness is enforced per-owner. The public,
unauthenticated surface is `GET /api/health`, `GET /api/public` (a service
entry point that lists which routes need auth), and `POST /api/auth/register` /
`POST /api/auth/login`. Register or log in to obtain a token; unauthenticated
resource requests get `401`. Records persisted before ownership existed are
back-filled with an empty owner on load (orphaned, invisible to every user).

| Method & path | Action |
|---|---|
| `POST /api/projects` | Create (409 on duplicate name) |
| `GET /api/projects` | List |
| `GET /api/projects/{id}` | Read (404 if missing) |
| `PUT /api/projects/{id}` | Full replace |
| `PATCH /api/projects/{id}` | Partial update |
| `DELETE /api/projects/{id}` | Delete |

Projects are persisted to a JSON file (`MASTER_PLAN_DB`, default
`./data/projects.json`) and keyed by a server-assigned id; `name` is enforced
unique so it stays a valid reference target for `WorkLog`.

The same backend exposes CRUDL + aggregation for the work log (a **Work Log**
tab in the SPA lets you log effort against a project and see per-project totals):

| Method & path | Action |
|---|---|
| `GET /api/work-summary` | Totals: overall, per project, busiest |
| `GET /api/work-report` | Full report over a rolling window (`?days=7/30/90`, omit for all-time) and optional `?project=`; returns totals, active days, avg/day, per-project, per-kind, per-day, busiest day/project |
| `GET /api/work-entries` | List (`?project=` filter), newest first |
| `POST /api/work-entries` | Log work |
| `GET /api/work-entries/{id}` | Read (404 if missing) |
| `PUT /api/work-entries/{id}` | Full replace |
| `PATCH /api/work-entries/{id}` | Partial update |
| `DELETE /api/work-entries/{id}` | Delete |

Work entries persist to `MASTER_PLAN_WORKLOG_DB` (default
`./data/work_entries.json`) and reference a project by name (decoupled from the
catalogue, matching the `WorkLog` model); totals are computed via the domain
`WorkLog` model so the API and library agree.

### Errors

Every non-2xx response — validation, auth, domain conflict, not-found, and
unexpected server faults — uses **one** JSON shape (the *error envelope*, defined
in `api/errors.py`):

```json
{
  "error": {
    "code": "duplicate_color",
    "message": "color_id 7 is already used by another project",
    "request_id": "cdf54b1f1c1a4e87b5c4fe1783be7972",
    "details": [{ "field": "name", "message": "String should have at least 1 character" }]
  }
}
```

- `code` is **stable and machine-readable** — branch on it; never string-match `message`.
- `message` is human-facing and may change.
- `request_id` is unique per request and is also returned as the **`X-Request-ID`**
  response header, so a client-side failure can be correlated with its server log line.
- `details` is present only for validation errors (`422`); each entry names the
  offending `field` and why it is invalid.

| `code` | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | Request body/query failed validation (see `details`) |
| `unauthorized` | 401 | Missing, malformed, expired, or revoked credential |
| `forbidden` | 403 | Authenticated but lacks the required scope (e.g. read-only key on a write) |
| `not_found` | 404 | Resource does not exist or is not owned by the caller |
| `duplicate_name` | 409 | A project with that name already exists (per owner) |
| `duplicate_color` | 409 | A project already uses that `color_id` (per owner) |
| `duplicate_user` | 409 | An account with that username or email already exists |
| `conflict` | 409 | Other uniqueness violation |
| `internal_error` | 500 | Unexpected server fault; the cause is logged server-side (with `request_id`) and **never** returned to the client |

> **ARCHITECTURAL REQUIREMENT (PALS's LAW):** LLMs and servers alike produce
> errors. The frontend treats every response as untrusted input —
> `frontend/src/lib/http.ts` turns any non-2xx into a typed `ApiError` carrying
> `status`, `code`, `message`,
> `details`, and `requestId`, rather than silently ignoring it. The `500` handler
> never leaks internal exception text.

```bash
# Backend  (repo root) — API on :8000
pip install -e ".[api]"
uvicorn master_plan.api.main:app --reload --port 8000

# Frontend (./frontend) — SPA on :5173, proxies /api to :8000
cd frontend && npm install && npm run dev
```

Then open <http://localhost:5173>. See [frontend/README.md](./frontend/README.md) for details.

## Layout

```
.
├── pyproject.toml
├── src/master_plan/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── project.py      # Project, Package, and enums
│   │   └── work_log.py     # WorkLog, WorkEntry, and enums
│   └── api/
│       ├── __init__.py
│       ├── main.py               # FastAPI app + all routes
│       ├── errors.py             # ErrorEnvelope contract + exception handlers
│       ├── security.py           # password hashing, JWTs, API-key tokens
│       ├── repository.py         # JSON-file-backed ProjectRepository
│       ├── schemas.py            # ProjectRecord / ProjectUpdate
│       ├── user_repository.py    # JSON-file-backed UserRepository
│       ├── auth_schemas.py       # RegisterRequest / LoginRequest / User / Token
│       ├── api_key_repository.py # JSON-file-backed ApiKeyRepository
│       ├── api_key_schemas.py    # ApiKeyCreate / ApiKeyPublic / ApiKeyCreated
│       ├── work_repository.py    # JSON-file-backed WorkLogRepository
│       └── work_schemas.py       # WorkEntryRecord / WorkEntryUpdate / WorkSummary
├── frontend/               # Svelte + TS + Vite SPA (see frontend/README.md)
└── tests/
    ├── test_project.py
    ├── test_work_log.py
    ├── test_api.py
    ├── test_work_api.py
    ├── test_auth.py
    ├── test_auth_api.py
    ├── test_api_keys.py
    └── test_error_envelope.py    # error-envelope contract
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Docker

Run the API and Svelte/Vite frontend together:

```bash
docker compose up --build
```

Three services come up:

| Service | Port | Role |
|---|---|---|
| `proxy` (nginx) | **8088** | Single front door — serves the SPA and proxies `/api` to the backend (one origin). |
| `frontend` (Vite) | 5173 | Dev server with HMR (also fronted by the proxy). |
| `api` (uvicorn) | 8000 | FastAPI backend. |

**Use <http://localhost:8088>** as the app URL — the SPA and API share that one
origin, so requests are same-origin (no CORS, no dev proxy) — closest to a real
deployment. `5173` stays published so Vite's HMR websocket keeps working when you
view the app through the proxy; `8000` is exposed for direct API access/debugging.
The nginx config is [`nginx/default.conf`](./nginx/default.conf); override the
host port with `PROXY_PORT` if `8088` is taken.

Project records are stored in the `api_data` Docker volume at
`/data/projects.json`.

> **Note (behind a custom hostname):** the Vite dev server may reject a Host it
> doesn't recognise. On `localhost` this works out of the box; for a UAT domain,
> add that host to `server.allowedHosts` in `frontend/vite.config.ts`.

## Production / UAT (build-journal.dev)

The dev compose above (source mounts, `uvicorn --reload`, Vite HMR) is **not** for
deployment. Production and UAT use [`docker-compose.prod.yml`](./docker-compose.prod.yml),
which builds two immutable images:

| Service | Image stage | Role |
|---|---|---|
| `web` | `web` (Caddy) | Edge. Serves the **pre-built** SPA and reverse-proxies `/api`. Automatic HTTPS (Let's Encrypt) + HTTP/3 for the configured hostname. |
| `api` | `api-runtime` | FastAPI on a non-root user, **single worker**, code baked into the image (no mounts, no reload). |

One origin, so the browser makes same-origin calls (no CORS). Response headers —
`X-Request-ID` and `WWW-Authenticate` — pass through the proxy unchanged.

```bash
cp .env.example .env
# set MASTER_PLAN_SECRET (openssl rand -hex 32); SITE_ADDRESS defaults to build-journal.dev
docker compose -f docker-compose.prod.yml up -d --build
```

**Configuration** (`.env`, see [`.env.example`](./.env.example)):

| Var | Purpose |
|---|---|
| `MASTER_PLAN_SECRET` | **Required.** JWT signing key. The compose refuses to start if unset (`openssl rand -hex 32`); with `MASTER_PLAN_ENV=production` the API also refuses to boot without it. |
| `SITE_ADDRESS` | Hostname Caddy serves and auto-provisions TLS for. `build-journal.dev` / `uat.build-journal.dev` → automatic HTTPS; `:80` → plain HTTP behind an external TLS terminator (cloud LB). |

**Automatic HTTPS** needs this host reachable on public `:80` and `:443` with a DNS
`A`/`AAAA` record for `SITE_ADDRESS` pointing at it. Issued certificates persist in
the `caddy_data` volume — **back it up** to avoid re-issuing on every redeploy.

> ⚠ **`--workers 1` is a correctness constraint, not a tuning choice.** The
> repositories are JSON-file-backed and cache the whole store in memory between
> writes; a second worker would keep a private copy and its writes would silently
> clobber the other's. Concurrency requires first moving to a store that supports
> concurrent writers (SQLite/Postgres) — see [`docker-compose.prod.yml`](./docker-compose.prod.yml).

Persisted state lives in named volumes: `api_data` (the JSON stores) and
`caddy_data` (TLS certificates/ACME state). Update with
`docker compose -f docker-compose.prod.yml up -d --build`.

---

Back to root [README.md](./README.md).
