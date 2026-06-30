"""Code-coverage axis — does every interesting code path have an atlas node?

This axis walks a set of "node-worthy" path patterns across the active repos
in `repos.yaml`, then compares against the union of all atlas `code_refs:`.
Anything code-side that no node references is a candidate gap — either a
missing atlas node, or proof we should add a `code_refs:` entry to an existing
node.

Path patterns are hard-coded for D1. A later PR moves them to per-repo config
in `repos.yaml` (`atlas_coverage_paths:`). See NW-450 description for the
deferred-scope list.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ...manifest import load_manifest
from ..model import AtlasIndex
from .model import DriftAxis, DriftFinding

# Per-repo glob patterns of directories that warrant an atlas node. Patterns
# are relative to the workspace root, evaluated with Path.glob. A directory
# matching one of these patterns is "node-worthy" — it should be referenced
# (directly or via a parent path) from at least one node's `code_refs:`.
#
# TODO: move to `repos.yaml` `atlas_coverage_paths:` per-repo block so each
# repo's owner controls its coverage shape rather than this central list.
_NODE_WORTHY_PATTERNS: dict[str, tuple[str, ...]] = {
    "notewell": (
        "notewell/backend/src/core/*",
        "notewell/backend/src/routes/*.py",
        "notewell/backend/src/database/*.py",
        "notewell/frontend/src/features/*",
    ),
    "infra": (
        "infra/*",
    ),
}

# Trivial paths we don't expect atlas coverage for, even when they match a
# node-worthy pattern. Keep this list narrow — bias toward false positives
# (which prompt the user to either add a node or extend this skiplist) over
# silent gaps.
_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "__pycache__",
        ".DS_Store",
        ".git",
        ".github",
        ".gitignore",
        # Top-level infra dirs that are pure config / docs / non-product.
        "docker-compose.yml",
        "README.md",
        ".env.example",
    }
)


def check_code_coverage(index: AtlasIndex, workspace_root: Path) -> list[DriftFinding]:
    """Find node-worthy paths that no atlas node references.

    Coverage rule: a path P is covered if any node's `code_refs:` entry is
    equal to P (after normalizing trailing slashes) OR is an ancestor of P.
    Ancestor matching catches the common case where a node points at
    `notewell/backend/src/core/search/` and we shouldn't separately flag
    `notewell/backend/src/core/search/hybrid.py` underneath it.
    """
    manifest = load_manifest(workspace_root)
    covered = _build_covered_set(index)
    findings: list[DriftFinding] = []

    for repo_name, patterns in _NODE_WORTHY_PATTERNS.items():
        repo = manifest.repos.get(repo_name)
        if repo is None or repo.status != "active":
            continue
        repo_root = workspace_root / repo_name
        if not repo_root.is_dir():
            continue
        for pattern in patterns:
            for match in sorted(workspace_root.glob(pattern)):
                if match.name in _SKIP_NAMES:
                    continue
                rel = match.relative_to(workspace_root).as_posix()
                # Append `/` for dirs so ancestor-matching against the same-trailing
                # `code_refs:` entries works uniformly. Files stay as-is.
                rel_key = rel + "/" if match.is_dir() else rel
                if _is_covered(rel_key, covered):
                    continue
                findings.append(
                    DriftFinding(
                        axis=DriftAxis.CODE,
                        code="uncovered-code-path",
                        severity="warning",
                        detail=(
                            f"{rel} has no atlas node referencing it "
                            "(no `code_refs:` entry resolves to this path or an ancestor)"
                        ),
                        path=rel,
                        suggested=_suggested_action(rel),
                    )
                )

    # Stable order: by path, alphabetical.
    findings.sort(key=lambda f: f.path or "")
    return findings


def _build_covered_set(index: AtlasIndex) -> set[str]:
    """Set of workspace-relative paths claimed by some node, with a trailing
    `/` on directory-style entries so ancestor matching is uniform."""
    covered: set[str] = set()
    for node in index.nodes:
        for ref in node.code_refs:
            covered.add(_normalize_ref(ref))
    return covered


def _normalize_ref(ref: str) -> str:
    """Strip leading slashes; preserve trailing slash if the author included one
    (signaling "this is a directory"). We don't stat the path — code_refs may
    point at moved code, which validate already flags as broken-code-ref."""
    ref = ref.lstrip("/")
    return ref


def _is_covered(rel_key: str, covered: Iterable[str]) -> bool:
    """A path P is covered iff some code_ref C either equals P (modulo trailing
    slash) or points at something INSIDE P (C starts with P + '/').

    Ancestor coverage is deliberately NOT honored — a node with
    `code_refs: notewell/backend/src/` should not silently mark every subdir under
    backend/src/ as "covered." That umbrella claim is the bug the drift
    detector is supposed to surface (the audit flagged `platform.storage`
    exactly this way). If a single node legitimately covers an umbrella dir
    today, it'll just produce findings for the subdirs; that's a feature.
    """
    rel_no_slash = rel_key.rstrip("/")
    rel_with_slash = rel_no_slash + "/"
    if rel_no_slash in covered or rel_with_slash in covered:
        return True
    for entry in covered:
        if entry.startswith(rel_with_slash):
            return True
    return False


def _suggested_action(rel: str) -> str:
    """Best-effort one-liner: which kind of node would cover this path."""
    if "/frontend/" in rel:
        return f"add an experience or capability node with code_refs: [{rel}/]"
    if "/infra/" in rel or rel.startswith("infra/"):
        return f"add a platform or ops node with code_refs: [{rel}/]"
    if "/routes/" in rel:
        return f"reference {rel} from an existing capability or pillar node"
    if "/database/" in rel:
        return f"reference {rel} from `platform.storage` code_refs"
    return f"add a node with code_refs: [{rel}/] or extend an existing node"
