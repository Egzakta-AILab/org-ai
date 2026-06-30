"""`org status` — per-repo git state across the workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..manifest import Manifest, load_manifest
from ..workspace import find_workspace_root, load_ignore

console = Console()


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def _repo_state(dest: Path) -> tuple[str, str, str, str]:
    """Return (branch, working-tree, ahead/behind, short-sha) for a cloned git repo."""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], dest) or "?"
    sha = _git(["rev-parse", "--short", "HEAD"], dest) or "?"
    dirty_lines = _git(["status", "--porcelain"], dest)
    tree = "clean" if not dirty_lines else f"{len(dirty_lines.splitlines())} changed"
    counts = _git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], dest)
    if counts and len(counts.split()) == 2:
        behind, ahead = counts.split()
        sync = f"+{ahead}/-{behind}" if (ahead != "0" or behind != "0") else "up-to-date"
    else:
        sync = "no upstream"
    return branch, tree, sync, sha


def _hygiene_check(root: Path, manifest: Manifest) -> tuple[list[str], list[str]]:
    """Compare workspace state against the manifest.

    Returns ``(unmanaged_dirs, broken_entries)``:
      * unmanaged_dirs — sibling git repos that aren't in the manifest and aren't
        in `.org-ignore`. These would silently differ across teammates.
      * broken_entries — manifest entries missing a `url:`. Without a URL,
        `org clone` skips them; teammates end up with a smaller workspace than
        the manifest claims. The manifest IS the contract — a URL-less entry
        breaks it.
    """
    ignore = load_ignore(root)
    sibling_repos: set[str] = set()
    for child in root.iterdir():
        # Hidden dirs (`.git`, `.cache`, etc.) and platform/org dirs aren't repos.
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / ".git").is_dir():
            sibling_repos.add(child.name)
    managed = set(manifest.repos)
    unmanaged = sorted(sibling_repos - managed - ignore)
    broken = [
        f"{repo.name} — no `url:`; teammates' `org clone` would silently skip this entry"
        for repo in manifest.repos.values()
        if not repo.cloneable
    ]
    return unmanaged, broken


def status(*, repos: list[str] | None = None, tags: list[str] | None = None) -> int:
    root = find_workspace_root()
    manifest = load_manifest(root)
    selected = manifest.select(names=repos, tags=tags)

    table = Table(title="egzakta workspace status")
    table.add_column("repo", style="bold")
    table.add_column("branch")
    table.add_column("tree")
    table.add_column("sync")
    table.add_column("HEAD")

    for repo in selected:
        dest = root / repo.name
        if not dest.exists():
            table.add_row(repo.name, "[dim]absent[/]", "", "", "")
        elif not (dest / ".git").is_dir():
            table.add_row(repo.name, "[yellow]no-git[/]", "", "", "")
        else:
            branch, tree, sync, sha = _repo_state(dest)
            tree_style = "green" if tree == "clean" else "yellow"
            table.add_row(repo.name, branch, f"[{tree_style}]{tree}[/]", sync, sha)

    console.print(table)

    # Hygiene warnings only make sense for the full workspace, not a filtered subset
    # (a teammate inspecting one repo doesn't care about siblings).
    if repos is None and tags is None:
        unmanaged, broken = _hygiene_check(root, manifest)
        if unmanaged:
            console.print()
            console.print(
                "[yellow]Sibling git repos not in repos.yaml or .org-ignore:[/] "
                "add to the manifest if they're workspace members, or to "
                "`.org-ignore` if they're personal clones."
            )
            for name in unmanaged:
                console.print(f"  • {name}")
        if broken:
            console.print()
            console.print("[red]Manifest entries that would silently diverge across teammates:[/]")
            for line in broken:
                console.print(f"  • {line}")

    return 0
