"""promptctl check — CI gate that exits 1 if scores fall below thresholds."""

from __future__ import annotations

from typing import Optional

import typer

from cli import output
from cli.config import load_config
from storage import scores as scores_storage
from storage.commits import get_head
from storage.db import init_db


def check(
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to check"),
    min_accuracy: Optional[float] = typer.Option(
        None, "--min-accuracy", help="Minimum required accuracy (0–1)"
    ),
    min_faithfulness: Optional[float] = typer.Option(
        None, "--min-faithfulness", help="Minimum required faithfulness (0–1)"
    ),
    max_latency: Optional[float] = typer.Option(
        None, "--max-latency", help="Maximum allowed latency in seconds"
    ),
) -> None:
    """
    CI gate: fail (exit 1) if HEAD scores are below configured thresholds.

    Thresholds can be passed as flags or read from promptctl.yaml.
    """
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    head = get_head(prompt_id=cfg.name, branch=branch, db_path=db_path)
    if not head:
        output.error(f"No commits on branch {branch!r}. Nothing to check.")
        raise typer.Exit(1)

    scores = scores_storage.get_scores_dict(commit_id=head.id, db_path=db_path)

    if not scores:
        output.warn("No eval scores found for HEAD. Run 'promptctl eval' first.")
        raise typer.Exit(0)

    # Build effective thresholds (flags override yaml)
    thresholds: dict[str, tuple[str, float]] = {}  # metric -> (direction, value)
    if min_accuracy is not None:
        thresholds["accuracy"] = ("min", min_accuracy)
    if min_faithfulness is not None:
        thresholds["faithfulness"] = ("min", min_faithfulness)
    if max_latency is not None:
        thresholds["latency"] = ("max", max_latency)

    # Fall back to yaml thresholds for any not specified via flags
    yaml_thresholds = cfg.__dict__.get("thresholds") or {}
    for metric, value in yaml_thresholds.items():
        if metric not in thresholds:
            direction = "max" if metric == "latency" else "min"
            thresholds[metric] = (direction, value)

    if not thresholds:
        output.warn(
            "No thresholds configured. Pass --min-accuracy / --min-faithfulness / --max-latency."
        )
        raise typer.Exit(0)

    failures: list[str] = []
    for metric, (direction, threshold) in thresholds.items():
        actual = scores.get(metric)
        if actual is None:
            output.warn(f"Metric {metric!r} not found in scores (skipping).")
            continue
        if direction == "min" and actual < threshold:
            failures.append(f"  {metric}: {actual:.2%} < {threshold:.2%} (required min)")
        elif direction == "max" and actual > threshold:
            failures.append(f"  {metric}: {actual:.2f}s > {threshold:.2f}s (required max)")

    from cli.output import short_id

    output.console.print(
        f"Checking commit [bold yellow]{short_id(head.id)}[/bold yellow] on [bold]{branch}[/bold]"
    )

    if failures:
        output.error("Threshold check FAILED:")
        for line in failures:
            output.err_console.print(line)
        raise typer.Exit(1)

    output.success("All thresholds passed.")
