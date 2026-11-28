# Handoff

Overwritten every session. This one: 2026-11-28, about 06:30 to 10:45 Eastern (15:45 UTC) (Claude Code, the owner's machine), session M4n, the main lane. Landed: #170. The side lane landed #171 (portfolio 0.1.0). `main` was 8e48530 (#171), and this handoff is its own docs PR.

## State

- **Reactions 0.1.0 (#170, decision 0068).** The owner approved `dev plans/contracts/reactions.md` as recommended, its five answers taken:
  - no custom emojis until community;
  - a verified member adds, with time-outs holding, and any member takes their own back;
  - any live thing a module gives through item references takes reactions;
  - counts and your own only;
  - the palette as a setting with no screen.
  - **What it does:** Fire, Love and Mind blown sit under a blog post, as the Post board draws them. Reactions names the thing by type and id and asks `kernel.refs`; the kernel's new props slot `content.reactions` carries the row (`ReactionParts`), so neither module requires the other.
  - **Blog 0.1.8** gives `blog.post` through `refs.py` (a featured slot can hold posts too), carries `LivePost.id`, and draws the row after the body.
  - **The kernel's web surface** gains `ReactionParts`, `signInFor` and `SESSION_KEY` (SPEC 6 and 8).
  - **The review rounds** (Codex, cubic, CodeRabbit) are in the contract's "Changes after approval":
    - a row's writes go one after the other;
    - each write asks the cache who's signed in when it goes and when it lands;
    - a dropped write reads the row again;
    - reads on their way are cancelled before a press or a saved answer is drawn.
  - **The site's answers** (VM Website Dev 27, the owner's word): only the Post board draws reactions; signed out goes to sign-in; the switch's line is "Reactions on posts, comments and messages"; the board's icons ship.
- **Portfolio 0.1.0 (#171, the side lane, decision 0074).** The owner approved `dev plans/contracts/portfolio.md` as recommended (eight answers).
  - **What it does:** pieces by discipline, each with one picture from media, the account it's credited to, a year, words and an optional YouTube link, through the lifecycle. It also gives search, `portfolio.piece` item references, server copy, export and erase, and a seed. Collective › Portfolio and the Art page are drawn to the AdminPortfolio and Art boards.
  - **Two permissions:** `portfolio.piece.add` for an artist's own pieces, `portfolio.piece.manage` for every piece. `require_owner_or(p)` passes anyone holding `p`, so a "your own" role needs its own permission. VM Website has its seed change.
  - **Its Result** is in `dev plans/done/2026-11-28-side-lane-m14-portfolio.md` §9.
- **The owner's call on VM Website's asks** (2026-11-28, "as recommended"):
  - B, Bandcamp's own player (discography and embeds), goes to the side lane after portfolio.
  - C, uploaded video, comes to the main lane after comments, contract first.
  - Their pages are VM Website's `dev plans/2026-11-28-ask-b-bandcamp-player.md` and `ask-c-uploaded-video.md`, under its approved `dev plans/contracts/player-sources.md`.
- **Progress:** v1.0 is at 83% (51 of 61). Step 3 is under way: reactions and portfolio are built; comments, then roster, to go. **The ledger** shows this PR's rows.

## Next

1. **Main lane:** reactions 0.1.1 first, VM Website Dev 28's X1 and X2 (the owner's call: the board wins; a count's figures and a pill's line height); then comments' contract and the module (`dev plans/2026-11-28-next-session-m4o-comments.md`, with what the boards draw); then ask C's contract; roster last.
2. **Side lane:** ask B's contract, then the build (`dev plans/2026-11-28-side-lane-m15-bandcamp.md`).

## Open questions for the owner

- Comments' contract: the questions are in the main lane's prompt, §5.
- Ask B's contract, and later ask C's, which changes decision 0054 and discography's non-goal.
- Roster: whether the profile-tabs hook comes forward, and its own-profile permission, apart from the staff one, as portfolio split `.add` from `.manage`.
- Removing the standby worktrees under `.claude/worktrees/` (`discography-0-1-0`, and M14's `mechframe-side-lane-portfolio-5d6e12`), and the two memory notes marked "can be deleted".

## Notes

- **IDs:**
  - **Used:** the main lane used decision 0068 and `reactions_0001`, the side lane 0074 and `portfolio_0001`.
  - **The main lane has** decisions 0069 and 0080 to 0089, `kernel_0017`, `kernel_0018`, `blog_0002`, `comments_0001`, `media_0002` and `featured_0002`.
  - **The side lane has** decisions 0075 to 0079, `discography_0002` and `embeds_0001`.
- **Traps met:**
  - **TanStack Query tells components of a cache change on a later tick** (`setTimeout`), so a ref synced from render lags it. A part that acts later must read the cache then (`queryClient.getQueryData(SESSION_KEY)`).
  - **A visually hidden label's trailing space is trimmed** from a button's name ("Fire3"): name it with `aria-label`, its visible words in it (axe's `label-content-name-mismatch`).
  - **Two modules' answer models of one name** (`Choice`) make the site's OpenAPI rename one (`Choice-Input`), and the kernel's committed spec goes stale: give a module's answers its own names.
  - **RTL's `rerender` drops `renderWithKernel`'s providers:** change a prop through a small stateful page instead.
  - **PowerShell's `Get-Content | Set-Content` turns `§` into `Â§`** and adds a BOM: edit files with Python.
  - **`npm run api:check` fails locally** on a `schema.ts` that git checked out with CRLF; CI's LF copy passes.
  - **cubic resolves its own threads on a push** it judges fixed; Codex reviews once, when the PR opens.
  - **The side lane's** (M14's Result): a seed may never ask for the owner (`ctx.user("owner")` raises); a manifest's `summary` is 120 characters at most; the e2e server's storage is off, so a module whose every item needs a picture stands in its reads at the browser.
- **Still true:**
  - The full Python suite takes about 30 minutes (3,939 tests before portfolio); the e2e suite has about 155 tests. On a shared PC, check `Get-Process` before diagnosing a timeout.
  - Commit with `git commit -F <file>` after `git branch --show-current`. Never `prettier --write` an existing file.
  - On Windows, the generators rewrite some `schema.ts` files with CRLF only: `git checkout` them.
  - **`docs/progress.json`:** `json.dumps` rewrites its whole layout. Edit a step's one line in place.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, never create a third-party account, and never edit `C:\DEV\VM Website`.
