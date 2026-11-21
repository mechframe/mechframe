"""`mechframe upgrade kernel`: a site takes the kernel's changes from a Git ref
of this checkout (`dev plans/contracts/mechframe-upgrade.md`; decision 0053).

Every file is compared three ways: L, what the site was given (the lock's hash
for the kernel's files, the base commit's copy for the template's); S, the
site's file now; and N, the new copy from `--from`'s commit.

| Case | Does |
| --- | --- |
| S = L, N differs | writes N |
| S differs, N = L | keeps the site's |
| S = N | writes nothing; the lock takes N |
| all three differ | a conflict |
| new in N, nothing there / the site's own file there | writes it / a conflict |
| gone from N, S = L / S differs | deletes it / a conflict |
| missing from the site, N = L / N differs | stays missing / a conflict |

It runs whole or not at all. With any conflict, nothing in the site changes
but `.mechframe/upgrade/`: a diff per conflict, the base to N, for an agent to
apply to the site's file, and `README.txt`. `--merged <path>` keeps the site's
file once it's merged, and the lock takes N's hash.

The base is the lock's `kernel.commit`. An older lock has none, so its base
is found among `--from`'s commits by the lock's hashes, and refused when those
that match differ in the template's files; `--base` names one instead.

The template's files (`templates/site/` with the site's name and theme written
in, the pins, the theme's `tokens.css`) follow the same rule, except the
site's own: `backend/app/site/`, `web/src/site/`, the two registries,
`.env.example` and `.railway/railway.ts`. The template's new settings are
printed instead. A run holds the site by `.mechframe-busy`, as `add` does.
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from mechframe import __version__, gitref, layout, lock, modules, new, registries, settings
from mechframe.hashes import digest, digest_bytes
from mechframe.source import ROOT

PATCHES = ".mechframe/upgrade"
#: Where the template's files are the site's own from the day it's made.
OWN_FOLDERS = ("backend/app/site/", "web/src/site/")
OWN_FILES = frozenset({registries.PYTHON, registries.WEB, settings.ENV, settings.RAILWAY})
TOKENS = "web/src/theme/tokens.css"
KERNEL_MANIFEST = "backend/kernel/kernel.json"
#: The kinds of verdict that change a file in the site.
WRITES = ("add", "write", "delete")
_SETTING = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)


class Refused(Exception):
    """`upgrade` won't run; the message says why. Nothing was written."""


@dataclass(frozen=True)
class Entry:
    """One file of the site, three ways: each as its hash and its bytes, or None where there's none."""

    path: str
    kernel: bool
    base: str | None
    base_data: bytes | None
    new: str | None
    new_data: bytes | None
    site: str | None


@dataclass(frozen=True)
class Verdict:
    path: str
    kind: str
    why: str = ""


@dataclass
class Outcome:
    site: Path
    ref: str
    base: str
    new: str
    from_version: str
    to_version: str
    how: str
    verdicts: list[Verdict] = field(default_factory=list)
    dry_run: bool = False
    wrote: bool = False
    #: the template's files left alone because the site's name isn't known
    unread: list[str] = field(default_factory=list)
    settings: list[str] = field(default_factory=list)
    base_given: str | None = None

    @property
    def conflicts(self) -> list[Verdict]:
        return [each for each in self.verdicts if each.kind == "conflict"]

    def count(self, kind: str) -> int:
        return sum(1 for each in self.verdicts if each.kind == kind)

    @property
    def exit_code(self) -> int:
        return 1 if self.conflicts else 0


class _Reader:
    """A checkout's blobs, read once each."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._data: dict[str, bytes] = {}
        self._hash: dict[str, str] = {}

    def load(self, ids: Iterable[str]) -> None:
        wanted = [each for each in set(ids) if each not in self._data]
        self._data.update(gitref.blobs(self.root, wanted))

    def data(self, blob: str) -> bytes:
        if blob not in self._data:
            self.load([blob])
        return self._data[blob]

    def hash(self, blob: str) -> str:
        if blob not in self._hash:
            self._hash[blob] = digest_bytes(self.data(blob))
        return self._hash[blob]


def kernel_blobs(root: Path, commit: str) -> dict[str, str]:
    """The kernel's files a site gets at `commit`, by their paths in the site, with their blobs."""
    copies = layout.kernel_copies()
    listed = gitref.files(root, commit, [each.source for each in copies])
    found: dict[str, str] = {}
    for path, blob in listed.items():
        for each in copies:
            if not each.folder and path == each.source:
                found[each.target] = blob
                break
            if each.folder and path.startswith(each.source + "/"):
                relative = PurePosixPath(path[len(each.source) + 1 :])
                if not layout.left_out(relative):
                    found[f"{each.target}/{relative}"] = blob
                break
    return found


