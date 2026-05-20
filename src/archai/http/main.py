"""FastAPI application for ArchAI.

Main HTTP service with middleware integration.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from archai.config.logging import setup_logging
from archai.middleware import ArchaiMiddleware

setup_logging()

app = FastAPI(title="ArchAI", version="0.1.0")

# Initialize middleware (singleton)
middleware = ArchaiMiddleware()

# Allowed repo root for path validation (None = no restriction)
ALLOWED_REPO_ROOT = os.environ.get("ARCHAI_ALLOWED_REPO_ROOT")


class ProcessRequest(BaseModel):
    repo_path: str

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, v: str) -> str:
        """Validate and normalize repo_path against allowed root."""
        # Resolve the incoming path to absolute
        resolved_path = Path(v).resolve()

        if ALLOWED_REPO_ROOT is not None:
            allowed_root = Path(ALLOWED_REPO_ROOT).resolve()
            if not resolved_path.is_relative_to(allowed_root):
                raise ValueError(
                    f"repo_path must be within allowed root: {allowed_root}. "
                    f"Got: {resolved_path}"
                )

        return str(resolved_path)


class ProcessResponse(BaseModel):
    repo_path: str
    file_count: int
    edge_count: int
    cluster_count: int
    clusters: dict


@app.get("/health")
def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.post("/process", response_model=ProcessResponse)
def process_repository(request: ProcessRequest) -> ProcessResponse:
    """Process a repository through the bootstrap + inference pipeline."""
    try:
        result = middleware.process(request.repo_path)

        return ProcessResponse(
            repo_path=result.repo_path,
            file_count=result.file_count,
            edge_count=result.edge_count,
            cluster_count=result.cluster_count,
            clusters=result.to_dict()["clusters"],
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
