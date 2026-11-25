// The music library in a browser (`dev plans/contracts/discography.md` §7): an
// editor makes a release on the Albums board, adds a SoundCloud track and a credit
// in the album editor and publishes it; the Tracks and Credits boards show them; a
// visitor finds it at /music and opens it: Play album, the row's play and the
// Player docked at the window's foot, with SoundCloud's credit (0.1.1, audio-player's
// contract §7), and its track's page with the player's bar. Nothing loads from
// SoundCloud until Play is pressed. Each board and page has nothing serious for axe,
// in both themes, at 1440 and at a phone's 390. The e2e server runs with storage
// off (harness.e2e), so no track is uploaded here: the contract suite uploads one
// through the job, and audio-player's own spec plays a real file.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

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

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor publishes a release, and a visitor plays it (${name})`, async ({ page, browser }) => {
    const editor = await makeUser(page.request, "music", { totp: true, roles: ["member", "editor"] });
    const tag = randomBytes(4).toString("hex");
    const title = `Catalyst ${tag}`;
    const person = `petro ${tag}`;

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
    await cleanAtEachWidth(page);
    await page.getByRole("button", { name: "Save", exact: true }).first().click();
    await expect(page.getByText("Saved.")).toBeVisible();

    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByText(/Live: saving changes its page at once\./)).toBeVisible();

    await page.goto("/admin/music/tracks");
    await page.getByRole("button", { name: "The full album" }).first().click();
    await expect(page.getByRole("heading", { level: 2, name: "The full album" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "SoundCloud link" })).toHaveValue("https://soundcloud.com/petrodestroys/sets/catalyst");
    await cleanAtEachWidth(page);

    await page.goto("/admin/music/credits");
    await expect(page.getByRole("cell", { name: person, exact: true })).toBeVisible();
    await cleanAtEachWidth(page);

    // A visitor, with no session: the library lists it, and its pages play it through audio-player.
    const visitor = await browser.newContext();
    const listener = await visitor.newPage();
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
    await visitor.close();
  });
}
