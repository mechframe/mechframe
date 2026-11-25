// audio-player in a browser (`dev plans/contracts/audio-player.md` §7), on the
// harness's /player.html: a WAV this spec makes really plays from the bar, its
// Seek slider moving; starting the YouTube playlist pauses it, and starting it
// again pauses the video; the dock rides the window's foot; each player is one
// named region; axe finds nothing serious, in both themes. Nothing reaches
// YouTube: its API is answered here with a fake.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { THEMES, theme } from "../../../../kernel/tests/e2e/support";

/** The kernel's axe check (support.ts) over the page but embeds' playlist, which is embeds' own to answer for:
 * its "Prev" is named "Previous video", which axe's label-content-name-mismatch refuses (a fix for embeds). */
async function axe(page: Page): Promise<string[]> {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .exclude(".mf-playlist")
    .analyze();
  return violations.filter((each) => each.impact === "serious" || each.impact === "critical").map((each) => `${each.id}: ${each.help}`);
}

/** A mono 16-bit WAV of a soft tone, `seconds` long. */
function wav(seconds: number, hertz: number): Buffer {
  const rate = 8000;
  const samples = rate * seconds;
  const data = Buffer.alloc(samples * 2);
  for (let at = 0; at < samples; at += 1) data.writeInt16LE(Math.round(Math.sin((2 * Math.PI * hertz * at) / rate) * 6000), at * 2);
  const head = Buffer.alloc(44);
  head.write("RIFF", 0);
  head.writeUInt32LE(36 + data.length, 4);
  head.write("WAVEfmt ", 8);
  head.writeUInt32LE(16, 16);
  head.writeUInt16LE(1, 20);
  head.writeUInt16LE(1, 22);
  head.writeUInt32LE(rate, 24);
  head.writeUInt32LE(rate * 2, 28);
  head.writeUInt16LE(2, 32);
  head.writeUInt16LE(16, 34);
  head.write("data", 36);
  head.writeUInt32LE(data.length, 40);
  return Buffer.concat([head, data]);
}

/** YouTube's IFrame API as the playlist calls it: a player that plays at once and counts its pauses. */
const FAKE_YOUTUBE = `
  window.__videoPauses = 0;
  window.YT = {
    PlayerState: { ENDED: 0, PLAYING: 1, PAUSED: 2 },
    Player: function (element, options) {
      setTimeout(function () { options.events.onReady(); options.events.onStateChange({ data: 1 }); }, 0);
      this.loadVideoById = function () {};
      this.pauseVideo = function () { window.__videoPauses += 1; options.events.onStateChange({ data: 2 }); };
      this.destroy = function () {};
    },
  };
  if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();
`;

async function open(page: Page): Promise<void> {
  const one = wav(20, 220);
  const two = wav(20, 330);
  await page.route("**/e2e-audio/*.wav", (route) =>
    route.fulfill({ status: 200, contentType: "audio/wav", body: route.request().url().endsWith("one.wav") ? one : two }),
  );
  await page.route("https://www.youtube.com/iframe_api", (route) =>
    route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE_YOUTUBE }),
  );
  await page.goto("/player.html");
  await expect(page.getByRole("heading", { level: 1, name: "The player" })).toBeVisible();
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`the bar plays a real file, takes turns with a video, and the dock rides the foot (${name})`, async ({ page }) => {
    await open(page);
    await theme(page, name, canvas);
    const bar = page.getByRole("region", { name: "Spotlight single" });
    const dock = page.getByRole("region", { name: "Player" });
    await expect(bar).toHaveCount(1);
    await expect(dock).toHaveCount(1);
    expect(await axe(page)).toEqual([]);

    // The dock rides the window's foot at the top of the long page.
    const height = await page.evaluate(() => window.innerHeight);
    const box = await dock.boundingBox();
    expect(box && Math.round(box.y + box.height)).toBe(height);

    await bar.getByRole("button", { name: "Play First sample" }).click();
    await expect(bar.getByRole("button", { name: "Pause First sample" })).toBeVisible();
    const seek = bar.getByRole("slider", { name: "Seek" });
    await expect(seek).toHaveAttribute("aria-valuemax", "20");
    await expect.poll(async () => Number(await seek.getAttribute("aria-valuenow")), { timeout: 10_000 }).toBeGreaterThanOrEqual(2);
    await expect(dock.getByText("Track 1 of 2")).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Now playing: First sample" })).toHaveCount(1);
    expect(await axe(page)).toEqual([]);

    // Starting the video pauses the audio where it is.
    await page.getByRole("button", { name: "Play A sample video" }).click();
    await expect(bar.getByRole("button", { name: "Play First sample" })).toBeVisible();
    const pausedAt = Number(await seek.getAttribute("aria-valuenow"));

    // Starting the audio again pauses the video, and plays on from there.
    await bar.getByRole("button", { name: "Play First sample" }).click();
    await expect(bar.getByRole("button", { name: "Pause First sample" })).toBeVisible();
    await expect.poll(() => page.evaluate(() => (window as unknown as { __videoPauses: number }).__videoPauses)).toBe(1);
    expect(Number(await seek.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(pausedAt);

    // Next moves the bar and the dock on together.
    await bar.getByRole("button", { name: "Next track" }).click();
    await expect(bar.getByText("Second sample")).toBeVisible();
    await expect(dock.getByText("Track 2 of 2")).toBeVisible();
  });
}

test("the dock hides its progress, queue and volume under 700px, as the board does", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  const dock = page.getByRole("region", { name: "Player" });
  await expect(dock.getByRole("button", { name: "Play First sample" })).toBeVisible();
  await expect(dock.getByRole("button", { name: "Queue" })).toBeHidden();
  await expect(dock.getByRole("button", { name: "Volume" })).toBeHidden();
  expect(await axe(page)).toEqual([]);
});
