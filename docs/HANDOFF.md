# Handoff

Overwritten every session. This one: 2026-11-21, evening Eastern (Claude Code, the owner's machine), session M3a of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. VM Website's items 6 and 7 landed (#113, #114), and `media` is begun on a local branch. `main` is `12b3993`.

## State

- **The kernel is done**, K0 to K5; hooks 1 to 8 of the ten are in (decision 0052). Entitlements and profile tabs wait.
- **#113, `<AfterFooter>`** (VM Website's "For MechFrame" item 6, the owner's goal: Release's docked player stays under the footer), landed at `0d19081`.
  - A page renders `<AfterFooter>` from `@/kernel`. Its children are portaled into a holder `SiteFrame` draws last in `.mf-site`, after the footer.
  - The holder is `display: contents`, so a `position: sticky; bottom: 0` bar sticks over the whole page and settles below the footer at the end.
  - It draws nothing in the sign-in or admin frames.
  - Contract `dev plans/contracts/after-footer.md`; SPEC 8; decision 0048 amended.
  - Playwright checks the bar on the harness frame page (`/frame-docked`) in both themes. A `display: block` mutant put the bar at y=1305 in a 720px window.
- **#114, the upgrade's new site files** (item 7, a bug from #111's first live run), landed at `12b3993`.
  - A template file new in `backend/app/site/` or `web/src/site/` since the base is written where the site has none, named after the run, and the site's from then on.
  - A file the site already has there is kept, and one the site removed isn't written again.
  - CodeRabbit's finding, fixed with tests: with no `SITE_NAME` in `.env.example`, such a file that carries the name stops the run before anything is written.
  - Decision 0053 and its contract amended.
- **`media`, begun.** Its contract, `dev plans/contracts/media.md`, was approved 2026-11-21 as recommended. On `feat/media`, committed locally (`d4ffa49`, then `aae5612`) and not pushed:
  - the backend: `pictures`, VybeSite's upload rules, with 53 of its tests ported and green; `models`, with `media_image` and `media_use`; `service`, `router`, `public`, `privacy`, `dashboard` and `seed`;
  - the migration `media_0001`, which grants admin and editor;
  - `module.json`, `openapi.json` and `catalog.json`; Pillow 13.0.0 and python-multipart 0.0.34 pinned, pip-audit clean;
  - green: mypy, ruff, the schema check, and the migration round trip with media's branch.
  - The contract's "Changes after approval" lists six things the build moved: no kernel CSP change (`img-src` already allows `https:`), `version` and `file_version`, 409 `media.changed`, the grants in the migration, the seed storing its own files, and python-multipart.
- **The full suite on `feat/media`** found one kernel test to widen: the seeded grants were held to `kernel.json` alone, so media's read as extra. Fixed in `aae5612`: they're held to every installed manifest's, which also checks `media_0001` against media's `default_roles`. A full rerun was started at the session's end; its result wasn't read, so run the suite first.
- VM Website has been told where items 6 and 7 landed.
- **The owner approved (2026-11-21, "Approved on both points")** #114's change to decision 0053 §5, and widening Playwright to `modules/*/tests/e2e` (the E2E workflow), for media's admin page first.

## Next

1. **Session M3b** (`dev plans/2026-11-21-next-session-m3-media-web.md`): media's service and contract tests, then its web (the admin page, `ImagePicker`, `Picture`), docs and PR.
2. M4 (`pages`, `blog`) and M5, as the plan has them.

## Open questions for the owner

- Hooks 6 to 8's changes after approval; a public name and handle for a person (hook 10); the Vibrant Mindz content; `mechframe-iac-probe` on Railway; the rest of M2's list.

## Notes

- **The full suite** takes 25 minutes on a quiet machine, more under load: in the background, with no edits or branch switches in that checkout. This handoff was written in a worktree beside it (`.claude/worktrees/handoff`).
- **A module's tests can't see `kernel/tests/conftest.py`:** media needs a `conftest.py` of its own.
- **The Write tool decodes `\uXXXX`:** build such characters with `chr()`. Git writes CRLF on a merge, so patch scripts match after `.replace("\r\n", "\n")`.
- **`npx.cmd` and a quoted argument with a space** fail in cmd: use `--grep=word`.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code (media's, before its PR).
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
