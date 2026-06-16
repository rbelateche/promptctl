"""Tests for storage/test_cases.py CRUD helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from storage.test_cases import (
    bulk_insert_from_file,
    delete_test_case,
    insert_test_case,
    list_test_cases,
    toggle_test_case,
)


def test_insert_and_list(db_path: Path) -> None:
    """A test case round-trips, preserving tags as a list."""
    tc = insert_test_case(
        prompt_id="demo",
        input="hi",
        expected="hello",
        tags=["greeting"],
        db_path=db_path,
    )
    assert tc.tags == ["greeting"]
    assert tc.active is True
    cases = list_test_cases(prompt_id="demo", db_path=db_path)
    assert len(cases) == 1


def test_insert_without_tags(db_path: Path) -> None:
    """A test case with no tags yields an empty list, not None."""
    tc = insert_test_case(prompt_id="demo", input="hi", expected="hello", db_path=db_path)
    assert tc.tags == []


def test_toggle_test_case(db_path: Path) -> None:
    """Toggling active=False hides the case from the active-only listing."""
    tc = insert_test_case(prompt_id="demo", input="hi", expected="hello", db_path=db_path)
    toggle_test_case(id=tc.id, active=False, db_path=db_path)
    assert list_test_cases(prompt_id="demo", active_only=True, db_path=db_path) == []
    assert len(list_test_cases(prompt_id="demo", active_only=False, db_path=db_path)) == 1


def test_toggle_missing_raises(db_path: Path) -> None:
    """Toggling a non-existent id raises KeyError."""
    with pytest.raises(KeyError):
        toggle_test_case(id=999, active=False, db_path=db_path)


def test_delete_test_case(db_path: Path) -> None:
    """delete_test_case removes the row."""
    tc = insert_test_case(prompt_id="demo", input="hi", expected="hello", db_path=db_path)
    delete_test_case(id=tc.id, db_path=db_path)
    assert list_test_cases(prompt_id="demo", active_only=False, db_path=db_path) == []


def test_delete_missing_raises(db_path: Path) -> None:
    """Deleting a non-existent id raises KeyError."""
    with pytest.raises(KeyError):
        delete_test_case(id=999, db_path=db_path)


def test_bulk_insert_from_file(test_cases_file: Path, db_path: Path) -> None:
    """bulk_insert_from_file loads every case from a JSON file."""
    inserted = bulk_insert_from_file(prompt_id="demo", path=test_cases_file, db_path=db_path)
    assert len(inserted) == 2
    assert len(list_test_cases(prompt_id="demo", db_path=db_path)) == 2


def test_bulk_insert_skip_existing(test_cases_file: Path, db_path: Path) -> None:
    """skip_existing avoids inserting duplicate (input, expected) pairs."""
    bulk_insert_from_file(prompt_id="demo", path=test_cases_file, db_path=db_path)
    second = bulk_insert_from_file(
        prompt_id="demo", path=test_cases_file, db_path=db_path, skip_existing=True
    )
    assert second == []
    assert len(list_test_cases(prompt_id="demo", db_path=db_path)) == 2
