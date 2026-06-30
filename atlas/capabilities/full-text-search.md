---
id: capability.search.full-text-search
name: Full-Text Search
type: capability
layer: L3
parent: "[[search]]"
status: shipped
owners: [jordan.lee]
depends_on:
  - "[[storage]]"
unlocks:
  - "[[version-history]]"
implements: null
code_refs:
  - notewell/src/search/fts.py
  - notewell/src/search/index.py
external_refs:
  competitors: [competitor-a, competitor-b]
  papers: [bm25-survey]
  docs: []
linear:
  initiative:
    name: "Search"
    id: 00000000-0000-0000-0000-0000000000a1
  projects:
    - name: "Query quality"
      id: 00000000-0000-0000-0000-0000000000b1
metrics: [ndcg@10, recall@50]
---

## Why it matters

Full-text search is the primary way users find notes. It must be fast and tolerant of partial matches. Without it, the knowledge base is only navigable by memory of exact titles.

## Current state

BM25 index over note body and title, updated on each save. Latency is sub-100ms at current corpus sizes. Recall@50 meets threshold; ndcg@10 is above baseline but dips on short queries.

## Key decisions

- BM25 chosen over pure semantic search for explainability and zero-shot performance on short corpora.
- Index stored in [[storage]] as a separate table; avoids a dedicated search service.

## Open questions

- At what corpus size do we add a semantic re-rank pass on top of BM25?

## References

- [[search]] — parent pillar
- [[storage]] — index persistence
- [[sync-strategy]] — index updates must be idempotent under concurrent writes
