"""Shared types for drift detection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from ..model import AtlasIndex


class DriftAxis(str, Enum):
    """Which surface the finding compares the atlas against."""

    CODE = "code"
    LINEAR = "linear"        # D2 scope
    CONTENT = "content"      # D3 scope


@dataclass(frozen=True)
class DriftFinding:
    """One drift observation. Stable shape across axes so a single output
    formatter (text / JSON) can render them uniformly."""

    axis: DriftAxis
    code: str               # short machine-readable kind, e.g. "uncovered-code-path"
    severity: str           # "info" | "warning" | "error" — keep aligned with validate.Issue
    detail: str             # human-readable one-liner
    path: str | None = None  # filesystem path or atlas rel_path, when applicable
    node_id: str | None = None  # atlas node id, when the finding is anchored to a node
    suggested: str | None = None  # optional concrete next step (e.g. "add node platform.scheduler")

    def to_dict(self) -> dict[str, str | None]:
        out = asdict(self)
        out["axis"] = self.axis.value
        return out


@dataclass(frozen=True)
class DriftReport:
    """Findings from one run, plus light metadata for machine consumers."""

    findings: tuple[DriftFinding, ...]
    axes_run: tuple[DriftAxis, ...] = field(default_factory=tuple)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "axes_run": [a.value for a in self.axes_run],
            "findings": [f.to_dict() for f in self.findings],
        }


def run_drift(
    index: AtlasIndex,
    workspace_root: Path,
    axes: Iterable[DriftAxis] | None = None,
) -> DriftReport:
    """Run the enabled axes and return a single combined report.

    Default (axes=None) runs all three axes (code, linear, content). Pass
    an explicit list to scope. The order in `axes_run` reflects the order
    findings were appended — useful for output grouping.
    """
    # Local imports to avoid circulars when downstream code re-exports.
    from .code_axis import check_code_coverage
    from .content_axis import check_content
    from .linear_axis import check_linear_sync

    requested = tuple(axes) if axes is not None else (DriftAxis.CODE, DriftAxis.LINEAR, DriftAxis.CONTENT)
    findings: list[DriftFinding] = []
    axes_run: list[DriftAxis] = []

    if DriftAxis.CODE in requested:
        findings.extend(check_code_coverage(index, workspace_root))
        axes_run.append(DriftAxis.CODE)

    if DriftAxis.LINEAR in requested:
        findings.extend(check_linear_sync(index))
        axes_run.append(DriftAxis.LINEAR)

    if DriftAxis.CONTENT in requested:
        findings.extend(check_content(index))
        axes_run.append(DriftAxis.CONTENT)

    return DriftReport(findings=tuple(findings), axes_run=tuple(axes_run))
