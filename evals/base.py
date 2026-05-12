"""Abstract base class for all evaluators."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.eval_runner import EvalCase, EvalResult


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(self, eval_cases: list[EvalCase]) -> list[EvalResult]:
        """
        Score a list of (test_case, actual_output) pairs.

        Args:
            eval_cases: Pre-generated pairs of TestCase + actual LLM output.

        Returns:
            One or more EvalResult objects (one per metric this evaluator produces).
        """
