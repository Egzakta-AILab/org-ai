"""Tests for the atlas validator checks added in the ontology-hardening pass.

Each test builds a minimal atlas tree on disk and asserts that the relevant
check produces (or suppresses) the expected Issue. Direct-fixture style keeps
the tests legible; we don't share fixtures across check types because each
check has its own narrow shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from egzakta_org.atlas.model import (
    CODE_REFS_REQUIRED_TYPES,
    KNOWN_STATUSES,
    METRICS_REQUIRED_STATUSES,
    STATUS_REQUIRED_TYPES,
)
from egzakta_org.atlas.parser import load_atlas
from egzakta_org.atlas.validate import Issue, validate


def _write_node(atlas_root: Path, dir_name: str, stem: str, frontmatter: str, body: str = "") -> Path:
    folder = atlas_root / dir_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stem}.md"
    path.write_text(f"---\n{frontmatter.strip()}\n---\n{body}", encoding="utf-8")
    return path


def _validate(atlas_root: Path, workspace_root: Path | None = None) -> list[Issue]:
    index = load_atlas(atlas_root)
    return validate(index, workspace_root=workspace_root or atlas_root.parent)


def _codes(issues: list[Issue], node: str | None = None) -> list[str]:
    return [i.code for i in issues if node is None or i.node == node]


# --- constants -------------------------------------------------------------


def test_known_statuses_set() -> None:
    assert KNOWN_STATUSES == frozenset(
        {"research", "planned", "wip", "shipped", "stable", "deprecated"}
    )


def test_required_type_sets_disjoint_persona_milestone() -> None:
    # persona + milestone must be exempt from code_refs.
    assert "persona" not in CODE_REFS_REQUIRED_TYPES
    assert "milestone" not in CODE_REFS_REQUIRED_TYPES
    # status is not required on persona/keystone/pillar.
    assert "persona" not in STATUS_REQUIRED_TYPES
    assert "keystone" not in STATUS_REQUIRED_TYPES
    assert "pillar" not in STATUS_REQUIRED_TYPES
    # capability has metrics required iff shipped/stable.
    assert METRICS_REQUIRED_STATUSES == frozenset({"shipped", "stable"})


# --- invalid status --------------------------------------------------------


def test_invalid_status_warns(tmp_path: Path) -> None:
    _write_node(
        tmp_path,
        "capabilities",
        "x",
        """
id: capability.search.x
name: X
type: capability
layer: L3
status: in-flight
code_refs: [notewell/]
""",
    )
    issues = _validate(tmp_path)
    assert "invalid-status" in _codes(issues, "capability.search.x")


def test_stable_and_deprecated_are_valid_statuses(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "a", """
id: capability.search.a
name: A
type: capability
status: stable
code_refs: [notewell/]
metrics: [ndcg@10]
""")
    _write_node(tmp_path, "capabilities", "b", """
id: capability.search.b
name: B
type: capability
status: deprecated
code_refs: [notewell/]
""")
    issues = _validate(tmp_path)
    assert "invalid-status" not in _codes(issues)


# --- missing-code-refs ----------------------------------------------------


def test_missing_code_refs_warns_on_shipped_node(tmp_path: Path) -> None:
    _write_node(tmp_path, "platform", "x", """
id: platform.x
name: X
type: platform
status: shipped
""")
    assert "missing-code-refs" in _codes(_validate(tmp_path), "platform.x")


def test_missing_code_refs_silent_on_research(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: research
""")
    assert "missing-code-refs" not in _codes(_validate(tmp_path))


def test_missing_code_refs_silent_on_planned(tmp_path: Path) -> None:
    """PR A2 refinement: `planned` nodes legitimately have no code yet, so
    requiring code_refs would be a false positive (was a pillar.agents-style
    bug in PR A1)."""
    _write_node(tmp_path, "platform", "x", """
id: platform.x
name: X
type: platform
status: planned
""")
    assert "missing-code-refs" not in _codes(_validate(tmp_path))


def test_missing_code_refs_silent_on_persona(tmp_path: Path) -> None:
    _write_node(tmp_path, "personas", "x", """
id: persona.x
name: X
type: persona
""")
    assert "missing-code-refs" not in _codes(_validate(tmp_path))


# --- wip-no-code-refs -----------------------------------------------------


def test_wip_no_code_refs_warns(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: wip
""")
    codes = _codes(_validate(tmp_path), "capability.search.x")
    assert "wip-no-code-refs" in codes
    # Also fires missing-code-refs — both are real signals (one says "promote
    # or demote", the other says "this isn't actually in progress").
    assert "missing-code-refs" in codes


def test_wip_with_code_refs_silent(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: wip
code_refs: [notewell/backend/src/foo/]
""")
    assert "wip-no-code-refs" not in _codes(_validate(tmp_path))


# --- missing-metrics ------------------------------------------------------


def test_shipped_capability_without_metrics_errors(tmp_path: Path) -> None:
    """Severity flipped to error in PR A2 — the rule is now load-bearing."""
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
""")
    issues = _validate(tmp_path)
    metric_issues = [i for i in issues if i.code == "missing-metrics" and i.node == "capability.search.x"]
    assert metric_issues, "expected one missing-metrics issue"
    assert metric_issues[0].severity == "error"


def test_stable_capability_with_metrics_silent(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: stable
code_refs: [notewell/]
metrics: [ndcg@10, recall@50]
""")
    assert "missing-metrics" not in _codes(_validate(tmp_path))


