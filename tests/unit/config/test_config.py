"""Tests for config/__init__.py (repo path validation)."""

import pytest


class TestValidateRepoPath:
    """Tests for validate_repo_path."""

    def test_validates_path_within_repo(self, tmp_path, monkeypatch):
        """A path within the repo root should be accepted."""
        from archai.config import validate_repo_path

        project = tmp_path / "myproject"
        project.mkdir()

        monkeypatch.setattr("archai.config.detect_repo_root", lambda: str(tmp_path.resolve()))

        result = validate_repo_path(str(project))
        assert result == str(project.resolve())

    def test_rejects_path_outside_repo(self, tmp_path, monkeypatch):
        """A path outside the repo root should raise ValueError."""
        from archai.config import validate_repo_path

        outer = tmp_path / "outer"
        outer.mkdir()
        inner = tmp_path / "inner"
        inner.mkdir()

        monkeypatch.setattr("archai.config.detect_repo_root", lambda: str(inner.resolve()))

        with pytest.raises(ValueError, match="repo_path must be within"):
            validate_repo_path(str(outer))

    def test_resolves_relative_paths(self, tmp_path, monkeypatch):
        """Relative paths should be resolved before comparison."""
        from archai.config import validate_repo_path

        project = tmp_path / "myproject"
        project.mkdir()

        monkeypatch.setattr("archai.config.detect_repo_root", lambda: str(tmp_path.resolve()))

        result = validate_repo_path(str(project))
        assert result == str(project.resolve())

    def test_rejects_absolute_path_outside(self, tmp_path, monkeypatch):
        """Absolute paths outside the repo should still be rejected."""
        from archai.config import validate_repo_path

        other = tmp_path / "other"
        other.mkdir()
        inside = tmp_path / "inside"
        inside.mkdir()

        monkeypatch.setattr("archai.config.detect_repo_root", lambda: str(inside.resolve()))

        with pytest.raises(ValueError, match="repo_path must be within"):
            validate_repo_path(str(other))


class TestDetectRepoRoot:
    """Tests for detect_repo_root."""

    def test_detects_git_root(self, tmp_path, monkeypatch):
        """Should detect git root when in a git repo."""
        project = tmp_path / "myproject"
        project.mkdir()

        def fake_run(*args, **kw):
            return type("Result", (), {"stdout": str(project) + "\n"})()

        monkeypatch.setattr("archai.config.subprocess.run", fake_run)

        from archai.config import detect_repo_root

        assert detect_repo_root() == str(project)

    def test_fallback_to_cwd(self, monkeypatch):
        """Should fallback to CWD when git fails."""

        def fake_run(*args, **kw):
            raise Exception("not a git repo")

        monkeypatch.setattr("archai.config.subprocess.run", fake_run)

        from archai.config import detect_repo_root
        from pathlib import Path

        assert detect_repo_root() == str(Path.cwd().resolve())
