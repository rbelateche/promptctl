"""Tests for core/diff_engine.py."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from core.diff_engine import (
    diff_commits,
    has_regression,
    line_diff,
    score_delta,
)
from storage.commits import Commit
from storage.scores import insert_score


def test_line_diff_add_remove_context() -> None:
    """line_diff classifies added, removed, and unchanged lines."""
    lines = line_diff("a\nb\nc", "a\nB\nc")
    types = {dl.content: dl.type for dl in lines}
    assert types["a"] == "context"
    assert types["c"] == "context"
    assert "b" in {dl.content for dl in lines if dl.type == "remove"}
    assert "B" in {dl.content for dl in lines if dl.type == "add"}


def test_line_diff_identical_is_all_context() -> None:
    """Diffing identical text yields only context lines."""
    lines = line_diff("x\ny", "x\ny")
    assert all(dl.type == "context" for dl in lines)


def test_score_delta_basic() -> None:
    """score_delta subtracts from-scores from to-scores per metric."""
    delta = score_delta({"accuracy": 0.5}, {"accuracy": 0.8})
    assert delta["accuracy"] == pytest.approx(0.3)


def test_score_delta_missing_metric_defaults_zero() -> None:
    """Metrics present in only one side default the other to 0.0."""
    delta = score_delta({}, {"latency": 1.2})
    assert delta["latency"] == pytest.approx(1.2)


def test_diff_commits(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """diff_commits returns both line diff and score delta."""
    c1 = make_commit(content="hello\nworld", message="c1")
    c2 = make_commit(content="hello\nthere", message="c2")
    insert_score(commit_id=c1.id, metric="accuracy", value=0.6, n_cases=2, db_path=db_path)
    insert_score(commit_id=c2.id, metric="accuracy", value=0.9, n_cases=2, db_path=db_path)

    diff_lines, delta = diff_commits(from_commit=c1, to_commit=c2, db_path=db_path)
    assert delta["accuracy"] == pytest.approx(0.3)
    assert any(dl.type == "add" and dl.content == "there" for dl in diff_lines)


def test_has_regression() -> None:
    """has_regression flags metrics with a negative delta that are tracked."""
    delta = {"accuracy": -0.1, "latency": 0.2}
    regressed = has_regression(delta, {"accuracy": 0.8})
    assert regressed == ["accuracy"]
