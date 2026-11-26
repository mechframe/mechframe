// The AI's writing help, as Chromium draws it (decision 0058; `dev plans/contracts/kernel-ai.md` §7):
// an admin saves a key in Settings → AI and checks it, keeps the writing rules and a style in
// Settings → Writing, and a writer drafts a post with Write with AI; axe finds nothing serious on
// either tab or in the dialog, in either theme. The Model row lists Anthropic's newest of each kind,
// and a model saved there is used until Use the host's model clears it (decision 0064). Every AI
// call goes to the harness's fake Anthropic.
import { expect, test, type Locator, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, saveAiKey, signInTo, theme } from "./support";

const KEY = `sk-ant-e2e-${"e".repeat(40)}`;

// The site has one key: two tests saving it at once would be a conflict, as two admins' are.
test.describe.configure({ mode: "serial" });

async function signedInAdmin(page: Page, next: string): Promise<void> {
  const user = await makeUser(page.request, "ai", { totp: true, roles: ["member", "admin"] });
  await signInTo(page, user, next);
}

/** A key saved in Settings → AI, from the page itself, tried again if it crosses another spec's
 * save of the site's one key (cubic on #165). */
async function keyed(page: Page): Promise<void> {
  await saveAiKey(page, KEY);
  await expect(page.getByRole("status").filter({ hasText: "uses the key saved here" })).toBeVisible();
}

test("an admin saves a key, checks it, and never sees it again", async ({ page }) => {
  await signedInAdmin(page, "/admin/settings/ai");
  await keyed(page);
  await expect(page.getByLabel("Replace the saved key")).toHaveValue("");
  await page.getByRole("button", { name: "Check the key" }).click();
  await expect(page.getByText("The saved key works.")).toBeVisible();
  expect(await page.content()).not.toContain(KEY);
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `Settings → AI in ${name}`).toEqual([]);
  }
});

test("a model saved in Settings → AI is used, and Use the host's model clears it", async ({ page }) => {
  await signedInAdmin(page, "/admin/settings/ai");
  await keyed(page);
  const model = page.getByRole("combobox", { name: "Model" });
  await expect(model).toBeEnabled();
  await expect(model.getByRole("option")).toHaveText(["Claude Opus 5.5", "Claude Sonnet 5.5", "Claude Haiku 5.5"]);
  await expect(page.getByText("The AI's writing help uses the host's model, ANTHROPIC_MODEL, until one is saved here.")).toBeVisible();
  await model.selectOption("claude-sonnet-5-5");
  await page.getByRole("button", { name: "Save the model" }).click();
  await expect(page.getByText("Saved the model.")).toBeVisible();
  await expect(page.getByText("The AI's writing help uses the model saved here.")).toBeVisible();
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `Settings → AI's model in ${name}`).toEqual([]);
  }
  await page.getByRole("button", { name: "Use the host's model" }).click();
  await expect(page.getByText("Using the host's model.")).toBeVisible();
  await expect(model).toHaveValue("claude-opus-5-5");
  await expect(page.getByRole("button", { name: "Use the host's model" })).toHaveCount(0);
});

/** `locator`'s box, in CSS pixels. */
async function boxOf(locator: Locator): Promise<{ top: number; bottom: number; middle: number; right: number }> {
  const box = await locator.boundingBox();
  if (!box) throw new Error("not drawn");
  return { top: box.y, bottom: box.y + box.height, middle: box.y + box.height / 2, right: box.x + box.width };
}

const FAILED = "Couldn't load Anthropic's model list, so the model in use is the only one shown.";

