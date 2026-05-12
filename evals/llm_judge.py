"""LLM-as-judge evaluator — uses a judge model to score accuracy, faithfulness, and tone."""

from __future__ import annotations

import json
import os
import re

from core.eval_runner import EvalCase, EvalResult
from evals.base import BaseEvaluator

_JUDGE_SYSTEM_PROMPT = """\
You are an objective evaluator for LLM outputs. Given a test case (input + expected output) \
and the actual output produced by an AI assistant, rate the actual output on the following metrics:

- accuracy (0.0–1.0): Does the actual output convey the same factual content as expected?
- faithfulness (0.0–1.0): Does the actual output stay faithful to the intent of the expected?
- tone (0.0–1.0): Is the tone of the actual output appropriate and similar to expected?

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{"accuracy": <float>, "faithfulness": <float>, "tone": <float>, "reasoning": "<one sentence>"}
"""

_JUDGE_USER_TEMPLATE = """\
Input: {input}
Expected output: {expected}
Actual output: {actual}
"""

_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _parse_judge_response(text: str) -> dict[str, float]:
    """Extract JSON from judge response. Raises ValueError on parse failure."""
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError(f"No JSON object found in judge response: {text!r}")
    data = json.loads(match.group())
    for key in ("accuracy", "faithfulness", "tone"):
        if key not in data:
            raise ValueError(f"Missing key {key!r} in judge response: {data}")
    return data


def _call_judge(user_message: str, model: str, client) -> dict[str, float]:  # type: ignore[no-untyped-def]
    """Call the judge model and return parsed scores. Retries once on parse error."""
    for attempt in range(2):
        if model.startswith("claude"):
            import anthropic

            anthropic_client: anthropic.Anthropic = client
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=256,
                system=_JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            block = response.content[0]
            raw = block.text if hasattr(block, "text") else ""  # type: ignore[union-attr]
        else:
            from openai import OpenAI

            openai_client: OpenAI = client
            oai_response = openai_client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            raw = oai_response.choices[0].message.content or ""

        try:
            return _parse_judge_response(raw)
        except ValueError:
            if attempt == 1:
                raise
    return {}  # unreachable


class LLMJudgeEvaluator(BaseEvaluator):
    """
    Use a judge model (default: ``gpt-4o``) to rate each actual output on
    accuracy, faithfulness, and tone against the expected output.

    Returns three EvalResult objects (one per metric), averaged across all cases.
    Falls back to returning 0.0 for all metrics when no API key is present.
    """

    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model

    def _make_client(self):  # type: ignore[no-untyped-def]
        if self.model.startswith("claude"):
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key or api_key == "test-key":
                return None
            import anthropic

            return anthropic.Anthropic(api_key=api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key or api_key == "test-key":
                return None
            from openai import OpenAI

            return OpenAI(api_key=api_key)

    def evaluate(self, eval_cases: list[EvalCase]) -> list[EvalResult]:
        if not eval_cases:
            return []

        client = self._make_client()
        if client is None:
            # No API key — return neutral scores so the pipeline doesn't crash
            n = len(eval_cases)
            return [
                EvalResult(metric="accuracy", value=0.0, n_cases=n),
                EvalResult(metric="faithfulness", value=0.0, n_cases=n),
                EvalResult(metric="tone", value=0.0, n_cases=n),
            ]

        totals: dict[str, float] = {"accuracy": 0.0, "faithfulness": 0.0, "tone": 0.0}
        for ec in eval_cases:
            user_message = _JUDGE_USER_TEMPLATE.format(
                input=ec.test_case.input,
                expected=ec.test_case.expected,
                actual=ec.actual,
            )
            scores = _call_judge(user_message, self.model, client)
            for metric in totals:
                totals[metric] += float(scores.get(metric, 0.0))

        n = len(eval_cases)
        return [
            EvalResult(metric=metric, value=total / n, n_cases=n)
            for metric, total in totals.items()
        ]
