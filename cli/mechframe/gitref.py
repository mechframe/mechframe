"""Reading the CLI's own checkout through Git, for `mechframe upgrade` and for
the commit `mechframe new` records (`dev plans/contracts/mechframe-upgrade.md`).

Every call is `git -C <checkout> ...` and only reads: no fetch, no checkout,
nothing written to the repository. A ref's files come from Git's objects, never
the working tree, so it reads `main` whatever branch the checkout is on.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath


class GitError(Exception):
    """Git couldn't answer: it isn't installed, this isn't a repository, or a ref is unknown."""


def _run(root: Path, *args: str, given: bytes | None = None) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise GitError("Git isn't installed, or isn't on the PATH.")
    done = (
        subprocess.run(  # noqa: S603 (Git itself, reading this checkout; refs never start with -)
            [git, "-C", str(root), *args],
            input=given,
            capture_output=True,
            check=False,
        )
    )
    if done.returncode != 0:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args[:2])} failed: {said or 'no reason given'}")
    return done.stdout


def is_repository(root: Path) -> bool:
    """Whether `root` is the top of a Git work tree."""
    try:
        top = _run(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    except GitError:
        return False
    return Path(top).resolve() == root.resolve()


def commit_of(root: Path, ref: str) -> str | None:
    """The commit `ref` names, in full, or None when there's no such commit."""
    if ref.startswith("-"):
        return None
    try:
        found = _run(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except GitError:
        return None
    return found.decode("utf-8").strip() or None


def history(root: Path, commit: str) -> list[str]:
    """Every commit `commit` reaches, newest first."""
    return _run(root, "rev-list", commit).decode("utf-8").split()


def files(root: Path, commit: str, paths: Iterable[str]) -> dict[str, str]:
    """Every file under `paths` at `commit`, by its path in the checkout, with its blob's id."""
    wanted = list(paths)
    if not wanted:
        return {}
    listed = _run(root, "ls-tree", "-r", "-z", "--full-tree", commit, "--", *wanted)
    found: dict[str, str] = {}
    for entry in listed.split(b"\0"):
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        _mode, kind, blob = meta.decode("ascii").split()
        if kind == "blob":
            found[name.decode("utf-8")] = blob
    return found


def objects(root: Path, specs: Iterable[str]) -> list[str | None]:
    """Each `<commit>:<path>`'s object id, or None where there's none, in one call."""
    asked = list(specs)
    if not asked:
        return []
    answer = _run(
        root, "cat-file", "--batch-check=%(objectname)", given="\n".join(asked).encode() + b"\n"
    )
    found: list[str | None] = []
    for line in answer.decode("utf-8").splitlines():
        found.append(
            None if line.endswith(" missing") or line.endswith(" ambiguous") else line.strip()
        )
    return found


def blobs(root: Path, ids: Iterable[str]) -> dict[str, bytes]:
    """Each blob's bytes, by its id, in one call."""
    asked = sorted(set(ids))
    if not asked:
        return {}
    answer = _run(root, "cat-file", "--batch", given="\n".join(asked).encode() + b"\n")
    found: dict[str, bytes] = {}
    at = 0
    for blob in asked:
        end = answer.index(b"\n", at)
        header = answer[at:end].decode("ascii").split()
        if len(header) != 3:
            raise GitError(f"git cat-file has no blob {blob}.")
        size = int(header[2])
        found[blob] = answer[end + 1 : end + 1 + size]
        at = end + 1 + size + 1  # the blob, then a newline
    return found


def clean(root: Path, paths: Iterable[str], skip: Callable[[PurePosixPath], bool]) -> bool:
    """Whether every file under `paths` is as `HEAD` has it: nothing changed,
    added, or ignored but there, except what `skip` says a copy leaves behind."""
    try:
        said = _run(
            root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--ignored",
            "--",
            *paths,
        )
    except GitError:
        return False
    for entry in said.split(b"\0"):
        if len(entry) < 4:
            continue
        if not skip(PurePosixPath(entry[3:].decode("utf-8").rstrip("/"))):
            return False
    return True
