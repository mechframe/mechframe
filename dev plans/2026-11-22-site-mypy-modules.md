# A site's mypy can't see its modules (sent by VM Website)

VM Website Dev 10 sent this on 2026-11-22, with the owner's OK, for the main lane's next session. It's a template fix: its own small PR, after media's round 3.

## The gap

A site's own code may import a module's public surface (decision 0057). VM Website's `backend/app/site/pages.py` imports `blog.public` for its own Blog and Post pages. At run time this works: importing `app` puts `backend/modules` on `sys.path` (`templates/site/backend/app/__init__.py`). mypy doesn't: the template's `pyproject.toml` has `mypy_path = "backend"`, so strict mypy fails with `import-not-found` for `blog`.

VM Website's own fix, in its `pyproject.toml`:
- `mypy_path = "backend,backend/modules"`;
- an override for the installed modules' packages (`["blog.*", "media.*"]`) with `follow_imports = "silent"`, since the copied modules are checked where MechFrame keeps them.

## What to decide and build

- **The template's answer, for every site.** VM Website suggests the CLI write the override's module list on `mechframe add` and `remove`, next to `app/modules.py` and the lock. The alternative is one static line, with no list to keep: `mypy_path` plus following modules normally, since each module already passes strict mypy here. Check that a module's own code passes under the template's mypy settings, overrides included, before choosing the static line.
- **The test, seen failing first:** a site made with `blog`, with a file in `backend/app/site/` that imports `blog.public`, through `mechframe check` or the CLI's tests. `tools.site_smoke` doesn't cover it: its second pass adds only the CLI's fixture modules, which have no `public.py`.
- `mechframe check`, `templates/README.md` and the site's `CLAUDE.md`/`AGENTS.md` stay true.

## Two notes from VM Website, both as designed

- `blog.public`'s answers carry dates as ISO text (`kernel.answers.When`), so a site's server copy parses them. Say so in blog's `MODULE.md`, "Extension points", with blog's next version.
- `kernel.server_copy`'s `Pages.page()` receives the address asked (`/blog/<slug>`), not the pattern. Its docstring already says so (`server_copy.py`, `Pages.page`). Nothing to change.

Done means a new site with a module whose site code imports that module's `public` passes `python -m mypy`, CI's site smoke stays green, and VM Website Dev 10 gets the PR number.
