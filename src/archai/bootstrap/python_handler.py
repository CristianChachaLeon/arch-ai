"""Python Language Handler - Implementation of the LangHandler protocol for Python.
Integrates existing ast_parser + dependency_resolver logic into a handler.
"""

from __future__ import annotations

from pathlib import Path

from archai.bootstrap.ast_parser import (
    get_classes,
    get_functions,
    get_imports,
    parse_python_file,
)
from archai.bootstrap.dependency_resolver import _resolve_single_import
from archai.bootstrap.file_discovery import PYTHON_EXCLUDED_DIRS
from archai.bootstrap.language import (
    ParsedFile,
    SHARED_EXCLUDED_DIRS,
    register_handler,
)


@register_handler
class PythonLangHandler:
    language = "python"
    extensions = frozenset({".py"})
    project_files = ("setup.py", "pyproject.toml", "setup.cfg")
    excluded_dirs: frozenset[str] = SHARED_EXCLUDED_DIRS | PYTHON_EXCLUDED_DIRS

    def is_project_root(self, path: Path) -> bool:
        return any((path / pf).exists() for pf in self.project_files)

    def parse(self, file: Path) -> ParsedFile:
        tree = parse_python_file(file)
        return ParsedFile(
            path=str(file),
            imports=get_imports(tree),
            functions=get_functions(tree),
            classes=get_classes(tree),
            language="python",
        )

    def _build_indices(self, all_files: set[str]) -> tuple[dict[str, str], dict[str, str]]:
        files_by_stem: dict[str, str] = {}
        files_by_module: dict[str, str] = {}
        for fp in all_files:
            stem = Path(fp).stem
            if stem not in files_by_stem or len(fp.split("/")) < len(
                files_by_stem[stem].split("/")
            ):
                files_by_stem[stem] = fp
            module_parts = fp.replace(".py", "").split("/")
            if module_parts[-1] == "__init__":
                module_parts = module_parts[:-1]
            for i in range(len(module_parts)):
                suffix = ".".join(module_parts[i:])
                if suffix not in files_by_module:
                    files_by_module[suffix] = fp
        return files_by_stem, files_by_module

    def resolve_import(
        self,
        import_name: str,
        file_path: str,
        all_files: set[str],
        project_root: Path,
    ) -> str | None:
        if not hasattr(self, "_cached_all_files") or self._cached_all_files is not all_files:
            self._cached_files_by_stem, self._cached_files_by_module = self._build_indices(
                all_files
            )
            self._cached_all_files = all_files

        resolved = _resolve_single_import(
            import_name, self._cached_files_by_stem, self._cached_files_by_module, file_path
        )
        if resolved and resolved in all_files:
            return resolved
        return None
