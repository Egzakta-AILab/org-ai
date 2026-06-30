"""File-tier reader for the Egzakta Atlas (typed knowledge graph at `atlas/`).

The atlas is canonical inside this meta-repo. This package parses the on-disk
markdown + YAML frontmatter into typed Python objects so headless agents, CI,
and the `org` CLI can consult it without needing a running Obsidian app
(`obsidian-cli` is the live-enrichment companion, not a backbone).

Public API:
    load_atlas(root=None) -> AtlasIndex
    Node                                 # one node = one markdown file
    AtlasIndex                           # the loaded set, with by-id lookup
    AtlasError                           # parser/loader failures
"""

from __future__ import annotations

from .model import AtlasIndex, Node
from .parser import AtlasError, load_atlas

__all__ = ["AtlasError", "AtlasIndex", "Node", "load_atlas"]
