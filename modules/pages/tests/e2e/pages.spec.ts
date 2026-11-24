// The pages in a browser (`dev plans/contracts/pages.md` §7): an editor writes a
// page in the editor, sees it under Preview, is asked before leaving with changes,
// publishes it into the footer's menu, and a visitor reads it at its address, the
// same words the server's copy says; the list, the editor and the page itself have
// nothing serious for axe, in both themes.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const WORDS = ":is(h1, h2, h3, p)";

/** The page's headings and paragraphs, the Updated line without its date: the page says it in the reader's own format. */
async function visibleWords(page: Page, within: string): Promise<string[]> {
  const found = await page.locator(`${within} ${WORDS}`).filter({ visible: true }).allInnerTexts();
  return found
    .map((text) => text.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .map((text) => (text.startsWith("Updated ") ? "Updated" : text));
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor writes and publishes a page, and a visitor reads it (${name})`, async ({ page, browser }) => {
    const editor = await makeUser(page.request, "pages", { totp: true, roles: ["member", "editor"] });
    const tag = randomBytes(4).toString("hex");
    const title = `Studio notes ${tag}`;
    const address = `/studio-notes-${tag}`;

    await signInTo(page, editor, "/admin/pages");
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Pages" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Pages" })).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.getByRole("link", { name: "New page" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "New page" })).toBeVisible();
    await page.getByRole("textbox", { name: "Title", exact: true }).fill(title);
    await expect(page.getByRole("textbox", { name: "Address" })).toHaveValue(address);
    await page.getByRole("textbox", { name: "Page body" }).fill("## Where we work\n\nA room with **two** windows.");
    await page.getByLabel("Menu").selectOption({ label: "Footer" });
    expect(await axe(page)).toEqual([]);

    await page.getByRole("tab", { name: "Preview" }).click();
    await expect(page.getByRole("heading", { name: "Where we work" })).toBeVisible();
    await page.getByRole("tab", { name: "Write" }).click();

    // Leaving with changes asks first; staying keeps them.
    await page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Pages" }).click();
    const asked = page.getByRole("dialog", { name: "You have changes that aren't saved" });
    await expect(asked).toBeVisible();
    await asked.getByRole("button", { name: "Stay" }).click();
    await expect(page.getByRole("textbox", { name: "Title", exact: true })).toHaveValue(title);

    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByText("Live. Saving changes the page on the site at once.")).toBeVisible();
    await expect(page).toHaveURL(/\/admin\/pages\/[0-9a-f-]{36}$/);

    // A visitor, with no session: the page, and the footer's link to it.
    const visitor = await browser.newContext();
    const reader = await visitor.newPage();
    const answer = await reader.goto(address);
    expect(answer?.status()).toBe(200);
    await theme(reader, name, canvas);
    await expect(reader.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(reader.getByRole("navigation", { name: "Footer" }).getByRole("link", { name: title })).toBeVisible();
    expect(await axe(reader)).toEqual([]);
    await visitor.close();

    // The server's copy says the same words, in the same order.
    const plain = await browser.newContext({ javaScriptEnabled: false });
    const crawler = await plain.newPage();
    await crawler.goto(address);
    const served = await visibleWords(crawler, "[data-server-copy]");
    await plain.close();
    const drawn = await browser.newContext();
    const person = await drawn.newPage();
    await person.goto(address);
    await expect(person.getByRole("heading", { level: 1, name: title })).toBeVisible();
    expect(await visibleWords(person, "main")).toEqual(served);
    await drawn.close();
  });
}
