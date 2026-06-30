"""Content axis — regex-based body-text heuristics for drift.

These checks are intentionally narrow: only patterns we're confident produce
zero false negatives on the audit-known cases. Cross-node fact conflicts
(e.g. Postgres 16 vs 18, three different LLM model claims) are NOT detected
here — they need semantic analysis and belong in an LLM-assisted axis.

Three checks ship in this PR:

- **aspirational-shipped**: a node marked `shipped`/`stable` whose body
  still uses "will" / "we plan to" / "TODO" / "should consider" language.
  Catches the audit's `experience.user-profile`-style cases where status
  outran the prose.

- **calendar-decay-week**: body references "week N" / "in week N" / similar
  cadence markers from time-limited plans. After the plan's horizon passed,
  these references become misleading.

- **calendar-decay-cycle**: body claims a milestone cycle is "active" or
  "live" when the cycle's window has closed (compared against today and the
  milestone's frontmatter dates if available).
"""

from __future__ import annotations

import datetime as dt
import re

from ..model import AtlasIndex
from .model import DriftAxis, DriftFinding

# Phrases that signal aspirational/forward-looking language. Matched
# case-insensitive against the body. Each phrase should be specific enough
# that random text won't trigger it — "will" alone is too noisy, but "we
# plan to" / "we'll" + verb is more reliable.
_ASPIRATIONAL_PHRASES: tuple[str, ...] = (
    r"\bwe\s+plan\s+to\b",
    r"\bwe['’]ll\s+\w+",          # "we'll add", "we'll ship"
    r"\bshould\s+consider\b",
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bnot\s+(yet\s+)?built\b",
    r"\bnot\s+(yet\s+)?(implemented|started)\b",
    r"\bblocked\s+on\b",
    r"\bcurrently\s+(no|none|missing|absent)\b",
)
_ASPIRATIONAL_RE = re.compile("|".join(_ASPIRATIONAL_PHRASES), re.IGNORECASE)

# Note: `\bopen\s+question[s]?\b` is deliberately NOT in the pattern above.
# Every node has a `## Open questions` section per the body template, so
# matching it would fire on every shipped node regardless of whether real
# open-questions bullets exist. A later refinement could parse the section
# body specifically and count non-empty bullets.

# Week-N references from time-boxed plans. Examples we want to catch:
#   "in week 3 of the action plan", "week 4: ship X", "weeks 3-5 we will…"
# We tolerate "weekly" / "week-over-week" since those aren't horizon markers.
_WEEK_REF_RE = re.compile(
    r"\bweek[s]?\s*[-:]?\s*(\d+(?:\s*[–\-]\s*\d+)?)\b",
    re.IGNORECASE,
)

# Cycle-N references. Teams may run 2-week cycles named cycle-N. A node
# saying "cycle 7 is active" when today is past cycle 7's end window is drift.
_CYCLE_REF_RE = re.compile(r"\bcycle[\s-]*(\d+)\b", re.IGNORECASE)

# Statuses that should not contain aspirational language in the body.
_SETTLED_STATUSES: frozenset[str] = frozenset({"shipped", "stable"})


def check_content(
    index: AtlasIndex,
    today: dt.date | None = None,
) -> list[DriftFinding]:
    """Run all three content checks. `today` lets tests pin the calendar."""
    today = today or dt.date.today()
    findings: list[DriftFinding] = []

    findings.extend(_check_aspirational_shipped(index))
    findings.extend(_check_calendar_decay_week(index))
    findings.extend(_check_calendar_decay_cycle(index, today))

    findings.sort(key=lambda f: (f.code, f.node_id or ""))
    return findings


def _check_aspirational_shipped(index: AtlasIndex) -> list[DriftFinding]:
    """Flag settled nodes whose body still uses forward-looking language."""
    findings: list[DriftFinding] = []
    for node in index.nodes:
        if (node.status or "") not in _SETTLED_STATUSES:
            continue
        matches = _ASPIRATIONAL_RE.findall(node.body)
        if not matches:
            continue
        # Surface up to 3 distinct phrases so the user can locate them quickly.
        sample = sorted({_first_str(m) for m in matches})[:3]
        findings.append(
            DriftFinding(
                axis=DriftAxis.CONTENT,
                code="aspirational-shipped",
                severity="warning",
                detail=(
                    f"`status: {node.status}` but body contains forward-looking "
                    f"language: {', '.join(repr(s) for s in sample)}"
                ),
                node_id=node.id,
                suggested="either rewrite body as as-built reality, or demote status to `wip`",
            )
        )
    return findings


