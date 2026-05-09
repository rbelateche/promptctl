"""Diff engine — line-level diffs and score delta computation."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from storage.commits import Commit
from storage.scores import get_scores_dict


@dataclass
class DiffLine:
    type: Literal["add", "remove", "context"]
    content: str  # line text without trailing newline


def line_diff(a: str, b: str) -> list[DiffLine]:
    """
    Compute a line-level diff between two prompt strings.

    Uses ``difflib.ndiff`` to produce a human-readable, annotated diff.
    Returns a list of DiffLine objects typed as 'add', 'remove', or 'context'.
    Intra-line hint lines (starting with '? ') emitted by ndiff are omitted.
    """
    a_lines = a.splitlines()
    b_lines = b.splitlines()

    result: list[DiffLine] = []
    for raw in difflib.ndiff(a_lines, b_lines):
        tag = raw[:2]
        content = raw[2:]
        if tag == "  ":
            result.append(DiffLine(type="context", content=content))
        elif tag == "+ ":
            result.append(DiffLine(type="add", content=content))
        elif tag == "- ":
            result.append(DiffLine(type="remove", content=content))
        # Skip '? ' hint lines

    return result


def score_delta(
    from_scores: dict[str, float],
    to_scores: dict[str, float],
) -> dict[str, float]:
    """
    Compute per-metric deltas between two score dicts.

    Returns a dict of {metric: delta} for every metric present in either dict.
    Missing values are treated as 0.0.
    """
    all_metrics = set(from_scores) | set(to_scores)
    return {
        metric: to_scores.get(metric, 0.0) - from_scores.get(metric, 0.0)
        for metric in sorted(all_metrics)
    }


def diff_commits(
    *,
    from_commit: Commit,
    to_commit: Commit,
    db_path: Path,
) -> tuple[list[DiffLine], dict[str, float]]:
    """
    High-level helper: diff two Commit objects.

    Returns:
        (diff_lines, delta) where delta is {metric: float} (positive = improvement).
    """
    diff_lines = line_diff(from_commit.content, to_commit.content)
    from_scores = get_scores_dict(commit_id=from_commit.id, db_path=db_path)
    to_scores = get_scores_dict(commit_id=to_commit.id, db_path=db_path)
    delta = score_delta(from_scores, to_scores)
    return diff_lines, delta


def has_regression(delta: dict[str, float], thresholds: dict[str, float]) -> list[str]:
    """
    Return a list of metric names that crossed below a threshold (i.e. regressed).

    ``thresholds`` maps metric name to the *minimum acceptable absolute value*,
    not a delta — this is used post-diff to flag which metrics are now under threshold.
    Pass the ``to_scores`` dict along with thresholds to your caller for that check.
    """
    return [metric for metric, drop in delta.items() if drop < 0 and metric in thresholds]
