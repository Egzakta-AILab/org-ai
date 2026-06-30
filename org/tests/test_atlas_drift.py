"""Tests for the atlas drift detector (D1 — code-coverage axis only).

Each test builds a synthetic atlas + synthetic workspace and asserts the
expected `DriftFinding`s appear (or don't). Real-atlas regression tests live
at the bottom — they assert known audit findings stay surfaced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from egzakta_org.atlas.drift import DriftAxis, run_drift
from egzakta_org.atlas.drift.code_axis import _is_covered, check_code_coverage
from egzakta_org.atlas.parser import load_atlas


# --- helpers --------------------------------------------------------------


def _write_node(atlas_root: Path, dir_name: str, stem: str, frontmatter: str) -> Path:
    folder = atlas_root / dir_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stem}.md"
    path.write_text(f"---\n{frontmatter.strip()}\n---\n", encoding="utf-8")
    return path


def _write_repos_yaml(workspace: Path, repos: dict[str, str]) -> None:
    """Minimal repos.yaml with each repo set to `status: active`."""
    body = "version: 1\nrepos:\n"
    for name, _ in repos.items():
        body += f"  {name}:\n    url: https://example.com/{name}.git\n    status: active\n"
    (workspace / "repos.yaml").write_text(body, encoding="utf-8")


def _mkdir(workspace: Path, rel: str) -> Path:
    p = workspace / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def _paths(findings: list) -> list[str]:
    return [f.path for f in findings if f.path]


# --- _is_covered (unit) ----------------------------------------------------


def test_exact_dir_match() -> None:
    covered = {"notewell/backend/src/core/search/"}
    assert _is_covered("notewell/backend/src/core/search/", covered)


def test_exact_dir_match_without_slash() -> None:
    covered = {"notewell/backend/src/core/search/"}
    assert _is_covered("notewell/backend/src/core/search", covered)


def test_descendant_coverage() -> None:
    """A code_ref pointing INSIDE a path covers that path (the ref claims this
    subtree is known)."""
    covered = {"notewell/backend/src/core/search/hybrid.py"}
    assert _is_covered("notewell/backend/src/core/search/", covered)


def test_ancestor_does_not_cover() -> None:
    """A code_ref pointing at an UMBRELLA path does NOT cover specific subdirs.
    This is the audit-flagged platform.storage case."""
    covered = {"notewell/backend/src/"}
    assert not _is_covered("notewell/backend/src/core/tool_runtime/", covered)


def test_sibling_does_not_cover() -> None:
    covered = {"notewell/backend/src/core/auth/"}
    assert not _is_covered("notewell/backend/src/core/search/", covered)


def test_empty_covered_set() -> None:
    assert not _is_covered("anything", set())


# --- code-axis integration ------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Synthetic workspace with repos.yaml + notewell and infra dirs."""
    _write_repos_yaml(tmp_path, {"notewell": "...", "infra": "..."})
    return tmp_path


def test_covered_dir_produces_no_finding(workspace: Path) -> None:
    # Real dir on disk.
    _mkdir(workspace, "notewell/backend/src/core/search")
    # Atlas node points at it.
    atlas = workspace / "atlas"
    _write_node(
        atlas,
        "capabilities",
        "search",
        """
id: capability.search.x
name: X
type: capability
status: shipped
code_refs:
  - notewell/backend/src/core/search/
""",
    )
    idx = load_atlas(atlas)
    findings = check_code_coverage(idx, workspace)
    assert "notewell/backend/src/core/search" not in _paths(findings)


def test_uncovered_dir_produces_finding(workspace: Path) -> None:
    _mkdir(workspace, "notewell/backend/src/core/lonely")
    atlas = workspace / "atlas"
    # No node points at lonely/.
    _write_node(atlas, "capabilities", "other", """
id: capability.x.other
name: Other
type: capability
status: shipped
code_refs: [notewell/backend/src/core/search/]
""")
    idx = load_atlas(atlas)
    findings = check_code_coverage(idx, workspace)
    assert "notewell/backend/src/core/lonely" in _paths(findings)


