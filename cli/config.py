"""Config loading for promptctl — shared between CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
import yaml


class Config:
    """Parsed promptctl.yaml values."""

    def __init__(self, data: dict) -> None:
        self.name: str = data["name"]
        self.prompt_file: Path = Path(data["prompt_file"])
        self.model: str = data.get("model", "gpt-4o")
        tc_val = data.get("test_cases")
        self.test_cases: Optional[Path] = Path(tc_val) if tc_val else None
        self.db_path: Path = Path(data.get("db_path", ".promptctl/db.sqlite"))
        evals = data.get("evals", {})
        self.strategies: list[str] = evals.get("strategies", ["exact_match"])
        self.judge_model: str = evals.get("judge_model", "gpt-4o")
        self.embedding_model: str = evals.get("embedding_model", "text-embedding-3-small")


def _find_config() -> Path:
    """Walk up directories (git-style) to find promptctl.yaml."""
    candidate = Path.cwd()
    for _ in range(20):
        cfg = candidate / "promptctl.yaml"
        if cfg.exists():
            return cfg
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    raise FileNotFoundError("promptctl.yaml not found. Run 'promptctl init' to create one.")


def load_config() -> tuple[Config, Path]:
    """
    Load promptctl.yaml and return (Config, project_root).

    Raises SystemExit with a helpful message if config is missing.
    """
    try:
        cfg_path = _find_config()
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        sys.exit(1)

    project_root = cfg_path.parent
    with cfg_path.open() as fh:
        data = yaml.safe_load(fh)

    return Config(data), project_root
