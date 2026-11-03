"""Scoped Windows SQLite handle-closure tests for metadata-only ROS outbox.

These tests create only synthetic temporary databases and never contact Hermes
Kanban or any remote API.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.integrations import ros_outbox as outbox


class TestOutboxWindowsResourceClosure(unittest.TestCase):
    def _exercise(self, action: str) -> None:
        root = Path(tempfile.mkdtemp(prefix="lukart-outbox-isolated-"))
        db_path = root / "outbox.sqlite3"
        try:
            if action == "drain":
                summary = outbox.drain(
                    hermes_cli="unused-with-no-events", db_path=db_path, limit=1
                )
                self.assertEqual(summary["pending"], 0)
            elif action == "requeue_failed":
                self.assertEqual(outbox.requeue_failed(db_path=db_path), 0)
            elif action == "status":
                self.assertEqual(outbox.status(db_path=db_path), {})
            else:
                raise ValueError(action)
            # No gc.collect: Windows must permit immediate WAL file deletion.
            shutil.rmtree(root)
            self.assertFalse(root.exists())
        finally:
            if root.exists():
                shutil.rmtree(root)

    def test_drain_closes_database(self) -> None:
        self._exercise("drain")

    def test_requeue_failed_closes_database(self) -> None:
        self._exercise("requeue_failed")

    def test_status_closes_database(self) -> None:
        self._exercise("status")


if __name__ == "__main__":
    unittest.main()