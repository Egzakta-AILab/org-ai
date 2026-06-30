"""User profiles — per-developer preferences, ownership, and identity bridges.

Public profiles live at `platform/profiles/<short-handle>.yaml` (git-tracked,
team-visible). The short handle is what appears in atlas `owners:` lists. The
Linear identity (`$LINEAR_HANDLE`, user_id, email) and git-author lines are
nested inside the YAML so consumers can bridge between the three identifier
spaces.

Private profiles live at `~/.egzakta/profile-local.yaml` (machine-local,
gitignored). Read-only from this package — written by the user manually or by
future hooks (PR4 onward).

This package is `users` (plural) to avoid name collision with the existing
`profiles.py` module which describes *tool* profiles (Claude/Cursor/droid
render deltas), not human profiles.
"""

from __future__ import annotations

from .loader import (
    UserProfile,
    current_handle,
    current_user,
    load_all_users,
    load_user,
    short_handle_from_linear,
)
from .private import PrivateProfile, load_private_profile

__all__ = [
    "PrivateProfile",
    "UserProfile",
    "current_handle",
    "current_user",
    "load_all_users",
    "load_private_profile",
    "load_user",
    "short_handle_from_linear",
]
