"""Focus Resolution - Tests for mapping user queries to subsystems.

This module tests the focus resolver that determines which subsystem
a user query relates to using keyword matching.
"""

from archai.orchestrator.focus_resolver import resolve_focus


class TestFocusResolution:
    """Test suite for focus resolution."""

    def test_exact_match_on_file_path(self):
        """Query 'http' should match cluster with http-related files."""
        clusters = {
            "api": ["src/api/routes.py", "src/api/http_handlers.py"],
            "core": ["src/core/engine.py"],
        }
        focus, _ = resolve_focus("http", clusters)
        assert focus == "api"

    def test_match_on_description(self):
        """Query 'authentication' should match cluster whose description mentions auth."""
        clusters = {
            "api": ["src/api/routes.py"],
            "auth": ["src/auth/login.py", "src/auth/session.py"],
        }
        descriptions = {
            "api": "HTTP API endpoints and routing",
            "auth": "Authentication and session management",
        }
        focus, _ = resolve_focus("authentication", clusters, descriptions)
        assert focus == "auth"

    def test_no_match_returns_unknown(self):
        """Unrelated query should return 'unknown'."""
        clusters = {
            "api": ["src/api/routes.py"],
        }
        focus, reasoning = resolve_focus("garbagequeryxyz", clusters)
        assert focus == "unknown"
        assert "No subsystem matched" in reasoning

    def test_multiple_clusters_best_rank_wins(self):
        """Query that partially matches multiple clusters picks the best."""
        clusters = {
            "api": ["src/api/http_routes.py", "src/api/http_handlers.py"],
            "auth": ["src/auth/login.py", "src/auth/session.py"],
        }
        focus, _ = resolve_focus("http route handler", clusters)
        assert focus == "api"

    def test_case_insensitive_matching(self):
        """'HTTP' should match 'http' files case-insensitively."""
        clusters = {
            "api": ["src/api/http_routes.py", "src/api/http_handlers.py"],
        }
        focus, _ = resolve_focus("HTTP", clusters)
        assert focus == "api"

    def test_empty_clusters(self):
        """Empty clusters dict should return unknown."""
        focus, reasoning = resolve_focus("http", {})
        assert focus == "unknown"
        assert "No subsystem matched" in reasoning

    def test_empty_query(self):
        """Empty query should return unknown."""
        clusters = {
            "api": ["src/api/routes.py"],
        }
        focus, reasoning = resolve_focus("", clusters)
        assert focus == "unknown"
        assert "No subsystem matched" in reasoning

    def test_match_on_multiple_files(self):
        """Clusters with more matching files should rank higher."""
        clusters = {
            "api": [
                "src/api/http_routes.py",
                "src/api/http_handlers.py",
                "src/api/http_client.py",
            ],
            "web": ["src/web/http_handler.py"],
        }
        focus, _ = resolve_focus("http", clusters)
        assert focus == "api"

    def test_reasoning_provides_context(self):
        """Reasoning should explain why that cluster was chosen."""
        clusters = {
            "api": ["src/api/routes.py", "src/api/http_handlers.py"],
            "core": ["src/core/engine.py"],
        }
        focus, reasoning = resolve_focus("http handler", clusters)
        assert focus == "api"
        assert "api" in reasoning.lower()
        assert "matched" in reasoning.lower()
        assert "hit" in reasoning.lower()
