"""Atlas validation checks.

Severity philosophy: lenient by default. Errors are structural problems that
break the graph contract (duplicate ids, missing ids, unparseable frontmatter).
Warnings are content drift (stale code_refs, unknown types, dangling wikilinks)
that users should know about but shouldn't gate CI/agents on.

The CLI (`org atlas validate`) exits 0 on warnings-only and 1 on any error.
`--strict` promotes warnings to errors.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .model import (
    CODE_REFS_REQUIRED_TYPES,
    KNOWN_STATUSES,
    KNOWN_TYPES,
    METRICS_REQUIRED_STATUSES,
    STATUS_REQUIRED_TYPES,
    AtlasIndex,
)
from .parser import NODE_DIRS, split_frontmatter

# `[[target]]` or `[[target|alias]]`. We're intentionally tolerant — only flag
# wikilinks that look like atlas node refs (no slash, no extension).
_WIKILINK_RE = re.compile(r"\[\[([^\]\|\#]+?)(?:\|[^\]]+)?\]\]")

# Required fields per node, by severity. `id`, `type`, and `name` are required
# for the node to even load; we re-check here so validate is self-contained.
_REQUIRED_FIELDS = ("id", "name", "type")


@dataclass(frozen=True)
class Issue:
    severity: str         # "error" | "warning"
    code: str
    node: str | None      # node id, or rel_path for files we couldn't load
    detail: str


def validate(index: AtlasIndex, workspace_root: Path) -> list[Issue]:
    """Run all checks. Returns issues in deterministic order (errors first, then warnings)."""
    issues: list[Issue] = []

    issues.extend(_check_unparseable_files(index))
    issues.extend(_check_required_fields(index))
    issues.extend(_check_duplicate_ids(index))
    issues.extend(_check_unknown_types(index))
    issues.extend(_check_invalid_statuses(index))
    issues.extend(_check_missing_status(index))
    issues.extend(_check_code_refs(index, workspace_root))
    issues.extend(_check_missing_code_refs(index))
    issues.extend(_check_wip_no_code_refs(index))
    issues.extend(_check_missing_metrics(index))
    issues.extend(_check_legacy_linear_shape(index))
    issues.extend(_check_dangling_wikilinks(index))
    issues.extend(_check_dangling_frontmatter_links(index))
    issues.extend(_check_dependency_cycles(index))

    # Errors first, then warnings; stable within each group.
    issues.sort(key=lambda i: (0 if i.severity == "error" else 1,))
    return issues


def _check_unparseable_files(index: AtlasIndex) -> list[Issue]:
    """Files in node dirs that the parser skipped (no frontmatter, no id, etc.)."""
    issues: list[Issue] = []
    loaded_paths = {node.path for node in index.nodes}
    for dir_name in NODE_DIRS:
        dir_path = index.root / dir_name
        if not dir_path.is_dir():
            continue
        for md_path in sorted(dir_path.glob("*.md")):
            if md_path in loaded_paths:
                continue
            rel = md_path.relative_to(index.root.parent).as_posix()
            text = md_path.read_text(encoding="utf-8", errors="replace")
            yaml_text, _ = split_frontmatter(text)
            if yaml_text is None:
                detail = "no `---` frontmatter block"
                code = "missing-frontmatter"
            else:
                detail = "frontmatter parsed but missing required `id:` field"
                code = "missing-id"
            issues.append(Issue(severity="error", code=code, node=rel, detail=detail))
    return issues


def _check_required_fields(index: AtlasIndex) -> list[Issue]:
    issues: list[Issue] = []
    for node in index.nodes:
        for field in _REQUIRED_FIELDS:
            if not node.frontmatter.get(field):
                issues.append(
                    Issue(
                        severity="error",
                        code=f"missing-{field}",
                        node=node.id or node.rel_path,
                        detail=f"required field `{field}` is missing or empty",
                    )
                )
    return issues


def _check_duplicate_ids(index: AtlasIndex) -> list[Issue]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for node in index.nodes:
        buckets[node.id].append(node.rel_path)
    issues: list[Issue] = []
    for node_id, paths in buckets.items():
        if len(paths) > 1:
            issues.append(
                Issue(
                    severity="error",
                    code="duplicate-id",
                    node=node_id,
                    detail=f"claimed by {len(paths)} files: {', '.join(paths)}",
                )
            )
    return issues


def _check_unknown_types(index: AtlasIndex) -> list[Issue]:
    issues: list[Issue] = []
    for node in index.nodes:
        if node.type not in KNOWN_TYPES:
            issues.append(
                Issue(
                    severity="warning",
                    code="unknown-type",
                    node=node.id,
                    detail=f"type `{node.type}` is not in known set {sorted(KNOWN_TYPES)}",
                )
            )
    return issues


def _check_missing_status(index: AtlasIndex) -> list[Issue]:
    issues: list[Issue] = []
    for node in index.nodes:
        if node.type not in STATUS_REQUIRED_TYPES:
            continue
        if not node.status:
            issues.append(
                Issue(
                    severity="warning",
                    code="missing-status",
                    node=node.id,
                    detail="`status:` field is missing",
                )
            )
    return issues


def _check_code_refs(index: AtlasIndex, workspace_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for node in index.nodes:
        for ref in node.code_refs:
            target = (workspace_root / ref).resolve()
            if not target.exists():
                issues.append(
                    Issue(
                        severity="warning",
                        code="broken-code-ref",
                        node=node.id,
                        detail=f"`{ref}` does not exist under the workspace root",
                    )
                )
    return issues


def _check_invalid_statuses(index: AtlasIndex) -> list[Issue]:
    """Status is set but not one of the canonical values."""
    issues: list[Issue] = []
    for node in index.nodes:
        if node.status and node.status not in KNOWN_STATUSES:
            issues.append(
                Issue(
                    severity="warning",
                    code="invalid-status",
                    node=node.id,
                    detail=(
                        f"`status: {node.status}` not in canonical set "
                        f"{sorted(KNOWN_STATUSES)}"
                    ),
                )
            )
    return issues


def _check_missing_code_refs(index: AtlasIndex) -> list[Issue]:
    """Required-type nodes implementing real work must carry `code_refs:`.

    Only fires for `status in {wip, shipped, stable}` — `planned` and
    `research` nodes legitimately have no implementation yet, so requiring
    `code_refs:` on them is wrong (was a false-positive source in PR A1).
    """
    implementing_statuses = {"wip", "shipped", "stable"}
    issues: list[Issue] = []
    for node in index.nodes:
        if node.type not in CODE_REFS_REQUIRED_TYPES:
            continue
        if (node.status or "") not in implementing_statuses:
            continue
        if not node.code_refs:
            issues.append(
                Issue(
                    severity="warning",
                    code="missing-code-refs",
                    node=node.id,
                    detail=(
                        f"`{node.type}` with `status: {node.status}` has no `code_refs:` — "
                        "point at the implementing code, decision artifact, or playbook"
                    ),
                )
            )
    return issues


def _check_wip_no_code_refs(index: AtlasIndex) -> list[Issue]:
    """A `wip` node without `code_refs:` is aspirational, not in progress."""
    issues: list[Issue] = []
    for node in index.nodes:
        if node.status != "wip":
            continue
        if node.type not in CODE_REFS_REQUIRED_TYPES:
            continue
        if not node.code_refs:
            issues.append(
                Issue(
                    severity="warning",
                    code="wip-no-code-refs",
                    node=node.id,
                    detail=(
                        "`status: wip` but no `code_refs:` — "
                        "demote to `planned` or add the code path"
                    ),
                )
            )
    return issues


def _check_missing_metrics(index: AtlasIndex) -> list[Issue]:
    """Capabilities promoted to shipped/stable need measurable metrics."""
    issues: list[Issue] = []
    for node in index.nodes:
        if node.type != "capability":
            continue
        if node.status not in METRICS_REQUIRED_STATUSES:
            continue
        if not node.metrics:
            issues.append(
                Issue(
                    severity="error",
                    code="missing-metrics",
                    node=node.id,
                    detail=(
                        f"`capability` with `status: {node.status}` has no `metrics:` — "
                        "shipped/stable capabilities must be measurable"
                    ),
                )
            )
    return issues


def _check_legacy_linear_shape(index: AtlasIndex) -> list[Issue]:
    """`linear.initiative` / `linear.projects` should be dict form `{name, id}`.

    String form still parses but loses the Linear ID, which is the rename-safe
    identifier. Migrate to dict form so atlas references survive Linear renames.
    """
    issues: list[Issue] = []
    for node in index.nodes:
        linear = node.frontmatter.get("linear")
        if not isinstance(linear, dict):
            continue
        legacy_fields: list[str] = []
        if isinstance(linear.get("initiative"), str):
            legacy_fields.append("initiative")
        projects = linear.get("projects")
        if isinstance(projects, list) and any(isinstance(p, str) for p in projects):
            legacy_fields.append("projects")
        if legacy_fields:
            issues.append(
                Issue(
                    severity="error",
                    code="legacy-linear-shape",
                    node=node.id,
                    detail=(
                        f"`linear.{'/'.join(legacy_fields)}` in legacy string form; "
                        "migrate to `{name, id}` dict form (see ontology.md)"
                    ),
                )
            )
    return issues


def _build_link_resolution_set(index: AtlasIndex) -> set[str]:
    """Set of strings a `[[target]]` may resolve to.

    Includes every node's id, file stem, last-dotted segment, frontmatter
    aliases, plus the file stems under `refs/` and `research/` (free-form
    folders that nodes legitimately cross-link).
    """
    known: set[str] = set()
    for node in index.nodes:
        known.add(node.id)
        known.add(node.path.stem)
        known.add(node.id.split(".", 1)[-1])
        for alias in node.frontmatter.get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                known.add(alias.strip())
    for dir_name in ("refs", "research"):
        dir_path = index.root / dir_name
        if dir_path.is_dir():
            for md_path in dir_path.glob("*.md"):
                known.add(md_path.stem)
    return known


def _check_dangling_wikilinks(index: AtlasIndex) -> list[Issue]:
    """Body `[[link]]` refs that don't resolve to any known atlas file."""
    known = _build_link_resolution_set(index)
    issues: list[Issue] = []
    for node in index.nodes:
        for match in _WIKILINK_RE.finditer(node.body):
            target = match.group(1).strip()
            if target in known:
                continue
            issues.append(
                Issue(
                    severity="warning",
                    code="dangling-wikilink",
                    node=node.id,
                    detail=f"body refers to `[[{target}]]` but no node, ref, or research doc matches",
                )
            )
    return issues


