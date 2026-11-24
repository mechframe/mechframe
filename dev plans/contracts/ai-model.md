---
feature: The AI's model, chosen in Settings › AI from Anthropic's own list (decision 0064; VM Website Dev 14's ask, sent with the owner's OK, 2026-11-24)
status: approved
approved: 2026-11-24, as recommended ("Approve as recommended"): §8's three answers
pr: #144
plan: after blog 0.1.3 (the owner, 2026-11-24); `dev plans/2026-11-23-next-session-m4h-blog-covers.md` §4
ask: `C:\DEV\VM Website\dev plans\2026-11-24-ai-model-dropdown-ask.md`; the board "Admin: Settings, AI" (`AdminAI.dc.html`, canvas version 101), its words in VM Website's `design/generators/test_ai_boards.py`, `DRAWN_AHEAD`
---

# Contract: the AI's model, from Anthropic's list

## 1. Goal

Settings › AI's Model row stops being read-only ("Set on the host, as ANTHROPIC_MODEL."). It becomes a dropdown of Anthropic's newest Opus, Sonnet and Haiku, read from Anthropic's Models API each time the page opens, so the model saved can only be one Anthropic offers the key. The host's `ANTHROPIC_MODEL` is used until a model is saved. Once one is, the saved model wins, and "Use the host's model" clears it. These are the owner's answers, given 2026-11-24.

## 2. Interfaces

**The model in use.** `await ai.model_in_use(db) -> tuple[str, ModelSource]`, where `ModelSource = Literal["settings", "environment"]`. It answers the saved model, else `ANTHROPIC_MODEL`, which already defaults to `claude-opus-5-5` in `config.py`. `ai.client(db)` hands it to the `Writer`, and `FALLBACK_MODELS` is checked against it, so a saved model is treated just as the host's would be. The sync `ai.model()` is renamed `ai.host_model()`, the host's alone.

**The saved model** is one more field in the settings section `kernel.ai`: `model: str | None = None`, beside `api_key`. A value must look like a model id (`claude-` followed by lowercase letters, digits, dots and hyphens, at most 100 characters), or the save answers 422. Since it's part of the section, it's versioned, merged on a crossed save and shown in the card's History, like the key. Saving it records `kernel.settings_saved` with `changed: ["model"]` and `via: "ai.model"`: in the activity log, as every settings save is.

**A field saved only by its own route** (SPEC 7). `settings.register(module_id, model, *, own_route: Mapping[str, str] = {})` names the fields the generic `PUT /admin/settings/{id}` may not change. Each field carries the sentence that route answers: 422 `kernel.invalid_request`, with `errors[field]`. `settings.save(..., via="form")` refuses them, and any other `via` may save them. `kernel.ai` registers `{"model": "Choose the model from Anthropic's list, in Settings → AI."}`, so only the route below saves it, and always after checking the list.

**HTTP**, under `/api/kernel`, both for `kernel.settings.manage` (as `GET /admin/ai` is), neither with step-up (as no settings save has):

- **`GET /admin/ai/models`** asks Anthropic, server-side with the key in use, every time (no cache), reading every page of `client.models.list`. It answers:
  ```json
  {"models": [{"id": "claude-opus-5-5", "name": "Claude Opus 5.5"}, ...],
   "in_use": {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "source": "environment", "listed": true}}
  ```
  - **The list:** for each family, the newest by `created_at` (`claude-opus-…`, `claude-sonnet-…`, `claude-haiku-…`, read from the id), in the order Opus, Sonnet, Haiku. Its `name` is Anthropic's `display_name`. Other families stay out (Fable, say).
  - **`in_use`:** the model in use and where it comes from. `listed` is false when Anthropic doesn't list it for this key at all (a retired model, or a host value with a typo); its `name` is then null. The page always shows the model in use, even when it isn't the newest of its kind.
  - **No working key:** 503 `kernel.ai_off` or `kernel.ai_key_unreadable`, as today. The page reads either as "Anthropic's model list loads once a key works."
  - **Anthropic unreachable, slow (15 s) or refusing the key:** 502 `kernel.ai_failed`, in `_refusal`'s words, never the key or Anthropic's own words. The page reads it as "Couldn't load Anthropic's model list, so the model in use is the only one shown.", with Try again.
  - **Its own budget,** `rate_limit("60/1h", key="account", scope="kernel.ai.models")`, then 429 `kernel.rate_limited`. A list costs nothing, so opening the page doesn't spend AI_RATE_LIMIT's writing budget (§8, 2).
