"""FastAPI application exposing full CRUDL over projects.

Endpoints (all under ``/api``):

===========================  ==========================================
``POST   /api/projects``     Create a project (409 on duplicate name)
``GET    /api/projects``     List all projects
``GET    /api/projects/{id}``   Read one project (404 if missing)
``PUT    /api/projects/{id}``   Full replace (404/409)
``PATCH  /api/projects/{id}``   Partial update (404/409)
``DELETE /api/projects/{id}``   Delete (404 if missing)
===========================  ==========================================

Auth endpoints (all under ``/api``):

=================================  =====================================
``POST   /api/auth/register``      Create an account (409 on duplicate)
``POST   /api/auth/login``         Exchange credentials for a token (401)
``GET    /api/auth/me``            Current user from the bearer token (401)
=================================  =====================================

API-key endpoints (session-only; a key can never manage keys):

=================================  =====================================
``POST   /api/auth/api-keys``      Mint a key (plaintext token shown once)
``GET    /api/auth/api-keys``      List the owner's keys (no secrets)
``DELETE /api/auth/api-keys/{id}`` Revoke a key (soft, audit-preserving)
=================================  =====================================

Requests authenticate with a browser session (signed JWT) OR an API key sent as
``X-API-Key: mpk_…`` or ``Authorization: Bearer mpk_…``. A key acts as its owner,
limited to its ``read``/``write`` scopes: reads need read, writes need write.

Work-log endpoints (all under ``/api``):

=================================  =====================================
``GET    /api/work-summary``       Totals: overall, per project, busiest
``GET    /api/work-entries``       List entries (``?project=`` filter)
``POST   /api/work-entries``       Log work
``GET    /api/work-entries/{id}``  Read one (404 if missing)
``PUT    /api/work-entries/{id}``  Full replace (404)
``PATCH  /api/work-entries/{id}``  Partial update (404/422)
``DELETE /api/work-entries/{id}``  Delete (404 if missing)
=================================  =====================================

All ``/api/projects`` and ``/api/work-*`` routes require a bearer token and are
scoped to the authenticated user: a caller only ever sees and mutates their own
resources. ``name``/``color_id`` uniqueness is per-owner. The public,
unauthenticated surface is ``GET /api/health``, ``GET /api/public``, and the
``POST /api/auth/{register,login}`` routes.

Every error response shares one JSON shape — the error envelope
``{"error": {"code", "message", "request_id", "details"?}}`` with a matching
``X-Request-ID`` header — installed by :func:`master_plan.api.errors.
install_error_handlers`. Routes raise plain ``HTTPException``s or let domain
exceptions (``DuplicateNameError``, ``DuplicateColorError``, ``DuplicateUserError``,
``ValidationError``) propagate; the handlers map each to a stable ``code``.

Repositories are injected via FastAPI dependency override in tests; in
production they read JSON paths from the ``MASTER_PLAN_DB`` (default
``./data/projects.json``), ``MASTER_PLAN_WORKLOG_DB`` (default
``./data/work_entries.json``) and ``MASTER_PLAN_USERS_DB`` (default
``./data/users.json``) env vars.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from master_plan.api.api_key_repository import ApiKeyRepository
from master_plan.api.api_key_schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyPublic,
    ApiKeyRecord,
)
from master_plan.api.auth_schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    Token,
    User,
    UserRecord,
)
from master_plan.api.errors import install_error_handlers
from master_plan.api.repository import ProjectRepository
from master_plan.api.schemas import ProjectCreate, ProjectRecord, ProjectUpdate
from master_plan.api.security import (
    API_KEY_PREFIX,
    TokenError,
    create_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    verify_password,
    verify_signing_secret,
)
from master_plan.api.user_repository import UserRepository
from master_plan.api.work_repository import WorkLogRepository
from master_plan.api.work_schemas import (
    WorkEntryCreate,
    WorkEntryRecord,
    WorkEntryUpdate,
    WorkReport,
    WorkSummary,
)

__all__ = [
    "app",
    "create_app",
    "get_repository",
    "get_work_repository",
    "get_user_repository",
    "get_api_key_repository",
    "require_user",
    "require_write",
    "require_session_user",
]

# Access-token lifetime in seconds (1 hour).
TOKEN_TTL_SECONDS = 3600


@lru_cache(maxsize=1)
def get_repository() -> ProjectRepository:
    """Default repository dependency (overridable in tests)."""
    db_path = os.environ.get("MASTER_PLAN_DB", "./data/projects.json")
    return ProjectRepository(db_path)


@lru_cache(maxsize=1)
def get_work_repository() -> WorkLogRepository:
    """Default work-log repository dependency (overridable in tests)."""
    db_path = os.environ.get("MASTER_PLAN_WORKLOG_DB", "./data/work_entries.json")
    return WorkLogRepository(db_path)


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    """Default user repository dependency (overridable in tests)."""
    db_path = os.environ.get("MASTER_PLAN_USERS_DB", "./data/users.json")
    return UserRepository(db_path)


@lru_cache(maxsize=1)
def get_api_key_repository() -> ApiKeyRepository:
    """Default API-key repository dependency (overridable in tests)."""
    db_path = os.environ.get("MASTER_PLAN_APIKEYS_DB", "./data/api_keys.json")
    return ApiKeyRepository(db_path)


def _current_user(
    users: UserRepository,
    authorization: str | None,
) -> UserRecord:
    """Resolve the ``Authorization: Bearer <token>`` header to a user record.

    ⚠ ARCHITECTURAL CONTRACT (PALS's LAW): the token is untrusted input. The
    signature and expiry are verified by :func:`decode_token`, and the subject
    is re-resolved against the store — a validly-signed token for a deleted
    user is still rejected here.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_token(token)
    except TokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    record = users.get(str(claims.get("sub", "")))
    if record is None or not record.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "user no longer valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return record


@dataclass(frozen=True)
class Principal:
    """The authenticated caller: the user plus how they authenticated.

    ``scopes`` gates what the caller may do — a browser session has full access;
    an API key carries only its granted scopes. ``via`` distinguishes the two so
    key/account management can stay session-only.
    """

    user: UserRecord
    scopes: frozenset[str]
    via: str  # "session" | "api_key"


def _principal_from_api_key(
    raw_key: str, users: UserRepository, keys: ApiKeyRepository
) -> Principal:
    """Resolve an API-key string to a :class:`Principal`, or raise 401."""
    now = datetime.now(timezone.utc)
    record = keys.get_by_token(hash_api_key(raw_key))
    if record is None or not record.is_active(now):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid, revoked, or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = users.get(record.owner_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user no longer valid")
    keys.touch(record.id, now)
    return Principal(
        user=user,
        scopes=frozenset(scope.value for scope in record.scopes),
        via="api_key",
    )


def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    users: UserRepository = Depends(get_user_repository),
    keys: ApiKeyRepository = Depends(get_api_key_repository),
) -> Principal:
    """Authenticate via API key (``X-API-Key`` or ``Bearer mpk_…``) or session.

    ⚠ ARCHITECTURAL CONTRACT (PALS's LAW): both credentials are untrusted input.
    Each is verified against the store and the subject re-resolved before any
    access is granted.
    """
    raw_key: str | None = None
    if x_api_key:
        raw_key = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        candidate = authorization.split(" ", 1)[1].strip()
        if candidate.startswith(API_KEY_PREFIX):
            raw_key = candidate
    if raw_key:
        return _principal_from_api_key(raw_key, users, keys)
    # Otherwise it must be a browser session (a signed JWT).
    user = _current_user(users, authorization)
    return Principal(user=user, scopes=frozenset({"read", "write"}), via="session")


def require_user(principal: Principal = Depends(get_principal)) -> UserRecord:
    """Caller for a read route — any credential with read access, else 401/403.

    Applied to every resource read so projects and work entries stay scoped to
    the caller. A write-only credential still has read access (write ⊇ read).
    """
    if not ({"read", "write"} & principal.scopes):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this key lacks read access")
    return principal.user


def require_write(principal: Principal = Depends(get_principal)) -> UserRecord:
    """Caller for a mutating route — requires the ``write`` scope, else 403."""
    if "write" not in principal.scopes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this key is read-only")
    return principal.user


def require_session_user(principal: Principal = Depends(get_principal)) -> UserRecord:
    """Caller for key/account management — a browser session only, else 403.

    API keys deliberately cannot mint or revoke keys: a leaked key must never be
    able to escalate its own reach or lock the user out.
    """
    if principal.via != "session":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "API keys cannot manage keys; use a signed-in session",
        )
    return principal.user


