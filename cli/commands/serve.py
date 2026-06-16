"""promptctl serve — start the FastAPI backend with Uvicorn."""

from __future__ import annotations

import typer

from cli import output
from cli.config import load_config


def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """
    Start the promptctl FastAPI backend with Uvicorn.

    The server exposes all API routes under ``/api`` and serves the built
    React UI (if present) at ``/ui``.  Run from your project directory so
    that ``promptctl.yaml`` is discoverable.

    Examples::

        promptctl serve                  # default: 127.0.0.1:8000
        promptctl serve --port 9000
        promptctl serve --reload         # dev mode with auto-reload
    """
    try:
        import uvicorn
    except ImportError:  # pragma: no cover
        output.error("uvicorn is not installed. Run: pip install 'uvicorn[standard]'")
        raise typer.Exit(1)

    cfg, _ = load_config()
    output.console.print(
        f"Starting promptctl API  "
        f"[cyan]http://{host}:{port}[/cyan]  "
        f"project: [bold]{cfg.name}[/bold]"
    )
    output.console.print(
        f"  API docs : [cyan]http://{host}:{port}/docs[/cyan]\n"
        f"  UI       : [cyan]http://{host}:{port}/ui[/cyan]"
    )

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
