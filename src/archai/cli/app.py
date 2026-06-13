"""ArchAI CLI - Architecture-aware AI coding assistant.

Provides commands for MCP server integration and project initialization.
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(name="archai", help="Architecture-aware AI coding assistant")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        typer.echo(f"archai-mcp v{version('archai-mcp')}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Architecture-aware AI coding assistant."""
    pass


@app.command()
def serve():
    """Start ArchAI in MCP server mode (stdio, for AI agents)."""
    from archai.mcp_server import mcp as mcp_app

    mcp_app.run(transport="stdio")


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to configure"),
    agent: str = typer.Option(
        "opencode",
        "--agent",
        help="AI coding assistant to configure (opencode, gemini, claude, cursor, all)",
    ),
):
    """Initialize archai MCP server for an AI coding assistant.

    Creates the agent-specific config file so it can discover and call
    archai's architecture tools in this project.
    """
    from archai.cli.adapters import resolve_adapters

    project_path = Path(project_dir).resolve()

    # Warn about old config files that OpenCode ignores
    old_paths = [
        project_path / ".opencode.json",
        project_path / ".opencode" / "mcp.json",
    ]
    for old in old_paths:
        if old.exists():
            relative = old.relative_to(project_path)
            typer.echo(
                typer.style(
                    f"\u26a0 Found old config file: {relative} (ignored by OpenCode)",
                    fg="yellow",
                )
            )

    adapters = resolve_adapters(agent, project_path)
    mcp_command = ["archai", "serve"]

    for adapter in adapters:
        result = adapter.write(mcp_command)
        if result is None:
            config_rel = adapter.config_path().relative_to(project_path)
            typer.echo(
                typer.style(
                    f"\u2713 archai is already configured in {config_rel}.",
                    fg="green",
                )
            )
        else:
            config_rel = result.relative_to(project_path)
            typer.echo(
                typer.style(
                    f"\u2713 Configured archai MCP server in {config_rel}",
                    fg="green",
                )
            )


