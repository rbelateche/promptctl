"""Tests for core/eval_runner.py in offline/mock mode."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from core.eval_runner import (
    EvalConfig,
    generate_eval_cases,
    run_evals,
)
from storage.commits import Commit
from storage.scores import get_scores_dict
from storage.test_cases import TestCase


def _test_cases() -> list[TestCase]:
    """Two simple test cases for the runner."""
    return [
        TestCase(id=1, prompt_id="demo", input="hi", expected="hello", tags=[], active=True),
        TestCase(id=2, prompt_id="demo", input="bye", expected="goodbye", tags=[], active=True),
    ]


def test_generate_eval_cases_mock_mode() -> None:
    """In mock mode every output is a deterministic placeholder string."""
    cases = generate_eval_cases("system prompt", _test_cases(), "gpt-4o")
    assert len(cases) == 2
    assert all(ec.actual.startswith("[mock]") for ec in cases)


def test_run_evals_empty_returns_empty(db_path: Path) -> None:
    """No test cases produces no results."""
    config = EvalConfig(strategies=["exact_match"])
    assert (
        run_evals(commit_id="x", prompt_content="p", test_cases=[], config=config, db_path=db_path)
        == []
    )


def test_run_evals_persists_scores(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """run_evals writes one score per metric, including latency."""
    commit = make_commit(content="p", message="c1")
    config = EvalConfig(strategies=["exact_match"])
    results = run_evals(
        commit_id=commit.id,
        prompt_content="p",
        test_cases=_test_cases(),
        config=config,
        db_path=db_path,
    )
    metrics = {r.metric for r in results}
    assert "accuracy" in metrics
    assert "latency" in metrics

    stored = get_scores_dict(commit_id=commit.id, db_path=db_path)
    assert "accuracy" in stored
    assert "latency" in stored


def test_run_evals_no_persist(make_commit: Callable[..., Commit], db_path: Path) -> None:
    """persist=False returns results without writing to the DB."""
    commit = make_commit(content="p", message="c1")
    config = EvalConfig(strategies=["exact_match"])
    results = run_evals(
        commit_id=commit.id,
        prompt_content="p",
        test_cases=_test_cases(),
        config=config,
        db_path=db_path,
        persist=False,
    )
    assert results
    assert get_scores_dict(commit_id=commit.id, db_path=db_path) == {}
