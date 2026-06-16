"""Shared FastAPI dependency: resolves the DB path from the nearest promptctl.yaml."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException


def _find_config_root() -> Path:
    """
    Walk up from the current working directory to find ``promptctl.yaml``.

    Mirrors the same discovery logic used by the CLI so that ``promptctl serve``
    and the FastAPI process always operate on the same database.

    Raises:
        HTTPException 503: If ``promptctl.yaml`` cannot be found.
    """
    candidate = Path.cwd()
    for _ in range(20):
        if (candidate / "promptctl.yaml").exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    raise HTTPException(
        status_code=503,
        detail="promptctl.yaml not found. Start the server from your project directory.",
    )


def get_db_path() -> Path:
    """
    FastAPI dependency that returns the SQLite database path for the current project.

    Reads ``db_path`` from ``promptctl.yaml`` relative to the project root.
    Falls back to ``.promptctl/db.sqlite`` if the key is absent.

    Usage::

        @router.get("/commits")
        def list_commits(db_path: Path = Depends(get_db_path)):
            ...
    """
    import yaml

    root = _find_config_root()
    cfg_path = root / "promptctl.yaml"
    with cfg_path.open() as fh:
        data = yaml.safe_load(fh)
    return root / data.get("db_path", ".promptctl/db.sqlite")
