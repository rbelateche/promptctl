"""API routes for eval scores."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from storage import scores as scores_storage

router = APIRouter(tags=["scores"])


class ScoreOut(BaseModel):
    """A single eval score row."""

    id: int
    commit_id: str
    metric: str
    value: float
    n_cases: int
    created_at: str


class ScoreHistoryPoint(BaseModel):
    """One data point in a metric's history over time."""

    commit_id: str
    short_id: str
    message: str
    value: float
    created_at: str


@router.get("/scores/history", response_model=list[ScoreHistoryPoint])
def get_score_history(
    prompt_id: str,
    metric: str,
    branch: str = "main",
    db_path: Path = Depends(get_db_path),
) -> list[ScoreHistoryPoint]:
    """
    Return the history of a single metric across all commits on a branch.

    Results are ordered oldest-first, suitable for plotting a time-series chart.

    Note:
        This route is declared *before* ``/scores/{commit_id}`` so that the
        literal path ``/scores/history`` is not captured by the dynamic
        ``{commit_id}`` parameter.

    Args:
        prompt_id: Logical name of the prompt project.
        metric:    Metric name (e.g. ``accuracy``, ``faithfulness``, ``latency``).
        branch:    Branch to query (default: ``main``).
    """
    rows = scores_storage.get_score_history(
        prompt_id=prompt_id, branch=branch, metric=metric, db_path=db_path
    )
    return [
        ScoreHistoryPoint(
            commit_id=r["commit_id"],
            short_id=r["short_id"],
            message=r["message"],
            value=r["value"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.get("/scores/{commit_id}", response_model=list[ScoreOut])
def get_scores(
    commit_id: str,
    db_path: Path = Depends(get_db_path),
) -> list[ScoreOut]:
    """
    Return all eval scores for a given commit, ordered by metric name.

    Args:
        commit_id: Full SHA-256 commit id.

    Raises:
        404: If no scores exist for the given commit id.
    """
    scores = scores_storage.get_scores(commit_id=commit_id, db_path=db_path)
    if not scores:
        raise HTTPException(
            status_code=404,
            detail=f"No scores found for commit {commit_id!r}",
        )
    return [
        ScoreOut(
            id=s.id,
            commit_id=s.commit_id,
            metric=s.metric,
            value=s.value,
            n_cases=s.n_cases,
            created_at=s.created_at,
        )
        for s in scores
    ]
