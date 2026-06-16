"""Rich-based terminal formatting helpers for promptctl CLI."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.diff_engine import DiffLine
from core.eval_runner import EvalResult
from storage.branches import Branch
from storage.commits import Commit

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Commit helpers
# ---------------------------------------------------------------------------


def short_id(commit_id: str) -> str:
    """Return the 7-character short hash used for display."""
    return commit_id[:7]


def _score_color(delta: float) -> str:
    """Map a score delta to a Rich colour string (green/red/yellow)."""
    if delta > 0.005:
        return "green"
    if delta < -0.005:
        return "red"
    return "yellow"


def print_commit_row(commit: Commit, scores: dict[str, float] | None = None) -> None:
    """
    Print a single compact commit summary line to stdout.

    Includes the short hash, message, and optionally inline score values.
    """
    sid = short_id(commit.id)
    score_parts = ""
    if scores:
        score_parts = "  " + "  ".join(
            f"[cyan]{m}[/cyan] {v:.0%}" for m, v in sorted(scores.items())
        )
    console.print(f"[bold yellow]{sid}[/bold yellow]  {commit.message}{score_parts}")


def print_log_table(commits: list[Commit], scores_by_id: dict[str, dict[str, float]]) -> None:
    """
    Render a Rich table listing commits with their eval scores.

    Args:
        commits:      List of commits to display, newest first.
        scores_by_id: Mapping of commit id → {metric: value} for score columns.
    """
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("hash", style="yellow", no_wrap=True)
    table.add_column("message")
    table.add_column("model", style="dim")
    table.add_column("date", style="dim", no_wrap=True)
    table.add_column("scores")

    for commit in commits:
        scores = scores_by_id.get(commit.id, {})
        score_str = "  ".join(f"{m}: {v:.0%}" for m, v in sorted(scores.items()))
        table.add_row(
            short_id(commit.id),
            commit.message,
            commit.model,
            commit.created_at[:16],
            score_str or "—",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Score diff helpers
# ---------------------------------------------------------------------------


def print_score_diff(
    results: list[EvalResult],
    parent_scores: dict[str, float] | None = None,
) -> None:
    """
    Print a table of eval results with deltas vs the parent commit.

    For latency, a negative delta (improvement) is coloured green.
    For all other metrics, a positive delta is coloured green.

    Args:
        results:       EvalResult list from the latest eval run.
        parent_scores: Optional {metric: value} dict for the parent commit.
    """
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("metric", style="cyan")
    table.add_column("score", justify="right")
    table.add_column("delta", justify="right")
    table.add_column("cases", justify="right", style="dim")

    for r in results:
        score_str = f"{r.value:.2%}" if r.metric != "latency" else f"{r.value:.2f}s"
        delta_str = ""
        delta_style = ""
        if parent_scores and r.metric in parent_scores:
            delta = r.value - parent_scores[r.metric]
            sign = "+" if delta >= 0 else ""
            if r.metric == "latency":
                delta_str = f"{sign}{delta:.2f}s"
                delta_style = _score_color(-delta)  # lower latency is better
            else:
                delta_str = f"{sign}{delta:.2%}"
                delta_style = _score_color(delta)
        table.add_row(
            r.metric,
            score_str,
            Text(delta_str, style=delta_style),
            str(r.n_cases),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Diff panel
# ---------------------------------------------------------------------------


def print_diff_panel(
    diff_lines: list[DiffLine],
    delta: dict[str, float],
    from_ref: str,
    to_ref: str,
) -> None:
    """
    Render a Rich panel showing line-level diff and score delta table.

    Added lines are green, removed lines are red, context lines are dim.
    Score deltas are shown below the diff panel with directional colouring.

    Args:
        diff_lines: Output of ``core.diff_engine.line_diff``.
        delta:      Score deltas from ``core.diff_engine.score_delta``.
        from_ref:   Human-readable label for the base commit.
        to_ref:     Human-readable label for the target commit.
    """
    text = Text()
    for line in diff_lines:
        if line.type == "add":
            text.append(f"+ {line.content}\n", style="green")
        elif line.type == "remove":
            text.append(f"- {line.content}\n", style="red")
        else:
            text.append(f"  {line.content}\n", style="dim")

    console.print(Panel(text, title=f"[bold]{from_ref}[/bold] → [bold]{to_ref}[/bold]"))

    if delta:
        console.print()
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("metric", style="cyan")
        table.add_column("delta", justify="right")
        for metric, d in sorted(delta.items()):
            sign = "+" if d >= 0 else ""
            val = f"{sign}{d:.2%}" if metric != "latency" else f"{sign}{d:.2f}s"
            color = _score_color(-d if metric == "latency" else d)
            table.add_row(metric, Text(val, style=color))
        console.print(table)


# ---------------------------------------------------------------------------
# Branch table
# ---------------------------------------------------------------------------


def print_branch_table(branches: list[Branch], current: str) -> None:
    """
    Render the list of branches, marking the active one with an asterisk.

    Args:
        branches: List of Branch objects to display.
        current:  Name of the currently active branch.
    """
    for branch in branches:
        prefix = "* " if branch.name == current else "  "
        tip = branch.head_id[:7] if branch.head_id else "—"
        console.print(f"{prefix}[bold]{branch.name}[/bold]  [dim]{tip}[/dim]")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def success(msg: str) -> None:
    """Print a green success message to stdout."""
    console.print(f"[green]✓[/green] {msg}")


def error(msg: str) -> None:
    """Print a red error message to stderr."""
    err_console.print(f"[red]✗[/red] {msg}")


def warn(msg: str) -> None:
    """Print a yellow warning message to stdout."""
    console.print(f"[yellow]⚠[/yellow] {msg}")
