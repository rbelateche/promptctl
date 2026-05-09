"""Commit engine — hashing, parent chain management, and branch pointer updates."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from storage import branches as branches_storage
from storage import commits as commits_storage
from storage.commits import Commit


def hash_prompt(content: str) -> str:
    """Return the full SHA-256 hex digest of the prompt content (UTF-8 encoded)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def short_id(full_id: str) -> str:
    """Return the 7-character short hash for display."""
    return full_id[:7]


def create_commit(
    *,
    prompt_id: str,
    branch: str,
    content: str,
    message: str,
    model: str,
    db_path: Path,
) -> Commit:
    """
    Hash the prompt content, store a new commit, and advance the branch head.

    - If a commit with the same content already exists on this branch, raises
      ValueError to avoid silent no-ops.
    - Idempotent branch creation: the branch row is created if it does not exist.

    Returns the newly created Commit.
    """
    commit_id = hash_prompt(content)

    # Guard against committing identical content
    try:
        existing = commits_storage.get_commit(id=commit_id, db_path=db_path)
        raise ValueError(
            f"Prompt content is identical to existing commit {short_id(commit_id)!r} "
            f"({existing.message!r}). Nothing to commit."
        )
    except KeyError:
        pass  # expected — content is new

    # Resolve parent
    parent: Optional[Commit] = commits_storage.get_head(
        prompt_id=prompt_id, branch=branch, db_path=db_path
    )
    parent_id: Optional[str] = parent.id if parent else None

    # Ensure the branch row exists before writing the commit
    branches_storage.ensure_branch(name=branch, prompt_id=prompt_id, db_path=db_path)

    # Persist the commit
    commit = commits_storage.insert_commit(
        id=commit_id,
        prompt_id=prompt_id,
        branch=branch,
        content=content,
        message=message,
        model=model,
        parent_id=parent_id,
        db_path=db_path,
    )

    # Advance branch head
    branches_storage.update_head(
        name=branch, prompt_id=prompt_id, head_id=commit_id, db_path=db_path
    )

    return commit


def restore_commit(
    *,
    target_id: str,
    prompt_id: str,
    branch: str,
    model: str,
    db_path: Path,
) -> Commit:
    """
    Non-destructive rollback: create a new commit whose content mirrors `target_id`.

    The original commit history is preserved. The new commit's parent is the
    current HEAD, so the full chain remains intact.

    Returns the newly created Commit.
    """
    target = commits_storage.get_commit(id=target_id, db_path=db_path)
    message = f"Revert to {short_id(target_id)} ({target.message!r})"

    # Re-hashing the same content produces the same id — we need to detect
    # that the current HEAD is already identical to the target.
    current_head = commits_storage.get_head(prompt_id=prompt_id, branch=branch, db_path=db_path)
    if current_head and current_head.id == target_id:
        raise ValueError(f"HEAD is already at {short_id(target_id)!r}. Nothing to restore.")

    return create_commit(
        prompt_id=prompt_id,
        branch=branch,
        content=target.content,
        message=message,
        model=model,
        db_path=db_path,
    )


def resolve_ref(
    *,
    ref: str,
    prompt_id: str,
    branch: str,
    db_path: Path,
) -> Commit:
    """
    Resolve a commit reference to a Commit object.

    Supported ref formats:
    - ``HEAD``         — current branch tip
    - ``HEAD~N``       — N steps before HEAD (e.g. HEAD~1, HEAD~3)
    - ``<hash>``       — full or partial commit hash (min 4 chars)
    """
    if ref.upper().startswith("HEAD"):
        head = commits_storage.get_head(prompt_id=prompt_id, branch=branch, db_path=db_path)
        if head is None:
            raise ValueError(f"No commits on branch {branch!r} for prompt {prompt_id!r}")

        suffix = ref[4:]  # everything after "HEAD"
        if not suffix:
            return head

        if suffix.startswith("~"):
            try:
                steps = int(suffix[1:])
            except ValueError:
                raise ValueError(f"Invalid HEAD ref: {ref!r}")
            return commits_storage.walk_ancestors(commit_id=head.id, steps=steps, db_path=db_path)

        raise ValueError(f"Invalid HEAD ref: {ref!r}")

    # Treat as hash prefix (full or short)
    return commits_storage.get_commit_by_prefix(prefix=ref, db_path=db_path)
