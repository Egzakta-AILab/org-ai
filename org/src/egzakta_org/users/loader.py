"""Load + introspect public user profiles from `platform/profiles/<handle>.yaml`."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..workspace import find_workspace_root

PROFILES_DIR = "platform/profiles"


@dataclass(frozen=True)
class LinearIdentity:
    handle: str = ""          # $LINEAR_HANDLE — Linear username (e.g. jordan-lee)
    user_id: str = ""          # Linear viewer.id, stable across renames
    email: str = ""


@dataclass(frozen=True)
class Preferences:
    grill_depth: str = "medium"        # shallow | medium | deep
    review_style: str = "balanced"     # terse | balanced | explanatory
    handoff_detail: str = "medium"     # low | medium | high
    ask_hook: str = "on"               # on | off — the closing-loop Stop nudge


@dataclass(frozen=True)
class UserProfile:
    """Public per-user profile. One file per person under `platform/profiles/`."""

    handle: str                                              # short workspace handle — matches atlas `owners:`
    linear: LinearIdentity = field(default_factory=LinearIdentity)
    display_name: str = ""
    git_authors: tuple[str, ...] = ()
    role: str = ""                                           # junior | mid | senior | staff | pm
    areas: tuple[str, ...] = ()
    owns: tuple[str, ...] = ()                               # atlas node ids
    learning: tuple[str, ...] = ()                           # atlas node ids
    skills: tuple[str, ...] = ()                             # personal opt-in skills (names from platform/skills/index.yaml); unioned onto skills.global on `org install --global`
    preferences: Preferences = field(default_factory=Preferences)
    path: Path | None = None                                 # absolute path the profile loaded from
    raw: dict[str, Any] = field(default_factory=dict)        # the un-parsed YAML for forward-compat reads

    def field_at(self, dotted: str) -> str | None:
        """Resolve a dotted path against the raw YAML (e.g. `preferences.grill_depth`).

        Returns the value coerced to str, or None if the path doesn't resolve.
        Used by `org user show --field <path>` for skill-side shell-out reads.
        """
        cur: Any = self.raw
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        if cur is None:
            return None
        if isinstance(cur, (list, tuple)):
            return ", ".join(str(x) for x in cur)
        return str(cur)


def _on_off(value: Any, default: str = "on") -> str:
    """Normalize an on/off preference to the literal "on" or "off".

    YAML parses bare `off`/`no` as boolean False and `on`/`yes` as True, so a
    profile that writes `ask_hook: off` arrives here as `False` — coerce it back.
    Quoted strings (`"off"`) and explicit booleans both work.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return "on" if value else "off"
    s = str(value).strip().lower()
    if s in ("off", "false", "no", "0"):
        return "off"
    if s in ("on", "true", "yes", "1"):
        return "on"
    return default


def _profiles_dir(root: Path | None = None) -> Path:
    root = root or find_workspace_root()
    return root / PROFILES_DIR


def _parse(path: Path) -> UserProfile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: profile root must be a mapping, got {type(raw).__name__}")
    handle = str(raw.get("handle") or path.stem)

    linear_raw = raw.get("linear") or {}
    if isinstance(linear_raw, dict):
        linear = LinearIdentity(
            handle=str(linear_raw.get("handle") or ""),
            user_id=str(linear_raw.get("user_id") or ""),
            email=str(linear_raw.get("email") or ""),
        )
    else:
        linear = LinearIdentity()

    prefs_raw = raw.get("preferences") or {}
    if isinstance(prefs_raw, dict):
        prefs = Preferences(
            grill_depth=str(prefs_raw.get("grill_depth") or "medium"),
            review_style=str(prefs_raw.get("review_style") or "balanced"),
            handoff_detail=str(prefs_raw.get("handoff_detail") or "medium"),
            ask_hook=_on_off(prefs_raw.get("ask_hook")),
        )
    else:
        prefs = Preferences()

    return UserProfile(
        handle=handle,
        linear=linear,
        display_name=str(raw.get("display_name") or ""),
        git_authors=tuple(str(g) for g in (raw.get("git_authors") or [])),
        role=str(raw.get("role") or ""),
        areas=tuple(str(a) for a in (raw.get("areas") or [])),
        owns=tuple(str(o) for o in (raw.get("owns") or [])),
        learning=tuple(str(o) for o in (raw.get("learning") or [])),
        skills=tuple(str(s) for s in (raw.get("skills") or [])),
        preferences=prefs,
        path=path,
        raw=raw,
    )


def load_user(handle: str, root: Path | None = None) -> UserProfile | None:
    """Load `<profiles_dir>/<handle>.yaml`. Returns None if the file isn't there."""
    path = _profiles_dir(root) / f"{handle}.yaml"
    if not path.is_file():
        return None
    return _parse(path)


def load_all_users(root: Path | None = None) -> dict[str, UserProfile]:
    """Load every `*.yaml` under `platform/profiles/`. Bad files are skipped silently —
    `org user validate` is the place that surfaces schema errors."""
    out: dict[str, UserProfile] = {}
    pdir = _profiles_dir(root)
    if not pdir.is_dir():
        return out
    for path in sorted(pdir.glob("*.yaml")):
        try:
            profile = _parse(path)
        except (yaml.YAMLError, ValueError):
            continue
        out[profile.handle] = profile
    return out


def short_handle_from_linear(linear_handle: str, root: Path | None = None) -> str | None:
    """Reverse-lookup short handle from $LINEAR_HANDLE by scanning all profiles."""
    if not linear_handle:
        return None
    for short, profile in load_all_users(root).items():
        if profile.linear.handle == linear_handle:
            return short
    return None


def current_handle(root: Path | None = None) -> str | None:
    """Resolve the active dev's short handle from $LINEAR_HANDLE via the profile registry."""
    linear_handle = os.environ.get("LINEAR_HANDLE", "").strip()
    if not linear_handle:
        return None
    return short_handle_from_linear(linear_handle, root)


def current_user(root: Path | None = None) -> UserProfile | None:
    """Return the active dev's profile (resolved via $LINEAR_HANDLE), or None."""
    short = current_handle(root)
    if not short:
        return None
    return load_user(short, root)
