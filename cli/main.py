"""promptctl CLI — Typer application root."""

from __future__ import annotations

import typer

from cli.commands import branch, check, commit, diff, init, log, rollback
from cli.commands import eval as eval_cmd

app = typer.Typer(
    name="promptctl",
    help="Git for prompts. Version, diff, and eval LLM prompts.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

# Register sub-commands
app.add_typer(branch.app, name="branch")
app.command("init")(init.init)
app.command("commit")(commit.commit)
app.command("log")(log.log)
app.command("diff")(diff.diff)
app.command("rollback")(rollback.rollback)
app.command("eval")(eval_cmd.eval)
app.command("check")(check.check)

if __name__ == "__main__":
    app()
