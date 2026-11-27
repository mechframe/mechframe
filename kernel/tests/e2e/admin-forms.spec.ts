// The admin's form parts as the boards draw them (VM Website Dev 17's ask, "Kit to the boards";
// decision 0040, amended): B1 to B10 and C1 to C5, the parts every admin form shares; W2 to W4 and
// S1, Settings › Writing's own; C1's minimum dropped; T1 and T2, contact's settings. Each line is
// measured at 1440 and 390 in both themes. The boards: VM Website's `AdminAI.dc.html`,
// `AdminWriting.dc.html`, `AdminStyle.dc.html` and `AdminSettings.dc.html` (canvas version 111),
// drawn by its `admin_kit.py`. Reads whose state the shared database can't promise (no key, no
// styles, one style) are answered by a route. Last, K3, K6, P2 and P3, the parts the admin's lists
// and dashboard share (pills, tables, the stat card), on the kit's page. Then VM Website Dev 22's
// ask (`2026-11-26-kit-r-items-ask.md`, against canvas 115): R1 to R3, R6 to R9 and K9 to K12;
// and Dev 25's on #165 (`2026-11-27-kit-165-parity.md`, canvas 121): D1, a dialog's title.
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

/** A name as long as the board's "[Style name]", whose description stays beside it at 390 (R6). */
const MID_STYLE = {
  ...A_STYLE,
  id: "00000000-0000-4000-8000-0000000000a4",
  name: "Announcements",
  description: "For tours, releases and news.",
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
    // R9: the page's title in the font's own line.
    expect.soft(await styleOf(page.getByRole("heading", { level: 1, name: "Settings" }), ["line-height"]), at).toEqual({ "line-height": "normal" });
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
          body: JSON.stringify({ items: [A_STYLE, { ...A_STYLE, id: "00000000-0000-4000-8000-0000000000a2", name: "Plain" }, LONG_STYLE, MID_STYLE] }),
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
    // None of the long name hidden in its link, and a short name on the button's one line (CodeRabbit on #156).
    const hidden = await long.getByRole("link").evaluate((link) => link.scrollWidth - link.clientWidth);
    expect.soft(hidden, at).toBeLessThanOrEqual(0);
    expect.soft(name.height, at).toBeCloseTo(34, 0);
    // R6: a name as long as the board's keeps its description beside it, at 390 too.
    const mid = styles.locator("li").filter({ has: page.getByRole("link", { name: MID_STYLE.name }) });
    const midName = await boxOf(mid.getByRole("link"));
    const midWords = await boxOf(mid.getByText(MID_STYLE.description));
    expect.soft(midWords.left, at).toBeGreaterThan(midName.right);
    expect.soft(midWords.top, at).toBeLessThan(midName.bottom);
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

test("Settings › Site: contact's topics (T1, T2), the Player section and the form cards (B1)", async ({ page }) => {
  await signedInAdmin(page, "/admin/settings");
  const contact = page.locator(".mf-settings-card").filter({ has: page.getByRole("heading", { name: "Contact form" }) });
  const add = contact.getByRole("button", { name: "Add a topic" });
  await expect(add).toBeVisible();
  const player = page.locator(".mf-settings-card").filter({ has: page.locator(".mf-player-settings") });
  await expect(player.locator(".mf-player-settings")).toBeVisible();
  const newsletter = page.locator(".mf-newsletter-settings");
  await expect(newsletter).toBeVisible();
  await eachLook(page, async (at, width) => {
    if (width === 1440) expect.soft((await boxOf(contact)).width, at).toBeCloseTo(760, 0);
    // audio-player's Player section spans its card, as the board's form cards' parts do (VM Website, 2026-11-25).
    if (width === 1440) expect.soft((await boxOf(player)).width, at).toBeCloseTo(760, 0);
    const inside = await player.evaluate((card) => {
      const style = getComputedStyle(card);
      return card.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    });
    expect.soft((await boxOf(player.locator(".mf-player-settings"))).width, at).toBeCloseTo(inside, 0);
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
    // R2: text a card's parts inherit is 16px, as contact's legend shows.
    expect.soft(await styleOf(contact.locator("legend"), ["font-size"]), at).toEqual({ "font-size": "16px" });
    // R3: a module's settings section spaces its parts 18px, as the kernel's form cards do
    // (audio-player's Player, campaigns' Newsletter).
    expect.soft(await styleOf(player.locator(".mf-player-settings"), ["row-gap"]), at).toEqual({ "row-gap": "18px" });
    expect.soft(await styleOf(newsletter, ["row-gap"]), at).toEqual({ "row-gap": "18px" });
  });
});

test("Settings › Site while the Player's settings load: its Loading line at the small size (K12)", async ({ page }) => {
  // The Player section's read held back until it's measured, GET only.
  let release = (): void => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/kernel/admin/settings/audio-player", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await held;
    return route.fallback();
  });
  await signedInAdmin(page, "/admin/settings");
  const loading = page.locator(".mf-player-hint").filter({ hasText: "Loading…" });
  await expect(loading).toBeVisible();
  await eachLook(page, async (at) => {
    expect.soft(await styleOf(loading, ["font-size", "line-height"]), at).toEqual({ "font-size": await tokenSize(page, "--mf-type-small"), "line-height": "normal" });
  });
  release();
});

