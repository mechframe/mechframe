// embeds in a browser (`dev plans/contracts/embeds.md` §7): an editor puts a
// YouTube player in a page with the editor's Embed button and sees its facade
// under Preview; a visitor sees the facade, with nothing loaded from YouTube,
// until Play, then the player on youtube-nocookie.com, which the page's CSP
// allows; the editor and the page have nothing serious for axe, in both themes.
import { randomBytes } from "node:crypto";

import { expect, test } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const VIDEO = "https://www.youtube.com/watch?v=aBcDeFgHiJk";

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor embeds a video in a page, and a visitor plays it (${name})`, async ({ page, browser }) => {
    const editor = await makeUser(page.request, "embeds", { totp: true, roles: ["member", "editor"] });
    const tag = randomBytes(4).toString("hex");
    const title = `Tour film ${tag}`;
    const address = `/tour-film-${tag}`;

    await signInTo(page, editor, "/admin/pages/new");
    await theme(page, name, canvas);
    await page.getByRole("textbox", { name: "Title", exact: true }).fill(title);
    await expect(page.getByRole("textbox", { name: "Address" })).toHaveValue(address);
    await page.getByRole("textbox", { name: "Page body" }).fill("Our film from the spring.");

    await page.getByRole("button", { name: "Embed", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Embed a player" });
    await dialog.getByRole("textbox", { name: /Paste a link/ }).fill(VIDEO);
    await expect(dialog.getByRole("status")).toHaveText("A video on YouTube.");
    await dialog.getByRole("textbox", { name: "Words under the player (optional)" }).fill("The spring tour");
    expect(await axe(page)).toEqual([]);
    await dialog.getByRole("button", { name: "Insert" }).click();
    await expect(page.getByRole("textbox", { name: "Page body" })).toHaveValue(
      `Our film from the spring.\n\n[The spring tour](${VIDEO})\n\n`,
    );

    await page.getByRole("tab", { name: "Preview" }).click();
    await expect(page.getByRole("button", { name: "Play: The spring tour" })).toBeVisible();
    await page.getByRole("tab", { name: "Write" }).click();
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page.getByText("Live. Saving changes the page on the site at once.")).toBeVisible();

    // A visitor, with no session and no choice made: the facade, and nothing asked of YouTube.
    const visitor = await browser.newContext();
    const reader = await visitor.newPage();
    const asked: string[] = [];
    reader.on("request", (request) => {
      const host = new URL(request.url()).hostname;
      if (/youtube|ytimg|google/.test(host)) asked.push(request.url());
    });
    const answer = await reader.goto(address);
    expect(answer?.status()).toBe(200);
    expect(answer?.headers()["content-security-policy"]).toContain("https://www.youtube-nocookie.com");
    await theme(reader, name, canvas);
    const play = reader.getByRole("button", { name: "Play: The spring tour" });
    await expect(play).toBeVisible();
    await expect(reader.getByRole("link", { name: "The spring tour" })).toHaveAttribute("href", VIDEO);
    expect(await axe(reader)).toEqual([]);
    expect(asked).toEqual([]);

    await play.click();
    await expect(reader.getByTitle("YouTube player: The spring tour")).toHaveAttribute(
      "src",
      "https://www.youtube-nocookie.com/embed/aBcDeFgHiJk?autoplay=1",
    );
    await visitor.close();
  });
}
