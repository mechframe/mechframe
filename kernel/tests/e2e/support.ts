// What the admin's end-to-end spec shares (K4.6): accounts made through the harness's test
// support, a TOTP code, signing in with both steps, a theme switched with its fades finished,
// and axe's serious and critical findings. sign-in.spec.ts keeps its own copies, from before.
import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { createHmac, randomBytes } from "node:crypto";

export const PASSWORD = "quiet orbit lantern 4471 marsh";

export const THEMES = {
  "machined-light": "rgb(236, 236, 234)",
  "vibrant-mindz": "rgb(7, 10, 22)",
} as const;

export type Made = { email: string; totp: string };

/** An account: verified, with a password, its roles, and a confirmed TOTP when asked. */
export async function makeUser(request: APIRequestContext, name: string, fields: { totp?: boolean; roles?: string[] } = {}): Promise<Made> {
  const email = `${name}-${randomBytes(5).toString("hex")}@mechframe.test`;
  const answer = await request.post("/api/_test/users", { data: { email, password: PASSWORD, verified: true, ...fields } });
  expect(answer.status(), await answer.text()).toBe(201);
  const body = (await answer.json()) as { totp_secret?: string };
  return { email, totp: body.totp_secret ?? "" };
}

function base32(text: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const letter of text.replace(/[\s=]/g, "").toUpperCase()) bits += alphabet.indexOf(letter).toString(2).padStart(5, "0");
  const bytes: number[] = [];
  for (let at = 0; at + 8 <= bits.length; at += 8) bytes.push(Number.parseInt(bits.slice(at, at + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238's code for `secret` now (30-second steps, six digits, SHA-1). */
export function totp(secret: string, when = Date.now()): string {
  const step = Buffer.alloc(8);
  step.writeBigUInt64BE(BigInt(Math.floor(when / 30_000)));
  const mac = createHmac("sha1", base32(secret)).update(step).digest();
  const offset = (mac[mac.length - 1] ?? 0) & 0xf;
  return String((mac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

/** Signs `user` in with their password and app code, landing on `next`. */
export async function signInTo(page: Page, user: Made, next: string): Promise<void> {
  await page.goto(`/sign-in?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("Code from your app").fill(totp(user.totp));
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(new RegExp(`${next.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")}$`));
}

/** The theme `name` on the page, once its fades have finished. A fade cancelled meanwhile (React
 * taking over from the server's copy, say) rejects `finished` with an AbortError: it's done too. */
export async function theme(page: Page, name: string, canvas: string): Promise<void> {
  await page.evaluate(async (chosen) => {
    document.documentElement.dataset.theme = chosen;
    document.body.getBoundingClientRect();
    await Promise.all(document.getAnimations().map((animation) => animation.finished.catch(() => undefined)));
  }, name);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor)).toBe(canvas);
}

/** The site's one AI key, saved in Settings → AI from the page itself. Specs running at once share
 * it, and the page saves it at the version it read, so a save that crosses another's is refused:
 * then the page is read again and the key saved once more (cubic on #165). With `fresh` false, a
 * key saved already is kept. */
export async function saveAiKey(page: Page, key: string, fresh = true): Promise<void> {
  for (let tries = 0; tries < 3; tries += 1) {
    await page.goto("/admin/settings/ai");
    const field = page.getByLabel(/^(Save a key|Replace the saved key)$/);
    await expect(field).toBeVisible();
    if (!fresh && (await page.getByLabel("Replace the saved key").count()) > 0) return;
    await field.fill(key);
    await page.getByRole("button", { name: "Save the key" }).click();
    const saved = page.getByText("Key saved.");
    const crossed = page.getByText("Someone else changed the key meanwhile. Reload the page to see it.");
    await expect(saved.or(crossed)).toBeVisible();
    if (await saved.isVisible()) return;
  }
  throw new Error("the AI key wasn't saved: each save crossed another");
}

/** axe's serious and critical findings, once every fade running has landed: a button just enabled
 * fades to its colour, and axe measured it halfway (campaigns' Save draft at 1.7 to 1, 10 of 41 CI
 * runs). An animation that never ends or is paused would never finish, so it isn't waited for. */
export async function axe(page: Page): Promise<string[]> {
  await page.evaluate(async () => {
    const landing = document
      .getAnimations()
      .filter((animation) => animation.playState === "running" && animation.effect?.getComputedTiming().endTime !== Infinity);
    await Promise.all(landing.map((animation) => animation.finished.catch(() => undefined)));
  });
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return violations.filter((each) => each.impact === "serious" || each.impact === "critical").map((each) => `${each.id}: ${each.help}`);
}
