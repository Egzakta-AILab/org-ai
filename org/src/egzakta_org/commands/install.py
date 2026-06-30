"""`org install` — render platform sources into each tool's native files.

For every selected repo × tool × component, render the tool-agnostic source and write it
to the location that tool auto-loads (.claude/agents, .cursor/agents, .factory/droids,
CLAUDE.md / AGENTS.md). Single source in, per-tool files out.

Skills are different from the file components: a skill is a directory, installed via
git clone / file copy, not a token-substituted file write. The skills branch lives in
`egzakta_org.skills`; this module orchestrates and reports results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from rich.console import Console

from .. import hooks as hooks_mod
from .. import skills as skills_mod
from ..manifest import Manifest, Repo, load_manifest
from ..profiles import Profile, load_profiles
from ..render import render_agent, render_command, render_command_override, render_rule, render_standards
from ..users.loader import current_handle, current_user
from ..workspace import find_workspace_root, platform_dir

console = Console()

DEFAULT_COMPONENTS = ("agents", "standards", "commands", "rules", "hooks", "skills")

# File components share the renderer pipeline; "skills" goes through skills_mod;
# "hooks" goes through hooks_mod (script copies + settings.json merge).
_FILE_COMPONENTS = ("agents", "standards", "commands", "rules", "hooks")


@dataclass
class Action:
    repo: str
    tool: str
    component: str
    dest: Path
    content: str
    source_rel: str
    # Hook scripts need user-exec at write time; settings.json doesn't. The flag
    # keeps the renderer-driven write path uniform (just an extra chmod).
    executable: bool = False


def _infer_repo(root: Path, manifest: Manifest, cwd: Path) -> str | None:
    try:
        rel = cwd.resolve().relative_to(root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    first = rel.parts[0]
    return first if first in manifest.repos else None


def _agent_sources(plat: Path, repo: str) -> list[Path]:
    sources: list[Path] = []
    for folder in ("_shared", repo):
        sources.extend(sorted((plat / "agents" / folder).glob("*.md")))
    return sources


def _standards_source(plat: Path, repo: str) -> Path | None:
    path = plat / "standards" / repo / "instructions.md"
    return path if path.is_file() else None


def _rule_sources(plat: Path, repo: str) -> list[Path]:
    """`.mdc` rule sources for the given repo (+ optional _shared/)."""
    sources: list[Path] = []
    for folder in ("_shared", repo):
        sources.extend(sorted((plat / "rules" / folder).glob("*.mdc")))
    return sources


def _command_aliases(plat: Path, repo: str) -> dict[str, str]:
    """Load alias → target-agent mappings from platform/commands/<repo>/aliases.yaml.

    The file is optional; an empty mapping is returned when missing. Aliases are
    declared explicitly because they are the *only* non-derivable bit of the commands
    surface (1:1 wrappers are derived from the agent list).
    """
    path = plat / "commands" / repo / "aliases.yaml"
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases = raw.get("aliases") or {}
    return {str(name): str(target) for name, target in aliases.items()}


def _command_overrides(plat: Path, repo: str) -> dict[str, Path]:
    """Find authored slash-command files under `platform/commands/{_shared,<repo>}/*.md`.

    Returns {command-name: source-path}. Sources from `_shared/` first, then the
    per-repo folder — same-named files in `<repo>/` win (explicit per-repo intent
    overrides the shared baseline). Override files take precedence over both
    1:1 wrappers (same name as an agent) AND aliases — explicit author intent wins.
    `aliases.yaml` is excluded (it's the alias declaration, not a command file).
    """
    result: dict[str, Path] = {}
    for folder in ("_shared", repo):
        dir_ = plat / "commands" / folder
        if not dir_.is_dir():
            continue
        for path in sorted(dir_.glob("*.md")):
            result[path.stem] = path  # per-repo overwrites _shared with the same name
    return result


def _shared_agent_sources(plat: Path) -> list[Path]:
    return sorted((plat / "agents" / "_shared").glob("*.md"))


def _shared_command_sources(plat: Path) -> list[Path]:
    return sorted((plat / "commands" / "_shared").glob("*.md"))


def _build_global_actions(
    root: Path,
    plat: Path,
    profiles: dict[str, Profile],
    tools: list[str],
    components: list[str],
) -> list[Action]:
    """Build Actions for workspace-shared `_shared/` assets installed user-globally.

    Today: agents + commands (overrides only — 1:1 wrappers and aliases stay
    per-repo since they reference per-repo agents) + hooks (from
    platform/hooks/_shared/). Skills already have a parallel global path
    (skills_mod) and are handled by the caller.

    The destination uses each profile's *_global_dir. We pass `repo_name=""`
    to the renderer — all our tools set `repo_relative_paths: true`, so the
    `{{R}}` token already collapses to `""` and the rendered output is
    workspace-shared by design.

    Hooks are deliberately NOT layered into per-repo settings (unlike agents +
    commands): a Stop hook present in both the user-global settings and a repo's
    settings would fire twice per turn. They install global-only.
    """
    actions: list[Action] = []
    for tool in tools:
        profile = profiles[tool]
        if "agents" in components and profile.agents_global_dir:
            partials_root = plat / "agents" / "_partials"
            dest_root = Path(profile.agents_global_dir).expanduser()
            for src in _shared_agent_sources(plat):
                rel = src.relative_to(root).as_posix()
                content = render_agent(src.read_text(encoding="utf-8"), rel, profile, "", partials_root)
                dest = dest_root / src.name
                actions.append(Action("_shared", tool, "agents", dest, content, rel))
        if "commands" in components and profile.commands_global_dir:
            dest_root = Path(profile.commands_global_dir).expanduser()
            for src in _shared_command_sources(plat):
                rel = src.relative_to(root).as_posix()
                content = render_command_override(src.read_text(encoding="utf-8"), rel, profile, "")
                dest = dest_root / src.name
                actions.append(Action("_shared", tool, "commands", dest, content, rel))
        if (
            "hooks" in components
            and profile.hooks_global_dir
            and profile.settings_global_file
        ):
            actions.extend(_global_hook_actions(root, plat, profile, tool))
    return actions


def _global_hook_actions(root: Path, plat: Path, profile: Profile, tool: str) -> list[Action]:
    """Script-copy + settings-merge Actions for the user-global `_shared/` hooks.

    Mirrors the per-repo hooks branch in `_build_actions`, but the destination is
    the profile's *_global_* dirs and the rendered command path is absolute
    (the script lives under $HOME, not the active project).
    """
    hooks_global_dir = profile.hooks_global_dir
    settings_global_file = profile.settings_global_file
    if not (hooks_global_dir and settings_global_file):
        return []

    # `load_source` reads platform/hooks/<name>/ — "_shared" is just a folder name.
    source = hooks_mod.load_source(plat, "_shared", root)
    if source.is_empty:
        return []

    actions: list[Action] = []
    global_root = str(Path(hooks_global_dir).expanduser())
    scripts_root = Path(global_root) / hooks_mod.ENGINE_NAMESPACE
    tool_scripts = {b.script for b in source.bindings if tool in b.tools}
    for src in source.scripts:
        if src.name not in tool_scripts:
            continue
        rel = src.relative_to(root).as_posix()
        content = hooks_mod.render_script(src.read_text(encoding="utf-8"), rel)
        actions.append(
            Action("_shared", tool, "hooks", scripts_root / src.name, content, rel, executable=True)
        )

    managed = hooks_mod.build_managed_block(
        list(source.bindings), tool, profile.hooks_dir or "", global_root=global_root
    )
    if managed:
        settings_path = Path(settings_global_file).expanduser()
        current = hooks_mod.read_settings(settings_path)
        for k, v in hooks_mod.settings_template(tool).items():
            current.setdefault(k, v)
        merged = hooks_mod.merge_into_settings(current, managed, tool)
        content = hooks_mod.render_settings(merged)
        source_rel = (plat / "hooks" / "_shared" / "hooks.yaml").relative_to(root).as_posix()
        actions.append(Action("_shared", tool, "hooks", settings_path, content, source_rel))
    return actions


def _build_actions(
    root: Path,
    plat: Path,
    repo: Repo,
    profiles: dict[str, Profile],
    tools: list[str],
    components: list[str],
) -> list[Action]:
    actions: list[Action] = []
    repo_dir = root / repo.name
    for tool in tools:
        profile = profiles[tool]
        if "agents" in components:
            partials_root = plat / "agents" / "_partials"
            for src in _agent_sources(plat, repo.name):
                rel = src.relative_to(root).as_posix()
                content = render_agent(src.read_text(encoding="utf-8"), rel, profile, repo.name, partials_root)
                dest = repo_dir / profile.agents_dir / src.name
                actions.append(Action(repo.name, tool, "agents", dest, content, rel))
        if "standards" in components:
            src = _standards_source(plat, repo.name)
            if src is not None:
                rel = src.relative_to(root).as_posix()
                content = render_standards(src.read_text(encoding="utf-8"), rel, profile, repo.name)
                dest = repo_dir / profile.instructions_file
                actions.append(Action(repo.name, tool, "standards", dest, content, rel))
        if "rules" in components and profile.rules_dir:
            # Source files are .mdc (Cursor's original format). For Claude the
            # destination filename loses the `c` because .claude/rules/ expects .md.
            rule_ext = ".mdc" if profile.tool == "cursor" else ".md"
            for src in _rule_sources(plat, repo.name):
                rel = src.relative_to(root).as_posix()
                content = render_rule(src.read_text(encoding="utf-8"), rel, profile, repo.name)
                dest = repo_dir / profile.rules_dir / f"{src.stem}{rule_ext}"
                actions.append(Action(repo.name, tool, "rules", dest, content, rel))
        if "commands" in components and profile.commands_dir:
            seen: set[str] = set()
            # 1. Override files (highest priority — explicit author intent).
            #    `platform/commands/<repo>/<name>.md` with frontmatter + body. Wins
            #    over both 1:1 wrappers and aliases of the same name.
            for name, src in _command_overrides(plat, repo.name).items():
                seen.add(name)
                rel = src.relative_to(root).as_posix()
                content = render_command_override(src.read_text(encoding="utf-8"), rel, profile, repo.name)
                dest = repo_dir / profile.commands_dir / f"{name}.md"
                actions.append(Action(repo.name, tool, "commands", dest, content, rel))
            # 2. 1:1 wrappers: one slash-command per agent, sourced from the agent file.
            #    Factory droids are invoked directly as /<name>, so a 1:1 wrapper would
            #    shadow the droid for no benefit — `commands_only_aliases` skips them.
            if not profile.commands_only_aliases:
                for src in _agent_sources(plat, repo.name):
                    name = src.stem
                    if name in seen:
                        continue  # override won
                    seen.add(name)
                    rel = src.relative_to(root).as_posix()
                    content = render_command(name, rel, profile)
                    dest = repo_dir / profile.commands_dir / f"{name}.md"
                    actions.append(Action(repo.name, tool, "commands", dest, content, rel))
            # 3. Aliases: declared in platform/commands/<repo>/aliases.yaml. Targets must
            #    be real agents (we don't validate here — `--check` would catch a typo
            #    by failing to point at any existing agent).
            aliases = _command_aliases(plat, repo.name)
            aliases_rel = (plat / "commands" / repo.name / "aliases.yaml").relative_to(root).as_posix()
            for alias_name, target_agent in aliases.items():
                if alias_name in seen:
                    # Either an override or a 1:1 wrapper already produced this command;
                    # the alias would silently overwrite it. Skip with a warning instead.
                    console.print(
                        f"  [yellow]skip alias[/] {alias_name} → {target_agent}: "
                        f"a higher-priority command of the same name already exists"
                    )
                    continue
                content = render_command(target_agent, aliases_rel, profile)
                dest = repo_dir / profile.commands_dir / f"{alias_name}.md"
                actions.append(Action(repo.name, tool, "commands", dest, content, aliases_rel))
        if "hooks" in components and profile.hooks_dir and profile.settings_file:
            source = hooks_mod.load_source(plat, repo.name, root)
            if not source.is_empty:
                # Scripts: one Action per .sh source. Land at <hooks_dir>/_org/<name>.sh
                # so the engine namespace is obvious in the rendered settings command paths.
                # Only emit a script Action for THIS tool if at least one binding for THIS
                # tool references the script — avoids ghost scripts in droid/cursor when
                # only Claude bindings exist.
                tool_scripts = {
                    b.script for b in source.bindings if tool in b.tools
                }
                scripts_root = repo_dir / profile.hooks_dir / hooks_mod.ENGINE_NAMESPACE
                for src in source.scripts:
                    if src.name not in tool_scripts:
                        continue
                    rel = src.relative_to(root).as_posix()
                    content = hooks_mod.render_script(src.read_text(encoding="utf-8"), rel)
                    dest = scripts_root / src.name
                    actions.append(
                        Action(repo.name, tool, "hooks", dest, content, rel, executable=True)
                    )
                # Settings file: read current, strip engine-managed entries, merge in the
                # per-tool managed block built from hooks.yaml. The merged content is the
                # Action's expected on-disk state, so --check compares it directly.
                managed = hooks_mod.build_managed_block(
                    list(source.bindings), tool, profile.hooks_dir
                )
                if managed:
                    settings_path = repo_dir / profile.settings_file
                    current = hooks_mod.read_settings(settings_path)
                    # Cursor wants a top-level `version: 1` even when there are no other
                    # fields; merge that in for fresh files (don't overwrite if present).
                    for k, v in hooks_mod.settings_template(tool).items():
                        current.setdefault(k, v)
                    merged = hooks_mod.merge_into_settings(current, managed, tool)
                    content = hooks_mod.render_settings(merged)
                    source_rel = (plat / "hooks" / repo.name / "hooks.yaml").relative_to(root).as_posix()
                    actions.append(Action(repo.name, tool, "hooks", settings_path, content, source_rel))
    return actions


def _check(actions: list[Action], root: Path) -> int:
    drift = 0
    for a in actions:
        current = a.dest.read_text(encoding="utf-8") if a.dest.is_file() else None
        if current == a.content:
            continue
        drift += 1
        label = _action_dest_label(a, root)
        if current is None:
            console.print(f"  [yellow]MISSING[/] {label}  (would be created from {a.source_rel})")
        else:
            console.print(f"  [red]DRIFT[/]   {label}  (differs from {a.source_rel})")
    return drift


def _action_dest_label(a: Action, root: Path) -> str:
    """Human-friendly destination path. Workspace files are repo-relative;
    user-global files (anywhere outside the workspace root) collapse $HOME → ~.
    """
    try:
        return str(a.dest.relative_to(root))
    except ValueError:
        return _dest_label(a.dest)


def _dest_label(dest: Path) -> str:
    """Short, human-friendly version of an absolute path (collapses $HOME → ~)."""
    home = str(Path.home())
    s = str(dest)
    return s.replace(home, "~", 1) if s.startswith(home) else s


def install(
    *,
    tools: list[str] | None = None,
    components: list[str] | None = None,
    repos: list[str] | None = None,
    tags: list[str] | None = None,
    is_global: bool = False,
    check: bool = False,
    dry_run: bool = False,
) -> int:
    root = find_workspace_root()
    manifest = load_manifest(root)
    plat = platform_dir(root)
    profiles = load_profiles(plat)

    comps = components or list(DEFAULT_COMPONENTS)
    file_comps = [c for c in comps if c in _FILE_COMPONENTS]
    do_skills = "skills" in comps

    unknown = [t for t in (tools or []) if t not in profiles]
    if unknown:
        console.print(f"[red]Unknown tool(s):[/] {', '.join(unknown)}. Known: {', '.join(profiles)}")
        return 2

    # ---- Resolve scope ---------------------------------------------------------
    selected: list[Repo] = []
    # --global: workspace-shared assets land user-globally. Today: skills, agents,
    # commands (from platform/{agents,commands}/_shared/), hooks (from
    # platform/hooks/_shared/). Standards + rules have no user-global target —
    # drop with a note when asked.
    _GLOBAL_FILE_COMPS = ("agents", "commands", "hooks")
    global_file_comps: list[str] = []
    if is_global:
        global_file_comps = [c for c in file_comps if c in _GLOBAL_FILE_COMPS]
        ignored = [c for c in file_comps if c not in _GLOBAL_FILE_COMPS]
        if ignored:
            console.print(
                f"[yellow]--global has no destination for[/] ({', '.join(ignored)}); "
                "those install per-repo only."
            )
    else:
        if repos:
            selected = manifest.select(names=repos)
        elif tags:
            selected = manifest.select(tags=tags)
        else:
            inferred = _infer_repo(root, manifest, Path.cwd())
            if inferred is not None:
                selected = manifest.select(names=[inferred])
            elif do_skills and not file_comps:
                # Bare `org install --component skills` from outside a repo: tell the
                # user how to scope it. We don't silently fall through to "Nothing to do".
                console.print(
                    "[red]No target.[/] Pass --global for workspace skills, "
                    "or --repo NAME for a repo's project skills."
                )
                return 2
            else:
                console.print(
                    "[red]No target.[/] Pass --repo NAME or --tags SEL, or run from inside a repo."
                )
                return 2

    # ---- Build file actions ---------------------------------------------------
    all_file_actions: list[Action] = []
    if is_global and global_file_comps:
        # When tools isn't explicitly set, install to every tool that ships a
        # `<comp>_global` dir — workspace-shared assets should reach every dev's
        # active tool by default.
        gtools = tools or list(profiles)
        all_file_actions.extend(_build_global_actions(root, plat, profiles, gtools, global_file_comps))
    elif not is_global and file_comps:
        for repo in selected:
            repo_dir = root / repo.name
            if not repo_dir.is_dir():
                console.print(f"[yellow]skip[/] {repo.name}: not cloned (run `org clone`)")
                continue
            repo_tools = tools or list(repo.tools)
            if not repo_tools:
                console.print(
                    f"[yellow]skip[/] {repo.name}: no tools (set `tools:` in repos.yaml or pass --tool)"
                )
                continue
            all_file_actions.extend(_build_actions(root, plat, repo, profiles, repo_tools, file_comps))

    # ---- Build skill actions --------------------------------------------------
    skill_actions: list[skills_mod.SkillAction] = []
    skill_warnings: list[str] = []
    if do_skills:
        registry = skills_mod.load_registry(plat)
        if is_global:
            # Shared baseline + current dev's personal opt-in skills (from their profile).
            global_skills = manifest.skills.global_
            user = current_user(root)
            if user is not None and user.skills:
                extra = tuple(s for s in user.skills if s not in global_skills)
                if extra:
                    global_skills = global_skills + extra
                    console.print(f"  [dim]+ personal skills from profile {user.handle}: {', '.join(extra)}[/]")
            elif current_handle(root) is None:
                console.print("  [yellow]note[/] LINEAR_HANDLE unset → personal profile skills skipped")
            skill_actions, skill_warnings = skills_mod.build_actions(
                plat,
                registry,
                profiles,
                is_global=True,
                global_skills=global_skills,
                repos_with_skills=[],
                tools_filter=tools,
            )
        else:
            repos_with_skills = []
            for repo in selected:
                repo_dir = root / repo.name
                if not repo_dir.is_dir():
                    continue
                if repo.skills:
                    repos_with_skills.append((repo.name, repo_dir, tuple(repo.skills)))
            skill_actions, skill_warnings = skills_mod.build_actions(
                plat,
                registry,
                profiles,
                is_global=False,
                global_skills=(),
                repos_with_skills=repos_with_skills,
                tools_filter=tools,
            )
    for warn in skill_warnings:
        console.print(f"  [yellow]warn[/] {warn}")

    if not all_file_actions and not skill_actions:
        console.print("Nothing to do.")
        return 0

    drift_total = 0

    # ---- Process file actions -------------------------------------------------
    if all_file_actions:
        if check:
            console.print(f"[bold]Checking[/] {len(all_file_actions)} target file(s) for drift…")
            drift_total += _check(all_file_actions, root)
        elif dry_run:
            console.print(f"[bold]Would write[/] {len(all_file_actions)} file(s):")
            for a in all_file_actions:
                console.print(
                    f"  [cyan]{a.repo}[/] {_action_dest_label(a, root)}  ({a.tool}, {a.component})"
                )
        else:
            console.print(f"[bold]Installing[/] {len(all_file_actions)} file(s)…")
            for a in all_file_actions:
                a.dest.parent.mkdir(parents=True, exist_ok=True)
                if a.executable:
                    hooks_mod.write_executable(a.dest, a.content)
                else:
                    a.dest.write_text(a.content, encoding="utf-8")
                console.print(f"  [green]wrote[/] {_action_dest_label(a, root)}")

    # ---- Process skill actions ------------------------------------------------
    if skill_actions:
        verb = "Checking" if check else ("Would install" if dry_run else "Installing")
        console.print(f"[bold]{verb}[/] {len(skill_actions)} skill destination(s)…")
        secrets_needed: set[str] = set()
        for action in skill_actions:
            result = skills_mod.process(action, plat, check=check, dry_run=dry_run, console=console)
            secrets_needed.update(result.secrets)
            label = _dest_label(action.dest)
            tag = f"{action.skill} → {action.tool}"
            if result.status == "OK":
                console.print(f"  [green]ok[/]      {tag}  ({label})")
            elif result.status == "INSTALLED":
                console.print(f"  [green]installed[/] {tag}  ({label}; {result.detail})")
            elif result.status == "WOULD":
                console.print(f"  [cyan]would[/]    {tag}  — {result.detail}")
            elif result.status == "DRIFT":
                drift_total += 1
                console.print(f"  [red]DRIFT[/]    {tag}  ({label}; {result.detail})")
            elif result.status == "ERROR":
                drift_total += 1
                console.print(f"  [red]error[/]    {tag}  ({label}; {result.detail})")
            else:
                console.print(f"  {result.status} {tag}  ({label}; {result.detail})")
        if secrets_needed and not check:
            console.print(
                "  [dim]secrets required at runtime: "
                + ", ".join(sorted(secrets_needed))
                + " — set them in your environment[/]"
            )

    # ---- Aggregate exit --------------------------------------------------------
    if check:
        if drift_total:
            console.print(f"[red]{drift_total} target(s) out of sync.[/] Run `org install` to regenerate.")
            return 1
        console.print("[green]All targets are in sync.[/]")
    return 0