@app.command()
def analyze(
    repo_path: str = typer.Argument(".", help="Path to the repository to analyze"),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON instead of pretty-print"
    ),
    clusters: bool = typer.Option(
        True, "--clusters/--no-clusters", help="Show cluster information"
    ),
    deps: bool = typer.Option(True, "--deps/--no-deps", help="Show dependency edges"),
    functions: bool = typer.Option(
        True, "--functions/--no-functions", help="Show functions and classes"
    ),
    sub_clusters: bool = typer.Option(
        True, "--sub-clusters/--no-sub-clusters", help="Show intra-file sub-clusters"
    ),
    force: bool = typer.Option(False, "--force", help="Force re-analysis, bypassing all caches"),
):
    """Analyze a repository and show its architecture."""
    import asyncio
    import json as stdjson

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree

    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator import ArchaiOrchestrator

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    with console.status(f"[bold green]Analyzing {repo.name}..."):
        try:
            middleware = ArchaiMiddleware()
            orch = ArchaiOrchestrator(middleware)
            result = asyncio.run(orch._get_pipeline_result(str(repo), force=force))
        except Exception as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error analyzing repository:[/red] {e}")
            raise typer.Exit(code=1)

    # JSON output
    if json_output:
        console.print(stdjson.dumps(result.to_dict(), indent=2))
        return

    # Summary
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column(style="white")
    summary.add_row("Files", str(result.file_count))
    summary.add_row("Dependencies", str(result.edge_count))
    summary.add_row("Clusters", str(result.cluster_count))

    console.print()
    console.print(Panel(summary, title=f"[bold]📊 {repo.name} — Architecture Overview[/bold]"))
    console.print()

    # Dependencies tree
    if deps and result.file_count > 0:
        dep_tree = Tree(f"📦 [bold]Dependency Graph ({result.edge_count} edges)[/bold]")
        for node in sorted(result.graph.graph.nodes()):
            n = result.graph.get_node(node)
            if n and n.imports:
                branch = dep_tree.add(f"  📄 [bold]{node}[/bold]")
                # Separate project imports from external (system/stdlib)
                project_imports = list(dict.fromkeys(imp for imp in n.imports if imp != "external"))
                external_count = len(n.imports) - len(project_imports)
                for imp in project_imports:
                    branch.add(f"  └> {imp}")
                if external_count:
                    branch.add(f"  [dim]└> ... and {external_count} external dependencies[/dim]")

        if dep_tree.children:
            console.print(dep_tree)
            console.print()

    # Clusters
    if clusters and result.cluster_count > 0:
        console.print(f"[bold]📁 Clusters ({result.cluster_count})[/bold]")
        cluster_table = Table(show_header=True, header_style="bold magenta")
        cluster_table.add_column("Cluster", style="cyan")
        cluster_table.add_column("Files", style="white")
        cluster_table.add_column("Key Files", style="green")

        for cname, files in sorted(result.clusters.items()):
            # Show the most "connected" files as key files
            key_files = sorted(files)[:3]
            key_str = ", ".join(key_files)
            if len(files) > 3:
                key_str += f" ... and {len(files) - 3} more"
            cluster_table.add_row(cname, str(len(files)), key_str)

        console.print(cluster_table)
        console.print()

    # Functions per file (optional)
    if functions and result.file_count > 0:
        console.print("[bold]🔧 Functions & Classes[/bold]")
        func_table = Table(show_header=True, header_style="bold magenta")
        func_table.add_column("File", style="cyan")
        func_table.add_column("Functions", style="white")
        func_table.add_column("Classes", style="yellow")

        for node in sorted(result.graph.graph.nodes()):
            n = result.graph.get_node(node)
            if n and (n.functions or n.classes):
                funcs = ", ".join(n.functions[:5]) if n.functions else "—"
                if len(n.functions) > 5:
                    funcs += " ..."
                cls = ", ".join(n.classes[:3]) if n.classes else "—"
                if len(n.classes) > 3:
                    cls += " ..."
                func_table.add_row(node, funcs, cls)

        console.print(func_table)
        console.print()

    # Sub-clusters (intra-file modules)
    if sub_clusters and result.sub_clusters:
        console.print("[bold]📦 Intra-File Modules (sub-clusters)[/bold]")
        for file_path, modules in sorted(result.sub_clusters.items()):
            sub_tree = Tree(f"📄 [bold]{file_path}[/bold]")
            for module_name, funcs in sorted(modules.items(), key=lambda x: -len(x[1])):
                short = ", ".join(funcs[:4])
                rest = f" ... +{len(funcs)-4}" if len(funcs) > 4 else ""
                sub_tree.add(f"[cyan]{module_name}[/cyan] ({len(funcs)}): {short}{rest}")
            console.print(sub_tree)
        console.print()


@app.command()
def file(
    file_path: str = typer.Argument(..., help="Path to the file to analyze (relative to repo)"),
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON instead of pretty-print"
    ),
):
    """Get detailed analysis of a single file.

    Shows functions (with line numbers and call info), classes,
    imports, dependents, and dependencies.
    """
    import asyncio
    import json as stdjson

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator import ArchaiOrchestrator

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    middleware = ArchaiMiddleware()
    orch = ArchaiOrchestrator(middleware)

    with console.status(f"[bold green]Analyzing {repo.name}..."):
        try:
            result = asyncio.run(orch.get_file_detail(str(repo), file_path))
        except ValueError as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1)

    # JSON output
    if json_output:
        console.print(stdjson.dumps(result.model_dump(), indent=2, default=str))
        return

    # Pretty-print
    # Summary
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column(style="white")
    summary.add_row("File", result.file_path)
    if result.cluster:
        summary.add_row("Cluster", result.cluster)
    summary.add_row("Functions", str(len(result.functions)))
    summary.add_row("Classes", str(len(result.classes)))

    imp_label = str(len(result.imports))
    if result.external_import_count:
        imp_label += f" (+{result.external_import_count} external)"
    summary.add_row("Imports", imp_label)

    summary.add_row("Dependents", str(len(result.dependents)))

    dep_label = str(len(result.dependencies))
    if result.external_dependency_count:
        dep_label += f" (+{result.external_dependency_count} external)"
    summary.add_row("Dependencies", dep_label)

    console.print()
    console.print(Panel(summary, title=f"[bold]📄 {result.file_path}[/bold]"))
    console.print()

    # Functions
    if result.functions:
        console.print("[bold]🔧 Functions[/bold]")
        func_table = Table(show_header=True, header_style="bold magenta")
        func_table.add_column("Name", style="green")
        func_table.add_column("Line", style="cyan")
        func_table.add_column("Calls (internal)", style="yellow")
        func_table.add_column("Calls (external)", style="blue")

        for func in result.functions:
            internal = ", ".join(func.calls_internal[:5]) if func.calls_internal else "—"
            if len(func.calls_internal) > 5:
                internal += " ..."
            external = ", ".join(func.calls_external[:5]) if func.calls_external else "—"
            if len(func.calls_external) > 5:
                external += " ..."
            func_table.add_row(func.name, str(func.line), internal, external)

        console.print(func_table)
        console.print()

    # Classes
    if result.classes:
        console.print(f"[bold]📦 Classes/Structs ({len(result.classes)})[/bold]")
        console.print(", ".join(result.classes))
        console.print()

    # Imports (only project files)
    if result.imports:
        total = len(result.imports)
        ext = f" + {result.external_import_count} external" if result.external_import_count else ""
        console.print(f"[bold]📥 Imports ({total}{ext})[/bold]")
        for imp in result.imports:
            console.print(f"  {imp}")
        console.print()

    # Dependents
    if result.dependents:
        console.print(
            f"[bold]⬆️ Dependents ({len(result.dependents)}) — files that depend on this[/bold]"
        )
        for dep in result.dependents:
            console.print(f"  {dep}")
        console.print()

    # Dependencies
    if result.dependencies or result.external_dependency_count:
        total = len(result.dependencies)
        ext = (
            f" + {result.external_dependency_count} external"
            if result.external_dependency_count
            else ""
        )
        console.print(f"[bold]⬇️ Dependencies ({total}{ext})[/bold]")
        for dep in result.dependencies:
            console.print(f"  {dep}")


