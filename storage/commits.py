"""CRUD operations for the commits table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from storage.db import get_connection


@dataclass
class Commit:
    id: str
    prompt_id: str
    branch: str
    content: str
    message: str
    model: str
    parent_id: Optional[str]
    created_at: str


def _row_to_commit(row) -> Commit:
    return Commit(
        id=row["id"],
        prompt_id=row["prompt_id"],
        branch=row["branch"],
        content=row["content"],
        message=row["message"],
        model=row["model"],
        parent_id=row["parent_id"],
        created_at=row["created_at"],
    )


def insert_commit(
    *,
    id: str,
    prompt_id: str,
    branch: str,
    content: str,
    message: str,
    model: str,
    parent_id: Optional[str],
    db_path: Path,
) -> Commit:
    """Insert a new commit row and return it."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO commits (id, prompt_id, branch, content, message, model, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (id, prompt_id, branch, content, message, model, parent_id),
        )
        conn.commit()
    return get_commit(id=id, db_path=db_path)


def get_commit(*, id: str, db_path: Path) -> Commit:
    """Fetch a single commit by full id. Raises KeyError if not found."""
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM commits WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise KeyError(f"Commit not found: {id!r}")
    return _row_to_commit(row)


def get_commit_by_prefix(*, prefix: str, db_path: Path) -> Commit:
    """Fetch a commit by a short hash prefix. Raises KeyError if none found, ValueError if ambiguous."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM commits WHERE id LIKE ?", (f"{prefix}%",)
        ).fetchall()
    if not rows:
        raise KeyError(f"No commit matching prefix: {prefix!r}")
    if len(rows) > 1:
        raise ValueError(f"Ambiguous prefix {prefix!r} matches {len(rows)} commits")
    return _row_to_commit(rows[0])


def list_commits(
    *,
    prompt_id: str,
    branch: str = "main",
    limit: int = 50,
    db_path: Path,
) -> list[Commit]:
    """List commits for a prompt/branch, newest first."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM commits
            WHERE prompt_id = ? AND branch = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (prompt_id, branch, limit),
        ).fetchall()
    return [_row_to_commit(r) for r in rows]


def get_head(*, prompt_id: str, branch: str = "main", db_path: Path) -> Optional[Commit]:
    """Return the most recent commit on a branch, or None if no commits exist."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.* FROM commits c
            JOIN branches b ON b.head_id = c.id
            WHERE b.prompt_id = ? AND b.name = ?
            """,
            (prompt_id, branch),
        ).fetchone()
    if row is None:
        return None
    return _row_to_commit(row)


def walk_ancestors(*, commit_id: str, steps: int, db_path: Path) -> Commit:
    """Walk up the parent chain `steps` times from `commit_id`. Raises ValueError if chain is shorter."""
    current_id = commit_id
    with get_connection(db_path) as conn:
        for i in range(steps):
            row = conn.execute(
                "SELECT parent_id FROM commits WHERE id = ?", (current_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Commit not found: {current_id!r}")
            if row["parent_id"] is None:
                raise ValueError(
                    f"Cannot walk {steps} steps: chain ends after {i} step(s)"
                )
            current_id = row["parent_id"]
    return get_commit(id=current_id, db_path=db_path)
