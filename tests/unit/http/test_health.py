"""
Tests for FastAPI health endpoint (T-004).

"""

import pytest


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_endpoint_returns_ok(self):
        """Health endpoint should return status 'ok'."""
        # Import will fail until we implement the endpoint
        from archai.http.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_endpoint_content_type_json(self):
        """Health endpoint should return JSON."""
        from archai.http.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")

        assert response.headers["content-type"] == "application/json"
