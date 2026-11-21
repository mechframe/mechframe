"""`mechframe upgrade kernel` (`dev plans/contracts/mechframe-upgrade.md`): a
site takes the kernel's changes from a Git ref of the CLI's checkout, each
file compared three ways (the lock, the site, the new copy), whole or not at
all, with diffs for an agent where both sides changed.

Each test makes a throwaway Git checkout from `site_maker`, a site from its
first commit, then a second commit to upgrade to."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mechframe import check, lock
from mechframe.__main__ import main
from mechframe.hashes import digest

from .conftest import tree, write

KERNEL_FILE = "kernel/backend/kernel/auth/sessions.py"
SITE_KERNEL_FILE = "backend/kernel/auth/sessions.py"
PATCHES = ".mechframe/upgrade"


GIT = shutil.which("git") or "git"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 (Git itself, on the test's own throwaway repository)
        [GIT, "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return done.stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(site_maker: Path) -> Path:
    """`site_maker` as a Git checkout on `main`, with one commit."""
    git(site_maker, "init", "-q", "-b", "main")
    git(site_maker, "config", "core.autocrlf", "false")
    commit(site_maker, "first")
    return site_maker


def make_site(repo: Path, folder: Path, *extra: str) -> Path:
    assert main(["new", str(folder), "--root", str(repo), *extra]) == 0
    return folder


@pytest.fixture
def site(repo: Path, tmp_path: Path) -> Path:
    return make_site(repo, tmp_path / "made")


def upgrade(repo: Path, site: Path, *extra: str) -> int:
    return main(["upgrade", "kernel", "--site", str(site), "--root", str(repo), *extra])


def kernel_lock(site: Path, repo: Path) -> dict[str, str]:
    files: dict[str, str] = lock.read(site, root=repo)["kernel"]["files"]
    return files


def edit(path: Path, text: str) -> None:
    write(path, text)


# --- new records where its copy came from ------------------------------------------------


def test_new_records_the_commit_its_copy_came_from(repo: Path, site: Path) -> None:
    assert lock.read(site, root=repo)["kernel"]["commit"] == git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "changed",
    [
        KERNEL_FILE,
        "templates/site/README.md",
        "requirements.txt",
        "themes/machined-light/tokens.css",
    ],
)
def test_new_leaves_the_commit_out_when_a_copied_file_differs_from_head(
    repo: Path, tmp_path: Path, changed: str
) -> None:
    edit(repo / changed, "changed, not committed\n")
    made = make_site(repo, tmp_path / "dirty")
    assert "commit" not in lock.read(made, root=repo)["kernel"]


def test_new_leaves_the_commit_out_outside_a_git_checkout(site_maker: Path, tmp_path: Path) -> None:
    made = make_site(site_maker, tmp_path / "plain")
    assert "commit" not in lock.read(made, root=site_maker)["kernel"]


def test_a_lock_without_a_commit_still_validates(repo: Path, site: Path) -> None:
    data = lock.read(site, root=repo)
    del data["kernel"]["commit"]
    lock.write(site, data, root=repo)
    assert lock.read(site, root=repo)["kernel"].get("commit") is None


# --- the table: each file three ways -----------------------------------------------------


def test_a_file_the_site_left_alone_takes_the_new_copy(repo: Path, site: Path) -> None:
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    second = commit(repo, "second")
    assert upgrade(repo, site) == 0
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 2\n"
    data = lock.read(site, root=repo)
    assert data["kernel"]["commit"] == second
    assert data["kernel"]["files"][SITE_KERNEL_FILE] == digest(site / SITE_KERNEL_FILE)
    report = check.check(site, root=repo)
    assert (report.exit_code(), report.edited, report.missing, report.added) == (0, [], [], [])
    assert not (site / ".mechframe").exists()


def test_a_file_only_the_site_changed_stays_the_sites(repo: Path, site: Path) -> None:
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 'ours'\n")
    edit(repo / "kernel/web/index.ts", "export const changed = 1;\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 0
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 'ours'\n"
    assert check.check(site, root=repo).edited == [SITE_KERNEL_FILE]


def test_a_file_both_changed_the_same_way_is_left_and_recorded(repo: Path, site: Path) -> None:
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 2\n")
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 0
    assert kernel_lock(site, repo)[SITE_KERNEL_FILE] == digest(site / SITE_KERNEL_FILE)
    assert check.check(site, root=repo).edited == []


def test_a_file_both_changed_differently_stops_it_and_writes_a_diff(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 'ours'\n")
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    edit(repo / "kernel/web/index.ts", "export const changed = 1;\n")
    commit(repo, "second")
    before = tree(site)
    capsys.readouterr()
    assert upgrade(repo, site) == 1
    after = tree(site)
    patches = {path: data for path, data in after.items() if path.startswith(PATCHES + "/")}
    # Nothing in the site changed but the diffs: not even the file only the kernel changed.
    assert {path: data for path, data in after.items() if path not in patches} == before
    patch = patches[f"{PATCHES}/{SITE_KERNEL_FILE}.patch"].decode("utf-8")
    assert "-SESSIONS = 1" in patch
    assert "+SESSIONS = 2" in patch
    listed = patches[f"{PATCHES}/README.txt"].decode("utf-8")
    assert SITE_KERNEL_FILE in listed
    assert "--merged" in listed
    out = capsys.readouterr().out
    assert SITE_KERNEL_FILE in out
    assert "--merged" in out


def test_a_new_file_lands_where_the_site_has_none(repo: Path, site: Path) -> None:
    write(repo / "kernel/backend/kernel/added.py", "ADDED = 1\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 0
    assert (site / "backend/kernel/added.py").read_text("utf-8") == "ADDED = 1\n"
    assert "backend/kernel/added.py" in kernel_lock(site, repo)


def test_a_new_file_where_the_site_has_one_of_its_own_is_a_conflict(repo: Path, site: Path) -> None:
    write(site / "backend/kernel/added.py", "OURS = 1\n")
    write(repo / "kernel/backend/kernel/added.py", "ADDED = 1\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 1
    assert (site / "backend/kernel/added.py").read_text("utf-8") == "OURS = 1\n"
    assert (site / PATCHES / "backend/kernel/added.py.patch").is_file()


def test_a_file_gone_from_the_kernel_goes_from_the_site_when_it_wasnt_edited(
    repo: Path, site: Path
) -> None:
    (repo / KERNEL_FILE).unlink()
    commit(repo, "second")
    assert upgrade(repo, site) == 0
    assert not (site / SITE_KERNEL_FILE).exists()
    assert SITE_KERNEL_FILE not in kernel_lock(site, repo)


def test_a_file_gone_from_the_kernel_that_the_site_edited_is_a_conflict(
    repo: Path, site: Path
) -> None:
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 'ours'\n")
    (repo / KERNEL_FILE).unlink()
    commit(repo, "second")
    assert upgrade(repo, site) == 1
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 'ours'\n"
    assert (site / PATCHES / f"{SITE_KERNEL_FILE}.patch").is_file()


def test_a_file_missing_from_the_site_that_the_kernel_changed_is_a_conflict(
    repo: Path, site: Path
) -> None:
    (site / SITE_KERNEL_FILE).unlink()
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 1
    assert not (site / SITE_KERNEL_FILE).exists()


def test_a_file_missing_from_the_site_that_the_kernel_left_alone_stays_missing(
    repo: Path, site: Path
) -> None:
    (site / SITE_KERNEL_FILE).unlink()
    edit(repo / "kernel/web/index.ts", "export const changed = 1;\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 0
    assert not (site / SITE_KERNEL_FILE).exists()
    assert check.check(site, root=repo).missing == [SITE_KERNEL_FILE]


def test_nothing_to_do_says_so_and_writes_nothing(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = tree(site)
    capsys.readouterr()
    assert upgrade(repo, site) == 0
    assert tree(site) == before
    assert "already" in capsys.readouterr().out


# --- merged conflicts --------------------------------------------------------------------


def _two_conflicts(repo: Path, site: Path) -> None:
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 'ours'\n")
    edit(site / "web/src/kernel/index.ts", "export const ours = 1;\n")
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    edit(repo / "kernel/web/index.ts", "export const theirs = 1;\n")
    write(repo / "kernel/backend/kernel/added.py", "ADDED = 1\n")
    commit(repo, "second")


def test_merged_clears_each_conflict_named_and_the_rest_still_stop_it(
    repo: Path, site: Path
) -> None:
    _two_conflicts(repo, site)
    assert upgrade(repo, site) == 1
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 2  # and ours\n")  # the agent's merge
    assert upgrade(repo, site, "--merged", SITE_KERNEL_FILE) == 1
    assert sorted(path for path in tree(site) if path.startswith(PATCHES)) == [
        f"{PATCHES}/README.txt",
        f"{PATCHES}/web/src/kernel/index.ts.patch",
    ]
    assert not (site / "backend/kernel/added.py").exists()


def test_once_every_conflict_is_merged_it_writes_everything(repo: Path, site: Path) -> None:
    _two_conflicts(repo, site)
    assert upgrade(repo, site) == 1
    edit(site / SITE_KERNEL_FILE, "SESSIONS = 2  # and ours\n")
    edit(site / "web/src/kernel/index.ts", "export const theirs = 1;\nexport const ours = 1;\n")
    merged = ["--merged", SITE_KERNEL_FILE, "--merged", "web\\src\\kernel\\index.ts"]
    assert upgrade(repo, site, *merged) == 0
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 2  # and ours\n"
    assert (site / "backend/kernel/added.py").read_text("utf-8") == "ADDED = 1\n"
    assert not (site / ".mechframe").exists()
    # A merged file is the site's edit on the new copy.
    files = kernel_lock(site, repo)
    assert files[SITE_KERNEL_FILE] == digest(repo / KERNEL_FILE)
    assert sorted(check.check(site, root=repo).edited) == [
        SITE_KERNEL_FILE,
        "web/src/kernel/index.ts",
    ]


def test_merged_naming_a_file_that_isnt_a_conflict_is_refused(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    before = tree(site)
    assert upgrade(repo, site, "--merged", "web/src/kernel/index.ts") == 2
    assert tree(site) == before
    assert "web/src/kernel/index.ts" in capsys.readouterr().err


# --- the base ----------------------------------------------------------------------------


def _without_commit(site: Path, repo: Path) -> None:
    data = lock.read(site, root=repo)
    del data["kernel"]["commit"]
    lock.write(site, data, root=repo)


def test_an_older_locks_base_is_found_by_its_hashes(repo: Path, site: Path) -> None:
    first = lock.read(site, root=repo)["kernel"]["commit"]
    _without_commit(site, repo)
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    edit(site / "web/src/kernel/index.ts", "export const ours = 1;\n")
    edit(repo / "kernel/web/index.ts", "export const theirs = 1;\n")
    commit(repo, "third")
    assert upgrade(repo, site) == 1  # a conflict: the diff runs from the base found
    patch = (site / PATCHES / "web/src/kernel/index.ts.patch").read_text("utf-8")
    assert "-export {};" in patch
    assert first[:7] in (site / PATCHES / "README.txt").read_text("utf-8")


def test_an_older_lock_is_refused_when_its_candidates_differ_in_the_template(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = lock.read(site, root=repo)["kernel"]["commit"]
    _without_commit(site, repo)
    edit(repo / "templates/site/README.md", "# __SITE_NAME__\n\nA README fix.\n")
    template_only = commit(repo, "a template-only fix")
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    before = tree(site)
    capsys.readouterr()
    assert upgrade(repo, site) == 2
    assert tree(site) == before
    err = capsys.readouterr().err
    assert first[:7] in err
    assert template_only[:7] in err
    assert "--base" in err
    # Named, the base settles it: the site's README was never edited, so it takes the fix.
    assert upgrade(repo, site, "--base", first) == 0
    assert "A README fix." in (site / "README.md").read_text("utf-8")
    assert lock.read(site, root=repo)["kernel"]["commit"] == git(repo, "rev-parse", "HEAD")


def test_an_older_locks_base_holds_exactly_the_locks_kernel_files(repo: Path, site: Path) -> None:
    # A later commit that only adds a kernel file holds every file the lock records, and one
    # more: it isn't the base. Were it taken, its template would differ from the first's.
    _without_commit(site, repo)
    write(repo / "kernel/backend/kernel/added.py", "ADDED = 1\n")
    edit(repo / "templates/site/README.md", "# __SITE_NAME__\n\nA README fix.\n")
    commit(repo, "a kernel file added, and the README")
    assert upgrade(repo, site) == 0
    assert (site / "backend/kernel/added.py").read_text("utf-8") == "ADDED = 1\n"
    assert "A README fix." in (site / "README.md").read_text("utf-8")


def test_an_older_lock_with_no_candidate_is_refused(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _without_commit(site, repo)
    data = lock.read(site, root=repo)
    data["kernel"]["files"][SITE_KERNEL_FILE] = "sha256:" + "0" * 64
    lock.write(site, data, root=repo)
    assert upgrade(repo, site) == 2
    assert "--base" in capsys.readouterr().err


@pytest.mark.parametrize("given", ["0" * 40, "no-such-ref"])
def test_a_base_that_isnt_a_commit_here_is_refused(
    repo: Path, site: Path, given: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert upgrade(repo, site, "--base", given) == 2
    assert given in capsys.readouterr().err


def test_a_base_whose_kernel_isnt_the_locks_is_refused(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    second = commit(repo, "second")
    assert upgrade(repo, site, "--base", second) == 2
    assert "doesn't hold the kernel" in capsys.readouterr().err


# --- where the new copy comes from -------------------------------------------------------


def test_the_new_copy_comes_from_the_ref_not_the_working_tree(repo: Path, site: Path) -> None:
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second on main")
    git(repo, "checkout", "-q", "-b", "elsewhere")
    edit(repo / KERNEL_FILE, "SESSIONS = 'a branch'\n")
    commit(repo, "on a branch")
    edit(repo / KERNEL_FILE, "SESSIONS = 'not committed'\n")
    assert upgrade(repo, site) == 0
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 2\n"
    assert lock.read(site, root=repo)["kernel"]["commit"] == git(repo, "rev-parse", "main")


def test_from_names_another_ref(repo: Path, site: Path) -> None:
    git(repo, "checkout", "-q", "-b", "next")
    edit(repo / KERNEL_FILE, "SESSIONS = 3\n")
    commit(repo, "on next")
    assert upgrade(repo, site, "--from", "next") == 0
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 3\n"


def test_dry_run_says_what_it_would_do_and_writes_nothing(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    write(repo / "kernel/backend/kernel/added.py", "ADDED = 1\n")
    edit(site / "web/src/kernel/index.ts", "export const ours = 1;\n")
    edit(repo / "kernel/web/index.ts", "export const theirs = 1;\n")
    commit(repo, "second")
    before = tree(site)
    capsys.readouterr()
    assert upgrade(repo, site, "--dry-run") == 1
    assert tree(site) == before
    out = capsys.readouterr().out
    assert f"write   {SITE_KERNEL_FILE}" in out
    assert "add     backend/kernel/added.py" in out
    assert "conflict web/src/kernel/index.ts" in out


# --- the template's files ----------------------------------------------------------------


def test_the_templates_files_follow_the_same_rule_with_the_name_and_theme_written_in(
    repo: Path, tmp_path: Path
) -> None:
    site = make_site(repo, tmp_path / "named", "--name", "Vibrant Test", "--theme", "vibrant-mindz")
    edit(site / "CLAUDE.md", "# CLAUDE.md: Vibrant Test\n\nOur own notes.\n")
    edit(repo / "templates/site/README.md", "# __SITE_NAME__\n\nMade with MechFrame, upgraded.\n")
    edit(repo / "templates/site/CLAUDE.md", "# CLAUDE.md: __SITE_NAME__\n\nThe kernel's notes.\n")
    edit(repo / "templates/site/web/index.html", '<html lang="en" data-theme="__THEME__"></html>\n')
    edit(repo / "themes/vibrant-mindz/tokens.css", '[data-theme="vibrant-mindz"] { --mf-x: 1; }\n')
    edit(
        repo / "themes/machined-light/tokens.css", '[data-theme="machined-light"] { --mf-y: 1; }\n'
    )
    edit(repo / "requirements.txt", "# requirements.txt, pinned again\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 1  # CLAUDE.md: both changed it
    assert (site / PATCHES / "CLAUDE.md.patch").is_file()
    assert upgrade(repo, site, "--merged", "CLAUDE.md") == 0
    assert (site / "README.md").read_text(
        "utf-8"
    ) == "# Vibrant Test\n\nMade with MechFrame, upgraded.\n"
    assert (site / "web/index.html").read_text(
        "utf-8"
    ) == '<html lang="en" data-theme="vibrant-mindz"></html>\n'
    assert "--mf-x: 1" in (site / "web/src/theme/tokens.css").read_text("utf-8")
    assert (site / "requirements.txt").read_text("utf-8") == "# requirements.txt, pinned again\n"
    assert (site / "CLAUDE.md").read_text(
        "utf-8"
    ) == "# CLAUDE.md: Vibrant Test\n\nOur own notes.\n"


def test_the_sites_own_folders_and_files_are_never_touched(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(repo / "templates/site/web/src/site/site.ts", "export const site = 1;\n")
    write(repo / "templates/site/backend/app/site/pages.py", "PAGES = 1\n")
    commit(repo, "the template's site folders")
    site = make_site(repo, tmp_path / "own")
    edit(repo / "templates/site/web/src/site/site.ts", "export const site = 2;\n")
    edit(repo / "templates/site/backend/app/site/pages.py", "PAGES = 2\n")
    env = (repo / "templates/site/.env.example").read_text("utf-8")
    edit(repo / "templates/site/.env.example", env + "NEW_KERNEL_SETTING=\n")
    edit(repo / "templates/site/.railway/railway.ts", 'const name = "changed";\n')
    edit(repo / "templates/site/backend/app/modules.py", '"""Changed."""\n')
    commit(repo, "second")
    before = tree(site)
    capsys.readouterr()
    assert upgrade(repo, site) == 0
    # Only the lock moved on: the site's folders, the registries and its settings files stay.
    after = tree(site)
    assert {path: data for path, data in after.items() if path != lock.NAME} == {
        path: data for path, data in before.items() if path != lock.NAME
    }
    out = capsys.readouterr().out
    assert "NEW_KERNEL_SETTING" in out


def test_a_site_whose_name_isnt_in_its_env_example_keeps_the_files_that_carry_it(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = site / ".env.example"
    env.write_text(env.read_text("utf-8").replace("SITE_NAME=", "# SITE_NAME="), encoding="utf-8")
    edit(repo / "templates/site/README.md", "# __SITE_NAME__\n\nUpgraded.\n")
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    capsys.readouterr()
    assert upgrade(repo, site) == 0
    assert "Upgraded." not in (site / "README.md").read_text("utf-8")
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 2\n"
    out = capsys.readouterr().out
    assert "README.md" in out
    assert "SITE_NAME" in out


def test_it_says_what_to_run_next(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(repo / "requirements.txt", "# requirements.txt, pinned again\n")
    write(repo / "templates/site/web/package.json", '{"name": "site"}\n')
    write(repo / "kernel/migrations/kernel_0002.py", "revision = 'kernel_0002'\n")
    commit(repo, "second")
    capsys.readouterr()
    assert upgrade(repo, site) == 0
    out = capsys.readouterr().out
    assert "pip install --require-hashes" in out
    assert "npm ci" in out
    assert "-m app.migrations upgrade" in out
    assert "pytest" in out
    assert "mechframe check" in out


# --- refusals ----------------------------------------------------------------------------


def test_a_folder_that_isnt_a_site_is_refused(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "empty").mkdir()
    assert upgrade(repo, tmp_path / "empty") == 2
    assert "mechframe.lock.json" in capsys.readouterr().err


def test_a_checkout_that_isnt_git_is_refused(
    site_maker: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    made = make_site(site_maker, tmp_path / "plain")
    assert upgrade(site_maker, made) == 2
    assert "Git" in capsys.readouterr().err


def test_an_unknown_ref_is_refused(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert upgrade(repo, site, "--from", "nowhere") == 2
    assert "nowhere" in capsys.readouterr().err


def test_a_lock_commit_this_checkout_lacks_is_refused(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = lock.read(site, root=repo)
    data["kernel"]["commit"] = "1" * 40
    lock.write(site, data, root=repo)
    assert upgrade(repo, site) == 2
    assert "1111111" in capsys.readouterr().err


def test_a_module_cant_be_upgraded_yet(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["upgrade", "demo-shop", "--site", str(site), "--root", str(repo)]) == 2
    assert "kernel" in capsys.readouterr().err


def test_another_run_holding_the_site_is_refused(
    repo: Path, site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (site / ".mechframe-busy").touch()
    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    commit(repo, "second")
    assert upgrade(repo, site) == 2
    assert (site / SITE_KERNEL_FILE).read_text("utf-8") == "SESSIONS = 1\n"


def test_a_failure_half_way_puts_every_file_back(
    repo: Path, site: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mechframe import modules

    edit(repo / KERNEL_FILE, "SESSIONS = 2\n")
    edit(repo / "kernel/web/index.ts", "export const changed = 1;\n")
    commit(repo, "second")
    before = tree(site)
    writes = 0
    real = modules.Journal.write

    def failing(self: modules.Journal, path: Path, data: bytes) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("the disk is full")
        real(self, path, data)

    monkeypatch.setattr(modules.Journal, "write", failing)
    with pytest.raises(OSError, match="the disk is full"):
        upgrade(repo, site)
    assert tree(site) == before


def test_the_lock_records_the_new_kernels_version(repo: Path, site: Path) -> None:
    manifest = json.loads((repo / "kernel/kernel.json").read_text("utf-8"))
    manifest["version"] = "0.2.0"
    edit(repo / "kernel/kernel.json", json.dumps(manifest, indent=2) + "\n")
    commit(repo, "0.2.0")
    assert upgrade(repo, site) == 0
    assert lock.read(site, root=repo)["kernel"]["version"] == "0.2.0"
