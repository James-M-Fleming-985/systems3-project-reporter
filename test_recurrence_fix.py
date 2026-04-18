"""
Tests for recurring task date generation and YAML round-trip integrity.
Covers: standalone_task_repository.create(), _ensure_date_str(), YAML save/load.
"""
import tempfile
import shutil
from pathlib import Path
from datetime import date, datetime

import yaml
import pytest

from repositories.standalone_task_repository import (
    StandaloneTaskRepository,
    _ensure_date_str,
)


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temporary storage dir and clean up after."""
    yield tmp_path


def _make_repo(storage_dir: Path) -> StandaloneTaskRepository:
    return StandaloneTaskRepository(storage_dir=storage_dir)


# ── _ensure_date_str tests ──────────────────────────────────────────────


class TestEnsureDateStr:
    def test_plain_string(self):
        assert _ensure_date_str("2026-04-30") == "2026-04-30"

    def test_string_with_time(self):
        assert _ensure_date_str("2026-04-30T14:30:00") == "2026-04-30"

    def test_datetime_date(self):
        assert _ensure_date_str(date(2026, 4, 30)) == "2026-04-30"

    def test_datetime_datetime(self):
        assert _ensure_date_str(datetime(2026, 4, 30, 14, 30)) == "2026-04-30"

    def test_empty(self):
        assert _ensure_date_str("") == ""
        assert _ensure_date_str(None) == ""


# ── Recurrence date generation ──────────────────────────────────────────


class TestRecurrenceDates:
    """Verify that recurring tasks get distinct, correctly offset dates."""

    def test_monthly_12_occurrences(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Monthly Review", "due_date": "2026-04-30"},
            recurrence_cadence="monthly",
            recurrence_count=12,
        )
        assert len(tasks) == 12
        dates = [t["due_date"] for t in tasks]
        expected = [
            "2026-04-30",
            "2026-05-30",
            "2026-06-30",
            "2026-07-30",
            "2026-08-30",
            "2026-09-30",
            "2026-10-30",
            "2026-11-30",
            "2026-12-30",
            "2027-01-30",
            "2027-02-28",  # Feb clamped
            "2027-03-30",
        ]
        assert dates == expected

    def test_monthly_year_boundary(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Year boundary", "due_date": "2026-11-15"},
            recurrence_cadence="monthly",
            recurrence_count=6,
        )
        dates = [t["due_date"] for t in tasks]
        expected = [
            "2026-11-15",
            "2026-12-15",
            "2027-01-15",
            "2027-02-15",
            "2027-03-15",
            "2027-04-15",
        ]
        assert dates == expected

    def test_monthly_31st_clamping(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "31st clamp", "due_date": "2026-01-31"},
            recurrence_cadence="monthly",
            recurrence_count=4,
        )
        dates = [t["due_date"] for t in tasks]
        expected = [
            "2026-01-31",
            "2026-02-28",  # Feb non-leap
            "2026-03-31",
            "2026-04-30",  # Apr has 30 days
        ]
        assert dates == expected

    def test_weekly_4_occurrences(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Weekly", "due_date": "2026-04-06"},
            recurrence_cadence="weekly",
            recurrence_count=4,
        )
        dates = [t["due_date"] for t in tasks]
        expected = ["2026-04-06", "2026-04-13", "2026-04-20", "2026-04-27"]
        assert dates == expected

    def test_daily_5_occurrences(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Daily", "due_date": "2026-04-28"},
            recurrence_cadence="daily",
            recurrence_count=5,
        )
        dates = [t["due_date"] for t in tasks]
        expected = [
            "2026-04-28", "2026-04-29", "2026-04-30", "2026-05-01", "2026-05-02",
        ]
        assert dates == expected

    def test_biweekly_3_occurrences(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Biweekly", "due_date": "2026-04-01"},
            recurrence_cadence="biweekly",
            recurrence_count=3,
        )
        dates = [t["due_date"] for t in tasks]
        expected = ["2026-04-01", "2026-04-15", "2026-04-29"]
        assert dates == expected

    def test_start_date_offset(self, tmp_storage):
        """start_date should be shifted by the same delta as due_date."""
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={
                "title": "With start",
                "due_date": "2026-04-30",
                "start_date": "2026-04-25",
            },
            recurrence_cadence="monthly",
            recurrence_count=3,
        )
        starts = [t["start_date"] for t in tasks]
        dues = [t["due_date"] for t in tasks]
        assert dues == ["2026-04-30", "2026-05-30", "2026-06-30"]
        assert starts == ["2026-04-25", "2026-05-25", "2026-06-25"]

    def test_no_recurrence_single_task(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "One-off", "due_date": "2026-04-30"},
        )
        assert len(tasks) == 1
        assert tasks[0]["due_date"] == "2026-04-30"

    def test_all_dates_unique(self, tmp_storage):
        """All due dates in a recurring series must be distinct."""
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Unique dates", "due_date": "2026-04-30"},
            recurrence_cadence="monthly",
            recurrence_count=12,
        )
        dates = [t["due_date"] for t in tasks]
        assert len(dates) == len(set(dates)), f"Duplicate dates found: {dates}"

    def test_series_metadata(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        tasks = repo.create(
            user_id="test-user",
            task_data={"title": "Series", "due_date": "2026-04-30"},
            recurrence_cadence="monthly",
            recurrence_count=3,
        )
        series_ids = {t["recurrence_series_id"] for t in tasks}
        assert len(series_ids) == 1  # all share one series_id
        occurrences = [t["recurrence_occurrence"] for t in tasks]
        assert occurrences == ["1 of 3", "2 of 3", "3 of 3"]


# ── YAML round-trip integrity ───────────────────────────────────────────


class TestYamlRoundTrip:
    """Verify dates survive save → load as strings, not datetime.date objects."""

    def test_dates_are_strings_after_roundtrip(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        repo.create(
            user_id="test-user",
            task_data={"title": "Roundtrip", "due_date": "2026-04-30"},
            recurrence_cadence="monthly",
            recurrence_count=3,
        )
        # Reload from YAML
        tasks = repo.get_all("test-user")
        for task in tasks:
            due = task.get("due_date")
            start = task.get("start_date")
            assert isinstance(due, str), f"due_date is {type(due)}, expected str"
            if start:
                assert isinstance(start, str), f"start_date is {type(start)}, expected str"

    def test_roundtrip_preserves_distinct_dates(self, tmp_storage):
        repo = _make_repo(tmp_storage)
        repo.create(
            user_id="test-user",
            task_data={"title": "Persist check", "due_date": "2026-04-30"},
            recurrence_cadence="monthly",
            recurrence_count=12,
        )
        tasks = repo.get_all("test-user")
        dates = [t["due_date"] for t in tasks]
        # Convert any datetime.date objects to strings for comparison
        dates_str = [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in dates]
        assert len(set(dates_str)) == 12, f"Expected 12 distinct dates, got: {dates_str}"

    def test_raw_yaml_has_quoted_dates(self, tmp_storage):
        """Verify that yaml.safe_dump writes dates as strings, not bare dates."""
        repo = _make_repo(tmp_storage)
        repo.create(
            user_id="test-user",
            task_data={"title": "Quote check", "due_date": "2026-04-30"},
        )
        yaml_path = tmp_storage / "users" / "test-user" / "standalone_tasks.yaml"
        raw = yaml_path.read_text()
        # yaml.safe_dump writes strings with quotes when they look like dates
        # Re-parse and verify
        data = yaml.safe_load(raw)
        task = data["tasks"][0]
        assert isinstance(task["due_date"], str), (
            f"YAML round-trip produced {type(task['due_date'])} instead of str"
        )


# ── Self-healing repair ─────────────────────────────────────────────────


class TestSelfHealingRepair:
    """Verify that get_all() auto-repairs broken recurrence series."""

    def _write_broken_series(self, storage_dir, user_id, count=12, cadence="monthly"):
        """Write a YAML file with all tasks on the same date (the bug)."""
        user_dir = storage_dir / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        broken = {
            "tasks": [
                {
                    "id": f"task-{i}",
                    "title": f"Review ({i+1}/{count})",
                    "due_date": "2026-04-30",
                    "start_date": "2026-04-25",
                    "status": "NOT_STARTED",
                    "recurrence_cadence": cadence,
                    "recurrence_series_id": "broken-series-1",
                    "recurrence_occurrence": f"{i+1} of {count}",
                }
                for i in range(count)
            ],
        }
        with open(user_dir / "standalone_tasks.yaml", "w") as f:
            yaml.dump(broken, f, default_flow_style=False)

    def test_get_all_repairs_broken_monthly(self, tmp_storage):
        StandaloneTaskRepository._repaired_users.clear()
        self._write_broken_series(tmp_storage, "u1", count=12, cadence="monthly")
        repo = _make_repo(tmp_storage)
        tasks = repo.get_all("u1")
        dates = [t["due_date"] for t in tasks]
        assert len(set(dates)) == 12, f"Expected 12 unique dates, got: {dates}"
        assert dates[0] == "2026-04-30"
        assert dates[1] == "2026-05-30"
        assert dates[-1] == "2027-03-30"

    def test_repair_persists_to_yaml(self, tmp_storage):
        StandaloneTaskRepository._repaired_users.clear()
        self._write_broken_series(tmp_storage, "u2", count=3)
        repo = _make_repo(tmp_storage)
        repo.get_all("u2")
        # Reload from a fresh repo instance (simulating server restart)
        StandaloneTaskRepository._repaired_users.clear()
        repo2 = _make_repo(tmp_storage)
        tasks = repo2.get_all("u2")
        dates = [t["due_date"] for t in tasks]
        assert len(set(dates)) == 3

    def test_skips_already_correct_series(self, tmp_storage):
        StandaloneTaskRepository._repaired_users.clear()
        repo = _make_repo(tmp_storage)
        repo.create(
            user_id="u3",
            task_data={"title": "Good series", "due_date": "2026-04-30"},
            recurrence_cadence="monthly",
            recurrence_count=4,
        )
        # Clear flag so repair runs again
        StandaloneTaskRepository._repaired_users.clear()
        tasks = repo.get_all("u3")
        dates = [t["due_date"] for t in tasks]
        # Should still be correct (not mangled by unnecessary repair)
        assert dates == ["2026-04-30", "2026-05-30", "2026-06-30", "2026-07-30"]

    def test_repair_only_runs_once_per_user(self, tmp_storage):
        StandaloneTaskRepository._repaired_users.clear()
        self._write_broken_series(tmp_storage, "u4", count=3)
        repo = _make_repo(tmp_storage)
        repo.get_all("u4")  # First call repairs
        assert "u4" in StandaloneTaskRepository._repaired_users
        # Second call should skip repair (flag already set)
        repo.get_all("u4")  # Should not error or re-repair
