# Setup — egzakta workspace

How to get a working egzakta workspace on a fresh machine.

## 1. Clone the meta-repo

The meta-repo (`org-ai`) versions the orchestration layer. Clone it as your workspace
root. The canonical local folder name is `egzakta/` even though the remote is `org-ai`:

```bash
git clone https://github.com/UkisAI-Egzakta/org-ai.git egzakta
cd egzakta
```

The code repos are **not** in this repo — they are independent clones, gitignored. You add them
in step 3.

## 2. Install the `org` CLI

Requires Python 3.13+. Install with [uv](https://docs.astral.sh/uv/) (recommended) or pipx:

```bash
uv tool install --editable ./org      # or: pipx install -e ./org
org version
```

`org` finds the workspace root by walking up to `repos.yaml`, so it works from any subdirectory.

> **Windows.** Install `uv` from PowerShell, then open a new terminal so it lands
> on PATH:
> ```powershell
> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
> ```
> The `uv tool install` / `org` commands above are identical in PowerShell. Run
> all setup steps from PowerShell, and use [Git for Windows](https://git-scm.com/download/win)
> so the repo's `.gitattributes` keeps `.sh`/`.patch` assets as LF on checkout
> (the `org` engine applies skill patches byte-for-byte and needs LF).

## 3. Clone the repos

```bash
org clone                 # clone/fast-forward every repo in repos.yaml
org status                # see per-repo git state
```

Repos that already exist as non-git directories are skipped (never clobbered); local-only
experiments without a `url` are skipped too.

## 4. Install platform assets into a repo

`org install` renders all six platform components from `platform/` into each coding tool's
native files (Claude Code, Cursor, Factory droid):

```bash
org install --repo notewell                       # all of notewell's tools, all components
org install --repo notewell --tool claude         # claude only
org install --repo notewell --tool claude,cursor  # claude + cursor
org install --repo notewell --component agents    # just the agents
org install --repo notewell --component hooks     # just the hooks (scripts + settings merge)
org install --repo notewell --check               # report drift (use in CI), non-zero exit
```

Components: `agents`, `standards`, `commands`, `rules`, `hooks`, `skills` (default: all).
Which tools a repo gets by default comes from its `tools:` list in `repos.yaml`; `--tool`
overrides it. Generated files carry a "do not edit — edit the source" marker; change behaviour
in `platform/`, then re-run `org install`. See [org/README.md](../org/README.md) for the full
per-tool destination table.

## 5. Workspace-shared assets (skills, commands, agents)

`org install --global` installs workspace-shared assets at the user level so they
resolve from any cwd — workspace root, any sub-repo, any sub-dir:

```bash
org install --global                                          # all global components
org install --global --component skills                       # skills only
org install --global --component commands                     # /work-ticket + future _shared/ commands
org install --global --component agents                       # future _shared/ agents
org install --global --tool claude                            # claude only across all components
org install --global --check                                  # CI drift guard
```

What flows where on `--global`:

| Component | Source | User-global destination |
|---|---|---|
| skills | `platform/skills/index.yaml` (top-level `skills.global:`) | `~/.claude/skills/`, `~/.cursor/skills/`, `~/.factory/skills/` |
| commands | `platform/commands/_shared/*.md` | `~/.claude/commands/`, `~/.cursor/commands/`, `~/.factory/commands/` |
| agents | `platform/agents/_shared/*.md` (currently empty; reserved) | `~/.claude/agents/`, `~/.cursor/agents/`, `~/.factory/droids/` |
| hooks | `platform/hooks/_shared/{hooks.yaml,scripts/}` | scripts → `~/.<tool>/hooks/_org/`; bindings merged into `~/.claude/settings.json`, `~/.cursor/hooks.json`, `~/.factory/settings.json` |

`standards` and `rules` have no user-global destination — they're repo-scoped only.
Unlike agents + commands, `_shared/` hooks are **not** also layered into each repo's
settings: a `Stop` hook present in both the user-global and a repo's settings would
fire twice per turn, so they install global-only.

Per-repo skills, agents, commands (when a repo lists them in its `skills:` / per-repo
sources) install via `org install --repo <name>`. The per-repo install layers atop the
user-global install: `_shared/` assets are also rendered into each repo's `.<tool>/`
directories so repo-scoped sessions see them too. Per-repo overrides win over the
shared baseline.

Some skills declare a `post_install` step — the `linear` skill runs `npm install` —
so **[Node.js](https://nodejs.org/) (LTS) must be on your PATH** before
`org install --global`. See [skills.md](skills.md) for the skills catalogue (what's
installed, where, secrets required).

> **Windows.** If a skill patch reports "does not apply" (typically `linear`), an
> earlier checkout left CRLF line endings in the skill clone. Remove the installed
> skill folders and re-run — the fresh clone is forced to LF:
> ```powershell
> Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\linear", "$env:USERPROFILE\.cursor\skills\linear", "$env:USERPROFILE\.factory\skills\linear"
> org install --global
> ```

## 6. Atlas — the workspace knowledge graph

The atlas at `atlas/` is git-canonical and queryable headlessly via `org atlas`:

```bash
org atlas list --type capability               # browse nodes
org atlas show capability.search.hybrid-retrieval
org atlas validate                             # surface broken code_refs, etc.
```

See [atlas.md](atlas.md) for the two-tier access model (file-tier headless + obsidian-cli
GUI companion) and the publish-to-shared-mirror workflow.

## 7. Shell environment

Set two env vars in your shell rc — both are per-teammate and never hardcoded
in shared sources:

```bash
# ~/.zshrc (or ~/.bashrc)

# Your Linear username. Used by /work-ticket and by the workflow's branch
# convention (<your-handle>/nw-NNN — that's how Linear auto-links PRs).
# Find your handle on your Linear profile: linear.app/<workspace>/profile/<your-handle>
export LINEAR_HANDLE=your-linear-username       # e.g. jordan-lee

# Path to the shared cloud mirror of the atlas (used only when publishing
# the atlas to non-dev teammates). Set to the local mount path of the
# shared folder. Skip this if you never publish the atlas.
export ATLAS_PUBLISH_TARGET="$HOME/cloud-mirror/notewell/atlas"
```

> **Windows.** There's no shell rc — set these as **user environment variables**.
> Quick way in PowerShell (`setx` persists to your user environment but doesn't
> affect the open terminal, so reopen it afterward):
> ```powershell
> setx LINEAR_HANDLE "your-linear-username"
> setx LINEAR_API_KEY "lin_api_xxxxxxxxxxxxxxxx"
> setx ATLAS_PUBLISH_TARGET "%USERPROFILE%\cloud-mirror\notewell\atlas"
> ```
> Or set them via **Start → "Edit the system environment variables" →
> Environment Variables… → New** under *User variables*. Read them back in a new
> terminal with `echo $env:LINEAR_HANDLE`. Note `rsync` isn't native on Windows —
> publish the atlas from Git Bash / WSL, or use `robocopy <src> <dst> /MIR`.

## 8. Bootstrap your user profile

`org user init` writes a per-developer profile that agents read for calibration
(grill depth, review style, handoff verbosity) and that the atlas cross-references
against `owners:` lists.

```bash
# Prereqs: $LINEAR_HANDLE + $LINEAR_API_KEY set (the bootstrap calls the Linear
# viewer query to autofill user_id, email, displayName).
org user init                       # writes platform/profiles/<short-handle>.yaml stub
org user init --dry-run             # preview without writing
org user init --handle jordan       # override the auto-suggested short handle

# After the stub exists, fill in the qualitative fields (role, areas, owns,
# learning, preferences) via the /profile-me skill in a Claude session:
> /profile-me

# Cross-checks:
org user list                       # registered profiles
org user show jordan                # one full profile
org user show jordan --field preferences.grill_depth    # single field
org user validate                   # schema + atlas-owner coverage
```

The short handle (filename) matches what appears in atlas `owners:` lists — e.g.
`jordan` for `jordan-lee`. The Linear handle lives inside the YAML under `linear:`
for the bridge.

Commit your profile to the meta-repo so the team can see who owns what.

## 9. First ticket

See [working-on-tickets.md](working-on-tickets.md) for the end-to-end loop
(Linear → atlas → worktree → grill (if `complexity:high`) → implement → review → PR).
The `/work-ticket NW-NNN` slash command (workspace-shared, installed via
`org install --global`) automates the preflight from any cwd: pulls ticket, grounds
in atlas, runs `org worktree create` to make worktrees in every affected repo, gates
on `complexity:high` (mandatory `/grill-with-docs`), and assembles the dispatch
template for the implementer.
