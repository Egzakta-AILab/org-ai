#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["ruamel.yaml>=0.18"]
# ///
"""migrate_linear_shape.py — one-shot atlas migration: string → dict.

Converts every `linear.initiative` / `linear.projects` entry in string form
to canonical dict form `{name, id}` by looking each name up against live
Linear. Comments in YAML are preserved via ruamel.yaml's round-trip loader.

Dry-run by default. Pass `--apply` to write changes.

Usage:
    python org/scripts/migrate_linear_shape.py            # dry-run
    python org/scripts/migrate_linear_shape.py --apply    # write changes

Requires `$LINEAR_API_KEY` in the environment (validated, never echoed).

Idempotent: re-running after `--apply` produces zero changes. Entries
already in dict form are skipped. Entries whose names don't resolve in
Linear are left alone and surfaced as warnings — operator fixes manually
(rename in atlas to match Linear, or fix the Linear name).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ATLAS_ROOT = WORKSPACE_ROOT / "atlas"

LINEAR_API = "https://api.linear.app/graphql"
TIMEOUT_SECONDS = 15

NODE_DIRS = (
    "pillars", "platform", "capabilities", "ops", "experience",
    "commercial", "keystones", "personas", "milestones",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
    args = parser.parse_args()

    api_key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not api_key:
        print("ERROR: $LINEAR_API_KEY not set. See linear skill setup.", file=sys.stderr)
        return 1

    print("Fetching Linear projects + initiatives …")
    try:
        projects = _fetch_linear_projects(api_key)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"  got {len(projects)} projects")

    project_by_name = _build_name_lookup(projects, key="name")

    # Derive initiatives from projects' edges, then top up with a direct
    # initiative query so we catch initiatives that have ZERO projects
    # attached (e.g. "Agents" today — paper-pillar initiative referenced by
    # the atlas but with no Linear projects yet).
    initiative_by_name: dict[str, dict[str, Any]] = {}
    for project in projects:
        for initiative in (project.get("initiatives") or {}).get("nodes") or []:
            initiative_by_name.setdefault(initiative["name"], initiative)
    try:
        for initiative in _fetch_all_initiatives(api_key):
            initiative_by_name.setdefault(initiative["name"], initiative)
    except RuntimeError as exc:
        print(f"  WARNING: couldn't fetch initiatives directly ({exc}); using project-derived set only", file=sys.stderr)
    print(f"  resolved {len(initiative_by_name)} initiatives")

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't reflow long lines
    # Match atlas convention: 4-space sequence indent with the dash at +2 from
    # the key (so `    - item` lines up under `  key:`). ruamel's default of
    # `mapping=2, sequence=2, offset=0` would reformat every list in the
    # touched files — unacceptable for a one-shot migration.
    yaml.indent(mapping=2, sequence=4, offset=2)

    files_changed = 0
    entries_migrated = 0
    unresolved: list[tuple[str, str, str]] = []  # (file, field, name)

    for dir_name in NODE_DIRS:
        for path in sorted((ATLAS_ROOT / dir_name).glob("*.md")):
            changed, migrated, miss = _migrate_file(
                path, yaml, project_by_name, initiative_by_name, apply=args.apply,
            )
            if changed:
                files_changed += 1
            entries_migrated += migrated
            unresolved.extend((str(path.relative_to(WORKSPACE_ROOT)), *m) for m in miss)

    print()
    if args.apply:
        print(f"Applied: {files_changed} file(s) changed, {entries_migrated} entries migrated.")
    else:
        print(f"Dry-run: would change {files_changed} file(s), migrate {entries_migrated} entries.")
        print("Re-run with --apply to write.")

    if unresolved:
        print()
        print(f"Unresolved ({len(unresolved)}) — name not found in Linear, left as string form:")
        for file, field, name in unresolved:
            print(f"  {file}  {field}: {name!r}")
        print()
        print("Fix by editing atlas to match Linear name, or correct the Linear project name.")
        return 2 if args.apply else 0
    return 0


def _migrate_file(
    path: Path,
    yaml: YAML,
    project_by_name: dict[str, dict[str, Any]],
    initiative_by_name: dict[str, dict[str, Any]],
    *,
    apply: bool,
) -> tuple[bool, int, list[tuple[str, str]]]:
    """Return (changed, entries_migrated, [(field, name) for unresolved])."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return False, 0, []
    end = text.find("\n---\n", 4)
    if end < 0:
        return False, 0, []
    fm_text = text[4:end]
    body = text[end + 5:]

    try:
        fm = yaml.load(fm_text)
    except Exception:
        return False, 0, []

    if not isinstance(fm, CommentedMap) or "linear" not in fm:
        return False, 0, []

    linear = fm["linear"]
    if not isinstance(linear, CommentedMap):
        return False, 0, []

    migrated_count = 0
    unresolved: list[tuple[str, str]] = []

    # initiative
    initiative = linear.get("initiative")
    if isinstance(initiative, str):
        name = initiative.strip()
        match = initiative_by_name.get(name)
        if match:
            replacement = CommentedMap()
            replacement["name"] = name
            replacement["id"] = match["id"]
            linear["initiative"] = replacement
            migrated_count += 1
        elif name:
            unresolved.append(("linear.initiative", name))

    # projects
    projects = linear.get("projects")
    if isinstance(projects, CommentedSeq):
        for i, entry in enumerate(projects):
            if isinstance(entry, str):
                name = entry.strip()
                match = project_by_name.get(name)
                if match:
                    replacement = CommentedMap()
                    replacement["name"] = name
                    replacement["id"] = match["id"]
                    projects[i] = replacement
                    migrated_count += 1
                elif name:
                    unresolved.append((f"linear.projects[{i}]", name))

    if migrated_count == 0:
        return False, 0, unresolved

    # Round-trip the frontmatter back out.
    buf = io.StringIO()
    yaml.dump(fm, buf)
    new_fm_text = buf.getvalue().rstrip("\n")
    new_text = f"---\n{new_fm_text}\n---\n{body}"

    if apply:
        path.write_text(new_text, encoding="utf-8")
    print(f"  {'apply' if apply else 'would update'}: {path.relative_to(WORKSPACE_ROOT)}  (+{migrated_count})")
    return True, migrated_count, unresolved


