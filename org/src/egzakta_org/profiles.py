"""Load tool profiles from platform/tools/*.yaml.

A profile describes the per-tool deltas the renderer applies: where files land, how
frontmatter is shaped, and the values substituted for body tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Frontmatter:
    emit: tuple[str, ...]
    description_style: str = "plain"  # plain | folded
    description_suffix: str = ""  # may contain {name}


@dataclass(frozen=True)
class Profile:
    tool: str
    agents_dir: str
    instructions_file: str
    repo_relative_paths: bool
    frontmatter: Frontmatter
    tokens: dict[str, str] = field(default_factory=dict)
    # Optional per-component output dirs. None means "this tool has no such surface" —
    # the renderer skips that component for this tool (e.g. cursor has no commands;
    # droid has no rules).
    commands_dir: str | None = None
    rules_dir: str | None = None
    # Skills install into one of two scopes; both are tool-relative. None on either
    # means the tool has no skills concept (no current tool — all three of claude,
    # cursor, droid ship skills today — but the option stays so a new tool can opt out).
    skills_global_dir: str | None = None
    skills_project_dir: str | None = None
    # User-global homes for shared agents + commands (e.g. ~/.claude/agents,
    # ~/.claude/commands). Populated by `org install --global` from sources at
    # platform/{agents,commands}/_shared/ so workspace-shared assets resolve from
    # any cwd. None means this tool has no user-global surface for that component.
    agents_global_dir: str | None = None
    commands_global_dir: str | None = None
    # When true, the commands surface only emits explicitly-declared aliases (not the
    # 1:1 agent → wrapper pointers). Factory sets this because droids are invoked
    # directly as /<droid-name>; a same-named wrapper would shadow the droid for
    # no benefit. Claude leaves it false: it needs the per-agent wrapper for the
    # slash command to exist at all.
    commands_only_aliases: bool = False
    # Hooks surface. Scripts land at `<hooks_dir>/_org/<name>.sh`; event bindings are
    # merged into `<settings_file>` under a managed namespace. None on either means
    # the tool has no hooks concept (Cursor today; droid until they ship a hooks API).
    hooks_dir: str | None = None
    settings_file: str | None = None
    # User-global homes for workspace-shared hooks (resolved from any cwd). Sourced
    # from platform/hooks/_shared/ on `org install --global`. Scripts land at
    # `<hooks_global_dir>/_org/<name>.sh` and bindings merge into <settings_global_file>.
    # The rendered command path is absolute (not $PROJECT_DIR-relative) because the
    # script lives under $HOME, not the active project. None means no global surface.
    hooks_global_dir: str | None = None
    settings_global_file: str | None = None

    def repo_prefix(self, repo_name: str) -> str:
        return "" if self.repo_relative_paths else f"{repo_name}/"


def load_profile(path: Path) -> Profile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    paths = raw.get("paths", {}) or {}
    fm = raw.get("frontmatter", {}) or {}
    return Profile(
        tool=raw["tool"],
        agents_dir=paths.get("agents", ".claude/agents"),
        instructions_file=paths.get("instructions", "AGENTS.md"),
        repo_relative_paths=bool(raw.get("repo_relative_paths", True)),
        frontmatter=Frontmatter(
            emit=tuple(fm.get("emit", ["name", "description"])),
            description_style=fm.get("description_style", "plain"),
            description_suffix=fm.get("description_suffix", ""),
        ),
        tokens=dict(raw.get("tokens", {}) or {}),
        commands_dir=paths.get("commands"),
        rules_dir=paths.get("rules"),
        skills_global_dir=paths.get("skills_global"),
        skills_project_dir=paths.get("skills_project"),
        agents_global_dir=paths.get("agents_global"),
        commands_global_dir=paths.get("commands_global"),
        commands_only_aliases=bool(raw.get("commands_only_aliases", False)),
        hooks_dir=paths.get("hooks"),
        settings_file=paths.get("settings"),
        hooks_global_dir=paths.get("hooks_global"),
        settings_global_file=paths.get("settings_global"),
    )


def load_profiles(platform_dir: Path) -> dict[str, Profile]:
    tools_dir = platform_dir / "tools"
    profiles: dict[str, Profile] = {}
    for path in sorted(tools_dir.glob("*.yaml")):
        profile = load_profile(path)
        profiles[profile.tool] = profile
    return profiles
