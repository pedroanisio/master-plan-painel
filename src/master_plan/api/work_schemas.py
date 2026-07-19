"""API request/response schemas for the work-log endpoints.

Mirrors the project schemas: the domain model
:class:`~master_plan.models.work_log.WorkEntry` is used directly as the create
body, :class:`WorkEntryRecord` adds a server-assigned ``id``, and
:class:`WorkEntryUpdate` is a partial patch.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from master_plan.models.work_log import Complexity, WorkEntry, WorkKind

__all__ = [
    "WorkEntryCreate",
    "WorkEntryRecord",
    "WorkEntryUpdate",
    "WorkSummary",
    "WorkReport",
]

# Creating a work entry takes the full domain model as its body.
WorkEntryCreate = WorkEntry


class WorkEntryRecord(WorkEntry):
    """A persisted work entry: the domain model plus server-assigned identity.

    ``owner_id`` is the id of the user the entry belongs to, assigned by the
    server from the authenticated caller.
    """

    id: str = Field(..., description="Server-assigned unique identifier.")
    owner_id: str = Field(..., description="Id of the user that owns this entry.")

    @classmethod
    def from_entry(
        cls, id: str, entry: WorkEntry, *, owner_id: str
    ) -> "WorkEntryRecord":
        """Combine an ``id`` and ``owner_id`` with an existing :class:`WorkEntry`."""
        return cls(id=id, owner_id=owner_id, **entry.model_dump())

    def to_entry(self) -> WorkEntry:
        """Return the underlying :class:`WorkEntry` without server-only fields."""
        return WorkEntry.model_validate(self.model_dump(exclude={"id", "owner_id"}))


class WorkEntryUpdate(BaseModel):
    """Partial update for a work entry; only provided fields are changed."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    project: str | None = Field(default=None, min_length=1)
    performed_at: datetime | None = None
    minutes: int | None = Field(default=None, gt=0)
    kind: WorkKind | None = None
    summary: str | None = None
    complexity: Complexity | None = None
    tags: list[str] | None = None

    def apply_to(self, entry: WorkEntry) -> WorkEntry:
        """Return a new ``WorkEntry`` with this patch's set fields overlaid."""
        patch = self.model_dump(exclude_unset=True)
        merged = {**entry.model_dump(), **patch}
        return WorkEntry.model_validate(merged)


class WorkSummary(BaseModel):
    """Aggregate view of the work log."""

    total_minutes: int
    by_project: dict[str, int]
    busiest_project: str | None
    by_day: dict[str, int] = Field(
        default_factory=dict,
        description="Total minutes per calendar day (YYYY-MM-DD → minutes).",
    )


class WorkReport(BaseModel):
    """A full effort report scoped to a rolling period and optional project.

    ``days`` is the window size (7/30/90/…); ``None`` means all-time. When
    ``project`` is set the whole report is scoped to that one project; either
    way ``by_project`` gives the per-project breakdown within the period.
    """

    days: int | None = Field(default=None, description="Window size; None = all-time.")
    from_date: str | None = Field(default=None, description="Inclusive start (YYYY-MM-DD).")
    to_date: str = Field(..., description="Reference 'today' (YYYY-MM-DD).")
    project: str | None = Field(default=None, description="Project filter, if any.")

    total_minutes: int
    entry_count: int
    active_days: int
    avg_minutes_per_active_day: float

    by_project: dict[str, int]
    by_kind: dict[str, int]
    by_day: dict[str, int]

    busiest_project: str | None
    busiest_day: str | None
