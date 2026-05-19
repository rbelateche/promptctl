"""promptctl eval — run evals manually against a commit or a file."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from cli import output
from cli.config import load_config
from core.commit_engine import resolve_ref
from core.eval_runner import EvalConfig, run_evals
from storage import scores as scores_storage
from storage.db import init_db
from storage.test_cases import bulk_insert_from_file, list_test_cases


def eval(
    commit_ref: Optional[str] = typer.Option(
        None, "--commit", "-c", help="Commit ref to eval (default: HEAD)"
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Eval an uncommitted prompt file instead"
    ),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch context"),
    model: Optional[str] = typer.Option(None, "--model", help="Override inference model"),
    no_persist: bool = typer.Option(
        False, "--no-persist", help="Print results without saving to DB"
    ),
) -> None:
    """Run the eval suite against a commit or a local prompt file."""
    cfg, root = load_config()
    db_path = root / cfg.db_path
    init_db(db_path)

    # Resolve prompt content
    if file:
        if not file.exists():
            output.error(f"File not found: {file}")
            raise typer.Exit(1)
        prompt_content = file.read_text()
        commit_id = "file:" + str(file)
        parent_scores: dict[str, float] = {}
    else:
        ref = commit_ref or "HEAD"
        try:
            target = resolve_ref(ref=ref, prompt_id=cfg.name, branch=branch, db_path=db_path)
        except (KeyError, ValueError) as exc:
            output.error(str(exc))
            raise typer.Exit(1)
        prompt_content = target.content
        commit_id = target.id
        parent_scores = scores_storage.get_scores_dict(commit_id=commit_id, db_path=db_path)

    # Load test cases
    test_cases_path = root / cfg.test_cases if cfg.test_cases else None
    if test_cases_path and test_cases_path.exists():
        bulk_insert_from_file(
            prompt_id=cfg.name, path=test_cases_path, db_path=db_path, skip_existing=True
        )

    active_cases = [tc for tc in list_test_cases(prompt_id=cfg.name, db_path=db_path) if tc.active]

    if not active_cases:
        output.warn("No active test cases found.")
        raise typer.Exit(0)

    output.console.print(f"Running eval suite ([cyan]{len(active_cases)}[/cyan] test cases)…")

    eval_cfg = EvalConfig(
        strategies=cfg.strategies,
        inference_model=model or cfg.model,
        judge_model=cfg.judge_model,
        embedding_model=cfg.embedding_model,
    )

    results = run_evals(
        commit_id=commit_id,
        prompt_content=prompt_content,
        test_cases=active_cases,
        config=eval_cfg,
        db_path=db_path,
        persist=not no_persist and not file,
    )

    output.console.print()
    output.print_score_diff(results, parent_scores or None)
