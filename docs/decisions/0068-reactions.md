# 0068: Reactions, any module's live thing reacted to through item references

- **Status:** Decided. The owner approved `dev plans/contracts/reactions.md` as recommended on 2026-11-28, its five questions answered as recommended. Applied in its PR.
- **Context:**
  - Step 3 of the Vibrant Mindz site starts with reactions, shared by comments and, later, community (module plan §2, §8 and §9). VM Website's Post board draws three under a post's body: Fire, Love and Mind blown, each a pill with its icon and a count.
  - VybeMindz has reactions on its messages: any emoji, one row per person, message and emoji, a duplicate press a no-op, and admin-uploaded custom emojis. It ties them to its channels' access checks and, in encrypted channels, a blind index.
  - Modules never import each other except through a `public.py` listed in `requires.modules` (SPEC 7). A site with a blog but no reactions must still work, and reactions shouldn't need code for each module it serves.
- **Decision:**
  1. **The thing is named by its content type and id** (`blog.post`), and reactions asks `kernel.refs.find` whether it's there and live (hook 11, decision 0072). It reads no module's rows and keeps no foreign key to them. Any live thing a module gives through item references takes reactions; blog 0.1.8 gives its posts. A type whose module is off answers 404, and the weekly sweep deletes only the reactions of things that are gone, so switching a module off loses nothing.
  2. **A props slot, `content.reactions`,** drawn by the kernel's `<ReactionParts type id />` on a module's public page, given the thing's type and id. Reactions fills it with its row. Blog's post page draws it after the body. Like `content.share` (decision 0067), its parts are given props, each in its own error boundary, and a page draws nothing there while no module on fills it.
  3. **A palette of built-in reactions,** not any emoji (§8, 1): `fire`, `love` and `mind_blown`, with the board's icons. The settings section `reactions` holds which are offered and their order, saved through the kernel's settings route. A key taken out keeps its rows, isn't counted, and can still be taken back.
  4. **Who:** a signed-in member with a verified address adds one, with moderation's time-out holding (SPEC 14.7: verification before public content); any member takes their own back (§8, 2). Guests can't. Everyone reads the counts; only the reader's own are named, never who else reacted (§8, 4).
  5. **One row each** per thing, person and key, held by a unique constraint and `INSERT … ON CONFLICT DO NOTHING`, so two presses at once make one.
  6. **The web's sign-in link** is the kernel's `signInFor(path)`, now on its web surface, so a module sends a signed-out reader to sign in and back as `RequireAuth` does.
- **Rejected:**
  - **Search's public documents** as the check (social's way): they can't tell a thing that's gone from one that's hidden, so the sweep couldn't keep a draft's reactions, and comments aren't searched.
  - **Blog listing reactions in `requires.modules`** and drawing its `public.ts`: a blog would need reactions.
  - **Routes in each module** calling a reactions `public.py` (VybeMindz's shape, one router per message type): every module would carry its own copy of the checks.
  - **Any emoji from a picker, and custom emojis,** now: no board draws them and nothing before community needs them (§8, 1).
  - **Denormalised counts:** a thing's rows are counted from the unique index, which suits a page's one read.
- **Consequences:**
  - SPEC 6 gains `signInFor`; SPEC 8 the slot `content.reactions` and `ReactionParts`; `schema/module.schema.json` the slot's name.
  - Blog 0.1.8 gives `blog.post` through `refs.py`, so a featured slot may also hold posts, and its `LivePost` carries the post's `id`.
  - Comments (step 3's next) can put the row under each comment by giving `comments.comment` through item references and drawing `ReactionParts`; its contract decides whether it needs more from reactions.
  - A site takes it with `mechframe add reactions`, and the kernel's part with `mechframe upgrade kernel`.
