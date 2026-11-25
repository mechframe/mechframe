// The admin's form parts as the boards draw them (VM Website Dev 17's ask, "Kit to the boards";
// decision 0040, amended): B1 to B10 and C1 to C5, the parts every admin form shares; W2 to W4 and
// S1, Settings › Writing's own; C1's minimum dropped; T1 and T2, contact's settings. Each line is
// measured at 1440 and 390 in both themes. The boards: VM Website's `AdminAI.dc.html`,
// `AdminWriting.dc.html`, `AdminStyle.dc.html` and `AdminSettings.dc.html` (canvas version 111),
// drawn by its `admin_kit.py`. Reads whose state the shared database can't promise (no key, no
// styles, one style) are answered by a route.
import { expect, test, type Locator, type Page } from "@playwright/test";

import { THEMES, makeUser, signInTo, theme } from "./support";

const WIDTHS = [1440, 390] as const;

type Box = { top: number; bottom: number; left: number; right: number; width: number; height: number; middle: number };

async function boxOf(locator: Locator): Promise<Box> {
  const box = await locator.boundingBox({ timeout: 5_000 });
  if (!box) throw new Error("not drawn");
  return { top: box.y, bottom: box.y + box.height, left: box.x, right: box.x + box.width, width: box.width, height: box.height, middle: box.y + box.height / 2 };
}

/** `locator`'s computed styles, by their CSS names. */
async function styleOf(locator: Locator, names: readonly string[]): Promise<Record<string, string>> {
  return locator.evaluate(
    (found, wanted) => {
      const style = getComputedStyle(found);
      return Object.fromEntries(wanted.map((name) => [name, style.getPropertyValue(name)]));
    },
    names,
    { timeout: 5_000 },
  );
}

/** A theme token's colour as the browser computes it. */
async function tokenColor(page: Page, token: string): Promise<string> {
  return page.evaluate((name) => {
    const probe = document.createElement("span");
    probe.style.color = `var(${name})`;
    document.body.append(probe);
    const colour = getComputedStyle(probe).color;
    probe.remove();
    return colour;
  }, token);
}

/** A type token's size as the browser computes it: the boards' sizes are Vibrant Mindz's tokens. */
async function tokenSize(page: Page, token: string): Promise<string> {
  return page.evaluate((name) => {
    const probe = document.createElement("span");
    probe.style.font = `var(${name})`;
    document.body.append(probe);
    const size = getComputedStyle(probe).fontSize;
    probe.remove();
    return size;
  }, token);
}

/** One line of `locator`'s font at its line height, in pixels: the boards' heights are Geist's
 * own lines (14px a line 18px), and the harness draws whichever font the machine has. */
async function lineOf(locator: Locator): Promise<number> {
  return locator.evaluate((found) => {
    const style = getComputedStyle(found);
    const probe = document.createElement("span");
    probe.style.cssText = `position: absolute; display: block; font: ${style.font}; line-height: ${style.lineHeight}; white-space: nowrap`;
    probe.textContent = "Line";
    document.body.append(probe);
    const height = probe.getBoundingClientRect().height;
    probe.remove();
    return height;
  });
}

async function signedInAdmin(page: Page, next: string): Promise<void> {
  const user = await makeUser(page.request, "forms", { totp: true, roles: ["member", "admin"] });
  await signInTo(page, user, next);
}

function problem(status: number, code: string) {
  return {
    status,
    contentType: "application/problem+json",
    body: JSON.stringify({ type: `urn:mechframe:problem:${code}`, title: "Refused", status, detail: "Refused.", code }),
  };
}

const MODELS = "**/api/kernel/admin/ai/models";
const STYLES = "**/api/kernel/admin/writing/styles";
const STYLE_ID = "00000000-0000-4000-8000-0000000000a1";
const A_STYLE = {
  id: STYLE_ID,
  version: 1,
  name: "Warm",
  description: "For news the site is glad to share.",
  voice_rules: "Short sentences.",
  avoid: "",
  samples: ["We play loud and we play late."],
};

/** The longest name a style may have (80 characters, no space) and a long description. */
const LONG_STYLE = {
  ...A_STYLE,
  id: "00000000-0000-4000-8000-0000000000a3",
  name: "Unbroken".repeat(10),
  description: "For the long announcements that need every word: tours, releases, collaborations and the stories behind them.",
};

/** Each width in each theme, the page laid out again for it. */
async function eachLook(page: Page, check: (at: string, width: number) => Promise<void>): Promise<void> {
  for (const [name, canvas] of Object.entries(THEMES)) {
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      await theme(page, name, canvas);
      await check(`${name} at ${String(width)}`, width);
    }
  }
}

