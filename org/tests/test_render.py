"""Tests for the partial-include resolver in render.py.

These cover the new `expand_includes` token plus the full `render_agent` path so
the partial mechanism is exercised end-to-end. The reviewer sources in
`platform/agents/notewell/` rely on these tokens; a regression here surfaces fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from egzakta_org.profiles import Frontmatter, Profile
from egzakta_org.render import expand_includes, render_agent, render_tool_blocks


# --- expand_includes -------------------------------------------------------


def test_basic_substitution(tmp_path: Path) -> None:
    (tmp_path / "intro.md").write_text("Hello, world.\n")
    result = expand_includes("Greeting: {{INCLUDE:intro}}", tmp_path)
    assert result == "Greeting: Hello, world.\n"


def test_no_includes_passes_through(tmp_path: Path) -> None:
    text = "Plain markdown with no tokens.\n"
    assert expand_includes(text, tmp_path) == text


def test_multiple_includes(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("alpha")
    (tmp_path / "b.md").write_text("beta")
    result = expand_includes("{{INCLUDE:a}} and {{INCLUDE:b}}", tmp_path)
    assert result == "alpha and beta"


def test_recursive_include(tmp_path: Path) -> None:
    (tmp_path / "outer.md").write_text("outer-start {{INCLUDE:inner}} outer-end")
    (tmp_path / "inner.md").write_text("INNER")
    result = expand_includes("{{INCLUDE:outer}}", tmp_path)
    assert result == "outer-start INNER outer-end"


def test_missing_partial_errors_loudly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"partial not found.*does-not-exist"):
        expand_includes("ref: {{INCLUDE:does-not-exist}}", tmp_path)


def test_cycle_detection(tmp_path: Path) -> None:
    # a → b → a → b → … should error before the stack blows.
    (tmp_path / "a.md").write_text("{{INCLUDE:b}}")
    (tmp_path / "b.md").write_text("{{INCLUDE:a}}")
    with pytest.raises(ValueError, match=r"include depth exceeded"):
        expand_includes("{{INCLUDE:a}}", tmp_path)


def test_name_pattern_is_restrictive(tmp_path: Path) -> None:
    # `{{INCLUDE:Foo}}` with capitals should NOT match — keeps the include
    # surface narrow (kebab-case, lowercase) and avoids accidental matches in
    # documentation that mentions the syntax.
    (tmp_path / "Foo.md").write_text("nope")
    result = expand_includes("{{INCLUDE:Foo}}", tmp_path)
    assert result == "{{INCLUDE:Foo}}"


# --- render_tool_blocks ----------------------------------------------------


def test_tool_block_kept_for_listed_tool() -> None:
    text = "A\n<!-- tool:droid -->\nDROID ONLY\n<!-- /tool -->\nB\n"
    assert render_tool_blocks(text, "droid") == "A\nDROID ONLY\nB\n"


def test_tool_block_dropped_for_other_tool() -> None:
    text = "A\n<!-- tool:droid -->\nDROID ONLY\n<!-- /tool -->\nB\n"
    assert render_tool_blocks(text, "claude") == "A\nB\n"


def test_tool_block_multi_tool_list() -> None:
    text = "<!-- tool:claude, cursor -->\nSHARED\n<!-- /tool -->\n"
    assert render_tool_blocks(text, "cursor") == "SHARED\n"
    assert render_tool_blocks(text, "droid") == ""


def test_tool_block_unfenced_passthrough() -> None:
    text = "No fences here.\nJust prose.\n"
    assert render_tool_blocks(text, "droid") == text


def test_tool_block_multiple_blocks() -> None:
    text = (
        "<!-- tool:droid -->\nD\n<!-- /tool -->\n"
        "<!-- tool:claude -->\nC\n<!-- /tool -->\n"
    )
    assert render_tool_blocks(text, "droid") == "D\n"
    assert render_tool_blocks(text, "claude") == "C\n"


def test_tool_block_case_insensitive() -> None:
    text = "<!-- tool:Droid -->\nX\n<!-- /tool -->\n"
    assert render_tool_blocks(text, "DROID") == "X\n"


# --- render_agent integration ---------------------------------------------


@pytest.fixture
def claude_profile() -> Profile:
    """A minimal Claude profile suitable for rendering."""
    return Profile(
        tool="claude",
        agents_dir=".claude/agents",
        instructions_file="CLAUDE.md",
        repo_relative_paths=True,
        frontmatter=Frontmatter(emit=("name", "description"), description_style="plain"),
        tokens={"SUBAGENT_DISPATCH": "", "REVIEW_ENTRYPOINT": "/review-2axis"},
    )


def test_render_agent_with_partials(tmp_path: Path, claude_profile: Profile) -> None:
    """End-to-end: a source that uses {{INCLUDE:scaffold}} renders with the
    partial spliced in, then standard tokens ({{NAME}}, {{R}}) resolved."""
    partials = tmp_path / "_partials"
    partials.mkdir()
    (partials / "scaffold.md").write_text("Step from scaffold: {{NAME}} at {{R}}path.")

    source = (
        "---\n"
        "name: demo-reviewer\n"
        "description: Demo.\n"
        "---\n"
        "Body opens.\n\n"
        "{{INCLUDE:scaffold}}\n\n"
        "Body closes.\n"
    )

    rendered = render_agent(source, "platform/agents/notewell/demo.md", claude_profile, "notewell", partials)

    assert "Step from scaffold: demo-reviewer at path." in rendered
    assert "Body opens." in rendered
    assert "Body closes." in rendered
    # Marker prepended in frontmatter.
    assert "Generated by `org install`" in rendered


def test_render_agent_no_partials_dir(tmp_path: Path, claude_profile: Profile) -> None:
    """If `partials_root` is given but the directory doesn't exist (or is None),
    a source with no INCLUDE tokens still renders fine. Sources WITH include
    tokens would fail at substitute-time later — we accept that as deliberate."""
    source = "---\nname: x\ndescription: y\n---\nBody.\n"
    rendered = render_agent(source, "rel.md", claude_profile, "notewell", tmp_path / "missing")
    assert "Body." in rendered


def test_notewell_reviewers_render(claude_profile: Profile) -> None:
    """All notewell reviewer sources must render cleanly with the real partials.
    Catches drift between reviewer sources and the partials they reference."""
    repo_root = Path(__file__).resolve().parents[2]
    partials = repo_root / "platform" / "agents" / "_partials"
    agents_dir = repo_root / "platform" / "agents" / "notewell"
    if not agents_dir.is_dir():
        pytest.skip("no notewell agents dir found — platform not yet rendered")
    reviewers = sorted(agents_dir.glob("notewell-*.md"))
    if not reviewers:
        pytest.skip("no notewell reviewers found")

    for src in reviewers:
        rendered = render_agent(src.read_text(), str(src.relative_to(repo_root)), claude_profile, "notewell", partials)
        # The marker is always present.
        assert "Generated by `org install`" in rendered
        # No unresolved tokens should leak through.
        assert "{{INCLUDE:" not in rendered, f"unresolved include in {src.name}"
        assert "{{NAME}}" not in rendered, f"unresolved NAME in {src.name}"
        assert "{{R}}" not in rendered, f"unresolved R in {src.name}"
