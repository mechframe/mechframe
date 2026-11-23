# Media round 3: Admin › Media against its board (sent by VM Website)

VM Website Dev 10 took media 0.1.2 (#126) on 2026-11-22. Round 2's ten items match the AdminMedia board (canvas version 82). Two small differences are left, sent with the owner's OK, "after your contact work, no hurry". Measured board against built at 1440, with no images, first view and pick-first. The board's mockup note, its longer sidebar and its `[dimensions]` and `[date]` placeholders are expected differences.

1. **The attention alert is about 3px shorter** than the board's (about 72 against 75), so everything below it sits 3px higher. The cause is its words' line height. On the board, "what" is 16px weight 600 and "why" is 14px, both at the browser's normal, 3px apart, padding 16px 18px. This is the kit's `Attention`, so the fix changes every admin page's alert: check the kit page and parity in both themes after.
2. **The alt-text box draws the browser's resize handle**, bottom right. The board's box draws none. Give `textarea.mf-input.mf-media-alt` `resize: none`: the box keeps its 64px least height and two rows.

Done means both match in both themes, media's web tests and e2e pass (`media.spec.ts`'s "draws to its board" grows a check for each), axe is clean, and VM Website Dev 10 gets the PR number. The alert's fix is a kit change (decision 0042, amended again, no number); the box's is media 0.1.3.

## Result (2026-11-22, session M4e)

Both, in one PR (#131).

1. **The alert.** Measured in Chromium with Geist loaded, the board's box is 75.8px: "what" is 16px at Geist's normal line height (20.8px), "why" is 14px (18.4px), 3px apart, inside 16px by 18px. The kit drew "what" at the theme's type.body, which is 15px in Vibrant Mindz (20px a line), so the box came to 75.4px by the same sum. The kit's `.mf-attention-what` now sets 1rem (16px) over the why's type.small, in every theme. Machined Light's body was already 16px, so nothing changes there. Every part of the alert now matches the board, and the kit page's new check finds nothing else in the box beyond those two lines, in both themes.
   - VM Website's fontsource Geist (5.3.0) and Google's Geist draw the same normal line height (1.3), so a different font file can't explain it. If parity still measures about 72 against 75, the 3px is on the site's side: check that Geist has loaded when the measurement runs.
2. **The alt box:** `textarea.mf-input.mf-media-alt` has `resize: none` and keeps its 64px least height and two rows (media 0.1.3).

Checked by the kit page's new check (`kit.spec.ts`, the alert's words in both themes) and two more checks in `media.spec.ts`'s "draws to its board" (no resize handle; the alert's "what" at 16px). Both failed before the fix. The whole end-to-end suite (104 tests) passes, axe clean, along with the web tests (890), lint, typecheck and mypy.
