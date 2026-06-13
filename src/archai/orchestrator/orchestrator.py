"""ArchaiOrchestrator - Orchestrates bootstrap + inference + focus resolution.

This module provides the main orchestrator that connects the middleware
pipeline with focus resolution to produce architecture-aware context packets.
"""

import asyncio
import re
from collections import deque

import networkx

from archai.models import (
    BlastRadiusResponse,
    CallNode,
    ChangeItem,
    ClusterEdge,
    ContextPacket,
    FileDetailResponse,
    FileMetadata,
    FunctionDetail,
    Risk,
    SharedStateResponse,
    SharedVariable,
    SideEffect,
    StructuralContext,
    SubsystemConstraints,
    TraceFlowResponse,
    ValidateChangeResponse,
    VariableAccess,
    Violation,
)
from archai.bootstrap.graph_builder import (
    function_dependents as get_function_dependents,
    function_dependencies as get_function_dependencies,
)
from archai.models import LabeledCluster
from archai.middleware.pipeline import PipelineResult
from archai.orchestrator.focus_resolver import resolve_focus

# Regex patterns for test file detection
_TEST_FILE_PATTERNS = re.compile(r"(test_.*\.py|.*_test\.py|conftest\.py)$")

# Blocking I/O patterns to detect in patches
_BLOCKING_IO_PATTERNS = ["time.sleep", "requests.", "open(", "subprocess.", "os.system"]


def _strip_test_prefix(filename: str) -> str:
    """Strip test_ prefix or _test suffix from a filename.

    Args:
        filename: e.g. "test_routes.py" or "routes_test.py"

    Returns:
        e.g. "routes.py"
    """
    if filename.startswith("test_"):
        return filename[5:]
    if filename.endswith("_test.py"):
        return filename[: -len("_test.py")] + ".py"
    return filename


def _test_to_source_path(test_path: str) -> str:
    """Convert a test file path to its presumed source counterpart.

    "tests/api/test_routes.py"         → "src/api/routes.py"
    "src/tests/api/test_routes.py"     → "src/api/routes.py"
    "src/api/tests/test_routes.py"     → "src/api/routes.py"
    "src/api/test_routes.py"           → "src/api/routes.py"

    Args:
        test_path: Path to a test file

    Returns:
        Presumed source file path
    """
    if test_path.startswith("tests/"):
        # tests/api/test_routes.py → api/test_routes.py → src/api/routes.py
        rel = test_path[len("tests/") :]
        dir_part, filename = rel.rsplit("/", 1) if "/" in rel else ("", rel)
        source_filename = _strip_test_prefix(filename)
        return f"src/{dir_part}/{source_filename}" if dir_part else f"src/{source_filename}"

    if "/tests/" in test_path:
        # src/api/tests/test_routes.py → src/api/test_routes.py → src/api/routes.py
        # src/tests/api/test_routes.py → src/api/test_routes.py → src/api/routes.py
        rel = test_path.replace("/tests/", "/", 1)
        dir_part, filename = rel.rsplit("/", 1) if "/" in rel else ("", rel)
        source_filename = _strip_test_prefix(filename)
        return f"{dir_part}/{source_filename}"

    # Inline case: src/api/test_routes.py → src/api/routes.py
    # Already in its source location, just strip the test_ prefix
    dir_part, filename = test_path.rsplit("/", 1) if "/" in test_path else ("", test_path)
    source_filename = _strip_test_prefix(filename)
    return f"{dir_part}/{source_filename}" if dir_part else source_filename


