"""CLI output formatting for ArchAI.

Provides human-readable (rich) and JSON output modes for all CLI commands.
"""

from __future__ import annotations

import io
import json
from typing import Any


def _ensure_dict(data: Any) -> dict:
    """Coerce Pydantic models or dicts to a plain dict."""
    if isinstance(data, dict):
        return data
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if hasattr(data, "dict"):
        return data.dict()
    return dict(data)


def format_context_packet(data: dict, json_mode: bool) -> str:
    """Format a ContextPacket for display.

    Args:
        data: The ContextPacket data (dict or Pydantic model).
        json_mode: If True, return raw JSON.

    Returns:
        Formatted string.
    """
    d = _ensure_dict(data)

    if json_mode:
        return json.dumps(d, indent=2)

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    buf = io.StringIO()
    console = Console(file=buf, record=True, width=120)

    # Header
    console.print(
        Panel(
            f"[bold cyan]Focus:[/] {d['focus']}\n"
            f"[bold cyan]Reasoning:[/] {d['focus_reasoning']}",
            title="Architecture Context",
            border_style="cyan",
        )
    )

    # Constraints
    constraints = d.get("constraints", {})
    if isinstance(constraints, dict):
        c = constraints
    else:
        c = constraints.model_dump() if hasattr(constraints, "model_dump") else dict(constraints)

    ctable = Table(title="Constraints", show_header=True, header_style="bold magenta")
    ctable.add_column("Rule", style="dim")
    ctable.add_column("Value")

    for key, val in c.items():
        if isinstance(val, list):
            val_str = ", ".join(val) if val else "(none)"
        else:
            val_str = str(val)
        ctable.add_row(key, val_str)

    console.print(ctable)

    # Relevant files
    files = d.get("relevant_files", [])
    if files:
        ftable = Table(title="Relevant Files", show_header=True, header_style="bold green")
        ftable.add_column("Path", style="cyan")
        ftable.add_column("Reason")
        ftable.add_column("Importance", justify="right")

        for f in files:
            importance = f.get("importance", 0)
            bar = "█" * int(importance * 10) + "░" * (10 - int(importance * 10))
            ftable.add_row(f.get("path", ""), f.get("reason", ""), f"{bar} {importance:.1f}")

        console.print(ftable)

    return console.export_text()


def format_blast_radius(data: dict, json_mode: bool) -> str:
    """Format a BlastRadiusResponse for display.

    Args:
        data: The BlastRadiusResponse data (dict or Pydantic model).
        json_mode: If True, return raw JSON.

    Returns:
        Formatted string.
    """
    d = _ensure_dict(data)

    if json_mode:
        return json.dumps(d, indent=2)

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    buf = io.StringIO()
    console = Console(file=buf, record=True, width=120)

    console.print(
        Panel(
            f"[bold cyan]Focus File:[/] {d['focus_file']}",
            title="Blast Radius Analysis",
            border_style="yellow",
        )
    )

    # Direct dependents
    direct = d.get("direct_dependents", [])
    if direct:
        console.print(f"\n[bold yellow]Direct Dependents ({len(direct)}):[/]")
        for f in direct:
            console.print(f"  • {f}")
    else:
        console.print("\n[bold yellow]Direct Dependents:[/] (none)")

    # Transitive dependents
    transitive = d.get("transitive_dependents", [])
    if transitive:
        console.print(f"\n[bold yellow]Transitive Dependents ({len(transitive)}):[/]")
        for f in transitive:
            console.print(f"  • {f}")
    else:
        console.print("\n[bold yellow]Transitive Dependents:[/] (none)")

    # Subsystems affected
    subsys = d.get("subsystems_affected", {})
    if subsys:
        stbl = Table(title="Subsystems Affected", show_header=True, header_style="bold red")
        stbl.add_column("Subsystem", style="cyan")
        stbl.add_column("Files Affected", justify="right")
        for name, count in subsys.items():
            stbl.add_row(name, str(count))
        console.print(stbl)

    return console.export_text()


def format_validation(data: dict, json_mode: bool) -> str:
    """Format a ValidateChangeResponse for display.

    Args:
        data: The ValidateChangeResponse data (dict or Pydantic model).
        json_mode: If True, return raw JSON.

    Returns:
        Formatted string.
    """
    d = _ensure_dict(data)

    if json_mode:
        return json.dumps(d, indent=2)

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    buf = io.StringIO()
    console = Console(file=buf, record=True, width=120)

    valid = d.get("valid", False)
    status = "[bold green]VALID[/]" if valid else "[bold red]INVALID[/]"
    console.print(
        Panel(
            f"Status: {status}", title="Change Validation", border_style="green" if valid else "red"
        )
    )

    violations = d.get("violations", [])
    if violations:
        vtable = Table(title="Violations", show_header=True, header_style="bold red")
        vtable.add_column("File", style="cyan")
        vtable.add_column("Rule", style="yellow")
        vtable.add_column("Message")

        for v in violations:
            vtable.add_row(v.get("file", ""), v.get("rule", ""), v.get("message", ""))

        console.print(vtable)

    return console.export_text()


def format_process_result(data: dict, json_mode: bool) -> str:
    """Format a ProcessResponse for display.

    Args:
        data: The ProcessResponse data (dict or Pydantic model).
        json_mode: If True, return raw JSON.

    Returns:
        Formatted string.
    """
    d = _ensure_dict(data)

    if json_mode:
        return json.dumps(d, indent=2)

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    buf = io.StringIO()
    console = Console(file=buf, record=True, width=120)

    console.print(
        Panel(
            f"[bold cyan]Repository:[/] {d.get('repo_path', 'N/A')}\n"
            f"[bold cyan]Files:[/] {d.get('file_count', 0)}   "
            f"[bold cyan]Edges:[/] {d.get('edge_count', 0)}   "
            f"[bold cyan]Clusters:[/] {d.get('cluster_count', 0)}",
            title="Pipeline Result",
            border_style="cyan",
        )
    )

    # Cluster names if available
    clusters = d.get("clusters", {})
    cluster_names = d.get("cluster_names", {})
    if clusters:
        ctable = Table(title="Clusters", show_header=True, header_style="bold magenta")
        ctable.add_column("Cluster ID", style="cyan")
        ctable.add_column("Name")
        ctable.add_column("Files", justify="right")

        for cid, files in clusters.items():
            name = cluster_names.get(cid, "") if cluster_names else ""
            ctable.add_row(cid, name, str(len(files)))

        console.print(ctable)

    return console.export_text()
