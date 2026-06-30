---
name: profile-me
description: >
  Fill in the qualitative fields of your egzakta workspace profile (role,
  areas, owns, learning, preferences) via a short grilling interview. Updates
  `platform/profiles/<short-handle>.yaml` in place. Run once after
  `org user init` to bootstrap, then re-run whenever your role / interests /
  preferences shift.
<!-- tool:claude -->
allowed-tools: Bash, Read, Write
<!-- /tool -->
<!-- tool:cursor,droid -->
allowed-tools: Bash Read Write
<!-- /tool -->
metadata:
  version: "0.1.0"
  triggers:
    - "profile-me"
    - "set up my profile"
    - "update my profile"
    - "/profile-me"
---

# profile-me — interview-driven profile completion

`org user init` writes the stub (handle, Linear identity, git authors). This
skill fills in the qualitative half (role, areas, owns, learning,
preferences) through a short interview — mattpocock-style: one question at a
time, never assume, never auto-commit.

## When to use

- **Once after `org user init`** to fill the TODOs.
- **When your role changes** (junior → mid, mid → senior, dev → PM).
- **When a capability you used to own moves to someone else**, or you start
  owning a new one.
- **When the default preferences feel off** — e.g. agents are grilling you
  too lightly (raise `grill_depth`) or reviews are too explanatory (drop
  `review_style` to terse).

## Precondition

```bash
test -f "platform/profiles/$(org user show --handle "$LINEAR_HANDLE" 2>/dev/null || echo MISSING).yaml"
```

If no profile exists, STOP and tell the user:

> "No profile found. Run `org user init` first to create the stub, then I'll
> fill in the qualitative fields."

## Procedure

### 1. Load the current state

```bash
SHORT_HANDLE=$(org user list 2>/dev/null | rg -A1 "$LINEAR_HANDLE" | head -1)
# OR: derive from `org user list` + match on linear.handle field
org user show "${SHORT_HANDLE}"
```

Read the existing values. Treat them as the user's last answers — don't
re-ask, just confirm at the end.

### 2. Interview — one question at a time

For each question, propose a recommended answer based on context (the
existing YAML, recent git commits, atlas owners, ticket history). Wait for
the user before continuing.

**Role.** Pick one: `junior | mid | senior | staff | pm`. Recommendation
heuristics:
- `git log --author=<email> --oneline | wc -l` < 50 → junior
- Heavy `atlas/keystones/` and `atlas/pillars/` edits → senior/staff
- Mostly cycle-management + project-state edits → pm

**Areas of expertise.** From: `backend | frontend | retrieval | platform |
ops | data-ingestion | search | chat | draft | agents | infrastructure |
design`. Multi-select. Recommend based on `git log --stat | rg <area>`
patterns.

**Atlas nodes owned.** Show `org atlas list --type capability`. Ask:
"Which of these are you the owner of (you make architectural calls,
respond to bugs)?" Multi-select.

**Atlas nodes you're learning.** Optional. The user may not want this
public — make the opt-in explicit. Ask: "Are there capabilities you'd
like the team to know you're growing into? (skip for none, this is opt-in)"

**Grill depth.** `shallow | medium | deep`.
- shallow → the grill walks only top-level decisions (1-2 questions)
- medium → walks every branching point (3-7 questions)
- deep → walks every branch + every counter-argument the user might face in
  review (8+ questions)

Recommend `deep` for junior, `medium` for mid/senior, `shallow` for staff
who'll catch their own gaps.

**Review style.** `terse | balanced | explanatory`.
- terse → just findings, no exposition
- balanced → findings + one-line reasoning
- explanatory → findings + reasoning + the standard cited

Recommend `explanatory` for junior, `balanced` for mid, `terse` for senior+.

**Handoff detail.** `low | medium | high`.
- low → ticket + commits + next-step bullet (under 200 words)
- medium → adds atlas refs + open questions
- high → full context dump, ~500-800 words

Recommend `medium` as the universal default; `high` only when working with
contractors or distributed teammates.

**Personal skills (opt-in).** Tools outside the shared baseline, installed only
for you (unioned onto `skills.global` on `org install --global`, resolved via
your `$LINEAR_HANDLE`). Today: `caveman` (token-compressed, terse replies;
`caveman-commit`, `caveman-review`, `compress` are its companions). Ask: "Want
caveman mode — terse, compressed responses? It's opt-in and you can turn it off
anytime (`stop caveman` in a session, or remove it here)." If yes, add the
chosen names to the top-level `skills:` list. Don't recommend by default — it's
a taste preference.

### 3. Present the YAML diff

Build the updated YAML in memory. Show the diff (added/removed/changed
lines) and ask:

> "Apply this to `platform/profiles/<short-handle>.yaml`? I'll write it but
> NOT commit — you review the git diff and commit yourself with `git add
> platform/profiles/<short-handle>.yaml && git commit -m 'profile:
> @<short-handle>'`."

If the user says yes, write the file. If no, end the session without
writing.

### 4. Suggest next steps

After write, suggest:

> "1. Commit the change.
>  2. Run `org user validate` — should be clean.
>  3. Run `org atlas drift --axis linear` — if you listed atlas nodes in
>     `owns:` that don't list you in their `owners:` (or vice versa),
>     the drift will surface it. Sync atlas if needed."

If you changed `skills:`, also suggest: "Run `org install --global` to install
your personal skills (needs `$LINEAR_HANDLE` set so it resolves your profile).
To remove one later, drop it from `skills:` and delete its dir under
`~/.<tool>/skills/<name>/`."

## What this skill does NOT do

- Auto-commit. Ever.
- Edit the private profile (`~/.egzakta/profile-local.yaml`) — that's
  yours alone; agents read it but don't write it.
- Add YOU to atlas `owners:` lists for nodes you said you own. The user
  edits atlas separately — keeps profile-side and atlas-side intent
  symmetric.
- Bootstrap from scratch. That's `org user init` (one-time, autofills the
  identity half). `profile-me` only edits an existing stub.

## References

- Bootstrap CLI: `org user init` (`docs/setup.md`)
- Profile schema: `org/src/egzakta_org/users/loader.py` (`UserProfile` dataclass)
- Where preferences are read: grill-with-docs SKILL.md (`GRILL_DEPTH`),
  handoff SKILL.md (`HANDOFF_DETAIL`), per-repo orchestrator agent (`REVIEW_STYLE`)
- Atlas owners convention: `atlas/ontology.md`
