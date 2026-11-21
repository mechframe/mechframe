# Handoff

Overwritten every session. This one: 2026-11-21, midday Eastern (Claude Code, the owner's machine), session M1 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`: the kit's two fixes (#101) and hooks 4 and 5 (#102, #103), all landed; `main` is `3f0a79b`. Hook 6, M1's stretch, is the next session's first job.

## State

- **The kernel is done**, K0 to K5. K2's steps 9 to 11 still wait for the site (decision 0029).
- **Hooks 1 to 5 of the ten are in** (decision 0052, `dev plans/contracts/hooks.md`): content lifecycle (#97), taxonomy (#98), search index (#99), seed data (#102), bot check (#103). Next: consent categories, export and erase, dashboard cards; then Vibrant Mindz's step 1. Entitlements and profile tabs wait (decision 0052, item 11).
- **#101, the kit's two fixes** (VM Website Dev 05, the owner's OK), landed at `b1e94b8`: the required token `color.field` fills `.mf-input` (Vibrant Mindz's canvas `#070A16`, Machined Light's well), and every switch takes the admin's gap ring, off as well as on. Decision 0042 amended; SPEC's change log; the K4 contract's token list.
- **#102, hook 4, seed data**, landed at `9658849`:
  - `kernel.seed`: a module's `seed.py` gives `async def seed(db, ctx)`, idempotent. `seed.run` seeds the modules in `requires` order (ties by id), then the site's own `backend/app/site/seed.py`, in one transaction, audited as `kernel.seed.ran`. `seed.Context`: `module`, a fixed `now` (2026-01-01 12:00 UTC), `random` seeded with the module's id, `user(role)` (`seed-<role>@example.com`, verified, no password, never owner; an account at that address the seed didn't make is refused), `put_image(name)` (the key at once; the PNG stored after the commit, so a seed that raises stores none).
  - Every caller goes through `run`, which refuses unless `MECHFRAME_ALLOW_SEED=1` is in the environment: never `.env`, never `railway.ts` (a template test). Commands: `python -m harness.seed`, the template's `python -m app.seed`, `mechframe seed --site <dir>` (`owner.run_in_site`, shared with `create-owner`). `POST /api/_test/seed {allow}` for the contract suite.
  - CodeRabbit's seven findings answered with fixes and tests: account collisions, the PNG off the event loop, the public import in the examples, the PowerShell line clearing the variable, images stored after the commit, what an upload failing after it leaves (the rows kept; the next run stores every image), and what a repeat run does besides its rows (another audit entry, the images again).
- **#103, hook 5, bot check**, landed at `3f0a79b`:
  - `kernel.bot`: a public form's body carries `bot: kernel.BotProof` (annotate with `kernel.BotProof`: a field named `bot` hides the module). `bot.verify(request, proof, form="<id>.<form>", db=db)`, with the route's own session, answers `Pass()` or `Held(reason)`; a held submission is kept and never dropped. The kernel's `form` check is VybeSite's contact filter (trap field `website`, three seconds). The settings section `kernel.bot` names `form` or a module's `__init__.py` `BOT_PROVIDER` while it's on; one that fails or answers neither is `provider_error`.
  - Codex's finding fixed with a test: `verify` reads through the route's session, since a second connection waited forever on a one-connection pool.
  - The kit's `<BotFields />` and `useBotProof()`, on the kit page so axe checks them. The probe's form is `POST /api/probe/inquiries`.
- Mutants: 12 caught for each hook. Brand check clean on #103. The full suite: 2595 passed, 98.23 %.
- **v1.0:** 70 % (43 of 61 steps); the hooks are after v1.0's steps. The ledger was republished from `3f0a79b`.

## Next

1. **Session M2** (`dev plans/2026-11-21-next-session-m2-hooks-6-to-8.md`): hook 6, consent categories (M1's stretch); hook 7, export and erase (14.7's export); hook 8, dashboard cards. Then decision 0052's Status reads "1 to 8 applied".
2. M3 to M5 as the plan has them.

## Open questions for the owner

- **Fields and the gap ring** (VM Website Dev 05): a focused field's ring meets its `#5C6584` edge at 2.2:1. Give fields the gap ring too, or leave them?
- **The Vibrant Mindz site** copies `themes/vibrant-mindz/tokens.json` byte for byte: it gained `color.field` (#101), and the site's count tests take one more alias and role.
- **Hooks 4 and 5's changes after approval** (the contract's list): override any you'd rather. One changed the contract's shape: `bot.verify` takes `db=`.
- **A public name and handle for a person**, before hook 10, which waits for wave 2b.
- **The `mechframe upgrade` contract** (M3), for your approval when it comes.
- **The Vibrant Mindz content** (`C:\DEV\VM Website\design\specs\content-intake.md`).
- `mechframe-iac-probe` on Railway; a Railway variable to confirm a destructive migration; seven unused ledger assets; cubic and CodeRabbit's limits; rewording the kernel's screens; the R2 test buckets; renaming the folder and the `devkit-*` skills.

## Notes

- **The full suite takes about 25 minutes.** Run it in the background with its log in the scratchpad, and edit nothing and switch no branch meanwhile: CLI tests copy the kernel.
- **CodeRabbit keeps reviewing each fix** and found something new five times on #102; Codex reviews only a PR's first push. Answer each finding with a fix and a test, or a reply saying why not.
- **A review fix on a stacked PR:** stash the next PR's work (`git stash push -u`), fix on the first PR's branch, then fast-forward the next and pop (once the next has commits, merge instead). Docs both touch conflict: keep the first PR's line, then the next's.
- **Git writes CRLF on a stash pop or a merge here:** a patch script matches after `.replace("\r\n", "\n")`.
- **A hook's contract test** calls only routes in `docs/contracts/auth-api.md`; a unit fixture restores a kernel global with `monkeypatch.setattr`. A test-support route can stand for an environment variable a suite can't set on a running server (`/api/_test/seed`'s `allow`).
- **A kernel call from a module route reads through the route's session** (`db=`): `require_module` already holds a connection.
- **The Bash tool decodes `\n` and `\uXXXX`:** write patch scripts with the Write tool.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner.
- Never edit `C:\DEV\VM Website`: a Vibrant Mindz session works there.
