"""Pydantic models for tracking work effort against projects (codebases).

A :class:`WorkEntry` records a single unit of work on one codebase: *which*
project, *when* the work happened, *how much* (duration), and *what kind* of
work it was. A :class:`WorkLog` is an ordered collection of entries with
aggregation helpers (total time, time per project, time within a date range).

Effort is recorded as an actual measured ``duration`` — this is logging of
work already performed, not an estimate. The XS–XL :class:`Complexity` scale is
offered as an optional, secondary label for qualitative sizing.

All models target Pydantic v2.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "WorkKind",
    "Complexity",
    "WorkEntry",
    "WorkLog",
]


class WorkKind(str, Enum):
    """Category of work performed in a single entry."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    REVIEW = "review"
    RESEARCH = "research"
    PLANNING = "planning"
    INFRA = "infra"
    MAINTENANCE = "maintenance"
    MEETING = "meeting"
    OTHER = "other"


class Complexity(str, Enum):
    """Qualitative effort size, per project convention (no time estimates)."""

    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class WorkEntry(BaseModel):
    """A single logged unit of work on one project."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    project: str = Field(
        ...,
        min_length=1,
        description="Name of the project worked on (matches `Project.name`).",
    )
    performed_at: datetime = Field(
        ...,
        description="When the work happened (timezone-aware recommended).",
    )
    minutes: int = Field(
        ...,
        gt=0,
        description="Amount of work, in whole minutes.",
    )
    kind: WorkKind = Field(
        default=WorkKind.OTHER,
        description="Category of work performed.",
    )
    summary: str | None = Field(
        default=None,
        description="Short description of what was done.",
    )
    complexity: Complexity | None = Field(
        default=None,
        description="Optional qualitative size (XS–XL).",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form labels for filtering/grouping.",
    )

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, value: list[str]) -> list[str]:
        """Strip, drop empties, and de-duplicate tags while preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for tag in value:
            cleaned = tag.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @property
    def duration(self) -> timedelta:
        """Work amount as a :class:`~datetime.timedelta`."""
        return timedelta(minutes=self.minutes)

    @property
    def hours(self) -> float:
        """Work amount in hours."""
        return self.minutes / 60


class WorkLog(BaseModel):
    """An ordered collection of :class:`WorkEntry` records with aggregations."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    entries: list[WorkEntry] = Field(
        default_factory=list,
        description="Work entries, in insertion order.",
    )

    def add(self, entry: WorkEntry) -> WorkEntry:
        """Append ``entry`` (re-validating the log) and return it."""
        self.entries = [*self.entries, entry]
        return entry

    def log(
        self,
        project: str,
        performed_at: datetime,
        minutes: int,
        *,
        kind: WorkKind = WorkKind.OTHER,
        summary: str | None = None,
        complexity: Complexity | None = None,
        tags: list[str] | None = None,
    ) -> WorkEntry:
        """Construct, append, and return a :class:`WorkEntry` in one call."""
        return self.add(
            WorkEntry(
                project=project,
                performed_at=performed_at,
                minutes=minutes,
                kind=kind,
                summary=summary,
                complexity=complexity,
                tags=tags or [],
            )
        )

    def entries_for(self, project: str) -> list[WorkEntry]:
        """Return entries recorded against ``project``."""
        return [e for e in self.entries if e.project == project]

    def entries_between(self, start: datetime, end: datetime) -> list[WorkEntry]:
        """Return entries whose ``performed_at`` falls within ``[start, end]``."""
        if start > end:
            raise ValueError("start must not be after end")
        return [e for e in self.entries if start <= e.performed_at <= end]

    def total_minutes(self, project: str | None = None) -> int:
        """Total minutes logged, optionally filtered to a single ``project``."""
        source = self.entries if project is None else self.entries_for(project)
        return sum(e.minutes for e in source)

    def total(self, project: str | None = None) -> timedelta:
        """Total effort as a :class:`~datetime.timedelta`."""
        return timedelta(minutes=self.total_minutes(project))

    def minutes_by_project(self) -> dict[str, int]:
        """Map each project name to its total logged minutes."""
        totals: dict[str, int] = defaultdict(int)
        for entry in self.entries:
            totals[entry.project] += entry.minutes
        return dict(totals)

    def minutes_by_kind(self, project: str | None = None) -> dict[WorkKind, int]:
        """Map each work kind to its total minutes, optionally per ``project``."""
        source = self.entries if project is None else self.entries_for(project)
        totals: dict[WorkKind, int] = defaultdict(int)
        for entry in source:
            totals[entry.kind] += entry.minutes
        return dict(totals)

    def busiest_project(self) -> str | None:
        """Project with the most logged minutes, or ``None`` if the log is empty."""
        totals = self.minutes_by_project()
        if not totals:
            return None
        return max(totals, key=lambda name: totals[name])

    def minutes_by_day(self, project: str | None = None) -> dict[str, int]:
        """Map each calendar day (``YYYY-MM-DD``) to its total logged minutes.

        The day is taken from each entry's ``performed_at`` date. Keys are ISO
        date strings so the mapping is JSON-serialisable and sorts naturally.
        Optionally filtered to a single ``project``.
        """
        source = self.entries if project is None else self.entries_for(project)
        totals: dict[str, int] = defaultdict(int)
        for entry in source:
            totals[entry.performed_at.date().isoformat()] += entry.minutes
        return dict(totals)

    def active_days(self) -> int:
        """Number of distinct calendar days that carry at least one entry."""
        return len(self.minutes_by_day())

    def busiest_day(self) -> str | None:
        """ISO date with the most logged minutes, or ``None`` if empty."""
        totals = self.minutes_by_day()
        if not totals:
            return None
        return max(totals, key=lambda day: totals[day])
