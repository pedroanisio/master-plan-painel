---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-07-18"
---

# master-plan-painel · Frontend

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../DISCLAIMER.md).

> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Svelte 5 + TypeScript + Vite single-page app with two tabs:

- **Projects** — full CRUDL over the catalogue: create, read (list + detail),
  update, and delete.
- **Work Log** — log effort against a project, filter entries by project, edit
  or delete them, see per-project totals, and explore **visualization modes**:
  day-by-day bars (14/30/90-day window), a calendar heatmap (last 26 weeks),
  and by-project / by-kind breakdowns.
- **Reports** — full effort report over **7 / 30 / 90-day** presets (and
  all-time), optionally scoped to one project: headline stats (total, active
  days, avg/active day, busiest day/project), a daily bar chart, and
  per-project (colored) and per-kind breakdowns. Backed by `GET /api/work-report`.
- **Public landing** — signed-out visitors see a public entry point (backed by
  `GET /api/public`) instead of any protected request.

It talks to the FastAPI backend over `/api`, proxied to
`http://localhost:8000` during development.

## Run (both processes)

```bash
# 1. Backend (from repo root) — serves the API on :8000
pip install -e ".[api]"
MASTER_PLAN_DB=./data/projects.json \
  uvicorn master_plan.api.main:app --reload --port 8000

# 2. Frontend (from ./frontend) — serves the SPA on :5173
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api/*` to the
backend, so no CORS configuration is needed in development.

## Scripts

| Command           | Purpose                                             |
| ----------------- | --------------------------------------------------- |
| `npm run dev`     | Start the dev server (hot reload) on port 5173.     |
| `npm run build`   | Type-check-free production build into `dist/`.      |
| `npm run preview` | Serve the built `dist/` locally.                    |
| `npm run check`   | `svelte-check` — TypeScript + Svelte type checking. |

## Structure

```
frontend/
├── index.html
├── vite.config.ts          # dev server + /api proxy to :8000
├── src/
│   ├── main.ts             # mounts App
│   ├── app.css             # theme tokens (light/dark)
│   ├── App.svelte          # page shell, tab nav, projects orchestration
│   └── lib/
│       ├── http.ts         # shared fetch helpers + ApiError
│       ├── types.ts        # project types mirroring the Pydantic models
│       ├── api.ts          # project API client
│       ├── work-types.ts   # work-log types
│       ├── work-api.ts     # work-log API client
│       ├── ProjectForm.svelte   # create/edit form
│       ├── ProjectList.svelte   # catalogue table
│       ├── ProjectView.svelte   # single-project detail (read)
│       └── WorkLogView.svelte   # work-log tab: form, totals, entries
```

The `http.ts` helpers treat every server response as untrusted input and raise
a typed `ApiError` on any non-2xx status, per the project's LLM/output
verification posture. `ApiError` parses the backend **error envelope**
(`{ error: { code, message, request_id, details } }`) and exposes `status`,
`code` (branch on this — it is stable), `message`, `details` (field-level
validation problems), and `requestId` (matches the `X-Request-ID` header, for
bug reports). Parsing is defensive: a non-envelope body falls back to the HTTP
status line. See the root [README](../README.md#errors) for the code catalogue.

---

Back to root [README.md](../README.md).
