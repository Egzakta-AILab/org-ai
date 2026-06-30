"""`org atlas …` — file-tier operations on the knowledge graph."""

from __future__ import annotations

import difflib

import typer
import yaml
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

import json
from pathlib import Path

from ..atlas import AtlasError, load_atlas
from ..atlas.drift import DriftAxis, run_drift
from ..atlas.validate import validate
from ..workspace import find_workspace_root

app = typer.Typer(no_args_is_help=True, help="Knowledge-graph operations on atlas/.")
console = Console()


@app.command("list")
def list_nodes(
    type: str | None = typer.Option(None, "--type", "-t", help="Filter by type (pillar|capability|…)."),
    pillar: str | None = typer.Option(None, "--pillar", "-p", help="Filter by pillar (e.g. `search`)."),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status (shipped|wip|planned|…)."),
) -> None:
    """List atlas nodes. Filters compose with AND."""
    try:
        index = load_atlas()
    except AtlasError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from None

    nodes = index.filter(type=type, pillar=pillar, status=status)
    if not nodes:
        console.print("[yellow]No nodes match the filter.[/]")
        raise typer.Exit(0)

    table = Table(title=f"atlas nodes ({len(nodes)} of {len(index.nodes)})")
    table.add_column("id", style="bold")
    table.add_column("name")
    table.add_column("type")
    table.add_column("status")
    table.add_column("path", style="dim")
    for node in nodes:
        table.add_row(node.id, node.name, node.type, node.status or "—", node.rel_path)
    console.print(table)


@app.command("show")
def show(node_id: str = typer.Argument(..., help="Node id, e.g. `capability.search.hybrid-retrieval`.")) -> None:
    """Show a node's frontmatter and body."""
    try:
        index = load_atlas()
    except AtlasError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from None

    node = index.by_id.get(node_id)
    if node is None:
        console.print(f"[red]Node `{node_id}` not found.[/]")
        suggestions = difflib.get_close_matches(node_id, list(index.by_id), n=3)
        if suggestions:
            console.print("Did you mean:")
            for candidate in suggestions:
                console.print(f"  • {candidate}")
        raise typer.Exit(1)

    console.print(f"[bold]{node.id}[/]  [dim]{node.rel_path}[/]")
    console.print()
    fm_yaml = yaml.safe_dump(node.frontmatter, sort_keys=False, allow_unicode=True).strip()
    console.print(Syntax(fm_yaml, "yaml", theme="ansi_dark", line_numbers=False, word_wrap=True))
    console.print()
    console.print(node.body.strip() or "[dim](empty body)[/]")


@app.command("validate")
def validate_cmd(
    strict: bool = typer.Option(False, "--strict", help="Promote warnings to errors (exit 1 on any issue)."),
) -> None:
    """Check the atlas for structural and content issues.

    Exit code: 0 if only warnings (lenient default), 1 if any error
    (or any warning under --strict).
    """
    root = find_workspace_root()
    try:
        index = load_atlas()
    except AtlasError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from None

    issues = validate(index, workspace_root=root)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    if not issues:
        console.print(f"[green]atlas validate: clean[/] ({len(index.nodes)} nodes loaded)")
        raise typer.Exit(0)

    # Issue detail strings can contain `[[wikilinks]]` and other bracketed text
    # that Rich would interpret as markup; print them with markup disabled.
    def _print_issue(issue: object) -> None:
        i = issue  # type: ignore[assignment]
        console.print(f"  • {i.code}  {i.node or '?'}  —  {i.detail}", markup=False)  # type: ignore[attr-defined]

    if errors:
        console.print(f"[red]Errors ({len(errors)}):[/]")
        for issue in errors:
            _print_issue(issue)
        console.print()
    if warnings:
        console.print(f"[yellow]Warnings ({len(warnings)}):[/]")
        for issue in warnings:
            _print_issue(issue)
        console.print()

    if errors or (strict and warnings):
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command("drift")
def drift_cmd(
    axis: str | None = typer.Option(
        None,
        "--axis",
        help="Comma-separated subset of axes to run (code,linear,content). Default: all.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit findings as JSON (single document)."),
    report: Path | None = typer.Option(
        None,
        "--report",
        help="Write the JSON report to this file (in addition to stdout / table output).",
        dir_okay=False,
        writable=True,
    ),
) -> None:
    """Check whether the atlas is still in sync with reality.

    `validate` answers structural integrity (parseable, schema-correct).
    `drift` answers whether the atlas still matches the world outside it —
    code on disk, Linear projects, calendar dates. Runs three axes by
    default; scope with `--axis code,linear,content`.

    Exit code: 0 if no findings, 1 if any drift was found.
    """
    root = find_workspace_root()
    try:
        index = load_atlas()
    except AtlasError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from None

    axes_filter: list[DriftAxis] | None = None
    if axis:
        try:
            axes_filter = [DriftAxis(a.strip()) for a in axis.split(",") if a.strip()]
        except ValueError as exc:
            console.print(f"[red]Unknown axis: {exc}. Valid: code, linear, content.[/]")
            raise typer.Exit(1) from None

    drift_report = run_drift(index, workspace_root=root, axes=axes_filter)

    if report is not None:
        report.write_text(json.dumps(drift_report.to_dict(), indent=2), encoding="utf-8")

    if json_out:
        # Stdout, machine-readable. No Rich coloring — keep parseable.
        print(json.dumps(drift_report.to_dict(), indent=2))
        raise typer.Exit(1 if drift_report.has_findings else 0)

    if not drift_report.has_findings:
        axes = ", ".join(a.value for a in drift_report.axes_run) or "—"
        console.print(f"[green]atlas drift: no findings[/] ({len(index.nodes)} nodes, axes: {axes})")
        raise typer.Exit(0)

    by_axis: dict[str, list] = {}
    for finding in drift_report.findings:
        by_axis.setdefault(finding.axis.value, []).append(finding)

    for axis, findings in by_axis.items():
        table = Table(title=f"[{axis}] drift findings ({len(findings)})", show_lines=False)
        table.add_column("code", style="bold", no_wrap=True)
        table.add_column("path / node", style="cyan", overflow="fold")
        table.add_column("suggested", style="dim", overflow="fold")
        for f in findings:
            table.add_row(
                f.code,
                f.path or f.node_id or "—",
                f.suggested or "—",
            )
        console.print(table)
        console.print()

    console.print(
        f"[dim]Re-run with `org atlas drift --json` for full detail, "
        f"or `--report PATH` to save findings to a file.[/]"
    )
    raise typer.Exit(1)
