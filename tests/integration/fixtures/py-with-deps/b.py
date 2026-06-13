"""Module B — imports from A (circular)."""
from a import foo


def bar() -> str:
    return f"bar -> {foo()}"