def own(relative: str) -> bool:
    """Whether a template file is the site's own from the day it's made."""
    return relative.startswith(OWN_FOLDERS) or relative in OWN_FILES


def template_blobs(root: Path, commit: str, theme: str) -> dict[str, str]:
    """The template's files a site gets at `commit` (its own left out), by their paths in the site."""
    tokens = f"themes/{theme}/tokens.css"
    listed = gitref.files(root, commit, [new.TEMPLATE, *new.REQUIREMENTS, tokens])
    found: dict[str, str] = {}
    for path, blob in listed.items():
        if path.startswith(new.TEMPLATE + "/"):
            relative = path[len(new.TEMPLATE) + 1 :]
            folders = PurePosixPath(relative).parts[:-1]
            if any(part in new.LEFT_OUT for part in folders) or own(relative):
                continue
            found[relative] = blob
        elif path in new.REQUIREMENTS:
            found[path] = blob
        elif path == tokens:
            found[TOKENS] = blob
    return found


def site_name(site: Path) -> str | None:
    """The site's name as `new` wrote it in `.env.example`'s `SITE_NAME`; None when it isn't there."""
    path = site / settings.ENV
    if not path.is_file():
        return None
    found = re.search(r"^SITE_NAME=(.*)$", path.read_text("utf-8"), re.MULTILINE)
    if found is None:
        return None
    value = found.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return re.sub(r"\\(.)", r"\1", value[1:-1])
    return value or None


def _settings(data: bytes | None) -> set[str]:
    return set(_SETTING.findall(data.decode("utf-8", "replace"))) if data else set()


@contextmanager
def _busy(site: Path) -> Iterator[None]:
    claim = site / modules.BUSY
    try:
        claim.open("x").close()
    except FileExistsError:
        raise Refused(
            f"Another mechframe add, remove or upgrade is writing to {site}. If none is, "
            f"one stopped half-way: delete {modules.BUSY} there and run it again."
        ) from None
    try:
        yield
    finally:
        claim.unlink(missing_ok=True)


def _matches(reader: _Reader, blobs: dict[str, str], files: dict[str, str]) -> bool:
    if set(blobs) != set(files):
        return False
    reader.load(blobs.values())
    return all(reader.hash(blobs[path]) == files[path] for path in files)


def _found_base(reader: _Reader, files: dict[str, str], tip: str, ref: str, theme: str) -> str:
    """An older lock's base: the commit on `tip`'s history whose kernel is the
    lock's, when every such commit holds the same template, pins and tokens."""
    root = reader.root
    commits = gitref.history(root, tip)
    trees = gitref.objects(root, [f"{commit}:kernel" for commit in commits])
    by_tree: dict[str, list[str]] = {}
    for commit, tree in zip(commits, trees, strict=True):
        if tree is not None:
            by_tree.setdefault(tree, []).append(commit)
    holding = {
        commit
        for group in by_tree.values()
        if _matches(reader, kernel_blobs(root, group[0]), files)
        for commit in group
    }
    candidates = [commit for commit in commits if commit in holding]
    if not candidates:
        raise Refused(
            f"The lock has no kernel.commit, and no commit on {ref} holds the kernel it records: "
            "the site was made from files Git doesn't have. Name the MechFrame commit it was made "
            "from with --base <commit>."
        )
    inputs = [new.TEMPLATE, *new.REQUIREMENTS, f"themes/{theme}/tokens.css"]
    ids = gitref.objects(root, [f"{commit}:{path}" for commit in candidates for path in inputs])
    held = {tuple(ids[at : at + len(inputs)]) for at in range(0, len(ids), len(inputs))}
    if len(held) > 1:
        raise Refused(
            f"The lock has no kernel.commit, and the {len(candidates)} commits that hold its kernel, "
            f"{candidates[-1][:7]} to {candidates[0][:7]}, differ in the template's files, pins or "
            "tokens.css, so the lock can't say which one the site was made from. Name it with "
            "--base <commit>: the MechFrame commit the site was made from (`git log` in this "
            "checkout, around the day it was made)."
        )
    return candidates[0]


