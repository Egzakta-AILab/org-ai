"""Tests for `egzakta_org.users` — loader, dotted-field accessor, drift signal."""

from __future__ import annotations

from pathlib import Path

import pytest

from egzakta_org.users.loader import (
    load_all_users,
    load_user,
    short_handle_from_linear,
)


# --- helpers --------------------------------------------------------------


def _write_profile(workspace: Path, handle: str, body: str) -> Path:
    pdir = workspace / "platform" / "profiles"
    pdir.mkdir(parents=True, exist_ok=True)
    path = pdir / f"{handle}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _write_repos_yaml(workspace: Path) -> None:
    (workspace / "repos.yaml").write_text(
        "version: 1\nrepos:\n  notewell:\n    url: x\n    status: active\n",
        encoding="utf-8",
    )


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_repos_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- loader -------------------------------------------------------------


def test_load_user_returns_none_when_missing(workspace: Path) -> None:
    assert load_user("nobody") is None


def test_load_user_parses_full_profile(workspace: Path) -> None:
    _write_profile(workspace, "alice", """
handle: alice
linear:
  handle: alice-linear
  user_id: abc-123
  email: alice@example.com
display_name: Alice
git_authors:
  - "Alice <alice@example.com>"
role: senior
areas: [backend, retrieval]
owns:
  - capability.search.hybrid-retrieval
learning:
  - platform.storage
preferences:
  grill_depth: deep
  review_style: terse
  handoff_detail: low
""")
    p = load_user("alice")
    assert p is not None
    assert p.handle == "alice"
    assert p.linear.handle == "alice-linear"
    assert p.linear.user_id == "abc-123"
    assert p.linear.email == "alice@example.com"
    assert p.display_name == "Alice"
    assert p.git_authors == ("Alice <alice@example.com>",)
    assert p.role == "senior"
    assert p.areas == ("backend", "retrieval")
    assert p.owns == ("capability.search.hybrid-retrieval",)
    assert p.learning == ("platform.storage",)
    assert p.preferences.grill_depth == "deep"
    assert p.preferences.review_style == "terse"
    assert p.preferences.handoff_detail == "low"


def test_load_user_falls_back_to_filename_when_handle_missing(workspace: Path) -> None:
    _write_profile(workspace, "bob", "role: junior\n")
    p = load_user("bob")
    assert p is not None
    assert p.handle == "bob"  # derived from filename
    assert p.role == "junior"


def test_preferences_default_when_omitted(workspace: Path) -> None:
    _write_profile(workspace, "carol", "handle: carol\n")
    p = load_user("carol")
    assert p is not None
    assert p.preferences.grill_depth == "medium"
    assert p.preferences.review_style == "balanced"
    assert p.preferences.handoff_detail == "medium"


# --- dotted-field accessor ----------------------------------------------


def test_field_at_simple(workspace: Path) -> None:
    _write_profile(workspace, "alice", "handle: alice\nrole: senior\n")
    p = load_user("alice")
    assert p is not None
    assert p.field_at("handle") == "alice"
    assert p.field_at("role") == "senior"


def test_field_at_nested(workspace: Path) -> None:
    _write_profile(workspace, "alice", """
handle: alice
preferences:
  grill_depth: deep
""")
    p = load_user("alice")
    assert p is not None
    assert p.field_at("preferences.grill_depth") == "deep"


def test_field_at_missing_returns_none(workspace: Path) -> None:
    _write_profile(workspace, "alice", "handle: alice\n")
    p = load_user("alice")
    assert p is not None
    assert p.field_at("preferences.grill_depth") is None
    assert p.field_at("nonexistent") is None


def test_field_at_list_joins(workspace: Path) -> None:
    _write_profile(workspace, "alice", "handle: alice\nareas: [backend, retrieval]\n")
    p = load_user("alice")
    assert p is not None
    assert p.field_at("areas") == "backend, retrieval"


# --- load_all_users -----------------------------------------------------


