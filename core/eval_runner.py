"""Eval runner — orchestrates evaluator strategies, collects scores, and persists results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from storage import scores as scores_storage
from storage.test_cases import TestCase

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    metric: str
    value: float       # 0.0–1.0 for ratios; seconds for latency
    n_cases: int


@dataclass
class EvalConfig:
    strategies: list[str]  # e.g. ["exact_match", "embedding_similarity", "llm_judge"]
    judge_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    metrics: dict[str, dict] | None = None  # weights per metric
    thresholds: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Evaluator protocol (matches evals/base.py BaseEvaluator)
# ---------------------------------------------------------------------------


class Evaluator(Protocol):
    def evaluate(
        self,
        prompt_content: str,
        test_cases: list[TestCase],
    ) -> list[EvalResult]: ...


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _load_evaluator(strategy: str, config: EvalConfig) -> Evaluator:
    """
    Lazily import and instantiate an evaluator by strategy name.
    Keeps heavy SDK imports out of the module-level scope.
    """
    if strategy == "exact_match":
        from evals.exact_match import ExactMatchEvaluator
        return ExactMatchEvaluator()

    if strategy == "embedding_similarity":
        from evals.embedding_sim import EmbeddingSimEvaluator
        return EmbeddingSimEvaluator(model=config.embedding_model)

    if strategy == "llm_judge":
        from evals.llm_judge import LLMJudgeEvaluator
        return LLMJudgeEvaluator(model=config.judge_model)

    raise ValueError(f"Unknown eval strategy: {strategy!r}")


def run_evals(
    *,
    commit_id: str,
    prompt_content: str,
    test_cases: list[TestCase],
    config: EvalConfig,
    db_path: Path,
    persist: bool = True,
) -> list[EvalResult]:
    """
    Run all configured evaluator strategies against the prompt + test suite.

    Steps:
    1. For each strategy in ``config.strategies``, run evaluate().
    2. Measure wall-clock latency across the full test suite and emit a
       ``latency`` metric (mean seconds per test case).
    3. Optionally persist all results to ``eval_scores``.

    Args:
        commit_id:      The commit these evals belong to.
        prompt_content: The full prompt text.
        test_cases:     Active test cases to run.
        config:         EvalConfig specifying strategies and model names.
        db_path:        SQLite DB path.
        persist:        If False, scores are returned but not written to DB.
                        Useful for dry-run / ``promptctl eval`` on uncommitted files.

    Returns:
        List of EvalResult, one per metric across all strategies.
    """
    if not test_cases:
        return []

    all_results: list[EvalResult] = []
    total_start = time.perf_counter()

    for strategy in config.strategies:
        evaluator = _load_evaluator(strategy, config)
        results = evaluator.evaluate(prompt_content, test_cases)
        all_results.extend(results)

    total_elapsed = time.perf_counter() - total_start
    mean_latency = total_elapsed / len(test_cases)
    all_results.append(EvalResult(metric="latency", value=mean_latency, n_cases=len(test_cases)))

    if persist:
        for result in all_results:
            scores_storage.insert_score(
                commit_id=commit_id,
                metric=result.metric,
                value=result.value,
                n_cases=result.n_cases,
                db_path=db_path,
            )

    return all_results
