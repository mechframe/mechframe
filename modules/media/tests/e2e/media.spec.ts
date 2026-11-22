// The media library's admin page in a browser (`dev plans/contracts/media.md`):
// an editor reaches it from the sidebar, sees the empty library and its
// Upload, is told plainly that uploads need the public bucket (the e2e server
// runs with storage off, harness.e2e), and axe finds nothing serious, in both themes.
import { expect, test } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor opens the media library, and an upload says it needs the public bucket (${name})`, async ({ page }) => {
    const editor = await makeUser(page.request, "media", { totp: true, roles: ["member", "editor"] });
    await signInTo(page, editor, "/admin/media");
    await theme(page, name, canvas);

    await expect(page.getByRole("heading", { level: 1, name: "Media" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Media" })).toBeVisible();
    await expect(page.getByText("No images yet")).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.getByLabel("Upload an image").setInputFiles({
      name: "photo.png",
      mimeType: "image/png",
      buffer: Buffer.from("89504e470d0a1a0a", "hex"),
    });
    await expect(page.getByText(/Uploads need the public bucket/)).toBeVisible();
  });
}
