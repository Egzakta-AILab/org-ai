"""Linear GraphQL transport + the handful of queries we share across commands.

Networking: stdlib `urllib.request` so we don't pull in `httpx` for a single
endpoint. Failures (network, 401, 5xx, GraphQL errors) raise `LinearAPIError`
with intentionally generic detail — never include the request body or the API
key in the message.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

LINEAR_API_URL = "https://api.linear.app/graphql"
_TIMEOUT_SECONDS = 15


class LinearAPIError(RuntimeError):
    """API call failed. Message intentionally does not include the API key."""


def graphql(api_key: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """One GraphQL POST. Raises `LinearAPIError` on any failure."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        LINEAR_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LinearAPIError(f"HTTP {exc.code} from Linear API") from None
    except urllib.error.URLError as exc:
        raise LinearAPIError(f"network error contacting Linear API: {exc.reason}") from None
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise LinearAPIError(f"{type(exc).__name__} parsing Linear API response") from None

    if "errors" in payload:
        first = payload["errors"][0].get("message", "unknown error")
        raise LinearAPIError(f"Linear API returned errors: {first}")
    return payload.get("data") or {}


# --- ticket / comment helpers ---------------------------------------------


def fetch_issue(api_key: str, identifier: str) -> dict[str, Any] | None:
    """Fetch one issue by identifier (e.g. ``NW-456``). Returns ``None`` if not found.

    Pulls fields needed by `org worktree`: id, identifier, title, state, labels
    (for `atlas:<node-id>` parsing), assignee handle.
    """
    query = """
    query IssueByIdentifier($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        state { name type }
        labels { nodes { id name } }
        assignee { id name displayName }
      }
    }
    """
    data = graphql(api_key, query, {"id": identifier})
    issue = data.get("issue")
    return issue if issue else None


def post_comment(api_key: str, issue_id: str, body: str) -> str:
    """Post a comment on an issue. Returns the new comment's id."""
    query = """
    mutation Comment($input: CommentCreateInput!) {
      commentCreate(input: $input) { success comment { id } }
    }
    """
    data = graphql(api_key, query, {"input": {"issueId": issue_id, "body": body}})
    result = data.get("commentCreate") or {}
    if not result.get("success"):
        raise LinearAPIError("commentCreate did not succeed")
    return str(result["comment"]["id"])


def find_claim_comment(
    api_key: str,
    issue_id: str,
    marker: str,
    *,
    since_hours: int = 24,
) -> dict[str, Any] | None:
    """Return the most recent comment whose body starts with ``marker`` and is
    newer than ``since_hours`` hours. Returns ``None`` if no match.

    Used by `org worktree create` to detect existing claims and refuse to
    double-claim a ticket. The marker is a fixed prefix so claims from other
    devs are recognizable without parsing the whole comment body.
    """
    query = """
    query Comments($id: String!) {
      issue(id: $id) {
        comments(first: 50, orderBy: createdAt) {
          nodes { id body createdAt user { id name displayName } }
        }
      }
    }
    """
    data = graphql(api_key, query, {"id": issue_id})
    issue = data.get("issue") or {}
    comments = ((issue.get("comments") or {}).get("nodes")) or []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=since_hours)
    matching: list[dict[str, Any]] = []
    for comment in comments:
        body = comment.get("body", "")
        if not body.startswith(marker):
            continue
        created_raw = comment.get("createdAt", "")
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if created >= cutoff:
            matching.append(comment)
    if not matching:
        return None
    # Most recent wins.
    matching.sort(key=lambda c: c.get("createdAt", ""), reverse=True)
    return matching[0]
