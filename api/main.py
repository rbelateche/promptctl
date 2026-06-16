"""FastAPI application root for promptctl."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import branches, commits, diff, scores, test_cases

app = FastAPI(
    title="promptctl API",
    description="REST API for the promptctl prompt-versioning system.",
    version="0.1.0",
)

# CORS — allow the local Vite dev server and any same-origin request
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(commits.router, prefix="/api")
app.include_router(diff.router, prefix="/api")
app.include_router(scores.router, prefix="/api")
app.include_router(branches.router, prefix="/api")
app.include_router(test_cases.router, prefix="/api")

# Serve the built React UI if it exists
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")


@app.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    """Return a simple liveness response used by load-balancers and CI checks."""
    return {"status": "ok"}
