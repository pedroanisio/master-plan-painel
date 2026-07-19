---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-07-18"
---

# Deploying to DigitalOcean App Platform

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](./DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

The App Platform spec lives at [.do/app.yaml](./.do/app.yaml). It defines two
components under one app, on one origin:

| Component | Type | Serves | Route |
|---|---|---|---|
| `web` | static site | the built Svelte SPA (`frontend/dist`), via DO's CDN | `/` |
| `api` | service | FastAPI, built from the repo `Dockerfile` (final `api-runtime` stage) | `/api` |

Because both sit behind the App Platform router on the same hostname, the SPA
calls `/api/...` **same-origin** — no CORS, and `MASTER_PLAN_CORS_ORIGINS` is
set to empty.

---

## Data persistence: DigitalOcean Spaces

App Platform **service containers have ephemeral local disk**, so this app
mirrors its JSON stores (projects, work log, users, API keys) to a **Spaces**
bucket: each store is downloaded to local disk on boot and re-uploaded after
every write (`master_plan/api/spaces.py`). Data therefore survives deploys and
restarts.

Two constraints follow from the write-through design:

- **`instance_count` must stay 1.** It is a single-writer mirror — two
  instances would race on the same objects and lose writes.
- **If the `MASTER_PLAN_SPACES_*` vars are unset, it falls back to ephemeral
  local disk** (demo only — wiped on every deploy).

### One-time Spaces setup

1. **Create a Space** (Create → Spaces Object Storage). Note its **name** and
   **region** (e.g. `nyc3`); the endpoint is `https://<region>.digitaloceanspaces.com`.
2. **Create a Spaces access key** (API → Spaces Keys → Generate New Key). You
   get an **access key** and a **secret** — store both as encrypted secrets.
3. Fill the `MASTER_PLAN_SPACES_*` values in [.do/app.yaml](./.do/app.yaml):

   | Var | Example | Notes |
   |---|---|---|
   | `MASTER_PLAN_SPACES_BUCKET` | `master-plan-data` | Space name |
   | `MASTER_PLAN_SPACES_ENDPOINT` | `https://nyc3.digitaloceanspaces.com` | regional host |
   | `MASTER_PLAN_SPACES_REGION` | `nyc3` | label (boto3 needs one) |
   | `MASTER_PLAN_SPACES_PREFIX` | `master-plan/` | optional key prefix |
   | `MASTER_PLAN_SPACES_KEY` | *(secret)* | Spaces access key |
   | `MASTER_PLAN_SPACES_SECRET` | *(secret)* | Spaces secret key |

> Note: the separate Docker/Caddy stack ([docker-compose.prod.yml](./docker-compose.prod.yml))
> instead persists to a mounted named volume — that path targets a self-managed
> VM/Droplet. App Platform is the managed/CDN path, and uses Spaces because it
> has no persistent local volume.

---

## Deploy steps

1. **Connect the repo.** Push this repository to GitHub, then in App Platform
   connect that GitHub account. Replace `your-github-org/master-plan-painel`
   in [.do/app.yaml](./.do/app.yaml) (two places) with your `owner/repo`.

2. **Set the signing secret.** Generate one and store it as an encrypted
   secret — never commit the real value:

   ```bash
   openssl rand -hex 32
   ```

   Put it in App Platform → your app → **Settings → Environment Variables**
   as `MASTER_PLAN_SECRET` (encrypted), or pass it when creating via `doctl`.
   The API **refuses to boot** in production without it (`MASTER_PLAN_ENV=production`).

3. **Create the app** (with the [`doctl`](https://docs.digitalocean.com/reference/doctl/) CLI):

   ```bash
   doctl apps spec validate .do/app.yaml
   doctl apps create --spec .do/app.yaml
   ```

   Or use the UI: **Create App → from your repo → import the App Spec**.

4. **Verify.** After the deploy goes green:

   ```bash
   curl https://<your-app>.ondigitalocean.app/api/health   # {"status":"ok"}
   ```

   Open the app URL; the SPA loads and talks to `/api` same-origin.

---

## Notes & tuning

- `instance_size_slug: basic-xxs` is the smallest tier — bump it (e.g.
  `basic-xs`) if the API needs more memory. Adjust `region` (`nyc`) to taste.
- The API route sets `preserve_path_prefix: true` — required, because App
  Platform strips the matched prefix by default and every API route is mounted
  under `/api`.
- The frontend loads Google Fonts at runtime (progressive enhancement); it
  falls back to the system stack if unreachable.
- Health check hits the unauthenticated `GET /api/health`.