- **`PUT /admin/ai/model`** takes `{version: int ≥ 0, model: string | null}`, strict, `version` being the section's, as the settings form reads it.
  - **`null`** is "Use the host's model": the saved model is cleared. No list is read.
  - **An id** is checked against the list, read again at that moment. It must be one the dropdown offers (the newest of its family), or the save answers 422 `kernel.invalid_request`, `errors.model`: "Anthropic doesn't offer that model to this key now. Choose one from the list." A list that can't be read answers the GET's 503 or 502, and nothing is saved.
  - It answers 200 `SettingsSaved` (`{version, changed, merged}`), as the generic save does, and the same 409 `kernel.settings_conflict` when a crossed save changed the model too.

**`GET /admin/ai`** keeps its shape: `model` is now the model in use, and it gains `model_source` (`settings` | `environment`).

**The fake.** `harness/fake_anthropic.py`'s models list answers what a real key sees: Opus 5.5, Opus 5, Sonnet 5.5, Haiku 5.5 and Fable 5.1, two to a page, honouring `limit` and `after_id`. That proves every page is read and only the newest Opus is kept. A key's check, at `limit=1`, still gets one. Tests queue a refusal or a slow answer as they do for messages. No suite calls Anthropic.

**Web**, `kernel/web/src/ai/AiSettings.tsx`, in the board's words (`DRAWN_AHEAD`):
- **The row:** Model, a `Select` of the list by name, with the hint "Anthropic's newest model of each kind, listed when this page opens." The model in use is selected, and added as its own option when it isn't one of the three.
- **Under it,** by source: "The AI's writing help uses the host's model, ANTHROPIC_MODEL, until one is saved here." or "The AI's writing help uses the model saved here."
- **Buttons:**
  - **Save the model**, primary, on once another model is picked. It says "Saved the model." and reads the list and the section again.
  - **Use the host's model**, shown while one is saved.
- **No working key:** the select is off, holding the model in use alone, with "Anthropic's model list loads once a key works." It loads by itself once a key is saved and checked.
- **The list failed:** the select is off, holding the model in use alone, with "Couldn't load Anthropic's model list, so the model in use is the only one shown." and Try again.
- **Not listed** (`listed: false`): an `Attention` above the row, in §8, 3's words, until VM Website draws it.
- **History** labels the field `model` as Model.

## 3. Data

None. `kernel.ai`'s values gain `model`, a key that's absent until a model is saved. There's no migration, and `kernel_0017` stays free.

## 4. Files

- **Backend:**
  - `kernel/backend/kernel/ai.py`: `model` in `KeySettings`, `model_in_use`, `host_model`, the `Writer`'s model, and `models(writer)`, the list filtered.
  - `ai_routes.py`: the two routes and `model_source`.
  - `settings.py`: `own_route`.
  - `config.py`: ANTHROPIC_MODEL's comment ("until a model is saved in Settings › AI").
  - `app.py`, where `kernel.ai`'s settings are registered: `own_route`.
- **Harness:** `harness/fake_anthropic.py`: the models list.
- **Web:** `kernel/web/src/ai/AiSettings.tsx` and `AiSettings.test.tsx`; `words.ts`, if the problems' words live there.
- **Generated:**
  - `kernel/openapi.json` and the web's `schema.ts` (`python -m tools.openapi`, `npm run api:types`);
  - `docs/HOST-VARIABLES.md` (`python -m tools.host_variables`).
