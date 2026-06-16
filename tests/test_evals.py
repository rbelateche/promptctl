"""Tests for the evaluator strategies (offline/mock mode)."""

from __future__ import annotations

import pytest

from core.eval_runner import EvalCase
from evals.embedding_sim import EmbeddingSimEvaluator, _cosine_similarity
from evals.exact_match import ExactMatchEvaluator, _normalize
from evals.llm_judge import LLMJudgeEvaluator, _parse_judge_response
from storage.test_cases import TestCase


def _case(expected: str, actual: str) -> EvalCase:
    """Build an EvalCase pairing an expected value with an actual output."""
    tc = TestCase(id=1, prompt_id="demo", input="q", expected=expected, tags=[], active=True)
    return EvalCase(test_case=tc, actual=actual)


# --- exact match -----------------------------------------------------------


def test_normalize_strips_case_and_punctuation() -> None:
    """Normalisation lowercases, removes punctuation, and collapses whitespace."""
    assert _normalize("Hello,   World!") == "hello world"


def test_exact_match_full_pass() -> None:
    """All matching cases yield accuracy 1.0."""
    results = ExactMatchEvaluator().evaluate(
        [_case("hello", "well, hello there"), _case("bye", "BYE!")]
    )
    assert results[0].metric == "accuracy"
    assert results[0].value == pytest.approx(1.0)


def test_exact_match_partial() -> None:
    """Half-matching cases yield accuracy 0.5."""
    results = ExactMatchEvaluator().evaluate(
        [_case("hello", "hello there"), _case("missing", "nope")]
    )
    assert results[0].value == pytest.approx(0.5)


def test_exact_match_empty() -> None:
    """No cases yields no results."""
    assert ExactMatchEvaluator().evaluate([]) == []


# --- embedding similarity --------------------------------------------------


def test_cosine_similarity_identity() -> None:
    """Identical vectors have cosine similarity 1.0."""
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal() -> None:
    """Orthogonal vectors have cosine similarity 0.0."""
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector() -> None:
    """A zero vector returns 0.0 instead of dividing by zero."""
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_embedding_sim_mock_mode_returns_neutral() -> None:
    """Without an API key, the evaluator returns a neutral 0.0 faithfulness."""
    results = EmbeddingSimEvaluator().evaluate([_case("a", "b")])
    assert results[0].metric == "faithfulness"
    assert results[0].value == 0.0


# --- llm judge -------------------------------------------------------------


def test_parse_judge_response_valid() -> None:
    """Valid JSON embedded in prose is parsed into a score dict."""
    raw = 'Here: {"accuracy": 0.9, "faithfulness": 0.8, "tone": 0.7, "reasoning": "ok"}'
    parsed = _parse_judge_response(raw)
    assert parsed["accuracy"] == 0.9


def test_parse_judge_response_missing_key_raises() -> None:
    """A response missing a required metric raises ValueError."""
    with pytest.raises(ValueError, match="Missing key"):
        _parse_judge_response('{"accuracy": 0.9}')


def test_parse_judge_response_no_json_raises() -> None:
    """A response with no JSON object raises ValueError."""
    with pytest.raises(ValueError, match="No JSON"):
        _parse_judge_response("totally not json")


def test_llm_judge_mock_mode_returns_three_metrics() -> None:
    """Without an API key the judge returns neutral accuracy/faithfulness/tone."""
    results = LLMJudgeEvaluator().evaluate([_case("a", "b")])
    metrics = {r.metric for r in results}
    assert metrics == {"accuracy", "faithfulness", "tone"}
    assert all(r.value == 0.0 for r in results)
