"""FastAPI application for ArchAI.

Main HTTP service with middleware integration.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from archai.config.logging import setup_logging
from archai.http.models import (
    BlastRadiusRequest,
    BlastRadiusResponse,
    ContextPacket,
    ContextRequest,
    ProcessRequest,
    ProcessResponse,
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
