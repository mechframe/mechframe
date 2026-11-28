// Reactions in a browser (`dev plans/contracts/reactions.md` §7): on a live post, a
// reader who isn't signed in sees the counts, and pressing Fire takes them to sign
// in and back; a member then presses Fire, sees it pressed with 1, and takes it
// back. The row has nothing serious for axe, in both themes.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { PASSWORD, THEMES, axe, makeUser, theme, totp } from "../../../../kernel/tests/e2e/support";

/** A post an editor writes and publishes over the API, the editor signed out after: its path. */
async function livePost(page: Page): Promise<string> {
  await page.goto("/");
  const headers = { Origin: new URL(page.url()).origin, "Sec-Fetch-Site": "same-origin" };
  const editor = await makeUser(page.request, "reactions-editor", { totp: true, roles: ["member", "editor"] });
  const signed = await page.request.post("/api/auth/sign-in", { headers, data: { email: editor.email, password: PASSWORD } });
  expect(signed.status(), await signed.text()).toBe(200);
  const { challenge } = (await signed.json()) as { challenge: string };
  const second = await page.request.post("/api/auth/sign-in/second-factor", { headers, data: { challenge, totp: totp(editor.totp) } });
  expect(second.status(), await second.text()).toBe(200);
  const slug = `react-${randomBytes(4).toString("hex")}`;
  const made = await page.request.post("/api/blog/admin/posts", { headers, data: { title: "Catalyst is out", slug, body: "Words." } });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const published = await page.request.post(`/api/blog/admin/posts/${id}/publish`, { headers, data: {} });
  expect(published.status(), await published.text()).toBe(200);
  await page.context().clearCookies();
  return `/blog/${slug}`;
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`a reader signs in from a reaction, presses Fire and takes it back (${name})`, async ({ page }) => {
    const path = await livePost(page);
    await page.goto(path);
    await theme(page, name, canvas);
    const row = page.getByRole("group", { name: "Reactions" });
    await expect(row.getByRole("button", { name: "Fire, 0" })).toHaveAttribute("aria-pressed", "false");
    await expect(row.getByRole("button", { name: "Love, 0" })).toBeVisible();
    await expect(row.getByRole("button", { name: "Mind blown, 0" })).toBeVisible();
    // The Post board's figures and line (VM Website Dev 28's X1 and X2): the font's own
    // figures in a count, and a pill's line height normal, not its type token's 1.3.
    for (const pill of await row.getByRole("button").all()) {
      await expect(pill).toHaveCSS("line-height", "normal");
      await expect(pill.locator(".mf-reaction-count")).toHaveCSS("font-variant-numeric", "normal");
    }
    expect(await axe(page)).toEqual([]);

    await row.getByRole("button", { name: "Fire, 0" }).click();
    await expect(page).toHaveURL(`/sign-in?next=${encodeURIComponent(path)}`);
    const member = await makeUser(page.request, "reactions-member");
    await page.getByLabel("Email").fill(member.email);
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(path);

    await theme(page, name, canvas);
    await page.getByRole("group", { name: "Reactions" }).getByRole("button", { name: "Fire, 0" }).click();
    const pressed = page.getByRole("group", { name: "Reactions" }).getByRole("button", { name: "Fire, 1" });
    await expect(pressed).toHaveAttribute("aria-pressed", "true");
    expect(await axe(page)).toEqual([]);

    await page.reload();
    await expect(page.getByRole("group", { name: "Reactions" }).getByRole("button", { name: "Fire, 1" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("group", { name: "Reactions" }).getByRole("button", { name: "Fire, 1" }).click();
    await expect(page.getByRole("group", { name: "Reactions" }).getByRole("button", { name: "Fire, 0" })).toHaveAttribute("aria-pressed", "false");
  });
}
