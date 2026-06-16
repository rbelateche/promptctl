"""Shared pytest fixtures for the promptctl test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from core.commit_engine import create_commit
from storage.commits import Commit
from storage.db import init_db


@pytest.fixture(autouse=True)
def _mock_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Force every test into mock/offline mode for LLM calls.

    Setting both keys to the sentinel ``test-key`` makes the eval runner and
    evaluators return deterministic placeholder responses instead of making
    real network calls.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a freshly-initialised, isolated SQLite database path."""
    path = tmp_path / "db.sqlite"
    init_db(path)
    return path


@pytest.fixture
def make_commit(db_path: Path) -> Callable[..., Commit]:
    """
    Return a factory that creates commits on the test database.

    The factory accepts ``content`` and ``message`` (plus optional ``prompt_id``,
    ``branch`` and ``model``) and returns the created :class:`Commit`.
    """

    def _factory(
        *,
        content: str,
        message: str,
        prompt_id: str = "demo",
        branch: str = "main",
        model: str = "gpt-4o",
    ) -> Commit:
        return create_commit(
            prompt_id=prompt_id,
            branch=branch,
            content=content,
            message=message,
            model=model,
            db_path=db_path,
        )

    return _factory


@pytest.fixture
def test_cases_file(tmp_path: Path) -> Path:
    """Write a small JSON test-cases file and return its path."""
    path = tmp_path / "test_cases.json"
    payload = [
        {
            "input": "How do I get a refund?",
            "expected": "Visit the refunds page.",
            "tags": ["refund"],
        },
        {"input": "Reset my password", "expected": "Click forgot password."},
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
