# 0058: The kernel's AI writing help: one Anthropic key, the site's writing rules, and Write with AI in every editor

- **Status:** Decided; applied in the AI PR (blog 0.1.2). The owner approved `dev plans/contracts/kernel-ai.md` on 2026-11-23, as recommended ("Approve as recommended"), after answering `blog.md` §8, 2 and 6 on 2026-11-22.
- **Context:** Vibrant Mindz wants blog's whole writing system from the start, AI help included (the owner, 2026-11-21). VybeSite has it: `ai_key_service.py`, `anthropic_service.py`, the writing constitution, writing styles, and the editor's buttons. But there it's blog's alone, and its key's order, its claims list and its post checks are bound to VybeSite's tables. The owner put the help in the kernel, for every module's `MarkdownEditor` (`blog.md` §8, 2). The key was to be "Host variable or Settings" (§8, 6), and the contract was to say which wins. SPEC 6 listed `ai.client()` with no session, but a saved key has to be read from the database.
- **Decision:**
  1. **The key:** `ANTHROPIC_API_KEY` on the host, or `api_key` (a `SecretStr`, sealed) in the settings section `kernel.ai`. **A saved key wins; the host's is the fallback.** That's VybeSite's order, and 0046's for `sign_up_mode`.
     - A saved key that can't be opened answers 503 `kernel.ai_key_unreadable`, never the host's key in its place.
     - A host value that couldn't be a key counts as none. A save of one is refused (422) in words that never repeat it.
     - The model is `ANTHROPIC_MODEL` (default `claude-opus-5-5`).
     - Every task shares one budget a person, `AI_RATE_LIMIT` (default `20/1h`).
  2. **`await ai.client(db)`** is the public surface: a `Writer` whose `write(task, style=, max_tokens=, effort=, seconds=, schema=)` sends the site's writing rules first, then the chosen style, each cached. Failures are 502 `kernel.ai_failed` in plain words, never Anthropic's or the key. The SDK is Anthropic's own (`anthropic` 2.x), called from the server only.
  3. **The writing rules are the settings section `kernel.writing`,** from VybeSite's constitution without the claims list:
     - VybeSite's six default rules, each a switch, then rules of the site's own, or the site's own text in their place;
     - then a brief of five boxes.
     A writing style is a row of `kernel_writing_style` (migration `kernel_0016`), kept by `kernel.writing.manage`.
  4. **The editor's buttons are one kernel entry in `editor.tools`** (0060), Write with AI, for `kernel.ai.write`. It's drawn only while a key can be used.
     - Draft and Rewrite work on the text. A rewrite that loses a link's or image's address is refused, and so is one whose words changed while the AI wrote.
     - Titles, Summary and Search words show only for the fields a page hands the editor. `MarkdownTools` gains `label`, `text()`, `replace()` and `fields`, and `MarkdownEditorProps` gains `fields`.
  5. **Settings gains AI and Writing,** built from the kit in the Site tab's cards (the owner: no boards first). AI is for `kernel.settings.manage`. Writing is for `kernel.writing.manage`, its rules card for `kernel.settings.manage`. A style has a page of its own.
- **Alternatives:**
  - *Which key wins:* the host's over a saved one, so the owner's typed variable can't be overridden from the admin. Rejected: an admin couldn't replace a leaked host key without a deploy.
  - *Where the help lives:* inside blog, as VybeSite has it. Rejected by the owner for every editor (§8, 2).
  - *Five buttons in the toolbar:* crowds every editor. One button opens a dialog with the five tasks.
  - *Calling the Messages API with httpx:* no new dependency, but the beta header, structured outputs and refusals would be ours to track.
- **Consequences:**
  - SPEC 6's row is `ai.client(db)`. 0060's note that the AI "needs no change to `MarkdownEditor.tsx`" is amended: the editor gains `text`, `replace`, `label` and `fields`.
  - A kernel page's path may hold a `:name` segment (`schema/kernel.schema.json`), for `/admin/settings/writing/styles/:id`, as the web's router already reads one. The shell answers every `/admin/` address, so the server needs nothing more.
  - The harness sends every call to a fake Anthropic (`harness/fake_anthropic.py`, `/api/_test/ai`). No suite calls Anthropic. The first real call is the owner's Check in Settings → AI, with their key.
  - The kit says "Something went wrong on our side" for a 5xx. The AI's screens show `kernel.ai_failed`'s own sentence instead.
  - Generated covers (the next PR) call `ai.client(db)` too. The claims list and the editor's advice on AI phrases and em dashes wait (the owner, 2026-11-22). Their two rules steer the AI only.
- **See:** `dev plans/contracts/kernel-ai.md`; `dev plans/contracts/blog.md` §8; SPEC 6; decisions 0046 and 0060; `kernel/backend/kernel/ai.py`, `writing.py`, `ai_routes.py`; `kernel/web/src/ai/`