@app.command()
def state(
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    var: str | None = typer.Option(None, "--var", help="Filter by variable name"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Analyze shared global state in a repository.

    Shows global variables and their declaration locations.
    Use --var to filter by variable name.
    """
    import asyncio
    import json as stdjson

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator import ArchaiOrchestrator

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    middleware = ArchaiMiddleware()
    orch = ArchaiOrchestrator(middleware)

    with console.status(f"[bold green]Analyzing shared state in {repo.name}..."):
        try:
            result = asyncio.run(orch.get_shared_state(str(repo), var))
        except Exception as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error analyzing shared state:[/red] {e}")
            raise typer.Exit(code=1)

    if json_output:
        console.print(stdjson.dumps(result.model_dump(), indent=2, default=str))
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Total:[/bold] {result.total_count} global variables"
            + (f" (filtered by '{var}')" if var else ""),
            title="[bold]🌐 Shared State Analysis[/bold]",
        )
    )
    console.print()

    if not result.variables:
        console.print("[yellow]No global variables found.[/yellow]")
        return

    var_table = Table(show_header=True, header_style="bold magenta")
    var_table.add_column("Variable", style="green")
    var_table.add_column("Declared In", style="cyan")
    var_table.add_column("Line", style="white")
    var_table.add_column("Writers", style="yellow")
    var_table.add_column("Readers", style="blue")

    for v in result.variables:
        writers = ", ".join(w.function for w in v.writers[:3]) if v.writers else "—"
        if len(v.writers) > 3:
            writers += " ..."
        readers = ", ".join(r.function for r in v.readers[:3]) if v.readers else "—"
        if len(v.readers) > 3:
            readers += " ..."
        var_table.add_row(v.name, v.declared_in, str(v.line), writers, readers)

    console.print(var_table)
    console.print()

    # Most written/read summary
    if result.most_written:
        console.print(f"[bold]✏️ Most written:[/bold] {', '.join(result.most_written)}")
    if result.most_read:
        console.print(f"[bold]📖 Most read:[/bold] {', '.join(result.most_read)}")
    console.print()


@app.command()
def context(
    query: str = typer.Argument(..., help="Context query string"),
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Get architecture context for a query.

    Analyzes the repository structure and returns cluster information,
    file dependencies, and test files relevant to the query.
    """
    import asyncio
    import json as stdjson

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from archai.mcp_server import get_architecture_context

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    with console.status(f"[bold green]Getting context for '{query}'..."):
        try:
            result = asyncio.run(get_architecture_context(query, str(repo)))
        except Exception as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1)

    try:
        data = stdjson.loads(result)
    except stdjson.JSONDecodeError:
        if json_output:
            console.print(stdjson.dumps({"error": "invalid JSON from MCP tool"}))
        else:
            console.print(
                "\n[red]✗ Error:[/red] Invalid JSON response from architecture context tool"
            )
        raise typer.Exit(code=1)

    if "error" in data:
        if json_output:
            console.print(result)
        else:
            console.print(f"\n[red]✗ Error:[/red] {data['error']}")
        raise typer.Exit(code=1)

    if json_output:
        console.print(result)
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Focus cluster:[/bold] {data['focus_cluster']}\n"
            f"[bold]Focus files:[/bold] {len(data['focus_files'])}\n"
            f"[bold]Focus reasoning:[/bold] {data['focus_reasoning']}\n"
            f"[bold]Total clusters:[/bold] {data['metadata']['cluster_count']}\n"
            f"[bold]Test files:[/bold] {len(data['test_files'])}",
            title="[bold]🔍 Architecture Context[/bold]",
        )
    )
    console.print()

    if data["focus_files"]:
        console.print(f"[bold]📁 Focus Files ({len(data['focus_files'])})[/bold]")
        for f in data["focus_files"]:
            console.print(f"  {f}")
        console.print()

    if data["cluster_edges"]:
        console.print(f"[bold]🔗 Cluster Edges ({len(data['cluster_edges'])})[/bold]")
        edge_table = Table(show_header=True, header_style="bold magenta")
        edge_table.add_column("From", style="cyan")
        edge_table.add_column("To", style="green")
        for edge in data["cluster_edges"]:
            edge_table.add_row(edge["from_cluster"], edge["to_cluster"])
        console.print(edge_table)
        console.print()

    if data["test_files"]:
        console.print(f"[bold]🧪 Test Files ({len(data['test_files'])})[/bold]")
        for f in data["test_files"]:
            console.print(f"  {f}")
        console.print()


