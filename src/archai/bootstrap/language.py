"""Language Handler Protocol - Interface for multi-language support.

Each language implements this protocol to provide:
- File discovery (which files to scan)
- AST parsing (extract imports, functions, classes)
- Import resolution (resolve import strings to file paths)
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ParsedFile(BaseModel):
    """Result of parsing a single file."""

    path: str
    imports: list[str]  # Raw import strings
    functions: list[str]
    classes: list[str]
    language: str  # e.g., "python", "c", "cpp"


@runtime_checkable
class LangHandler(Protocol):
    """Interface each language must implement.

    To add a new language:
    1. Create a class that implements this protocol
    2. Register it in REGISTERED_HANDLERS
    """

    language: str
    """Human-readable language name (e.g., 'python', 'c', 'cpp')."""

    extensions: frozenset[str]
    """File extensions this handler owns (e.g., frozenset({'.py'}))."""

    project_files: tuple[str, ...]
    """Project files that indicate this language is used (e.g., ('pyproject.toml',))."""

    excluded_dirs: frozenset[str]
    """Directories to exclude when discovering files."""

    def is_project_root(self, path: Path) -> bool:
        """Check if a directory looks like a project root for this language."""
        ...

    def parse(self, file: Path) -> ParsedFile:
        """Parse a file and extract imports, functions, classes."""
        ...

    def resolve_import(
        self,
        import_name: str,
        file_path: str,
        all_files: set[str],
        project_root: Path,
    ) -> str | None:
        """Resolve an import string to a relative file path.

        Args:
            import_name: Raw import string (e.g., 'os', './helpers')
            file_path: Path of the file doing the importing (relative to project_root)
            all_files: Set of all discovered file paths (relative to project_root)
            project_root: Absolute path to the repository root

        Returns:
            Resolved relative path, or None if external/unresolvable.
        """
        ...


# Shared excluded dirs (applied to ALL languages)
SHARED_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".coverage",
        "htmlcov",
        ".egg-info",
        ".gitignore",
    }
)

# Registry of all language handlers
# Populated by importing handler modules which call register_handler()
_REGISTERED_HANDLERS: dict[str, type[LangHandler]] = {}


def register_handler(handler_cls: type[LangHandler]) -> type[LangHandler]:
    """Register a language handler class.

    Called by handler modules at import time:

    ```python
    @register_handler
    class PythonLangHandler:
        ...
    ```

    Or manually:

    ```python
    register_handler(MyHandler)
    ```
    """
    lang = getattr(handler_cls, "language", None)
    if not lang:
        raise ValueError(f"Handler {handler_cls.__name__} must have a 'language' attribute")
    _REGISTERED_HANDLERS[lang] = handler_cls
    return handler_cls


def get_registered_handlers() -> dict[str, type[LangHandler]]:
    """Get all registered language handlers."""
    return dict(_REGISTERED_HANDLERS)


def detect_languages(repo: Path) -> list[LangHandler]:
    """Auto-detect which languages are used in a repository.

    Scans for project files and file extensions. Returns instantiated
    handlers for each detected language.
    """
    handlers: list[LangHandler] = []
    for handler_cls in _REGISTERED_HANDLERS.values():
        # Create instance for detection
        handler = handler_cls()  # type: ignore[call-arg]

        # Check for project files
        for pf in handler.project_files:
            if (repo / pf).exists():
                handlers.append(handler)
                break
        else:
            # Fallback: check if any files with handler extensions exist
            if any(repo.rglob(f"*{ext}") for ext in handler.extensions):
                handlers.append(handler)

    return handlers