test("the kit's pills, a table's heads and rows' names, and a dashboard card (K3, K6, P2, P3)", async ({ page }) => {
  // VM Website's asks of 2026-11-25 (`2026-11-25-admin-music-ask.md`, items 5 and 6, and
  // `2026-11-25-statcard-ask.md`): `admin_kit.pill`, the boards' tables and AdminDashboard's `stat()`.
  await page.goto("/kit.html");
  const admin = page.locator("section.mf-admin-look").filter({ has: page.getByRole("heading", { name: "The admin's look" }) });
  await expect(admin).toBeVisible();
  const pill = admin.locator(".mf-pill").filter({ hasText: "Processing" });
  const people = admin.locator('[data-kit="people"]');
  const head = people.getByRole("columnheader", { name: "Email" });
  const name = people.getByRole("rowheader", { name: "Ann Example" });
  const cell = people.getByRole("cell", { name: "ann.example@mechframe.test" });
  const card = admin.locator(".mf-stat").filter({ hasText: "Plays this week" });
  const link = card.getByRole("link", { name: "Music" });
  const figure = card.locator(".mf-stat-value");
  const laidOut = ["font-size", "font-weight", "line-height", "color", "text-align", "vertical-align", "padding-top", "padding-left", "border-top-width"];

  await eachLook(page, async (at) => {
    // K3: a pill's words 12px at 600, in the font's own line; the pill 24px tall.
    expect.soft(await styleOf(pill, ["font-size", "font-weight", "line-height"]), at).toEqual({ "font-size": "12px", "font-weight": "600", "line-height": "normal" });
    expect.soft((await boxOf(pill)).height, at).toBeCloseTo(24, 0);
    // K6: a column's head 12px at 600, muted, in the font's own line.
    expect.soft(await styleOf(head, ["font-size", "font-weight", "line-height", "color"]), at).toEqual({
      "font-size": "12px",
      "font-weight": "600",
      "line-height": "normal",
      color: await tokenColor(page, "--mf-color-text-muted"),
    });
    // K6: a row's name at 600, laid out as its row's other cells, which stay at 400.
    const cellStyle = await styleOf(cell, laidOut);
    expect.soft(cellStyle["font-weight"], at).toBe("400");
    expect.soft(await styleOf(name, laidOut), at).toEqual({ ...cellStyle, "font-weight": "600" });
    // P2: the card's link as tall as its words, or its chevron if that's taller: no minimum.
    const chevron = (await boxOf(link.locator("svg"))).height;
    expect.soft((await boxOf(link)).height, at).toBeCloseTo(Math.max(await lineOf(link), chevron), 0);
    // P3: the figure in the font's own line.
    expect.soft(await styleOf(figure, ["line-height"]), at).toEqual({ "line-height": "normal" });
    expect.soft((await boxOf(figure)).height, at).toBeCloseTo(await lineOf(figure), 0);
  });
});

