---
id: ops.observability
name: Observability
type: ops
layer: L1
status: wip
owners: [alex.kim]
depends_on: []
unlocks: []
code_refs:
  - infra/compose/metrics/
  - notewell/src/telemetry/
---

## Why it matters

Without observability, incidents are discovered by users, not engineers. Metrics, logs, and traces are the foundation for reliable operations, capacity planning, and debugging production issues quickly.

## Current state

Structured logging is in place (JSON, shipped to log aggregator). Basic uptime metrics collected. Distributed tracing is stub-only. No alerting rules defined yet. Backup job success is not yet included in the dashboard.

## Open questions

- Which metrics matter most for the sync engine's CRDT merge latency?
- Should we self-host the metrics stack or use a managed service?

## References

- [[backups]] — backup success metrics belong here
- [[sync-engine]] — highest-value instrumentation target
