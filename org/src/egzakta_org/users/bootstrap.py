"""`org user init` — autofill a profile stub from Linear viewer + git log."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..linear import LinearAPIError, graphql
from ..manifest import load_manifest
from ..workspace import find_workspace_root
from .loader import PROFILES_DIR


class BootstrapError(RuntimeError):
    pass


def _viewer(api_key: str) -> dict:
    query = """
    query { viewer { id name displayName email } }
    """
    data = graphql(api_key, query)
    viewer = data.get("viewer")
    if not viewer:
        raise BootstrapError("Linear API returned no viewer payload — is the API key valid?")
    return viewer


def _suggest_short_handle(display_name: str, fallback_linear_handle: str) -> str:
    """Default: first word of displayName, lowercase. Fallback to LINEAR_HANDLE."""
    if display_name:
        first = display_name.split()[0].lower()
        if first:
            return first
    return fallback_linear_handle.lower()


def _git_authors_for(root: Path, email: str, repo_names: list[str]) -> list[str]:
    """Walk `git log --author=<email> --format='%an <%ae>' | sort -u` across cloned repos."""
    seen: set[str] = set()
    out: list[str] = []
    for repo_name in repo_names:
        repo_dir = root / repo_name
        if not (repo_dir / ".git").exists():
            continue
        result = subprocess.run(
            ["git", "log", f"--author={email}", "--format=%an <%ae>"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                out.append(line)
    return out


def _profile_path(root: Path, handle: str) -> Path:
    return root / PROFILES_DIR / f"{handle}.yaml"


def _render_stub(
    *,
    short_handle: str,
    linear_handle: str,
    user_id: str,
    email: str,
    display_name: str,
    git_authors: list[str],
) -> str:
    """Render the initial profile YAML. Hand-formatted (not yaml.dump) so the
    `# TODO via /profile-me` comments survive."""
    authors_block = "\n".join(f"  - {a!r}" for a in git_authors) if git_authors else "  []"
    return f"""# Workspace profile for @{short_handle}. Run `/profile-me` to fill in the TODOs.
handle: {short_handle}
linear:
  handle: {linear_handle}
  user_id: {user_id}
  email: {email}
display_name: {display_name}
git_authors:
{authors_block}

# === Filled in by /profile-me ===

role: ""                # junior | mid | senior | staff | pm   # TODO via /profile-me
areas: []               # backend | frontend | retrieval | …    # TODO via /profile-me
owns: []                # atlas node ids you own                # TODO via /profile-me
learning: []            # atlas node ids you're learning        # TODO via /profile-me

preferences:
  grill_depth: medium    # shallow | medium | deep   # TODO via /profile-me
  review_style: balanced # terse | balanced | explanatory   # TODO via /profile-me
  handoff_detail: medium # low | medium | high   # TODO via /profile-me
"""


def init_profile(
    *,
    short_handle_override: str | None = None,
    dry_run: bool = False,
) -> tuple[Path, str]:
    """Bootstrap a profile. Returns ``(path, rendered_yaml)``.

    Raises ``BootstrapError`` for predictable failures (missing env vars,
    Linear API issues, existing profile).
    """
    linear_handle = os.environ.get("LINEAR_HANDLE", "").strip()
    if not linear_handle:
        raise BootstrapError(
            "$LINEAR_HANDLE not set. Add `export LINEAR_HANDLE=<your-linear-username>` "
            "to your shell rc (see docs/setup.md)."
        )
    api_key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not api_key:
        raise BootstrapError(
            "$LINEAR_API_KEY not set. Bootstrap needs it to fetch the viewer "
            "(user_id, email, displayName)."
        )

    try:
        viewer = _viewer(api_key)
    except LinearAPIError as exc:
        raise BootstrapError(f"Linear viewer query failed: {exc}") from None

    display_name = viewer.get("displayName") or viewer.get("name") or ""
    email = viewer.get("email") or ""
    user_id = viewer.get("id") or ""

    short_handle = short_handle_override or _suggest_short_handle(display_name, linear_handle)
    if not short_handle:
        raise BootstrapError("Could not derive a short handle — pass --handle explicitly.")

    root = find_workspace_root()
    path = _profile_path(root, short_handle)
    if path.exists() and not dry_run:
        raise BootstrapError(
            f"Profile already exists at {path.relative_to(root)} — "
            f"use `org user show {short_handle}` to view or `/profile-me` to update."
        )

    manifest = load_manifest(root)
    repo_names = list(manifest.repos)
    git_authors = _git_authors_for(root, email, repo_names) if email else []

    rendered = _render_stub(
        short_handle=short_handle,
        linear_handle=linear_handle,
        user_id=user_id,
        email=email,
        display_name=display_name,
        git_authors=git_authors,
    )

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return path, rendered
