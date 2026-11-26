# The UI kit

Every part a kernel screen or a module's page is built from (K4 contract Â§4 item 4, change 15). `@/kernel` exports all of it. Use a part before writing a component of your own (SPEC 16).

The behavior is ported from VybeSite; the look is drawn from the Vibrant Mindz admin boards (VM Website `design/generators/admin_kit.py`, `design/theme/vibrant-mindz/shell-slots.md`) on the theme's tokens alone, so Machined Light draws the same parts in its own values. The styles are `kit.css`, in the `mf.kit` cascade layer after the frames' `mf.base`.

| Part | What it's for |
| --- | --- |
| `Button`, `LinkButton` | Secondary (outlined) by default, `primary` for the page's own action, `strong` for sign-in's passkey; `small` for the top bar and a Needs-you item, `large` for the sign-in screens' 54px. A `Button` is `type="button"` unless it says otherwise |
| `QuietLink` | A link that stands on its own beside a row's buttons, as the boards draw "Open the release": the info colour at the small size, underlined only when hovered, at least 24px each way for its target. A link in running text keeps the page's look |
| `Field` with `Input`, `TextArea`, `Select` | A labelled control with its hint and its error, wired to it (`aria-describedby`, `aria-invalid`); the field's `id` is the control's. `size="large"` is sign-in's 54px; `aside` sits beside the label ("Forgot password?") |
| `Switch` | A setting that's on or off at once (`role="switch"`) |
| `BotFields`, `useBotProof` | A public form's bot check (hook 5, `kernel.bot`): the hidden trap field and the time the form was open, sent as `bot: bot.proof()` for the server to judge. The trap is off the page, out of the tab order and `aria-hidden`; the form thanks a held sender as any other |
| `Card` | A panel with an optional heading row, a `description` under its title, and actions; `flush` for a table that fills it |
| `Pill`, `Chip` | A state in words over its tint (neutral, success, warning, danger, info); a filter that's pressed or not, with a check while pressed |
| `Attention` | One "Needs you" item: what's wrong, why, and the action that fixes it; `info` for what's only worth knowing. In the admin, one with no action inside a card lies on the canvas's ground; every other note keeps the card's colour |
| `StatCard` | A dashboard card (`admin.dashboard.widget`): what it counts, its state as a pill, the figure, a line, and a link to the detail |
| `Accordion` | A collapsible section on `<details>`, remembering the reader's own choice, opening by itself when its first state is a problem (a later one keeps to its pill) |
| `Tabs` | WAI-ARIA tabs: one tab stop, arrows, Home and End; every panel stays drawn |
| `Table` | Records in a sideways scroller that keeps the focused control in view, a tab stop named by its caption while it slides; empty, its caption over the empty state. `rowHeader` names the column that names each row: its cell is the row's header, at 600 |
| `Dialog` | A modal `<dialog>` named by its heading, focus in and back |
| `UnsavedDialog`, `useUnsavedGuard`, `useLeaveGuard` | Asking before a move away loses changes: `useUnsavedGuard` with `UnsavedDialog`; `useLeaveGuard` is the blocker alone, for an editor that draws its own question, or the move is held with nothing said |
| `SaveBar` | A form's Save while it has changes, with room kept below what scrolls |
| `SaveConflict`, `settingsConflict`, `resolveConflict` | A settings save someone else got to first (`kernel.settings_conflict`) |
| `SectionHistory` | A settings section's saved versions, one click deeper |
| `ToastProvider`, `useToast` | Short notes after an action, in live regions (the provider is in every page's tree); a failure stays until it's closed |
| `EmptyState`, `LoadError` | Nothing there yet; a load that failed, said as a failure |
| `ErrorBoundary` | A part that fails to draw, kept from taking the page with it |
| `RouteFocus`, `ScrollMemory`, `landOn`, `reveal` | Focus and scroll on a move between pages, and landing on a `#place` |
| `Icon`, `ICON_NAMES` | The kit's icon set; `IconName` is one of its names |
| `QrCode` | A value as a QR code for a phone's camera (uqr's grid, one SVG path): dark on light in every theme, named by its `label`, with what it holds shown beside it as words |
| `MarkdownEditor` | Someone's Markdown (decision 0055; VM Website `AdminPost.dc.html`): Write and Preview tabs over one text, Bold, Italic, Heading, Quote and Link, Ctrl B and Ctrl I, and a module's own `tools` after them. Preview asks the module's route for the HTML `kernel.markdown.render` makes, so it shows what the page will. A button's change is typed in, so Ctrl Z takes it back |
| `Prose` | The server's cleaned HTML of someone's Markdown, in the theme's type; a link to a page here moves inside the app; a lone link a `prose.embed` player claims drawn as that player (decision 0060) |
| `TextPartsContext` | What the kernel and the modules on add to every editor (`editor.tools`) and every `Prose` (`prose.embed`), filled by `mountApp` (decision 0060); empty by default, so the kit works alone |
| `SearchBox` | A search: one 38px box, the magnifier inside, the label as its placeholder and its name; its edge a field's, the admin's ring round the box |
| `SearchFields` | Search and sharing: the title in search results and the description, each showing what an empty one becomes |

## The site's look

The site's frames (`SiteFrame`, the sign-in frame) carry `.mf-site-look`, the look of VM Website's site boards (`Auth.dc.html`, `Account.dc.html`; shell-slots.md, findings 3 to 5): the body's words at 17px, every button fully round and 44px, cards padded 28px at a 22px radius under a display title, a pill's words in the strongest colour with its tone in the dot. `.mf-text-link` draws a link, or a button that moves the page on, as underlined words. Sizes are fixed in code at the boards' values, as the admin's are (decision 0043).

## Focus, two ways

The site, sign-in and account screens keep the base outline: 2px of `color.focus`, 3px off (`frames.css`). Inside the admin (`.mf-admin-look`, on the admin frame), focus is the accent ring (`shadow.focus-ring`), as the owner set it on 2026-11-18:

- a 2px page-colour gap first on a filled or pressed control: the primary button, every switch (an off track meets the ring's line at 2.2:1 in Vibrant Mindz), anything `aria-pressed="true"`, and a field, a select or a text area (a field's edge meets the ring's line at 2.2:1 there too) (`shadow.focus-ring-gap`);
- drawn inside on a table's scroller and on a row of a clipped list, class `mf-pick` (`shadow.focus-ring-inset`);
- over the 2px edge the current nav item and the selected tab keep (`shadow.nav-current-focus`, `shadow.tab-current-focus`).

The outline turns transparent rather than off, so forced colours still draw it.

## Checked

- Vitest: the parts' tests in `src/ui/`; `RouteFocus` through `app/routes.test.tsx`, `ErrorBoundary` through `slots/slots.test.tsx`, `ScrollMemory` through `place.test.tsx`.
- Playwright on the kit's page, `harness/web/kit.html` at `/kit.html` (`kernel/tests/e2e/kit.spec.ts`): axe in both themes, the dialog open and shut; the boundary as drawn of each field, select, switch, pressed chip and filled button, 3:1 against what's behind it, and a switch's knob against its track (a secondary button or a chip that's not pressed keeps `border-strong`: its words name it, contract change 15); a field's, a select's and a text area's fill (`color.field`); the focus rings, reached with real Tab presses, the gap on an off switch as on an on one and on an admin field, a site field keeping its outline; a half-hidden button in a table's scroller brought fully into view; and the save bar keeping the focus clear of itself.