def _check_dangling_frontmatter_links(index: AtlasIndex) -> list[Issue]:
    """Frontmatter `parent`, `depends_on`, `unlocks` refs that don't resolve.

    The body-link check existed already; this extends the same resolution to
    structural frontmatter edges so an ID rename can't silently break the graph.
    """
    known = _build_link_resolution_set(index)
    issues: list[Issue] = []
    for node in index.nodes:
        candidates: list[tuple[str, str]] = []  # (field, target)
        if node.parent:
            candidates.append(("parent", node.parent))
        for target in node.depends_on:
            candidates.append(("depends_on", target))
        for target in node.unlocks:
            candidates.append(("unlocks", target))
        for field, target in candidates:
            if target in known:
                continue
            issues.append(
                Issue(
                    severity="warning",
                    code="dangling-frontmatter-link",
                    node=node.id,
                    detail=f"`{field}: [[{target}]]` doesn't resolve to any known node",
                )
            )
    return issues


def _check_dependency_cycles(index: AtlasIndex) -> list[Issue]:
    """Detect cycles in the `depends_on` graph.

    Builds the graph keyed by the same resolution rules as wikilink checks
    (id, file stem, last-dotted segment). For each strongly-connected component
    of size ≥ 2, emit one warning per node in the cycle citing the cycle path.
    """
    alias_to_node: dict[str, str] = {}
    for node in index.nodes:
        for alias in (node.id, node.path.stem, node.id.split(".", 1)[-1]):
            alias_to_node.setdefault(alias, node.id)

    graph: dict[str, list[str]] = {node.id: [] for node in index.nodes}
    for node in index.nodes:
        for target in node.depends_on:
            resolved = alias_to_node.get(target)
            if resolved and resolved != node.id:
                graph[node.id].append(resolved)

    # Iterative DFS with grey/black coloring. When we hit a grey node, walk back
    # through `parent` to recover the cycle path.
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in graph}
    parent: dict[str, str | None] = {nid: None for nid in graph}
    cycles: list[tuple[str, ...]] = []
    seen_cycles: set[frozenset[str]] = set()

    def walk(start: str) -> None:
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GREY
        while stack:
            node_id, idx = stack[-1]
            neighbors = graph[node_id]
            if idx >= len(neighbors):
                color[node_id] = BLACK
                stack.pop()
                continue
            stack[-1] = (node_id, idx + 1)
            nxt = neighbors[idx]
            if color[nxt] == WHITE:
                parent[nxt] = node_id
                color[nxt] = GREY
                stack.append((nxt, 0))
            elif color[nxt] == GREY:
                # Recover cycle: walk parent chain from node_id back to nxt.
                path: list[str] = [nxt, node_id]
                cur = parent[node_id]
                while cur is not None and cur != nxt:
                    path.append(cur)
                    cur = parent[cur]
                cycle = tuple(reversed(path))
                key = frozenset(cycle)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    cycles.append(cycle)

    for nid in graph:
        if color[nid] == WHITE:
            walk(nid)

    issues: list[Issue] = []
    for cycle in cycles:
        path_str = " → ".join(cycle) + f" → {cycle[0]}"
        for nid in cycle:
            issues.append(
                Issue(
                    severity="warning",
                    code="dependency-cycle",
                    node=nid,
                    detail=f"cycle in `depends_on`: {path_str}",
                )
            )
    return issues
