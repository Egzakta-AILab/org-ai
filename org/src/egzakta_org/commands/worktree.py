"""`org worktree …` — coordinated git worktrees across the workspace.

Each ticket gets one worktree per affected repo at ``<repo>/.worktrees/nw-NNN/``
on branch ``$LINEAR_HANDLE/nw-NNN``. A soft Linear claim (one comment with a
recognisable marker prefix) blocks two devs from grabbing the same ticket.

The point of this primitive: multiple agent sessions can work on different
tickets in parallel without branch/file collisions, and a single ticket spanning
several repos gets coordinated worktrees in each.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..atlas import AtlasError, AtlasIndex, load_atlas
from ..linear import LinearAPIError, fetch_issue, find_claim_comment, post_comment
from ..manifest import Manifest, Repo, load_manifest
from ..workspace import find_workspace_root

app = typer.Typer(no_args_is_help=True, help="Coordinated git worktrees across the workspace.")
console = Console()

_TICKET_RE = re.compile(r"^(?P<prefix>[A-Z][A-Z0-9]+)-(?P<num>\d+)$")
_CLAIM_MARKER_PREFIX = "🔒 org-worktree: claimed by"
_DEFAULT_FALLBACK_REPO = "notewell"


# --- helpers --------------------------------------------------------------


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _parse_ticket(raw: str) -> tuple[str, int, str]:
    """Validate ``NW-NNN`` shape. Returns ``(prefix, number, normalised-lower)``."""
    match = _TICKET_RE.match(raw.strip().upper())
    if not match:
        raise typer.BadParameter(
            f"ticket id must look like NW-123 (got {raw!r})"
        )
    prefix = match.group("prefix")
    num = int(match.group("num"))
    return prefix, num, f"{prefix.lower()}-{num}"


def _linear_handle() -> str:
    handle = os.environ.get("LINEAR_HANDLE", "").strip()
    if not handle:
        raise typer.BadParameter(
            "$LINEAR_HANDLE not set — needed to name the branch and the claim. "
            "Add `export LINEAR_HANDLE=<your-linear-handle>` to your shell rc."
        )
    return handle


def _worktree_path(repo_root: Path, ticket_lower: str) -> Path:
    return repo_root / ".worktrees" / ticket_lower


def _branch_name(handle: str, ticket_lower: str) -> str:
    return f"{handle}/{ticket_lower}"


def _ensure_gitignore(repo_root: Path) -> None:
    """Idempotently append ``.worktrees/`` to the repo's .gitignore."""
    gi = repo_root / ".gitignore"
    needle = ".worktrees/"
    if gi.is_file():
        existing = gi.read_text(encoding="utf-8")
        for line in existing.splitlines():
            if line.strip() == needle or line.strip() == ".worktrees":
                return
        suffix = "" if existing.endswith("\n") else "\n"
        gi.write_text(existing + suffix + needle + "\n", encoding="utf-8")
    else:
        gi.write_text(needle + "\n", encoding="utf-8")


def _repo_root(workspace_root: Path, repo: Repo) -> Path:
    return workspace_root / repo.name


def _branch_exists(repo_root: Path, branch: str) -> bool:
    result = _git(["rev-parse", "--verify", f"refs/heads/{branch}"], cwd=repo_root)
    return result.returncode == 0


def _worktree_state(worktree: Path) -> tuple[str, str]:
    """Return ``(branch, tree-status)`` for an existing worktree."""
    branch_res = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree)
    branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "?"
    porcelain = _git(["status", "--porcelain"], cwd=worktree)
    if porcelain.returncode != 0:
        tree = "?"
    elif not porcelain.stdout.strip():
        tree = "clean"
    else:
        tree = f"{len(porcelain.stdout.splitlines())} changed"
    return branch, tree


