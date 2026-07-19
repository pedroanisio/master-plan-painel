"""Tests for the WorkLog / WorkEntry effort-tracking models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from master_plan.models import Complexity, WorkEntry, WorkKind, WorkLog

UTC = timezone.utc
JAN1 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
JAN2 = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
JAN3 = datetime(2026, 1, 3, 9, 0, tzinfo=UTC)


class TestWorkEntry:
    def test_minimal_entry(self) -> None:
        entry = WorkEntry(project="master-plan-painel", performed_at=JAN1, minutes=90)
        assert entry.kind is WorkKind.OTHER
        assert entry.complexity is None
        assert entry.duration == timedelta(minutes=90)
        assert entry.hours == 1.5

    def test_minutes_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            WorkEntry(project="p", performed_at=JAN1, minutes=0)

    def test_project_is_required(self) -> None:
        with pytest.raises(ValidationError):
            WorkEntry(project="", performed_at=JAN1, minutes=30)

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkEntry(project="p", performed_at=JAN1, minutes=30, hours=1)  # type: ignore[call-arg]

    def test_tags_are_stripped_and_deduped(self) -> None:
        entry = WorkEntry(
            project="p", performed_at=JAN1, minutes=30, tags=[" api ", "api", ""],
        )
        assert entry.tags == ["api"]

    def test_complexity_accepts_scale(self) -> None:
        entry = WorkEntry(
            project="p", performed_at=JAN1, minutes=30, complexity=Complexity.L,
        )
        assert entry.complexity is Complexity.L


class TestWorkLog:
    def _log(self) -> WorkLog:
        log = WorkLog()
        log.log("alpha", JAN1, 60, kind=WorkKind.FEATURE)
        log.log("alpha", JAN2, 30, kind=WorkKind.BUGFIX)
        log.log("beta", JAN3, 120, kind=WorkKind.FEATURE)
        return log

    def test_empty_log(self) -> None:
        log = WorkLog()
        assert log.total_minutes() == 0
        assert log.busiest_project() is None
        assert log.minutes_by_project() == {}

    def test_add_and_log_append(self) -> None:
        log = WorkLog()
        entry = log.log("alpha", JAN1, 45)
        assert log.entries == [entry]

    def test_total_minutes_overall_and_per_project(self) -> None:
        log = self._log()
        assert log.total_minutes() == 210
        assert log.total_minutes("alpha") == 90
        assert log.total_minutes("beta") == 120

    def test_total_returns_timedelta(self) -> None:
        assert self._log().total("alpha") == timedelta(hours=1, minutes=30)

    def test_minutes_by_project(self) -> None:
        assert self._log().minutes_by_project() == {"alpha": 90, "beta": 120}

    def test_minutes_by_kind_filtered(self) -> None:
        log = self._log()
        assert log.minutes_by_kind("alpha") == {
            WorkKind.FEATURE: 60,
            WorkKind.BUGFIX: 30,
        }

    def test_busiest_project(self) -> None:
        assert self._log().busiest_project() == "beta"

    def test_minutes_by_day(self) -> None:
        assert self._log().minutes_by_day() == {
            "2026-01-01": 60,
            "2026-01-02": 30,
            "2026-01-03": 120,
        }

    def test_minutes_by_day_filtered_by_project(self) -> None:
        assert self._log().minutes_by_day("alpha") == {
            "2026-01-01": 60,
            "2026-01-02": 30,
        }

    def test_minutes_by_day_sums_same_day(self) -> None:
        log = WorkLog()
        log.log("alpha", JAN1, 20)
        log.log("alpha", datetime(2026, 1, 1, 18, 0, tzinfo=UTC), 25)
        assert log.minutes_by_day() == {"2026-01-01": 45}

    def test_entries_for(self) -> None:
        assert len(self._log().entries_for("alpha")) == 2

    def test_entries_between_is_inclusive(self) -> None:
        log = self._log()
        window = log.entries_between(JAN1, JAN2)
        assert [e.project for e in window] == ["alpha", "alpha"]

    def test_entries_between_rejects_reversed_range(self) -> None:
        with pytest.raises(ValueError, match="start must not be after end"):
            self._log().entries_between(JAN3, JAN1)

    def test_round_trips_through_json(self) -> None:
        log = self._log()
        restored = WorkLog.model_validate_json(log.model_dump_json())
        assert restored == log
