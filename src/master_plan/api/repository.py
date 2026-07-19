"""JSON-file-backed repository for :class:`Project` records.

This is deliberately simple, synchronous storage suitable for a single-user
local tool: the whole catalogue is held in memory and rewritten to a JSON file
on every mutation. Records are keyed by an opaque server-assigned id.

Project ``name`` and ``color_id`` are both treated as unique business keys
(a project is referenced by name from the work log, and every project owns a
distinct display color), so create/replace raise a :class:`ConflictError`
subclass on collision.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from master_plan.api._io import atomic_write_text
from master_plan.api.schemas import ProjectRecord
from master_plan.models.project import COLOR_ID_MAX, COLOR_ID_MIN, Project

__all__ = [
    "ProjectRepository",
    "ConflictError",
    "DuplicateNameError",
    "DuplicateColorError",
]


class ConflictError(ValueError):
    """Base for uniqueness violations in the project catalogue."""


class DuplicateNameError(ConflictError):
    """Raised when a project name would collide with an existing project."""

    def __init__(self, name: str) -> None:
        super().__init__(f"a project named {name!r} already exists")
        self.name = name


class DuplicateColorError(ConflictError):
    """Raised when a project color_id would collide with an existing project."""

    def __init__(self, color_id: int) -> None:
        super().__init__(f"color_id {color_id} is already used by another project")
        self.color_id = color_id


class ProjectRepository:
    """In-memory catalogue persisted to a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._records: dict[str, ProjectRecord] = {}
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8") or "[]")
        migrated = self._migrate_missing_colors(raw)
        self._records = {
            item["id"]: ProjectRecord.model_validate(item) for item in raw
        }
        if migrated:
            # Persist assigned colors so the migration runs exactly once.
            self._persist()

    @staticmethod
    def _migrate_missing_colors(raw: list[dict]) -> bool:
        """Back-fill legacy records missing ``color_id`` or ``owner_id``.

        Both fields became required after the first records were written:
        ``color_id`` (unique per owner) and ``owner_id`` (resource ownership).
        Rather than crash on load, assign each legacy record the smallest free
        color and an empty ``owner_id`` (an orphan owned by no user, invisible
        to every authenticated caller). Returns ``True`` if anything changed.
        """
        used = {
            item["color_id"]
            for item in raw
            if isinstance(item.get("color_id"), int)
        }
        migrated = False
        next_candidate = COLOR_ID_MIN
        for item in raw:
            if not isinstance(item.get("color_id"), int):
                while next_candidate in used and next_candidate <= COLOR_ID_MAX:
                    next_candidate += 1
                if next_candidate > COLOR_ID_MAX:
                    raise RuntimeError(
                        "cannot migrate: all color ids in "
                        f"[{COLOR_ID_MIN}, {COLOR_ID_MAX}] are taken"
                    )
                item["color_id"] = next_candidate
                used.add(next_candidate)
                migrated = True
            if not isinstance(item.get("owner_id"), str):
                item["owner_id"] = ""
                migrated = True
        return migrated

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self._records.values()]
        atomic_write_text(
            self._path, json.dumps(payload, indent=2, ensure_ascii=False)
        )

    # -- queries -----------------------------------------------------------
    # Every query and mutation is scoped to an ``owner_id``: callers only ever
    # see and touch their own projects. ``name`` and ``color_id`` uniqueness is
    # likewise per-owner — two different users may reuse the same name/color.
    def list(self, owner_id: str) -> list[ProjectRecord]:
        """Return the owner's records in insertion order."""
        return [r for r in self._records.values() if r.owner_id == owner_id]

    def get(self, project_id: str, owner_id: str) -> ProjectRecord | None:
        """Return the owner's record with ``project_id``, or ``None``."""
        record = self._records.get(project_id)
        if record is None or record.owner_id != owner_id:
            return None
        return record

    def _name_owner(self, name: str, owner_id: str) -> str | None:
        """Return the id of the owner's record holding ``name``, if any."""
        lowered = name.lower()
        for record in self._records.values():
            if record.owner_id == owner_id and record.name.lower() == lowered:
                return record.id
        return None

    def _color_owner(self, color_id: int, owner_id: str) -> str | None:
        """Return the id of the owner's record holding ``color_id``, if any."""
        for record in self._records.values():
            if record.owner_id == owner_id and record.color_id == color_id:
                return record.id
        return None

    def used_color_ids(self, owner_id: str) -> set[int]:
        """Return the owner's color ids currently in use."""
        return {
            r.color_id for r in self._records.values() if r.owner_id == owner_id
        }

    def _assert_unique(
        self, project: Project, owner_id: str, exclude_id: str | None = None
    ) -> None:
        """Raise if ``name`` or ``color_id`` collide within the owner's set."""
        name_owner = self._name_owner(project.name, owner_id)
        if name_owner is not None and name_owner != exclude_id:
            raise DuplicateNameError(project.name)
        color_owner = self._color_owner(project.color_id, owner_id)
        if color_owner is not None and color_owner != exclude_id:
            raise DuplicateColorError(project.color_id)

    # -- mutations ---------------------------------------------------------
    def create(self, project: Project, owner_id: str) -> ProjectRecord:
        """Persist a new project owned by ``owner_id`` and return its record."""
        self._assert_unique(project, owner_id)
        project_id = uuid.uuid4().hex
        record = ProjectRecord.from_project(project_id, project, owner_id=owner_id)
        self._records[project_id] = record
        self._persist()
        return record

    def replace(
        self, project_id: str, project: Project, owner_id: str
    ) -> ProjectRecord | None:
        """Replace the owner's project; return ``None`` if missing/not owned."""
        existing = self._records.get(project_id)
        if existing is None or existing.owner_id != owner_id:
            return None
        self._assert_unique(project, owner_id, exclude_id=project_id)
        record = ProjectRecord.from_project(project_id, project, owner_id=owner_id)
        self._records[project_id] = record
        self._persist()
        return record

    def delete(self, project_id: str, owner_id: str) -> bool:
        """Delete the owner's record; return ``True`` if something was removed."""
        existing = self._records.get(project_id)
        if existing is None or existing.owner_id != owner_id:
            return False
        del self._records[project_id]
        self._persist()
        return True
