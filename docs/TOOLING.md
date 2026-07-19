---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "master_plan.docgen"
---

# Tooling & API reference

> **Generated file — do not edit by hand.** Produced from source by `python -m master_plan.docgen`. Re-run after changing routes, env vars, or scripts; CI can enforce freshness with `--check`.

## Run it

| Command | What it does |
|---|---|
| `pip install -e ".[api]"` | Install the backend + tooling. |
| `uvicorn master_plan.api.main:app --host 0.0.0.0 --port 8000` | Run the API. |
| `python -m master_plan.docgen` | Regenerate this document. |
| `docker compose up` | Run the full stack (API + frontend + nginx). |

## HTTP API (22 routes)

`🔒` = requires a bearer token (owner-scoped); `public` = no auth. The gate name is the FastAPI dependency enforcing it.

| Method | Path | Access | Summary |
|---|---|---|---|
| `GET` | `/api/auth/api-keys` | 🔒 session_user | — |
| `POST` | `/api/auth/api-keys` | 🔒 session_user | — |
| `DELETE` | `/api/auth/api-keys/{key_id}` | 🔒 session_user | — |
| `POST` | `/api/auth/login` | public | — |
| `GET` | `/api/auth/me` | 🔒 bearer | — |
| `POST` | `/api/auth/register` | public | — |
| `GET` | `/api/health` | public | — |
| `GET` | `/api/projects` | 🔒 user | — |
| `POST` | `/api/projects` | 🔒 write | — |
| `DELETE` | `/api/projects/{project_id}` | 🔒 write | — |
| `GET` | `/api/projects/{project_id}` | 🔒 user | — |
| `PATCH` | `/api/projects/{project_id}` | 🔒 write | — |
| `PUT` | `/api/projects/{project_id}` | 🔒 write | — |
| `GET` | `/api/public` | public | — |
| `GET` | `/api/work-entries` | 🔒 user | — |
| `POST` | `/api/work-entries` | 🔒 write | — |
| `DELETE` | `/api/work-entries/{entry_id}` | 🔒 write | — |
| `GET` | `/api/work-entries/{entry_id}` | 🔒 user | — |
| `PATCH` | `/api/work-entries/{entry_id}` | 🔒 write | — |
| `PUT` | `/api/work-entries/{entry_id}` | 🔒 write | — |
| `GET` | `/api/work-report` | 🔒 user | — |
| `GET` | `/api/work-summary` | 🔒 user | — |

## Configuration (9 environment variables)

Every `MASTER_PLAN_*` variable the API reads, discovered from source.

| Variable | Default | Read in |
|---|---|---|
| `MASTER_PLAN_APIKEYS_DB` | `./data/api_keys.json` | `main.py` |
| `MASTER_PLAN_CORS_ORIGINS` | *(unset)* | `main.py` |
| `MASTER_PLAN_DB` | `./data/projects.json` | `main.py` |
| `MASTER_PLAN_ENV` | `` | `security.py` |
| `MASTER_PLAN_SECRET` | *(unset)* | `security.py` |
| `MASTER_PLAN_SPACES_PREFIX` | `` | `spaces.py` |
| `MASTER_PLAN_SPACES_REGION` | `us-east-1` | `spaces.py` |
| `MASTER_PLAN_USERS_DB` | `./data/users.json` | `main.py` |
| `MASTER_PLAN_WORKLOG_DB` | `./data/work_entries.json` | `main.py` |

## CLI scripts (1)

### `scripts/seed.py`

Seed the catalogue with realistic demo data for exercising the UI/analytics.

```
PYTHONPATH=src python3 scripts/seed.py [--out DIR] [--no-reset]
```
