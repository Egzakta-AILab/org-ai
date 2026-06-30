"""Typed representation of atlas nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_WIKILINK_BARE_RE = re.compile(r"^\s*\[\[([^\]\|\#]+?)(?:\|[^\]]+)?\]\]\s*$")


def _unwrap_wikilinks(raw: Any) -> list[str]:
    """Pull bare wikilink targets out of a list of frontmatter values.

    Accepts entries like ``"[[hybrid-retrieval]]"``, ``"[[search|Search]]"``,
    or plain ``"hybrid-retrieval"``. Returns the unwrapped target string for
    each. Non-string / empty entries are dropped.
    """
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        match = _WIKILINK_BARE_RE.match(entry)
        target = match.group(1).strip() if match else entry.strip()
        if target:
            out.append(target)
    return out

# The types we recognize. Anything else is loaded as a Node but flagged by
# `validate` with `unknown-type` (warning).
KNOWN_TYPES: frozenset[str] = frozenset(
    {"pillar", "capability", "platform", "ops", "experience", "commercial", "keystone", "persona", "milestone"}
)

# Canonical status lifecycle — see atlas/ontology.md § Status lifecycle.
# `shipped` = first usable impl merged; `stable` = settled, no open questions.
KNOWN_STATUSES: frozenset[str] = frozenset(
    {"research", "planned", "wip", "shipped", "stable", "deprecated"}
)

# Types that must carry a `status:` field. Personas / keystones / pillars are
# allowed to omit it (personas describe customer archetypes, keystones describe
# architectural forks, pillars are abstract umbrellas over their children).
STATUS_REQUIRED_TYPES: frozenset[str] = frozenset(
    {"capability", "platform", "ops", "experience", "commercial", "milestone"}
)

# Types that must carry `code_refs:` (when not `status: research`). Personas
# and milestones are exempt — personas are customer archetypes, milestones are
# time markers, neither has code to point at.
CODE_REFS_REQUIRED_TYPES: frozenset[str] = frozenset(
    {"pillar", "capability", "platform", "ops", "experience", "commercial", "keystone"}
)

# Statuses for which a `capability` must carry `metrics:` — once shipped or
# stable, a capability should be measurable.
METRICS_REQUIRED_STATUSES: frozenset[str] = frozenset({"shipped", "stable"})

# Folders under atlas/ that contain nodes (one .md = one node). Other dirs
# (`refs/`, `research/`, `items/`) hold free-form content that we deliberately
# do not load as nodes — see parser.NODE_DIRS for the canonical list and the
# reasoning.


@dataclass(frozen=True)
class Node:
    """One atlas node — parsed from one markdown file with YAML frontmatter."""

    id: str
    name: str
    type: str
    path: Path                            # absolute path on disk
    rel_path: str                         # workspace-relative posix path (for display)
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def layer(self) -> str | None:
        value = self.frontmatter.get("layer")
        if value is None:
            return None
        return str(value)

    @property
    def status(self) -> str | None:
        value = self.frontmatter.get("status")
        return str(value) if value else None

    @property
    def pillar(self) -> str | None:
        """Parse the pillar segment out of dotted ids like `capability.search.hybrid-retrieval`.

        Returns None for ids that don't have a pillar segment (e.g. `pillar.search`,
        `persona.internal-enterprise`, `keystone.observability-strategy`).
        """
        parts = self.id.split(".")
        if len(parts) < 3:
            return None
        return parts[1]

    @property
    def code_refs(self) -> list[str]:
        raw = self.frontmatter.get("code_refs") or []
        return [str(ref) for ref in raw if ref]

    @property
    def metrics(self) -> list[str]:
        raw = self.frontmatter.get("metrics") or []
        return [str(m) for m in raw if m]

    @property
    def depends_on(self) -> list[str]:
        """Wikilink targets from frontmatter `depends_on:`, unwrapped from `[[…]]`."""
        return _unwrap_wikilinks(self.frontmatter.get("depends_on") or [])

    @property
    def unlocks(self) -> list[str]:
        return _unwrap_wikilinks(self.frontmatter.get("unlocks") or [])

    @property
    def parent(self) -> str | None:
        raw = self.frontmatter.get("parent")
        if raw is None:
            return None
        unwrapped = _unwrap_wikilinks([raw])
        return unwrapped[0] if unwrapped else None

    @property
    def linear_projects(self) -> list[tuple[str, str | None]]:
        """Return ``[(name, id_or_None), …]``. Handles both canonical and legacy shapes.

        Canonical: ``linear.projects: [{name, id}, …]``
        Legacy:    ``linear.projects: ["Name", …]``
        """
        linear = self.frontmatter.get("linear") or {}
        projects = linear.get("projects") if isinstance(linear, dict) else None
        if not projects:
            return []
        out: list[tuple[str, str | None]] = []
        for entry in projects:
            if isinstance(entry, dict):
                name = str(entry.get("name", "")).strip()
                if name:
                    out.append((name, entry.get("id")))
            elif isinstance(entry, str) and entry.strip():
                out.append((entry.strip(), None))
        return out


@dataclass(frozen=True)
class AtlasIndex:
    """The loaded atlas — a sequence of nodes plus an id lookup."""

    root: Path
    nodes: tuple[Node, ...]
    by_id: dict[str, Node]

    def filter(
        self,
        *,
        type: str | None = None,
        pillar: str | None = None,
        status: str | None = None,
    ) -> list[Node]:
        """Filter nodes by type / pillar / status. Filters compose with AND."""
        out: list[Node] = []
        for node in self.nodes:
            if type and node.type != type:
                continue
            if pillar and node.pillar != pillar:
                continue
            if status and node.status != status:
                continue
            out.append(node)
        return out
