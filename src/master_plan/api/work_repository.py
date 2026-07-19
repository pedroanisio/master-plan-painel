"""JSON-file-backed repository for work-log entries.

Mirrors :class:`~master_plan.api.repository.ProjectRepository`: the whole log
is held in memory and rewritten to a JSON file on every mutation. Records are
keyed by an opaque server-assigned id.

Aggregation is delegated to the domain :class:`~master_plan.models.work_log.WorkLog`
model so the API and library share one source of truth for totals.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from master_plan.api._io import atomic_write_text
from master_plan.api.work_schemas import WorkEntryRecord, WorkReport, WorkSummary
from master_plan.models.work_log import WorkEntry, WorkLog

__all__ = ["WorkLogRepository"]


class WorkLogRepository:
    """In-memory work log persisted to a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._records: dict[str, WorkEntryRecord] = {}
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8") or "[]")
        migrated = False
        for item in raw:
            # owner_id became required with resource ownership; back-fill legacy
            # entries with an empty owner (orphaned, invisible to real users).
            if not isinstance(item.get("owner_id"), str):
                item["owner_id"] = ""
                migrated = True
        self._records = {
            item["id"]: WorkEntryRecord.model_validate(item) for item in raw
        }
        if migrated:
            self._persist()

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self._records.values()]
        atomic_write_text(
            self._path, json.dumps(payload, indent=2, ensure_ascii=False)
        )

    # -- queries -----------------------------------------------------------
    # Every query and mutation is scoped to an ``owner_id``: a user only ever
    # sees and touches their own work entries and totals.
    def list(
        self, owner_id: str, project: str | None = None
    ) -> list[WorkEntryRecord]:
        """Return the owner's entries, newest first, optionally by project."""
        records = [
            r for r in self._records.values()
            if r.owner_id == owner_id and (project is None or r.project == project)
        ]
        return sorted(records, key=lambda r: r.performed_at, reverse=True)

    def get(self, entry_id: str, owner_id: str) -> WorkEntryRecord | None:
        """Return the owner's record with ``entry_id``, or ``None``."""
        record = self._records.get(entry_id)
        if record is None or record.owner_id != owner_id:
            return None
        return record

    def as_work_log(self, owner_id: str) -> WorkLog:
        """Build a domain :class:`WorkLog` from the owner's stored entries."""
        return WorkLog(
            entries=[
                r.to_entry() for r in self._records.values()
                if r.owner_id == owner_id
            ]
        )

    def summary(self, owner_id: str) -> WorkSummary:
        """Aggregate totals across the owner's log."""
        log = self.as_work_log(owner_id)
        return WorkSummary(
            total_minutes=log.total_minutes(),
            by_project=log.minutes_by_project(),
            busiest_project=log.busiest_project(),
            by_day=log.minutes_by_day(),
        )

    def report(
        self,
        owner_id: str,
        *,
        now: datetime,
        days: int | None = None,
        project: str | None = None,
    ) -> WorkReport:
        """Build a full effort report for the owner over a rolling window.

        ``days`` selects a "last N days" window ending on ``now``'s date
        (inclusive); ``None`` reports all-time. ``project`` optionally scopes
        the whole report to a single project. Aggregation is delegated to the
        domain :class:`WorkLog` so the API and library agree on every number.
        """
        today = now.date()
        from_date = today - timedelta(days=days - 1) if days else None

        def in_scope(entry: WorkEntry) -> bool:
            d = entry.performed_at.date()
            if d > today:  # future-dated entries fall outside any window
                return False
            if from_date is not None and d < from_date:
                return False
            return project is None or entry.project == project

        window = WorkLog(
            entries=[
                r.to_entry()
                for r in self._records.values()
                if r.owner_id == owner_id and in_scope(r.to_entry())
            ]
        )
        total = window.total_minutes()
        active = window.active_days()
        return WorkReport(
            days=days,
            from_date=from_date.isoformat() if from_date else None,
            to_date=today.isoformat(),
            project=project,
            total_minutes=total,
            entry_count=len(window.entries),
            active_days=active,
            avg_minutes_per_active_day=round(total / active, 1) if active else 0.0,
            by_project=window.minutes_by_project(),
            by_kind={k.value: v for k, v in window.minutes_by_kind().items()},
            by_day=window.minutes_by_day(),
            busiest_project=window.busiest_project(),
            busiest_day=window.busiest_day(),
        )

    # -- mutations ---------------------------------------------------------
    def create(self, entry: WorkEntry, owner_id: str) -> WorkEntryRecord:
        """Persist a new work entry owned by ``owner_id``."""
        entry_id = uuid.uuid4().hex
        record = WorkEntryRecord.from_entry(entry_id, entry, owner_id=owner_id)
        self._records[entry_id] = record
        self._persist()
        return record

    def replace(
        self, entry_id: str, entry: WorkEntry, owner_id: str
    ) -> WorkEntryRecord | None:
        """Replace the owner's entry; return ``None`` if missing/not owned."""
        existing = self._records.get(entry_id)
        if existing is None or existing.owner_id != owner_id:
            return None
        record = WorkEntryRecord.from_entry(entry_id, entry, owner_id=owner_id)
        self._records[entry_id] = record
        self._persist()
        return record

    def delete(self, entry_id: str, owner_id: str) -> bool:
        """Delete the owner's record; return ``True`` if something was removed."""
        existing = self._records.get(entry_id)
        if existing is None or existing.owner_id != owner_id:
            return False
        del self._records[entry_id]
        self._persist()
        return True
