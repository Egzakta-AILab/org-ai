"""`org user …` — workspace user profiles (init, show, list, validate)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from ..atlas import AtlasError, load_atlas
from ..users.bootstrap import BootstrapError, init_profile
from ..users.loader import load_all_users, load_user
from ..workspace import find_workspace_root

app = typer.Typer(no_args_is_help=True, help="Per-developer profiles (preferences, ownership).")
console = Console()


@app.command("init")
def init_cmd(
    handle: str | None = typer.Option(
        None, "--handle", "-h",
        help="Override the auto-suggested short handle (default: displayName.lower().split()[0]).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the YAML without writing."),
) -> None:
    """Create a profile stub from Linear viewer + git log. Refuses if it exists."""
    try:
        path, rendered = init_profile(short_handle_override=handle, dry_run=dry_run)
    except BootstrapError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(2) from None

    root = find_workspace_root()
    rel = path.relative_to(root)
    if dry_run:
        console.print(f"[bold]Would write[/] {rel}:")
        console.print(Syntax(rendered, "yaml", theme="ansi_dark"))
    else:
        console.print(f"[green]wrote[/] {rel}")
        console.print(
            "\nRun [bold]/profile-me[/] in a Claude session to fill in the TODOs "
            "(role, areas, owns, learning, preferences)."
        )


@app.command("show")
def show_cmd(
    handle: str = typer.Argument(..., help="Short handle (filename in platform/profiles/)."),
    field: str | None = typer.Option(
        None, "--field", "-f",
        help="Print a single dotted field (e.g. `preferences.grill_depth`). Exits 0 on hit, 1 on miss.",
    ),
) -> None:
    """Show a profile's full YAML — or one dotted field via --field."""
    profile = load_user(handle)
    if profile is None:
        console.print(f"[red]No profile at platform/profiles/{handle}.yaml[/]")
        raise typer.Exit(1)
    if field:
        value = profile.field_at(field)
        if value is None:
            raise typer.Exit(1)
        typer.echo(value)
        return
    assert profile.path is not None
    console.print(Syntax(profile.path.read_text(encoding="utf-8"), "yaml", theme="ansi_dark"))


@app.command("list")
def list_cmd() -> None:
    """Tabular view of every registered profile."""
    users = load_all_users()
    if not users:
        console.print(f"[dim]No profiles yet — run `org user init` to create one.[/]")
        raise typer.Exit(0)

    table = Table(title=f"workspace profiles ({len(users)})")
    table.add_column("handle", style="bold")
    table.add_column("display name")
    table.add_column("linear handle")
    table.add_column("role")
    table.add_column("owns", justify="right")
    table.add_column("learning", justify="right")
    for handle in sorted(users):
        p = users[handle]
        table.add_row(
            p.handle,
            p.display_name or "—",
            p.linear.handle or "—",
            p.role or "—",
            str(len(p.owns)),
            str(len(p.learning)),
        )
    console.print(table)


@app.command("validate")
def validate_cmd(
    strict: bool = typer.Option(
        False, "--strict",
        help="Promote info-level findings (e.g. atlas owners without profiles) to errors.",
    ),
) -> None:
    """Schema check + cross-reference against atlas owners."""
    users = load_all_users()
    issues: list[tuple[str, str]] = []  # (severity, message)
    valid_roles = {"junior", "mid", "senior", "staff", "pm", ""}
    valid_depths = {"shallow", "medium", "deep"}
    valid_styles = {"terse", "balanced", "explanatory"}
    valid_detail = {"low", "medium", "high"}

    for profile in users.values():
        loc = f"profiles/{profile.handle}.yaml"
        if profile.role not in valid_roles:
            issues.append(("error", f"{loc}: role={profile.role!r} not in {sorted(valid_roles)}"))
        if profile.preferences.grill_depth not in valid_depths:
            issues.append(("error", f"{loc}: preferences.grill_depth={profile.preferences.grill_depth!r}"))
        if profile.preferences.review_style not in valid_styles:
            issues.append(("error", f"{loc}: preferences.review_style={profile.preferences.review_style!r}"))
        if profile.preferences.handoff_detail not in valid_detail:
            issues.append(("error", f"{loc}: preferences.handoff_detail={profile.preferences.handoff_detail!r}"))
        if not profile.linear.handle:
            issues.append(("warning", f"{loc}: linear.handle empty — bootstrap incomplete"))

    # Cross-reference: atlas owners with no profile
    try:
        index = load_atlas()
    except AtlasError:
        index = None
    if index is not None:
        all_owners: set[str] = set()
        for node in index.nodes:
            owners = node.frontmatter.get("owners") or []
            if isinstance(owners, list):
                for o in owners:
                    if isinstance(o, str):
                        all_owners.add(o)
        missing = sorted(all_owners - set(users))
        for handle in missing:
            issues.append((
                "info",
                f"atlas owner @{handle} has no profile — run `org user init` as that dev"
            ))

    errors = [m for sev, m in issues if sev == "error"]
    warnings = [m for sev, m in issues if sev == "warning"]
    infos = [m for sev, m in issues if sev == "info"]

    for m in errors:
        console.print(f"  [red]error[/]   {m}")
    for m in warnings:
        console.print(f"  [yellow]warning[/] {m}")
    for m in infos:
        console.print(f"  [dim]info[/]    {m}")

    if errors or (strict and (warnings or infos)):
        raise typer.Exit(1)
    if not issues:
        console.print(f"[green]all {len(users)} profile(s) valid; atlas owners covered[/]")
