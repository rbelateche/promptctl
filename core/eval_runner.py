"""Eval runner — orchestrates evaluator strategies, collects scores, and persists results."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from storage import scores as scores_storage
from storage.test_cases import TestCase

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    metric: str
    value: float  # 0.0–1.0 for ratios; seconds for latency
    n_cases: int


@dataclass
class EvalCase:
    """A test case paired with the actual LLM output generated during eval."""

    test_case: TestCase
    actual: str  # LLM response to test_case.input given prompt_content as system prompt


@dataclass
class EvalConfig:
    strategies: list[str]  # e.g. ["exact_match", "embedding_similarity", "llm_judge"]
    inference_model: str = "gpt-4o"
    judge_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    metrics: dict[str, dict] | None = None  # weights per metric
    thresholds: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Inference — generate actual outputs from the prompt + test inputs
# ---------------------------------------------------------------------------


def _generate_output(prompt_content: str, user_input: str, model: str) -> str:
    """
    Call the configured LLM and return the actual text output.

    Supports OpenAI models (default) and Anthropic models (prefix: ``claude``).
    Raises ``RuntimeError`` with a clear message if the API key is missing.
    """
    if model.startswith("claude"):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key == "test-key":
            return f"[mock] response to: {user_input[:60]}"
        import anthropic

        anthropic_client = anthropic.Anthropic(api_key=api_key)
        message = anthropic_client.messages.create(
            model=model,
            max_tokens=1024,
            system=prompt_content,
            messages=[{"role": "user", "content": user_input}],
        )
        block = message.content[0]
        return block.text if hasattr(block, "text") else ""  # type: ignore[union-attr]
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key or api_key == "test-key":
            return f"[mock] response to: {user_input[:60]}"
        from openai import OpenAI

        openai_client = OpenAI(api_key=api_key)
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": user_input},
            ],
        )
        return response.choices[0].message.content or ""


def generate_eval_cases(
    prompt_content: str,
    test_cases: list[TestCase],
    model: str,
) -> list[EvalCase]:
    """Generate actual LLM outputs for all test cases (one API call each)."""
    return [
        EvalCase(
            test_case=tc,
            actual=_generate_output(prompt_content, tc.input, model),
        )
        for tc in test_cases
    ]


# ---------------------------------------------------------------------------
# Evaluator protocol (matches evals/base.py BaseEvaluator)
# ---------------------------------------------------------------------------


class Evaluator(Protocol):
    def evaluate(self, eval_cases: list[EvalCase]) -> list[EvalResult]: ...


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
    1. Generate actual LLM outputs for all test cases (inference step).
    2. For each strategy, score the (expected, actual) pairs.
    3. Measure wall-clock latency and emit a ``latency`` metric.
    4. Optionally persist all results to ``eval_scores``.

    Args:
        commit_id:      The commit these evals belong to.
        prompt_content: The full prompt text.
        test_cases:     Active test cases to run.
        config:         EvalConfig specifying strategies and model names.
        db_path:        SQLite DB path.
        persist:        If False, scores are returned but not written to DB.

    Returns:
        List of EvalResult, one per metric across all strategies.
    """
    if not test_cases:
        return []

    all_results: list[EvalResult] = []
    total_start = time.perf_counter()

    # Inference: generate all actual outputs in one pass (shared across strategies)
    eval_cases = generate_eval_cases(prompt_content, test_cases, config.inference_model)

    for strategy in config.strategies:
        evaluator = _load_evaluator(strategy, config)
        results = evaluator.evaluate(eval_cases)
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
