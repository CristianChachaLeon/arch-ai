"""Module A — imports from B (circular)."""
from b import bar


def foo() -> str:
    return f"foo -> {bar()}"
