from pathlib import Path

from core.night_shift.engine import LocalJournalWorkflowEngine
from core.night_shift.runtime_pilot import run_restart_pilot


def test_local_journal_runtime_survives_restart(tmp_path: Path) -> None:
    db = tmp_path / "pilot.db"
    result = run_restart_pilot(lambda: LocalJournalWorkflowEngine(db))
    assert result.passed


def test_local_journal_releases_database_after_restart_pilot() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "pilot-cleanup.db"
        result = run_restart_pilot(lambda: LocalJournalWorkflowEngine(db))
        assert result.passed
    assert not db.exists()