def _build_name_lookup(items: list[dict[str, Any]], *, key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        name = item.get(key)
        if isinstance(name, str) and name:
            out.setdefault(name, item)
    return out


def _fetch_linear_projects(api_key: str) -> list[dict[str, Any]]:
    """Fetch all projects from the configured Linear team.
    Set LINEAR_TEAM_KEY in the environment to target a specific team; defaults to "NW"."""
    import os
    team_key = os.environ.get("LINEAR_TEAM_KEY", "NW")
    query = """
    query AtlasMigrate($teamKey: String!) {
      teams(filter: { key: { eq: $teamKey } }) {
        nodes {
          projects(first: 100) {
            nodes {
              id
              name
              state
              initiatives { nodes { id name } }
            }
          }
        }
      }
    }
    """
    data = _graphql(api_key, query, variables={"teamKey": team_key})
    teams = (data.get("teams") or {}).get("nodes") or []
    if not teams:
        return []
    return list((teams[0].get("projects") or {}).get("nodes") or [])


def _fetch_all_initiatives(api_key: str) -> list[dict[str, Any]]:
    """Fetch every initiative the API key can see — covers zero-project
    initiatives that the project edge wouldn't surface."""
    query = """
    query AtlasMigrateInitiatives {
      initiatives(first: 100) {
        nodes { id name }
      }
    }
    """
    data = _graphql(api_key, query)
    return list((data.get("initiatives") or {}).get("nodes") or [])


def _graphql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_obj: dict[str, Any] = {"query": query}
    if variables:
        payload_obj["variables"] = variables
    body = json.dumps(payload_obj).encode("utf-8")
    request = urllib.request.Request(
        LINEAR_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from Linear API") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from None

    if "errors" in payload:
        first = payload["errors"][0].get("message", "unknown error")
        raise RuntimeError(f"Linear API returned errors: {first}")
    return payload.get("data") or {}


if __name__ == "__main__":
    sys.exit(main())
