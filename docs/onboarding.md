# Getting started — from zero to your first ticket

Welcome. This guide takes you from a fresh laptop to shipping your first ticket
with Claude as your copilot. No prior knowledge of the workspace assumed.

Here's the big picture in one breath: all our repos (notewell, infra, and the
rest) live together inside one folder called the **workspace**. A small CLI named
`org` keeps them in sync and gives every coding agent the same skills, the same
knowledge graph, and the same workflow — no matter which repo you're in. You set
it up once, and then most of your day is one command: `/work-ticket`.

By the end you'll have the workspace installed, your profile set up, and you'll
have walked through working a ticket end to end. Plan for about 15 minutes.

---

## What you need first

- **A Mac, Linux, or Windows machine** with `git`. On Windows, install
  [Git for Windows](https://git-scm.com/download/win) and run the commands in
  this guide from **PowerShell** (the `org`, `git`, and `uv` commands are
  identical; only the install one-liners and env-var setup differ, called out
  inline below).
- **[uv](https://docs.astral.sh/uv/)** — our Python runner. Install it with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  > **On Windows (PowerShell):**
  > ```powershell
  > powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  > ```
  > Then **close and reopen** your terminal so `uv` is on your PATH.
- **[Node.js](https://nodejs.org/) (LTS)** — the `linear` skill installs its npm
  dependencies during Step 4, so `node` and `npm` must be on your PATH.
- **A coding agent** — [Claude Code](https://claude.com/claude-code) is the one
  this guide uses. Cursor and Factory droid work too; the commands are identical.
- **Two things from Linear** (our issue tracker):
  1. Your **handle** — find it at `linear.app/<workspace>/profile/<your-handle>`.
  2. A **personal API key** — Linear → Settings → Security & access → Personal
     API keys → Create key. It starts with `lin_api_`.

> A note on the API key: it's a secret. Don't paste it into a chat, a commit, or
> any file that gets committed. You'll put it in your shell config in Step 2, and
> that's the only place it lives.

---

## Step 1 — Get the workspace

Clone the meta-repo (the folder is called `egzakta` even though the remote is
`egzakta-org`), then put the `org` CLI on your PATH:

```bash
git clone https://github.com/UkisAI-Egzakta/org-ai.git egzakta
cd egzakta
uv tool install --editable ./org
org version          # should print a version — that means it's working
```

`org` finds the workspace from any folder inside it, so you never have to be in a
specific directory to use it.

---

## Step 2 — Tell your shell who you are

Add two lines to your `~/.zshrc` (or `~/.bashrc`), then open a new terminal:

```bash
# Your Linear handle — used for branch names and to find your profile.
export LINEAR_HANDLE=your-linear-handle

# Your Linear API key — lets the tools read tickets and post comments.
export LINEAR_API_KEY=lin_api_xxxxxxxxxxxxxxxx
```

> **On Windows** there's no shell rc — set these as **user environment
> variables** instead.
>
> Quick way, in PowerShell:
> ```powershell
> setx LINEAR_HANDLE "your-linear-handle"
> setx LINEAR_API_KEY "lin_api_xxxxxxxxxxxxxxxx"
> ```
> `setx` writes to your persistent user environment but does **not** touch the
> current terminal — **close and reopen** PowerShell, then confirm with
> `echo $env:LINEAR_HANDLE`.
>
> Prefer clicking? **Start → "Edit the system environment variables" →
> Environment Variables… → New** under *User variables*, add each name and value,
> then open a new terminal.

That's the only place your key needs to be. The tooling reads it from the
environment and never writes it anywhere.

---

## Step 3 — Pull in the code repos

The code repos aren't part of the meta-repo — they're separate clones that live
inside the workspace. Grab them all in one go:

```bash
org clone            # clones every repo listed in repos.yaml
org status           # shows the git state of each one
```

If a repo already exists on your disk, `org clone` leaves it untouched. Nothing
gets clobbered.

---

## Step 4 — Install the shared toolkit

This is the step that makes every agent session feel the same. One command
installs the workspace-shared skills, the `/work-ticket` command, and the
end-of-session helper into your user-level config (so they work from any folder):

```bash
org install --global
```

You'll see a note that `standards` and `rules` "install per-repo only" — that's
expected, those are repo-specific. Everything else (skills, `/work-ticket`, the
closing nudge) is now available everywhere.

Then install the repo-specific pieces for whatever you're working on — the agents,
coding standards, and review tools that are tuned to that repo:

```bash
org install --repo notewell
```

Run that for any repo you'll touch. You can re-run `org install` any time; it only
rewrites what changed.

---

## Step 5 — Make your profile

Your profile tells agents how you like to work — how deep to grill a design, how
terse to keep reviews, how much detail to put in a handoff. It also records which
parts of the system you own.

```bash
org user init        # fills in your identity from Linear + git history
```

Then open a Claude session in the workspace and run the interview:

```
/profile-me
```

It asks you a handful of questions and writes the answers to
`platform/profiles/<your-handle>.yaml`. Review the file, then commit it so the team
can see who owns what. (You can edit it by hand later — it's just YAML.)

---

## Step 6 — Meet the atlas

The **atlas** is our knowledge graph: a typed map of what we're building
(capabilities), what they run on (platform), how we operate (ops), and the big
decisions that shaped the system. It lives at `atlas/` as one markdown file per
"node," and it's the thing that lets an agent understand how your little change
fits the whole picture.

**Good news on setup: there's nothing extra to install.** The `org atlas`
commands ship with the `org` CLI (Step 1), and the `atlas` skill — which teaches
agents when to consult it — came in with `org install --global` (Step 4). So you
can already browse it:

```bash
org atlas list                              # every node
org atlas list --type capability            # just the capabilities
org atlas show capability.search.hybrid-retrieval   # one node, in full
```

That's the **file tier** — it reads the markdown directly, works from any folder,
needs no app and no network. It's how agents, CI, and the hooks all read the atlas.

You'll bump into the atlas naturally while working: when a ticket is linked to a
capability, `/work-ticket` grounds the session in the relevant node for you, and
the `/zoom-out` skill uses it to map an unfamiliar area. When your change alters
how a capability behaves — its status, its metrics, or the files it points at —
update that node in a small follow-up, and run `org atlas validate` before you
commit. (Design decisions go in the node's `## Decisions` section — that's where
`/grill-with-docs` writes too.)

### Browse it visually in Obsidian

The file tier is all an agent ever needs. But if you'd rather *click* around the
graph than read raw markdown, point [Obsidian](https://obsidian.md/download) at
the atlas and you get backlinks, full-text search, and a graph view of the
`depends_on` / `unlocks` edges between nodes.

1. Install **Obsidian Desktop** (free) from [obsidian.md/download](https://obsidian.md/download).
2. In Obsidian: **Open folder as vault** → select your `atlas/` folder.
3. Done. First open writes a `.obsidian/` folder for *your* personal layout — it's
   gitignored, so it never lands in the repo.

You're now browsing your own git working copy. Open the **graph view** (left-rail
icon, or ⌘P → "Open graph view") to see how nodes connect, click any node to jump
to it, and use the **backlinks** pane to see what points *at* the node you're
reading. None of this touches the network — it's just a nicer lens on the same
files `org atlas` reads.

> Edits you make in Obsidian *are* edits to the git files. That's fine — review
> them with `git diff` and run `org atlas validate` before you commit, exactly as
> you would for any hand edit.

### Optional — let an agent drive Obsidian (`obsidian-cli`)

For interactive vault work *from an agent* — "search the vault for X", "show me
this node's outline", "what links here" — there's the **`obsidian-cli`** skill. It
already came in with `org install --global` (Step 4); you just switch on the
underlying CLI:

1. Obsidian **v1.12 or newer** (the official CLI shipped Feb 2026).
2. **Settings → Command line interface → toggle ON.** On macOS/Linux this drops an
   `obsidian` binary on your PATH automatically.
   > **On Windows**, enabling the CLI installs `obsidian.exe` under
   > `%LOCALAPPDATA%\Obsidian\`. If `obsidian version` isn't found, add that
   > folder to your PATH (the same Environment Variables dialog from Step 2) and
   > open a new terminal.
3. **Keep Obsidian running** — the CLI talks to the live app over IPC and does
   nothing while the app is closed.

Verify it:

```bash
obsidian version          # prints the app version → CLI is wired up
obsidian vault            # shows the active vault (should be your atlas)
```

The CLI drives **whatever vault is currently active**, so keep your `atlas/` vault
focused when you want an agent working in it.

> This tier is **GUI-bound** by design — it needs the running app, so it's useless
> in CI, hooks, or headless agent loops. Those always use the `org atlas` file
> tier. Reach for `obsidian-cli` only when you're interactively browsing.

### Sharing with non-dev teammates — the shared mirror

Devs live in git; PMs, designers, and other non-dev teammates read and edit the
atlas through **Obsidian on a shared cloud folder**. That copy is a **one-way
mirror** of git, and the sync is **manual** — there is no cron job, no `org atlas
publish`, and no two-way sync:

- **git is canonical.** You *publish* git → the mirror with `rsync` (run with
  `--delete`, so the mirror ends up byte-for-byte matching git). Nothing syncs on
  its own — you run the publish on purpose, and always dry-run it first.
- **Non-dev edits don't flow back automatically.** When a teammate changes
  something in the mirror vault, a dev copies it into git, validates, and commits
  — *before* the next publish, which would otherwise overwrite it with `--delete`.

One-time setup: export `$ATLAS_PUBLISH_TARGET` in your shell rc pointing at your
local mount of the shared cloud folder (e.g. `~/cloud-mirror/notewell/atlas`). The
actual dry-run-first `rsync` recipe, the editing workflow, and the validation rules
all live in **[atlas.md](atlas.md)**.

> You can skip this whole subsection until you actually need to share the atlas
> outside the dev team.

> Don't worry about memorizing node ids. `org atlas list` is right there, and most
> of the time `/work-ticket` surfaces the right node for you.

---

## Step 7 — Work on a ticket

Here's the part you'll do every day. Open a Claude session — from the workspace
root or from inside a repo, either works — and run:

```
/work-ticket NW-123
```

`/work-ticket` does the boring preflight for you:

1. **Pulls the ticket** from Linear so the full context is in front of you.
2. **Grounds in the atlas** — our knowledge graph — if the ticket is linked to a
   capability, so the agent knows how the piece fits the whole.
3. **Creates a worktree** at `<repo>/.worktrees/nw-123/` on a branch named
   `your-handle/nw-123`. (A worktree is just an isolated copy of the repo on its
   own branch — it means you can have several tickets in flight without them
   stepping on each other.) For a ticket that spans repos, it makes one in each.
4. **Stops and hands you a brief.** It does **not** start writing code.

That last point is the whole philosophy: **the agent is your copilot, not your
autopilot.** You read the brief, you decide the approach, you stay in the loop.
That's how you grow the judgment that makes you a better engineer — the AI
critiques and accelerates, but you own the solution.

From there a normal ticket looks like:

- **If the ticket is labeled `complexity:high`**, the workflow requires a design
  grill first. Run `/grill-with-docs` — it interrogates your plan one question at a
  time against the atlas and the codebase until the design holds up. (For simpler
  tickets this is optional but still a great habit.)
- **Implement.** Drive the work yourself, leaning on the agent for the parts where
  it helps. Stuck on a gnarly bug? `/diagnose` walks a disciplined debugging loop.
  New to the area? `/zoom-out` maps it for you using the atlas.
- **Review your diff** before you push. `/review-2axis` is a quick two-angle read
  that works in any repo.
- **Open the PR.** Use your handle in the branch name (already done by the
  worktree) so Linear auto-links it.
- **Close the loop in Linear** — drop a comment with the PR link and move the
  ticket along.

For the full, detailed version of this loop, see
[working-on-tickets.md](working-on-tickets.md).

---

## Step 8 — The closing nudge

At the end of a work session, Claude may ask you **one** quick question — and only
when it's actually useful. For example: "You've got 3 commits on NW-123 with no
Linear update. Comment now?" or "Long session, no handoff written — want one?"

Answer it or skip it. It never asks more than once per session, and it stays quiet
for a week after you've dealt with something. Sessions where you only edited the
atlas never get nudged at all.

If it's not for you, turn it off in your profile:

```yaml
# platform/profiles/<your-handle>.yaml
preferences:
  ask_hook: off
```

(It's on by default. To get the nudge in the first place, make sure you ran
`org install --global` in Step 4.)

---

## Your daily cheat sheet

```bash
org status                       # where does every repo stand?
org clone                        # pull the latest of every repo
org install --repo notewell      # refresh a repo's agents/standards after a pull
org worktree list                # what am I working on right now?
org atlas show <node-id>         # look something up in the knowledge graph
```

And inside a Claude session:

```
/work-ticket NW-123     start a ticket (pull + atlas + worktree + brief)
/grill-with-docs          pressure-test a design (required for complexity:high)
/diagnose                 disciplined debugging for a hard bug
/zoom-out                 map an unfamiliar area via the atlas
/review-2axis             two-axis review of your diff
/handoff                  leave a note for the next session
```

---

## When something looks off

Most problems are drift between the generated files and their sources. These three
commands localize almost anything:

```bash
org install --check        # are the generated files in sync with platform/?
org atlas validate         # is the knowledge graph well-formed?
org status                 # any repo in a weird git state?
```

If `org install --check` reports drift, just run `org install` (or
`org install --repo <name>`) to regenerate. A broken loop is worse than no loop —
fix drift before starting real work.

> **On Windows**, if `org install` reports a skill patch "does not apply" (most
> often the `linear` skill), it's usually a **stale clone with CRLF line
> endings** left over from a checkout that predates the repo's `.gitattributes`.
> Delete the installed skill folders and re-run — the fresh clone is forced to
> LF:
> ```powershell
> Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\linear", "$env:USERPROFILE\.cursor\skills\linear", "$env:USERPROFILE\.factory\skills\linear"
> org install --global
> ```
> If the skill clones but its `npm install` post-step fails, make sure Node.js is
> installed (see "What you need first"), then run `npm install` once inside each
> skill folder.

Still stuck? The deeper docs are [setup.md](setup.md) for installation details,
[skills.md](skills.md) for what each skill does, and
[workspace-platform.md](workspace-platform.md) for how the whole thing is designed.
