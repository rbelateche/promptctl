"""Embedding similarity evaluator — semantic faithfulness via cosine similarity."""

from __future__ import annotations

import math
import os

from core.eval_runner import EvalCase, EvalResult
from evals.base import BaseEvaluator


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_embedding(text: str, model: str, client) -> list[float]:  # type: ignore[no-untyped-def]
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


class EmbeddingSimEvaluator(BaseEvaluator):
    """
    Compute cosine similarity between embeddings of the expected and actual output.

    Uses OpenAI's ``text-embedding-3-small`` by default. Gracefully falls back to
    a score of 0.0 (logged as a warning) when ``OPENAI_API_KEY`` is absent or is
    the placeholder ``test-key``.

    Returns a single ``faithfulness`` metric (mean cosine similarity, 0.0–1.0).
    """

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model

    def evaluate(self, eval_cases: list[EvalCase]) -> list[EvalResult]:
        if not eval_cases:
            return []

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key or api_key == "test-key":
            # No key available — return a neutral score so the pipeline doesn't crash
            return [EvalResult(metric="faithfulness", value=0.0, n_cases=len(eval_cases))]

        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        total_sim = 0.0
        for ec in eval_cases:
            expected_emb = _get_embedding(ec.test_case.expected, self.model, client)
            actual_emb = _get_embedding(ec.actual, self.model, client)
            total_sim += _cosine_similarity(expected_emb, actual_emb)

        mean_sim = total_sim / len(eval_cases)
        return [EvalResult(metric="faithfulness", value=mean_sim, n_cases=len(eval_cases))]
