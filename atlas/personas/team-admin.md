---
id: persona.team-admin
name: Team Admin
type: persona
layer: "—"
status: planned
owners: [jordan.lee]
lights_up:
  - "[[share]]"
  - "[[auth]]"
  - "[[observability]]"
  - "[[version-history]]"
---

## Why it matters

The team admin manages a shared workspace: inviting members, setting access policies, and auditing changes. This persona gates the share pillar and drives most permission and audit requirements.

## Current state

Persona is defined but the product surface it needs (role enforcement, member management UI, audit log) is not yet shipped. Auth schema supports the role model; UI and API enforcement are wip.

## Open questions

- Should the team admin see a dashboard of workspace activity (notes created, active users)?
- Do we need per-workspace vs per-note permission granularity for the first team plan?

## References

- [[share]] — primary pillar for this persona
- [[auth]] — permission enforcement
- [[version-history]] — audit trail for shared notes
