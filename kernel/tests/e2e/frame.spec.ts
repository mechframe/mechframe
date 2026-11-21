// The site frame with a site's own header and footer, and a page that runs
// full bleed (dev plans/contracts/site-frame.md; decision 0048, amended), on
// the harness's frame page (harness/web/frame.html, at /frame.html), in both
// themes: the bleed page edge to edge and the next page's padding back, one
// of each landmark, the skip link first, and nothing serious for axe.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const THEMES = {
  "machined-light": "rgb(236, 236, 234)",
  "vibrant-mindz": "rgb(7, 10, 22)",
} as const;

async function open(page: Page, theme: string, canvas: string): Promise<void> {
  await page.goto("/frame.html");
  await expect(page.getByRole("heading", { level: 1, name: "Edge to edge" })).toBeVisible();
  // The new theme's colours fade in where a part has a transition: measure once they've landed.
  await page.evaluate(async (name) => {
    document.documentElement.dataset.theme = name;
    document.body.getBoundingClientRect();
    await Promise.all(document.getAnimations().map((animation) => animation.finished));
  }, theme);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor)).toBe(canvas);
}

/** The main's padding, side by side: top, right, bottom, left. */
async function padding(page: Page): Promise<string[]> {
  return page.getByRole("main").evaluate((main) => {
    const style = getComputedStyle(main);
    return [style.paddingTop, style.paddingRight, style.paddingBottom, style.paddingLeft];
  });
}

async function axe(page: Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return violations.filter((each) => each.impact === "serious" || each.impact === "critical").map((each) => `${each.id}: ${each.help}`);
}

for (const [theme, canvas] of Object.entries(THEMES)) {
  test.describe(theme, () => {
    test("a page that runs full bleed is edge to edge, and the next page gets its padding back", async ({ page }) => {
      await open(page, theme, canvas);
      const width = await page.evaluate(() => document.documentElement.clientWidth);
      const hero = await page.locator(".frame-hero").boundingBox();
      expect(hero?.x).toBe(0);
      expect(hero?.width).toBe(width);
      expect(await padding(page)).toEqual(["0px", "0px", "0px", "0px"]);

      await page.getByRole("link", { name: "An ordinary page" }).click();
      await expect(page.getByRole("heading", { level: 1, name: "An ordinary page" })).toBeVisible();
      expect(await padding(page)).toEqual(["16px", "16px", "16px", "16px"]);
      // The site's header and footer stay: the page changed without a reload.
      await expect(page.getByText("The site's own footer")).toBeVisible();
    });

    test("has one banner, one main and one contentinfo, the site's, with the skip link first", async ({ page }) => {
      await open(page, theme, canvas);
      await expect(page.getByRole("banner")).toHaveCount(1);
      await expect(page.getByRole("main")).toHaveCount(1);
      await expect(page.getByRole("contentinfo")).toHaveCount(1);
      await expect(page.getByRole("banner")).toHaveClass("frame-header");
      await expect(page.getByRole("contentinfo")).toHaveClass("frame-footer");
      await expect(page.getByRole("navigation", { name: "Site" })).toHaveCount(0);

      await page.keyboard.press("Tab");
      await expect(page.getByRole("link", { name: "Skip to the content" })).toBeFocused();
      await page.keyboard.press("Tab");
      expect(await page.evaluate(() => document.activeElement?.closest("header")?.className)).toBe("frame-header");
      await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
    });

    test("axe finds nothing serious on the bleed page or the ordinary one", async ({ page }) => {
      await open(page, theme, canvas);
      expect(await axe(page)).toEqual([]);
      await page.getByRole("link", { name: "An ordinary page" }).click();
      await expect(page.getByRole("heading", { level: 1, name: "An ordinary page" })).toBeVisible();
      expect(await axe(page)).toEqual([]);
    });
  });
}