@app.command()
def trace(
    entry_point: str = typer.Argument(..., help="Function name to start tracing from"),
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Trace a feature's call flow through the codebase.

    Starting from a function name, traces the call chain,
    global variables touched, side effects, and risks.
    """
    import asyncio
    import json as stdjson

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree

    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator import ArchaiOrchestrator

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    middleware = ArchaiMiddleware()
    orch = ArchaiOrchestrator(middleware)

    with console.status(f"[bold green]Tracing {entry_point}..."):
        try:
            result = asyncio.run(orch.trace_feature_flow(str(repo), entry_point))
        except ValueError as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1)

    if json_output:
        console.print(stdjson.dumps(result.model_dump(), indent=2, default=str))
        return

    # Pretty-print
    console.print()
    console.print(
        Panel(
            f"[bold]Entry:[/bold] {result.entry_point}\n"
            f"[bold]File:[/bold] {result.entry_file}\n"
            f"[bold]Functions traced:[/bold] {result.functions_traced}",
            title="[bold]🔍 Trace Analysis[/bold]",
        )
    )
    console.print()

    # Call chain tree
    if result.call_chain:
        console.print("[bold]📞 Call Chain[/bold]")

        def render_tree(node, tree, depth=0):
            label = f"[green]{node.function}[/green] [dim]{node.file_path}[/dim]"
            if node.line:
                label += f" [cyan]:{node.line}[/cyan]"
            branch = tree.add(label)
            for child in node.calls:
                render_tree(child, branch, depth + 1)

        tree = Tree(f"[bold]{result.entry_point}[/bold]")
        for child in result.call_chain[0].calls:
            render_tree(child, tree)
        if tree.children:
            console.print(tree)
            console.print()

    # Shared state
    if result.shared_state:
        console.print(f"[bold]📦 Shared State ({len(result.shared_state)})[/bold]")
        for var in result.shared_state:
            console.print(f"  {var}")
        console.print()

    # Side effects
    if result.side_effects:
        console.print("[bold]⚡ Side Effects[/bold]")
        se_table = Table(show_header=True, header_style="bold magenta")
        se_table.add_column("Type", style="cyan")
        se_table.add_column("Description", style="white")
        for se in result.side_effects:
            se_table.add_row(se.type, se.description)
        console.print(se_table)
        console.print()

    # Risks
    if result.risks:
        console.print("[bold]⚠️ Risks[/bold]")
        risk_table = Table(show_header=True, header_style="bold magenta")
        risk_table.add_column("Severity", style="red")
        risk_table.add_column("Description", style="white")
        for r in result.risks:
            risk_table.add_row(r.severity.upper(), r.description)
        console.print(risk_table)


@app.command()
def blast(
    file_path: str = typer.Argument(..., help="File to analyze (relative to repo)"),
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    depth: int = typer.Option(2, "--depth", help="How deep to traverse for transitive dependents"),
    function: str | None = typer.Option(
        None, "--function", help="Function name for function-level analysis"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Analyze the impact of changing a file.

    Shows direct/transitive dependents and affected subsystems.
    """
    import asyncio
    import json as stdjson

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator import ArchaiOrchestrator

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    middleware = ArchaiMiddleware()
    orch = ArchaiOrchestrator(middleware)

    with console.status(f"[bold green]Analyzing blast radius for {file_path}..."):
        try:
            result = asyncio.run(
                orch.get_blast_radius(str(repo), file_path, depth, function_name=function)
            )
        except ValueError as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1)

    if json_output:
        console.print(stdjson.dumps(result.model_dump(), indent=2, default=str))
        return

    console.print()
    console.print(
        Panel(
            f"[bold]File:[/bold] {result.focus_file}\n"
            f"[bold]Direct dependents:[/bold] {len(result.direct_dependents)}\n"
            f"[bold]Transitive dependents:[/bold] {len(result.transitive_dependents)}",
            title="[bold]💥 Blast Radius[/bold]",
        )
    )
    console.print()

    if result.direct_dependents:
        console.print("[bold]⬆️ Direct Dependents[/bold]")
        for f in result.direct_dependents:
            console.print(f"  {f}")
        console.print()

    if result.transitive_dependents:
        console.print("[bold]↗️ Transitive Dependents[/bold]")
        for f in result.transitive_dependents:
            console.print(f"  {f}")
        console.print()

    if result.subsystems_affected:
        console.print("[bold]📊 Subsystems Affected[/bold]")
        sub_table = Table(show_header=True, header_style="bold magenta")
        sub_table.add_column("Subsystem", style="cyan")
        sub_table.add_column("Files affected", style="white")
        for subsystem, count in sorted(result.subsystems_affected.items()):
            sub_table.add_row(subsystem, str(count))
        console.print(sub_table)

    if result.function_name:
        console.print(f"\n[bold]Function:[/bold] {result.function_name}")
        if result.function_dependents:
            console.print("[bold]Function dependents:[/bold]")
            for f in result.function_dependents:
                console.print(f"  {f}")
        if result.function_dependencies:
            console.print("[bold]Function dependencies:[/bold]")
            for f in result.function_dependencies:
                console.print(f"  {f}")


