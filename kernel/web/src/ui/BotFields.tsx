/**
 * The bot check's two signals for a public form (hook 5, decision 0052;
 * `kernel.bot` on the server), lifted from VybeSite's contact form: a trap
 * field a bot fills in and a person never sees, and how long the form was
 * open. The server judges them; the form only sends them.
 *
 *     const bot = useBotProof();
 *     <BotFields {...bot.fields} />
 *     send({ ...values, bot: bot.proof() });
 *
 * A held submission is still kept, set apart, and its sender is thanked all
 * the same, so a bot learns nothing.
 */
import { useId, useState } from "react";

/** What a public form sends as `bot`: the server's `kernel.BotProof`. */
export type BotProof = { website: string; elapsed_ms: number; token?: string };

export type BotFieldsProps = { value: string; onChange: (value: string) => void };

/** The trap: out of sight, the tab order and the accessibility tree, but an ordinary input to a bot. */
export function BotFields({ value, onChange }: BotFieldsProps) {
  const id = `${useId()}-website`;
  return (
    <div className="mf-bot-trap" aria-hidden="true">
      <label htmlFor={id}>Leave this field empty</label>
      <input
        id={id}
        name="website"
        type="text"
        tabIndex={-1}
        autoComplete="off"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </div>
  );
}

/** The trap's state and the form's open time; `proof()` is what to send. */
export function useBotProof(): { fields: BotFieldsProps; proof: () => BotProof } {
  const [website, setWebsite] = useState("");
  const [openedAt] = useState(() => Date.now());
  return {
    fields: { value: website, onChange: setWebsite },
    proof: () => ({ website, elapsed_ms: Math.max(0, Date.now() - openedAt) }),
  };
}
