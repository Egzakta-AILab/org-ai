"""Tests for the content axis (D3) of `org atlas drift`.

Each test builds a synthetic atlas with a single node, sets its body to a
specific phrase, and asserts which check fires (or doesn't). Calendar checks
take a pinned `today` so they're stable.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from egzakta_org.atlas.drift import DriftAxis
from egzakta_org.atlas.drift.content_axis import check_content
from egzakta_org.atlas.parser import load_atlas


def _write_node(atlas_root: Path, dir_name: str, stem: str, frontmatter: str, body: str = "") -> Path:
    folder = atlas_root / dir_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stem}.md"
    path.write_text(f"---\n{frontmatter.strip()}\n---\n{body}", encoding="utf-8")
    return path


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


# --- aspirational-shipped --------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "we plan to ship this in Q3",
        "we'll add this when the API is ready",
        "TODO: wire up the new endpoint",
        "TBD",
        "should consider switching to Postgres 18",
        "blocked on the auth team",
        "currently no rate limiting in place",
        "not yet built",
        "not implemented",
    ],
)
def test_aspirational_phrase_fires_on_shipped(tmp_path: Path, phrase: str) -> None:
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [ndcg@10]
""",
        body=f"## Why it matters\nSome prose. {phrase}\n",
    )
    findings = check_content(load_atlas(tmp_path))
    assert "aspirational-shipped" in _codes(findings)


def test_aspirational_silent_on_planned(tmp_path: Path) -> None:
    """`planned` nodes are EXPECTED to use forward-looking language."""
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: planned
""",
        body="## Why\nWe plan to ship this. TODO: design the API.\n",
    )
    findings = check_content(load_atlas(tmp_path))
    assert "aspirational-shipped" not in _codes(findings)


def test_open_questions_section_header_does_not_trigger(tmp_path: Path) -> None:
    """Every node has `## Open questions` per the body template. The header
    alone must not fire aspirational-shipped."""
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [ndcg@10]
""",
        body="## Why\nIt works.\n\n## Open questions\n- Some bullet.\n",
    )
    findings = check_content(load_atlas(tmp_path))
    assert "aspirational-shipped" not in _codes(findings)


def test_aspirational_fires_on_stable_too(tmp_path: Path) -> None:
    """`stable` is even stronger than `shipped` — also must not be aspirational."""
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: stable
code_refs: [notewell/]
metrics: [ndcg@10]
""",
        body="we plan to refactor this later",
    )
    findings = check_content(load_atlas(tmp_path))
    assert "aspirational-shipped" in _codes(findings)


# --- calendar-decay-week --------------------------------------------------


def test_week_decay_fires_with_plan_vocabulary(tmp_path: Path) -> None:
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: planned
""",
        body="In week 3 of the action plan we ship X.\n",
    )
    assert "calendar-decay-week" in _codes(check_content(load_atlas(tmp_path)))


def test_week_decay_silent_without_plan_vocabulary(tmp_path: Path) -> None:
    """A bare `week 3` reference without action-plan / cycle / sprint vocabulary
    is NOT flagged — could be referring to onboarding week 3, etc."""
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: planned
""",
        body="Onboarding step at week 3.\n",
    )
    assert "calendar-decay-week" not in _codes(check_content(load_atlas(tmp_path)))


def test_weekly_not_treated_as_week_marker(tmp_path: Path) -> None:
    """`weekly` cadence is a different word; mustn't trigger."""
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
""",
        body="We run weekly syncs as part of the action plan.\n",
    )
    assert "calendar-decay-week" not in _codes(check_content(load_atlas(tmp_path)))


# --- calendar-decay-cycle --------------------------------------------------


def test_cycle_decay_fires_when_cycle_window_passed(tmp_path: Path) -> None:
    # Milestone defines the window for cycle 7.
    _write_node(
        tmp_path, "milestones", "cycle-7",
        """
id: milestone.cycle-7
name: Cycle 7
type: milestone
start_date: 2026-04-26
end_date: 2026-05-10
""",
    )
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: wip
code_refs: [notewell/]
""",
        body="Cycle 7 is currently active — we ship X this cycle.\n",
    )
    today = dt.date(2026, 5, 27)
    findings = check_content(load_atlas(tmp_path), today=today)
    codes = _codes(findings)
    assert "calendar-decay-cycle" in codes


def test_cycle_decay_silent_when_cycle_still_open(tmp_path: Path) -> None:
    _write_node(
        tmp_path, "milestones", "cycle-7",
        """
id: milestone.cycle-7
name: Cycle 7
type: milestone
start_date: 2026-04-26
end_date: 2026-05-10
""",
    )
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: wip
code_refs: [notewell/]
""",
        body="Cycle 7 is active.\n",
    )
    today = dt.date(2026, 5, 1)  # mid-cycle
    findings = check_content(load_atlas(tmp_path), today=today)
    assert "calendar-decay-cycle" not in _codes(findings)


def test_cycle_decay_silent_without_active_cues(tmp_path: Path) -> None:
    """A historical mention ('cycle 7 deferred late-interaction') is fine —
    only 'active'/'live'/'ongoing'/'current cycle'/'this cycle' cues fire."""
    _write_node(
        tmp_path, "milestones", "cycle-7",
        """
id: milestone.cycle-7
name: Cycle 7
type: milestone
start_date: 2026-04-26
end_date: 2026-05-10
""",
    )
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: planned
""",
        body="Cycle 7 deferred this work. We'll pick it up later.\n",
    )
    today = dt.date(2026, 5, 27)
    findings = check_content(load_atlas(tmp_path), today=today)
    assert "calendar-decay-cycle" not in _codes(findings)


def test_cycle_decay_silent_when_no_milestone_defines_window(tmp_path: Path) -> None:
    """Without a `milestone.cycle-N` node + start/end dates, we have no
    ground truth — so we don't guess."""
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: wip
code_refs: [notewell/]
""",
        body="Cycle 9 is currently active.\n",
    )
    findings = check_content(load_atlas(tmp_path))
    assert "calendar-decay-cycle" not in _codes(findings)


# --- general behavior ------------------------------------------------------


def test_no_findings_on_well_kept_node(tmp_path: Path) -> None:
    _write_node(
        tmp_path, "capabilities", "x",
        """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [ndcg@10]
""",
        body="## Why\nIt works.\n## Code\nLives in notewell/.\n",
    )
    findings = check_content(load_atlas(tmp_path))
    assert findings == []


def test_axis_label_is_content() -> None:
    """All findings produced by this axis must carry `axis=CONTENT`."""
    # Synthesize using a tmp dir inline (no fixture).
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_node(
            root, "capabilities", "x",
            """
id: capability.x.x
name: X
type: capability
status: shipped
code_refs: [notewell/]
metrics: [x]
""",
            body="TBD: this whole thing.\n",
        )
        for f in check_content(load_atlas(root)):
            assert f.axis == DriftAxis.CONTENT
