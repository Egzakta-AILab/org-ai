"""Tests for the hooks engine: `_shared/` loading, global vs per-repo command
paths, settings merge, and the user-global hook install actions."""

from __future__ import annotations

from pathlib import Path

from egzakta_org import hooks as hooks_mod
from egzakta_org.commands.install import _global_hook_actions
from egzakta_org.profiles import Frontmatter, Profile


# --- helpers --------------------------------------------------------------


def _write_shared_hook(plat: Path) -> None:
    d = plat / "hooks" / "_shared"
    (d / "scripts").mkdir(parents=True)
    (d / "hooks.yaml").write_text("hooks:\n  - event: Stop\n    script: ask-once.sh\n")
    (d / "scripts" / "ask-once.sh").write_text("#!/usr/bin/env bash\nexit 0\n")


def _claude_profile(tmp_path: Path) -> Profile:
    return Profile(
        tool="claude",
        agents_dir=".claude/agents",
        instructions_file="CLAUDE.md",
        repo_relative_paths=True,
        frontmatter=Frontmatter(emit=("name", "description")),
        hooks_dir=".claude/hooks",
        settings_file=".claude/settings.json",
        hooks_global_dir=str(tmp_path / "globalhome" / ".claude" / "hooks"),
        settings_global_file=str(tmp_path / "globalhome" / ".claude" / "settings.json"),
    )


# --- load_source(_shared) -------------------------------------------------


def test_load_source_reads_shared(tmp_path: Path) -> None:
    plat = tmp_path / "platform"
    _write_shared_hook(plat)
    source = hooks_mod.load_source(plat, "_shared", tmp_path)
    assert not source.is_empty
    assert len(source.bindings) == 1
    b = source.bindings[0]
    assert b.event == "Stop"
    assert b.script == "ask-once.sh"
    assert b.tools == ("claude", "cursor", "droid")
    assert [p.name for p in source.scripts] == ["ask-once.sh"]


def test_load_source_missing_dir_is_empty(tmp_path: Path) -> None:
    plat = tmp_path / "platform"
    (plat / "hooks").mkdir(parents=True)
    assert hooks_mod.load_source(plat, "_shared", tmp_path).is_empty


# --- command-path: global (absolute) vs per-repo ($PROJECT_DIR) -----------


def _stop_binding() -> hooks_mod.HookBinding:
    return hooks_mod.HookBinding(
        event="Stop", matcher="", script="ask-once.sh",
        tools=("claude", "cursor", "droid"), source_rel="platform/hooks/_shared/hooks.yaml",
    )


def test_managed_block_per_repo_uses_project_dir_var() -> None:
    block = hooks_mod.build_managed_block([_stop_binding()], "claude", ".claude/hooks")
    cmd = block["Stop"][0]["hooks"][0]["command"]
    assert cmd == "$CLAUDE_PROJECT_DIR/.claude/hooks/_org/ask-once.sh"


def test_managed_block_global_uses_absolute_path() -> None:
    block = hooks_mod.build_managed_block(
        [_stop_binding()], "claude", ".claude/hooks", global_root="/home/u/.claude/hooks"
    )
    cmd = block["Stop"][0]["hooks"][0]["command"]
    assert cmd == "/home/u/.claude/hooks/_org/ask-once.sh"


def test_managed_block_global_cursor_flat_absolute() -> None:
    block = hooks_mod.build_managed_block(
        [_stop_binding()], "cursor", ".cursor/hooks", global_root="/home/u/.cursor/hooks"
    )
    # Cursor uses camelCase event + flat schema.
    entry = block["stop"][0]
    assert entry["command"] == "/home/u/.cursor/hooks/_org/ask-once.sh"
    assert entry["__org_managed__"] is True


# --- merge preserves user-authored hooks ----------------------------------


def test_merge_preserves_user_hooks() -> None:
    user_settings = {
        "hooks": {
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "my-own.sh"}]}]
        }
    }
    managed = hooks_mod.build_managed_block(
        [_stop_binding()], "claude", ".claude/hooks", global_root="/g/.claude/hooks"
    )
    merged = hooks_mod.merge_into_settings(user_settings, managed, "claude")
    commands = [h["command"] for block in merged["hooks"]["Stop"] for h in block["hooks"]]
    assert "my-own.sh" in commands
    assert "/g/.claude/hooks/_org/ask-once.sh" in commands


def test_merge_is_idempotent() -> None:
    managed = hooks_mod.build_managed_block(
        [_stop_binding()], "claude", ".claude/hooks", global_root="/g/.claude/hooks"
    )
    once = hooks_mod.merge_into_settings({}, managed, "claude")
    twice = hooks_mod.merge_into_settings(once, managed, "claude")
    assert once == twice


# --- _global_hook_actions (install layer) ---------------------------------


def test_global_hook_actions_emits_script_and_settings(tmp_path: Path) -> None:
    plat = tmp_path / "platform"
    _write_shared_hook(plat)
    profile = _claude_profile(tmp_path)
    actions = _global_hook_actions(tmp_path, plat, profile, "claude")

    by_dest = {a.dest.name: a for a in actions}
    assert "ask-once.sh" in by_dest
    assert "settings.json" in by_dest

    script_action = by_dest["ask-once.sh"]
    assert script_action.executable is True
    assert script_action.dest.parent.name == hooks_mod.ENGINE_NAMESPACE  # …/_org/

    settings_action = by_dest["settings.json"]
    # The rendered settings carry the absolute command path under the global home.
    expected_cmd = str(tmp_path / "globalhome" / ".claude" / "hooks") + "/_org/ask-once.sh"
    assert expected_cmd in settings_action.content


def test_global_hook_actions_empty_without_global_dirs(tmp_path: Path) -> None:
    plat = tmp_path / "platform"
    _write_shared_hook(plat)
    profile = Profile(
        tool="claude",
        agents_dir=".claude/agents",
        instructions_file="CLAUDE.md",
        repo_relative_paths=True,
        frontmatter=Frontmatter(emit=("name", "description")),
        hooks_dir=".claude/hooks",
        settings_file=".claude/settings.json",
        # no hooks_global_dir / settings_global_file
    )
    assert _global_hook_actions(tmp_path, plat, profile, "claude") == []