for (const [name, canvas] of Object.entries(THEMES)) {
  // VM Website Dev 16's A1 to A4 (`2026-11-24-admin-ai-parity.md`): the Model row as its board draws it,
  // in its Model list failed state, which shows all four.
  test(`the Model row sits as its board draws it, at 1440 and 390, in ${name}`, async ({ page }) => {
    await page.route("**/api/kernel/admin/ai/models", (route) =>
      route.fulfill({
        status: 502,
        contentType: "application/problem+json",
        body: JSON.stringify({ type: "urn:mechframe:problem:kernel.ai_failed", title: "Refused", status: 502, detail: "Refused.", code: "kernel.ai_failed" }),
      }),
    );
    await signedInAdmin(page, "/admin/settings/ai");
    const key = page.getByRole("form", { name: "Anthropic key" });
    const row = page.getByRole("form", { name: "Model" });
    await expect(row.getByText(FAILED)).toBeVisible();
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await theme(page, name, canvas);
      const at = `at ${String(width)}`;
      // A1: a 1px rule above the row, 18px from the key's form and 18px from the row's first line.
      const rule = await row.evaluate((form) => {
        const style = getComputedStyle(form);
        return { width: style.borderTopWidth, style: style.borderTopStyle, below: style.paddingTop };
      });
      expect.soft(rule, at).toEqual({ width: "1px", style: "solid", below: "18px" });
      expect.soft((await boxOf(row)).top - (await boxOf(key)).bottom, at).toBeCloseTo(18, 0);
      // A2: where the model comes from, first.
      const label = row.locator("label", { hasText: /^Model$/ });
      expect.soft((await boxOf(row.getByRole("status"))).bottom, at).toBeLessThan((await boxOf(label)).top);
      // A3: the state's sentence is the select's one hint.
      await expect.soft(row.getByRole("combobox", { name: "Model" }), at).toHaveAccessibleDescription(FAILED);
      await expect.soft(page.getByText("Anthropic's newest model of each kind, listed when this page opens."), at).toHaveCount(0);
      // A4: Try again on the label's line, centred on it, at the row's right.
      const again = await boxOf(row.getByRole("button", { name: "Try again" }));
      expect.soft(again.middle, at).toBeCloseTo((await boxOf(label)).middle, 0);
      expect.soft(again.right, at).toBeCloseTo((await boxOf(row)).right, 0);
    }
  });
}

test("the writing rules and a style are kept in Settings → Writing", async ({ page }) => {
  await signedInAdmin(page, "/admin/settings/writing");
  const rule = page.getByRole("switch", { name: "At most one em dash a piece" });
  await rule.click();
  await page.getByRole("textbox", { name: "About the site" }).fill("A record label from the end-to-end run.");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Writing rules saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("switch", { name: "At most one em dash a piece" })).not.toBeChecked();
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `Settings → Writing in ${name}`).toEqual([]);
  }

  await page.getByRole("link", { name: "New style" }).click();
  const named = `Warm ${String(Date.now())}`;
  await page.getByRole("textbox", { name: "Name", exact: true }).fill(named);
  await page.getByRole("textbox", { name: "Sample 1" }).fill("We play loud and we play late.");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Style saved.")).toBeVisible();
  await expect(page).toHaveURL(/\/admin\/settings\/writing\/styles\/[0-9a-f-]{36}$/);
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `a writing style in ${name}`).toEqual([]);
  }
});

test("a writer drafts a post with Write with AI, and Ctrl Z takes it back", async ({ page }) => {
  await signedInAdmin(page, "/admin/settings/ai");
  await keyed(page);
  await page.goto("/admin/blog/new");
  const body = page.getByRole("textbox", { name: "Post body" });
  await expect(body).toHaveValue("");
  await page.getByRole("button", { name: "Write with AI" }).click();
  const dialog = page.getByRole("dialog", { name: "Write with AI" });
  await expect(dialog.getByRole("button", { name: "Titles" })).toBeVisible();
  await dialog.getByRole("textbox", { name: "What should it be about?" }).fill("Our spring tour");
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `Write with AI in ${name}`).toEqual([]);
  }
  await dialog.getByRole("button", { name: "Write the draft" }).click();
  await expect(body).toHaveValue("Words for the test.");
  await expect(dialog).toBeHidden();
  await body.focus();
  await page.keyboard.press("ControlOrMeta+z");
  await expect(body).toHaveValue("");
});