def _base(
    reader: _Reader, data: dict[str, Any], given: str | None, tip: str, ref: str, theme: str
) -> tuple[str, str]:
    """The commit the site's copy came from, and how it was known."""
    root = reader.root
    files: dict[str, str] = data["kernel"]["files"]
    if given is not None:
        commit = gitref.commit_of(root, given)
        if commit is None:
            raise Refused(f"--base {given} isn't a commit in {root}.")
        if not _matches(reader, kernel_blobs(root, commit), files):
            raise Refused(
                f"--base {given} doesn't hold the kernel the lock records: name the commit the "
                "site was made from."
            )
        return commit, "--base"
    recorded = data["kernel"].get("commit")
    if recorded:
        commit = gitref.commit_of(root, recorded)
        if commit is None:
            raise Refused(
                f"The lock's kernel.commit {recorded[:7]} isn't in {root}: fetch it there, or "
                "name the site's base with --base <commit>."
            )
        return commit, "the lock"
    return _found_base(reader, files, tip, ref, theme), "found by the lock's hashes"


def _entries(
    reader: _Reader,
    site: Path,
    data: dict[str, Any],
    base: str,
    tip: str,
    name: str | None,
    unread: list[str],
) -> list[Entry]:
    root = reader.root
    theme: str = data["theme"]
    entries: list[Entry] = []
    recorded: dict[str, str] = data["kernel"]["files"]
    old, now = kernel_blobs(root, base), kernel_blobs(root, tip)
    reader.load([*old.values(), *now.values()])
    for path in sorted(set(recorded) | set(now)):
        here = site / path
        entries.append(
            Entry(
                path=path,
                kernel=True,
                base=recorded.get(path),
                base_data=reader.data(old[path]) if path in old else None,
                new=reader.hash(now[path]) if path in now else None,
                new_data=reader.data(now[path]) if path in now else None,
                site=digest(here) if here.is_file() else None,
            )
        )
    old, now = template_blobs(root, base, theme), template_blobs(root, tip, theme)
    reader.load([*old.values(), *now.values()])
    for path in sorted(set(old) | set(now)):
        raw = [reader.data(found[path]) if path in found else None for found in (old, now)]
        if name is None and any(
            each is not None and new.NAME_MARK.encode() in each for each in raw
        ):
            unread.append(path)
            continue
        given, coming = (
            None if each is None else new.written_in(each, path, name or "", theme) for each in raw
        )
        here = site / path
        entries.append(
            Entry(
                path=path,
                kernel=False,
                base=None if given is None else digest_bytes(given),
                base_data=given,
                new=None if coming is None else digest_bytes(coming),
                new_data=coming,
                site=digest(here) if here.is_file() else None,
            )
        )
    return entries


def judge(entry: Entry) -> Verdict:
    """The table's verdict for one file (the module's docstring)."""
    was, now, here = entry.base, entry.new, entry.site
    if was is None and now is None:
        return Verdict(entry.path, "unchanged")
    if was is None:
        if here is None:
            return Verdict(entry.path, "add")
        if here == now:
            return Verdict(entry.path, "same")
        return Verdict(
            entry.path, "conflict", "new in the kernel, and the site has a file of its own there"
        )
    if now is None:
        if here is None:
            return Verdict(entry.path, "dropped")
        if here == was:
            return Verdict(entry.path, "delete")
        return Verdict(entry.path, "conflict", "gone from the new kernel, and the site edited it")
    if here is None:
        if now == was:
            return Verdict(entry.path, "missing")
        return Verdict(
            entry.path, "conflict", "missing from the site, and the new kernel changed it"
        )
    if here == now:
        return Verdict(entry.path, "unchanged" if was == now else "same")
    if here == was:
        return Verdict(entry.path, "write")
    if now == was:
        return Verdict(entry.path, "keep")
    return Verdict(entry.path, "conflict", "changed on both sides")


def _patch(entry: Entry, base: str, tip: str) -> bytes:
    """The new kernel's change to the file since the site's copy, as a unified diff."""
    try:
        before = (entry.base_data or b"").replace(b"\r\n", b"\n").decode("utf-8")
        after = (entry.new_data or b"").replace(b"\r\n", b"\n").decode("utf-8")
    except UnicodeDecodeError:
        return (
            f"# {entry.path} isn't text: compare the site's file with {tip[:7]}'s by hand.\n"
        ).encode()
    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{entry.path}" if entry.base_data is not None else "/dev/null",
        tofile=f"b/{entry.path}" if entry.new_data is not None else "/dev/null",
    )
    head = f"# {entry.path}: the kernel's change from {base[:7]} (the site's copy) to {tip[:7]}.\n"
    return (head + "".join(lines)).encode("utf-8")


