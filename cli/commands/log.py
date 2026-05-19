"""promptctl log — list commit history."""

from __future__ import annotations

import typer

from cli import output
from cli.config import load_config
from storage import scores as scores_storage
from storage.commits import list_commits
from storage.db import init_db


def log(
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to show"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max commits to display"),
) -> None:
    """Show the commit history for a branch."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    commits = list_commits(prompt_id=cfg.name, branch=branch, limit=limit, db_path=db_path)

    if not commits:
        output.console.print(f"No commits on branch [bold]{branch}[/bold] yet.")
        return

    scores_by_id = {
        c.id: scores_storage.get_scores_dict(commit_id=c.id, db_path=db_path) for c in commits
    }

    output.print_log_table(commits, scores_by_id)