def _find_related_test_files(
    focus_files: list[str],
    all_clusters: dict[str, list[str]],
) -> list[str]:
    """Find test files related to the focus subsystem.

    Uses cluster-aware mapping: a test file is included only if its
    derived source file belongs to the same cluster as the focus files.
    Basename matching is kept as the primary discovery mechanism, with
    cluster-aware refinement filtering out false positives.

    Args:
        focus_files: Files in the focused subsystem
        all_clusters: All clusters from the pipeline result

    Returns:
        Sorted list of related test file paths
    """
    # Build reverse mapping: file_path → cluster_id
    file_to_cluster: dict[str, str] = {}
    for cluster_id, files in all_clusters.items():
        for f in files:
            file_to_cluster[f] = cluster_id

    # Derive focus cluster from the first focus file
    focus_cluster = file_to_cluster.get(focus_files[0]) if focus_files else None

    all_files: set[str] = set()
    for files in all_clusters.values():
        all_files.update(files)

    related: list[str] = []
    for file in all_files:
        if (
            not _TEST_FILE_PATTERNS.search(file)
            and "/tests/" not in file
            and not file.startswith("tests/")
        ):
            continue

        if file.startswith("tests/"):
            file_path = file[len("tests/") :]
        elif "/tests/" in file:
            file_path = file.replace("/tests/", "/", 1)
        else:
            file_path = file
        test_name = file_path.split("/")[-1].replace(".py", "")

        # Derive source path for cluster-aware check
        source_path = _test_to_source_path(file)
        source_cluster = file_to_cluster.get(source_path)

        for focus_file in focus_files:
            focus_name = focus_file.split("/")[-1].replace(".py", "")

            # Match by basename: "routes" is a substring of "test_routes"
            if focus_name in test_name or test_name in focus_name:
                # Cluster-aware refinement: only include if source
                # cluster matches the focus cluster
                if source_cluster == focus_cluster:
                    related.append(file)
                    break

    return sorted(set(related))


def get_cluster_edges(
    graph: "networkx.DiGraph",
    clusters: dict[str, list[str]],
) -> list[ClusterEdge]:
    """Compute dependency edges between clusters.

    For each cluster, finds all imports to files in other clusters.
    Returns edges representing cross-cluster dependencies.

    Args:
        graph: NetworkX DiGraph where A→B means "A imports B"
        clusters: dict mapping cluster_id -> list of file paths

    Returns:
        List of ClusterEdge, one per (from_cluster, to_cluster) pair
    """
    # Build reverse file -> cluster mapping
    file_to_cluster: dict[str, str] = {}
    for cid, files in clusters.items():
        for f in files:
            file_to_cluster[f] = cid

    # Track edges we've already seen to avoid duplicates
    seen: set[tuple[str, str]] = set()
    edges: list[ClusterEdge] = []

    for from_cluster, files in clusters.items():
        for f in files:
            if f not in graph:
                continue
            # For each file, check what it imports (successors in graph)
            for imported in graph.successors(f):
                imported_cluster = file_to_cluster.get(imported)
                if imported_cluster and imported_cluster != from_cluster:
                    key = (from_cluster, imported_cluster)
                    if key not in seen:
                        seen.add(key)
                        edges.append(
                            ClusterEdge(
                                from_cluster=from_cluster,
                                to_cluster=imported_cluster,
                                files=[f],
                            )
                        )
                    else:
                        # Add file to existing edge
                        for edge in edges:
                            if (
                                edge.from_cluster == from_cluster
                                and edge.to_cluster == imported_cluster
                            ):
                                if f not in edge.files:
                                    edge.files.append(f)
                                break

    return edges


def get_file_dependencies(
    graph: "networkx.DiGraph",
    files: list[str] | None = None,
) -> dict[str, list[str]]:
    """Return per-file import lists.

    Maps each file to all files it imports (with resolved paths).
    Optionally filters to a specific file list.

    Args:
        graph: NetworkX DiGraph where A→B means "A imports B"
        files: Optional list of files to filter. If None, returns all.

    Returns:
        Dict mapping file path to list of imported file paths
    """
    result: dict[str, list[str]] = {}
    nodes = files if files is not None else list(graph.nodes())

    for f in nodes:
        if f in graph:
            deps = sorted(graph.successors(f))
            if deps:
                result[f] = deps

    return result


