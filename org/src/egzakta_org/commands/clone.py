"""`org clone` — clone or update every repo in the manifest.

Clones missing repos, fast-forwards existing git repos, and refuses to touch a directory
that exists but is not a git repo (never clobber local work).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

from ..manifest import load_manifest
from ..workspace import find_workspace_root

console = Console()


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def clone(*, repos: list[str] | None = None, tags: list[str] | None = None, dry_run: bool = False) -> int:
    root = find_workspace_root()
    manifest = load_manifest(root)
    selected = manifest.select(names=repos, tags=tags)

    rc = 0
    for repo in selected:
        dest = root / repo.name
        if not repo.cloneable:
            console.print(f"  [dim]skip[/] {repo.name}: local-only (no url in manifest)")
            continue
        if (dest / ".git").is_dir():
            if dry_run:
                console.print(f"  [cyan]would fetch[/] {repo.name}")
                continue
            result = _git(["fetch", "--prune"], cwd=dest)
            status = "[green]fetched[/]" if result.returncode == 0 else "[red]fetch failed[/]"
            console.print(f"  {status} {repo.name}")
            rc |= result.returncode
        elif dest.exists():
            console.print(f"  [yellow]skip[/] {repo.name}: directory exists but is not a git repo")
        else:
            if dry_run:
                console.print(f"  [cyan]would clone[/] {repo.name} <- {repo.url}")
                continue
            result = _git(["clone", repo.url or "", str(dest)])
            status = "[green]cloned[/]" if result.returncode == 0 else "[red]clone failed[/]"
            console.print(f"  {status} {repo.name}")
            if result.returncode != 0:
                console.print(f"    [red]{result.stderr.strip()}[/]")
            rc |= result.returncode
    return 1 if rc else 0
