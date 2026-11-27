// The music library in a browser (`dev plans/contracts/discography.md` §7), in three
// tests run in order for each theme, so each ends within its 30 seconds at the end of a
// full run (0.1.4): an editor makes a release on the Albums board, adds a SoundCloud
// track and a credit in the album editor and publishes it; the Tracks and Credits
// boards show them, each in the theme (a page loaded afresh starts in the default); a
// Tracks and Credits name each row by its track or person, at 600 (0.1.3, the kit's
// rowHeader, VM Website's K6); a credit's row stacks where it's narrow and no
// paragraph laid out as a row keeps the browser's margins (VM Website's P3 and P1). A
// visitor finds it at /music and opens it: Play album, the row's play and the
// Player docked at the window's foot, with SoundCloud's credit (0.1.1, audio-player's
// contract §7), and its track's page with the player's bar. Nothing loads from
// SoundCloud until Play is pressed. Each board and page has nothing serious for axe,
// in both themes, at 1440 and at a phone's 390. The e2e server runs with storage
// off (harness.e2e), so no track is uploaded here: the contract suite uploads one
// through the job, and audio-player's own spec plays a real file.
import { randomBytes } from "node:crypto";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
] as const;

/** axe at each width, the page as it is. */
async function cleanAtEachWidth(page: Page): Promise<void> {
  for (const size of WIDTHS) {
    await page.setViewportSize(size);
    expect(await axe(page)).toEqual([]);
  }
  await page.setViewportSize(WIDTHS[0]);
}

/** No paragraph laid out as a row keeps the browser's margins (VM Website's P1). */
async function rowsUnmargined(page: Page): Promise<void> {
  const margins = await page.locator("p.mf-music-row").evaluateAll((nodes) =>
    nodes.map((node) => {
      const style = getComputedStyle(node);
      return `${style.marginTop} ${style.marginBottom}`;
    }),
  );
  expect.soft(margins.length).toBeGreaterThan(0);
  expect.soft([...new Set(margins)]).toEqual(["0px 0px"]);
}

/**
 * A credit's row at each width (VM Website's P3): stacked, its role on a line of its own and its
 * name most of the row's width under it, beside the remove button; else role and name side by side.
 */
async function creditRowAtEachWidth(page: Page, row: Locator, stacked: (width: number) => boolean): Promise<void> {
  for (const size of WIDTHS) {
    await page.setViewportSize(size);
    const at = `${String(size.width)}px`;
    const [whole, role, name] = await Promise.all([
      row.boundingBox(),
      row.getByRole("combobox", { name: "Role" }).boundingBox(),
      row.getByRole("textbox", { name: "Name" }).boundingBox(),
    ]);
    if (!whole || !role || !name) throw new Error(`the credit's row isn't drawn at ${at}`);
    if (stacked(size.width)) {
      expect.soft(name.y, at).toBeGreaterThanOrEqual(role.y + role.height - 1);
      expect.soft(name.width, at).toBeGreaterThanOrEqual(whole.width * 0.75);
    } else {
      expect.soft(Math.abs(name.y - role.y), at).toBeLessThan(2);
    }
  }
  await page.setViewportSize(WIDTHS[0]);
}

