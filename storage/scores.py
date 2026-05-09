"""CRUD operations for the eval_scores table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from storage.db import get_connection


@dataclass
class EvalScore:
    id: int
    commit_id: str
    metric: str
    value: float
    n_cases: int
    created_at: str


def _row_to_score(row) -> EvalScore:
    return EvalScore(
        id=row["id"],
        commit_id=row["commit_id"],
        metric=row["metric"],
        value=row["value"],
        n_cases=row["n_cases"],
        created_at=row["created_at"],
    )


def insert_score(
    *,
    commit_id: str,
    metric: str,
    value: float,
    n_cases: int,
    db_path: Path,
) -> EvalScore:
    """Insert a single eval score and return it."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO eval_scores (commit_id, metric, value, n_cases)
            VALUES (?, ?, ?, ?)
            """,
            (commit_id, metric, value, n_cases),
        )
        row_id = cursor.lastrowid
        conn.commit()
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM eval_scores WHERE id = ?", (row_id,)).fetchone()
    return _row_to_score(row)


def get_scores(*, commit_id: str, db_path: Path) -> list[EvalScore]:
    """Return all eval scores for a given commit."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM eval_scores WHERE commit_id = ? ORDER BY metric",
            (commit_id,),
        ).fetchall()
    return [_row_to_score(r) for r in rows]


def get_scores_dict(*, commit_id: str, db_path: Path) -> dict[str, float]:
    """Return scores as a {metric: value} dict for easy comparison."""
    return {s.metric: s.value for s in get_scores(commit_id=commit_id, db_path=db_path)}


def get_score_history(
    *,
    prompt_id: str,
    branch: str = "main",
    metric: str,
    db_path: Path,
) -> list[dict]:
    """
    Return score history for a metric on a branch, oldest first.
    Each entry: {commit_id, short_id, message, value, created_at}
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                c.id        AS commit_id,
                substr(c.id, 1, 7) AS short_id,
                c.message,
                es.value,
                c.created_at
            FROM eval_scores es
            JOIN commits c ON c.id = es.commit_id
            WHERE c.prompt_id = ?
              AND c.branch = ?
              AND es.metric = ?
            ORDER BY c.created_at ASC
            """,
            (prompt_id, branch, metric),
        ).fetchall()
    return [dict(r) for r in rows]
