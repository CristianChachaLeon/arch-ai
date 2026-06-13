"""Minimal CLI-like structure with argument parsing."""

import argparse
import sys


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample CLI")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--name", default="world", help="Name to greet")
    return parser.parse_args(args)


def greet(name: str, verbose: bool = False) -> str:
    if verbose:
        return f"Hello, {name}! (verbose mode)"
    return f"Hello, {name}!"


def main() -> None:
    args = parse_args()
    result = greet(args.name, args.verbose)
    print(result)
    sys.exit(0)


if __name__ == "__main__":
    main()
