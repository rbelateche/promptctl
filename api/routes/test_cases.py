"""API routes for test case management."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from storage import test_cases as tc_storage

router = APIRouter(tags=["test-cases"])


class TestCaseOut(BaseModel):
    """Serialisable representation of a test case."""

    id: int
    prompt_id: str
    input: str
    expected: str
    tags: list[str]
    active: bool


class TestCaseCreate(BaseModel):
    """Request body for creating a new test case."""

    prompt_id: str
    input: str
    expected: str
    tags: list[str] = []


class TestCaseToggle(BaseModel):
    """Request body for enabling or disabling a test case."""

    active: bool


def _tc_out(tc) -> TestCaseOut:
    """Convert a storage ``TestCase`` to the API response model."""
    return TestCaseOut(
        id=tc.id,
        prompt_id=tc.prompt_id,
        input=tc.input,
        expected=tc.expected,
        tags=tc.tags,
        active=tc.active,
    )


@router.get("/test-cases", response_model=list[TestCaseOut])
def list_test_cases(
    prompt_id: str,
    active_only: bool = False,
    db_path: Path = Depends(get_db_path),
) -> list[TestCaseOut]:
    """
    List test cases for a prompt.

    Args:
        prompt_id:   Logical name of the prompt project.
        active_only: When True, only active (non-disabled) cases are returned.
    """
    cases = tc_storage.list_test_cases(
        prompt_id=prompt_id, active_only=active_only, db_path=db_path
    )
    return [_tc_out(tc) for tc in cases]


@router.post("/test-cases", response_model=TestCaseOut, status_code=201)
def create_test_case(
    body: TestCaseCreate,
    db_path: Path = Depends(get_db_path),
) -> TestCaseOut:
    """
    Create a new test case.

    Args:
        body: JSON payload containing ``prompt_id``, ``input``, ``expected``,
              and optionally ``tags``.
    """
    tc = tc_storage.insert_test_case(
        prompt_id=body.prompt_id,
        input=body.input,
        expected=body.expected,
        tags=body.tags or None,
        db_path=db_path,
    )
    return _tc_out(tc)


@router.patch("/test-cases/{tc_id}", response_model=TestCaseOut)
def toggle_test_case(
    tc_id: int,
    body: TestCaseToggle,
    db_path: Path = Depends(get_db_path),
) -> TestCaseOut:
    """
    Enable or disable a test case without deleting it.

    Args:
        tc_id: Primary key of the test case.
        body:  JSON payload with ``active`` boolean.

    Raises:
        404: If no test case with the given id exists.
    """
    try:
        tc = tc_storage.toggle_test_case(id=tc_id, active=body.active, db_path=db_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _tc_out(tc)


@router.delete("/test-cases/{tc_id}", status_code=204)
def delete_test_case(
    tc_id: int,
    db_path: Path = Depends(get_db_path),
) -> None:
    """
    Hard-delete a test case by id.

    Args:
        tc_id: Primary key of the test case.

    Raises:
        404: If no test case with the given id exists.
    """
    try:
        tc_storage.delete_test_case(id=tc_id, db_path=db_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