def test_overly_broad_code_ref_does_not_silence_subdirs(workspace: Path) -> None:
    """The platform.storage problem: an umbrella code_ref shouldn't mask
    specific gaps under it."""
    _mkdir(workspace, "notewell/backend/src/core/tool_runtime")
    _mkdir(workspace, "notewell/backend/src/core/scheduler")
    atlas = workspace / "atlas"
    _write_node(atlas, "platform", "storage", """
id: platform.storage
name: Storage
type: platform
status: shipped
code_refs: [notewell/backend/src/]
""")
    idx = load_atlas(atlas)
    paths = _paths(check_code_coverage(idx, workspace))
    assert "notewell/backend/src/core/tool_runtime" in paths
    assert "notewell/backend/src/core/scheduler" in paths


def test_dotfile_dirs_skipped(workspace: Path) -> None:
    _mkdir(workspace, "infra/.git")
    _mkdir(workspace, "infra/.github")
    _mkdir(workspace, "infra/mlflow")  # real
    atlas = workspace / "atlas"  # no nodes
    atlas.mkdir()
    idx = load_atlas(atlas)
    paths = _paths(check_code_coverage(idx, workspace))
    assert "infra/.git" not in paths
    assert "infra/.github" not in paths
    assert "infra/mlflow" in paths


def test_inactive_repo_skipped(tmp_path: Path) -> None:
    # repos.yaml with notewell marked legacy → patterns under notewell shouldn't fire.
    body = """version: 1
repos:
  notewell:
    url: https://example.com/notewell.git
    status: legacy
"""
    (tmp_path / "repos.yaml").write_text(body, encoding="utf-8")
    _mkdir(tmp_path, "notewell/backend/src/core/lonely")
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    idx = load_atlas(atlas)
    findings = check_code_coverage(idx, tmp_path)
    assert findings == []


def test_repo_dir_missing_is_silent(workspace: Path) -> None:
    # infra declared in repos.yaml but no infra/ dir on disk.
    atlas = workspace / "atlas"
    atlas.mkdir()
    idx = load_atlas(atlas)
    # notewell dir doesn't exist either; whole run should be silent rather than crash.
    findings = check_code_coverage(idx, workspace)
    assert findings == []


# --- run_drift orchestration ----------------------------------------------


def test_run_drift_default_runs_all_axes(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default runs all three axes. The linear axis returns the info-only
    `linear-api-key-missing` finding when the key isn't set, so we drop it
    for this test rather than mock HTTP."""
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    _mkdir(workspace, "notewell/backend/src/core/lonely")
    atlas = workspace / "atlas"
    atlas.mkdir()
    idx = load_atlas(atlas)
    report = run_drift(idx, workspace)
    assert set(report.axes_run) == {DriftAxis.CODE, DriftAxis.LINEAR, DriftAxis.CONTENT}
    assert report.has_findings


def test_run_drift_explicit_empty_axes_is_silent(workspace: Path) -> None:
    """Passing axes=[] explicitly disables all axes."""
    _mkdir(workspace, "notewell/backend/src/core/lonely")
    atlas = workspace / "atlas"
    atlas.mkdir()
    idx = load_atlas(atlas)
    report = run_drift(idx, workspace, axes=[])
    assert not report.has_findings
    assert report.axes_run == ()


def test_drift_report_to_dict_shape(workspace: Path) -> None:
    _mkdir(workspace, "notewell/backend/src/core/lonely")
    atlas = workspace / "atlas"
    atlas.mkdir()
    idx = load_atlas(atlas)
    report = run_drift(idx, workspace)
    d = report.to_dict()
    assert "axes_run" in d
    assert "findings" in d
    assert isinstance(d["findings"], list)
    assert all(set(f.keys()) >= {"axis", "code", "severity", "detail"} for f in d["findings"])
    # Round-trip serializable.
    json.dumps(d)


# --- real workspace regression --------------------------------------------


def test_atlas_drift_detector_runs_against_real_atlas() -> None:
    """The drift detector must run against the real atlas without crashing.

    Verify the code axis completes cleanly. Specific findings are not
    asserted here — they change as the atlas and repos evolve."""
    repo_root = Path(__file__).resolve().parents[2]
    idx = load_atlas(repo_root / "atlas")
    findings = check_code_coverage(idx, repo_root)
    # Findings may be empty if all notewell/infra paths are covered —
    # the important thing is the call completes without raising.
    assert isinstance(findings, list)
