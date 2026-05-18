"""promptctl branch — create, list, switch, and compare branches."""

from __future__ import annotations

import typer

from cli import output
from cli.config import load_config
from core.diff_engine import score_delta
from storage import branches as branches_storage
from storage import scores as scores_storage
from storage.db import init_db

app = typer.Typer(help="Manage prompt branches.", no_args_is_help=True)


@app.command("create")
def branch_create(
    name: str = typer.Argument(..., help="Branch name to create"),
) -> None:
    """Create a new branch from the current HEAD."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    try:
        from storage.commits import get_head

        head = get_head(prompt_id=cfg.name, branch="main", db_path=db_path)
        branches_storage.create_branch(
            name=name,
            prompt_id=cfg.name,
            head_id=head.id if head else None,
            db_path=db_path,
        )
    except ValueError as exc:
        output.error(str(exc))
        raise typer.Exit(1)

    output.success(f"Branch [bold]{name}[/bold] created.")


@app.command("list")
def branch_list() -> None:
    """List all branches."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    branches = branches_storage.list_branches(prompt_id=cfg.name, db_path=db_path)
    if not branches:
        output.console.print("No branches yet.")
        return

    # Current branch is read from config (could be extended to store in promptctl.yaml)
    output.print_branch_table(branches, current="main")


@app.command("compare")
def branch_compare(
    branch_a: str = typer.Argument(..., help="First branch"),
    branch_b: str = typer.Argument(..., help="Second branch"),
) -> None:
    """Compare eval scores between two branches (HEAD of each)."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    from storage.commits import get_head

    head_a = get_head(prompt_id=cfg.name, branch=branch_a, db_path=db_path)
    head_b = get_head(prompt_id=cfg.name, branch=branch_b, db_path=db_path)

    if not head_a:
        output.error(f"No commits on branch {branch_a!r}.")
        raise typer.Exit(1)
    if not head_b:
        output.error(f"No commits on branch {branch_b!r}.")
        raise typer.Exit(1)

    scores_a = scores_storage.get_scores_dict(commit_id=head_a.id, db_path=db_path)
    scores_b = scores_storage.get_scores_dict(commit_id=head_b.id, db_path=db_path)
    delta = score_delta(scores_a, scores_b)

    from rich.table import Table

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("metric", style="cyan")
    table.add_column(branch_a, justify="right")
    table.add_column(branch_b, justify="right")
    table.add_column("delta", justify="right")

    all_metrics = sorted(set(scores_a) | set(scores_b))
    for metric in all_metrics:
        a_val = scores_a.get(metric, 0.0)
        b_val = scores_b.get(metric, 0.0)
        d = delta.get(metric, 0.0)
        sign = "+" if d >= 0 else ""
        if metric == "latency":
            delta_str = f"{sign}{d:.2f}s"
        else:
            delta_str = f"{sign}{d:.2%}"

        from rich.text import Text

        color = "green" if d > 0.005 else ("red" if d < -0.005 else "yellow")
        table.add_row(
            metric,
            f"{a_val:.2%}" if metric != "latency" else f"{a_val:.2f}s",
            f"{b_val:.2%}" if metric != "latency" else f"{b_val:.2f}s",
            Text(delta_str, style=color),
        )

    output.console.print(table)
