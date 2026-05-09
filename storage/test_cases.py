"""CRUD operations for the test_cases table."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from storage.db import get_connection


@dataclass
class TestCase:
    id: int
    prompt_id: str
    input: str
    expected: str
    tags: list[str]
    active: bool


def _row_to_test_case(row) -> TestCase:
    raw_tags = row["tags"]
    tags: list[str] = json.loads(raw_tags) if raw_tags else []
    return TestCase(
        id=row["id"],
        prompt_id=row["prompt_id"],
        input=row["input"],
        expected=row["expected"],
        tags=tags,
        active=bool(row["active"]),
    )


def insert_test_case(
    *,
    prompt_id: str,
    input: str,
    expected: str,
    tags: Optional[list[str]] = None,
    db_path: Path,
) -> TestCase:
    """Insert a test case and return it."""
    tags_json = json.dumps(tags) if tags else None
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO test_cases (prompt_id, input, expected, tags)
            VALUES (?, ?, ?, ?)
            """,
            (prompt_id, input, expected, tags_json),
        )
        row_id = cursor.lastrowid
        conn.commit()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM test_cases WHERE id = ?", (row_id,)
        ).fetchone()
    return _row_to_test_case(row)


def list_test_cases(
    *,
    prompt_id: str,
    active_only: bool = True,
    db_path: Path,
) -> list[TestCase]:
    """List test cases for a prompt, optionally filtering to active only."""
    query = "SELECT * FROM test_cases WHERE prompt_id = ?"
    params: list = [prompt_id]
    if active_only:
        query += " AND active = TRUE"
    query += " ORDER BY id"
    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_test_case(r) for r in rows]


def delete_test_case(*, id: int, db_path: Path) -> None:
    """Hard-delete a test case by id. Raises KeyError if not found."""
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM test_cases WHERE id = ?", (id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Test case not found: {id}")


def toggle_test_case(*, id: int, active: bool, db_path: Path) -> TestCase:
    """Enable or disable a test case without deleting it."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE test_cases SET active = ? WHERE id = ?", (active, id)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Test case not found: {id}")
        row = conn.execute("SELECT * FROM test_cases WHERE id = ?", (id,)).fetchone()
    return _row_to_test_case(row)


def bulk_insert_from_file(*, prompt_id: str, path: Path, db_path: Path) -> list[TestCase]:
    """
    Load test cases from a JSON file and insert them.
    Expected format: list of {input, expected, tags?}.
    """
    raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))
    results: list[TestCase] = []
    for item in raw:
        tc = insert_test_case(
            prompt_id=prompt_id,
            input=item["input"],
            expected=item["expected"],
            tags=item.get("tags"),
            db_path=db_path,
        )
        results.append(tc)
    return results
