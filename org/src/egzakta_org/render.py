"""Render tool-agnostic platform sources into per-tool files.

A source carries a superset frontmatter plus a body with {{TOKEN}} placeholders. The
profile supplies the per-tool deltas. With repo_relative_paths=true the token {{R}}
renders to "" and the Claude output reproduces the original hand-written file (plus a
generated-by marker).

Agent bodies may also reference shared scaffolding via {{INCLUDE:<name>}} — the
contents of `partials_root/<name>.md` are spliced in BEFORE token substitution so
tokens inside partials still resolve.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .profiles import Profile

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_INCLUDE_RE = re.compile(r"\{\{INCLUDE:([a-z][a-z0-9_-]*)\}\}")
_MAX_INCLUDE_DEPTH = 10

# Per-tool conditional blocks: `<!-- tool:droid,cursor -->…<!-- /tool -->`. Content
# survives only when the active tool is in the comma list; otherwise the whole block
# (fences + body) is dropped. Lets one shared source carry tool-specific sections —
# e.g. a Droid-only "Task tool" path in a vendor skill that Claude/Cursor never see.
_TOOL_BLOCK_RE = re.compile(
    r"[ \t]*<!--[ \t]*tool:([A-Za-z0-9_, \t-]+?)[ \t]*-->[ \t]*\n?(.*?)\n?[ \t]*<!--[ \t]*/tool[ \t]*-->[ \t]*\n?",
    re.DOTALL,
)


def render_tool_blocks(text: str, tool: str) -> str:
    """Resolve `<!-- tool:a,b -->…<!-- /tool -->` fences for `tool`.

    Keep the inner body (fences removed) when `tool` is listed; drop the whole
    block otherwise. Unfenced text passes through untouched. Tool names are matched
    case-insensitively after trimming whitespace.
    """

    def _replace(match: re.Match[str]) -> str:
        tools = {t.strip().lower() for t in match.group(1).split(",") if t.strip()}
        return match.group(2) + "\n" if tool.lower() in tools else ""

    return _TOOL_BLOCK_RE.sub(_replace, text)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("source is missing YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2)


def expand_includes(text: str, partials_root: Path, _depth: int = 0) -> str:
    """Resolve `{{INCLUDE:<name>}}` → contents of `partials_root/<name>.md`.

    Recursive — a partial may include another partial — with a hard depth cap so a
    cyclic include errors loudly instead of looping. The substitution runs BEFORE
    `_substitute` so tokens like `{{R}}` or `{{NAME}}` inside partials still resolve
    against the calling agent's profile and frontmatter.
    """
    if _depth > _MAX_INCLUDE_DEPTH:
        raise ValueError(
            f"include depth exceeded {_MAX_INCLUDE_DEPTH} — likely a cyclic "
            f"{{{{INCLUDE:…}}}} chain in {partials_root}"
        )

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        path = partials_root / f"{name}.md"
        if not path.is_file():
            raise ValueError(
                f"partial not found: {path} (referenced as {{{{INCLUDE:{name}}}}})"
            )
        return expand_includes(path.read_text(encoding="utf-8"), partials_root, _depth + 1)

    return _INCLUDE_RE.sub(_replace, text)


def _substitute(text: str, profile: Profile, repo_name: str, name: str = "") -> str:
    # Inject the multi-line dispatch first; its value may itself contain {{R}} etc.
    text = text.replace("{{SUBAGENT_DISPATCH}}", profile.tokens.get("SUBAGENT_DISPATCH", ""))
    replacements = {
        "{{R}}": profile.repo_prefix(repo_name),
        "{{INSTRUCTIONS_FILE}}": profile.instructions_file,
        "{{REVIEW_ENTRYPOINT}}": profile.tokens.get("REVIEW_ENTRYPOINT", ""),
        "{{NAME}}": name,
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _build_frontmatter(fm: dict, profile: Profile) -> list[str]:
    lines: list[str] = []
    name = fm.get("name", "")
    for key in profile.frontmatter.emit:
        if key == "description":
            desc = fm.get("description", "")
            if profile.frontmatter.description_style == "folded":
                lines.append("description: >")
                lines.append(f"  {desc}")
                if profile.frontmatter.description_suffix:
                    lines.append(f"  {profile.frontmatter.description_suffix.format(name=name)}")
            else:
                lines.append(f"description: {desc}")
        elif key == "readonly":
            if "readonly" in fm:
                lines.append(f"readonly: {'true' if fm['readonly'] else 'false'}")
        elif key in fm:
            lines.append(f"{key}: {fm[key]}")
    return lines


def render_agent(
    source_text: str,
    source_rel: str,
    profile: Profile,
    repo_name: str,
    partials_root: Path | None = None,
) -> str:
    fm, body = parse_frontmatter(source_text)
    if partials_root is not None and partials_root.is_dir():
        body = expand_includes(body, partials_root)
    body = _substitute(body, profile, repo_name, name=fm.get("name", ""))
    marker = f"# Generated by `org install` from {source_rel} — edit the source, not this file."
    fm_block = "\n".join([marker, *_build_frontmatter(fm, profile)])
    return f"---\n{fm_block}\n---\n{body}"


def render_standards(source_text: str, source_rel: str, profile: Profile, repo_name: str) -> str:
    body = _substitute(source_text, profile, repo_name)
    marker = f"<!-- Generated by `org install` from {source_rel} — edit the source, not this file. -->\n"
    return marker + body


def render_command(target_agent: str, source_rel: str, profile: Profile) -> str:
    """Render a slash-command wrapper pointing at the named agent for this tool.

    Each wrapper is a one-line pointer; the source is either the agent itself (1:1)
    or an entry in aliases.yaml (the review-2axis → orchestrator alias pattern).
    The pointer uses the active tool's agents dir — Claude `.claude/agents/`,
    Cursor `.cursor/agents/`, Factory `.factory/droids/`. All three accept plain
    Markdown command files; the same pointer body works for all three.
    """
    marker = f"<!-- Generated by `org install` from {source_rel} — edit the source, not this file. -->\n"
    return marker + f"Read and follow the agent instructions in {profile.agents_dir}/{target_agent}.md\n"


def render_command_override(source_text: str, source_rel: str, profile: Profile, repo_name: str) -> str:
    """Render an authored slash-command file as the per-tool destination content.

    Override files at `platform/commands/<repo>/<name>.md` win over both 1:1 wrappers
    and aliases — explicit author intent over derived output. The body supports the
    same {{R}} / {{INSTRUCTIONS_FILE}} / {{REVIEW_ENTRYPOINT}} substitutions as agents
    so the same source can target multiple tools.

    Per-tool quirks:
      * Claude — keep YAML frontmatter, inject the marker as a YAML comment inside
        the `---` block (so the parser keeps reading `description`, `argument-hint`,
        `allowed-tools`, `model`, …). Body uses `$ARGUMENTS` for positional input.
      * Factory droid — same as Claude (Claude-compatible frontmatter + $ARGUMENTS).
      * Cursor — plain Markdown, NO frontmatter (Cursor renders YAML as literal
        text). Strip the frontmatter; body uses `$1`/`$2`/… for args so the
        renderer translates `$ARGUMENTS` → `$1`. HTML comment marker before the body.
    """
    marker_yaml = f"# Generated by `org install` from {source_rel} — edit the source, not this file."
    marker_html = f"<!-- Generated by `org install` from {source_rel} — edit the source, not this file. -->"
    m = _FRONTMATTER_RE.match(source_text)
    if m:
        frontmatter_text = m.group(1)
        raw_body = m.group(2)
    else:
        frontmatter_text = ""
        raw_body = source_text

    if profile.tool == "cursor":
        body = _substitute(raw_body, profile, repo_name).replace("$ARGUMENTS", "$1")
        return f"{marker_html}\n{body}"

    body = _substitute(raw_body, profile, repo_name)
    if frontmatter_text:
        return f"---\n{marker_yaml}\n{frontmatter_text}\n---\n{body}"
    return f"{marker_html}\n{body}"


def render_rule(source_text: str, source_rel: str, profile: Profile, repo_name: str) -> str:
    """Render a code-convention rule for the active tool.

    Source format is Cursor `.mdc` (the original): YAML frontmatter with
    `description` / `globs` / `alwaysApply`, then a markdown body. We translate
    per tool:

    * Cursor — preserve the frontmatter byte-for-byte (it IS the rule config),
      only prepending the generated-by marker as a YAML comment.
    * Claude — rewrite into the `.claude/rules/` shape: keep `description`,
      translate `globs:` → `paths:`, drop `alwaysApply` (Claude has no equivalent;
      `alwaysApply: true` is expressed by omitting `paths:` so the rule applies
      to every file). Extension changes .mdc → .md (handled by install pipeline).
    * Factory droid — plain Markdown, NO YAML frontmatter (droid doesn't parse it).
      Strip the frontmatter. `description` becomes an H1 header; `globs` surfaces
      as a body `**Applies to**: <globs>` line so the scope info survives. Extension
      is .md (handled by install pipeline).

    Body tokens (`{{R}}` etc.) substitute on all branches.
    """
    m = _FRONTMATTER_RE.match(source_text)
    if not m:
        raise ValueError(f"rule source {source_rel} is missing YAML frontmatter")
    frontmatter_text = m.group(1)
    body = _substitute(m.group(2), profile, repo_name)
    marker = f"# Generated by `org install` from {source_rel} — edit the source, not this file."

    if profile.tool == "cursor":
        return f"---\n{marker}\n{frontmatter_text}\n---\n{body}"

    if profile.tool == "droid":
        # Droid: strip frontmatter, surface rule metadata as plain body header.
        fm = yaml.safe_load(frontmatter_text) or {}
        marker_html = f"<!-- Generated by `org install` from {source_rel} — edit the source, not this file. -->"
        header: list[str] = [marker_html, ""]
        if fm.get("description"):
            header.append(f"# {fm['description']}")
        if fm.get("alwaysApply"):
            header.append("**Applies to**: all files")
        elif fm.get("globs"):
            header.append(f"**Applies to**: `{fm['globs']}`")
        if len(header) > 2:  # we added something beyond marker + blank
            header.append("")
        return "\n".join(header) + body

    # Claude branch — translate the Cursor frontmatter into Claude's shape.
    fm = yaml.safe_load(frontmatter_text) or {}
    lines: list[str] = [marker]
    if fm.get("description"):
        lines.append(f"description: {fm['description']}")
    # Cursor `alwaysApply: true` means "load this rule for every file" — in Claude
    # that's expressed by omitting `paths:` entirely. So we only emit `paths:` when
    # the rule is NOT alwaysApply and globs are present.
    if not fm.get("alwaysApply") and fm.get("globs"):
        lines.append(f"paths: {fm['globs']}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body
