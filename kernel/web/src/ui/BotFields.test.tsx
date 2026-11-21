import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BotFields, useBotProof, type BotProof } from "./BotFields";

/** A public form as a module draws one: its fields, the trap, and the proof sent with it. */
function Form({ onSend }: { onSend: (proof: BotProof) => void }) {
  const bot = useBotProof();
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSend(bot.proof());
      }}
    >
      <label htmlFor="message">Message</label>
      <textarea id="message" name="message" />
      <BotFields {...bot.fields} />
      <button type="submit">Send</button>
    </form>
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("BotFields and useBotProof (hook 5, the kernel's form check)", () => {
  it("keep the trap out of sight, out of the tab order and away from screen readers", async () => {
    const { container } = render(<Form onSend={() => undefined} />);
    const trap = container.querySelector<HTMLInputElement>('input[name="website"]');
    expect(trap).not.toBeNull();
    expect(trap?.tabIndex).toBe(-1);
    expect(trap).toHaveAttribute("autocomplete", "off");
    expect(trap?.closest('[aria-hidden="true"]')).toHaveClass("mf-bot-trap");
    expect(screen.queryByRole("textbox", { name: /leave this field empty/i })).toBeNull();

    await userEvent.tab();
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Send" })).toHaveFocus();
  });

  it("send an empty trap and how long the form was open", () => {
    vi.useFakeTimers({ now: 1_000_000 });
    const sent: BotProof[] = [];
    render(<Form onSend={(proof) => sent.push(proof)} />);
    vi.setSystemTime(1_012_500);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(sent).toEqual([{ website: "", elapsed_ms: 12_500 }]);
  });

  it("send whatever a bot types in the trap, for the server to judge", () => {
    const sent: BotProof[] = [];
    const { container } = render(<Form onSend={(proof) => sent.push(proof)} />);
    const trap = container.querySelector<HTMLInputElement>('input[name="website"]');
    if (!trap) throw new Error("No trap.");
    fireEvent.change(trap, { target: { value: "http://spam.example" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(sent[0]?.website).toBe("http://spam.example");
    expect(sent[0]?.elapsed_ms).toBeGreaterThanOrEqual(0);
  });

  it("never send a negative time, though the clock goes back", () => {
    vi.useFakeTimers({ now: 5_000_000 });
    const sent: BotProof[] = [];
    render(<Form onSend={(proof) => sent.push(proof)} />);
    vi.setSystemTime(4_000_000);
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(sent[0]?.elapsed_ms).toBe(0);
  });
});