test("Settings › AI: the field's parts, the select, History and the warning (B2 to B10)", async ({ page }) => {
  // The saved model isn't listed (B10's warning), and the list read once more fails with no key (B9).
  let reads = 0;
  await page.route(MODELS, (route) => {
    reads += 1;
    return reads === 1
      ? route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            models: [{ id: "claude-opus-5-5", name: "Claude Opus 5.5" }],
            in_use: { id: "claude-opus-4-typo", name: null, source: "settings", listed: false },
          }),
        })
      : route.fulfill(problem(503, "kernel.ai_off"));
  });
  await signedInAdmin(page, "/admin/settings/ai");
  const card = page.locator(".mf-settings-card").first();
  const keyField = page.getByLabel(/^(Save a key|Replace the saved key)$/);
  await expect(keyField).toBeVisible();
  const warning = page.locator(".mf-attention").filter({ hasText: "doesn't list claude-opus-4-typo" });
  await expect(warning).toBeVisible();

  await eachLook(page, async (at) => {
    // B2: the card's description 14px.
    expect.soft(await styleOf(card.locator(".mf-card-description"), ["font-size"]), at).toEqual({ "font-size": "14px" });
    // B3: a label at 400, in the theme's meta size (13px in Vibrant Mindz).
    const label = card.locator("label").filter({ hasText: /^(Save a key|Replace the saved key)$/ });
    expect.soft(await styleOf(label, ["font-size", "font-weight"]), at).toEqual({ "font-size": await tokenSize(page, "--mf-type-meta"), "font-weight": "400" });
    // B4: the hint under its control, 12px at 400.
    const hint = card.getByText("From the Anthropic console. It's kept sealed and never shown again.");
    expect.soft((await boxOf(hint)).top, at).toBeGreaterThan((await boxOf(keyField)).bottom);
    expect.soft(await styleOf(hint, ["font-size", "font-weight"]), at).toEqual({ "font-size": "12px", "font-weight": "400" });
    // B5: a form card's buttons 34px.
    expect.soft((await boxOf(card.getByRole("button", { name: "Save the key" }))).height, at).toBeCloseTo(34, 0);
    // B6: the boards' chevron, 16px, 10px from the select's right edge, centred; 30px of room.
    const select = card.getByRole("combobox", { name: "Model" });
    expect.soft(await styleOf(select, ["appearance", "padding-right"]), at).toEqual({ appearance: "none", "padding-right": "30px" });
    const chevron = await boxOf(card.locator(".mf-select-chevron"));
    const selected = await boxOf(select);
    // The box is the select's own height, so the chevron centres on the select (cubic on #156).
    expect.soft((await boxOf(card.locator(".mf-select-box"))).height, at).toBeCloseTo(selected.height, 0);
    expect.soft(chevron.width, at).toBeCloseTo(16, 0);
    expect.soft(selected.right - chevron.right, at).toBeCloseTo(10, 0);
    expect.soft(chevron.middle, at).toBeCloseTo(selected.middle, 0);
    // B7: History 51px tall in Geist (its title's line, 14px above and below, and its edges),
    // radius 12, its title 16px.
    const history = card.locator(".mf-accordion").last();
    expect.soft((await boxOf(history)).height, at).toBeCloseTo((await lineOf(history.locator(".mf-accordion-title"))) + 30, 0);
    expect.soft(await styleOf(history, ["border-top-left-radius"]), at).toEqual({ "border-top-left-radius": "12px" });
    expect.soft(await styleOf(history.locator(".mf-accordion-title"), ["font-size"]), at).toEqual({ "font-size": "16px" });
    // B8: a note's lines at the font's own height.
    expect.soft(await styleOf(card.locator(".mf-ai-note").first(), ["line-height"]), at).toEqual({ "line-height": "normal" });
    // B10: a warning with nothing to click, on the canvas's ground, radius 12.
    expect.soft(await styleOf(warning, ["background-color", "border-top-left-radius"]), at).toEqual({
      "background-color": await tokenColor(page, "--mf-color-canvas"),
      "border-top-left-radius": "12px",
    });
  });

  // B9: a select that's off is at 55% (the list read again, with no key now).
  await page.reload();
  const off = page.getByRole("combobox", { name: "Model" });
  await expect(off).toBeDisabled();
  await eachLook(page, async (at) => {
    expect.soft(await styleOf(off, ["opacity"]), at).toEqual({ opacity: "0.55" });
  });
});

