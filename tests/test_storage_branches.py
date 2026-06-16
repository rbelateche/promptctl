"""Tests for storage/branches.py CRUD helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from storage.branches import (
    create_branch,
    ensure_branch,
    get_branch,
    list_branches,
    update_head,
)
from storage.commits import insert_commit


def test_create_and_get_branch(db_path: Path) -> None:
    """A branch round-trips through create and get."""
    create_branch(name="main", prompt_id="demo", db_path=db_path)
    branch = get_branch(name="main", prompt_id="demo", db_path=db_path)
    assert branch.name == "main"
    assert branch.head_id is None


def test_create_duplicate_branch_raises(db_path: Path) -> None:
    """Creating the same branch twice raises ValueError."""
    create_branch(name="main", prompt_id="demo", db_path=db_path)
    with pytest.raises(ValueError, match="already exists"):
        create_branch(name="main", prompt_id="demo", db_path=db_path)


def test_get_branch_missing_raises_keyerror(db_path: Path) -> None:
    """Fetching an unknown branch raises KeyError."""
    with pytest.raises(KeyError):
        get_branch(name="ghost", prompt_id="demo", db_path=db_path)


def test_list_branches(db_path: Path) -> None:
    """list_branches returns every branch for a prompt."""
    create_branch(name="main", prompt_id="demo", db_path=db_path)
    create_branch(name="exp", prompt_id="demo", db_path=db_path)
    names = {b.name for b in list_branches(prompt_id="demo", db_path=db_path)}
    assert names == {"main", "exp"}


def test_update_head(db_path: Path) -> None:
    """update_head advances the stored head pointer to a real commit."""
    create_branch(name="main", prompt_id="demo", db_path=db_path)
    insert_commit(
        id="a" * 64,
        prompt_id="demo",
        branch="main",
        content="v1",
        message="c1",
        model="gpt-4o",
        parent_id=None,
        db_path=db_path,
    )
    updated = update_head(name="main", prompt_id="demo", head_id="a" * 64, db_path=db_path)
    assert updated.head_id == "a" * 64


def test_update_head_missing_branch_raises(db_path: Path) -> None:
    """Updating a non-existent branch raises KeyError."""
    with pytest.raises(KeyError):
        update_head(name="ghost", prompt_id="demo", head_id="a" * 64, db_path=db_path)


def test_ensure_branch_is_idempotent(db_path: Path) -> None:
    """ensure_branch creates once then returns the existing branch."""
    first = ensure_branch(name="main", prompt_id="demo", db_path=db_path)
    second = ensure_branch(name="main", prompt_id="demo", db_path=db_path)
    assert first.name == second.name == "main"
    assert len(list_branches(prompt_id="demo", db_path=db_path)) == 1
