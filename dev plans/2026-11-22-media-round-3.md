# Media round 3: Admin › Media against its board (sent by VM Website)

VM Website Dev 10 took media 0.1.2 (#126) on 2026-11-22. Round 2's ten items match the AdminMedia board (canvas version 82). Two small differences are left, sent with the owner's OK, "after your contact work, no hurry". Measured board against built at 1440, with no images, first view and pick-first. The board's mockup note, its longer sidebar and its `[dimensions]` and `[date]` placeholders are expected differences.

1. **The attention alert is about 3px shorter** than the board's (about 72 against 75), so everything below it sits 3px higher. The cause is its words' line height. On the board, "what" is 16px weight 600 and "why" is 14px, both at the browser's normal, 3px apart, padding 16px 18px. This is the kit's `Attention`, so the fix changes every admin page's alert: check the kit page and parity in both themes after.
2. **The alt-text box draws the browser's resize handle**, bottom right. The board's box draws none. Give `textarea.mf-input.mf-media-alt` `resize: none`: the box keeps its 64px least height and two rows.

Done means both match in both themes, media's web tests and e2e pass (`media.spec.ts`'s "draws to its board" grows a check for each), axe is clean, and VM Website Dev 10 gets the PR number. The alert's fix is a kit change (decision 0042, amended again, no number); the box's is media 0.1.3.
