"""Tests for the linear axis (D2) of `org atlas drift`.

We mock `urllib.request.urlopen` so tests are deterministic and don't hit
Linear. The fake response payload mirrors Linear's GraphQL shape closely
enough that the real call path exercises in tests.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from egzakta_org.atlas.drift import DriftAxis
from egzakta_org.atlas.drift.linear_axis import check_linear_sync
from egzakta_org.atlas.parser import load_atlas


def _write_node(atlas_root: Path, dir_name: str, stem: str, frontmatter: str) -> Path:
    folder = atlas_root / dir_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stem}.md"
    path.write_text(f"---\n{frontmatter.strip()}\n---\n", encoding="utf-8")
    return path


def _codes(findings) -> list[str]:
    return [f.code for f in findings]


class _FakeResponse:
    """Stand-in for the context-managed object urlopen returns."""

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _projects_response(projects: list[dict]) -> dict:
    return {
        "data": {
            "team": {
                "projects": {"nodes": projects},
            }
        }
    }


# --- key-missing path -----------------------------------------------------


def test_axis_skips_silently_when_key_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The axis must not crash when $LINEAR_API_KEY is unset — useful in CI
    where the key isn't always available."""
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    findings = check_linear_sync(load_atlas(atlas))
    assert _codes(findings) == ["linear-api-key-missing"]
    assert findings[0].severity == "info"
    assert findings[0].axis == DriftAxis.LINEAR


# --- ID resolution --------------------------------------------------------


def test_broken_linear_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    _write_node(
        atlas, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
linear:
  projects:
    - {name: Gone, id: dead-project-id}
""",
    )
    fake = _projects_response([])  # no projects at all → ID won't resolve
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    assert "broken-linear-project" in _codes(findings)


def test_resolved_project_is_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    _write_node(
        atlas, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
linear:
  projects:
    - {name: Foo, id: live-1}
""",
    )
    fake = _projects_response([
        {"id": "live-1", "name": "Foo", "state": "completed", "initiatives": {"nodes": []}},
    ])
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    assert "broken-linear-project" not in _codes(findings)


# --- status mapping -------------------------------------------------------


def test_status_mismatch_shipped_vs_started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """atlas says shipped (expects completed); Linear says started → mismatch."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    _write_node(
        atlas, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
linear:
  projects:
    - {name: Foo, id: live-1}
""",
    )
    fake = _projects_response([
        {"id": "live-1", "name": "Foo", "state": "started", "initiatives": {"nodes": []}},
    ])
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    assert "status-mismatch" in _codes(findings)


def test_status_match_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    _write_node(
        atlas, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: wip
code_refs: [notewell/]
linear:
  projects:
    - {name: Foo, id: live-1}
""",
    )
    fake = _projects_response([
        {"id": "live-1", "name": "Foo", "state": "started", "initiatives": {"nodes": []}},
    ])
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    assert "status-mismatch" not in _codes(findings)


# --- inverse coverage ----------------------------------------------------


def test_unbacked_linear_project_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Active Linear project with no atlas node referencing it → info finding."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    atlas.mkdir()  # zero nodes
    fake = _projects_response([
        {"id": "alone-1", "name": "Lonely Project", "state": "started", "initiatives": {"nodes": []}},
    ])
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    codes = _codes(findings)
    assert "unbacked-linear-project" in codes


def test_unbacked_skips_dead_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Linear project in `canceled` or `completed` state isn't flagged as
    unbacked — too noisy to ask for atlas coverage of dead projects."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    fake = _projects_response([
        {"id": "dead-1", "name": "Old", "state": "canceled", "initiatives": {"nodes": []}},
        {"id": "done-1", "name": "Shipped", "state": "completed", "initiatives": {"nodes": []}},
    ])
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    assert "unbacked-linear-project" not in _codes(findings)


# --- API failure path ----------------------------------------------------


def test_http_error_produces_one_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing API call must emit a single `linear-api-error` finding (no
    per-node noise) and not leak the API key."""
    import urllib.error

    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_secret_value_should_not_appear")
    atlas = tmp_path / "atlas"
    _write_node(atlas, "capabilities", "x", """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
linear:
  projects:
    - {name: Foo, id: x}
""")
    err = urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO())  # type: ignore[arg-type]
    with patch("urllib.request.urlopen", side_effect=err):
        findings = check_linear_sync(load_atlas(atlas))
    assert _codes(findings) == ["linear-api-error"]
    # API key must NEVER leak into a finding's detail.
    assert "lin_api_secret_value_should_not_appear" not in findings[0].detail


# --- all findings carry correct axis -------------------------------------


def test_findings_carry_linear_axis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    atlas = tmp_path / "atlas"
    _write_node(atlas, "capabilities", "x", """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
linear:
  projects:
    - {name: Gone, id: dead}
""")
    fake = _projects_response([])
    with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
        findings = check_linear_sync(load_atlas(atlas))
    for f in findings:
        assert f.axis == DriftAxis.LINEAR
