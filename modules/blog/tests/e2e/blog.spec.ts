// The blog in a browser (`dev plans/contracts/blog.md` §7): an editor adds a
// category on the board, writes a post in the editor, sees it under Preview and
// publishes it; a visitor finds it on the blog and reads it, the same headings
// and body the server's copy says; the board, the editor, the blog and the post
// have nothing serious for axe, in both themes. The e2e server runs with storage
// off (harness.e2e), so the post has no cover.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const WORDS = ":is(h1, h2, h3, p)";

/** The page's headings and paragraphs, but the byline: its date is the reader's own format. */
async function visibleWords(page: Page, within: string): Promise<string[]> {
  const found = await page.locator(`${within} ${WORDS}`).filter({ visible: true }).allInnerTexts();
  return found
    .map((text) => text.replace(/\s+/g, " ").trim())
    .filter((text) => text && !text.endsWith("min read"));
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor writes and publishes a post, and a visitor reads it (${name})`, async ({ page, browser }) => {
    const editor = await makeUser(page.request, "blog", { totp: true, roles: ["member", "editor"] });
    const tag = randomBytes(4).toString("hex");
    const title = `Studio notes ${tag}`;
    const category = `News ${tag}`;

    await signInTo(page, editor, "/admin/blog");
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Blog" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Blog" })).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.getByRole("button", { name: "Edit categories" }).click();
    const editing = page.getByRole("dialog", { name: "Edit categories" });
    await editing.getByRole("textbox", { name: "New category" }).fill(category);
    await editing.getByRole("button", { name: "Add", exact: true }).click();
    await expect(editing.getByRole("textbox", { name: `Name of ${category}` })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await editing.getByRole("button", { name: "Done" }).click();

    await page.getByRole("link", { name: "New post" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "New post" })).toBeVisible();
    await page.getByRole("textbox", { name: "Title", exact: true }).fill(title);
    await expect(page.getByRole("textbox", { name: "Address" })).toHaveValue(`studio-notes-${tag}`);
    await page.getByRole("textbox", { name: "Post body" }).fill("## Where we work\n\nA room with **two** windows.");
    await page.getByRole("textbox", { name: "Summary" }).fill("Where the new record is made.");
    await page.getByLabel("Category").selectOption({ label: category });
    expect(await axe(page)).toEqual([]);

    await page.getByRole("tab", { name: "Preview" }).click();
    await expect(page.getByRole("heading", { name: "Where we work" })).toBeVisible();
    await page.getByRole("tab", { name: "Write" }).click();

    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByText("Live. Saving changes the post on the site at once.")).toBeVisible();
    await expect(page).toHaveURL(/\/admin\/blog\/[0-9a-f-]{36}$/);

    // A visitor, with no session: the blog lists it, and its page reads it.
    const visitor = await browser.newContext();
    const reader = await visitor.newPage();
    await reader.goto("/blog");
    await theme(reader, name, canvas);
    await expect(reader.getByRole("link", { name: title })).toBeVisible();
    expect(await axe(reader)).toEqual([]);
    await reader.getByRole("link", { name: title }).click();
    await expect(reader.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(reader.getByRole("link", { name: category })).toBeVisible();
    expect(await axe(reader)).toEqual([]);
    const address = new URL(reader.url()).pathname;
    expect(address).toBe(`/blog/studio-notes-${tag}`);
    await visitor.close();

    // The server's copy says the same headings and body, in the same order.
    const plain = await browser.newContext({ javaScriptEnabled: false });
    const crawler = await plain.newPage();
    const served = await crawler.goto(address);
    expect(served?.status()).toBe(200);
    const said = await visibleWords(crawler, "[data-server-copy]");
    await plain.close();
    const drawn = await browser.newContext();
    const person = await drawn.newPage();
    await person.goto(address);
    await expect(person.getByRole("heading", { level: 1, name: title })).toBeVisible();
    expect(await visibleWords(person, "main")).toEqual(said);
    await drawn.close();
  });
}
