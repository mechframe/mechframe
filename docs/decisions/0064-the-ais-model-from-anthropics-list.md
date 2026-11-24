# 0064: The AI's model is picked from Anthropic's own list

- **Status:** Decided. The owner approved `dev plans/contracts/ai-model.md` as recommended on 2026-11-24. Applied in its PR.
- **Context:**
  - Settings → AI showed the model read-only: "Set on the host, as ANTHROPIC_MODEL." Changing it meant changing a host variable, and a typo there only showed when a task failed.
  - VM Website asked, for the owner, for a dropdown of the models Anthropic offers, read from Anthropic's Models API each time the page opens "so there isn't the chance of a mismatch ever" (the owner, 2026-11-24).
  - The owner's answers: `ANTHROPIC_MODEL` stays the default until a model is saved, and the saved one then wins; the dropdown holds the newest Opus, Sonnet and Haiku only; when the list can't load, the model in use is shown alone.
- **Decision:**
  1. **The saved model** is a field of the settings section `kernel.ai`, `model`, beside the key. So it's versioned, merged on a crossed save, audited by `kernel.settings_saved` and shown in the card's History. `await ai.model_in_use(db)` answers it, else `ANTHROPIC_MODEL`. `ai.client(db)` hands it to the `Writer`, and `FALLBACK_MODELS` is checked against it.
  2. **The list is read every time,** server-side with the key in use, every page, never cached: `GET /api/kernel/admin/ai/models`, for `kernel.settings.manage`. For each kind (`claude-opus-…`, `claude-sonnet-…`, `claude-haiku-…`), it keeps the newest by `created_at`, named by Anthropic's `display_name`. It also answers the model in use, and whether Anthropic lists it for the key at all.
  3. **A model is saved only through `PUT /api/kernel/admin/ai/model`,** which reads the list again and refuses an id it doesn't offer (the owner's answer 1). The settings form can't change the field. That's the new `own_route` of SPEC 7: a field registered with a sentence is refused, with 422 and that sentence, by a save `via="form"`, and saved by any other.
  4. **The list has its own budget,** 60 an hour a person (the owner's answer 2). Listing is free, and opening Settings shouldn't spend the writing help's AI_RATE_LIMIT.
  5. **A model in use that Anthropic doesn't list** (retired, or a host value with a typo) stays in the dropdown, unnamed, under a warning: "Anthropic doesn't list {id} for this key", "So the AI's writing help may fail. Choose another, or use the host's model." (the owner's answer 3). VM Website draws it on the board.
- **Rejected:**
  - **Caching the list:** the owner asked for it read when the page opens.
  - **Checking a saved model only in the browser:** the settings form would still take any id.
  - **Every model Anthropic lists, or every family:** the owner's "each kind" is the newest Opus, Sonnet and Haiku.
  - **Sharing AI_RATE_LIMIT:** a page load would spend the writing help.
- **Consequences:**
  - `ai.model()` is `ai.host_model()`, the host's alone; nothing outside the kernel called it.
  - `harness/fake_anthropic.py` lists five models, two to a page, so the suites prove every page is read and only the newest of a kind is kept. A key's check still gets one. No suite calls Anthropic.
  - `docs/contracts/auth-api.md` gains the two rows, and `GET /api/kernel/admin/ai` gains `model_source`.
  - `FALLBACK_MODELS` stays a fixed set: a newer model Anthropic lists goes without server-side fallbacks until it's added there.
