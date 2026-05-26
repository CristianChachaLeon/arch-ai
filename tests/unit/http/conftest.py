"""Pytest configuration for HTTP unit tests."""

import os

# Allow unsafe repo paths in tests so validation doesn't block test fixtures.
# Without this, BlastRadiusRequest.validate_repo_path (and any other
# repo_path validator) rejects paths when ARCHAI_ALLOWED_REPO_ROOT is not set.
os.environ.setdefault("ARCHAI_ALLOW_UNSAFE_REPO_ROOT", "true")