test("the kit's card title and text, its notes, a long accordion, a quiet link, a field's error and a dialog (R1, R2, R7, R8, K9 to K11, D1)", async ({ page }) => {
  await page.goto("/kit.html");
  const admin = page.locator("section.mf-admin-look").filter({ has: page.getByRole("heading", { name: "The admin's look" }) });
  await expect(admin).toBeVisible();
  const card = admin.locator(".mf-card").filter({ has: page.getByRole("heading", { name: "Recent activity" }) });
  const withAction = admin.locator(".mf-attention").filter({ hasText: "The site has no description" });
  const onPage = admin.locator(".mf-attention").filter({ hasText: "Two names aren't linked to a profile" });
  const inCard = admin.locator(".mf-card .mf-attention").filter({ hasText: "Anthropic doesn't list this model" });
  const summary = admin.locator(".mf-accordion").filter({ hasText: "Streaming links" }).locator(".mf-accordion-summary");
  const quiet = admin.getByRole("link", { name: "Open the release" });
  const error = admin.getByText("That's not an email address.");

  await eachLook(page, async (at) => {
    // R1: a card's title in the theme's section size (16px in Vibrant Mindz), in the font's own line.
    expect.soft(await styleOf(card.locator(".mf-card-title"), ["font-size", "line-height"]), at).toEqual({
      "font-size": await tokenSize(page, "--mf-type-section-title"),
      "line-height": "normal",
    });
    // R2: text a card's parts inherit is 16px.
    expect.soft(await styleOf(card.getByText("Ann Example changed the site's name."), ["font-size"]), at).toEqual({ "font-size": "16px" });
    // R8: a field's error in the font's own line.
    expect.soft(await styleOf(error, ["line-height"]), at).toEqual({ "line-height": "normal" });
    // K9: every note radius 12, its what 16px over its why 14px; on the page's ground in a card's
    // colour, inside a card on the canvas's (B10).
    for (const note of [withAction, onPage, inCard]) {
      expect.soft(await styleOf(note, ["border-top-left-radius"]), at).toEqual({ "border-top-left-radius": "12px" });
      expect.soft(await styleOf(note.locator(".mf-attention-what"), ["font-size"]), at).toEqual({ "font-size": "16px" });
      expect.soft(await styleOf(note.locator(".mf-attention-why"), ["font-size"]), at).toEqual({ "font-size": "14px" });
    }
    expect.soft(await styleOf(onPage, ["background-color"]), at).toEqual({ "background-color": await tokenColor(page, "--mf-color-surface") });
    expect.soft(await styleOf(inCard, ["background-color"]), at).toEqual({ "background-color": await tokenColor(page, "--mf-color-canvas") });
    // K10: a long description wraps beside the title, which keeps its one line, and the chevron
    // stays at the right, centred on the row.
    const title = summary.locator(".mf-accordion-title");
    const titleBox = await boxOf(title);
    const meta = await boxOf(summary.locator(".mf-accordion-meta"));
    const chevron = await boxOf(summary.locator(".mf-accordion-chevron"));
    expect.soft(titleBox.height, at).toBeCloseTo(await lineOf(title), 0);
    expect.soft(meta.left, at).toBeGreaterThan(titleBox.right);
    expect.soft(chevron.left, at).toBeGreaterThan(meta.right);
    expect.soft(chevron.middle, at).toBeCloseTo(meta.middle, 0);
    // A long title that can't break, with a state's pill: the pill and the chevron wrap under it
    // rather than running out of the summary, at 390 too (CodeRabbit on #165).
    const long = admin.locator(".mf-accordion").filter({ hasText: "TransactionalMailSettings" }).locator(".mf-accordion-summary");
    const longBox = await boxOf(long);
    for (const part of [long.locator(".mf-pill"), long.locator(".mf-accordion-chevron")]) {
      expect.soft((await boxOf(part)).right, at).toBeLessThanOrEqual(longBox.right + 0.5);
    }
    // K11: a quiet link in the info colour at the small size, no underline, 24px of target.
    expect.soft(await styleOf(quiet, ["color", "font-size", "text-decoration-line"]), at).toEqual({
      color: await tokenColor(page, "--mf-color-info"),
      "font-size": await tokenSize(page, "--mf-type-small"),
      "text-decoration-line": "none",
    });
    expect.soft((await boxOf(quiet)).height, at).toBeGreaterThanOrEqual(24);
  });

  // R7: a dialog 16px from the window's edges at 390, and 512px wide at 1440. D1 (VM Website Dev
  // 25, on #165): its title in the font's own line, as R1's card title.
  await admin.getByRole("button", { name: "Open a dialog" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete this role?" });
  await expect(dialog).toBeVisible();
  await eachLook(page, async (at, width) => {
    expect.soft(await styleOf(dialog.locator(".mf-dialog-title"), ["line-height"]), at).toEqual({ "line-height": "normal" });
    const box = await boxOf(dialog);
    if (width === 1440) {
      expect.soft(box.width, at).toBeCloseTo(512, 0);
    } else {
      expect.soft(box.left, at).toBeCloseTo(16, 0);
      expect.soft(width - box.right, at).toBeCloseTo(16, 0);
    }
  });
});
