"""Tests for storage/commits.py CRUD helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from storage import branches as branches_storage
from storage.commits import (
    get_commit,
    get_commit_by_prefix,
    get_head,
    insert_commit,
    list_commits,
    walk_ancestors,
)


def _insert(db_path: Path, *, id: str, message: str, parent_id: str | None = None) -> None:
    """Insert a commit with sensible defaults for testing."""
    branches_storage.ensure_branch(name="main", prompt_id="demo", db_path=db_path)
    insert_commit(
        id=id,
        prompt_id="demo",
        branch="main",
        content=f"content-{id}",
        message=message,
        model="gpt-4o",
        parent_id=parent_id,
        db_path=db_path,
    )


def test_insert_and_get_commit(db_path: Path) -> None:
    """A commit round-trips through insert and get with all fields intact."""
    _insert(db_path, id="a" * 64, message="first")
    commit = get_commit(id="a" * 64, db_path=db_path)
    assert commit.message == "first"
    assert commit.prompt_id == "demo"
    assert commit.parent_id is None


def test_get_commit_missing_raises_keyerror(db_path: Path) -> None:
    """Fetching an unknown id raises KeyError."""
    with pytest.raises(KeyError):
        get_commit(id="deadbeef", db_path=db_path)


def test_get_commit_by_prefix(db_path: Path) -> None:
    """A unique prefix resolves to exactly one commit."""
    _insert(db_path, id="abc" + "0" * 61, message="prefixed")
    commit = get_commit_by_prefix(prefix="abc", db_path=db_path)
    assert commit.message == "prefixed"


def test_get_commit_by_prefix_ambiguous_raises(db_path: Path) -> None:
    """An ambiguous prefix matching multiple commits raises ValueError."""
    _insert(db_path, id="ab" + "1" * 62, message="one")
    _insert(db_path, id="ab" + "2" * 62, message="two", parent_id="ab" + "1" * 62)
    with pytest.raises(ValueError, match="Ambiguous"):
        get_commit_by_prefix(prefix="ab", db_path=db_path)


def test_get_commit_by_prefix_missing_raises_keyerror(db_path: Path) -> None:
    """A prefix matching nothing raises KeyError."""
    with pytest.raises(KeyError):
        get_commit_by_prefix(prefix="zzz", db_path=db_path)


def test_list_commits_newest_first(db_path: Path) -> None:
    """list_commits respects the limit and orders newest first."""
    _insert(db_path, id="1" * 64, message="older")
    _insert(db_path, id="2" * 64, message="newer", parent_id="1" * 64)
    commits = list_commits(prompt_id="demo", branch="main", limit=10, db_path=db_path)
    assert len(commits) == 2
    assert commits[0].message == "newer"


def test_get_head_none_when_empty(db_path: Path) -> None:
    """get_head returns None when the branch has no commits."""
    assert get_head(prompt_id="demo", branch="main", db_path=db_path) is None


def test_walk_ancestors(db_path: Path) -> None:
    """walk_ancestors steps up the parent chain N times."""
    _insert(db_path, id="1" * 64, message="root")
    _insert(db_path, id="2" * 64, message="mid", parent_id="1" * 64)
    _insert(db_path, id="3" * 64, message="tip", parent_id="2" * 64)
    ancestor = walk_ancestors(commit_id="3" * 64, steps=2, db_path=db_path)
    assert ancestor.message == "root"


def test_walk_ancestors_beyond_root_raises(db_path: Path) -> None:
    """Walking past the root commit raises ValueError."""
    _insert(db_path, id="1" * 64, message="root")
    with pytest.raises(ValueError, match="chain ends"):
        walk_ancestors(commit_id="1" * 64, steps=1, db_path=db_path)
