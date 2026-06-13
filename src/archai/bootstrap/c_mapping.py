"""C/C++ .c ↔ .h file mapping.

Maps implementation files (.c) to their corresponding header files (.h)
based on matching basenames in the same directory. This is used to trace
blast radius through header files: when a .c changes, its dependents
include files that include its .h counterpart.
"""

from __future__ import annotations

from pathlib import Path


def build_c_h_mapping(file_nodes: list, repo_path: str) -> dict[str, str]:
    """Build .c → .h mapping for C/C++ files.

    For each .c file, finds a matching .h file with the same basename
    in the same directory. Also maps .h → .c for reverse lookups.

    Args:
        file_nodes: List of FileNode objects from the bootstrap pipeline
        repo_path: Path to the repository root

    Returns:
        dict mapping file paths: each .c maps to its .h, and each .h maps to its .c
    """
    c_files: set[str] = set()
    h_files: set[str] = set()
    c_extensions = frozenset({".c", ".cpp", ".cc", ".cxx"})
    h_extensions = frozenset({".h", ".hpp", ".hh"})

    for node in file_nodes:
        path = node.path
        suffix = Path(path).suffix.lower()
        if suffix in c_extensions:
            c_files.add(path)
        elif suffix in h_extensions:
            h_files.add(path)

    mapping: dict[str, str] = {}

    for c_path in sorted(c_files):
        p = Path(c_path)
        stem = p.stem
        parent = str(p.parent) if p.parent != "." else ""

        for h_path in sorted(h_files):
            hp = Path(h_path)
            h_parent = str(hp.parent) if hp.parent != "." else ""
            if hp.stem == stem and h_parent == parent:
                if mapping.get(c_path) is not None:
                    break
                if mapping.get(h_path) is not None:
                    break
                mapping[c_path] = h_path
                mapping[h_path] = c_path
                break

    return mapping
