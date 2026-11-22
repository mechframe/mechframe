// The contact module in a browser (`dev plans/contracts/contact.md` §7): a visitor
// writes from /contact and is thanked, an admin finds the message in the Inbox's
// New tab, opens it and marks it replied; the Contact page, its thanks and the
// Inbox have nothing serious for axe, in both themes, and the page says the same
// words as the server's copy.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const WORDS = ":is(h1, h2, h3, p, li)";
// The kernel's bot check holds a form sent faster than this (hook 5).
const FILL_MS = 3_200;

async function visibleWords(page: Page, within: string): Promise<string[]> {
  const found = await page.locator(`${within} ${WORDS}`).filter({ visible: true }).allInnerTexts();
  return found.map((text) => text.replace(/\s+/g, " ").trim()).filter(Boolean);
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`a visitor writes, and an admin reads it in the Inbox (${name})`, async ({ page, browser }) => {
    const tag = randomBytes(4).toString("hex");
    const sender = `Rae ${tag}`;

    const visitor = await browser.newContext();
    const writer = await visitor.newPage();
    const answer = await writer.goto("/contact");
    expect(answer?.status()).toBe(200);
    await theme(writer, name, canvas);
    await expect(writer.getByRole("heading", { level: 1, name: "Contact" })).toBeVisible();
    await expect(writer.getByRole("navigation", { name: "Footer" }).getByRole("link", { name: "Contact" })).toBeVisible();
    expect(await axe(writer)).toEqual([]);

    // Nothing sent until the fields are filled: the first one says so.
    await writer.getByRole("button", { name: "Send message" }).click();
    await expect(writer.getByRole("textbox", { name: "Name" })).toBeFocused();
    await expect(writer.getByText("Enter your name.")).toBeVisible();
    expect(await axe(writer)).toEqual([]);

    await writer.getByRole("textbox", { name: "Name" }).fill(sender);
    await writer.getByRole("textbox", { name: "Email" }).fill(`rae-${tag}@example.com`);
    await writer.getByLabel("What it's about").selectOption({ label: "Working together" });
    await writer.getByRole("textbox", { name: "Message" }).fill("Could you play a night in March?");
    await writer.waitForTimeout(FILL_MS);
    await writer.getByRole("button", { name: "Send message" }).click();
    const thanks = writer.getByRole("status");
    await expect(thanks.getByRole("heading", { name: "Message sent" })).toBeVisible();
    await expect(thanks).toBeFocused();
    expect(await axe(writer)).toEqual([]);
    await visitor.close();

    const admin = await makeUser(page.request, "contact", { totp: true, roles: ["member", "admin"] });
    await signInTo(page, admin, "/admin/contact?tab=new");
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Inbox" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Inbox" })).toBeVisible();
    const row = page.getByRole("list", { name: "Messages" }).getByRole("link", { name: new RegExp(sender) });
    await expect(row).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await row.click();
    await expect(page.getByRole("heading", { level: 2, name: sender })).toBeVisible();
    await expect(page.getByRole("link", { name: "Reply by email" })).toHaveAttribute("href", /^mailto:rae-/);
    expect(await axe(page)).toEqual([]);
    await page.getByRole("button", { name: "Mark as replied" }).click();
    await expect(page.getByText("Marked as replied.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Mark as replied" })).toHaveCount(0);
  });
}

test("the Contact page says the same words as the server's copy", async ({ browser }) => {
  const plain = await browser.newContext({ javaScriptEnabled: false });
  const crawler = await plain.newPage();
  await crawler.goto("/contact");
  const served = await visibleWords(crawler, "[data-server-copy]");
  await plain.close();
  expect(served.slice(0, 2)).toEqual(["Contact", "Send a message and we'll reply by email."]);

  const drawn = await browser.newContext();
  const person = await drawn.newPage();
  await person.goto("/contact");
  await expect(person.getByRole("heading", { level: 1, name: "Contact" })).toBeVisible();
  await expect(person.getByText("Send a message and we'll reply by email.")).toBeVisible();
  expect((await visibleWords(person, "main")).slice(0, 2)).toEqual(served.slice(0, 2));
  await drawn.close();
});