class ArchaiOrchestrator:
    """Orchestrates the bootstrap + inference + focus resolution pipeline."""

    def __init__(self, middleware):
        """Initialize with an ArchaiMiddleware instance."""
        self.middleware = middleware
        self._cache: dict[str, PipelineResult] = {}
        self._inflight: dict[str, asyncio.Task] = {}

    async def get_blast_radius(
        self, repo_path: str, file_path: str, depth: int = 2, function_name: str | None = None
    ) -> BlastRadiusResponse:
        """Analyze the blast radius of changing a file.

        Computes direct dependents (files that import the given file),
        direct dependencies (files that the given file imports),
        transitive dependents (files that indirectly depend on it),
        and a count of affected files per subsystem.

        Args:
            repo_path: Path to the repository
            file_path: The file being changed (relative to repo root)
            depth: How deep to traverse for transitive dependents (1-5)
            function_name: Optional function name for function-level blast radius analysis

        Returns:
            BlastRadiusResponse with the analysis results

        Raises:
            ValueError: If file_path is not in the dependency graph, or if
                function_name is provided but not found in the function graph
        """
        pipeline_result = await self._get_pipeline_result(repo_path)
        graph = pipeline_result.graph.graph

        if function_name is not None and pipeline_result.function_graph is not None:
            fg = pipeline_result.function_graph
            key = f"{file_path}::{function_name}"
            if key not in fg.graph:
                raise ValueError(
                    f"Function '{function_name}' not found in '{file_path}' — "
                    f"missing key '{key}' in function graph"
                )
            deps = get_function_dependencies(fg, file_path, function_name)
            dependents = get_function_dependents(fg, file_path, function_name)
            return BlastRadiusResponse(
                focus_file=file_path,
                direct_dependents=[],
                direct_dependencies=[],
                transitive_dependents=[],
                subsystems_affected={},
                function_name=function_name,
                function_dependents=dependents,
                function_dependencies=deps,
            )

        if file_path not in graph:
            raise ValueError(f"File '{file_path}' not found in dependency graph")

        direct_dependents = sorted(graph.predecessors(file_path))
        direct_dependencies = sorted(graph.successors(file_path))
        transitive = _get_transitive_dependents(graph, file_path, max_depth=depth)

        # Build file to subsystem name mapping
        file_to_subsystem = _build_file_to_subsystem(pipeline_result)

        # Count affected files per subsystem
        all_affected = set(direct_dependents) | set(transitive)
        subsystems_affected: dict[str, int] = {}
        for f in sorted(all_affected):
            sub = file_to_subsystem.get(f, "unknown")
            subsystems_affected[sub] = subsystems_affected.get(sub, 0) + 1

        return BlastRadiusResponse(
            focus_file=file_path,
            direct_dependents=direct_dependents,
            direct_dependencies=direct_dependencies,
            transitive_dependents=sorted(transitive),
            subsystems_affected=dict(sorted(subsystems_affected.items())),
        )

    async def get_file_detail(self, repo_path: str, file_path: str) -> FileDetailResponse:
        """Get detailed analysis of a single file.

        Returns functions (with calls), classes, imports, dependents,
        and dependencies for the specified file.

        Args:
            repo_path: Path to the repository
            file_path: The file to analyze (relative to repo root)

        Returns:
            FileDetailResponse with the analysis results

        Raises:
            ValueError: If file_path is not in the dependency graph
        """
        pipeline_result = await self._get_pipeline_result(repo_path)
        graph = pipeline_result.graph.graph

        if file_path not in graph:
            raise ValueError(f"File '{file_path}' not found in dependency graph")

        node = pipeline_result.graph.get_node(file_path)
        cluster = pipeline_result.get_cluster_for_file(file_path)

        dependents = sorted(graph.predecessors(file_path))
        dependencies = sorted(graph.successors(file_path))

        functions: list[FunctionDetail] = []
        if node:
            if node.functions_detail:
                # Rich detail from tree-sitter (C/C++): name, line, calls
                for func in node.functions_detail:
                    functions.append(
                        FunctionDetail(
                            name=func.name,
                            line=func.line,
                            calls_internal=list(func.calls_internal),
                            calls_external=list(func.calls_external),
                        )
                    )
            else:
                # Basic detail from AST (Python): name only
                for fname in node.functions:
                    functions.append(FunctionDetail(name=fname, line=0))

        # Separate external imports from project imports
        all_imports = sorted(node.imports) if node else []
        project_imports = [i for i in all_imports if i != "external"]
        ext_import_count = len(all_imports) - len(project_imports)

        # Separate external dependencies from project dependencies
        all_deps = sorted(dependencies) if dependencies else []
        project_deps = [d for d in all_deps if d != "external"]
        ext_dep_count = len(all_deps) - len(project_deps)

        return FileDetailResponse(
            file_path=file_path,
            cluster=cluster,
            functions=functions,
            classes=sorted(node.classes) if node else [],
            imports=project_imports,
            external_import_count=ext_import_count,
            dependents=dependents,
            dependencies=project_deps,
            external_dependency_count=ext_dep_count,
        )

    async def get_shared_state(
        self, repo_path: str, variable_filter: str | None = None
    ) -> SharedStateResponse:
        """Get shared state analysis for a repository.

        Returns all global variables with their declaration locations.
        Optionally filter by variable name.

        Args:
            repo_path: Path to the repository
            variable_filter: Optional substring filter for variable name

        Returns:
            SharedStateResponse with variables, total_count, most_written, most_read
        """
        pipeline_result = await self._get_pipeline_result(repo_path)

        all_vars: dict[str, SharedVariable] = {}

        for file_path in pipeline_result.graph.graph.nodes():
            node = pipeline_result.graph.get_node(file_path)
            if not node or not node.global_vars:
                continue

            for gvar in node.global_vars:
                name = gvar["name"]
                if name not in all_vars:
                    all_vars[name] = SharedVariable(
                        name=name,
                        declared_in=file_path,
                        line=gvar.get("line", 0),
                    )

            if node.var_access:
                for func_name, access in node.var_access.items():
                    for w in access.get("writes", []):
                        var_name = w["name"]
                        if var_name in all_vars:
                            all_vars[var_name].writers.append(
                                VariableAccess(
                                    function=func_name,
                                    file_path=file_path,
                                    line=w.get("line", 0),
                                    access_type="write",
                                )
                            )
                    for r in access.get("reads", []):
                        var_name = r["name"]
                        if var_name in all_vars:
                            all_vars[var_name].readers.append(
                                VariableAccess(
                                    function=func_name,
                                    file_path=file_path,
                                    line=r.get("line", 0),
                                    access_type="read",
                                )
                            )

        variables = list(all_vars.values())
        if variable_filter:
            variables = [v for v in variables if variable_filter.lower() in v.name.lower()]

        variables.sort(key=lambda v: v.name)

        return SharedStateResponse(
            variables=variables,
            total_count=len(variables),
            most_written=[
                v.name for v in sorted(variables, key=lambda v: len(v.writers), reverse=True)[:5]
            ],
            most_read=[
                v.name for v in sorted(variables, key=lambda v: len(v.readers), reverse=True)[:5]
            ],
        )

    async def trace_feature_flow(self, repo_path: str, entry_point: str) -> TraceFlowResponse:
        """Trace a feature/function call flow through the codebase.

        Starting from entry_point, traces the call chain through
        the function graph, collecting shared state and side effects.

        Args:
            repo_path: Path to the repository
            entry_point: Function name to start tracing from

        Returns:
            TraceFlowResponse with call chain, shared state, and risks
        """
        pipeline_result = await self._get_pipeline_result(repo_path)
        fg = pipeline_result.function_graph

        if fg is None or fg.node_count == 0:
            return TraceFlowResponse(
                entry_point=entry_point,
                functions_traced=0,
            )

        # Find the entry node — match by function name
        entry_key = None
        for key in fg.graph.nodes():
            if key.endswith(f"::{entry_point}"):
                entry_key = key
                break

        if entry_key is None:
            return TraceFlowResponse(
                entry_point=entry_point,
                functions_traced=0,
            )

        # BFS to build call chain
        visited: set[str] = set()
        side_effects: list[SideEffect] = []
        # NOTE: per-function shared state tracking is not yet implemented.
        # Once the AST layer tracks which globals each function reads/writes,
        # this should collect from function-level `writers`/`readers` instead.
        shared_state: set[str] = set()
        risks: list[Risk] = []

        def build_call_node(key: str, depth: int = 0) -> CallNode | None:
            if depth > 10 or key in visited:
                return None
            visited.add(key)

            node = fg.get_node(key)
            if node is None:
                return None

            file_path, func_name = key.split("::", 1)

            # Detect side effects from function name patterns
            se = _detect_side_effects(func_name, node)
            side_effects.extend(se)

            # Detect risks
            r = _detect_risks(func_name, node, depth)
            risks.extend(r)

            # Recursively trace callees
            children: list[CallNode] = []
            for callee_key in fg.graph.successors(key):
                child = build_call_node(callee_key, depth + 1)
                if child:
                    children.append(child)

            return CallNode(
                function=func_name,
                file_path=file_path,
                line=node.line if hasattr(node, "line") else 0,
                calls=children,
            )

        root = build_call_node(entry_key)

        return TraceFlowResponse(
            entry_point=entry_point,
            entry_file=root.file_path if root else "",
            call_chain=[root] if root else [],
            functions_traced=len(visited),
            shared_state=sorted(shared_state),
            side_effects=side_effects,
            risks=risks,
        )

    async def _get_pipeline_result(self, repo_path: str, force: bool = False) -> PipelineResult:
        """Get or process the pipeline result for a repo path.

        Uses cache and in-flight task deduplication. If the result is already
        cached, returns it. If another request is processing this repo, awaits
        that task. Otherwise, starts a new pipeline process.

        Args:
            repo_path: Path to the repository
            force: If True, bypass cache and re-process the repo
        """
        if force:
            if repo_path in self._inflight:
                self._inflight[repo_path].cancel()
                self._inflight.pop(repo_path, None)
            pipeline_result = await self.middleware.process(repo_path, force=force)
            self._cache[repo_path] = pipeline_result
            return pipeline_result

        if repo_path in self._cache:
            return self._cache[repo_path]
        if repo_path in self._inflight:
            return await self._inflight[repo_path]

        task = asyncio.ensure_future(self.middleware.process(repo_path, force=force))
        self._inflight[repo_path] = task
        try:
            pipeline_result = await task
        finally:
            self._inflight.pop(repo_path, None)
        self._cache[repo_path] = pipeline_result
        return pipeline_result

    async def validate_changes(
        self, repo_path: str, changes: list[ChangeItem]
    ) -> ValidateChangeResponse:
        """Validate proposed code changes against architectural constraints.

        For each changed file:
        - Checks if the file belongs to a known cluster
        - Checks for blocking I/O violations in async-required subsystems
        - Checks for forbidden dependency violations
        - Gracefully degrades when labeled_clusters is None
        """
        pipeline_result = await self._get_pipeline_result(repo_path)

        label_lookup: dict[str, LabeledCluster] = {}
        if pipeline_result.labeled_clusters is not None:
            for lc in pipeline_result.labeled_clusters:
                label_lookup[lc.cluster_id] = lc

        violations: list[Violation] = []

        for change in changes:
            file_path = change.file_path
            cluster_id = pipeline_result.get_cluster_for_file(file_path)

            if cluster_id is None:
                violations.append(
                    Violation(
                        file=file_path,
                        rule="unknown_file",
                        message=f"File '{file_path}' does not belong to any known cluster",
                    )
                )
                continue

            if pipeline_result.labeled_clusters is None:
                continue

            cluster = label_lookup.get(cluster_id)
            if cluster is None:
                continue

            patch = change.patch

            # Check blocking I/O patterns (async_only or no_blocking_io constraint)
            if cluster.async_only or cluster.no_blocking_io:
                for kw in _BLOCKING_IO_PATTERNS:
                    if kw in patch:
                        violations.append(
                            Violation(
                                file=file_path,
                                rule="no_blocking_io",
                                message=(
                                    f"Patch contains blocking I/O call '{kw}' "
                                    f"which is not allowed in this subsystem"
                                ),
                            )
                        )
                        break

            # Check forbidden dependencies
            if cluster.forbidden_dependencies:
                for dep in cluster.forbidden_dependencies:
                    normalized = dep.rstrip("/").replace("/", ".")
                    if re.search(
                        rf"(?m)^\s*import\s+{re.escape(normalized)}(?:\s+as\s+\w+)?(?:\s*,|\s*$|\.)",
                        patch,
                    ) or re.search(
                        rf"(?m)^\s*from\s+{re.escape(normalized)}(?:\.|\s+)import\s+",
                        patch,
                    ):
                        violations.append(
                            Violation(
                                file=file_path,
                                rule="forbidden_dependency",
                                message=f"Patch imports forbidden dependency '{dep}'",
                            )
                        )
                        break

        return ValidateChangeResponse(
            valid=len(violations) == 0,
            violations=violations,
        )

    async def get_context(self, query: str, repo_path: str, force: bool = False) -> ContextPacket:
        """Process a repo and query, return an architecture-governed ContextPacket.

        The PipelineResult is cached by repo_path so subsequent queries against
        the same repo skip the bootstrap + inference pipeline. Concurrent
        requests for the same repo are de-duplicated via an in-flight task tracker.

        Args:
            query: User query to resolve focus for
            repo_path: Path to the repository
            force: If True, bypass cache and re-process the repo
        """
        pipeline_result = await self._get_pipeline_result(repo_path, force)

        cluster_descriptions = None
        if pipeline_result.labeled_clusters is not None:
            cluster_descriptions = {
                lc.cluster_id: lc.description for lc in pipeline_result.labeled_clusters
            }

        focus, focus_reasoning = resolve_focus(
            query,
            pipeline_result.clusters,
            cluster_descriptions,
        )

        subgraph = pipeline_result.clusters.get(focus, [])

        # Find related test files across all clusters and include them
        test_files = _find_related_test_files(subgraph, pipeline_result.clusters)
        # Remove duplicates: test files already in the focus subgraph
        test_files = [tf for tf in test_files if tf not in subgraph]
        all_focus_files = list(subgraph) + test_files

        relevant_files = [
            FileMetadata(path=file, reason="part of focus subsystem", importance=1.0)
            for file in subgraph
        ]
        if test_files:
            relevant_files.extend(
                [
                    FileMetadata(path=tf, reason="related test file", importance=0.8)
                    for tf in test_files
                ]
            )

        constraints = SubsystemConstraints()
        if pipeline_result.labeled_clusters is not None:
            for lc in pipeline_result.labeled_clusters:
                if lc.cluster_id == focus:
                    constraints = SubsystemConstraints(
                        async_only=lc.async_only,
                        no_blocking_io=lc.no_blocking_io,
                        forbidden_dependencies=lc.forbidden_dependencies,
                        allowed_dependencies=lc.allowed_dependencies,
                    )
                    break

        # Map focus from cluster ID to semantic label for the response
        if pipeline_result.labeled_clusters is not None:
            for lc in pipeline_result.labeled_clusters:
                if lc.cluster_id == focus:
                    focus = lc.name
                    break

        metadata = {
            "source": "orchestrator",
            "cluster_count": len(pipeline_result.clusters),
        }

        return ContextPacket(
            focus=focus,
            focus_reasoning=focus_reasoning,
            constraints=constraints,
            subgraph=all_focus_files,
            relevant_files=relevant_files,
            metadata=metadata,
        )

    async def get_structural_context(
        self, query: str, repo_path: str, force: bool = False
    ) -> StructuralContext:
        """Process a repo and query, return rich structural data without LLM.

        Returns clusters with file lists, inter-cluster dependency edges,
        per-file dependencies, and test files. No LLM labeling involved.

        Args:
            query: User query to resolve focus for
            repo_path: Path to the repository
            force: If True, bypass cache and re-process the repo
        """
        pipeline_result = await self._get_pipeline_result(repo_path, force)

        focus, focus_reasoning = resolve_focus(
            query,
            pipeline_result.clusters,
            cluster_descriptions=None,  # No LLM labels
        )

        subgraph = pipeline_result.clusters.get(focus, [])

        # Find related test files
        test_files = _find_related_test_files(subgraph, pipeline_result.clusters)
        test_files = [tf for tf in test_files if tf not in subgraph]

        # Compute cluster edges
        edges = get_cluster_edges(pipeline_result.graph.graph, pipeline_result.clusters)

        # Compute file dependencies for focus files only
        file_deps = get_file_dependencies(pipeline_result.graph.graph, subgraph)

        metadata = {
            "source": "orchestrator",
            "cluster_count": len(pipeline_result.clusters),
        }

        return StructuralContext(
            focus_cluster=focus,
            focus_files=subgraph,
            focus_reasoning=focus_reasoning,
            all_clusters=pipeline_result.clusters,
            cluster_edges=edges,
            file_dependencies=file_deps,
            test_files=test_files,
            sub_clusters=pipeline_result.sub_clusters,
            metadata=metadata,
        )

    async def propose_change(self, repo_path: str, description: str) -> dict:
        """Suggest files affected for a desired change.

        Args:
            repo_path: Path to the repository
            description: Description of the desired change

        Returns:
            Dict with suggested files and metadata
        """
        pipeline_result = await self._get_pipeline_result(repo_path)
        keywords = description.lower().split()
        matched = []
        for file_path in pipeline_result.graph.graph.nodes():
            if file_path == "external":
                continue
            path_lower = file_path.lower()
            matches = sum(1 for kw in keywords if kw in path_lower)
            if matches > 0:
                matched.append({"file": file_path, "relevance": matches})
        matched.sort(key=lambda x: -x["relevance"])
        return {
            "description": description,
            "suggested_files": [m["file"] for m in matched],
            "total_matches": len(matched),
        }


