"""Exact-match evaluator — fast, zero-cost, no API calls required."""

from __future__ import annotations

import re
import string

from core.eval_runner import EvalCase, EvalResult
from evals.base import BaseEvaluator


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ExactMatchEvaluator(BaseEvaluator):
    """
    Check whether the normalized expected string appears anywhere in the
    normalized actual LLM output.

    Returns a single ``accuracy`` metric (fraction of cases that pass).
    """

    def evaluate(self, eval_cases: list[EvalCase]) -> list[EvalResult]:
        if not eval_cases:
            return []

        passed = sum(
            1 for ec in eval_cases if _normalize(ec.test_case.expected) in _normalize(ec.actual)
        )
        score = passed / len(eval_cases)
        return [EvalResult(metric="accuracy", value=score, n_cases=len(eval_cases))]