/** A row's name at 600 and its row's other cells at 400, at each width (K6, the kit's rowHeader). */
async function namedAtEachWidth(page: Page, name: Locator, cell: Locator): Promise<void> {
  for (const size of WIDTHS) {
    await page.setViewportSize(size);
    expect(await name.evaluate((node) => getComputedStyle(node).fontWeight), `${String(size.width)}px`).toBe("600");
    expect(await cell.evaluate((node) => getComputedStyle(node).fontWeight), `${String(size.width)}px`).toBe("400");
  }
  await page.setViewportSize(WIDTHS[0]);
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test.describe(`a release, from the editor to a visitor (${name})`, () => {
    // One release, made by the first test and read by the next two: in order, in one worker.
    test.describe.configure({ mode: "serial" });
    const tag = randomBytes(4).toString("hex");
    const title = `Catalyst ${tag}`;
    const person = `petro ${tag}`;

    test(`an editor publishes a release (${name})`, async ({ page }) => {
      const editor = await makeUser(page.request, "music", { totp: true, roles: ["member", "editor"] });
      await signInTo(page, editor, "/admin/music");
      await theme(page, name, canvas);
      await expect(page.getByRole("heading", { level: 1, name: "Music" })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Albums" })).toBeVisible();
      await cleanAtEachWidth(page);

      await page.getByRole("button", { name: "New release" }).click();
      const making = page.getByRole("dialog", { name: "New release" });
      await making.getByRole("textbox", { name: "Title" }).fill(title);
      expect(await axe(page)).toEqual([]);
      await making.getByRole("button", { name: "Make the draft" }).click();
      await expect(page).toHaveURL(/\/admin\/music\/[0-9a-f-]{36}$/);
      await expect(page.getByText(/A draft: nothing is on the site until you publish it\./)).toBeVisible();

      await page.getByRole("button", { name: "Add SoundCloud link" }).click();
      const linking = page.getByRole("dialog", { name: "Add a SoundCloud link" });
      await linking.getByRole("textbox", { name: "Title" }).fill("The full album");
      await linking.getByRole("textbox", { name: /SoundCloud link/ }).fill("https://soundcloud.com/petrodestroys/sets/catalyst");
      await linking.getByRole("button", { name: "Add the track" }).click();
      await expect(page.getByRole("link", { name: "The full album" })).toBeVisible();

      await page.locator("summary").filter({ hasText: "Who made it" }).click();
      await page.getByRole("button", { name: "Add a credit" }).click();
      await page.getByRole("textbox", { name: "Name" }).fill(person);
      await creditRowAtEachWidth(page, page.locator("li.mf-music-credit--role").first(), (width) => width < 640);
      await cleanAtEachWidth(page);
      await page.getByRole("button", { name: "Save", exact: true }).first().click();
      await expect(page.getByText("Saved.")).toBeVisible();

      await page.getByRole("button", { name: "Publish", exact: true }).click();
      await expect(page.getByText(/Live: saving changes its page at once\./)).toBeVisible();
      await rowsUnmargined(page); // the Publish card's status line
    });

    test(`the Tracks and Credits boards show it (${name})`, async ({ page }) => {
      // An editor of its own, so no app code is used twice in its 30 seconds.
      const editor = await makeUser(page.request, "music", { totp: true, roles: ["member", "editor"] });
      await signInTo(page, editor, "/admin/music/tracks");
      await theme(page, name, canvas);
      // The row whose release is this one's: the other theme's run makes a track of the same name.
      const named = page.getByRole("rowheader").filter({ hasText: title });
      await expect(named).toHaveCount(1);
      await named.getByRole("button", { name: "The full album" }).click();
      await expect(page.getByRole("heading", { level: 2, name: "The full album" })).toBeVisible();
      await expect(page.getByRole("textbox", { name: "SoundCloud link" })).toHaveValue("https://soundcloud.com/petrodestroys/sets/catalyst");
      const row = page.getByRole("row").filter({ has: named });
      await namedAtEachWidth(page, named, row.getByRole("cell", { name: "SoundCloud playlist" }));
      await rowsUnmargined(page); // the panel's Audio line
      // In Tracks' panel a credit's row is stacked at every width; taken off again, the form is as saved.
      const panel = page.locator(".mf-music-side");
      await panel.getByRole("button", { name: "Add a credit" }).click();
      await creditRowAtEachWidth(page, panel.locator("li.mf-music-credit--role"), () => true);
      await panel.getByRole("button", { name: "Remove the credit 1" }).click();
      await expect(panel.getByRole("button", { name: "Add a credit" })).toBeFocused();
      // The track that's open is 700 among names at 600, as the board draws it.
      expect(await named.getByRole("button", { name: "The full album", pressed: true }).evaluate((node) => getComputedStyle(node).fontWeight)).toBe("700");
      await cleanAtEachWidth(page);

      await page.goto("/admin/music/credits");
      await theme(page, name, canvas);
      const credited = page.getByRole("rowheader", { name: person, exact: true });
      await expect(credited).toBeVisible();
      await namedAtEachWidth(page, credited, page.getByRole("row").filter({ has: credited }).getByRole("cell").first());
      await cleanAtEachWidth(page);
    });

    test(`a visitor plays it (${name})`, async ({ page: listener, browser }) => {
      // A visitor, with no session: the library lists it, and its pages play it through audio-player.
      const asked: string[] = [];
      listener.on("request", (request) => {
        asked.push(new URL(request.url()).hostname);
      });
      await listener.goto("/music");
      await theme(listener, name, canvas);
      await expect(listener.getByRole("link", { name: title })).toBeVisible();
      await cleanAtEachWidth(listener);
      await listener.getByRole("link", { name: title }).click();
      await expect(listener.getByRole("heading", { level: 1, name: title })).toBeVisible();
      await expect(listener.getByText(`Artist: ${person}`)).toBeVisible();
      await expect(listener.getByRole("button", { name: "Play album" })).toBeVisible();
      await expect(listener.getByRole("button", { name: "Play 01 The full album" })).toBeVisible();
      const dock = listener.getByRole("region", { name: "Player" });
      await expect(dock).toHaveCount(1);
      await expect(dock.getByText("The full album")).toBeVisible();
      await expect(dock.getByRole("link", { name: "on SoundCloud (opens SoundCloud)" })).toHaveAttribute("href", "https://soundcloud.com/petrodestroys/sets/catalyst");
      expect(await dock.evaluate((node) => node.closest("main") === null)).toBe(true); // after the footer
      await cleanAtEachWidth(listener);
      // On a phone the page runs past the window, and the dock rides its foot.
      await listener.setViewportSize(WIDTHS[1]);
      const box = await dock.boundingBox();
      expect(box && Math.round(box.y + box.height)).toBe(WIDTHS[1].height);
      await listener.setViewportSize(WIDTHS[0]);
      await listener.getByRole("link", { name: "The full album", exact: true }).click();
      await expect(listener.getByRole("heading", { level: 1, name: "The full album" })).toBeVisible();
      await expect(listener.getByRole("region", { name: "Player" })).toHaveCount(1);
      await cleanAtEachWidth(listener);
      expect(asked.filter((host) => host.endsWith("soundcloud.com"))).toEqual([]);

      // The server's copy is a real page for crawlers, and a draft's address a real 404.
      const plain = await browser.newContext({ javaScriptEnabled: false });
      const crawler = await plain.newPage();
      const served = await crawler.goto(new URL(listener.url()).pathname.replace(/\/[^/]+$/, ""));
      expect(served?.status()).toBe(200);
      await expect(crawler.locator("[data-server-copy] h1")).toHaveText(title);
      expect((await crawler.goto("/music/no-such-release"))?.status()).toBe(404);
      await plain.close();
    });
  });
}
