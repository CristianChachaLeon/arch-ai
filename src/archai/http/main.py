"""FastAPI application for ArchAI.

Main HTTP service with middleware integration.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from archai.config.logging import setup_logging
from archai.http.models import (
    BlastRadiusResponse,
    ContextPacket,
    ValidateChangeRequest,
    ValidateChangeResponse,
)
from archai.inference.llm import LiteLLMProvider
from archai.middleware import ArchaiMiddleware
from archai.orchestrator import ArchaiOrchestrator

load_dotenv()

setup_logging()

app = FastAPI(title="ArchAI", version="0.1.0")

# LLM model override (default: claude-sonnet-4-20250514, e.g. gemini/gemini-2.0-flash)
LLM_MODEL = os.environ.get("ARCHAI_LLM_MODEL")

# Initialize middleware (singleton)
llm_provider = LiteLLMProvider(model=LLM_MODEL) if LLM_MODEL else None
middleware = ArchaiMiddleware(llm_provider=llm_provider)
orchestrator = ArchaiOrchestrator(middleware)


def _validate_repo_path(v: str) -> str:
    """Validate repo_path against allowed root (fail-closed).

    Shared validator used by ContextRequest, ProcessRequest, and BlastRadiusRequest.
    Reads env vars at call time so tests can use monkeypatch instead of reimporting.
    """
    resolved_path = Path(v).resolve()
    allowed_root = os.environ.get("ARCHAI_ALLOWED_REPO_ROOT")
    allow_unsafe = os.environ.get("ARCHAI_ALLOW_UNSAFE_REPO_ROOT", "").lower() == "true"

    if allowed_root is not None:
        allowed_root_path = Path(allowed_root).resolve()
        if not resolved_path.is_relative_to(allowed_root_path):
            raise ValueError(
                f"repo_path must be within allowed root: {allowed_root_path}. "
                f"Got: {resolved_path}"
            )
    elif not allow_unsafe:
        raise ValueError(
            "ARCHAI_ALLOWED_REPO_ROOT is not set. "
            "Set it to a safe repo root, or set "
            "ARCHAI_ALLOW_UNSAFE_REPO_ROOT=true to allow any path (dev only)."
        )

    return str(resolved_path)


class ContextRequest(BaseModel):
    query: str
    repo_path: str

    validate_repo_path = field_validator("repo_path")(_validate_repo_path)


class ProcessRequest(BaseModel):
    repo_path: str

    validate_repo_path = field_validator("repo_path")(_validate_repo_path)


class ProcessResponse(BaseModel):
    repo_path: str
    file_count: int
    edge_count: int
    cluster_count: int
    clusters: dict
    cluster_names: dict | None = None
    cluster_descriptions: dict | None = None
    cluster_reasonings: dict | None = None


class BlastRadiusRequest(BaseModel):
    repo_path: str
    file_path: str
    depth: int = 2

    validate_repo_path = field_validator("repo_path")(_validate_repo_path)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        if not v.endswith(".py"):
            raise ValueError("file_path must be a Python file (.py)")
        return v

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("depth must be between 1 and 5")
        return v


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


@app.post("/context", response_model=ContextPacket)
async def get_context(request: ContextRequest) -> ContextPacket:
    """Resolve architecture context for a query against a repository."""
    try:
        packet = await orchestrator.get_context(request.query, request.repo_path)
        return packet
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context resolution error: {str(e)}") from e


@app.post("/validate-change", response_model=ValidateChangeResponse)
async def validate_change(request: ValidateChangeRequest) -> ValidateChangeResponse:
    """Validate proposed code changes against architectural constraints."""
    try:
        repo_path = ProcessRequest.validate_repo_path(request.repo_path)
        result = await orchestrator.validate_changes(repo_path, request.changes)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}") from e


@app.post("/blast-radius", response_model=BlastRadiusResponse)
async def get_blast_radius(request: BlastRadiusRequest) -> BlastRadiusResponse:
    """Analyze the blast radius of changing a file."""
    try:
        result = await orchestrator.get_blast_radius(
            request.repo_path, request.file_path, request.depth
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blast radius error: {str(e)}") from e
