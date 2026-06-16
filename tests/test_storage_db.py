"""Tests for the SQLite schema and connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from storage.db import get_connection, init_db


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    """Calling init_db twice must not raise and must keep the schema intact."""
    path = tmp_path / "db.sqlite"
    init_db(path)
    init_db(path)

    with get_connection(path) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"commits", "eval_scores", "test_cases", "branches"} <= tables


def test_foreign_keys_enforced(db_path: Path) -> None:
    """A score referencing a non-existent commit must violate the FK constraint."""
    with get_connection(db_path) as conn:
        try:
            conn.execute(
                "INSERT INTO eval_scores (commit_id, metric, value, n_cases) "
                "VALUES ('missing', 'accuracy', 1.0, 1)"
            )
            conn.commit()
            raised = False
        except sqlite3.IntegrityError:
            raised = True

    assert raised, "expected a foreign-key IntegrityError"


def test_wal_mode_enabled(db_path: Path) -> None:
    """The connection should run in WAL journal mode."""
    with get_connection(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
