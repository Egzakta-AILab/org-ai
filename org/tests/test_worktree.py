"""Tests for `org worktree` — unit + end-to-end against real git in tmp_path.

Linear API calls are skipped automatically when `LINEAR_API_KEY` is unset
(checked by the `_no_linear_key` autouse fixture), so the e2e tests exercise
worktree creation without touching the network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from egzakta_org.commands.worktree import (
    _branch_exists,
    _branch_name,
    _ensure_gitignore,
    _flatten,
    _parse_ticket,
    _resolve_target_repos,
    _worktree_path,
    app,
)
from egzakta_org.manifest import Manifest, Repo, WorkspaceSkills


runner = CliRunner()


# --- fixtures -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_linear_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests don't hit Linear. Force the env var off so claim logic short-circuits."""
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)


@pytest.fixture
def linear_handle(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("LINEAR_HANDLE", "alice")
    return "alice"


def _git_init(path: Path) -> None:
    """Make `path` a real git repo with one commit so worktrees can branch off."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def _write_repos_yaml(workspace: Path, repos: list[str]) -> None:
    body = "version: 1\nrepos:\n"
    for name in repos:
        body += f"  {name}:\n    url: https://example.com/{name}.git\n    status: active\n"
    (workspace / "repos.yaml").write_text(body, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Workspace with two real git repos (notewell + infra) and a manifest."""
    _write_repos_yaml(tmp_path, ["notewell", "infra"])
    _git_init(tmp_path / "notewell")
    _git_init(tmp_path / "infra")
    # Run all worktree commands from the workspace root.
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- _parse_ticket --------------------------------------------------------


def test_parse_ticket_uppercase() -> None:
    prefix, num, lower = _parse_ticket("NW-456")
    assert (prefix, num, lower) == ("NW", 456, "nw-456")


def test_parse_ticket_mixed_case() -> None:
    prefix, num, lower = _parse_ticket("nw-12")
    assert (prefix, num, lower) == ("NW", 12, "nw-12")


def test_parse_ticket_rejects_bad_shape() -> None:
    with pytest.raises(typer.BadParameter):
        _parse_ticket("not-a-ticket")
    with pytest.raises(typer.BadParameter):
        _parse_ticket("NW")
    with pytest.raises(typer.BadParameter):
        _parse_ticket("NW-abc")


# --- pure helpers ---------------------------------------------------------


def test_branch_name_format() -> None:
    assert _branch_name("alice", "nw-456") == "alice/nw-456"


def test_worktree_path_format(tmp_path: Path) -> None:
    assert _worktree_path(tmp_path / "notewell", "nw-456") == tmp_path / "notewell" / ".worktrees" / "nw-456"


def test_flatten_comma_and_repeat() -> None:
    assert _flatten(None) is None
    assert _flatten([]) is None
    assert _flatten(["notewell"]) == ["notewell"]
    assert _flatten(["notewell,infra"]) == ["notewell", "infra"]
    assert _flatten(["notewell", "infra,notewell"]) == ["notewell", "infra"]  # dedupe


# --- _ensure_gitignore ----------------------------------------------------


def test_ensure_gitignore_creates_missing(tmp_path: Path) -> None:
    _ensure_gitignore(tmp_path)
    assert (tmp_path / ".gitignore").read_text() == ".worktrees/\n"


def test_ensure_gitignore_appends_to_existing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    _ensure_gitignore(tmp_path)
    assert (tmp_path / ".gitignore").read_text() == "node_modules/\n.worktrees/\n"


def test_ensure_gitignore_idempotent(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("node_modules/\n.worktrees/\n")
    before = (tmp_path / ".gitignore").read_text()
    _ensure_gitignore(tmp_path)
    _ensure_gitignore(tmp_path)
    assert (tmp_path / ".gitignore").read_text() == before


def test_ensure_gitignore_accepts_unslashed_form(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".worktrees\n")
    before = (tmp_path / ".gitignore").read_text()
    _ensure_gitignore(tmp_path)
    assert (tmp_path / ".gitignore").read_text() == before


def test_ensure_gitignore_handles_no_trailing_newline(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("node_modules/")
    _ensure_gitignore(tmp_path)
    assert (tmp_path / ".gitignore").read_text() == "node_modules/\n.worktrees/\n"


# --- _resolve_target_repos -----------------------------------------------


def _manifest_with(*names: str) -> Manifest:
    repos = {
        name: Repo(name=name, url=f"https://example.com/{name}.git", status="active")
        for name in names
    }
    return Manifest(version=1, repos=repos, skills=WorkspaceSkills())


def test_resolve_explicit_wins(workspace: Path) -> None:
    manifest = _manifest_with("notewell", "infra")
    repos, issue = _resolve_target_repos(
        explicit=["infra"], ticket_full="NW-1", manifest=manifest, api_key=None
    )
    assert [r.name for r in repos] == ["infra"]
    assert issue is None


def test_resolve_explicit_unknown_repo_raises(workspace: Path) -> None:
    manifest = _manifest_with("notewell")
    with pytest.raises(typer.BadParameter):
        _resolve_target_repos(
            explicit=["Nonexistent"], ticket_full="NW-1", manifest=manifest, api_key=None
        )


def test_resolve_fallback_to_default_when_no_api_key(workspace: Path) -> None:
    manifest = _manifest_with("notewell", "infra")
    repos, issue = _resolve_target_repos(
        explicit=None, ticket_full="NW-1", manifest=manifest, api_key=None
    )
    # No API key → fallback to notewell with a warning.
    assert [r.name for r in repos] == ["notewell"]
    assert issue is None


# --- end-to-end create / list / drop --------------------------------------


def test_create_multi_repo(workspace: Path, linear_handle: str) -> None:
    result = runner.invoke(app, ["create", "NW-456", "--repos", "notewell,infra"])
    assert result.exit_code == 0, result.output
    assert (workspace / "notewell" / ".worktrees" / "nw-456").is_dir()
    assert (workspace / "infra" / ".worktrees" / "nw-456").is_dir()
    # Branch should exist in both repos.
    assert _branch_exists(workspace / "notewell", "alice/nw-456")
    assert _branch_exists(workspace / "infra", "alice/nw-456")
    # .gitignore should have been updated in both.
    assert ".worktrees/" in (workspace / "notewell" / ".gitignore").read_text()
    assert ".worktrees/" in (workspace / "infra" / ".gitignore").read_text()


def test_create_idempotent_on_existing_worktree(workspace: Path, linear_handle: str) -> None:
    runner.invoke(app, ["create", "NW-456", "--repos", "notewell"])
    result = runner.invoke(app, ["create", "NW-456", "--repos", "notewell"])
    assert "exists" in result.output


def test_create_requires_linear_handle(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINEAR_HANDLE", raising=False)
    result = runner.invoke(app, ["create", "NW-456", "--repos", "notewell"])
    assert result.exit_code != 0
    assert "LINEAR_HANDLE" in result.output


def test_create_rejects_bad_ticket(workspace: Path, linear_handle: str) -> None:
    result = runner.invoke(app, ["create", "bogus", "--repos", "notewell"])
    assert result.exit_code != 0


def test_create_falls_back_to_notewell_when_repos_omitted(workspace: Path, linear_handle: str) -> None:
    result = runner.invoke(app, ["create", "NW-456"])
    assert result.exit_code == 0
    assert (workspace / "notewell" / ".worktrees" / "nw-456").is_dir()
    assert not (workspace / "infra" / ".worktrees" / "nw-456").exists()


def test_list_empty_workspace_says_so(workspace: Path) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No active worktrees" in result.output


def test_list_shows_existing_worktrees(workspace: Path, linear_handle: str) -> None:
    runner.invoke(app, ["create", "NW-456", "--repos", "notewell,infra"])
    runner.invoke(app, ["create", "NW-789", "--repos", "notewell"])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "NW-456" in result.output
    assert "NW-789" in result.output


def test_list_filter_by_ticket(workspace: Path, linear_handle: str) -> None:
    runner.invoke(app, ["create", "NW-456", "--repos", "notewell,infra"])
    runner.invoke(app, ["create", "NW-789", "--repos", "notewell"])
    result = runner.invoke(app, ["list", "--ticket", "NW-456"])
    assert "NW-456" in result.output
    assert "NW-789" not in result.output


def test_drop_removes_worktrees(workspace: Path, linear_handle: str) -> None:
    runner.invoke(app, ["create", "NW-456", "--repos", "notewell,infra"])
    result = runner.invoke(app, ["drop", "NW-456"])
    assert result.exit_code == 0
    assert not (workspace / "notewell" / ".worktrees" / "nw-456").exists()
    assert not (workspace / "infra" / ".worktrees" / "nw-456").exists()


def test_drop_refuses_dirty_worktree(workspace: Path, linear_handle: str) -> None:
    runner.invoke(app, ["create", "NW-456", "--repos", "notewell"])
    # Add an uncommitted change inside the worktree.
    (workspace / "notewell" / ".worktrees" / "nw-456" / "new.txt").write_text("dirty\n")
    result = runner.invoke(app, ["drop", "NW-456"])
    assert result.exit_code == 2
    assert "Refusing to drop" in result.output
    assert (workspace / "notewell" / ".worktrees" / "nw-456").exists()


def test_drop_force_overrides_dirty(workspace: Path, linear_handle: str) -> None:
    runner.invoke(app, ["create", "NW-456", "--repos", "notewell"])
    (workspace / "notewell" / ".worktrees" / "nw-456" / "new.txt").write_text("dirty\n")
    result = runner.invoke(app, ["drop", "NW-456", "--force"])
    assert result.exit_code == 0
    assert not (workspace / "notewell" / ".worktrees" / "nw-456").exists()


def test_drop_silent_when_no_worktrees(workspace: Path) -> None:
    result = runner.invoke(app, ["drop", "NW-999"])
    assert result.exit_code == 0
    assert "No worktrees found" in result.output