def _resolve_repos_from_atlas(
    api_key: str,
    ticket_full: str,
    manifest: Manifest,
) -> tuple[list[Repo], list[str], dict | None]:
    """Fetch the ticket, parse ``atlas:<node-id>`` labels, and resolve to repos
    via each atlas node's ``code_refs``.

    Returns ``(repos, atlas_node_ids, issue)``. ``issue`` is the Linear payload
    (id, identifier, …) or ``None`` if the API call failed in a recoverable way.
    """
    try:
        issue = fetch_issue(api_key, ticket_full)
    except LinearAPIError as exc:
        console.print(f"  [yellow]Linear lookup failed:[/] {exc} (continuing without atlas auto-detect)")
        return [], [], None
    if issue is None:
        console.print(f"  [yellow]Linear ticket {ticket_full} not found — continuing without atlas auto-detect[/]")
        return [], [], None

    label_names = [lab["name"] for lab in (issue.get("labels") or {}).get("nodes", [])]
    atlas_ids = [name[len("atlas:"):] for name in label_names if name.startswith("atlas:")]
    if not atlas_ids:
        return [], [], issue

    try:
        index: AtlasIndex = load_atlas()
    except AtlasError as exc:
        console.print(f"  [yellow]Could not load atlas:[/] {exc}")
        return [], atlas_ids, issue

    repo_names: list[str] = []
    seen: set[str] = set()
    for node_id in atlas_ids:
        node = index.by_id.get(node_id)
        if node is None:
            console.print(f"  [yellow]atlas:{node_id} not found in atlas (ignoring)[/]")
            continue
        for ref in node.frontmatter.get("code_refs") or []:
            first_segment = str(ref).split("/", 1)[0]
            if first_segment in manifest.repos and first_segment not in seen:
                seen.add(first_segment)
                repo_names.append(first_segment)

    repos = [manifest.repos[name] for name in repo_names]
    return repos, atlas_ids, issue


def _resolve_target_repos(
    *,
    explicit: list[str] | None,
    ticket_full: str,
    manifest: Manifest,
    api_key: str | None,
) -> tuple[list[Repo], dict | None]:
    """Apply the precedence rules: explicit > atlas-derived > default-repo fallback."""
    if explicit:
        try:
            return manifest.select(names=explicit), None
        except KeyError as exc:
            raise typer.BadParameter(str(exc)) from None

    if api_key:
        repos, _atlas_ids, issue = _resolve_repos_from_atlas(api_key, ticket_full, manifest)
        if repos:
            return repos, issue
        if issue is not None:
            console.print(
                f"  [yellow]No atlas-derived repos for {ticket_full}[/] — "
                f"falling back to {_DEFAULT_FALLBACK_REPO}"
            )
            fallback = manifest.repos.get(_DEFAULT_FALLBACK_REPO)
            return ([fallback] if fallback else []), issue

    console.print(
        f"  [yellow]No --repos and no Linear lookup possible[/] — "
        f"defaulting to {_DEFAULT_FALLBACK_REPO}"
    )
    fallback = manifest.repos.get(_DEFAULT_FALLBACK_REPO)
    return ([fallback] if fallback else []), None


# --- commands -------------------------------------------------------------


