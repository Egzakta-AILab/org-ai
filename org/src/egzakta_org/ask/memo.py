"""On-disk state for the closing-loop ask-once hook.

Two small JSON stores under a cache dir (``~/.cache/egzakta-org`` by default;
override with ``$EGZAKTA_CACHE_DIR`` — tests point it at a tmp dir):

* **session memo** — ``session-memo/<session_id>.json``. Created on the first
  Stop event of a session; tracks whether we've already asked (one question per
  session) and the union of touched paths seen across the session's Stop events.
* **skip-cache** — ``skip-cache.json``. ``{signal_key: expires_iso}``. Written
  optimistically when we ask; a signal is suppressed until expiry. Keys carry a
  discriminator (e.g. ``atlas-refresh:capability.x``) so a *different* underlying
  truth produces a different key and re-fires immediately.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


def cache_dir() -> Path:
    override = os.environ.get("EGZAKTA_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".cache" / "egzakta-org"


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# --- session memo ----------------------------------------------------------


@dataclass
class SessionMemo:
    session_id: str
    started_at: datetime = field(default_factory=_now)
    asked: bool = False
    touched: set[str] = field(default_factory=set)
    path: Path | None = None

    @property
    def age_minutes(self) -> float:
        return (_now() - self.started_at).total_seconds() / 60.0


def _session_memo_path(session_id: str) -> Path:
    # Never let a hostile/odd session_id escape the memo dir.
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "no-session"
    return cache_dir() / "session-memo" / f"{safe}.json"


def load_session_memo(session_id: str) -> SessionMemo:
    """Load the session memo, or return a fresh one (started now) if absent/corrupt."""
    path = _session_memo_path(session_id)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            started = datetime.fromisoformat(raw["started_at"])
            return SessionMemo(
                session_id=session_id,
                started_at=started,
                asked=bool(raw.get("asked", False)),
                touched=set(raw.get("touched", [])),
                path=path,
            )
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass
    return SessionMemo(session_id=session_id, path=path)


def save_session_memo(memo: SessionMemo) -> None:
    path = memo.path or _session_memo_path(memo.session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": memo.session_id,
        "started_at": _iso(memo.started_at),
        "asked": memo.asked,
        "touched": sorted(memo.touched),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# --- skip-cache ------------------------------------------------------------


def _skip_cache_path() -> Path:
    return cache_dir() / "skip-cache.json"


def _load_skip_cache() -> dict[str, str]:
    path = _skip_cache_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def is_skipped(signal_key: str) -> bool:
    """True if `signal_key` has an unexpired skip entry."""
    expires_raw = _load_skip_cache().get(signal_key)
    if not expires_raw:
        return False
    try:
        expires = datetime.fromisoformat(expires_raw)
    except ValueError:
        return False
    return expires > _now()


def record_skip(signal_key: str, *, days: int = 7) -> None:
    """Suppress `signal_key` for `days`. Prunes already-expired entries on write."""
    cache = _load_skip_cache()
    now = _now()
    pruned: dict[str, str] = {}
    for key, expires_raw in cache.items():
        try:
            if datetime.fromisoformat(expires_raw) > now:
                pruned[key] = expires_raw
        except ValueError:
            continue
    pruned[signal_key] = _iso(now + timedelta(days=days))
    path = _skip_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pruned, indent=2) + "\n", encoding="utf-8")
