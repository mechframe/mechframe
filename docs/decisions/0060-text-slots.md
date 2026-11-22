# 0060: Two text slots, `editor.tools` and `prose.embed`, drawn by the kit

- **Status:** Decided; applied in `embeds`' PR. The owner approved `dev plans/contracts/embeds.md` on 2026-11-22. The main lane agreed the same day that blog's AI writing help (decision 0058) fills `editor.tools` as a kernel entry.
- **Context:** VybeSite draws Markdown in the browser, so its post page turned a lone media link into a player as it drew. MechFrame makes Markdown HTML on the server (decision 0055), and the kit's `Prose` draws that HTML. `MarkdownEditor`'s `tools` prop lets the page that draws an editor add buttons. But the Embed button belongs in every editor (pages', blog's, any later module's), and a page may only use another module's `public.ts` when it lists that module in `requires.modules` (SPEC 7). `pages` shouldn't need `embeds` to exist, and the AI's buttons need the same reach.
- **Decision:**
  1. **Two slots, typed in `Slots`:**
     - `editor.tools`: `{id, lazy, permission?}`, the part given `{editor: MarkdownTools}`;
     - `prose.embed`: `{claims(href), lazy}`, the part given `{href, words}`.
     `defineModule` refuses an `editor.tools` entry with no `id` and a `prose.embed` entry with no `claims`.
  2. **The kit reads them through `TextPartsContext`,** never through `useSlot`, so the kit still works alone. `mountApp`'s `TextPartsFromSlots` fills it: the kernel's own editor buttons first (`KERNEL_EDITOR_TOOLS`), then the modules on, in their order, each shown only to people who hold its `permission`. It's made again only when what's shown changes, so a player keeps its state.
  3. **`MarkdownEditor`** draws them after its own buttons and the page's `tools`. A button that fails is left out.
  4. **`Prose`**, once it has drawn the server's HTML, swaps each paragraph that holds only one link (no image) that an entry claims for that entry's part, drawn through a portal. It gives the paragraph back before the text or the parts change. A part that fails draws its link again. The HTML object stays the same for the same text, so React never sets the HTML again under a player.
- **Rejected:**
  - Pages and blog each passing embeds' button as `tools`: both would require `embeds`, and every later editor would have to remember it.
  - A Markdown extension in `kernel.markdown` that writes the player's markup on the server: it would need an allowlist hole for iframes or placeholders, and the consent facade is the browser's to draw.
  - The kit calling `useSlot` itself: the kit would need the app's session and module switches to draw a button.
- **Consequences:**
  - `embeds` is the first module to fill both slots.
  - Blog's AI writing help registers in `KERNEL_EDITOR_TOOLS` and needs no change to `MarkdownEditor.tsx`.
  - A site without `embeds` draws every link as before, and the server copy never changes.
  - `SlotOutlet` takes every slot but these two (`OutletSlotName`).
