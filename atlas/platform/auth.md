---
id: platform.auth
name: Auth
type: platform
layer: L2
status: shipped
owners: [alex.kim]
depends_on:
  - "[[storage]]"
unlocks:
  - "[[share]]"
code_refs:
  - notewell/src/auth/
  - infra/compose/auth/
---

## Why it matters

Auth controls who can access what. Without it, sharing is not safe to ship and multi-user workspaces cannot be isolated. Every sharing and permission surface depends on a correct auth layer.

## Current state

Email + password auth with session tokens is shipped. OAuth (Google) is implemented but not yet enabled in production. Role model (owner / editor / viewer) schema exists; enforcement is partial — see [[share]].

## Key decisions

- Session tokens stored in the database (not stateless JWT) to allow instant revocation.
- Role model scoped at workspace level for simplicity; per-note ACLs deferred to a later iteration.

## Open questions

- When do we enable SSO / SAML for team plans?

## References

- [[share]] — consuming pillar
- [[storage]] — session and user tables live here
