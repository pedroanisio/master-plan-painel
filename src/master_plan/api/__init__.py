"""HTTP API layer for the master-plan project catalogue."""

from master_plan.api.main import (
    app,
    create_app,
    get_repository,
    get_user_repository,
    get_work_repository,
)
from master_plan.api.auth_schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    Token,
    TokenPayload,
    UserRecord,
    UserUpdate,
)
from master_plan.api.user_repository import DuplicateUserError, UserRepository
from master_plan.api.repository import DuplicateNameError, ProjectRepository
from master_plan.api.schemas import ProjectCreate, ProjectRecord, ProjectUpdate
from master_plan.api.work_repository import WorkLogRepository
from master_plan.api.work_schemas import (
    WorkEntryCreate,
    WorkEntryRecord,
    WorkEntryUpdate,
    WorkSummary,
)

__all__ = [
    "app",
    "create_app",
    "get_repository",
    "get_work_repository",
    "get_user_repository",
    "DuplicateNameError",
    "ProjectRepository",
    "ProjectCreate",
    "ProjectRecord",
    "ProjectUpdate",
    "RegisterRequest",
    "LoginRequest",
    "UserRecord",
    "UserUpdate",
    "UserRepository",
    "DuplicateUserError",
    "Token",
    "TokenPayload",
    "AuthResponse",
    "WorkLogRepository",
    "WorkEntryCreate",
    "WorkEntryRecord",
    "WorkEntryUpdate",
    "WorkSummary",
]
