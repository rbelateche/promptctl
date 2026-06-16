"""Tests for core/commit_engine.py."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from core.commit_engine import (
    create_commit,
    hash_prompt,
    resolve_ref,
    restore_commit,
    short_id,
)
from storage.commits import Commit, get_head


def test_hash_prompt_is_deterministic() -> None:
    """Identical content always hashes to the same 64-char digest."""
    assert hash_prompt("hello") == hash_prompt("hello")
    assert len(hash_prompt("hello")) == 64


def test_short_id() -> None:
    """short_id truncates to 7 characters."""
    assert short_id("a" * 64) == "aaaaaaa"


def test_create_commit_advances_head(db_path: Path) -> None:
    """Creating a commit sets it as the branch HEAD and links the parent."""
    first = create_commit(
        prompt_id="demo", branch="main", content="v1", message="c1", model="gpt-4o", db_path=db_path
    )
    second = create_commit(
        prompt_id="demo", branch="main", content="v2", message="c2", model="gpt-4o", db_path=db_path
    )
    head = get_head(prompt_id="demo", branch="main", db_path=db_path)
    assert head is not None
    assert head.id == second.id
    assert second.parent_id == first.id


def test_create_commit_rejects_identical_content(
    make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """Committing identical content raises ValueError (no silent no-op)."""
    make_commit(content="same", message="c1")
    with pytest.raises(ValueError, match="identical"):
        create_commit(
            prompt_id="demo",
            branch="main",
            content="same",
            message="c2",
            model="gpt-4o",
            db_path=db_path,
        )


def test_resolve_ref_head(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """HEAD resolves to the branch tip."""
    make_commit(content="v1", message="c1")
    tip = make_commit(content="v2", message="c2")
    resolved = resolve_ref(ref="HEAD", prompt_id="demo", branch="main", db_path=db_path)
    assert resolved.id == tip.id


def test_resolve_ref_head_tilde(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """HEAD~1 resolves to the parent of the tip."""
    first = make_commit(content="v1", message="c1")
    make_commit(content="v2", message="c2")
    resolved = resolve_ref(ref="HEAD~1", prompt_id="demo", branch="main", db_path=db_path)
    assert resolved.id == first.id


def test_resolve_ref_short_hash(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """A short hash prefix resolves to the matching commit."""
    commit = make_commit(content="v1", message="c1")
    resolved = resolve_ref(ref=commit.id[:8], prompt_id="demo", branch="main", db_path=db_path)
    assert resolved.id == commit.id


def test_resolve_ref_empty_branch_raises(db_path: Path) -> None:
    """HEAD on a branch with no commits raises ValueError."""
    with pytest.raises(ValueError, match="No commits"):
        resolve_ref(ref="HEAD", prompt_id="demo", branch="main", db_path=db_path)


def test_resolve_ref_invalid_head_raises(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """A malformed HEAD ref raises ValueError."""
    make_commit(content="v1", message="c1")
    with pytest.raises(ValueError, match="Invalid HEAD ref"):
        resolve_ref(ref="HEAD~abc", prompt_id="demo", branch="main", db_path=db_path)


def test_restore_commit_to_prior_version_raises(
    make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """
    KNOWN LIMITATION: restoring to a prior version currently fails.

    Because a commit's id is the SHA-256 of its content, re-committing the
    content of an older commit collides with that commit's primary key, so
    ``create_commit`` (called by ``restore_commit``) raises ValueError.
    This effectively breaks ``promptctl rollback`` and should be fixed in a
    dedicated bugfix PR (e.g. by salting the commit id with the parent id).
    """
    first = make_commit(content="v1", message="original")
    make_commit(content="v2", message="changed")
    with pytest.raises(ValueError, match="identical"):
        restore_commit(
            target_id=first.id,
            prompt_id="demo",
            branch="main",
            model="gpt-4o",
            db_path=db_path,
        )


def test_restore_commit_when_head_already_target_raises(
    make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """Restoring to the current HEAD raises ValueError."""
    tip = make_commit(content="v1", message="c1")
    with pytest.raises(ValueError, match="already at"):
        restore_commit(
            target_id=tip.id, prompt_id="demo", branch="main", model="gpt-4o", db_path=db_path
        )
