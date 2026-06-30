"""Read-only loader for `~/.egzakta/profile-local.yaml`.

Machine-local, gitignored. Used by future PR4 ask-once hook to read grill
history + skill state for signal computation. Never written by agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PRIVATE_PROFILE_PATH = Path.home() / ".egzakta" / "profile-local.yaml"


@dataclass(frozen=True)
class GrillHistoryEntry:
    timestamp: str = ""
    ticket: str = ""
    node: str = ""
    decisions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrivateProfile:
    handle: str = ""
    grill_history: tuple[GrillHistoryEntry, ...] = ()
    skill_state: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    path: Path = field(default_factory=lambda: PRIVATE_PROFILE_PATH)


def load_private_profile(path: Path | None = None) -> PrivateProfile | None:
    """Return the private profile, or None if the file doesn't exist."""
    path = path or PRIVATE_PROFILE_PATH
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return None
    history_raw = raw.get("grill_history") or []
    history: list[GrillHistoryEntry] = []
    if isinstance(history_raw, list):
        for entry in history_raw:
            if not isinstance(entry, dict):
                continue
            history.append(
                GrillHistoryEntry(
                    timestamp=str(entry.get("timestamp") or ""),
                    ticket=str(entry.get("ticket") or ""),
                    node=str(entry.get("node") or ""),
                    decisions=tuple(str(d) for d in (entry.get("decisions") or [])),
                )
            )
    skill_state = raw.get("skill_state") or {}
    if not isinstance(skill_state, dict):
        skill_state = {}
    return PrivateProfile(
        handle=str(raw.get("handle") or ""),
        grill_history=tuple(history),
        skill_state=skill_state,
        notes=str(raw.get("notes") or ""),
        path=path,
    )
