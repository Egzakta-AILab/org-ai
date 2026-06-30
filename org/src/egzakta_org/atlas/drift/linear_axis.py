"""Linear axis — does the atlas still match what Linear actually shows?

For each node with `linear:` populated, we hit Linear's GraphQL API to verify
project / initiative IDs still resolve. We also map atlas `status:` to Linear
project state and emit mismatches. Finally, an inverse sweep lists active
projects that no atlas node references — coverage gaps from the Linear side.

Auth: reads `$LINEAR_API_KEY` at the call site. Never logs, echoes, prints,
or interpolates it into error messages. If unset, the axis returns a single
"linear-api-key-missing" finding instead of crashing — useful in CI where
the key isn't available.

Networking: stdlib `urllib.request` so we don't pull in `httpx` for a single
endpoint. Failures (network, 401, 5xx) surface as one `linear-api-error`
finding rather than per-node noise.
"""

from __future__ import annotations

import os
from typing import Any

from ...linear import LinearAPIError, graphql
from ...users import load_all_users
from ..model import AtlasIndex
from .model import DriftAxis, DriftFinding

# Atlas status → set of Linear project states that satisfy "in sync".
# `shipped`/`stable` should land as `completed`; everything else mostly aligns
# with Linear's own lifecycle. `research` doesn't have a great Linear analog
# (Linear's "backlog" covers both not-started and being-thought-about), so we
# treat it permissively.
_STATUS_TO_LINEAR_STATES: dict[str, frozenset[str]] = {
    "shipped": frozenset({"completed"}),
    "stable": frozenset({"completed"}),
    "wip": frozenset({"started", "in-progress"}),
    "planned": frozenset({"planned", "backlog"}),
    "research": frozenset({"backlog", "planned"}),
    "deprecated": frozenset({"canceled", "completed"}),
}


def check_linear_sync(index: AtlasIndex) -> list[DriftFinding]:
    """Run the Linear axis. Returns a list of `DriftFinding`s.

    Quietly returns one informational finding if the API key isn't set —
    don't crash the whole `drift` run for a missing optional credential.
    """
    api_key = os.environ.get("LINEAR_API_KEY", "").strip()
    if not api_key:
        return [
            DriftFinding(
                axis=DriftAxis.LINEAR,
                code="linear-api-key-missing",
                severity="info",
                detail=(
                    "$LINEAR_API_KEY not set — skipping linear-axis checks. "
                    "Set it locally (`varlock load` flow) or pass it via CI secrets."
                ),
            )
        ]

    project_ids = _collect_project_ids(index)
    initiative_ids = _collect_initiative_ids(index)

    findings: list[DriftFinding] = []
    try:
        live_projects = _fetch_linear_projects(api_key)
    except LinearAPIError as exc:
        return [
            DriftFinding(
                axis=DriftAxis.LINEAR,
                code="linear-api-error",
                severity="warning",
                detail=f"Linear API call failed: {exc} (axis skipped)",
            )
        ]

    live_project_index = {p["id"]: p for p in live_projects}
    live_initiative_index: dict[str, dict[str, Any]] = {}
    for project in live_projects:
        for initiative in (project.get("initiatives", {}).get("nodes") or []):
            live_initiative_index.setdefault(initiative["id"], initiative)

    # Per-node checks: ID resolution + status mapping.
    for node in index.nodes:
        for ref in project_ids[node.id]:
            project = live_project_index.get(ref.id)
            if project is None:
                findings.append(
                    DriftFinding(
                        axis=DriftAxis.LINEAR,
                        code="broken-linear-project",
                        severity="warning",
                        detail=(
                            f"node references Linear project id `{ref.id}` "
                            f"(name on node: {ref.name!r}) — not found in configured Linear team"
                        ),
                        node_id=node.id,
                        suggested="project may have been deleted or archived; re-link or drop the reference",
                    )
                )
                continue
            # Status mismatch — only flag when both sides have an opinion.
            expected = _STATUS_TO_LINEAR_STATES.get(node.status or "", frozenset())
            actual = project.get("state", "")
            if expected and actual and actual not in expected:
                findings.append(
                    DriftFinding(
                        axis=DriftAxis.LINEAR,
                        code="status-mismatch",
                        severity="warning",
                        detail=(
                            f"atlas status `{node.status}` expects Linear state in "
                            f"{sorted(expected)} but project '{project.get('name')}' is `{actual}`"
                        ),
                        node_id=node.id,
                        path=ref.name,
                    )
                )

        for ref in initiative_ids[node.id]:
            if ref.id not in live_initiative_index:
                findings.append(
                    DriftFinding(
                        axis=DriftAxis.LINEAR,
                        code="broken-linear-initiative",
                        severity="warning",
                        detail=(
                            f"node references Linear initiative id `{ref.id}` "
                            f"(name on node: {ref.name!r}) — not visible from any configured project"
                        ),
                        node_id=node.id,
                    )
                )

    # Inverse coverage: Linear projects that no atlas node references.
    referenced_ids = {ref.id for refs in project_ids.values() for ref in refs}
    for project in live_projects:
        if project["id"] in referenced_ids:
            continue
        if project.get("state") in {"canceled", "completed"}:
            # Don't ask for atlas backing on dead projects — too noisy.
            continue
        findings.append(
            DriftFinding(
                axis=DriftAxis.LINEAR,
                code="unbacked-linear-project",
                severity="info",
                detail=(
                    f"Linear project '{project.get('name')}' "
                    f"(state: {project.get('state')}) has no atlas node referencing it"
                ),
                path=project.get("name"),
                suggested="add to an existing node's linear.projects or create a new atlas node",
            )
        )

    findings.extend(_check_owner_profiles(index))
    findings.sort(key=lambda f: (f.code, f.node_id or f.path or ""))
    return findings


