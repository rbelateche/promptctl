"""promptctl diff — show line diff and score delta between two commits."""

from __future__ import annotations

import typer

from cli import output
from cli.config import load_config
from core.commit_engine import resolve_ref
from core.diff_engine import diff_commits
from storage.db import init_db


def diff(
    from_ref: str = typer.Argument("HEAD~1", help="From commit ref (e.g. HEAD~1, abc1234)"),
    to_ref: str = typer.Argument("HEAD", help="To commit ref (default: HEAD)"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch context for HEAD refs"),
) -> None:
    """Show diff between two commits."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    try:
        from_commit = resolve_ref(ref=from_ref, prompt_id=cfg.name, branch=branch, db_path=db_path)
        to_commit = resolve_ref(ref=to_ref, prompt_id=cfg.name, branch=branch, db_path=db_path)
    except (KeyError, ValueError) as exc:
        output.error(str(exc))
        raise typer.Exit(1)

    diff_lines, delta = diff_commits(from_commit=from_commit, to_commit=to_commit, db_path=db_path)

    output.print_diff_panel(diff_lines, delta, from_ref, to_ref)
