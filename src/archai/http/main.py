"""
FastAPI application for ArchAI (T-004).

Minimal implementation for health endpoint.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="ArchAI", version="0.1.0")


@app.get("/health")
def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok"}, status_code=200)