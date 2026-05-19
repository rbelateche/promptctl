"""API routes for commit history."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from storage import commits as commits_storage
from storage import scores as scores_storage

router = APIRouter(tags=["commits"])


class CommitOut(BaseModel):
    """Serialisable representation of a single commit."""

    id: str
    short_id: str
    prompt_id: str
    branch: str
    message: str
    model: str
    parent_id: str | None
    created_at: str
    scores: dict[str, float]


def _commit_out(commit, db_path: Path) -> CommitOut:
    """
    Convert a storage ``Commit`` to the API response model.

    Fetches the associated eval scores in a second query and embeds them inline
    so callers receive a complete picture without a separate scores request.
    """
    scores = scores_storage.get_scores_dict(commit_id=commit.id, db_path=db_path)
    return CommitOut(
        id=commit.id,
        short_id=commit.id[:7],
        prompt_id=commit.prompt_id,
        branch=commit.branch,
        message=commit.message,
        model=commit.model,
        parent_id=commit.parent_id,
        created_at=commit.created_at,
        scores=scores,
    )


@router.get("/commits", response_model=list[CommitOut])
def list_commits(
    prompt_id: str,
    branch: str = "main",
    limit: int = 50,
    db_path: Path = Depends(get_db_path),
) -> list[CommitOut]:
    """
    List commits for a prompt on a given branch, newest first.

    Args:
        prompt_id: Logical name of the prompt project.
        branch:    Branch to query (default: ``main``).
        limit:     Maximum number of commits to return (default: 50, max: 200).
    """
    limit = min(limit, 200)
    commits = commits_storage.list_commits(
        prompt_id=prompt_id, branch=branch, limit=limit, db_path=db_path
    )
    return [_commit_out(c, db_path) for c in commits]


@router.get("/commits/{commit_id}", response_model=CommitOut)
def get_commit(
    commit_id: str,
    db_path: Path = Depends(get_db_path),
) -> CommitOut:
    """
    Fetch a single commit by full or short hash.

    Raises:
        404: If no commit matches the provided id or prefix.
    """
    try:
        if len(commit_id) == 64:
            commit = commits_storage.get_commit(id=commit_id, db_path=db_path)
        else:
            commit = commits_storage.get_commit_by_prefix(prefix=commit_id, db_path=db_path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _commit_out(commit, db_path)