def _cors_origins() -> list[str]:
    """Resolve the CORS allow-list from ``MASTER_PLAN_CORS_ORIGINS``.

    - unset  → the local Vite dev origins (developer default);
    - ``""`` → no origins (middleware disabled — same-origin deployment);
    - ``"*"``→ any origin;
    - else   → comma-separated list of allowed origins.
    """
    raw = os.environ.get("MASTER_PLAN_CORS_ORIGINS")
    if raw is None:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(
    repository: ProjectRepository | None = None,
    work_repository: WorkLogRepository | None = None,
    user_repository: UserRepository | None = None,
    api_key_repository: ApiKeyRepository | None = None,
) -> FastAPI:
    """Build the FastAPI app, optionally with explicit repositories."""
    # Refuse to boot in production without a stable signing secret.
    verify_signing_secret()

    app = FastAPI(title="master-plan-painel API", version="0.1.0")

    # Every error path renders as a single ErrorEnvelope shape (see errors.py).
    install_error_handlers(app)

    # CORS origins are configurable so the API can sit on a different origin
    # than the SPA. MASTER_PLAN_CORS_ORIGINS is a comma-separated allow-list;
    # "*" allows any origin; empty disables the middleware entirely (the
    # default single-origin nginx deployment serves the SPA same-origin, so no
    # CORS is needed there). Unset falls back to the local Vite dev origins.
    origins = _cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if repository is not None:
        app.dependency_overrides[get_repository] = lambda: repository
    if work_repository is not None:
        app.dependency_overrides[get_work_repository] = lambda: work_repository
    if user_repository is not None:
        app.dependency_overrides[get_user_repository] = lambda: user_repository
    if api_key_repository is not None:
        app.dependency_overrides[get_api_key_repository] = lambda: api_key_repository

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # -- unauthenticated entry point --------------------------------------
    # A public route for callers with no session: it advertises the service and
    # which routes are reachable without a bearer token. Everything under
    # /api/projects and /api/work-* requires authentication.
    @app.get("/api/public")
    def public() -> dict[str, object]:
        return {
            "service": "master-plan-painel",
            "version": "0.1.0",
            "authenticated": False,
            "message": "Sign in to access your projects and work log.",
            "public_routes": [
                "GET /api/health",
                "GET /api/public",
                "POST /api/auth/register",
                "POST /api/auth/login",
            ],
            "authenticated_routes": [
                "GET /api/auth/me",
                "/api/projects (CRUDL)",
                "/api/work-entries (CRUDL)",
                "GET /api/work-summary",
            ],
        }

    # -- auth --------------------------------------------------------------
    @app.post(
        "/api/auth/register",
        response_model=AuthResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def register(
        payload: RegisterRequest,
        users: UserRepository = Depends(get_user_repository),
    ) -> AuthResponse:
        # DuplicateUserError propagates to the envelope handler (409).
        record = users.create(payload)
        access_token, expires_in = create_token(
            subject=record.id,
            role=record.role.value,
            expires_in=TOKEN_TTL_SECONDS,
        )
        return AuthResponse(
            user=record.public(),
            token=Token(access_token=access_token, expires_in=expires_in),
        )

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(
        payload: LoginRequest,
        users: UserRepository = Depends(get_user_repository),
    ) -> AuthResponse:
        record = users.get_by_identifier(payload.identifier)
        # Verify even when the user is unknown-shaped to avoid leaking which
        # half of the credentials was wrong; the outcome is the same 401.
        password_ok = record is not None and verify_password(
            payload.password.get_secret_value(), record.hashed_password
        )
        if record is None or not password_ok or not record.is_active:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "invalid credentials"
            )
        access_token, expires_in = create_token(
            subject=record.id,
            role=record.role.value,
            expires_in=TOKEN_TTL_SECONDS,
        )
        return AuthResponse(
            user=record.public(),
            token=Token(access_token=access_token, expires_in=expires_in),
        )

    @app.get("/api/auth/me", response_model=User)
    def me(
        authorization: str | None = Header(default=None),
        users: UserRepository = Depends(get_user_repository),
    ) -> User:
        return _current_user(users, authorization).public()

    # -- projects (owner-scoped; every route requires authentication) ------
    @app.get("/api/projects", response_model=list[ProjectRecord])
    def list_projects(
        repo: ProjectRepository = Depends(get_repository),
        user: UserRecord = Depends(require_user),
    ) -> list[ProjectRecord]:
        return repo.list(user.id)

    @app.post(
        "/api/projects",
        response_model=ProjectRecord,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(
        payload: ProjectCreate,
        repo: ProjectRepository = Depends(get_repository),
        user: UserRecord = Depends(require_write),
    ) -> ProjectRecord:
        # DuplicateName/DuplicateColorError propagate to the envelope handler.
        return repo.create(payload, user.id)

    @app.get("/api/projects/{project_id}", response_model=ProjectRecord)
    def read_project(
        project_id: str,
        repo: ProjectRepository = Depends(get_repository),
        user: UserRecord = Depends(require_user),
    ) -> ProjectRecord:
        record = repo.get(project_id, user.id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
        return record

    @app.put("/api/projects/{project_id}", response_model=ProjectRecord)
    def replace_project(
        project_id: str,
        payload: ProjectCreate,
        repo: ProjectRepository = Depends(get_repository),
        user: UserRecord = Depends(require_write),
    ) -> ProjectRecord:
        # DuplicateName/DuplicateColorError propagate to the envelope handler.
        record = repo.replace(project_id, payload, user.id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
        return record

    @app.patch("/api/projects/{project_id}", response_model=ProjectRecord)
    def update_project(
        project_id: str,
        payload: ProjectUpdate,
        repo: ProjectRepository = Depends(get_repository),
        user: UserRecord = Depends(require_write),
    ) -> ProjectRecord:
        existing = repo.get(project_id, user.id)
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
        # A ValidationError from the merged patch and a DuplicateName/Color
        # conflict from replace both propagate to the envelope handlers.
        merged = payload.apply_to(existing.to_project())
        record = repo.replace(project_id, merged, user.id)
        assert record is not None  # existence checked above
        return record

    @app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_project(
        project_id: str,
        repo: ProjectRepository = Depends(get_repository),
        user: UserRecord = Depends(require_write),
    ) -> Response:
        if not repo.delete(project_id, user.id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # -- work log (owner-scoped; every route requires authentication) ------
    @app.get("/api/work-summary", response_model=WorkSummary)
    def work_summary(
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_user),
    ) -> WorkSummary:
        return repo.summary(user.id)

    @app.get("/api/work-report", response_model=WorkReport)
    def work_report(
        days: int | None = None,
        project: str | None = None,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_user),
    ) -> WorkReport:
        # A full effort report over a rolling window (e.g. days=7/30/90) and an
        # optional project scope. Omitting `days` reports all-time.
        if days is not None and days <= 0:
            raise HTTPException(422, "days must be a positive integer")
        return repo.report(
            user.id,
            now=datetime.now(timezone.utc),
            days=days,
            project=project,
        )

    @app.get("/api/work-entries", response_model=list[WorkEntryRecord])
    def list_work_entries(
        project: str | None = None,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_user),
    ) -> list[WorkEntryRecord]:
        return repo.list(user.id, project)

    @app.post(
        "/api/work-entries",
        response_model=WorkEntryRecord,
        status_code=status.HTTP_201_CREATED,
    )
    def create_work_entry(
        payload: WorkEntryCreate,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_write),
    ) -> WorkEntryRecord:
        return repo.create(payload, user.id)

    @app.get("/api/work-entries/{entry_id}", response_model=WorkEntryRecord)
    def read_work_entry(
        entry_id: str,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_user),
    ) -> WorkEntryRecord:
        record = repo.get(entry_id, user.id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "work entry not found")
        return record

    @app.put("/api/work-entries/{entry_id}", response_model=WorkEntryRecord)
    def replace_work_entry(
        entry_id: str,
        payload: WorkEntryCreate,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_write),
    ) -> WorkEntryRecord:
        record = repo.replace(entry_id, payload, user.id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "work entry not found")
        return record

    @app.patch("/api/work-entries/{entry_id}", response_model=WorkEntryRecord)
    def update_work_entry(
        entry_id: str,
        payload: WorkEntryUpdate,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_write),
    ) -> WorkEntryRecord:
        existing = repo.get(entry_id, user.id)
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "work entry not found")
        # A ValidationError from the merged patch propagates to the envelope handler.
        merged = payload.apply_to(existing.to_entry())
        record = repo.replace(entry_id, merged, user.id)
        assert record is not None  # existence checked above
        return record

    @app.delete(
        "/api/work-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    def delete_work_entry(
        entry_id: str,
        repo: WorkLogRepository = Depends(get_work_repository),
        user: UserRecord = Depends(require_write),
    ) -> Response:
        if not repo.delete(entry_id, user.id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "work entry not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # -- API keys (session-only; keys cannot manage keys) ------------------
    @app.post(
        "/api/auth/api-keys",
        response_model=ApiKeyCreated,
        status_code=status.HTTP_201_CREATED,
    )
    def create_api_key(
        payload: ApiKeyCreate,
        keys: ApiKeyRepository = Depends(get_api_key_repository),
        user: UserRecord = Depends(require_session_user),
    ) -> ApiKeyCreated:
        token, prefix, token_hash = generate_api_key()
        now = datetime.now(timezone.utc)
        expires_at = (
            now + timedelta(days=payload.expires_in_days)
            if payload.expires_in_days
            else None
        )
        record = ApiKeyRecord(
            id=uuid.uuid4().hex,
            owner_id=user.id,
            name=payload.name,
            prefix=prefix,
            token_sha256=token_hash,
            scopes=payload.scopes,
            created_at=now,
            expires_at=expires_at,
        )
        keys.add(record)
        # The plaintext token appears here and never again.
        return ApiKeyCreated(**record.public().model_dump(), token=token)

    @app.get("/api/auth/api-keys", response_model=list[ApiKeyPublic])
    def list_api_keys(
        keys: ApiKeyRepository = Depends(get_api_key_repository),
        user: UserRecord = Depends(require_session_user),
    ) -> list[ApiKeyPublic]:
        return [record.public() for record in keys.list_for_owner(user.id)]

    @app.delete(
        "/api/auth/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    def revoke_api_key(
        key_id: str,
        keys: ApiKeyRepository = Depends(get_api_key_repository),
        user: UserRecord = Depends(require_session_user),
    ) -> Response:
        if not keys.revoke(key_id, user.id, datetime.now(timezone.utc)):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "api key not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
