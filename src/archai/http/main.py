"""FastAPI application for ArchAI.

Main HTTP service with middleware integration.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from archai.config.logging import setup_logging
from archai.inference.llm import LiteLLMProvider
from archai.middleware import ArchaiMiddleware

setup_logging()

app = FastAPI(title="ArchAI", version="0.1.0")

# LLM model override (default: claude-sonnet-4-20250514, e.g. gemini/gemini-2.0-flash)
LLM_MODEL = os.environ.get("ARCHAI_LLM_MODEL")

# Initialize middleware (singleton)
llm_provider = LiteLLMProvider(model=LLM_MODEL) if LLM_MODEL else None
middleware = ArchaiMiddleware(llm_provider=llm_provider)

# Allowed repo root for path validation (fail-closed: must be set or override enabled)
ALLOWED_REPO_ROOT = os.environ.get("ARCHAI_ALLOWED_REPO_ROOT") or None
ALLOW_UNSAFE = os.environ.get("ARCHAI_ALLOW_UNSAFE_REPO_ROOT", "").lower() == "true"


class ProcessRequest(BaseModel):
    repo_path: str

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, v: str) -> str:
        """Validate and normalize repo_path against allowed root (fail-closed)."""
        resolved_path = Path(v).resolve()

        if ALLOWED_REPO_ROOT is not None:
            # Restrictive mode: validate against the configured root
            allowed_root = Path(ALLOWED_REPO_ROOT).resolve()
            if not resolved_path.is_relative_to(allowed_root):
                raise ValueError(
                    f"repo_path must be within allowed root: {allowed_root}. "
                    f"Got: {resolved_path}"
                )
        elif not ALLOW_UNSAFE:
            # Fail-closed: no root configured and no dev override
            raise ValueError(
                "ARCHAI_ALLOWED_REPO_ROOT is not set. "
                "Set it to a safe repo root, or set "
                "ARCHAI_ALLOW_UNSAFE_REPO_ROOT=true to allow any path (dev only)."
            )
        # else: dev override — allow any path

        return str(resolved_path)


class ProcessResponse(BaseModel):
    repo_path: str
    file_count: int
    edge_count: int
    cluster_count: int
    clusters: dict
    cluster_names: dict | None = None
    cluster_descriptions: dict | None = None
    cluster_reasonings: dict | None = None


@app.get("/health")
def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.post("/process", response_model=ProcessResponse)
async def process_repository(request: ProcessRequest) -> ProcessResponse:
    """Process a repository through the bootstrap + inference pipeline."""
    try:
        result = await middleware.process(request.repo_path)

        result_dict = result.to_dict()
        return ProcessResponse(
            repo_path=result.repo_path,
            file_count=result.file_count,
            edge_count=result.edge_count,
            cluster_count=result.cluster_count,
            clusters=result_dict["clusters"],
            cluster_names=result_dict.get("cluster_names"),
            cluster_descriptions=result_dict.get("cluster_descriptions"),
            cluster_reasonings=result_dict.get("cluster_reasonings"),
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}") from e
