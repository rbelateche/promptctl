"""SQLite connection and schema migrations for promptctl."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path(".promptctl/db.sqlite")

# DDL statements executed in order on every startup (idempotent).
_MIGRATIONS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS commits (
        id          TEXT PRIMARY KEY,
        prompt_id   TEXT NOT NULL,
        branch      TEXT NOT NULL DEFAULT 'main',
        content     TEXT NOT NULL,
        message     TEXT NOT NULL,
        model       TEXT NOT NULL,
        parent_id   TEXT REFERENCES commits(id),
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_scores (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        commit_id   TEXT NOT NULL REFERENCES commits(id),
        metric      TEXT NOT NULL,
        value       REAL NOT NULL,
        n_cases     INTEGER NOT NULL,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS test_cases (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id   TEXT NOT NULL,
        input       TEXT NOT NULL,
        expected    TEXT NOT NULL,
        tags        TEXT,
        active      BOOLEAN DEFAULT TRUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS branches (
        name        TEXT NOT NULL,
        prompt_id   TEXT NOT NULL,
        head_id     TEXT REFERENCES commits(id),
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (name, prompt_id)
    )
    """,
    # Indexes for common query patterns
    "CREATE INDEX IF NOT EXISTS idx_commits_prompt_branch ON commits(prompt_id, branch)",
    "CREATE INDEX IF NOT EXISTS idx_scores_commit ON eval_scores(commit_id)",
    "CREATE INDEX IF NOT EXISTS idx_test_cases_prompt ON test_cases(prompt_id)",
]


def get_connection(db_path: Path | str = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with foreign keys enforced and row factory set."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path | str = _DEFAULT_DB_PATH) -> None:
    """Run all schema migrations. Safe to call multiple times (idempotent)."""
    with get_connection(db_path) as conn:
        for statement in _MIGRATIONS:
            conn.execute(statement)
        conn.commit()
