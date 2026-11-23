---
feature: The kernel's AI writing help, `kernel.ai` (decision 0058): the Anthropic client, Settings → AI and Writing, the editor's five buttons; blog 0.1.2 takes them (Vibrant Mindz step 1; M4's AI PR)
status: approved
approved: 2026-11-23, as recommended ("Approve as recommended"): §8's four answers
plan: `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M4); `dev plans/contracts/blog.md` §8, 2 and 6
pr: — (from GitHub just before the push)
---

# Contract: `kernel.ai`

## 1. Goal

Anyone who writes in a `MarkdownEditor` can ask Claude to draft, rewrite, title, summarise and write the search words for what they're writing, in the site's writing rules and in a writing style they pick. An admin gives the site its Anthropic key, as a host variable or saved in Settings → AI, and sets the rules in Settings → Writing. With no key, no AI shows anywhere (blog.md §8, 6). Lifted from VybeSite (`services/ai_key_service.py`, `anthropic_service.py`, `writing_constitution.py`, `writing_styles.py`, `routers/ai.py`, `ai_settings.py`, `writing_constitution.py`, `writing_styles.py`), reshaped to the kernel's settings service, permissions and kit.

## 2. Interfaces

**The key.** `ANTHROPIC_API_KEY` on the host, typed by the owner, or `api_key: SecretStr | None` in the settings section `kernel.ai`, sealed by `kernel.crypto` and never answered (the settings service's `{"kept", "changes"}`). **A saved key wins; the host's is the fallback** (VybeSite's order, and decision 0046's for `sign_up_mode`). Saving `""` removes the saved key, and the host's is used again. A saved key that can't be opened (`ENCRYPTION_KEYS` changed) is reported as `kernel.ai_key_unreadable` and is never quietly swapped for the host's. A host value that couldn't be a key (blank, spaces, the `.env.example` placeholder, under 20 or over 400 characters) counts as none. The model is `ANTHROPIC_MODEL`, default `claude-opus-5-5` (VybeSite's).

**Backend, `kernel.ai`** (SPEC 6's row changes from `ai.client()` to this):
- `await ai.client(db) -> ai.Writer`. Raises `Problem("kernel.ai_off", 503)` with no key, or `kernel.ai_key_unreadable` (503).
- `Writer.write(task: str, *, style: ai.Style | None = None, max_tokens: int, effort: Literal["low", "medium", "high"], timeout: float, schema: dict | None = None) -> str | dict`. The system prompt is the site's writing constitution block (cached), then the style's block (cached), then the task. Calls follow VybeSite's `_call`: no retries for long tasks, and plain sentences for a refusal, a cut-off or a timeout, never Anthropic's own words or the key. These raise `Problem("kernel.ai_failed", 502, detail)`.
- `Writer.check() -> None`: lists one model, which costs nothing.
- `ai.Source = Literal["settings", "environment", "none"]`; `await ai.source(db) -> ai.Source`.
- `ai.constitution(db) -> str`, the block. It is VybeSite's three parts: how the site works (the site's name from `server_copy.identity`; links by path, never a domain), the rules, then the brief.

A module's own AI task (generated covers, next) calls `ai.client(db)`.

**HTTP**, under `/api/kernel` (codes `kernel.ai_*`, `kernel.writing_*`):
- `GET /ai` (`kernel.ai.write`) → `{ready: bool, unreadable: bool, styles: [{id, name, description}]}`. This is the editor's one read.
- `POST /ai/draft` `{what, topic ≤ 300, length: "short" | "medium" | "long", style_id?}` → `{markdown}`.
- `POST /ai/titles` `{what, topic? ≤ 300, body? ≤ 20,000, style_id?}` → `{titles: string[] ≤ 8}`. It reads the body, or the topic when the body is empty.
- `POST /ai/summary` `{what, body ≤ 20,000, max: 50 to 500, style_id?}` → `{summary}`, at most `max` characters.
- `POST /ai/search` `{what, title, body ≤ 20,000, style_id?}` → `{title ≤ 70, description ≤ 160}` (the kit's `SEARCH_TITLE_MAX` and `SEARCH_DESCRIPTION_MAX`).
- `POST /ai/rewrite` `{what, markdown ≤ 20,000, style_id?}` → `{markdown}`. It changes how the text is written, never what it says. If a link's or image's address is missing from the answer, the route answers 502 `kernel.ai_rewrite_lost`, and the editor keeps its text.
- `POST /ai/style-rules` (`kernel.writing.manage`) `{samples: string[1..3] ≤ 8,000 each}` → `{voice_rules, avoid}`, cut down to what a style can hold.
- `what` is the editor's `label` ("Post body", "Page body"), ≤ 80, so a task says what it writes. A gone `style_id` answers 404 `kernel.writing_style_not_found`. Every `/ai/*` call shares one budget a person, `rate_limit(AI_RATE_LIMIT, key="account", scope="kernel.ai")`, default `20/hour`.
- `GET /admin/ai` (`kernel.settings.manage`) → `{source, model, unreadable}`. `POST /admin/ai/check` → `{works: true, source}`, or 502 `kernel.ai_failed`, never a 401.
- The key and the constitution are saved through the settings routes, `PUT /admin/settings/kernel.ai` and `/admin/settings/kernel.writing`, which are versioned, with history and conflicts. `GET /admin/writing/rules` → the default rules `[{id, label, text, why, warning}]`, the mechanics and `default_text` (read-only).
- Styles: `GET` and `POST /admin/writing/styles`, and `GET`, `PATCH` (`version`, 409 `kernel.writing_style_changed`) and `DELETE /admin/writing/styles/{id}`. A name is unique in any case (409 `kernel.writing_style_name_taken`). Listing needs `kernel.ai.write`; the rest needs `kernel.writing.manage`.

**`kernel.writing`** is a settings section: `mode: "defaults" | "own"`, `rules_off: list[RuleId]`, `added_rules`, `own_text` (≤ 20,000), and the brief's `about`, `audience`, `can_say`, `never_say` and `voice` (each ≤ 4,000). The default rules are VybeSite's six: `verified_only`, `no_fabrication` (with its FTC warning when switched off), `illustrations`, `plain_words`, `ai_tells` (VybeSite's phrase list) and `em_dash`.

**Permissions** (`kernel/kernel.json`, granted in `kernel_0016`): `kernel.ai.write`, "Use the AI's writing help" (admin, editor). `kernel.writing.manage`, "Keep the writing styles" (admin, editor). The key and the rules use `kernel.settings.manage` (admin). The owner holds all three.

**Web.**
- `KERNEL_EDITOR_TOOLS` gains `{ id: "kernel.ai", permission: "kernel.ai.write", lazy: WritingHelp }`.
- `WritingHelp` reads `GET /ai`. It draws nothing unless `ready`, and says so when the key is `unreadable`. When it draws, it shows a Style picker (House style, then the styles) and the buttons.
- `MarkdownTools` gains `label`, `text(): string`, `replace(text: string): void` (typed in, as `insert` is, so undo keeps it) and `fields?: WritingFields`.
- `MarkdownEditorProps` gains `fields?: WritingFields`, where `WritingFields = { title?: { value: string; set(t: string): void }; summary?: { value: string; max: number; set(s: string): void }; search?: { set(title: string, description: string): void } }`.
- Draft and Rewrite always show. Rewrite works on the selection, or on the whole text when nothing is selected. Titles, Summary and Search words show only for the fields the module hands in. Titles offers a list to pick from.
- `SETTINGS_TABS` gains AI (`/admin/settings/ai`, `kernel.settings.manage`) and Writing (`/admin/settings/writing`, the rules for `kernel.settings.manage`, the styles for `kernel.writing.manage`). A style's own page is `/admin/settings/writing/styles/:id`.

**Blog 0.1.2.** `AdminPost` hands its Title, Summary (300) and search fields to the editor. `MODULE.md` "Extension points" says `blog.public`'s dates are ISO text (`kernel.answers.When`). Pages gets Draft and Rewrite with no change.

## 3. Data

`kernel_0016` (`0016_writing.py`, after `kernel_0015`): the table below, and the two permissions granted to `admin` and `editor` (the downgrade takes the grants first, as `0013` does). `kernel.ai` and `kernel.writing` live in the settings table, with no column of their own.

| Table | Column | Type | Null | Default / FK / index |
|---|---|---|---|---|
| `kernel_writing_style` | `id` | uuid | no | PK |
| | `version` | integer | no | 1 |
| | `name` | varchar(80) | no | unique index on `lower(name)` |
| | `description` | varchar(200) | no | `''` |
| | `voice_rules` | text (≤ 6,000, CHECK) | no | `''` |
| | `avoid` | text, one phrase a line (≤ 100 lines of ≤ 120) | no | `''` |
| | `samples` | text[] (≤ 3 of ≤ 8,000) | no | `'{}'` |
| | `created_by_id`, `updated_by_id` | uuid | yes | → `auth_user` `ON DELETE SET NULL`, each indexed |
| | `created_at`, `updated_at` | timestamptz | no | `now()` |

## 4. Files

- **Kernel backend:** `kernel/backend/kernel/ai.py` (the key, the client, the tasks), `writing.py` (the constitution, the styles' service), `ai_routes.py` (the routes above, on `kernel_router` and `admin_router`), `config.py` (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `AI_RATE_LIMIT`), `app.py` (registers `kernel.ai` and `kernel.writing`), `models.py`, `auth/permissions.py`, `kernel/kernel.json`, `__init__.py` (`ai`), `migrations/0016_writing.py`, `openapi.json`.
- **Kernel web:** `kernel/web/src/ai/WritingHelp.tsx`, `AiSettings.tsx`, `Writing.tsx`, `WritingStyle.tsx`, `api.ts`, each with its test. `app/editorTools.ts`, `ui/MarkdownEditor.tsx`, `admin/SettingsPage.tsx`, `app/pages/KernelPages.tsx`, `api/schema.ts`.
- **Tests:** `kernel/tests/test_ai.py`, `test_writing.py`, and a fake Anthropic transport in `conftest.py`. No test calls Anthropic.
- **Blog:** `modules/blog/web/pages/AdminPost.tsx`, `module.json` (0.1.2), `MODULE.md`, `CHANGELOG.md`.
- **The site template:** `.env.example` and `.railway/railway.ts` list `ANTHROPIC_API_KEY` (`preserve()`, typed by the owner), `ANTHROPIC_MODEL` and `AI_RATE_LIMIT`.
- **The rest:** `requirements.in` and its pins (the `anthropic` SDK); SPEC 6 and its change log; `docs/decisions/0058-ai-writing-help.md`; `CLAUDE.md` and `AGENTS.md`'s Stack; `docs/progress.json`.

## 5. Conventions this follows

SPEC 6, 7, 14.12 and 15; decisions 0042 (answers), 0046 (settings, secrets, a saved setting over its variable), 0054 (body limits), 0055 (the editor) and 0060 (`editor.tools`); `CLAUDE.md`'s provenance rule and VybeSite's brand check; `module-contract-lint` for blog.

## 6. Non-goals

- The claims list, and the editor's advice on AI phrases and em dashes. These are VybeSite's post checks, which the owner put off on 2026-11-22. The `ai_tells` and `em_dash` rules steer the AI only.
- Generated covers (the next PR, through `ai.client`) and social posting (blog.md §8, 7).
- VybeSite's site assistant and its other AI help (`assist`).
- Pages' Title and search fields: they wait for pages' next version.
- Streaming answers, and any AI call from the browser. The key never leaves the server, and only staff's own text goes to Anthropic.

## 7. Acceptance

- `test_ai.py`:
  - The key's order: a saved key beats the host's; the host's is used when none is saved; a placeholder counts as none; an unreadable saved key answers 503 and never falls back to the host's.
  - The key appears in no answer and no log (`caplog`).
  - Each route's access: a member gets 403; no key gets 503.
  - The 21st call in an hour answers 429, across all the buttons.
  - The request's system blocks come in order with `cache_control`: the constitution, then the style.
  - The rewrite guard, checked with a mutant: a dropped link answers 502.
  - Each answer is bounded (titles ≤ 8, summary ≤ `max`, search ≤ 70 and 160).
  - The check answers 502, not 401, on a refused key.
- `test_writing.py`:
  - The block as it ships (every rule on, no brief), with rules off, with own text, with brief boxes.
  - The two sections' round trip and conflicts.
  - Styles: create, a name taken in another case, a stale `version` (409), a deleted author (`SET NULL`), a gone style (404).
- The migration's round trip; `tools.openapi --check`, `npm run api:check`, `validate_schemas`, the brand check, `module-contract-lint` on blog, and `mechframe add blog` then `mechframe check`.
- Web:
  - `WritingHelp`: hidden without `ready` or the permission; field buttons only with `fields`; Rewrite replaces the text and Ctrl+Z restores it; a failure keeps the text.
  - The AI and Writing tabs, in both themes, axe clean (Playwright, against the e2e server's fake Anthropic).
- **Live:** nothing is deployed. The first real call happens when the owner types a key into a site and presses Check, never in CI.

## 8. The owner's answers (2026-11-23, all as recommended)

1. **Which key wins:** a saved key over `ANTHROPIC_API_KEY`, the host's the fallback.
2. **The look of Settings → AI and Writing:** built from the kit, in the Site tab's cards, checked in both themes; no boards drawn first.
3. **Who may:** `kernel.ai.write` and `kernel.writing.manage` for admin and editor, the key and the rules for admin; the owner holds all.
4. **The budget:** 20 calls an hour a person on Claude Opus 5.5, both set by host variables (`AI_RATE_LIMIT`, `ANTHROPIC_MODEL`).

## Changes after approval

2026-11-23, as it was built:

- **`AI_RATE_LIMIT`'s default is written `20/1h`,** the kernel's `count/period` form; a bad one fails the start.
- **A pasted value that couldn't be a key is refused on save** (422 on `api_key`, in words that never repeat it), not only counted as none on the host.
- **Write with AI is one button** in the editor's tools, opening a dialog: a Style picker, then the task (Draft, Rewrite, and Titles, Summary and Search words for the fields given). The actions are "Write the draft" and "Rewrite it", so no two buttons share a name. Titles, Summary and Search words show their answer first, used on Use. A rewrite whose words changed while the AI wrote isn't put in.
- **The Writing page is for `kernel.writing.manage`** (a kernel page holds one permission), its rules card for `kernel.settings.manage`; the AI page for `kernel.settings.manage`. Three kernel pages: `/admin/settings/ai`, `/admin/settings/writing` and `/admin/settings/writing/styles/:id` (`new` makes one).
- **The AI's 502s show their own sentence:** the kit says "Something went wrong on our side" for a 5xx, which would hide `kernel.ai_failed`'s and `kernel.ai_rewrite_lost`'s.
- **The styles are audited** as `kernel.writing_style.created`, `.changed` and `.deleted`, under the Activity page's Settings.
- **The SDK resolved to `anthropic` 2.12** (the floor is VybeSite's 1.11); it sends the key as a bearer token.
- **The harness's fake Anthropic** (`harness/fake_anthropic.py`) answers every call of the contract suite and the end-to-end server, driven through `POST` and `GET /api/_test/ai` (`docs/contracts/auth-api.md`).
- **A kernel page's path may hold a `:name` segment** (`schema/kernel.schema.json`), for the style's page.
- **A draft or a rewrite is typed in after the dialog has gone, from a task of its own:** while the modal is open the editor is inert, and from inside React's effects React writes the old value back over the browser's typing, either of which loses Ctrl Z (found by `ai.spec.ts`).
- **A site keeps at most 50 writing styles** (409 `kernel.writing_styles_full`), so their list and the Style picker stay one short read (module-contract-lint: lists are bounded).
- **A validator's own words reach its field** (VM Website Dev 12's finding, folded in): `errors.field_message` drops pydantic's "Value error, " for a route's 422 and a settings save alike.
- **The kit gains the icon `sparkle`,** for Write with AI and Draft the rules from the samples.
