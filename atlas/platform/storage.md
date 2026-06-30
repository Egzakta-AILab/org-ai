---
id: platform.storage
name: Storage
type: platform
layer: L2
status: stable
owners: [alex.kim]
depends_on: []
unlocks:
  - "[[full-text-search]]"
  - "[[sync-engine]]"
  - "[[backups]]"
code_refs:
  - infra/compose/postgres/
  - notewell/src/db/migrations/
---

## Why it matters

Storage is the foundation every other node builds on. All notes, tags, version snapshots, and search indexes live here. Reliability and schema stability directly gate the stability of the whole product.

## Current state

Postgres (relational + JSON columns for note body). Schema is stable; migrations are applied via Alembic. Separate schema for search index tables. Backup strategy governed by [[backups]].

## Key decisions

- Single Postgres instance (no separate search DB); reduces operational surface for the current scale.
- JSON column for note body allows incremental schema evolution without a migration per body change.

## References

- [[backups]] — disaster-recovery companion
- [[sync-engine]] — writes through to storage