def _get_transitive_dependents(graph, file: str, max_depth: int) -> set[str]:
    """Get files that transitively depend on file, up to max_depth.

    Uses BFS following predecessor edges (reverse of import direction).
    Only includes files at distance >= 2 (beyond direct dependents).

    Args:
        graph: NetworkX DiGraph where A→B means "A imports B"
        file: The focus file path
        max_depth: Maximum distance to traverse

    Returns:
        Set of file paths that transitively depend on the focus file
    """
    result: set[str] = set()
    visited: set[str] = {file}
    queue: deque = deque([(file, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for pred in graph.predecessors(current):
            if pred not in visited:
                visited.add(pred)
                next_depth = depth + 1
                if next_depth > 1:  # Distance >= 2 = transitive
                    result.add(pred)
                queue.append((pred, next_depth))
    return result


def _build_file_to_subsystem(pipeline_result: PipelineResult) -> dict[str, str]:
    """Build a mapping from file path to human-readable subsystem name.

    Uses labeled clusters if available, otherwise falls back to cluster IDs.

    Args:
        pipeline_result: The pipeline result with clusters and optional labels

    Returns:
        Dict mapping file path to subsystem name
    """
    file_to_subsystem: dict[str, str] = {}
    if pipeline_result.labeled_clusters:
        for lc in pipeline_result.labeled_clusters:
            for f in lc.files:
                file_to_subsystem[f] = lc.name
    else:
        for cluster_id, files in pipeline_result.clusters.items():
            for f in files:
                file_to_subsystem[f] = cluster_id
    return file_to_subsystem


def _detect_side_effects(func_name: str, node) -> list[SideEffect]:
    """Detect side effects from function name or call patterns."""
    effects = []
    name_lower = func_name.lower()

    if any(kw in name_lower for kw in ["fork", "clone"]):
        effects.append(
            SideEffect(
                type="fork",
                description=f"Process creation via {func_name}",
                line=node.line if hasattr(node, "line") else 0,
            )
        )
    if any(kw in name_lower for kw in ["exec", "spawn", "system", "popen"]):
        effects.append(
            SideEffect(
                type="exec",
                description=f"Process execution via {func_name}",
                line=node.line if hasattr(node, "line") else 0,
            )
        )
    if any(kw in name_lower for kw in ["open", "read", "write", "fopen", "fread", "fwrite"]):
        effects.append(
            SideEffect(
                type="file_io",
                description=f"File I/O via {func_name}",
                line=node.line if hasattr(node, "line") else 0,
            )
        )
    if any(kw in name_lower for kw in ["connect", "socket", "send", "recv", "listen"]):
        effects.append(
            SideEffect(
                type="network",
                description=f"Network via {func_name}",
                line=node.line if hasattr(node, "line") else 0,
            )
        )
    if any(kw in name_lower for kw in ["signal", "kill"]):
        effects.append(
            SideEffect(
                type="signal",
                description=f"Signal via {func_name}",
                line=node.line if hasattr(node, "line") else 0,
            )
        )

    return effects


def _detect_risks(func_name: str, node, depth: int) -> list[Risk]:
    """Detect risks based on function patterns."""
    risks = []
    name_lower = func_name.lower()

    if any(kw in name_lower for kw in ["fork", "clone"]):
        risks.append(
            Risk(
                severity="high", description=f"Fork in '{func_name}' — child process inherits state"
            )
        )
    if depth >= 8:
        risks.append(
            Risk(
                severity="medium",
                description=f"Deep call chain (depth {depth}) — hard to reason about",
            )
        )
    if any(kw in name_lower for kw in ["signal", "sigaction"]):
        risks.append(
            Risk(
                severity="high",
                description=f"Signal handler '{func_name}' — async-signal unsafe functions may crash",
            )
        )

    return risks
