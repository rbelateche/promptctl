"""CRUD operations for the branches table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from storage.db import get_connection


@dataclass
class Branch:
    name: str
    prompt_id: str
    head_id: Optional[str]
    created_at: str


def _row_to_branch(row) -> Branch:
    return Branch(
        name=row["name"],
        prompt_id=row["prompt_id"],
        head_id=row["head_id"],
        created_at=row["created_at"],
    )


def create_branch(
    *,
    name: str,
    prompt_id: str,
    head_id: Optional[str] = None,
    db_path: Path,
) -> Branch:
    """Create a new branch. Raises ValueError if it already exists."""
    with get_connection(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO branches (name, prompt_id, head_id)
                VALUES (?, ?, ?)
                """,
                (name, prompt_id, head_id),
            )
            conn.commit()
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError(
                    f"Branch {name!r} already exists for prompt {prompt_id!r}"
                ) from exc
            raise
    return get_branch(name=name, prompt_id=prompt_id, db_path=db_path)


def get_branch(*, name: str, prompt_id: str, db_path: Path) -> Branch:
    """Fetch a branch by name and prompt_id. Raises KeyError if not found."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM branches WHERE name = ? AND prompt_id = ?",
            (name, prompt_id),
        ).fetchone()
    if row is None:
        raise KeyError(f"Branch {name!r} not found for prompt {prompt_id!r}")
    return _row_to_branch(row)


def list_branches(*, prompt_id: str, db_path: Path) -> list[Branch]:
    """List all branches for a prompt, ordered by creation time."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM branches WHERE prompt_id = ? ORDER BY created_at",
            (prompt_id,),
        ).fetchall()
    return [_row_to_branch(r) for r in rows]


def update_head(*, name: str, prompt_id: str, head_id: str, db_path: Path) -> Branch:
    """Update the head commit pointer of a branch. Raises KeyError if branch not found."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE branches SET head_id = ? WHERE name = ? AND prompt_id = ?",
            (head_id, name, prompt_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Branch {name!r} not found for prompt {prompt_id!r}")
    return get_branch(name=name, prompt_id=prompt_id, db_path=db_path)


def ensure_branch(
    *,
    name: str,
    prompt_id: str,
    db_path: Path,
) -> Branch:
    """Return an existing branch or create it if it doesn't exist."""
    try:
        return get_branch(name=name, prompt_id=prompt_id, db_path=db_path)
    except KeyError:
        return create_branch(name=name, prompt_id=prompt_id, db_path=db_path)
