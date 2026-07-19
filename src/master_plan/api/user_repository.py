"""JSON-file-backed repository for user accounts.

Mirrors :class:`~master_plan.api.repository.ProjectRepository`: the whole set of
users is held in memory and rewritten to a JSON file on every mutation, keyed by
an opaque server-assigned id.

Both ``email`` and ``username`` are unique business keys (either can be used to
log in), so :meth:`UserRepository.create` raises :class:`DuplicateUserError` on
collision with a specific ``field`` so the API can report which one clashed.

The stored password *hash* is persisted here even though
:class:`~master_plan.api.auth_schemas.UserRecord` excludes it from ordinary
serialization — the exclusion protects API responses, so this module writes the
hash explicitly rather than relying on ``model_dump``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from master_plan.api._io import atomic_write_text
from master_plan.api.auth_schemas import UserRecord
from master_plan.api.security import hash_password
from master_plan.models.auth import Role, UserRegistration

__all__ = ["UserRepository", "DuplicateUserError"]


class DuplicateUserError(ValueError):
    """Raised when an email or username collides with an existing account."""

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"a user with that {field} already exists")
        self.field = field
        self.value = value


class UserRepository:
    """In-memory user store persisted to a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._records: dict[str, UserRecord] = {}
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8") or "[]")
        self._records = {
            item["id"]: UserRecord.model_validate(item) for item in raw
        }

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for record in self._records.values():
            # hashed_password is excluded from model_dump by design; write it
            # back explicitly so accounts survive a reload.
            item = record.model_dump(mode="json")
            item["hashed_password"] = record.hashed_password
            payload.append(item)
        atomic_write_text(
            self._path, json.dumps(payload, indent=2, ensure_ascii=False)
        )

    # -- queries -----------------------------------------------------------
    def list(self) -> list[UserRecord]:
        """Return all user records in insertion order."""
        return list(self._records.values())

    def get(self, user_id: str) -> UserRecord | None:
        """Return the record with ``user_id``, or ``None``."""
        return self._records.get(user_id)

    def get_by_identifier(self, identifier: str) -> UserRecord | None:
        """Return the record whose email or username equals ``identifier``.

        Matching is case-insensitive, consistent with how the domain model
        lower-cases emails and how usernames are treated as handles.
        """
        needle = identifier.strip().lower()
        for record in self._records.values():
            if record.email == needle or record.username.lower() == needle:
                return record
        return None

    def _field_owner(self, field: str, value: str) -> str | None:
        lowered = value.lower()
        for record in self._records.values():
            current = getattr(record, field)
            if current.lower() == lowered:
                return record.id
        return None

    # -- mutations ---------------------------------------------------------
    def create(
        self, registration: UserRegistration, *, role: Role = Role.VIEWER
    ) -> UserRecord:
        """Hash the password, persist a new user, and return its record."""
        if self._field_owner("email", registration.email) is not None:
            raise DuplicateUserError("email", registration.email)
        if self._field_owner("username", registration.username) is not None:
            raise DuplicateUserError("username", registration.username)

        user_id = uuid.uuid4().hex
        hashed = hash_password(registration.password.get_secret_value())
        record = UserRecord.from_user(
            user_id, registration.to_user(role=role), hashed_password=hashed
        )
        self._records[user_id] = record
        self._persist()
        return record

    def delete(self, user_id: str) -> bool:
        """Delete the record; return ``True`` if something was removed."""
        if user_id not in self._records:
            return False
        del self._records[user_id]
        self._persist()
        return True