def _check_owner_profiles(index: AtlasIndex) -> list[DriftFinding]:
    """Flag atlas `owners:` handles that have no profile YAML in `platform/profiles/`.

    Info-level (not warning) — profiles are opt-in and the absence isn't a
    correctness bug, just a coordination gap. One finding per missing handle
    (not per node) so the report doesn't fan out N×M.
    """
    profiles = load_all_users()
    known_handles = set(profiles)
    if not known_handles:
        # No profiles registered yet — don't flag every owner. Caller will see
        # zero coverage in `org user list` and act accordingly.
        return []
    seen: set[str] = set()
    findings: list[DriftFinding] = []
    for node in index.nodes:
        owners = node.frontmatter.get("owners") or []
        if not isinstance(owners, list):
            continue
        for owner in owners:
            if not isinstance(owner, str):
                continue
            if owner in known_handles or owner in seen:
                continue
            seen.add(owner)
            findings.append(
                DriftFinding(
                    axis=DriftAxis.LINEAR,
                    code="unknown-owner-handle",
                    severity="info",
                    detail=(
                        f"atlas owner `{owner}` has no profile at "
                        f"platform/profiles/{owner}.yaml — run `org user init` as that dev"
                    ),
                    path=owner,
                    suggested="`org user init` (as that dev) or remove from atlas `owners:`",
                )
            )
    return findings


# --- internals -----------------------------------------------------------


class _Ref:
    """Light tuple-like for a linear reference. Kept private to this module."""

    __slots__ = ("id", "name")

    def __init__(self, id: str, name: str) -> None:
        self.id = id
        self.name = name


def _collect_project_ids(index: AtlasIndex) -> dict[str, list[_Ref]]:
    """Return ``{node_id: [Ref(id, name), …]}`` of every linear.projects entry
    that has an id. Entries lacking an id (legacy string-only) are ignored —
    `validate` already flags those via `legacy-linear-shape`."""
    out: dict[str, list[_Ref]] = {}
    for node in index.nodes:
        linear = node.frontmatter.get("linear")
        if not isinstance(linear, dict):
            out[node.id] = []
            continue
        refs: list[_Ref] = []
        for entry in linear.get("projects") or []:
            if isinstance(entry, dict) and entry.get("id") and entry.get("name"):
                refs.append(_Ref(id=str(entry["id"]), name=str(entry["name"])))
        out[node.id] = refs
    return out


def _collect_initiative_ids(index: AtlasIndex) -> dict[str, list[_Ref]]:
    out: dict[str, list[_Ref]] = {}
    for node in index.nodes:
        linear = node.frontmatter.get("linear")
        if not isinstance(linear, dict):
            out[node.id] = []
            continue
        initiative = linear.get("initiative")
        refs: list[_Ref] = []
        if isinstance(initiative, dict) and initiative.get("id") and initiative.get("name"):
            refs.append(_Ref(id=str(initiative["id"]), name=str(initiative["name"])))
        out[node.id] = refs
    return out


def _fetch_linear_projects(api_key: str) -> list[dict[str, Any]]:
    """Fetch all projects from the configured Linear team in one query.

    Includes initiatives via the project's edge — saves a separate round trip.
    Linear paginates at 50 by default; bump to 100. If we cross that, this needs
    a paged loop. Set ``LINEAR_TEAM_KEY`` to target a specific team; defaults to
    the example team key ``NW``.
    """
    query = """
    query AtlasDrift {
      team(id: "%s") {
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
    """ % _team_key()
    data = graphql(api_key, query)
    team = data.get("team")
    if not team:
        # Older API shape may need team name; try by key.
        return _fetch_linear_projects_by_key(api_key)
    nodes = team.get("projects", {}).get("nodes") or []
    return list(nodes)


def _fetch_linear_projects_by_key(api_key: str) -> list[dict[str, Any]]:
    """Fallback for installations where `team(id: ...)` isn't accepted."""
    query = """
    query AtlasDriftByKey {
      teams(filter: { key: { eq: "%s" } }) {
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
    """ % _team_key()
    data = graphql(api_key, query)
    teams = data.get("teams", {}).get("nodes") or []
    if not teams:
        return []
    return list(teams[0].get("projects", {}).get("nodes") or [])


def _team_key() -> str:
    """Linear team key to scan; override via ``LINEAR_TEAM_KEY`` (default ``NW``)."""
    import os

    return os.environ.get("LINEAR_TEAM_KEY", "NW")
