"""The five dev signals for the closing-loop nudge, in priority order.

Each detector takes a `SignalContext` and returns a `Signal` (fire) or `None`.
Detection is git-state-driven — robust and offline. The one place we'd want
Linear (has the dev already commented on the ticket?) is deferred to the agent
turn: the hook only detects that un-synced commits exist; when the user acts,
the agent uses the `linear` skill to check/post. No network in the Stop path.

Priority order (locked): ticket-comment > handoff > atlas-refresh > docs-update
> owner-notify. `compute_signals` returns every fired signal in this order; the
entrypoint picks the highest-priority one not currently in the skip-cache.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..atlas import AtlasIndex, load_atlas
from ..users import UserProfile

# `<handle>/<prefix>-NNN` — the workspace branch convention. Case-insensitive on the
# ticket-prefix segment; the handle is any non-slash run.
_BRANCH_RE = re.compile(r"^(?P<handle>[^/]+)/(?P<prefix>[a-z]+)-(?P<num>\d+)$", re.IGNORECASE)

# Bases we try (in order) to count "commits this session" as commits ahead of the
# integration branch. First one that resolves wins.
_BASE_CANDIDATES = ("origin/main", "main", "origin/master", "master")

_HANDOFF_MIN_FILES = 8
_HANDOFF_MIN_MINUTES = 60.0


@dataclass(frozen=True)
class Signal:
    key: str            # skip-cache key, carries a discriminator (e.g. "atlas-refresh:capability.x")
    name: str           # stable signal family (e.g. "atlas-refresh")
    header: str         # AskUserQuestion header chip (<=12 chars)
    question: str       # the question text shown to the user
    options: tuple[str, ...]
    reason: str         # short user-facing line for the Stop `reason`
    action_hint: str    # tells the model how to act on each option (goes in additionalContext)


# --- git helpers -----------------------------------------------------------


def _git(args: list[str], cwd: Path, *, strip: bool = True) -> str | None:
    """Run git, return stdout (stripped by default) or None on failure.

    `strip=False` is required for `git status --porcelain`: porcelain lines begin
    with a 2-char status that may start with a space (e.g. ` M path`), so stripping
    the whole output would eat the leading space of the first line and shift its path.
    """
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() if strip else out.stdout


def repo_toplevel(start: Path) -> Path | None:
    top = _git(["rev-parse", "--show-toplevel"], start)
    return Path(top) if top else None


def current_branch(top: Path) -> str | None:
    branch = _git(["branch", "--show-current"], top)
    return branch or None


def commits_ahead(top: Path) -> int:
    for base in _BASE_CANDIDATES:
        # Does the base ref exist?
        if _git(["rev-parse", "--verify", "--quiet", base], top) is None:
            continue
        count = _git(["rev-list", "--count", f"{base}..HEAD"], top)
        if count is not None and count.isdigit():
            return int(count)
    return 0


def _porcelain(top: Path) -> list[tuple[str, str]]:
    """Return [(status, path), …] from `git status --porcelain` (repo-relative paths)."""
    # --untracked-files=all lists new files individually instead of collapsing a
    # fresh untracked directory to a single `?? dir/` entry — needed so a new file
    # inside a new subdir still matches atlas code_refs. Respects .gitignore.
    text = _git(["status", "--porcelain", "--untracked-files=all"], top, strip=False)
    if not text:
        return []
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if len(line) < 4:
            continue
        status, rest = line[:2], line[3:]
        if " -> " in rest:  # rename/copy: take the destination
            rest = rest.split(" -> ", 1)[1]
        rows.append((status, rest.strip().strip('"')))
    return rows


def _repo_prefix(top: Path, workspace_root: Path) -> str | None:
    """Posix prefix mapping repo-relative paths to workspace-relative ones.

    Returns "" when the repo IS the workspace root (meta-repo edits), "notewell/"
    when working inside a cloned repo, or None if the repo is outside the
    workspace entirely.
    """
    try:
        rel = top.resolve().relative_to(workspace_root.resolve())
    except ValueError:
        return None
    s = rel.as_posix()
    return "" if s == "." else f"{s}/"


# --- context ---------------------------------------------------------------


@dataclass
class SignalContext:
    workspace_root: Path
    project_dir: Path
    user: UserProfile | None
    age_minutes: float
    session_id: str = "no-session"
    # Populated by `build_context`:
    branch: str | None = None
    ticket: str | None = None
    commits_ahead: int = 0
    touched: set[str] = field(default_factory=set)  # workspace-relative posix paths
    new_paths: set[str] = field(default_factory=set)  # untracked/added, workspace-relative
    _atlas: AtlasIndex | None = None
    _atlas_loaded: bool = False

    @property
    def atlas(self) -> AtlasIndex | None:
        if not self._atlas_loaded:
            self._atlas_loaded = True
            try:
                # load_atlas wants the atlas DIR, not the workspace root.
                self._atlas = load_atlas(self.workspace_root / "atlas")
            except Exception:  # atlas parse failure must never break the hook
                self._atlas = None
        return self._atlas


def build_context(
    workspace_root: Path,
    project_dir: Path,
    user: UserProfile | None,
    age_minutes: float,
    session_id: str = "no-session",
) -> SignalContext:
    ctx = SignalContext(
        workspace_root=workspace_root,
        project_dir=project_dir,
        user=user,
        age_minutes=age_minutes,
        session_id=session_id,
    )
    top = repo_toplevel(project_dir)
    if top is None:
        return ctx
    prefix = _repo_prefix(top, workspace_root)
    if prefix is None:
        return ctx

    ctx.branch = current_branch(top)
    if ctx.branch:
        m = _BRANCH_RE.match(ctx.branch)
        if m:
            ctx.ticket = f"{m.group('prefix').upper()}-{m.group('num')}"
    ctx.commits_ahead = commits_ahead(top)

    for status, path in _porcelain(top):
        ws_path = f"{prefix}{path}"
        ctx.touched.add(ws_path)
        # `??` untracked or `A ` added → a new file.
        if status.strip() == "??" or status[0] == "A":
            ctx.new_paths.add(ws_path)
    return ctx


# --- signal detectors ------------------------------------------------------


def _ticket_comment(ctx: SignalContext) -> Signal | None:
    if not ctx.ticket or ctx.commits_ahead <= 0:
        return None
    n = ctx.commits_ahead
    plural = "s" if n != 1 else ""
    return Signal(
        key=f"ticket-comment:{ctx.ticket}",
        name="ticket-comment",
        header="Ticket update",
        question=f"You have {n} commit{plural} on {ctx.ticket} with no Linear update. Comment now?",
        options=("Draft from commits", "Write my own", "Skip"),
        reason=f"{n} commit{plural} on {ctx.ticket} with no Linear update.",
        action_hint=(
            f"This is {ctx.ticket}. 'Draft from commits' → read `git log` for the commits ahead "
            "of the base branch, use the `linear` skill to check the ticket for an existing recent "
            "comment, then draft a concise progress comment and show it for approval before posting. "
            "'Write my own' → ask the user what to record. 'Skip' → do nothing."
        ),
    )


def _handoff(ctx: SignalContext) -> Signal | None:
    long_enough = ctx.age_minutes >= _HANDOFF_MIN_MINUTES
    many_files = len(ctx.touched) >= _HANDOFF_MIN_FILES
    if not (long_enough or many_files):
        return None
    # Best-effort: if a handoff doc already exists in the active worktree, skip.
    handoffs = ctx.project_dir / ".handoffs"
    if handoffs.is_dir() and any(handoffs.glob("*.md")):
        return None
    why = []
    if long_enough:
        why.append(f"{int(ctx.age_minutes)}min")
    if many_files:
        why.append(f"{len(ctx.touched)} files touched")
    detail = " and ".join(why)
    return Signal(
        # Keyed by session: handoff is inherently per-session, so the optimistic
        # 7-day skip written at ask-time only ever matches THIS session (within-
        # session re-asks are already blocked by the session memo's `asked` flag).
        # A new session gets a fresh key and can re-evaluate.
        key=f"handoff:{ctx.session_id}",
        name="handoff",
        header="Long session",
        question=f"{detail}. Write a /handoff doc for the next session?",
        options=("Yes", "Skip"),
        reason=f"{detail}; no handoff written yet.",
        action_hint=(
            "'Yes' → run the /handoff skill to write a worktree-local handoff document. "
            "'Skip' → do nothing."
        ),
    )


def _node_for_path(ctx: SignalContext, want_capability: bool):
    """Return (node, matched_path) for the first touched path covered by a node's
    code_refs. If `want_capability`, only consider `capability.*` nodes."""
    atlas = ctx.atlas
    if atlas is None:
        return None
    for node in atlas.nodes:
        if want_capability and not node.id.startswith("capability."):
            continue
        for ref in node.code_refs:
            for path in ctx.touched:
                if path == ref or path.startswith(ref.rstrip("/") + "/"):
                    return node, path
    return None


def _atlas_refresh(ctx: SignalContext) -> Signal | None:
    match = _node_for_path(ctx, want_capability=False)
    if match is None:
        return None
    node, path = match
    return Signal(
        key=f"atlas-refresh:{node.id}",
        name="atlas-refresh",
        header="Atlas drift",
        question=f"You touched `{path}` (in `{node.id}` code_refs). Refresh the node?",
        options=("Refresh now", "Draft note", "Skip"),
        reason=f"`{path}` is a code_ref of atlas node `{node.id}`.",
        action_hint=(
            f"The atlas node `{node.id}` ({node.rel_path}) references the file you changed. "
            "'Refresh now' → re-read the code and update the node body/frontmatter to match, "
            "show the diff for approval, don't auto-commit. 'Draft note' → jot a one-line "
            "'needs refresh' note on the node. 'Skip' → do nothing."
        ),
    )


def _docs_update(ctx: SignalContext) -> Signal | None:
    new_assets = sorted(
        p for p in ctx.new_paths
        if p.startswith("platform/agents/") or p.startswith("platform/skills/")
    )
    if not new_assets:
        return None
    n = len(new_assets)
    plural = "s" if n != 1 else ""
    return Signal(
        key="docs-update",
        name="docs-update",
        header="New assets",
        question=f"{n} new platform asset{plural}. Update docs/skills.md?",
        options=("Yes", "Skip"),
        reason=f"{n} new platform asset{plural} not yet documented.",
        action_hint=(
            "New agent/skill sources were added. 'Yes' → update docs/skills.md (and "
            "docs/agents if relevant) to register them, show the diff for approval. "
            "'Skip' → do nothing."
        ),
    )


def _owner_notify(ctx: SignalContext) -> Signal | None:
    match = _node_for_path(ctx, want_capability=True)
    if match is None:
        return None
    node, path = match
    owns = set(ctx.user.owns) if ctx.user else set()
    if node.id in owns:
        return None
    owners = node.frontmatter.get("owners") or []
    owner_str = ", ".join(f"@{o}" for o in owners) if owners else "its owner"
    return Signal(
        key=f"owner-notify:{node.id}",
        name="owner-notify",
        header="Cross-touch",
        question=f"You touched `{node.id}` (owned by {owner_str}), not yours. Notify them?",
        options=("@mention in Linear", "Skip"),
        reason=f"`{path}` belongs to `{node.id}`, owned by {owner_str}.",
        action_hint=(
            f"`{node.id}` is owned by {owner_str}, not the current dev. "
            "'@mention in Linear' → use the `linear` skill to leave a heads-up comment "
            "@mentioning the owner on the relevant ticket. 'Skip' → do nothing."
        ),
    )


ORDERED_DETECTORS = (
    _ticket_comment,
    _handoff,
    _atlas_refresh,
    _docs_update,
    _owner_notify,
)


def compute_signals(ctx: SignalContext) -> list[Signal]:
    """Every fired signal, in priority order."""
    fired: list[Signal] = []
    for detector in ORDERED_DETECTORS:
        sig = detector(ctx)
        if sig is not None:
            fired.append(sig)
    return fired
