"""Atlas drift detection — is the graph still in sync with reality?

`validate` answers "is the atlas internally consistent?" — fast, runs at
git-commit time. `drift` answers "is the atlas still accurate?" — slower
checks against external state (code on disk, Linear projects, calendar
dates). Different cadence, different output, kept as a distinct command.

Public surface:
    DriftFinding   — one issue from a single axis (code | linear | content)
    DriftAxis      — enum of axes
    run_drift      — run all enabled axes, return findings

D1 ships the `code` axis only. `linear` and `content` are scaffolded as
follow-up PRs (D2, D3).
"""

from .code_axis import check_code_coverage
from .content_axis import check_content
from .linear_axis import check_linear_sync
from .model import DriftAxis, DriftFinding, DriftReport, run_drift

__all__ = [
    "DriftAxis",
    "DriftFinding",
    "DriftReport",
    "check_code_coverage",
    "check_content",
    "check_linear_sync",
    "run_drift",
]
