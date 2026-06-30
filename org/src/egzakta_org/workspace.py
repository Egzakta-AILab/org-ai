"""Locate the workspace root (the directory that holds repos.yaml)."""

from __future__ import annotations

from pathlib import Path

MANIFEST_NAME = "repos.yaml"
IGNORE_NAME = ".org-ignore"


def find_workspace_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) until a directory containing repos.yaml is found.

    Raises FileNotFoundError if no manifest is found up to the filesystem root.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / MANIFEST_NAME).is_file():
            return candidate
    raise FileNotFoundError(
        f"No {MANIFEST_NAME} found in {current} or any parent. "
        "Run `org` from inside the egzakta workspace."
    )


def platform_dir(root: Path) -> Path:
    return root / "platform"


def load_ignore(root: Path) -> set[str]:
    """Read `.org-ignore` (one dir name per line, `#` comments allowed).

    The file marks sibling dirs as intentional personal clones (forks, references,
    scratch) so the manifest-vs-disk hygiene check stays quiet about them. Missing
    file is fine — returns an empty set.
    """
    path = root / IGNORE_NAME
    if not path.is_file():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        # Strip comments and surrounding whitespace; ignore blank lines.
        bare = line.split("#", 1)[0].strip()
        if bare:
            out.add(bare)
    return out
