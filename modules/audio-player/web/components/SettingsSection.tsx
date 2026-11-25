// The Settings section "Player" (`admin.settings.section`;
// `dev plans/contracts/audio-player.md` §2): whether the next track plays when
// one ends, and how long a play takes to count. The boards don't draw them, so
// they sit on Settings, Site. The Site tab's one Save sends them.
import { Field, Input, LoadError, Switch, useSettings } from "@/kernel";

import "../player.css";

const MIN = 5;
const MAX = 120;

export default function SettingsSection() {
  const form = useSettings("audio-player");
  if (form.read === "failed") {
    return <LoadError what="The player's settings" error={form.problem} onRetry={form.retry} inline />;
  }
  if (form.read === "loading") return <p className="mf-player-hint">Loading…</p>;
  const autoplay = form.values.autoplay_next !== false;
  const seconds = typeof form.values.count_after_seconds === "number" ? form.values.count_after_seconds : 30;
  return (
    <div className="mf-player-settings">
      <Switch
        label="Play the next track when one ends"
        checked={autoplay}
        onChange={(on) => { form.set("autoplay_next", on); }}
      />
      <Field
        label="Count a play after (seconds)"
        hint={`From ${String(MIN)} to ${String(MAX)}: how long someone listens before it counts in "Plays this week". A shorter track counts once nearly all of it is heard.`}
        error={form.errors.count_after_seconds}
      >
        <Input
          type="number"
          inputMode="numeric"
          min={MIN}
          max={MAX}
          value={String(seconds)}
          onChange={(event) => {
            const value = Number(event.target.value);
            form.set("count_after_seconds", Number.isFinite(value) ? Math.round(value) : seconds);
          }}
        />
      </Field>
    </div>
  );
}
