/**
 * What the AI's screens say of a problem (decision 0058): the kernel's codes
 * in the editor's words, anything else as the kernel said it.
 */
import { ApiProblem } from "../api/problem";
import { said } from "../auth/words";

const AI_PROBLEMS: Readonly<Record<string, string>> = {
  "kernel.ai_off": "The AI's writing help is off: no Anthropic key is set. An admin can add one in Settings → AI.",
  "kernel.ai_key_unreadable": "The saved Anthropic key can't be read. An admin can save it again in Settings → AI.",
  "kernel.rate_limited": "You've asked the AI for a lot in the last hour. Try again later.",
  "kernel.writing_style_not_found": "That writing style no longer exists. Choose another.",
};

/** The AI's 502s, whose own sentence says what went wrong: Anthropic refused the key, an answer was cut off, a link was lost. */
const SAID_BY_THE_KERNEL = new Set(["kernel.ai_failed", "kernel.ai_rewrite_lost"]);

/** A failure as one sentence: a problem's own words for the AI's codes, else the kernel's. */
export function sayAi(error: unknown): string {
  if (error instanceof ApiProblem) {
    if (SAID_BY_THE_KERNEL.has(error.code) && error.detail) return error.detail;
    return said(error, AI_PROBLEMS);
  }
  return "That didn't work. Try again.";
}

/** The Style picker's name for the writing rules' own voice. */
export const HOUSE_STYLE = "House style";
