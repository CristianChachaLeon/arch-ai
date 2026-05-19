"""FastAPI application for ArchAI.

Main HTTP service with middleware integration.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from archai.config.logging import setup_logging
from archai.middleware import ArchaiMiddleware

setup_logging()

app = FastAPI(title="ArchAI", version="0.1.0")

# Initialize middleware (singleton)
middleware = ArchaiMiddleware()


class ProcessRequest(BaseModel):
    repo_path: str


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
