# syntax=docker/dockerfile:1

FROM python:3.13-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MASTER_PLAN_DB=/data/projects.json

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

# Editable install: the package resolves to /app/src, which docker-compose
# mounts from the host. Without -e, uvicorn would import a baked-in copy from
# site-packages and ignore live source edits (requiring a rebuild per change).
RUN pip install --no-cache-dir -e ".[api]"

EXPOSE 8000

CMD ["uvicorn", "master_plan.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM node:22-alpine AS frontend-deps

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci


FROM node:22-alpine AS frontend

ENV VITE_API_PROXY_TARGET=http://api:8000

WORKDIR /app/frontend

COPY --from=frontend-deps /app/frontend/node_modules ./node_modules
COPY frontend ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# ======================================================================
# Production / UAT stages (build-journal.dev). See docker-compose.prod.yml.
# ======================================================================

# --- Compile the SPA to static, hashed assets (no dev server) ---------
FROM frontend-deps AS frontend-build

WORKDIR /app/frontend

# node_modules comes from frontend-deps; .dockerignore keeps the host copy out.
COPY frontend ./
# All API calls are relative ("/api/..."), so the bundle needs no baked-in URL —
# it is served same-origin behind Caddy. Vite emits hashed assets into dist/.
RUN npm run build


# --- Edge: Caddy serves the SPA + reverse-proxies /api, with auto HTTPS ---
FROM caddy:2.8-alpine AS web

COPY --from=frontend-build /app/frontend/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile


# --- Production API: immutable install, non-root, single worker -------
#
# ⚠ SINGLE WORKER IS A CORRECTNESS CONSTRAINT, NOT A PERFORMANCE KNOB.
# The repositories are JSON-file-backed and cache the whole store in memory
# (functools.lru_cache) between writes. Two workers would each mutate a private
# copy and rewrite the file wholesale — the last writer silently clobbers the
# other's data. Do not add --workers > 1 without first moving to a store that
# supports concurrent writers (e.g. SQLite/Postgres).
FROM python:3.13-slim AS api-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root runtime user; owns the data dir so the volume is writable.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

# Non-editable install: the code is baked into site-packages (immutable image),
# unlike the dev `api` stage which installs -e for live source mounts.
RUN pip install --no-cache-dir ".[api]"

RUN mkdir -p /data && chown app:app /data
VOLUME ["/data"]

USER app

EXPOSE 8000

CMD ["uvicorn", "master_plan.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
