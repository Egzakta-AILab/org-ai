---
id: capability.capture.tagging
name: Tagging
type: capability
layer: L3
parent: "[[capture]]"
status: planned
owners: [sam.rivera]
depends_on: []
unlocks:
  - "[[full-text-search]]"
implements: null
---

## Why it matters

Tags let users apply structured metadata to notes without imposing a rigid folder hierarchy. Good tagging makes faceted search and personal organisation possible in the same workspace.

## Current state

Schema designed; UI mockups approved. Not yet implemented. The search indexer already has a stub tag-filter path that will activate once tags are written to the store.

## Open questions

- Flat tags only, or should we support hierarchical tags (e.g., `project/alpha`)?
- Auto-suggest tags from note content, or manual-only to avoid noise?

## References

- [[capture]] — parent pillar
- [[full-text-search]] — tag filters will be applied here
- [[editor-ux]] — tagging surface in the editor