test("Settings › Writing: the card, its head, the rule rows, The brief and the styles (B1, C1, C2, C5, W2 to W4)", async ({ page }) => {
  await page.route(STYLES, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [A_STYLE, { ...A_STYLE, id: "00000000-0000-4000-8000-0000000000a2", name: "Plain" }, LONG_STYLE] }),
        })
      : route.fallback(),
  );
  await signedInAdmin(page, "/admin/settings/writing");
  const rules = page.locator(".mf-settings-card").filter({ has: page.getByRole("heading", { name: "Writing rules" }) });
  const styles = page.locator(".mf-settings-card").filter({ has: page.getByRole("heading", { name: "Writing styles" }) });
  await expect(rules.getByRole("switch").first()).toBeVisible();
  await expect(styles.getByRole("link", { name: "Plain" })).toBeVisible();
  // W2: a rule switched off says its warning in the warning colour.
  const invent = rules.getByRole("switch", { name: "Never invent customers, quotes, reviews or numbers" });
  if ((await invent.getAttribute("aria-checked")) === "true") await invent.click();
  const ftc = rules.getByText(/banned by the FTC/);
  await expect(ftc).toBeVisible();

  await eachLook(page, async (at, width) => {
    // B1: a one-column form's card stops at 760px.
    const card = await boxOf(rules);
    if (width === 1440) expect.soft(card.width, at).toBeCloseTo(760, 0);
    else expect.soft(card.width, at).toBeLessThan(760);
    // C2: the head's button on the title's line, centred on it; the description under both.
    const title = await boxOf(rules.getByRole("heading", { name: "Writing rules" }));
    const save = await boxOf(rules.getByRole("button", { name: "Save", exact: true }));
    const description = await boxOf(rules.locator(".mf-card-description"));
    expect.soft(save.middle, at).toBeCloseTo(title.middle, 0);
    expect.soft(description.top - save.bottom, at).toBeCloseTo(8, 0);
    // C5: a rule above each switch row, 12px above and below its words, the rows touching; the
    // name 16px at 400, its hint 13px; the switch with no edge.
    const rows = rules.locator(".mf-switch-row");
    const first = await boxOf(rows.nth(0));
    const second = await boxOf(rows.nth(1));
    expect.soft(second.top, at).toBeCloseTo(first.bottom, 0);
    expect.soft(await styleOf(rows.nth(1), ["border-top-width", "padding-top", "padding-bottom"]), at).toEqual({
      "border-top-width": "1px",
      "padding-top": "12px",
      "padding-bottom": "12px",
    });
    expect.soft(await styleOf(rows.nth(1).locator(".mf-switch-label"), ["font-size", "font-weight"]), at).toEqual({ "font-size": "16px", "font-weight": "400" });
    expect.soft(await styleOf(rows.nth(1).locator(".mf-field-hint"), ["font-size"]), at).toEqual({ "font-size": await tokenSize(page, "--mf-type-meta") });
    expect.soft(await styleOf(rows.nth(1).getByRole("switch"), ["border-top-width"]), at).toEqual({ "border-top-width": "0px" });
    // W2: the warning's colour.
    expect.soft(await styleOf(ftc, ["color"]), at).toEqual({ color: await tokenColor(page, "--mf-color-warning") });
    // W3: the form's parts 18px apart; a rule above The brief, 18px over its title, which is 15px.
    const mode = await boxOf(rules.getByRole("combobox", { name: "Rules" }));
    expect.soft(first.top - mode.bottom, at).toBeCloseTo(18, 0);
    const brief = rules.locator(".mf-ai-brief");
    const briefTitle = brief.getByRole("heading", { name: "The brief" });
    expect.soft(await styleOf(brief, ["border-top-width"]), at).toEqual({ "border-top-width": "1px" });
    expect.soft((await boxOf(briefTitle)).top - (await boxOf(brief)).top, at).toBeCloseTo(19, 0);
    expect.soft(await styleOf(briefTitle, ["font-size"]), at).toEqual({ "font-size": "15px" });
    // C1: a text box's lines at the font's own height, as tall as its rows with no minimum, its
    // padding and edges 20px: 3 rows 74px and 4 rows 92px in Geist.
    const about = rules.getByRole("textbox", { name: "About the site" });
    const added = rules.getByRole("textbox", { name: "Rules of our own" });
    expect.soft(await styleOf(about, ["line-height", "min-height"]), at).toEqual({ "line-height": "normal", "min-height": "0px" });
    expect.soft((await boxOf(about)).height, at).toBeCloseTo(3 * (await lineOf(about)) + 20, 0);
    expect.soft((await boxOf(added)).height, at).toBeCloseTo(4 * (await lineOf(added)) + 20, 0);
    // W4: a rule above each style, 12px above and below; its description 14px beside the name, in the soft colour.
    const style = styles.locator("li").first();
    expect.soft(await styleOf(style, ["border-top-width", "padding-top", "padding-bottom"]), at).toEqual({
      "border-top-width": "1px",
      "padding-top": "12px",
      "padding-bottom": "12px",
    });
    const name = await boxOf(style.getByRole("link", { name: "Warm" }));
    const words = style.getByText("For news the site is glad to share.");
    expect.soft((await boxOf(words)).left, at).toBeGreaterThan(name.right);
    expect.soft(await styleOf(words, ["font-size", "color"]), at).toEqual({ "font-size": "14px", color: await tokenColor(page, "--mf-color-text") });
    // The longest name a style may have stays inside the card, its description too, at 390 as well
    // (Codex, cubic and CodeRabbit on #156).
    const list = await boxOf(styles.locator(".mf-ai-styles"));
    const long = styles.locator("li").filter({ has: page.getByRole("link", { name: LONG_STYLE.name }) });
    expect.soft((await boxOf(long.getByRole("link"))).right, at).toBeLessThanOrEqual(list.right + 0.5);
    expect.soft((await boxOf(long.locator(".mf-ai-style-line"))).right, at).toBeLessThanOrEqual(list.right + 0.5);
  });
});

