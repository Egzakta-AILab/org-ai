"""`org` — the egzakta workspace orchestration CLI."""

from __future__ import annotations

import sys

import typer

from . import __version__

# Windows consoles default to cp1252, which can't encode glyphs we print (→, …).
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
from .commands import atlas as atlas_cmd
from .commands import clone as clone_cmd
from .commands import install as install_cmd
from .commands import status as status_cmd
from .commands import user as user_cmd
from .commands import worktree as worktree_cmd

app = typer.Typer(
    help="Orchestration CLI for the egzakta multi-repo workspace.",
    no_args_is_help=True,
    add_completion=False,
)

# Reusable option declarations.
ToolOpt = typer.Option(None, "--tool", "-t", help="Tools to target (claude|cursor|droid). Repeat or comma-separate.")
ComponentOpt = typer.Option(
    None,
    "--component",
    "-c",
    help="Components (agents|standards|commands|rules|hooks|skills). Default: all.",
)
RepoOpt = typer.Option(None, "--repo", "-r", help="Target repo(s) by name. Repeat or comma-separate.")
TagOpt = typer.Option(None, "--tags", help="Target repos by tag. Repeat or comma-separate.")


def _split(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    out: list[str] = []
    for value in values:
        out.extend(part.strip() for part in value.split(",") if part.strip())
    return out or None


@app.command()
def install(
    tool: list[str] | None = ToolOpt,
    component: list[str] | None = ComponentOpt,
    repo: list[str] | None = RepoOpt,
    tags: list[str] | None = TagOpt,
    is_global: bool = typer.Option(
        False,
        "--global",
        help="Install workspace skills into ~/.<tool>/skills/ (skips file components).",
    ),
    check: bool = typer.Option(False, "--check", help="Report drift without writing; non-zero exit if any."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be written, then stop."),
) -> None:
    """Render platform sources into each tool's native files."""
    code = install_cmd.install(
        tools=_split(tool),
        components=_split(component),
        repos=_split(repo),
        tags=_split(tags),
        is_global=is_global,
        check=check,
        dry_run=dry_run,
    )
    raise typer.Exit(code)


@app.command()
def clone(
    repo: list[str] | None = RepoOpt,
    tags: list[str] | None = TagOpt,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the clone/fetch plan, then stop."),
) -> None:
    """Clone missing repos and fast-forward existing ones, per the manifest."""
    code = clone_cmd.clone(repos=_split(repo), tags=_split(tags), dry_run=dry_run)
    raise typer.Exit(code)


@app.command()
def status(
    repo: list[str] | None = RepoOpt,
    tags: list[str] | None = TagOpt,
) -> None:
    """Show per-repo git state across the workspace."""
    code = status_cmd.status(repos=_split(repo), tags=_split(tags))
    raise typer.Exit(code)


app.add_typer(atlas_cmd.app, name="atlas", help="Knowledge-graph operations on atlas/.")
app.add_typer(worktree_cmd.app, name="worktree", help="Coordinated git worktrees across the workspace.")
app.add_typer(user_cmd.app, name="user", help="Per-developer profiles (preferences, ownership).")


@app.command()
def version() -> None:
    """Print the org CLI version."""
    typer.echo(f"org {__version__}")


if __name__ == "__main__":
    app()
