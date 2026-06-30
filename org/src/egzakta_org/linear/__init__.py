"""Linear API client — shared GraphQL primitive plus ticket/comment helpers.

Used by the atlas drift detector (linear axis) and by `org worktree` for ticket
metadata + soft-claim coordination. Centralizes the auth + transport so we don't
duplicate the urllib pattern across callsites.

Auth: reads `$LINEAR_API_KEY` at the call site. The key is sent only in the
`Authorization` header and never logged, echoed, or interpolated into error
messages — exceptions surface generic status/network info only.
"""

from __future__ import annotations

from .client import (
    LINEAR_API_URL,
    LinearAPIError,
    fetch_issue,
    find_claim_comment,
    graphql,
    post_comment,
)

__all__ = [
    "LINEAR_API_URL",
    "LinearAPIError",
    "fetch_issue",
    "find_claim_comment",
    "graphql",
    "post_comment",
]
