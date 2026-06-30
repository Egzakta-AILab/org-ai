"""Closing-loop ask-once hook: signal detection + per-session/skip memoization.

The Stop-hook entrypoint lives at `org/scripts/ask_once.py`; this package holds
the reusable pieces it composes:

* `signals` — the five dev signals + `compute_signals` (priority-ordered).
* `memo` — session memo (one question per session) + 7-day skip-cache.
"""

from __future__ import annotations

from .memo import (
    SessionMemo,
    is_skipped,
    load_session_memo,
    record_skip,
    save_session_memo,
)
from .signals import Signal, SignalContext, build_context, compute_signals

__all__ = [
    "SessionMemo",
    "Signal",
    "SignalContext",
    "build_context",
    "compute_signals",
    "is_skipped",
    "load_session_memo",
    "record_skip",
    "save_session_memo",
]
