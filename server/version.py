"""T145: which git commit this code is, so a deployment can be checked for being up to date.

Read straight from the repository's .git (no git binary needed: the Docker deploy bind-mounts the repo, T14).
`commit()` is the checkout now (what web/ serves after a `git pull`); `STARTED` is the commit this API process was
started with (the server's Python code only changes on a restart).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SHA = re.compile(r"[0-9a-f]{40}")


def commit(repo: Path = REPO) -> str | None:
    """The full hash of the checked-out commit, or None when it can't be read."""
    try:
        git = repo / ".git"
        if git.is_file():                                   # a worktree: "gitdir: <path>"
            line = git.read_text(encoding="utf-8").strip()
            if not line.startswith("gitdir:"):
                return None
            git = (repo / line.split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if _SHA.fullmatch(head):                            # detached HEAD
            return head
        if not head.startswith("ref:"):
            return None
        ref = head.split(":", 1)[1].strip()
        common = git
        if (git / "commondir").is_file():
            common = (git / (git / "commondir").read_text(encoding="utf-8").strip()).resolve()
        bases = list(dict.fromkeys((git, common)))
        for base in bases:
            loose = base / ref
            if loose.is_file():
                sha = loose.read_text(encoding="utf-8").strip()
                return sha if _SHA.fullmatch(sha) else None
        for base in bases:
            packed = base / "packed-refs"
            if packed.is_file():
                for row in packed.read_text(encoding="utf-8").splitlines():
                    parts = row.split()
                    if len(parts) == 2 and parts[1] == ref and _SHA.fullmatch(parts[0]):
                        return parts[0]
    except (OSError, UnicodeDecodeError):
        return None
    return None


STARTED = commit()
