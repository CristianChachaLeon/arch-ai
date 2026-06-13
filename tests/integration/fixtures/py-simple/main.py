"""Simple module with functions, globals, and stdlib imports."""
import os
import sys

DEBUG = True
counter = 0
config = {"verbose": False}


def greet(name: str) -> str:
    return f"Hello, {name}"


def increment(amount: int = 1) -> int:
    global counter
    counter += amount
    return counter


def main() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO")
    print(greet("world"))
    print(f"Counter: {increment()}")
    return None
