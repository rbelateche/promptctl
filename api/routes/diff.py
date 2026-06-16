"""API routes for prompt diffs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from core.commit_engine import resolve_ref
from core.diff_engine import diff_commits

router = APIRouter(tags=["diff"])


class DiffLineOut(BaseModel):
    """A single line in a prompt diff."""

    type: str  # "add" | "remove" | "context"
    content: str


class DiffOut(BaseModel):
    """Response payload for the diff endpoint."""

    from_commit_id: str
    to_commit_id: str
    diff_lines: list[DiffLineOut]
    score_delta: dict[str, float]


@router.get("/diff", response_model=DiffOut)
def get_diff(
    prompt_id: str,
    from_ref: str,
    to_ref: str,
    branch: str = "main",
    db_path: Path = Depends(get_db_path),
) -> DiffOut:
    """
    Compute a line-level diff and score delta between two commit references.

    Both ``from_ref`` and ``to_ref`` support the same ref syntax as the CLI:
    ``HEAD``, ``HEAD~N``, or a full/short commit hash.

    Args:
        prompt_id: Logical name of the prompt project.
        from_ref:  Base commit reference (e.g. ``HEAD~1``).
        to_ref:    Target commit reference (e.g. ``HEAD``).
        branch:    Branch context used to resolve HEAD refs.

    Raises:
        404: If either ref cannot be resolved.
    """
    try:
        from_commit = resolve_ref(ref=from_ref, prompt_id=prompt_id, branch=branch, db_path=db_path)
        to_commit = resolve_ref(ref=to_ref, prompt_id=prompt_id, branch=branch, db_path=db_path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    diff_lines, delta = diff_commits(from_commit=from_commit, to_commit=to_commit, db_path=db_path)

    return DiffOut(
        from_commit_id=from_commit.id,
        to_commit_id=to_commit.id,
        diff_lines=[DiffLineOut(type=dl.type, content=dl.content) for dl in diff_lines],
        score_delta=delta,
    )