@app.command("create")
def create(
    ticket: str = typer.Argument(..., help="Ticket id, e.g. NW-456."),
    repos: list[str] | None = typer.Option(
        None, "--repos", "-r",
        help="Override repo selection. Comma-separated or repeat the flag.",
    ),
    no_claim: bool = typer.Option(
        False, "--no-claim", help="Skip the Linear claim comment."
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Override an existing claim by another dev.",
    ),
) -> None:
    """Create worktrees for a ticket across one or more repos."""
    _prefix, _num, ticket_lower = _parse_ticket(ticket)
    ticket_full = ticket.strip().upper()
    handle = _linear_handle()
    branch = _branch_name(handle, ticket_lower)

    workspace_root = find_workspace_root()
    manifest = load_manifest(workspace_root)

    repo_names = _flatten(repos)
    api_key = os.environ.get("LINEAR_API_KEY", "").strip() or None
    target_repos, issue = _resolve_target_repos(
        explicit=repo_names,
        ticket_full=ticket_full,
        manifest=manifest,
        api_key=api_key,
    )
    if not target_repos:
        console.print(f"[red]No target repos resolved for {ticket_full}.[/]")
        raise typer.Exit(2)

    # Soft Linear claim — only if we know the issue id (we either fetched it just
    # now in `_resolve_repos_from_atlas`, or we look it up here).
    if not no_claim and api_key:
        if issue is None:
            try:
                issue = fetch_issue(api_key, ticket_full)
            except LinearAPIError as exc:
                console.print(f"  [yellow]Skipping claim (Linear lookup failed):[/] {exc}")
                issue = None
        if issue is not None:
            claim_ok = _check_and_post_claim(
                api_key=api_key,
                issue_id=issue["id"],
                handle=handle,
                ticket_full=ticket_full,
                force=force,
            )
            if not claim_ok:
                raise typer.Exit(3)

    # Create the worktrees.
    table = Table(title=f"Worktrees for {ticket_full}")
    table.add_column("repo", style="bold")
    table.add_column("worktree")
    table.add_column("branch")
    table.add_column("status")

    rc = 0
    for repo in target_repos:
        repo_root = _repo_root(workspace_root, repo)
        if not (repo_root / ".git").exists():
            table.add_row(repo.name, "—", branch, "[red]repo not cloned[/]")
            rc |= 1
            continue
        wt_path = _worktree_path(repo_root, ticket_lower)
        if wt_path.exists():
            table.add_row(repo.name, str(wt_path.relative_to(workspace_root)), branch, "[yellow]exists[/]")
            continue

        _ensure_gitignore(repo_root)

        if _branch_exists(repo_root, branch):
            result = _git(["worktree", "add", str(wt_path), branch], cwd=repo_root)
        else:
            # Branch off the repo's current HEAD (usually `main`).
            result = _git(["worktree", "add", "-b", branch, str(wt_path)], cwd=repo_root)

        if result.returncode != 0:
            stderr = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown error"
            table.add_row(repo.name, str(wt_path.relative_to(workspace_root)), branch, f"[red]{stderr}[/]")
            rc |= 1
        else:
            table.add_row(repo.name, str(wt_path.relative_to(workspace_root)), branch, "[green]created[/]")

    console.print(table)
    raise typer.Exit(1 if rc else 0)


@app.command("list")
def list_worktrees(
    ticket: str | None = typer.Option(None, "--ticket", "-t", help="Filter to one ticket id."),
    repo: list[str] | None = typer.Option(None, "--repo", "-r", help="Filter to one or more repos."),
) -> None:
    """List active worktrees across the workspace."""
    workspace_root = find_workspace_root()
    manifest = load_manifest(workspace_root)
    repo_names = _flatten(repo)
    selected = manifest.select(names=repo_names) if repo_names else list(manifest.repos.values())

    ticket_filter: str | None = None
    if ticket:
        _p, _n, ticket_filter = _parse_ticket(ticket)

    table = Table(title="org worktrees")
    table.add_column("ticket", style="bold")
    table.add_column("repo")
    table.add_column("path")
    table.add_column("branch")
    table.add_column("tree")

    rows = 0
    for r in selected:
        wt_root = _repo_root(workspace_root, r) / ".worktrees"
        if not wt_root.is_dir():
            continue
        for child in sorted(wt_root.iterdir()):
            if not child.is_dir():
                continue
            ticket_name = child.name
            if ticket_filter and ticket_name != ticket_filter:
                continue
            branch_, tree_ = _worktree_state(child)
            tree_style = "green" if tree_ == "clean" else "yellow"
            table.add_row(
                ticket_name.upper(),
                r.name,
                str(child.relative_to(workspace_root)),
                branch_,
                f"[{tree_style}]{tree_}[/]",
            )
            rows += 1

    if rows == 0:
        console.print("[dim]No active worktrees.[/]")
        raise typer.Exit(0)
    console.print(table)