def _command(outcome: Outcome, merged: Iterable[str]) -> str:
    parts = ["python -m mechframe upgrade kernel", f'--site "{outcome.site}"']
    if outcome.ref != "main":
        parts.append(f"--from {outcome.ref}")
    if outcome.base_given is not None:
        parts.append(f"--base {outcome.base_given}")
    parts += [f"--merged {path}" for path in merged]
    return " ".join(parts)


def _write_patches(
    site: Path, outcome: Outcome, entries: dict[str, Entry], merged: list[str]
) -> None:
    folder = site / PATCHES
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for each in outcome.conflicts:
        target = folder / f"{each.path}.patch"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_patch(entries[each.path], outcome.base, outcome.new))
    paths = [*merged, *(each.path for each in outcome.conflicts)]
    listed = "\n".join(f"  {each.path}: {each.why}" for each in outcome.conflicts)
    text = (
        f"mechframe upgrade kernel stopped: {len(outcome.conflicts)} files changed on both sides "
        f"since the site's copy (base {outcome.base[:7]}, {outcome.how}) and the kernel at "
        f"{outcome.new[:7]} ({outcome.ref}). Nothing else in the site was written.\n\n"
        "Each .patch here is the kernel's change to that file since the site's copy. Apply it to "
        "the site's file by hand, keeping the site's own change, then run it again from "
        "MechFrame's checkout, naming every file you merged:\n\n"
        f"  {_command(outcome, paths)}\n\n"
        f"The files:\n{listed}\n\n"
        "This folder goes once the upgrade runs through.\n"
    )
    (folder / "README.txt").write_text(text, encoding="utf-8", newline="\n")


def _clear_patches(site: Path) -> None:
    shutil.rmtree(site / PATCHES, ignore_errors=True)
    with suppress(OSError):
        (site / PATCHES).parent.rmdir()  # .mechframe/, when nothing else is in it