def test_load_all_users_returns_empty_dict_when_dir_missing(workspace: Path) -> None:
    assert load_all_users() == {}


def test_load_all_users_skips_malformed_files(workspace: Path) -> None:
    _write_profile(workspace, "alice", "handle: alice\n")
    _write_profile(workspace, "broken", "this is: : not: : valid: yaml\n  - x\n  - y\n: nope")
    users = load_all_users()
    # alice loads; broken silently skipped (validate is the place that complains).
    assert "alice" in users
    # broken might or might not parse depending on YAML's tolerance; the contract is
    # that load_all_users doesn't RAISE.


# --- short_handle_from_linear -------------------------------------------


def test_short_handle_from_linear_resolves(workspace: Path) -> None:
    _write_profile(workspace, "jordan", """
handle: jordan
linear:
  handle: jordan-lee
""")
    assert short_handle_from_linear("jordan-lee") == "jordan"


def test_short_handle_from_linear_returns_none_on_miss(workspace: Path) -> None:
    _write_profile(workspace, "jordan", "handle: jordan\nlinear:\n  handle: jordan-lee\n")
    assert short_handle_from_linear("someone-else") is None


def test_short_handle_from_linear_handles_empty_input(workspace: Path) -> None:
    assert short_handle_from_linear("") is None


# --- drift signal (unknown-owner-handle) --------------------------------


def test_unknown_owner_handle_finding_when_profile_missing(workspace: Path) -> None:
    """Atlas node has owner `jordan` but no profile yaml exists → info finding."""
    from egzakta_org.atlas.drift.linear_axis import _check_owner_profiles
    from egzakta_org.atlas import load_atlas

    # Synthetic atlas: one node with owner jordan, but only `alex.yaml` exists.
    atlas = workspace / "atlas"
    (atlas / "capabilities").mkdir(parents=True)
    (atlas / "capabilities" / "x.md").write_text("""---
id: capability.x
name: X
type: capability
status: planned
owners: [jordan]
---
""", encoding="utf-8")
    _write_profile(workspace, "alex", "handle: alex\n")

    index = load_atlas(atlas)
    findings = _check_owner_profiles(index)
    codes = {f.code for f in findings}
    paths = {f.path for f in findings}
    assert "unknown-owner-handle" in codes
    assert "jordan" in paths


def test_unknown_owner_handle_silent_when_no_profiles_yet(workspace: Path) -> None:
    """No profiles registered → don't fan out one finding per atlas owner."""
    from egzakta_org.atlas.drift.linear_axis import _check_owner_profiles
    from egzakta_org.atlas import load_atlas

    atlas = workspace / "atlas"
    (atlas / "capabilities").mkdir(parents=True)
    (atlas / "capabilities" / "x.md").write_text("""---
id: capability.x
name: X
type: capability
status: planned
owners: [jordan, alex]
---
""", encoding="utf-8")
    # No profiles written.

    index = load_atlas(atlas)
    findings = _check_owner_profiles(index)
    assert findings == []


def test_unknown_owner_handle_dedupes_across_nodes(workspace: Path) -> None:
    """Two nodes both owned by `alex`; one finding for `alex`, not two."""
    from egzakta_org.atlas.drift.linear_axis import _check_owner_profiles
    from egzakta_org.atlas import load_atlas

    atlas = workspace / "atlas"
    (atlas / "capabilities").mkdir(parents=True)
    for stem, content in [
        ("a", "id: capability.a\nname: A\ntype: capability\nstatus: planned\nowners: [alex]"),
        ("b", "id: capability.b\nname: B\ntype: capability\nstatus: planned\nowners: [alex]"),
    ]:
        (atlas / "capabilities" / f"{stem}.md").write_text(f"---\n{content}\n---\n", encoding="utf-8")
    _write_profile(workspace, "jordan", "handle: jordan\n")

    index = load_atlas(atlas)
    findings = [f for f in _check_owner_profiles(index) if f.code == "unknown-owner-handle"]
    assert len(findings) == 1
    assert findings[0].path == "alex"