- **Docs:**
  - `SPEC.md` 6 (`ai.client`'s row: the model in use) and 7 (settings: a field saved only by its own route), plus the change log;
  - `docs/decisions/0064-the-ais-model-from-anthropics-list.md`;
  - `dev plans/contracts/kernel-ai.md`, a line under "Changes after approval" pointing here;
  - `docs/progress.json`, then `python -m tools.progress`.

## 5. Conventions this follows

- `CLAUDE.md`, Rules: tests first, one logical change per PR.
- Decision 0058: the key never reaches the browser, failures are plain sentences, and no suite calls Anthropic.
- Settings saves are conditional, versioned and audited (SPEC 7, `kernel.settings`).
- `POST /admin/ai/check`'s 15-second wait and its refusal words.
- The board's words, `DRAWN_AHEAD`, word for word.

## 6. Non-goals

- No cache of the list, as the owner asked: each page open and each save reads it.
- No family other than Opus, Sonnet and Haiku, and no older model of theirs to pick (the owner's "each kind").
- No model per task, per writing style or per module. A module's own task (a generated cover) uses the model in use.
- No prices, context sizes or other details from the list.
- `FALLBACK_MODELS` stays a fixed set. A newer model Anthropic lists goes without server-side fallbacks until it's added there.

## 7. Acceptance

- **`kernel/tests/test_ai.py`:**
  - `test_the_model_in_use_is_the_saved_one_then_the_hosts`;
  - `test_the_list_is_the_newest_of_each_kind_from_every_page`: from the fake's five, Opus 5.5, Sonnet 5.5 and Haiku 5.5, in that order;
  - `test_a_saved_model_gets_the_fallbacks_as_the_hosts_would`;
  - `test_a_model_that_is_not_an_id_is_refused`.
- **`kernel/tests/test_settings.py`:** `test_a_field_with_its_own_route_is_refused_by_the_form`, with a positive control: the same change through `via="ai.model"` saves.
- **`kernel/tests/contract/test_ai_contract.py`:**
  - `test_get_admin_ai_models`: 200 with `in_use` and its source; 503 with no key and with an unreadable one; 502 when Anthropic refuses or is slow; 403 without `kernel.settings.manage`; 429 past the budget;
  - `test_put_admin_ai_model`: saves an offered model and `GET /admin/ai` then answers it with `settings`; 422 for one not offered, and for `model` through the generic settings route; `null` clears it; 409 for a crossed save; nothing saved when the list fails.
- **`AiSettings.test.tsx`,** one test for each of the board's Tweaks states: Host's key, Model picked, Model saved, Model list failed (Try again reads it again) and No key.
- **End to end:** `ai.spec.ts`, "A model saved in Settings › AI is used, and Use the host's model clears it", against the fake, in both themes.
- **Live:** none in the suites. Your first real list is Settings › AI opened with a working key.

## 8. Open questions

None. The owner's answers, 2026-11-24, as recommended:
1. **The checked save:** a model is saved only from the dropdown, through `PUT /admin/ai/model`, and the generic settings route refuses it (`own_route`, SPEC 7). It's the one way "never a mismatch" holds.
2. **The list's budget:** its own, 60 an hour a person, not AI_RATE_LIMIT's shared 20. A list is free, and opening Settings shouldn't use up the writing help.
3. **A model in use that Anthropic no longer lists** (a retired one, or a host value with a typo): an attention above the row says "Anthropic doesn't list {id} for this key, so the AI's writing help may fail. Choose another, or use the host's model." VM Website draws it as a sixth Tweaks state, or sends the words it wants instead.

## Changes after approval

- 2026-11-24, as built (#144):
  - **The answer is built by `ai.offer(listed, model, source)`,** from `ai.newest_of_each_kind` and `Writer.models()`, which answers every model as an `ai.Listed`. So a model in use that Anthropic doesn't list is held by a unit test, `test_a_model_in_use_that_anthropic_no_longer_lists_is_unnamed`. Over HTTP the harness's model is always listed, and the route refuses an unlisted one.
  - **A slow or unreachable list** is held by `test_a_list_that_is_slow_or_unreachable_is_a_plain_failure`, not over HTTP. The contract suite holds a refusing Anthropic (401) for the read, and a failing one (500) for the save.
  - **The budget** has a test of its own, `test_the_model_list_has_its_own_budget`: the 61st read is 429, and the writing help still answers.
  - **The warning** is the kit's `Attention`, in the words of VM Website's Model not listed state (canvas version 102): "Anthropic doesn't list {id} for this key, so the AI's writing help may fail." as its what, "Choose another, or use the host's model." as its why. The model in use, when it isn't one of the three, is listed first.
  - **The toasts** say "Saved the model." and "Using the host's model." The second isn't on the board yet.
  - **The settings form's refusal** reads "Choose the model from Anthropic's list, in Settings → AI.", with the kernel's arrow, as its other words have it.
  - **`docs/HOST-VARIABLES.md`'s ANTHROPIC_MODEL line** comes from `tools/host_variables.py`, which says "until an admin saves one in Settings → AI".
  - **A pick keeps the version it began at** (Codex on #144): the section read again meanwhile, by a key saved or another admin's save, never moves it, so a crossed save of the model is a 409, not an overwrite. Use the host's model sends the version read.
  - **From CodeRabbit on #144:**
    - The settings form's check compares a routed field with the form's own version, not the stored value. So a stale form sending the model as it read it merges and keeps the route's newer one, while changing it is still refused.
    - A read of the list that fails after one that worked shows the model in use alone, not the list kept from before.
    - The budget test spends the writing budget with a draft, which `GET /ai` never did.
    - A routed secret, replaced or cleared through the form, is refused too, since a typed secret is a change (its second look).
    - Each has a test seen failing first.
