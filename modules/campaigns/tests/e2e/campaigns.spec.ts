// The newsletter in a browser (`dev plans/contracts/campaigns.md` §7): a person who
// signed up confirms from the email's link, then unsubscribes from the page every
// newsletter links to; an admin sets the postal address, writes an email, sends
// themselves a test and finds it on the Newsletter page's tabs. Each page has nothing
// serious for axe, in both themes. NewsletterSignup is drawn by a site's own
// sections, so its states are the web tests'.
import { randomBytes } from "node:crypto";

import { expect, test, type APIRequestContext } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

// The kernel's bot check holds a form sent faster than this (hook 5).
const PERSON = { website: "", elapsed_ms: 5_000 };

/** The newest confirm link mailed to `to`, its path and query, waiting for it to be sent. */
async function confirmLink(request: APIRequestContext, to: string): Promise<string> {
  let found = "";
  await expect
    .poll(
      async () => {
        const answer = await request.get(`/api/_test/mail?to=${encodeURIComponent(to)}`);
        const { messages } = (await answer.json()) as { messages: { text: string }[] };
        const link = messages.map((message) => /https?:\/\/[^/\s]+(\/newsletter\/confirm\?token=\S+)/.exec(message.text)?.[1]).filter(Boolean).at(-1);
        found = link ?? "";
        return found !== "";
      },
      { timeout: 10_000 },
    )
    .toBe(true);
  return found;
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`a sign-up confirms, then unsubscribes from the link (${name})`, async ({ browser }) => {
    const address = `fan-${randomBytes(4).toString("hex")}@example.com`;
    const visitor = await browser.newContext();
    const page = await visitor.newPage();
    const signed = await page.request.post("/api/campaigns/subscribe", { data: { email: address, bot: PERSON } });
    expect(signed.status()).toBe(202);
    const confirm = await confirmLink(page.request, address);

    await page.goto(confirm);
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Confirm your subscription" })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await page.getByRole("button", { name: "Confirm" }).click();
    const done = page.getByRole("status");
    await expect(done.getByRole("heading", { name: "You're subscribed" })).toBeVisible();
    await expect(done).toBeFocused();
    expect(await axe(page)).toEqual([]);

    await page.goto(confirm.replace("/newsletter/confirm", "/newsletter/unsubscribe"));
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Unsubscribe from the newsletter" })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await page.getByRole("button", { name: "Unsubscribe" }).click();
    await expect(page.getByRole("heading", { name: "You're unsubscribed" })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await visitor.close();
  });

  test(`an admin writes an email, tests it and finds it on the Newsletter page (${name})`, async ({ page }) => {
    const tag = randomBytes(4).toString("hex");
    const admin = await makeUser(page.request, "campaigns", { totp: true, roles: ["member", "admin"] });
    await signInTo(page, admin, "/admin/campaigns");
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Newsletter" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Newsletter" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Subscribed" })).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.getByRole("link", { name: "New email" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "New email" })).toBeVisible();
    await page.getByRole("textbox", { name: "Subject" }).fill(`Winter shows ${tag}`);
    await page.getByRole("textbox", { name: "Preview text" }).fill("Three nights in December");
    await page.getByRole("textbox", { name: "Email body" }).fill("Three nights in **December**.");
    expect(await axe(page)).toEqual([]);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page).toHaveURL(/\/admin\/campaigns\/[0-9a-f-]{36}$/);
    await page.getByRole("tab", { name: "Preview" }).click();
    await expect(page.getByText("December", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Send a test to me" }).click();
    await expect(page.getByText(`A test is on its way to ${admin.email}.`)).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.goto("/admin/campaigns");
    await theme(page, name, canvas);
    await expect(page.getByRole("table").getByText(`Winter shows ${tag}`)).toBeVisible();
    for (const tab of ["Subscribers", "Set aside"]) {
      await page.getByRole("tab", { name: tab }).click();
      await expect(page.getByRole("tab", { name: tab })).toHaveAttribute("aria-selected", "true");
      expect(await axe(page)).toEqual([]);
    }
  });
}

test("the Settings section saves the postal address", async ({ page }) => {
  const owner = await makeUser(page.request, "campaigns-owner", { totp: true, roles: ["member", "owner"] });
  await signInTo(page, owner, "/admin/settings");
  const address = page.getByRole("textbox", { name: "Postal address" });
  await expect(address).toBeVisible();
  const typed = `P.O. Box ${String(Date.now() % 10_000)}\nBoston, MA 02101`;
  await address.fill(typed);
  expect(await axe(page)).toEqual([]);
  // Saved and read back, not only typed (CodeRabbit on #134).
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Settings saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Postal address" })).toHaveValue(typed);
});
