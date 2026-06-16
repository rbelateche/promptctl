"""Tests for storage/scores.py CRUD helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from storage.commits import Commit
from storage.scores import (
    get_score_history,
    get_scores,
    get_scores_dict,
    insert_score,
)


def test_insert_and_get_scores(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """Scores insert and read back ordered by metric name."""
    commit = make_commit(content="p1", message="c1")
    insert_score(commit_id=commit.id, metric="faithfulness", value=0.8, n_cases=4, db_path=db_path)
    insert_score(commit_id=commit.id, metric="accuracy", value=0.9, n_cases=4, db_path=db_path)

    scores = get_scores(commit_id=commit.id, db_path=db_path)
    assert [s.metric for s in scores] == ["accuracy", "faithfulness"]
    assert scores[0].value == 0.9


def test_get_scores_dict(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """get_scores_dict returns a {metric: value} mapping."""
    commit = make_commit(content="p1", message="c1")
    insert_score(commit_id=commit.id, metric="accuracy", value=0.75, n_cases=2, db_path=db_path)
    assert get_scores_dict(commit_id=commit.id, db_path=db_path) == {"accuracy": 0.75}


def test_get_scores_dict_empty(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """A commit with no scores yields an empty dict."""
    commit = make_commit(content="p1", message="c1")
    assert get_scores_dict(commit_id=commit.id, db_path=db_path) == {}


def test_get_score_history_oldest_first(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """Score history for a metric is returned oldest-first across commits."""
    c1 = make_commit(content="p1", message="first")
    c2 = make_commit(content="p2", message="second")
    insert_score(commit_id=c1.id, metric="accuracy", value=0.5, n_cases=2, db_path=db_path)
    insert_score(commit_id=c2.id, metric="accuracy", value=0.7, n_cases=2, db_path=db_path)

    history = get_score_history(prompt_id="demo", branch="main", metric="accuracy", db_path=db_path)
    assert [h["value"] for h in history] == [0.5, 0.7]
    assert history[0]["short_id"] == c1.id[:7]
