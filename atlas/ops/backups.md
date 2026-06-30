---
id: ops.backups
name: Backups
type: ops
layer: L1
status: shipped
owners: [alex.kim]
depends_on:
  - "[[storage]]"
unlocks: []
code_refs:
  - infra/scripts/backup.sh
  - infra/compose/backup/
---

## Why it matters

Backups are the last line of defence against data loss from bugs, operator error, or infrastructure failure. Without tested backups, shipped features have no safety net.

## Current state

Daily Postgres dumps to object storage, retained for 30 days. Restore procedure documented and tested manually. No automated restore drill yet.

## Key decisions

- Object storage (S3-compatible) for backup destination — infrastructure-independent and cheap.
- Logical dumps (pg_dump) rather than physical snapshots for portability across Postgres versions.

## Open questions

- Should we add point-in-time recovery (WAL archiving) for the production database?
- When do we automate restore drills in CI?

## References

- [[storage]] — the source of truth being backed up
- [[observability]] — backup job success/failure is monitored here
