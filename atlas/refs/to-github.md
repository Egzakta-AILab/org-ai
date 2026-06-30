# Code Reference Index — GitHub

Maps `code_refs` path prefixes (used in atlas node frontmatter) to their GitHub repositories.

The validator (`org atlas validate`) resolves wikilinks against this file to produce full GitHub URLs for CI linking and Obsidian hover previews.

## Prefix map

| Prefix | Repository | URL | Status |
|---|---|---|---|
| `notewell/` | Main app — API + web | https://github.com/your-org/notewell | active |
| `infra/` | Shared infra (compose stacks, scripts) | https://github.com/your-org/infra | active |
| `legacy-wiki/` | Previous iteration, migrating out | https://github.com/your-org/legacy-wiki | legacy |
| `search-lab/` | Search-quality experiments | https://github.com/your-org/search-lab | experimental |

## Usage

In a node's frontmatter:

```yaml
code_refs:
  - notewell/src/search/fts.py
  - infra/compose/postgres/
```

The validator expands `notewell/src/search/fts.py` →
`https://github.com/your-org/notewell/blob/main/src/search/fts.py`.

Paths that do not match any prefix produce a `unresolved-code-ref` warning.
