"""Configuration and shared validation for the ArchAI HTTP layer.

Auto-detects the repo root via git for security-by-default path validation.
No env vars needed — zero-config security.
"""

import subprocess
from pathlib import Path


def detect_repo_root() -> str:
    """Detect the repository root directory.

    Uses ``git rev-parse --show-toplevel`` to find the repo root.
    Falls back to the current working directory if not in a git repo.

    Returns:
        Absolute path to the repo root.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return str(Path.cwd().resolve())


def validate_repo_path(v: str) -> str:
    """Validate ``repo_path`` is within the detected repo root.

    Fail-closed: if ``v`` resolves to a path outside the repo root,
    raises ``ValueError``. Always uses the auto-detected repo root
    from :func:`detect_repo_root`.

    Args:
        v: The ``repo_path`` to validate.

    Returns:
        The resolved, canonical form of ``v``.

    Raises:
        ValueError: If ``v`` is outside the detected repo root.
    """
    resolved = Path(v).resolve()
    allowed = Path(detect_repo_root()).resolve()

    if not resolved.is_relative_to(allowed):
        raise ValueError(
            f"repo_path must be within the repo root. "
            f"repo_path: {resolved}, repo_root: {allowed}"
        )

    return str(resolved)
