// The three bars beside the row that plays (`dev plans/contracts/audio-player.md`
// §2), moving while it plays and still under reduced motion.
import "../player.css";

export function Equalizer({ playing }: { playing: boolean }) {
  return (
    <span className={playing ? "mf-player-eq mf-player-eq-on" : "mf-player-eq"} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}