@app.command("drop")
def drop(
    ticket: str = typer.Argument(..., help="Ticket id, e.g. NW-456."),
    force: bool = typer.Option(False, "--force", help="Drop even if a worktree is dirty."),
) -> None:
    """Remove every worktree for a ticket. Refuses on dirty trees unless --force."""
    _p, _n, ticket_lower = _parse_ticket(ticket)
    workspace_root = find_workspace_root()
    manifest = load_manifest(workspace_root)

    dirty: list[tuple[str, Path]] = []
    matches: list[tuple[Repo, Path]] = []
    for repo in manifest.repos.values():
        repo_root = _repo_root(workspace_root, repo)
        wt = _worktree_path(repo_root, ticket_lower)
        if not wt.exists():
            continue
        matches.append((repo, wt))
        _, tree_ = _worktree_state(wt)
        if tree_ != "clean":
            dirty.append((repo.name, wt))

    if not matches:
        console.print(f"[dim]No worktrees found for {ticket.upper()}.[/]")
        raise typer.Exit(0)

    if dirty and not force:
        console.print(f"[red]Refusing to drop — these worktrees have uncommitted changes:[/]")
        for name, path in dirty:
            console.print(f"  • {name}: {path.relative_to(workspace_root)}")
        console.print("[dim]Re-run with --force to drop anyway (changes will be lost).[/]")
        raise typer.Exit(2)

    rc = 0
    for repo, wt in matches:
        repo_root = _repo_root(workspace_root, repo)
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(wt))
        result = _git(args, cwd=repo_root)
        if result.returncode != 0:
            console.print(f"  [red]{repo.name}: {result.stderr.strip()}[/]")
            rc |= 1
        else:
            console.print(f"  [green]dropped[/] {repo.name}: {wt.relative_to(workspace_root)}")
    raise typer.Exit(1 if rc else 0)


# --- internals ------------------------------------------------------------


def _flatten(values: list[str] | None) -> list[str] | None:
    """Comma-split + dedupe (Typer hands us multi-value as a list)."""
    if not values:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in value.split(","):
            stripped = part.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                out.append(stripped)
    return out or None


def _check_and_post_claim(
    *,
    api_key: str,
    issue_id: str,
    handle: str,
    ticket_full: str,
    force: bool,
) -> bool:
    """Return True if the claim is ours (newly posted or pre-existing), False if blocked."""
    try:
        existing = find_claim_comment(api_key, issue_id, _CLAIM_MARKER_PREFIX, since_hours=24)
    except LinearAPIError as exc:
        console.print(f"  [yellow]Could not check existing claim:[/] {exc} (skipping claim)")
        return True

    if existing is not None:
        body = existing.get("body", "")
        if f"@{handle}" in body:
            # Already ours — idempotent re-claim.
            console.print(f"  [dim]existing claim by @{handle} found — proceeding[/]")
            return True
        if not force:
            other = ""
            for token in body.split():
                if token.startswith("@"):
                    other = token
                    break
            console.print(
                f"[red]{ticket_full} already claimed by {other or 'another dev'}[/] "
                f"(comment {existing.get('id')}). Use --force to override."
            )
            return False
        console.print(f"  [yellow]overriding existing claim ({existing.get('id')})[/]")

    body = (
        f"{_CLAIM_MARKER_PREFIX} @{handle} at "
        f"{datetime.now(tz=timezone.utc).isoformat(timespec='seconds')}. "
        f"Drop with: `org worktree drop {ticket_full}`"
    )
    try:
        post_comment(api_key, issue_id, body)
        console.print(f"  [green]claimed[/] {ticket_full} as @{handle}")
    except LinearAPIError as exc:
        console.print(f"  [yellow]Could not post claim:[/] {exc} (continuing anyway)")
    return True
