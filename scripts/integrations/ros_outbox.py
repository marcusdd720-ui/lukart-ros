"""LUKART ROS -> Hermes Kanban durable event outbox (stdlib, local-only).

This module is not a new authority for ROS tasks. Call `enqueue_task` only
AFTER the existing ROS task's authoritative transaction has committed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import uuid

EVENT_TYPE = "lukart.ros.task.created"
BOARD = "lukart-hermes-os"
ASSIGNEE = "lukart-hermes-ops"
MAX_ATTEMPTS = 8
LEASE_SECONDS = 90
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,80}\Z", re.ASCII)
SCHEMA_VERSION = 1


def default_db_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA not set; Windows local installation required")
    return Path(local) / "LUKART" / "ROS-Hermes-Outbox" / "outbox.sqlite3"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA busy_timeout=5000")
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA synchronous=FULL")
    try:
        version = cx.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            raise RuntimeError("Outbox schema version unknown; fail closed")
        if version == 0:
            cx.execute("BEGIN IMMEDIATE")
            try:
                cx.execute("""CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    ref_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','leased','delivered','failed')),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                    created_at INTEGER NOT NULL,
                    next_at INTEGER NOT NULL,
                    lease_token TEXT,
                    lease_until INTEGER,
                    delivered_at INTEGER,
                    last_error TEXT,
                    UNIQUE (event_type, ref_hash)
                )""")
                cx.execute("CREATE INDEX IF NOT EXISTS idx_due ON events(status,next_at,lease_until)")
                cx.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                cx.commit()
            except BaseException:
                cx.rollback()
                raise
    except BaseException:
        cx.close()
        raise
    return cx


def event_key(task_id: str) -> str:
    if not isinstance(task_id, str) or not ID_PATTERN.fullmatch(task_id):
        raise ValueError("Task ID must be an opaque 1-80 character token [A-Za-z0-9_-]")
    # Do not store raw ROS task ID (or case IDs, paths, documents) in this outbox.
    return hashlib.sha256((EVENT_TYPE + "\x00" + task_id).encode("ascii")).hexdigest()


def enqueue_task(task_id: str, *, db_path: Path | None = None) -> bool:
    """Store a metadata-only event; return False if already queued/delivered.

    IMPORTANT: calling this independently after ROS commit leaves a small
    commit->enqueue crash window. Native transactional integration is required
    for an atomic producer outbox once a real ROS task storage is identified.
    """
    key = event_key(task_id)
    # FIX-002: explicit open/close instead of `with connect() as cx`.
    # sqlite3.Connection.__exit__ calls commit/rollback but NOT close().
    # On Windows with WAL mode the file handle stays open until GC,
    # causing PermissionError when callers delete the directory afterwards
    # (e.g. unittest TemporaryDirectory teardown, WinError 32).
    cx = connect(db_path)
    try:
        cx.execute("BEGIN IMMEDIATE")
        try:
            now = int(time.time())  # transaction timestamps AFTER acquiring lock
            cursor = cx.execute(
                """INSERT OR IGNORE INTO events
                   (event_id,event_type,ref_hash,status,created_at,next_at)
                   VALUES (?,?,?,'pending',?,?)""",
                (key, EVENT_TYPE, key, now, now),
            )
            cx.commit()
            return cursor.rowcount == 1
        except BaseException:
            cx.rollback()
            raise
    finally:
        cx.close()


def claim_due(cx: sqlite3.Connection, *, now: int | None = None):
    cx.execute("BEGIN IMMEDIATE")
    try:
        ts = int(time.time()) if now is None else now
        # KIRO-ROS-FIX-001: exhausted due rows must NEVER receive attempt 9.
        # Update all exhausted due entries atomically before selecting work,
        # so a healthy event behind them cannot be starved.
        cx.execute(
            """UPDATE events SET status='failed', lease_token=NULL, lease_until=NULL
               WHERE attempts >= ? AND status NOT IN ('delivered', 'failed')
                 AND (
                       (status='pending' AND next_at <= ?)
                    OR (status='leased' AND lease_until <= ?)
                 )""",
            (MAX_ATTEMPTS, ts, ts),
        )
        row = cx.execute(
            """SELECT * FROM events WHERE
                 (status='pending' AND next_at <= ?)
              OR (status='leased' AND lease_until <= ?)
                ORDER BY created_at, event_id LIMIT 1""", (ts, ts)
        ).fetchone()
        result = None
        if row is not None:
            token = uuid.uuid4().hex
            cx.execute(
                """UPDATE events SET status='leased', lease_token=?, lease_until=?,
                   attempts=attempts+1 WHERE event_id=?""",
                (token, ts + LEASE_SECONDS, row["event_id"]),
            )
            result = dict(row), token
        cx.commit()
        return result
    except BaseException:
        cx.rollback()
        raise


def finish(cx, event_id: str, token: str, *, ok: bool, error_code: str = "", now: int | None = None):
    cx.execute("BEGIN IMMEDIATE")
    try:
        ts = int(time.time()) if now is None else now
        row = cx.execute("SELECT attempts FROM events WHERE event_id=? AND lease_token=? AND status='leased'", (event_id, token)).fetchone()
        if row is None:
            cx.commit()
            return False  # Lost lease or stale worker; fail closed.
        if ok:
            cx.execute("""UPDATE events SET status='delivered',delivered_at=?,
               lease_token=NULL, lease_until=NULL, last_error=NULL
               WHERE event_id=? AND lease_token=?""", (ts, event_id, token))
        else:
            attempts = row["attempts"]
            final = attempts >= MAX_ATTEMPTS
            delay = min(3600, 10 * (2 ** min(attempts, 8)))
            # Store only bounded constant error codes, not subprocess stdout/stderr.
            reason = error_code if error_code in {"CLI_UNAVAILABLE","CLI_FAILURE","CLI_TIMEOUT","DB_ERROR"} else "CLI_FAILURE"
            cx.execute("""UPDATE events SET status=?,next_at=?,
               lease_token=NULL,lease_until=NULL,last_error=?
               WHERE event_id=? AND lease_token=?""",
               ("failed" if final else "pending", ts + delay, reason, event_id, token))
        cx.commit()
        return True
    except BaseException:
        cx.rollback()
        raise


def create_kanban_card(event_id: str, hermes_cli: str) -> tuple[bool, str]:
    if not hermes_cli or not Path(hermes_cli).is_file():
        return False, "CLI_UNAVAILABLE"
    # Project-safe, generic notice. No real case content or identifiers.
    label = event_id[:14]
    cmd = [hermes_cli, "kanban", "--board", BOARD, "create", f"ROS task notification [{label}]",
           "--assignee", ASSIGNEE, "--workspace", "scratch", "--initial-status", "blocked",
           "--idempotency-key", f"lukart-ros-outbox-{event_id[:32]}",
           "--max-runtime", "5m", "--max-retries", "1",
           "--body", "Local ROS task notification (opaque reference only). Human review required. "
                     "No case data. Do not execute LEGAL OS or Generator Pism. No paid APIs."]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=20, check=False)
    except (OSError, ValueError):
        return False, "CLI_UNAVAILABLE"
    except subprocess.TimeoutExpired:
        return False, "CLI_TIMEOUT"
    return (True, "") if result.returncode == 0 else (False, "CLI_FAILURE")


def drain(*, hermes_cli: str, db_path: Path | None = None, limit: int = 5) -> dict:
    summary = {"delivered": 0, "retried": 0, "pending": 0, "failed": 0}
    cx = connect(db_path)
    try:
            for _ in range(max(0, min(limit, 5))):
                claimed = claim_due(cx)
                if claimed is None:
                    break
                row, token = claimed
                ok, code = create_kanban_card(row["event_id"], hermes_cli)
                # Claim loss can occur after a slow CLI operation; key provides best-effort dedupe.
                if finish(cx, row["event_id"], token, ok=ok, error_code=code):
                    summary["delivered" if ok else "retried"] += 1
            summary["pending"] = cx.execute("SELECT COUNT(*) FROM events WHERE status IN ('pending','leased')").fetchone()[0]
            summary["failed"] = cx.execute("SELECT COUNT(*) FROM events WHERE status='failed'").fetchone()[0]
    finally:
        cx.close()
    return summary


def requeue_failed(*, db_path: Path | None = None) -> int:
    """Operator-controlled recovery after diagnosing a permanent failure."""
    cx = connect(db_path)
    try:
            cx.execute("BEGIN IMMEDIATE")
            try:
                now = int(time.time())
                cur = cx.execute("""UPDATE events SET status='pending', attempts=0, next_at=?,
                                  lease_token=NULL, lease_until=NULL, last_error=NULL
                                  WHERE status='failed'""", (now,))
                cx.commit()
                return cur.rowcount
            except BaseException:
                cx.rollback()
                raise
    finally:
        cx.close()


def status(*, db_path: Path | None = None) -> dict:
    cx = connect(db_path)
    try:
            items = cx.execute("SELECT status,COUNT(*) AS n FROM events GROUP BY status").fetchall()
    finally:
        cx.close()
    return {k:v for k,v in ((r["status"],r["n"]) for r in items)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="LUKART ROS durable local Kanban outbox")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enqueue", metavar="OPAQUE_TASK_ID", help="queue metadata only; call after ROS commit")
    group.add_argument("--drain", action="store_true", help="deliver <=5 queued events to blocked Kanban cards")
    group.add_argument("--status", action="store_true", help="show only counts, no identifiers")
    group.add_argument("--requeue-failed", action="store_true", help="manual recovery after fixing the cause")
    parser.add_argument("--hermes-cli", help="absolute path to hermes executable, required for --drain")
    args = parser.parse_args(argv)
    try:
        if args.enqueue:
            print("QUEUED" if enqueue_task(args.enqueue) else "EXISTS")
        elif args.requeue_failed:
            print(f"REQUEUED={requeue_failed()}")
        elif args.drain:
            if not args.hermes_cli:
                parser.error("--drain requires --hermes-cli")
            print(" ".join(f"{k}={v}" for k,v in drain(hermes_cli=args.hermes_cli).items()))
        else:
            print(" ".join(f"{k}={v}" for k,v in status().items()) or "EMPTY")
        return 0
    except (sqlite3.Error, RuntimeError, ValueError, OSError) as exc:
        print("ERROR - Outbox action failed: " + type(exc).__name__, file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
