"""promptctl init — initialise a new prompt project."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from cli import output


def init(
    name: str = typer.Option(..., "--name", "-n", help="Logical name for the prompt project"),
    model: str = typer.Option("gpt-4o", "--model", help="Default LLM model"),
    prompt_text: str = typer.Option(
        "You are a helpful assistant.", "--prompt", help="Initial prompt text"
    ),
) -> None:
    """Initialise a promptctl project in the current directory."""
    cfg_path = Path("promptctl.yaml")
    if cfg_path.exists():
        output.error("promptctl.yaml already exists. Nothing to do.")
        raise typer.Exit(1)

    prompt_file = Path("prompts") / f"{name}.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt_text)

    db_dir = Path(".promptctl")
    db_dir.mkdir(exist_ok=True)

    config: dict = {
        "name": name,
        "prompt_file": str(prompt_file),
        "model": model,
        "test_cases": "test_cases.json",
        "db_path": ".promptctl/db.sqlite",
        "evals": {
            "strategies": ["exact_match"],
            "judge_model": "gpt-4o",
            "embedding_model": "text-embedding-3-small",
        },
    }

    with cfg_path.open("w") as fh:
        yaml.dump(config, fh, default_flow_style=False, sort_keys=False)

    # Initialise the database
    from storage.db import init_db

    init_db(db_dir / "db.sqlite")

    output.success(f"Initialised project [bold]{name}[/bold]")
    output.console.print(f"  prompt file : [cyan]{prompt_file}[/cyan]")
    output.console.print("  db          : [cyan].promptctl/db.sqlite[/cyan]")
    output.console.print(f"  model       : [cyan]{model}[/cyan]")
    output.console.print()
    output.console.print(
        "Next: edit your prompt then run [bold]promptctl commit -m 'initial'[/bold]"
    )
