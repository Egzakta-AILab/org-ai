"""Tests for `egzakta_org.ask` — memo/skip-cache, git signals, and the entrypoint."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from egzakta_org.ask import memo as memo_mod
from egzakta_org.ask import signals as sig
from egzakta_org.users import UserProfile


# --- helpers --------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    _run_git(["init", "-b", "main"], path)
    _run_git(["config", "user.email", "t@example.com"], path)
    _run_git(["config", "user.name", "Test"], path)
    (path / "README.md").write_text("seed\n")
    _run_git(["add", "."], path)
    _run_git(["commit", "-m", "init"], path)


def _write_repos_yaml(workspace: Path) -> None:
    (workspace / "repos.yaml").write_text(
        "version: 1\nrepos:\n  notewell:\n    url: x\n    status: active\n",
        encoding="utf-8",
    )


def _write_node(workspace: Path, stem: str, body: str) -> None:
    d = workspace / "atlas" / "capabilities"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.md").write_text(f"---\n{body}\n---\n", encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_repos_yaml(tmp_path)
    _init_repo(tmp_path)
    monkeypatch.setenv("EGZAKTA_CACHE_DIR", str(tmp_path / ".cache"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- memo + skip-cache ----------------------------------------------------


def test_session_memo_round_trip(workspace: Path) -> None:
    m = memo_mod.load_session_memo("sess-1")
    assert m.asked is False
    m.asked = True
    m.touched = {"a.py", "b.py"}
    memo_mod.save_session_memo(m)

    again = memo_mod.load_session_memo("sess-1")
    assert again.asked is True
    assert again.touched == {"a.py", "b.py"}
    assert again.started_at == m.started_at


def test_session_memo_fresh_when_absent(workspace: Path) -> None:
    m = memo_mod.load_session_memo("never-seen")
    assert m.asked is False
    assert m.touched == set()


def test_skip_cache_records_and_expires(workspace: Path) -> None:
    assert memo_mod.is_skipped("atlas-refresh:capability.x") is False
    memo_mod.record_skip("atlas-refresh:capability.x", days=7)
    assert memo_mod.is_skipped("atlas-refresh:capability.x") is True
    # A different discriminator is independent.
    assert memo_mod.is_skipped("atlas-refresh:capability.y") is False


def test_skip_cache_prunes_expired(workspace: Path) -> None:
    path = workspace / ".cache" / "skip-cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
    path.write_text(json.dumps({"handoff:old": past}))
    assert memo_mod.is_skipped("handoff:old") is False
    # Writing a new entry prunes the expired one.
    memo_mod.record_skip("ticket-comment:NW-1")
    data = json.loads(path.read_text())
    assert "handoff:old" not in data
    assert "ticket-comment:NW-1" in data


# --- build_context --------------------------------------------------------


def test_build_context_detects_branch_and_ticket(workspace: Path) -> None:
    _run_git(["checkout", "-b", "jordan-lee/nw-459"], workspace)
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert ctx.branch == "jordan-lee/nw-459"
    assert ctx.ticket == "NW-459"


def test_build_context_non_ticket_branch(workspace: Path) -> None:
    _run_git(["checkout", "-b", "scratch/experiment"], workspace)
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert ctx.ticket is None


def test_build_context_touched_paths_full(workspace: Path) -> None:
    # A tracked-modified file whose porcelain line begins with a space (` M path`)
    # must keep its full path — regression for the strip()-eats-leading-space bug.
    (workspace / "README.md").write_text("changed\n")
    (workspace / "new.py").write_text("x\n")  # untracked
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert "README.md" in ctx.touched
    assert "new.py" in ctx.touched
    assert "new.py" in ctx.new_paths
    assert "README.md" not in ctx.new_paths  # modified, not new


# --- individual signals ---------------------------------------------------


def test_ticket_comment_fires_with_commits(workspace: Path) -> None:
    _run_git(["checkout", "-b", "jordan-lee/nw-459"], workspace)
    (workspace / "feature.py").write_text("work\n")
    _run_git(["add", "."], workspace)
    _run_git(["commit", "-m", "feature work"], workspace)
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    s = sig._ticket_comment(ctx)
    assert s is not None
    assert s.name == "ticket-comment"
    assert s.key == "ticket-comment:NW-459"
    assert "NW-459" in s.question


def test_ticket_comment_silent_without_commits(workspace: Path) -> None:
    _run_git(["checkout", "-b", "jordan-lee/nw-459"], workspace)
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert sig._ticket_comment(ctx) is None  # no commits ahead of main


def test_ticket_comment_silent_off_ticket_branch(workspace: Path) -> None:
    (workspace / "feature.py").write_text("work\n")
    _run_git(["add", "."], workspace)
    _run_git(["commit", "-m", "x"], workspace)
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert sig._ticket_comment(ctx) is None  # on `main`, not a ticket branch


def test_handoff_fires_on_many_files(workspace: Path) -> None:
    for i in range(8):
        (workspace / f"f{i}.py").write_text("x\n")
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    s = sig._handoff(ctx)
    assert s is not None and s.name == "handoff"
    assert s.key == f"handoff:{ctx.session_id}"


def test_handoff_fires_on_long_session(workspace: Path) -> None:
    (workspace / "one.py").write_text("x\n")
    ctx = sig.build_context(workspace, workspace, None, 75.0)
    assert sig._handoff(ctx) is not None


def test_handoff_silent_when_short_and_few_files(workspace: Path) -> None:
    (workspace / "one.py").write_text("x\n")
    ctx = sig.build_context(workspace, workspace, None, 5.0)
    assert sig._handoff(ctx) is None


def test_handoff_silent_when_handoff_doc_exists(workspace: Path) -> None:
    for i in range(8):
        (workspace / f"f{i}.py").write_text("x\n")
    handoffs = workspace / ".handoffs"
    handoffs.mkdir()
    (handoffs / "nw-459-2026.md").write_text("# handoff\n")
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert sig._handoff(ctx) is None


def test_atlas_refresh_fires_on_code_ref_touch(workspace: Path) -> None:
    _write_node(
        workspace,
        "search",
        "id: capability.search\nname: Search\ntype: capability\nstatus: shipped\n"
        "code_refs: [src/core/search.py]\nmetrics: [recall]",
    )
    (workspace / "src" / "core").mkdir(parents=True)
    (workspace / "src" / "core" / "search.py").write_text("x\n")
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    s = sig._atlas_refresh(ctx)
    assert s is not None
    assert s.key == "atlas-refresh:capability.search"


def test_atlas_refresh_silent_without_match(workspace: Path) -> None:
    _write_node(
        workspace,
        "search",
        "id: capability.search\nname: Search\ntype: capability\nstatus: shipped\n"
        "code_refs: [src/core/search.py]\nmetrics: [recall]",
    )
    (workspace / "unrelated.py").write_text("x\n")
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert sig._atlas_refresh(ctx) is None


def test_docs_update_fires_on_new_platform_asset(workspace: Path) -> None:
    (workspace / "platform" / "skills").mkdir(parents=True)
    (workspace / "platform" / "skills" / "new-skill.md").write_text("x\n")
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    s = sig._docs_update(ctx)
    assert s is not None and s.name == "docs-update"


def test_docs_update_silent_for_modified_only(workspace: Path) -> None:
    # An existing, tracked platform asset that's merely modified is not "new".
    skills = workspace / "platform" / "skills"
    skills.mkdir(parents=True)
    asset = skills / "existing.md"
    asset.write_text("v1\n")
    _run_git(["add", "."], workspace)
    _run_git(["commit", "-m", "add asset"], workspace)
    asset.write_text("v2\n")
    ctx = sig.build_context(workspace, workspace, None, 0.0)
    assert sig._docs_update(ctx) is None


def test_owner_notify_fires_for_unowned_capability(workspace: Path) -> None:
    _write_node(
        workspace,
        "ranking",
        "id: capability.ranking\nname: Ranking\ntype: capability\nstatus: shipped\n"
        "owners: [alex]\ncode_refs: [src/rank.py]\nmetrics: [ndcg]",
    )
    (workspace / "src").mkdir()
    (workspace / "src" / "rank.py").write_text("x\n")
    user = UserProfile(handle="jordan", owns=("capability.search",))
    ctx = sig.build_context(workspace, workspace, user, 0.0)
    s = sig._owner_notify(ctx)
    assert s is not None
    assert s.key == "owner-notify:capability.ranking"


def test_owner_notify_silent_when_owned(workspace: Path) -> None:
    _write_node(
        workspace,
        "ranking",
        "id: capability.ranking\nname: Ranking\ntype: capability\nstatus: shipped\n"
        "owners: [jordan]\ncode_refs: [src/rank.py]\nmetrics: [ndcg]",
    )
    (workspace / "src").mkdir()
    (workspace / "src" / "rank.py").write_text("x\n")
    user = UserProfile(handle="jordan", owns=("capability.ranking",))
    ctx = sig.build_context(workspace, workspace, user, 0.0)
    assert sig._owner_notify(ctx) is None


# --- priority ordering ----------------------------------------------------


def test_compute_signals_priority_ticket_beats_handoff(workspace: Path) -> None:
    _run_git(["checkout", "-b", "jordan-lee/nw-459"], workspace)
    for i in range(8):
        (workspace / f"f{i}.py").write_text("x\n")
    _run_git(["add", "."], workspace)
    _run_git(["commit", "-m", "lots"], workspace)
    ctx = sig.build_context(workspace, workspace, None, 90.0)
    fired = sig.compute_signals(ctx)
    names = [s.name for s in fired]
    assert names[0] == "ticket-comment"
    assert "handoff" in names
    assert names.index("ticket-comment") < names.index("handoff")


# --- entrypoint -----------------------------------------------------------


def _load_entrypoint():
    here = Path(__file__).resolve().parents[1]  # org/
    spec = importlib.util.spec_from_file_location("ask_once", here / "scripts" / "ask_once.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _feed_stdin(monkeypatch: pytest.MonkeyPatch, session_id: str, cwd: Path) -> None:
    payload = json.dumps({"session_id": session_id, "cwd": str(cwd)})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))


def test_entrypoint_emits_block_then_throttles(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_entrypoint()
    for i in range(8):
        (workspace / f"f{i}.py").write_text("x\n")

    _feed_stdin(monkeypatch, "ep-1", workspace)
    assert mod.main([]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"

    # Second Stop, same session → throttled (empty stdout).
    _feed_stdin(monkeypatch, "ep-1", workspace)
    assert mod.main([]) == 0
    assert capsys.readouterr().out == ""


def test_entrypoint_silent_when_ask_hook_off(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Profile with ask_hook: off, resolved via $LINEAR_HANDLE.
    pdir = workspace / "platform" / "profiles"
    pdir.mkdir(parents=True)
    (pdir / "jordan.yaml").write_text(
        "handle: jordan\nlinear:\n  handle: jordan-lee\n"
        "preferences:\n  ask_hook: off\n"
    )
    monkeypatch.setenv("LINEAR_HANDLE", "jordan-lee")
    for i in range(8):
        (workspace / f"f{i}.py").write_text("x\n")
    mod = _load_entrypoint()
    _feed_stdin(monkeypatch, "ep-off", workspace)
    assert mod.main([]) == 0
    assert capsys.readouterr().out == ""


def test_entrypoint_atlas_only_never_asks(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Many touched files, but all under atlas/ → guard suppresses.
    adir = workspace / "atlas" / "capabilities"
    adir.mkdir(parents=True)
    for i in range(8):
        (adir / f"n{i}.md").write_text("---\nid: capability.n\nname: N\ntype: capability\n---\n")
    mod = _load_entrypoint()
    _feed_stdin(monkeypatch, "ep-atlas", workspace)
    assert mod.main([]) == 0
    assert capsys.readouterr().out == ""


def test_entrypoint_silent_outside_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # No repos.yaml anywhere above → not an egzakta session.
    monkeypatch.setenv("EGZAKTA_CACHE_DIR", str(tmp_path / ".cache"))
    mod = _load_entrypoint()
    _feed_stdin(monkeypatch, "ep-none", tmp_path)
    assert mod.main([]) == 0
    assert capsys.readouterr().out == ""
