"""promptctl rollback — restore a previous prompt version."""

from __future__ import annotations

import typer

from cli import output
from cli.config import load_config
from core.commit_engine import resolve_ref, restore_commit, short_id
from storage.db import init_db


def rollback(
    ref: str = typer.Argument(..., help="Commit ref to restore (hash, HEAD~N)"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to roll back on"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Restore a previous prompt version (non-destructive — creates a new commit)."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    try:
        target = resolve_ref(ref=ref, prompt_id=cfg.name, branch=branch, db_path=db_path)
    except (KeyError, ValueError) as exc:
        output.error(str(exc))
        raise typer.Exit(1)

    output.console.print(
        f"Rolling back to [bold yellow]{short_id(target.id)}[/bold yellow]: {target.message!r}"
    )

    if not yes:
        confirmed = typer.confirm("Proceed?", default=True)
        if not confirmed:
            output.warn("Rollback cancelled.")
            raise typer.Exit(0)

    # Write restored content back to the prompt file
    prompt_file = root / cfg.prompt_file
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(target.content)

    try:
        new_commit = restore_commit(
            target_id=target.id,
            prompt_id=cfg.name,
            branch=branch,
            model=cfg.model,
            db_path=db_path,
        )
    except ValueError as exc:
        output.error(str(exc))
        raise typer.Exit(1)

    output.success(
        f"Rolled back to {short_id(target.id)!r} → new commit "
        f"[bold yellow]{short_id(new_commit.id)}[/bold yellow]"
    )
    output.console.print(f"  Prompt file restored: [cyan]{prompt_file}[/cyan]")
