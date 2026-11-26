// The blog in a browser (`dev plans/contracts/blog.md` §7): an editor adds a
// category on the board, writes a post in the editor, sees it under Preview and
// publishes it; a visitor finds it on the blog and reads it, the same headings
// and body the server's copy says; the board, the editor, the blog and the post
// have nothing serious for axe, in both themes. The e2e server runs with storage
// off (harness.e2e), so the post has no cover. An editor draws a cover with the
// AI (decision 0065) against the server's fake Anthropic; with storage off, the
// cover it keeps is stood in at the browser, and the contract suite keeps a real one.
import { randomBytes } from "node:crypto";

import { expect, test, type Page, type Route } from "@playwright/test";

import { THEMES, axe, makeUser, saveAiKey, signInTo, theme } from "../../../../kernel/tests/e2e/support";

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

const KEY = `sk-ant-e2e-${"e".repeat(40)}`;
/** A 1 × 1 PNG: the kept cover's file, stood in while the e2e server's storage is off. */
const PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==";

/** The site's one key, saved in Settings → AI unless one is already (ai.spec.ts saves the same).
 * Both cover tests and ai.spec save it at once, so a crossed save is tried again (cubic on #165). */
async function keyed(page: Page): Promise<void> {
  await saveAiKey(page, KEY, false);
}

test("an editor draws a cover with the AI, and the post's Cover field shows it", async ({ page }) => {
  const admin = await makeUser(page.request, "covers", { totp: true, roles: ["member", "admin"] });
  await signInTo(page, admin, "/admin/blog");
  await keyed(page);
  await page.route("**/api/blog/admin/covers", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { storage: true } });
      return;
    }
    const sent = route.request().postDataJSON() as { svg: string; alt: string };
    expect(sent.svg).toContain('id="cover-wordmark"');
    const cover = { id: "61111111-1111-4111-8111-111111111111", url: PNG, srcset: `${PNG} 2400w`, width: 2400, height: 1260, alt: sent.alt, decorative: false };
    await route.fulfill({ status: 201, json: { cover } });
  });

  await page.goto("/admin/blog/new");
  await page.getByRole("textbox", { name: "Title", exact: true }).fill(`Ten years ${randomBytes(4).toString("hex")}`);
  const opener = page.getByRole("button", { name: "Draw a cover" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Draw a cover" });
  await expect(dialog.getByRole("heading", { name: "Draw a cover" })).toBeFocused();
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `Draw a cover's ask in ${name}`).toEqual([]);
  }

  await dialog.getByRole("button", { name: "Draw", exact: true }).click();
  const drawn = dialog.getByRole("img", { name: "Words for the test." });
  await expect(drawn).toBeVisible();
  expect(await drawn.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  for (const [name, canvas] of Object.entries(THEMES)) {
    await theme(page, name, canvas);
    expect(await axe(page), `the cover drawn in ${name}`).toEqual([]);
  }

  await dialog.getByRole("textbox", { name: "Alt text" }).fill("A ring of fire on a dark ground");
  await dialog.getByRole("button", { name: "Use this cover" }).click();
  await expect(page.getByText("The cover is in place. Save the post to keep it.")).toBeVisible();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("img", { name: "A ring of fire on a dark ground" })).toBeVisible();
  await expect(opener).toBeFocused();
});

