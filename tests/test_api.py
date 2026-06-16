"""Integration tests for the FastAPI routes using dependency overrides."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db_path
from api.main import app
from storage.commits import Commit
from storage.scores import insert_score


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    """A TestClient whose DB dependency is overridden to the isolated test DB."""
    app.dependency_overrides[get_db_path] = lambda: db_path
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_healthz(client: TestClient) -> None:
    """The liveness endpoint returns ok."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_commits(
    client: TestClient, make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """GET /api/commits returns commits with inline scores."""
    commit = make_commit(content="v1", message="c1")
    insert_score(commit_id=commit.id, metric="accuracy", value=0.9, n_cases=2, db_path=db_path)

    resp = client.get("/api/commits", params={"prompt_id": "demo"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["short_id"] == commit.id[:7]
    assert body[0]["scores"]["accuracy"] == 0.9


def test_get_commit_by_short_id(client: TestClient, make_commit: Callable[..., Commit]) -> None:
    """GET /api/commits/{id} resolves a short prefix."""
    commit = make_commit(content="v1", message="c1")
    resp = client.get(f"/api/commits/{commit.id[:8]}")
    assert resp.status_code == 200
    assert resp.json()["id"] == commit.id


def test_get_commit_not_found(client: TestClient) -> None:
    """An unknown commit id returns 404."""
    resp = client.get("/api/commits/doesnotexist")
    assert resp.status_code == 404


def test_diff_endpoint(
    client: TestClient, make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """GET /api/diff returns line diff and score delta between two refs."""
    c1 = make_commit(content="hello\nworld", message="c1")
    c2 = make_commit(content="hello\nthere", message="c2")
    insert_score(commit_id=c1.id, metric="accuracy", value=0.6, n_cases=2, db_path=db_path)
    insert_score(commit_id=c2.id, metric="accuracy", value=0.8, n_cases=2, db_path=db_path)

    resp = client.get(
        "/api/diff",
        params={"prompt_id": "demo", "from_ref": "HEAD~1", "to_ref": "HEAD"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["score_delta"]["accuracy"] == pytest.approx(0.2)
    assert any(dl["type"] == "add" and dl["content"] == "there" for dl in body["diff_lines"])


def test_scores_history(
    client: TestClient, make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """GET /api/scores/history returns a metric time-series."""
    commit = make_commit(content="v1", message="c1")
    insert_score(commit_id=commit.id, metric="accuracy", value=0.7, n_cases=2, db_path=db_path)
    resp = client.get("/api/scores/history", params={"prompt_id": "demo", "metric": "accuracy"})
    assert resp.status_code == 200
    assert resp.json()[0]["value"] == 0.7


def test_scores_for_commit_not_found(client: TestClient) -> None:
    """Requesting scores for an unscored commit returns 404."""
    resp = client.get("/api/scores/unknown")
    assert resp.status_code == 404


def test_branches_endpoints(
    client: TestClient, make_commit: Callable[..., Commit], db_path: Path
) -> None:
    """GET /api/branches lists branches; POST /compare returns a delta."""
    main_tip = make_commit(content="v1", message="c1")
    insert_score(commit_id=main_tip.id, metric="accuracy", value=0.5, n_cases=2, db_path=db_path)
    exp_tip = make_commit(content="v2", message="c2", branch="exp")
    insert_score(commit_id=exp_tip.id, metric="accuracy", value=0.9, n_cases=2, db_path=db_path)

    listed = client.get("/api/branches", params={"prompt_id": "demo"})
    assert listed.status_code == 200
    assert {b["name"] for b in listed.json()} == {"main", "exp"}

    compared = client.post(
        "/api/branches/compare",
        json={"prompt_id": "demo", "branch_a": "main", "branch_b": "exp"},
    )
    assert compared.status_code == 200
    assert compared.json()["delta"]["accuracy"] == pytest.approx(0.4)


def test_test_cases_crud(client: TestClient, db_path: Path) -> None:
    """Full CRUD cycle over the test-cases endpoints."""
    created = client.post(
        "/api/test-cases",
        json={"prompt_id": "demo", "input": "hi", "expected": "hello", "tags": ["greet"]},
    )
    assert created.status_code == 201
    tc_id = created.json()["id"]

    listed = client.get("/api/test-cases", params={"prompt_id": "demo"})
    assert len(listed.json()) == 1

    toggled = client.patch(f"/api/test-cases/{tc_id}", json={"active": False})
    assert toggled.status_code == 200
    assert toggled.json()["active"] is False

    deleted = client.delete(f"/api/test-cases/{tc_id}")
    assert deleted.status_code == 204
    assert client.get("/api/test-cases", params={"prompt_id": "demo"}).json() == []


def test_test_case_toggle_not_found(client: TestClient) -> None:
    """Toggling a non-existent test case returns 404."""
    resp = client.patch("/api/test-cases/999", json={"active": False})
    assert resp.status_code == 404