def test_planned_capability_without_metrics_silent(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: planned
code_refs: [notewell/]
""")
    assert "missing-metrics" not in _codes(_validate(tmp_path))


def test_shipped_platform_without_metrics_silent(tmp_path: Path) -> None:
    # Metrics requirement is capability-only.
    _write_node(tmp_path, "platform", "x", """
id: platform.x
name: X
type: platform
status: shipped
code_refs: [notewell/]
""")
    assert "missing-metrics" not in _codes(_validate(tmp_path))


# --- legacy-linear-shape --------------------------------------------------


def test_legacy_linear_initiative_errors(tmp_path: Path) -> None:
    """Severity flipped to error in PR A2 — atlas data is fully migrated, so
    any new string-form entry indicates an authoring mistake worth blocking."""
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: planned
code_refs: [notewell/]
linear:
  initiative: Search
""")
    issues = _validate(tmp_path)
    legacy = [i for i in issues if i.code == "legacy-linear-shape" and i.node == "capability.search.x"]
    assert legacy, "expected legacy-linear-shape issue"
    assert legacy[0].severity == "error"


def test_legacy_linear_projects_errors(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: planned
code_refs: [notewell/]
linear:
  projects:
    - Search v1
""")
    assert "legacy-linear-shape" in _codes(_validate(tmp_path), "capability.search.x")


def test_canonical_linear_shape_silent(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: planned
code_refs: [notewell/]
linear:
  initiative: {name: Search, id: 0f7dbb92}
  projects:
    - {name: Search v1, id: abcd-1234}
""")
    assert "legacy-linear-shape" not in _codes(_validate(tmp_path))


# --- dangling-frontmatter-link --------------------------------------------


def test_unresolved_depends_on_warns(tmp_path: Path) -> None:
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: planned
code_refs: [notewell/]
depends_on:
  - "[[does-not-exist]]"
""")
    issues = _codes(_validate(tmp_path), "capability.search.x")
    assert "dangling-frontmatter-link" in issues


def test_resolved_depends_on_silent(tmp_path: Path) -> None:
    _write_node(tmp_path, "platform", "storage", """
id: platform.storage
name: Storage
type: platform
status: shipped
code_refs: [notewell/]
""")
    _write_node(tmp_path, "capabilities", "x", """
id: capability.search.x
name: X
type: capability
status: planned
code_refs: [notewell/]
depends_on:
  - "[[storage]]"
""")
    assert "dangling-frontmatter-link" not in _codes(_validate(tmp_path))


# --- dependency-cycle -----------------------------------------------------


def test_two_node_cycle_warns(tmp_path: Path) -> None:
    _write_node(tmp_path, "platform", "a", """
id: platform.a
name: A
type: platform
status: shipped
code_refs: [notewell/]
depends_on:
  - "[[b]]"
""")
    _write_node(tmp_path, "platform", "b", """
id: platform.b
name: B
type: platform
status: shipped
code_refs: [notewell/]
depends_on:
  - "[[a]]"
""")
    issues = _validate(tmp_path)
    cycle_issues = [i for i in issues if i.code == "dependency-cycle"]
    assert len(cycle_issues) == 2
    assert {i.node for i in cycle_issues} == {"platform.a", "platform.b"}


def test_three_node_cycle_warns(tmp_path: Path) -> None:
    for name, dep in [("a", "b"), ("b", "c"), ("c", "a")]:
        _write_node(tmp_path, "platform", name, f"""
id: platform.{name}
name: {name.upper()}
type: platform
status: shipped
code_refs: [notewell/]
depends_on:
  - "[[{dep}]]"
""")
    issues = _validate(tmp_path)
    cycle_issues = [i for i in issues if i.code == "dependency-cycle"]
    assert len(cycle_issues) == 3


def test_no_cycle_silent(tmp_path: Path) -> None:
    _write_node(tmp_path, "platform", "a", """
id: platform.a
name: A
type: platform
status: shipped
code_refs: [notewell/]
""")
    _write_node(tmp_path, "platform", "b", """
id: platform.b
name: B
type: platform
status: shipped
code_refs: [notewell/]
depends_on:
  - "[[a]]"
""")
    assert "dependency-cycle" not in _codes(_validate(tmp_path))


def test_self_loop_not_flagged_as_cycle(tmp_path: Path) -> None:
    # Graph construction filters self-loops (`if resolved != node.id`). A self
    # loop is a separate kind of mistake; surfacing it as a "cycle" would be
    # misleading.
    _write_node(tmp_path, "platform", "a", """
id: platform.a
name: A
type: platform
status: shipped
code_refs: [notewell/]
depends_on:
  - "[[a]]"
""")
    assert "dependency-cycle" not in _codes(_validate(tmp_path))


# --- real atlas regression --------------------------------------------------


@pytest.fixture
def real_atlas_root() -> Path:
    return Path(__file__).resolve().parents[2] / "atlas"


def test_real_atlas_loads_and_has_no_errors(real_atlas_root: Path) -> None:
    """The shipped atlas must always validate clean (errors = 0).

    Warnings are expected during the migration (PR A2 will close them).
    """
    index = load_atlas(real_atlas_root)
    issues = validate(index, workspace_root=real_atlas_root.parent)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], f"atlas has {len(errors)} validation errors: {errors[:3]}"


def test_real_atlas_has_no_dependency_cycles(real_atlas_root: Path) -> None:
    """Cycles broken in this PR must stay broken."""
    index = load_atlas(real_atlas_root)
    issues = validate(index, workspace_root=real_atlas_root.parent)
    cycle_issues = [i for i in issues if i.code == "dependency-cycle"]
    assert cycle_issues == [], (
        f"atlas regressed into {len(cycle_issues)} cycle warnings: "
        f"{[i.detail for i in cycle_issues[:3]]}"
    )
