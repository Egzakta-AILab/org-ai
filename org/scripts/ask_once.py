#!/usr/bin/env python
"""Stop-hook entrypoint for the closing-loop ask-once nudge.

Invoked by platform/hooks/_shared/scripts/ask-once.sh on every Stop event. Reads
the hook payload as JSON on stdin, computes the dev signals, and — at most once
per session, only when a real signal fires — emits a Stop-decision JSON that
tells the model to ask one AskUserQuestion. No signal → empty stdout, exit 0.

Stdout contract: empty (allow stop) OR exactly one Stop-decision JSON object.
Anything else would corrupt the hook protocol, so all diagnostics go to stderr.

Modes:
    (no args)        normal Stop-hook operation
    --dry-run        print the chosen signal + question to stderr; emit no block
    --skip <key>     record a 7-day skip for `key` and exit (the agent calls this
                     when the user picks "Skip", so the nudge stays quiet)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from egzakta_org.ask import (
    build_context,
    compute_signals,
    is_skipped,
    load_session_memo,
    record_skip,
    save_session_memo,
)
from egzakta_org.users import current_user
from egzakta_org.workspace import find_workspace_root


def _read_stdin_payload() -> dict:
    """Parse the hook's stdin JSON. Tolerates empty / malformed input (other tools
    may shape the payload differently) — returns {} rather than raising."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_project_dir(payload: dict) -> Path:
    candidate = os.environ.get("EGZAKTA_PROJECT_DIR") or payload.get("cwd")
    return Path(candidate) if candidate else Path.cwd()


def _additional_context(signal) -> str:
    return (
        "Before stopping, surface exactly one follow-up. Use the AskUserQuestion tool "
        "to ask the user this and then act on their choice:\n"
        f"  Question: {signal.question}\n"
        f"  Options: {' / '.join(signal.options)}\n"
        f"  {signal.action_hint}\n"
        "This nudge is already throttled (asked once per session; suppressed for 7 days), "
        "so ask only this one question — do not raise any other follow-ups."
    )


def _emit_block(signal) -> None:
    payload = {
        "decision": "block",
        "reason": signal.reason,
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": _additional_context(signal),
        },
    }
    sys.stdout.write(json.dumps(payload))


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    if "--skip" in argv:
        idx = argv.index("--skip")
        if idx + 1 < len(argv):
            record_skip(argv[idx + 1])
        return 0

    payload = _read_stdin_payload()
    session_id = str(payload.get("session_id") or "no-session")
    project_dir = _resolve_project_dir(payload)

    try:
        workspace_root = find_workspace_root(project_dir)
    except FileNotFoundError:
        return 0  # not an egzakta session — stay silent

    user = current_user(workspace_root)
    if user is not None and user.preferences.ask_hook == "off":
        return 0

    memo = load_session_memo(session_id)
    if memo.asked and not dry_run:
        return 0

    ctx = build_context(workspace_root, project_dir, user, memo.age_minutes, session_id)
    # Accumulate the session's touched footprint so signals see commits that left
    # the working tree on earlier turns, not just this turn's uncommitted changes.
    ctx.touched |= memo.touched
    memo.touched = set(ctx.touched)

    # Atlas-only sessions never nag: if there are changes and every one is under
    # atlas/, save the accumulated footprint and stay silent.
    if ctx.touched and all(p.startswith("atlas/") for p in ctx.touched):
        save_session_memo(memo)
        return 0

    signals = compute_signals(ctx)
    chosen = next((s for s in signals if not is_skipped(s.key)), None)

    if chosen is None:
        save_session_memo(memo)
        return 0

    if dry_run:
        print(
            f"[ask-once] would fire: {chosen.name} (key={chosen.key})\n"
            f"  Q: {chosen.question}\n"
            f"  options: {' / '.join(chosen.options)}",
            file=sys.stderr,
        )
        save_session_memo(memo)
        return 0

    _emit_block(chosen)
    memo.asked = True
    record_skip(chosen.key)
    save_session_memo(memo)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # a hook must never disrupt the session
        print(f"[ask-once] suppressed error: {exc}", file=sys.stderr)
        sys.exit(0)
