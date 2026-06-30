"""Parse repos.yaml — the canonical workspace manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .workspace import MANIFEST_NAME


@dataclass(frozen=True)
class Repo:
    name: str
    url: str | None = None
    status: str = "active"
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    description: str = ""
    # Skill names from platform/skills/index.yaml to project into this repo's
    # `<tool>/skills_project` dir (e.g. .claude/skills/<name>/). Workspace-level
    # skills installed via `--global` are listed under `skills.global` at the top.
    skills: tuple[str, ...] = ()

    @property
    def cloneable(self) -> bool:
        return bool(self.url)


@dataclass(frozen=True)
class WorkspaceSkills:
    """Workspace-level skills configuration from the top-level `skills:` block."""

    global_: tuple[str, ...] = ()  # installed by `org install --global`


@dataclass(frozen=True)
class Manifest:
    version: int
    repos: dict[str, Repo]
    skills: WorkspaceSkills = WorkspaceSkills()

    def select(self, names: list[str] | None = None, tags: list[str] | None = None) -> list[Repo]:
        """Return repos matching explicit names and/or any of the given tags. No filter => all."""
        repos = list(self.repos.values())
        if names:
            wanted = {n for n in names}
            missing = wanted - set(self.repos)
            if missing:
                raise KeyError(f"Unknown repo(s): {', '.join(sorted(missing))}")
            repos = [r for r in repos if r.name in wanted]
        if tags:
            tagset = set(tags)
            repos = [r for r in repos if tagset & set(r.tags)]
        return repos


def load_manifest(root: Path) -> Manifest:
    raw = yaml.safe_load((root / MANIFEST_NAME).read_text(encoding="utf-8")) or {}
    repos: dict[str, Repo] = {}
    for name, spec in (raw.get("repos") or {}).items():
        spec = spec or {}
        repos[name] = Repo(
            name=name,
            url=spec.get("url"),
            status=spec.get("status", "active"),
            tags=tuple(spec.get("tags", []) or []),
            depends_on=tuple(spec.get("depends_on", []) or []),
            provides=tuple(spec.get("provides", []) or []),
            tools=tuple(spec.get("tools", []) or []),
            description=spec.get("description", ""),
            skills=tuple(spec.get("skills", []) or []),
        )
    skills_block = raw.get("skills") or {}
    skills = WorkspaceSkills(global_=tuple(skills_block.get("global", []) or []))
    return Manifest(version=int(raw.get("version", 1)), repos=repos, skills=skills)