@app.command()
def validate(
    patch_file: str = typer.Argument(..., help="Path to a patch/diff file"),
    repo_path: str = typer.Argument(".", help="Path to the repository"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show structural context for proposed code changes.

    Reads a patch file (diff format), analyzes which files are touched,
    and returns cluster info, dependencies, and new imports.
    The agent uses this structural data to determine validity.
    """
    import asyncio
    import json as stdjson
    import re
    from pathlib import Path

    from rich.console import Console
    from rich.panel import Panel

    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator import ArchaiOrchestrator
    from archai.orchestrator.orchestrator import get_cluster_edges

    console = Console()
    repo = Path(repo_path).resolve()
    patch_path = Path(patch_file)

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    if not patch_path.exists():
        console.print(f"[red]✗ Error:[/red] Patch file not found: {patch_path}")
        raise typer.Exit(code=1)

    patch_text = patch_path.read_text()
    changes = _parse_patch_file(patch_text)

    if not changes:
        console.print("[yellow]⚠ No changes detected in patch file[/yellow]")
        raise typer.Exit(code=0)

    middleware = ArchaiMiddleware()
    orch = ArchaiOrchestrator(middleware)

    with console.status(f"[bold green]Analyzing {len(changes)} change(s)..."):
        try:
            pipeline_result = asyncio.run(orch._get_pipeline_result(str(repo)))
        except Exception as e:
            if json_output:
                console.print(stdjson.dumps({"error": str(e)}))
            else:
                console.print(f"\n[red]✗ Error:[/red] {e}")
            raise typer.Exit(code=1)

    graph = pipeline_result.graph.graph

    structural_results = []
    for change in changes:
        file_cluster = pipeline_result.get_cluster_for_file(change.file_path)
        cluster_files = list(pipeline_result.clusters.get(file_cluster, [])) if file_cluster else []

        cluster_deps = {"imports_from_cluster": [], "imported_by_clusters": []}
        if file_cluster:
            edges = [
                e
                for e in get_cluster_edges(graph, pipeline_result.clusters)
                if e.from_cluster == file_cluster or e.to_cluster == file_cluster
            ]
            for e in edges:
                if (
                    e.from_cluster == file_cluster
                    and e.to_cluster not in cluster_deps["imports_from_cluster"]
                ):
                    cluster_deps["imports_from_cluster"].append(e.to_cluster)
                if (
                    e.to_cluster == file_cluster
                    and e.from_cluster not in cluster_deps["imported_by_clusters"]
                ):
                    cluster_deps["imported_by_clusters"].append(e.from_cluster)

        added_lines = [
            line[1:]
            for line in change.patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added_text = "\n".join(added_lines)

        new_imports = re.findall(r"^(?:from\s+(\S+)\s+)?import\s+(\S+)", added_text, re.MULTILINE)
        new_import_paths = []
        for from_match, import_match in new_imports:
            if from_match:
                new_import_paths.append(from_match.replace(".", "/") + ".py")
            else:
                new_import_paths.append(import_match.replace(".", "/") + ".py")

        file_deps = {}
        if change.file_path in graph:
            file_deps[change.file_path] = sorted(graph.successors(change.file_path))

        structural_results.append(
            {
                "file_path": change.file_path,
                "file_cluster": file_cluster or "unknown",
                "cluster_files": cluster_files,
                "cluster_dependencies": cluster_deps,
                "file_dependencies": file_deps,
                "new_imports_in_patch": new_import_paths,
            }
        )

    if json_output:
        out = structural_results if len(structural_results) > 1 else structural_results[0]
        console.print(stdjson.dumps(out, indent=2, default=str))
        return

    for item in structural_results:
        console.print()
        console.print(
            Panel(
                f"[bold]File:[/bold] [cyan]{item['file_path']}[/cyan]\n"
                f"[bold]Cluster:[/bold] [yellow]{item['file_cluster']}[/yellow] "
                f"({len(item['cluster_files'])} files)",
                title="Structural Analysis",
            )
        )

        if item["new_imports_in_patch"]:
            console.print("\n[bold]New imports in patch:[/bold]")
            for imp in item["new_imports_in_patch"]:
                console.print(f"  [green]+[/green] {imp}")

        if item["cluster_dependencies"]["imports_from_cluster"]:
            console.print("\n[bold]Cluster imports to:[/bold]")
            for dep in item["cluster_dependencies"]["imports_from_cluster"]:
                console.print(f"  [blue]→[/blue] {dep}")

        if item["cluster_dependencies"]["imported_by_clusters"]:
            console.print("\n[bold]Imported by clusters:[/bold]")
            for dep in item["cluster_dependencies"]["imported_by_clusters"]:
                console.print(f"  [magenta]←[/magenta] {dep}")

        if item["file_dependencies"].get(item["file_path"]):
            console.print("\n[bold]File dependencies:[/bold]")
            for dep in item["file_dependencies"][item["file_path"]]:
                console.print(f"  [dim]{dep}[/dim]")


def _parse_patch_file(patch_text: str) -> list:
    """Parse a unified diff/patch file into ChangeItem objects."""
    from archai.models import ChangeItem

    changes: list[ChangeItem] = []
    current_file = None
    current_lines: list[str] = []

    for line in patch_text.splitlines():
        if line.startswith("--- a/"):
            continue
        if line.startswith("+++ b/"):
            # Save previous file's patch
            if current_file and current_lines:
                changes.append(
                    ChangeItem(
                        file_path=current_file,
                        patch="\n".join(current_lines),
                    )
                )
            current_file = line[6:]  # strip "+++ b/"
            current_lines = []
        elif current_file:
            current_lines.append(line)

    # Save last file
    if current_file and current_lines:
        changes.append(
            ChangeItem(
                file_path=current_file,
                patch="\n".join(current_lines),
            )
        )

    return changes





if __name__ == "__main__":
    app()
