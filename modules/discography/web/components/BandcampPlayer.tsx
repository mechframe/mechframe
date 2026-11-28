// Bandcamp's own player for a track with no upload or SoundCloud link (0.1.5,
// `dev plans/contracts/bandcamp-player.md` §2 and §8, 2): a Listen in embeds'
// facade words, then embeds' frame. Listen grants `media` and takes its turn,
// which pauses audio-player; audio-player starting puts it back to Listen, and
// unmounting the frame stops it, since nothing can pause Bandcamp's frame.
// Each player asks for its own Listen, so two never play at once.
import { Button, useConsent } from "@/kernel";
import { useExclusive } from "@/modules/audio-player/public";
import { EmbedFrame } from "@/modules/embeds/public";
import { useCallback, useEffect, useRef, useState } from "react";

export type BandcampPlayerProps = {
  /** The player's link, from `bandcampPlayer(track)`. */
  link: string;
  /** What it plays: "07 One Hunned Thousand". */
  label: string;
};

export function BandcampPlayer({ link, label }: BandcampPlayerProps) {
  const media = useConsent("media");
  const [listening, setListening] = useState(false);
  const frame = useRef<HTMLDivElement>(null);
  const claim = useExclusive(
    useCallback(() => {
      setListening(false);
    }, []),
  );
  const shown = listening && media.granted;
  // The Listen pressed is gone: its frame takes the focus, so a keyboard goes on from there.
  useEffect(() => {
    if (shown) frame.current?.focus();
  }, [shown]);
  if (shown) {
    return (
      <div ref={frame} className="mf-music-bandcamp" tabIndex={-1}>
        <EmbedFrame link={link} words={label} />
      </div>
    );
  }
  return (
    <div className="mf-music-bandcamp-ask">
      <Button
        variant="primary"
        icon="play"
        aria-label={`Listen: ${label}`}
        onClick={() => {
          media.grant();
          claim();
          setListening(true);
        }}
      >
        Listen
      </Button>
      <span className="mf-music-bandcamp-words">
        <span className="mf-music-bandcamp-from">Bandcamp</span>
        <span className="mf-music-hint">Plays from Bandcamp, which may set cookies.</span>
      </span>
    </div>
  );
}
