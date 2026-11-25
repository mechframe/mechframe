// Social posting in a browser (`dev plans/contracts/social.md` §7): an admin saves a
// Buffer token in Settings and checks it, opens a live post's editor, shares it to
// two channels from the Share card, sees both queued, and takes one back. Buffer is
// the e2e server's fake (harness.fake_buffer), so nothing leaves. Settings and the
// editor have nothing serious for axe, in both themes.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

// The token and Buffer's channels are the site's, one of each: the two themes' runs
// take turns, or one saves over the other mid-run.
test.describe.configure({ mode: "serial" });

/** A post written and published over the API, as the signed-in admin. */
async function livePost(page: Page, title: string): Promise<string> {
  const origin = new URL(page.url()).origin;
  const headers = { Origin: origin, "Sec-Fetch-Site": "same-origin" };
  const made = await page.request.post("/api/blog/admin/posts", {
    headers,
    data: { title, slug: `share-${randomBytes(4).toString("hex")}`, body: "Words.", summary: "Where to hear it." },
  });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const published = await page.request.post(`/api/blog/admin/posts/${id}/publish`, { headers, data: {} });
  expect(published.status(), await published.text()).toBe(200);
  return id;
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an admin connects Buffer, shares a live post to two channels and takes one back (${name})`, async ({ page }) => {
    const admin = await makeUser(page.request, "social", { totp: true, roles: ["member", "admin"] });
    await signInTo(page, admin, "/admin/settings");
    await theme(page, name, canvas);
    const settings = page.getByRole("region", { name: "Social" });
    await settings.getByLabel(/Save a Buffer token|Replace the saved token/).fill(`buffer-token-for-the-e2e-${randomBytes(6).toString("hex")}`);
    await settings.getByRole("button", { name: "Save the token" }).click();
    await expect(page.getByText("Token saved. Check it to list its channels.")).toBeVisible();
    await settings.getByRole("button", { name: "Check the token" }).click();
    await expect(page.getByText("The token works: Buffer lists 5 channels.")).toBeVisible();
    await expect(settings.getByText("Instagram takes no link posts from here: a post there needs a picture or a video of its own.")).toBeVisible();
    expect(await axe(page)).toEqual([]);

    const title = `Jazz at noon ${randomBytes(3).toString("hex")}`;
    const id = await livePost(page, title);
    await page.goto(`/admin/blog/${id}`);
    await theme(page, name, canvas);
    const card = page.getByRole("region", { name: "Share" });
    await expect(card.getByRole("textbox", { name: "Text" })).toHaveValue(`${title}\n\nWhere to hear it.`);
    expect(await axe(page)).toEqual([]);

    await card.getByRole("button", { name: "@testsite (X)" }).click();
    await card.getByRole("button", { name: "Test Site (LinkedIn)" }).click();
    await card.getByRole("button", { name: "Share", exact: true }).click();
    await expect(page.getByText("Shared to 2 channels.")).toBeVisible();
    const shared = card.getByRole("list", { name: "Shared so far" }).getByRole("listitem");
    await expect(shared).toHaveCount(2);
    await expect(shared.filter({ hasText: "Queued in Buffer" })).toHaveCount(2);
    expect(await axe(page)).toEqual([]);

    await shared.first().getByRole("button", { name: "Take it back" }).click();
    await expect(page.getByText(/^Taken back from /)).toBeVisible();
    await expect(shared.filter({ hasText: "Taken back" })).toHaveCount(1);
  });
}