// Draw a cover's parts as the AdminPost board draws them (canvas 116; VM Website Dev 22's C1 to
// C3), at 1440 and 390 in both themes: Custom's two switch rows touching, one rule above each; the
// failure line 14px at 400 in the font's own line; Change it level with What to change's bottom,
// 10px from it.
test("Draw a cover's switch rows, failure line and Change it, as the board draws them (C1 to C3)", async ({ page }) => {
  const admin = await makeUser(page.request, "cover-parts", { totp: true, roles: ["member", "admin"] });
  await signInTo(page, admin, "/admin/blog");
  await keyed(page);
  await page.route("**/api/blog/admin/covers", (route) =>
    route.request().method() === "GET" ? route.fulfill({ json: { storage: true } }) : route.fallback(),
  );
  // The first draw fails, the next reaches the server's fake Anthropic.
  let draws = 0;
  await page.route("**/api/blog/admin/covers/draw", (route) => {
    draws += 1;
    if (draws > 1) return route.fallback();
    return route.fulfill({
      status: 502,
      contentType: "application/problem+json",
      body: JSON.stringify({ type: "urn:mechframe:problem:kernel.ai_failed", title: "Refused", status: 502, detail: "Refused.", code: "kernel.ai_failed" }),
    });
  });
  const looks = async (check: (at: string) => Promise<void>): Promise<void> => {
    for (const [name, canvas] of Object.entries(THEMES)) {
      for (const width of [1440, 390]) {
        await page.setViewportSize({ width, height: 900 });
        await theme(page, name, canvas);
        await check(`${name} at ${String(width)}`);
      }
    }
  };
  const small = (): Promise<string> =>
    page.evaluate(() => {
      const probe = document.createElement("span");
      probe.style.font = "var(--mf-type-small)";
      document.body.append(probe);
      const size = getComputedStyle(probe).fontSize;
      probe.remove();
      return size;
    });
  const danger = (): Promise<string> =>
    page.evaluate(() => {
      const probe = document.createElement("span");
      probe.style.color = "var(--mf-color-danger)";
      document.body.append(probe);
      const colour = getComputedStyle(probe).color;
      probe.remove();
      return colour;
    });

  await page.goto("/admin/blog/new");
  await page.getByRole("textbox", { name: "Title", exact: true }).fill(`Ten years ${randomBytes(4).toString("hex")}`);
  await page.getByRole("button", { name: "Draw a cover" }).click();
  const dialog = page.getByRole("dialog", { name: "Draw a cover" });
  await dialog.getByRole("combobox", { name: "Style" }).selectOption({ label: "Custom" });
  const rows = dialog.locator(".mf-switch-row");
  await expect(rows).toHaveCount(2);
  await looks(async (at) => {
    // C1: the two rows touch, a 1px rule above each.
    const first = await rows.nth(0).boundingBox();
    const second = await rows.nth(1).boundingBox();
    if (!first || !second) throw new Error("a switch row isn't drawn");
    expect.soft(second.y, at).toBeCloseTo(first.y + first.height, 0);
    for (const row of [rows.nth(0), rows.nth(1)]) {
      expect.soft(await row.evaluate((found) => getComputedStyle(found).borderTopWidth), at).toBe("1px");
    }
  });

  await dialog.getByRole("textbox", { name: "What to draw" }).fill("A ring of fire on a dark ground");
  await dialog.getByRole("button", { name: "Draw", exact: true }).click();
  const failure = dialog.getByRole("alert").filter({ hasText: /\S/ });
  await expect(failure).toBeVisible();
  await looks(async (at) => {
    // C2: the failure line 14px at 400, in the font's own line and the danger colour.
    const style = await failure.evaluate((found) => {
      const computed = getComputedStyle(found);
      return { size: computed.fontSize, weight: computed.fontWeight, line: computed.lineHeight, colour: computed.color };
    });
    expect.soft(style, at).toEqual({ size: await small(), weight: "400", line: "normal", colour: await danger() });
  });

  await dialog.getByRole("button", { name: "Draw", exact: true }).click();
  const change = dialog.getByRole("textbox", { name: "What to change" });
  await expect(change).toBeVisible();
  await change.fill("Warmer colours");
  const button = dialog.getByRole("button", { name: "Change it" });
  await looks(async (at) => {
    // C3: Change it level with the box's bottom, 10px from it.
    const box = await change.boundingBox();
    const beside = await button.boundingBox();
    if (!box || !beside) throw new Error("What to change or Change it isn't drawn");
    expect.soft(beside.y + beside.height, at).toBeCloseTo(box.y + box.height, 0);
    expect.soft(beside.x - (box.x + box.width), at).toBeCloseTo(10, 0);
  });
});

// A first load of /blog doesn't move the footer as its list arrives (decision 0066: a page that
// draws its heading first and its content once its read answers is the page's own to hold back).
// Both reads are held back 400 ms and answered here, so the list has height whatever the database
// holds; a layout-shift observer sums the shifts that moved the footer (or anything after <main>).
const SHIFTS = `
  window.__shifts = 0;
  const after = (node) => node instanceof Element && node.closest(".mf-site > #main ~ *") !== null;
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput && (entry.sources || []).some((source) => after(source.node))) window.__shifts += entry.value;
    }
  }).observe({ type: "layout-shift", buffered: true });
`;

/** A GET held back 400 ms and answered with `body`; any other method goes on to the server (cubic on #161). */
function heldBack(body: unknown) {
  return async (route: Route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  };
}

for (const [width, height] of [
  [412, 823],
  [1440, 900],
] as const) {
  test(`a first load of /blog at ${String(width)} doesn't move the footer as its posts and categories arrive`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.addInitScript(SHIFTS);
    const cards = [1, 2, 3, 4].map((at) => ({
      title: `Held post ${String(at)}`,
      slug: `held-post-${String(at)}`,
      summary: "A line about it, long enough to take a line or two on a phone.",
      cover: null,
      category: { slug: at === 4 ? "shows" : "news", label: at === 4 ? "Shows" : "News" },
      author: "Ann Example",
      published_at: "2026-11-20T12:00:00Z",
      reading_minutes: 2,
    }));
    await page.route((url) => url.pathname === "/api/blog/posts", heldBack({ items: cards, next_cursor: null }));
    await page.route(
      (url) => url.pathname === "/api/blog/categories",
      heldBack({ items: [{ slug: "news", label: "News", posts: 3 }, { slug: "shows", label: "Shows", posts: 1 }] }),
    );
    await page.goto("/blog");
    await expect(page.getByRole("link", { name: "Held post 4" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Shows" })).toBeVisible();
    await expect(page.locator(".mf-site > #main ~ footer").first()).toBeVisible();
    // Two frames after the page is in, any shift it caused has been reported.
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
    expect(await page.evaluate(() => (window as unknown as { __shifts: number }).__shifts)).toBeLessThanOrEqual(0.001);
  });
}
