"""promptctl commit — save a prompt version and run evals."""

from __future__ import annotations

from typing import Optional

import typer

from cli import output
from cli.config import load_config
from core.commit_engine import create_commit, short_id
from core.eval_runner import EvalConfig, run_evals
from storage import scores as scores_storage
from storage.db import init_db
from storage.test_cases import bulk_insert_from_file, list_test_cases


def commit(
    message: str = typer.Option(..., "--message", "-m", help="Commit message"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to commit to"),
    skip_eval: bool = typer.Option(False, "--skip-eval", help="Skip eval suite"),
    model: Optional[str] = typer.Option(None, "--model", help="Override model for this commit"),
) -> None:
    """Save the current prompt and run the eval suite."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    prompt_file = root / cfg.prompt_file
    if not prompt_file.exists():
        output.error(f"Prompt file not found: {prompt_file}")
        raise typer.Exit(1)

    content = prompt_file.read_text()
    effective_model = model or cfg.model

    try:
        new_commit = create_commit(
            prompt_id=cfg.name,
            branch=branch,
            content=content,
            message=message,
            model=effective_model,
            db_path=db_path,
        )
    except ValueError as exc:
        output.error(str(exc))
        raise typer.Exit(1)

    output.success(f"Commit [bold yellow]{short_id(new_commit.id)}[/bold yellow]  {message}")

    if skip_eval:
        output.warn("Eval skipped (--skip-eval)")
        return

    # Load test cases
    test_cases_path = root / cfg.test_cases if cfg.test_cases else None
    if test_cases_path and test_cases_path.exists():
        bulk_insert_from_file(
            prompt_id=cfg.name, path=test_cases_path, db_path=db_path, skip_existing=True
        )

    active_cases = [tc for tc in list_test_cases(prompt_id=cfg.name, db_path=db_path) if tc.active]

    if not active_cases:
        output.warn("No active test cases found — skipping eval. Add cases to test_cases.json.")
        return

    output.console.print(f"\nRunning eval suite ([cyan]{len(active_cases)}[/cyan] test cases)…")

    eval_cfg = EvalConfig(
        strategies=cfg.strategies,
        inference_model=effective_model,
        judge_model=cfg.judge_model,
        embedding_model=cfg.embedding_model,
    )

    results = run_evals(
        commit_id=new_commit.id,
        prompt_content=content,
        test_cases=active_cases,
        config=eval_cfg,
        db_path=db_path,
    )

    # Fetch parent scores for delta display
    parent_scores: dict[str, float] = {}
    if new_commit.parent_id:
        parent_scores = scores_storage.get_scores_dict(
            commit_id=new_commit.parent_id, db_path=db_path
        )

    output.console.print()
    output.print_score_diff(results, parent_scores or None)

    # Warn on regression
    regressions = [
        r
        for r in results
        if r.metric != "latency"
        and r.metric in parent_scores
        and r.value < parent_scores[r.metric] - 0.01
    ]
    if regressions:
        metrics = ", ".join(r.metric for r in regressions)
        output.warn(f"Regression detected: {metrics}")
        if new_commit.parent_id:
            sid = short_id(new_commit.parent_id)
            output.console.print(f"  Suggested rollback: [bold]promptctl rollback {sid}[/bold]")
