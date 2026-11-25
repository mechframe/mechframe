// featured in a browser (`dev plans/contracts/featured.md` §7): an admin makes a
// player on Players, adds a probe note from the picker and a YouTube link pasted
// (titled by the harness's fake YouTube), and saves it live; Players has nothing
// serious for axe in both themes at 1440 and 390, with no sideways scroll, and
// nothing loads from YouTube there. Then a note added, given a start and saved
// shows on the harness's /featured.html, which reads the slot through
// useFeatured, only once it starts.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const VIDEO = "https://youtu.be/aBcDeFgHiJk";

/** A probe note, published: what a slot points at in the harness (`probe.note`). */
async function note(page: Page, title: string): Promise<void> {
  const origin = new URL(page.url()).origin;
  const headers = { Origin: origin, "Sec-Fetch-Site": "same-origin" };
  const made = await page.request.post("/api/probe/notes", { headers, data: { slug: `n-${randomBytes(6).toString("hex")}`, title } });
  expect(made.status(), await made.text()).toBe(201);
  const { id } = (await made.json()) as { id: string };
  const published = await page.request.post(`/api/probe/notes/${id}/publish`, { headers });
  expect(published.status(), await published.text()).toBe(204);
}

/** A new player made on Players: its name, Notes and YouTube links. */
async function newPlayer(page: Page, label: string): Promise<void> {
  await page.getByRole("button", { name: "New player" }).click();
  const dialog = page.getByRole("dialog", { name: "New player" });
  await dialog.getByRole("textbox", { name: "Name" }).fill(label);
  await dialog.getByRole("checkbox", { name: "Notes" }).check();
  await dialog.getByRole("checkbox", { name: "YouTube links" }).check();
  await dialog.getByRole("button", { name: "Add a kind" }).click();
  await dialog.getByRole("textbox", { name: "Kind 1" }).fill("Music video");
  await dialog.getByRole("button", { name: "Make the player" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("tab", { name: new RegExp(`^${label}`) })).toHaveAttribute("aria-selected", "true");
}

async function addNote(page: Page, title: string): Promise<void> {
  await page.getByRole("button", { name: "Add note" }).click();
  const picker = page.getByRole("dialog", { name: "Add note" });
  await picker.getByRole("searchbox", { name: "Search notes" }).fill(title);
  await picker.getByRole("button", { name: "Search" }).click();
  await picker.getByRole("button", { name: `Add ${title}` }).click();
  await picker.getByRole("button", { name: "Done" }).click();
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`Players: a player made, filled and saved, at 1440 and 390 (${name})`, async ({ page }) => {
    const admin = await makeUser(page.request, "players", { totp: true, roles: ["member", "admin"] });
    const tag = randomBytes(3).toString("hex");
    const asked: string[] = [];
    page.on("request", (request) => {
      if (/youtube|ytimg|googlevideo/.test(new URL(request.url()).hostname)) asked.push(request.url());
    });
    await signInTo(page, admin, "/admin/featured");
    await theme(page, name, canvas);
    await note(page, `Catalyst ${tag}`);
    await newPlayer(page, `Spotlight ${tag}`);
    await addNote(page, `Catalyst ${tag}`);

    await page.getByRole("button", { name: "Paste links" }).click();
    const paste = page.getByRole("dialog", { name: "Paste links" });
    await paste.getByRole("textbox", { name: "YouTube links" }).fill(`${VIDEO}\nhttps://vimeo.com/1`);
    await paste.getByRole("button", { name: "Read the links" }).click();
    await expect(paste.getByText("https://vimeo.com/1")).toBeVisible();
    await expect(paste.getByRole("textbox", { name: "Title of youtu.be/aBcDeFgHiJk" })).toHaveValue("A video aBcDeFgHiJk");
    await paste.getByRole("button", { name: "Add 1 video" }).click();

    const bar = page.getByRole("region", { name: "Changes not saved" });
    await expect(bar).toHaveText(new RegExp(`2 changes not saved: Catalyst ${tag} added, A video aBcDeFgHiJk added`));
    await bar.getByRole("button", { name: "Save and go live" }).click();
    await expect(bar).toBeHidden();
    await expect(page.getByText(`Now playing: Catalyst ${tag}, then A video aBcDeFgHiJk`)).toBeVisible();

    for (const [width, height] of [
      [1440, 900],
      [390, 844],
    ] as const) {
      await page.setViewportSize({ width, height });
      await expect(page.getByRole("heading", { level: 1, name: "Players" })).toBeVisible();
      expect(await axe(page), `axe at ${String(width)}`).toEqual([]);
      const sideways = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(sideways, `sideways scroll at ${String(width)}`).toBeLessThanOrEqual(0);
    }
    await page.getByRole("button", { name: `Dates of Catalyst ${tag}: Always` }).click();
    const dates = page.getByRole("dialog", { name: `Dates of Catalyst ${tag}` });
    expect(await axe(page)).toEqual([]);
    await dates.getByRole("button", { name: "Cancel" }).click();
    expect(asked).toEqual([]);
  });
}

test("a note added, given a start and saved shows on the page once it starts", async ({ page, browser }) => {
  test.setTimeout(150_000);
  const editor = await makeUser(page.request, "players", { totp: true, roles: ["member", "admin"] });
  const tag = randomBytes(3).toString("hex");
  await signInTo(page, editor, "/admin/featured");
  await note(page, `Gather Around ${tag}`);
  await newPlayer(page, `Releases ${tag}`);
  const key = new URL(page.url()).searchParams.get("slot") ?? "";
  expect(key).toBe(`releases-${tag}`);
  await addNote(page, `Gather Around ${tag}`);

  // The next whole minute at least 5 s away: the dates dialog takes minutes.
  const startsAt = Math.ceil((Date.now() + 5_000) / 60_000) * 60_000;
  const local = new Date(startsAt);
  const pad = (n: number) => String(n).padStart(2, "0");
  const value = `${String(local.getFullYear())}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`;
  await page.getByRole("button", { name: `Dates of Gather Around ${tag}: Always` }).click();
  const dates = page.getByRole("dialog", { name: `Dates of Gather Around ${tag}` });
  await dates.getByLabel("Starts").fill(value);
  await dates.getByRole("button", { name: "Set the dates" }).click();
  const bar = page.getByRole("region", { name: "Changes not saved" });
  await expect(bar).toHaveText(new RegExp(`Gather Around ${tag} added`));
  await bar.getByRole("button", { name: "Save and go live" }).click();
  await expect(bar).toBeHidden();
  await expect(page.getByText(`Up next: Gather Around ${tag}`, { exact: false })).toBeVisible();

  // A visitor of their own each time: no cached read between the two.
  const before = await browser.newContext();
  const early = await before.newPage();
  await early.goto(`/featured.html?slot=${key}`);
  await expect(early.getByRole("heading", { level: 1, name: `Releases ${tag}` })).toBeVisible();
  await expect(early.getByText("Nothing is live in it now.")).toBeVisible();
  await before.close();

  await page.waitForTimeout(Math.max(0, startsAt - Date.now()) + 1_500);
  const after = await browser.newContext();
  const later = await after.newPage();
  await later.goto(`/featured.html?slot=${key}`);
  await expect(later.getByRole("list", { name: `Live in the Releases ${tag}` })).toContainText(`Gather Around ${tag}`);
  await after.close();
});