def _check_calendar_decay_week(index: AtlasIndex) -> list[DriftFinding]:
    """Flag nodes referencing "week N" markers from past time-boxed plans.

    Heuristic: if the body has any `week N` reference AND there's surrounding
    plan/cycle vocabulary, treat as a calendar marker. References to past
    time-boxed plans are stale and should be updated or removed.
    """
    findings: list[DriftFinding] = []
    for node in index.nodes:
        if not _has_plan_vocabulary(node.body):
            continue
        matches = list(_WEEK_REF_RE.finditer(node.body))
        if not matches:
            continue
        weeks_referenced = sorted({m.group(1).strip() for m in matches})[:5]
        findings.append(
            DriftFinding(
                axis=DriftAxis.CONTENT,
                code="calendar-decay-week",
                severity="info",
                detail=(
                    f"body references week markers ({', '.join(weeks_referenced)}) "
                    "near plan/cycle vocabulary — likely stale calendar pointer"
                ),
                node_id=node.id,
                suggested="replace `week N` with a Linear project link or absolute date",
            )
        )
    return findings


def _check_calendar_decay_cycle(index: AtlasIndex, today: dt.date) -> list[DriftFinding]:
    """Flag cycle-N references whose window has closed.

    Source of truth for cycle windows: any `milestone.cycle-N` node with
    frontmatter `start_date` and `end_date`. If a non-milestone node mentions
    `cycle N` as "active" / "live" but cycle N's `end_date` is in the past,
    flag it.
    """
    cycle_windows = _load_cycle_windows(index)
    if not cycle_windows:
        return []

    findings: list[DriftFinding] = []
    for node in index.nodes:
        if node.type == "milestone":
            continue
        for match in _CYCLE_REF_RE.finditer(node.body):
            cycle_num = int(match.group(1))
            window = cycle_windows.get(cycle_num)
            if not window:
                continue
            end_date = window[1]
            if end_date >= today:
                continue
            # Look at a window of text around the reference for "active" / "live" cues.
            start = max(0, match.start() - 60)
            end_ctx = min(len(node.body), match.end() + 60)
            context = node.body[start:end_ctx].lower()
            if any(cue in context for cue in ("active", "live", "ongoing", "current cycle", "this cycle")):
                findings.append(
                    DriftFinding(
                        axis=DriftAxis.CONTENT,
                        code="calendar-decay-cycle",
                        severity="warning",
                        detail=(
                            f"body describes cycle {cycle_num} as current, "
                            f"but its window closed {end_date.isoformat()} (today: {today.isoformat()})"
                        ),
                        node_id=node.id,
                        suggested=f"update to the current cycle or remove the cycle-{cycle_num} reference",
                    )
                )
                break  # one finding per node is enough
    return findings


# --- helpers --------------------------------------------------------------


_PLAN_VOCAB_RE = re.compile(
    r"\b(action\s+plan|6-?week\s+plan|cycle|sprint|kickoff)\b",
    re.IGNORECASE,
)


def _has_plan_vocabulary(body: str) -> bool:
    return bool(_PLAN_VOCAB_RE.search(body))


def _load_cycle_windows(index: AtlasIndex) -> dict[int, tuple[dt.date, dt.date]]:
    """Read `cycle.N` milestone nodes' `start_date`/`end_date` frontmatter."""
    out: dict[int, tuple[dt.date, dt.date]] = {}
    for node in index.nodes:
        if node.type != "milestone":
            continue
        match = re.search(r"cycle[\s\-_.]*(\d+)", node.id, re.IGNORECASE)
        if not match:
            continue
        start = _coerce_date(node.frontmatter.get("start_date"))
        end = _coerce_date(node.frontmatter.get("end_date"))
        if start and end:
            out[int(match.group(1))] = (start, end)
    return out


def _coerce_date(value: object) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _first_str(match: object) -> str:
    """`re.findall` returns strings OR tuples (when there are groups). Normalize."""
    if isinstance(match, tuple):
        for part in match:
            if part:
                return str(part)
        return ""
    return str(match)


