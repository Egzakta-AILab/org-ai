---
id: pillar.search
name: Search
type: pillar
layer: L4
status: shipped
owners: [jordan.lee]
depends_on:
  - "[[storage]]"
unlocks: []
code_refs:
  - notewell/src/search/
linear:
  initiative:
    name: "Search"
    id: 00000000-0000-0000-0000-0000000000a1
---

## Why it matters

Search is how users recover knowledge they've already captured. Without good search, Notewell is a write-only store. High-quality search multiplies the value of every note in the knowledge base.

## Current state

Full-text search is shipped and indexed. Tag-filtered queries work. Ranking quality is acceptable for small corpora; version-history-aware search is still wip.

## Open questions

- At what corpus size does full-text recall degrade enough to warrant a second-tier semantic pass?

## References

- [[full-text-search]] — primary capability
- [[tagging]] — enriches search facets
- [[storage]] — index lives here
