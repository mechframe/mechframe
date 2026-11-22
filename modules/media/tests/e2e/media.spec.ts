// The media library's admin page in a browser (`dev plans/contracts/media.md`):
// an editor reaches it from the sidebar, sees the empty library and its
// Upload, is told plainly that uploads need the public bucket (the e2e server
// runs with storage off, harness.e2e), and axe finds nothing serious, in both themes.
import { expect, test } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor opens the media library, and an upload says it needs the public bucket (${name})`, async ({ page }) => {
    const editor = await makeUser(page.request, "media", { totp: true, roles: ["member", "editor"] });
    await signInTo(page, editor, "/admin/media");
    await theme(page, name, canvas);

    await expect(page.getByRole("heading", { level: 1, name: "Media" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Media" })).toBeVisible();
    await expect(page.getByText("No images yet")).toBeVisible();
    expect(await axe(page)).toEqual([]);

    await page.getByLabel("Upload an image").setInputFiles({
      name: "photo.png",
      mimeType: "image/png",
      buffer: Buffer.from("89504e470d0a1a0a", "hex"),
    });
    await expect(page.getByText(/Uploads need the public bucket/)).toBeVisible();
  });
}

// The page against its board (VM Website's AdminMedia, canvas version 82; media's round 2,
// `dev plans/2026-11-22-media-round-2.md`). The e2e server has no storage, so the library's
// answers and its pictures are stubbed here; the layout is the browser's own.
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

function picture(id: string, filename: string, alt: string | null) {
  return {
    id,
    url: `/media-fixture/${id}.png`,
    srcset: `/media-fixture/${id}.png 1000w`,
    width: 1000,
    height: 1000,
    bytes: 48_000,
    content_type: "image/png",
    filename,
    alt,
    decorative: false,
    uploaded_by: "Pat",
    created_at: "2026-11-21T12:00:00+00:00",
    version: 1,
  };
}

const HERO = picture("33333333-3333-4333-8333-333333333333", "catalyst-hero3.webp", null);
const COVER = picture("44444444-4444-4444-8444-444444444444", "catalyst-cover.webp", "Catalyst album cover");

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`the page draws to its board: the panel level with the grid, the board's tiles, pill, box and words (${name})`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1229 });
    await page.route(
      (url) => url.pathname.startsWith("/media-fixture/"),
      (route) => route.fulfill({ contentType: "image/png", body: PNG }),
    );
    await page.route(
      (url) => url.pathname === "/api/media/admin/images",
      (route) => route.fulfill({ json: { items: [HERO, COVER], next_cursor: null, missing_alt: 1 } }),
    );
    await page.route(
      (url) => url.pathname === `/api/media/admin/images/${HERO.id}`,
      (route) => route.fulfill({ json: { ...HERO, uses: [{ label: "The Catalyst post", link: "/admin/blog" }] } }),
    );
    const editor = await makeUser(page.request, "media-board", { totp: true, roles: ["member", "editor"] });
    await signInTo(page, editor, "/admin/media");
    await theme(page, name, canvas);
    await page.getByRole("button", { name: "catalyst-hero3.webp, no alt text" }).click();
    await expect(page.getByRole("link", { name: "The Catalyst post" })).toBeVisible();

    const drawn = await page.evaluate(() => {
      const one = (selector: string) => {
        const found = document.querySelector(selector);
        if (!(found instanceof HTMLElement)) throw new Error(`nothing matches ${selector}`);
        return found;
      };
      const probe = document.createElement("span");
      probe.style.color = "var(--mf-color-info)";
      document.body.append(probe);
      const info = getComputedStyle(probe).color;
      probe.style.backgroundColor = "transparent";
      const clear = getComputedStyle(probe).backgroundColor;
      probe.remove();
      const tile = one(".mf-media-thumb");
      const tiled = getComputedStyle(tile);
      const pill = one(".mf-media-thumb .mf-pill");
      const decoration = getComputedStyle(one(".mf-media-describe .mf-switch-label"));
      return {
        panelTop: one(".mf-media-panel").getBoundingClientRect().top,
        gridTop: one(".mf-media-grid").getBoundingClientRect().top,
        tileCorner: tiled.borderTopLeftRadius,
        tileInside: tile.getBoundingClientRect().width - 2 * parseFloat(tiled.borderLeftWidth) - 2 * parseFloat(tiled.paddingLeft),
        pillWidth: pill.getBoundingClientRect().width,
        pillSize: getComputedStyle(pill).fontSize,
        altHeight: one(".mf-media-alt").getBoundingClientRect().height,
        hintWeight: getComputedStyle(one(".mf-media-hint")).fontWeight,
        decoration: { size: decoration.fontSize, weight: decoration.fontWeight },
        usedIn: getComputedStyle(one(".mf-media-uses a")).color,
        info,
        // The kit's items: the boards' normal line height on labels and leads, and a search box with no fill.
        lines: [".mf-admin-page-lead", ".mf-attention-why", ".mf-media-thumb-name", ".mf-media-facts", ".mf-media-muted"].map(
          (selector) => `${selector} ${getComputedStyle(one(selector)).lineHeight}`,
        ),
        searchFill: getComputedStyle(one(".mf-search")).backgroundColor,
        clear,
        searchSize: getComputedStyle(one(".mf-search-input")).fontSize,
      };
    });

    expect(Math.abs(drawn.panelTop - drawn.gridTop)).toBeLessThanOrEqual(1);
    expect(drawn.tileCorner).toBe("12px");
    expect(Math.abs(drawn.pillWidth - drawn.tileInside)).toBeLessThanOrEqual(1);
    expect(drawn.pillSize).toBe("12px");
    expect(drawn.altHeight).toBeCloseTo(64, 0);
    expect(drawn.hintWeight).toBe("400");
    expect(drawn.decoration).toEqual({ size: "16px", weight: "400" });
    expect(drawn.usedIn).toBe(drawn.info);
    expect(drawn.lines).toEqual([
      ".mf-admin-page-lead normal",
      ".mf-attention-why normal",
      ".mf-media-thumb-name normal",
      ".mf-media-facts normal",
      ".mf-media-muted normal",
    ]);
    expect(drawn.searchFill).toBe(drawn.clear);
    expect(drawn.searchSize).toBe("14px");
    expect(await axe(page)).toEqual([]);
  });
}