test("Settings › Writing with no styles: the card's empty state is a dashed box (C3)", async ({ page }) => {
  await page.route(STYLES, (route) =>
    route.request().method() === "GET" ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) }) : route.fallback(),
  );
  await signedInAdmin(page, "/admin/settings/writing");
  const empty = page.locator(".mf-card > .mf-empty");
  await expect(empty.getByText("No writing styles yet")).toBeVisible();
  await eachLook(page, async (at) => {
    expect.soft(
      await styleOf(empty, ["border-top-style", "border-top-width", "border-top-color", "border-top-left-radius", "padding-top", "padding-left", "text-align"]),
      at,
    ).toEqual({
      "border-top-style": "dashed",
      "border-top-width": "1px",
      "border-top-color": await tokenColor(page, "--mf-color-border-strong"),
      "border-top-left-radius": "12px",
      "padding-top": "28px",
      "padding-left": "16px",
      "text-align": "center",
    });
    expect.soft(await styleOf(empty.locator(".mf-empty-title"), ["font-size"]), at).toEqual({ "font-size": "16px" });
  });
});

test("A writing style's page: the Writing tab marked, and its delete dialog (S1, C4, B5)", async ({ page }) => {
  await page.route(`${STYLES}/${STYLE_ID}`, (route) =>
    route.request().method() === "GET" ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(A_STYLE) }) : route.fallback(),
  );
  await signedInAdmin(page, `/admin/settings/writing/styles/${STYLE_ID}`);
  await expect(page.getByRole("textbox", { name: "Name", exact: true })).toHaveValue("Warm");
  // S1: the page a style belongs to.
  await expect(page.getByRole("navigation", { name: "Settings" }).getByRole("link", { name: "Writing" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await eachLook(page, async (at) => {
    // C4: the dialog's lead 14px, in the muted colour.
    expect.soft(await styleOf(dialog.locator(".mf-dialog-lead"), ["font-size", "color"]), at).toEqual({
      "font-size": "14px",
      color: await tokenColor(page, "--mf-color-text-muted"),
    });
    // B5: a dialog's buttons 34px.
    for (const button of await dialog.getByRole("button").all()) expect.soft((await boxOf(button)).height, at).toBeCloseTo(34, 0);
  });
});

test("Settings › Site: contact's topics (T1, T2) and the form cards (B1)", async ({ page }) => {
  await signedInAdmin(page, "/admin/settings");
  const contact = page.locator(".mf-settings-card").filter({ has: page.getByRole("heading", { name: "Contact form" }) });
  const add = contact.getByRole("button", { name: "Add a topic" });
  await expect(add).toBeVisible();
  await eachLook(page, async (at, width) => {
    if (width === 1440) expect.soft((await boxOf(contact)).width, at).toBeCloseTo(760, 0);
    // T1: Add a topic as wide as its words.
    expect.soft((await boxOf(add)).width, at).toBeLessThan(200);
    // T2: a topic's First as a field's label (13px in Vibrant Mindz), muted, at 400, with no rule above it.
    const first = contact.locator(".mf-switch-row").first();
    expect.soft(await styleOf(first.locator(".mf-switch-label"), ["font-size", "font-weight", "color"]), at).toEqual({
      "font-size": await tokenSize(page, "--mf-type-meta"),
      "font-weight": "400",
      color: await tokenColor(page, "--mf-color-text-muted"),
    });
    expect.soft(await styleOf(first, ["border-top-width"]), at).toEqual({ "border-top-width": "0px" });
  });
});