def _normal(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix().removeprefix("./")


def run(
    site: Path,
    *,
    root: Path = ROOT,
    ref: str = "main",
    base: str | None = None,
    merged: Sequence[str] = (),
    dry_run: bool = False,
) -> Outcome:
    """Upgrade the site's kernel to `ref`'s. Raises Refused before writing anything."""
    if not gitref.is_repository(root):
        raise Refused(
            f"{root} isn't a Git checkout: mechframe upgrade reads the kernel from Git. "
            "Run it from a clone of MechFrame."
        )
    if not site.is_dir():
        raise Refused(f"{site} isn't a folder: is this a MechFrame site?")
    try:
        data = lock.read(site, root)
    except lock.LockError as error:
        raise Refused("; ".join(error.problems)) from None
    with _busy(site):
        return _run(site, data, root, ref, base, [_normal(each) for each in merged], dry_run)


def _run(
    site: Path,
    data: dict[str, Any],
    root: Path,
    ref: str,
    given: str | None,
    merged: list[str],
    dry_run: bool,
) -> Outcome:
    tip = gitref.commit_of(root, ref)
    if tip is None:
        raise Refused(
            f"There's no commit {ref} in {root}: name a branch, tag or commit with --from."
        )
    reader = _Reader(root)
    theme: str = data["theme"]
    if gitref.objects(root, [f"{tip}:themes/{theme}/tokens.css"]) == [None]:
        raise Refused(f"{ref} has no theme {theme}, the one this site uses.")
    base, how = _base(reader, data, given, tip, ref, theme)
    now = kernel_blobs(root, tip)
    if KERNEL_MANIFEST not in now:
        raise Refused(f"{ref} has no kernel/kernel.json.")
    manifest = json.loads(reader.data(now[KERNEL_MANIFEST]))
    unread: list[str] = []
    entries = _entries(reader, site, data, base, tip, site_name(site), unread)
    by_path = {each.path: each for each in entries}
    verdicts = [judge(each) for each in entries]
    conflicted = {each.path for each in verdicts if each.kind == "conflict"}
    stray = [path for path in merged if path not in conflicted]
    if stray:
        raise Refused(
            f"--merged {', '.join(stray)}: not a file both sides changed in this upgrade, so "
            "there's nothing to merge. Name only the files it listed."
        )
    verdicts = [Verdict(each.path, "merged") if each.path in merged else each for each in verdicts]
    env = [
        gitref.objects(root, [f"{commit}:{new.TEMPLATE}/{settings.ENV}"])[0]
        for commit in (base, tip)
    ]
    site_env = site / settings.ENV
    fresh = (
        _settings(reader.data(env[1]) if env[1] else None)
        - _settings(reader.data(env[0]) if env[0] else None)
        - _settings(site_env.read_bytes() if site_env.is_file() else None)
    )
    outcome = Outcome(
        site=site,
        ref=ref,
        base=base,
        new=tip,
        from_version=data["kernel"]["version"],
        to_version=manifest["version"],
        how=how,
        verdicts=verdicts,
        dry_run=dry_run,
        unread=unread,
        settings=sorted(fresh),
        base_given=given,
    )
    if dry_run:
        return outcome
    if outcome.conflicts:
        _write_patches(site, outcome, by_path, merged)
        return outcome
    updated = {
        **data,
        "mechframe": __version__,
        "spec": manifest["spec"],
        "kernel": {
            "version": manifest["version"],
            "files": {path: reader.hash(blob) for path, blob in now.items()},
            "commit": tip,
        },
    }
    changes = [each for each in verdicts if each.kind in WRITES]
    if not changes and lock.text(updated, root) == lock.text(data, root):
        _clear_patches(site)
        return outcome
    journal = modules.Journal()
    try:
        for each in changes:
            target = site / each.path
            if each.kind == "delete":
                journal.delete(target)
            else:
                written = by_path[each.path].new_data
                if written is None:  # never: an add or a write has a new copy
                    raise RuntimeError(f"{each.path} has no new copy to write.")
                journal.write(target, written)
        journal.write(site / lock.NAME, lock.text(updated, root).encode("utf-8"))
    except BaseException:
        journal.undo()
        raise
    outcome.wrote = True
    _clear_patches(site)
    return outcome


def _verdict_line(each: Verdict) -> str:
    line = f"{each.kind:<7} {each.path}"
    return f"{line} ({each.why})" if each.why else line


def _next_steps(outcome: Outcome) -> list[str]:
    written = {each.path for each in outcome.verdicts if each.kind in ("add", "write")}
    steps = ["", "Next, in the site's folder:"]
    if written & set(new.REQUIREMENTS):
        steps.append(
            "  .venv/Scripts/python.exe -m pip install --require-hashes "
            "-r requirements.txt -r requirements-dev.txt"
        )
    if written & {"web/package.json", "web/package-lock.json"}:
        steps.append("  cd web; npm ci; cd ..")
    return [
        *steps,
        '  $env:PYTHONPATH = "backend"',
        "  .venv/Scripts/python.exe -m app.migrations upgrade",
        "  .venv/Scripts/python.exe -m pytest backend/tests",
        f'  and from MechFrame\'s checkout: python -m mechframe check --site "{outcome.site}"',
    ]


def lines(outcome: Outcome) -> list[str]:
    """What the run did, or would do, and what's next."""
    shown = [each for each in outcome.verdicts if each.kind not in ("unchanged", "dropped")]
    span = (
        f"the kernel {outcome.from_version} (base {outcome.base[:7]}, {outcome.how}) to "
        f"{outcome.to_version} ({outcome.new[:7]}, {outcome.ref})"
    )
    found: list[str] = []
    if outcome.dry_run:
        found.append(f"Would upgrade {span}; nothing was written:")
        found += [f"  {_verdict_line(each)}" for each in shown] or ["  nothing to change"]
    elif outcome.conflicts:
        found += [
            f"Stopped: {len(outcome.conflicts)} files changed on both sides, so nothing was "
            f"written but the diffs in {PATCHES}/ (its README.txt says how to merge them):",
            *(f"  {_verdict_line(each)}" for each in outcome.conflicts),
            "Merge each into the site's file, then run it again with --merged <path> for "
            "every one you merged.",
        ]
    elif not outcome.wrote:
        found.append(
            f"The site's kernel is already {outcome.ref}'s ({outcome.new[:7]}): nothing to write."
        )
    else:
        found.append(
            f"Upgraded {span}: {outcome.count('add')} added, {outcome.count('write')} written, "
            f"{outcome.count('delete')} deleted; {outcome.count('keep')} kept as the site's edits, "
            f"{outcome.count('merged')} merged."
        )
    if outcome.unread:
        found.append(
            "Not compared, since .env.example has no SITE_NAME to write in: "
            + ", ".join(outcome.unread)
            + ". Each is kept as it is."
        )
    if outcome.settings:
        found.append(
            "New settings in the template, to add to .env.example and to .railway/railway.ts "
            "(as preserve()): " + ", ".join(outcome.settings)
        )
    if outcome.wrote:
        found += _next_steps(outcome)
    return found
