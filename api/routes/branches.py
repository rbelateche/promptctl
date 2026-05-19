"""API routes for branch management and comparison."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from core.diff_engine import score_delta
from storage import branches as branches_storage
from storage import scores as scores_storage
from storage.commits import get_head

router = APIRouter(tags=["branches"])


class BranchOut(BaseModel):
    """Serialisable representation of a branch."""

    name: str
    prompt_id: str
    head_id: str | None
    created_at: str


class BranchCompareRequest(BaseModel):
    """Request body for the branch comparison endpoint."""

    prompt_id: str
    branch_a: str
    branch_b: str


class BranchCompareOut(BaseModel):
    """Side-by-side score comparison between two branches."""

    branch_a: str
    branch_b: str
    scores_a: dict[str, float]
    scores_b: dict[str, float]
    delta: dict[str, float]


@router.get("/branches", response_model=list[BranchOut])
def list_branches(
    prompt_id: str,
    db_path: Path = Depends(get_db_path),
) -> list[BranchOut]:
    """
    List all branches for a prompt, ordered by creation time.

    Args:
        prompt_id: Logical name of the prompt project.
    """
    branches = branches_storage.list_branches(prompt_id=prompt_id, db_path=db_path)
    return [
        BranchOut(
            name=b.name,
            prompt_id=b.prompt_id,
            head_id=b.head_id,
            created_at=b.created_at,
        )
        for b in branches
    ]


@router.post("/branches/compare", response_model=BranchCompareOut)
def compare_branches(
    body: BranchCompareRequest,
    db_path: Path = Depends(get_db_path),
) -> BranchCompareOut:
    """
    Compare the HEAD eval scores of two branches side-by-side.

    Returns per-metric scores for each branch and the signed delta
    (``branch_b - branch_a``) so the UI can highlight improvements and regressions.

    Raises:
        404: If either branch has no commits.
    """
    head_a = get_head(prompt_id=body.prompt_id, branch=body.branch_a, db_path=db_path)
    head_b = get_head(prompt_id=body.prompt_id, branch=body.branch_b, db_path=db_path)

    if not head_a:
        raise HTTPException(
            status_code=404,
            detail=f"No commits on branch {body.branch_a!r}",
        )
    if not head_b:
        raise HTTPException(
            status_code=404,
            detail=f"No commits on branch {body.branch_b!r}",
        )

    scores_a = scores_storage.get_scores_dict(commit_id=head_a.id, db_path=db_path)
    scores_b = scores_storage.get_scores_dict(commit_id=head_b.id, db_path=db_path)
    delta = score_delta(scores_a, scores_b)

    return BranchCompareOut(
        branch_a=body.branch_a,
        branch_b=body.branch_b,
        scores_a=scores_a,
        scores_b=scores_b,
        delta=delta,
    )
