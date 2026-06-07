"""ArchAI CLI - Architecture-aware AI coding assistant.

Provides commands for MCP server integration and project initialization.
"""

from __future__ import annotations

import json
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
def mcp():
    """Start ArchAI in MCP server mode (stdio, for AI agents)."""
    from archai.mcp_server import mcp as mcp_app

    mcp_app.run(transport="stdio")


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to configure"),
):
    """Initialize archai in a project for OpenCode MCP integration.

    Creates .opencode.json so OpenCode can discover and call
    archai's architecture tools in this project.
    """
    project_path = Path(project_dir).resolve()
    config_file = project_path / ".opencode.json"

    # Read existing config or start fresh
    existing = {}
    if config_file.exists():
        try:
            existing = json.loads(config_file.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    if config_file.exists():
        # Check if archai is already configured
        raw_mcp = existing.get("mcp")
        if raw_mcp is None:
            mcp_config = {}
        elif not isinstance(raw_mcp, dict):
            raise ValueError(
                f"Invalid type for 'mcp' in .opencode.json: expected dict, got {type(raw_mcp).__name__} ({raw_mcp!r})"
            )
        else:
            mcp_config = raw_mcp
        if "archai" in mcp_config:
            typer.echo(
                typer.style(
                    "✓ archai is already configured in this project.",
                    fg="green",
                )
            )
            raise typer.Exit(code=0)

    existing.setdefault("mcp", {})["archai"] = {
        "type": "local",
        "command": ["archai", "mcp"],
        "enabled": True,
    }

    config_file.write_text(json.dumps(existing, indent=2) + "\n")

    typer.echo(typer.style("✓ Configured archai MCP server in .opencode.json", fg="green"))


@app.command()
def analyze(
    repo_path: str = typer.Argument(".", help="Path to the repository to analyze"),
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
):
    """Analyze a repository and show its architecture."""
    import asyncio

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree

    from archai.middleware.pipeline import ArchaiMiddleware

    console = Console()
    repo = Path(repo_path).resolve()

    if not repo.is_dir():
        console.print(f"[red]✗ Error:[/red] {repo} is not a directory")
        raise typer.Exit(code=1)

    with console.status(f"[bold green]Analyzing {repo.name}..."):
        try:
            result = asyncio.run(ArchaiMiddleware().process(str(repo)))
        except Exception as e:
            console.print(f"\n[red]✗ Error analyzing repository:[/red] {e}")
            raise typer.Exit(code=1)

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
                for imp in n.imports:
                    branch.add(f"  └> {imp}")

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


if __name__ == "__main__":
    app()
