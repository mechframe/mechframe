// What a site's own code, and a module that lists audio-player in
// requires.modules, may use as `@/modules/audio-player/public` (SPEC 7,
// decision 0057; `dev plans/contracts/audio-player.md` §2): the player, its
// parts, and the hook another kind of player takes turns with.
export { usePlayer, useExclusive } from "./hooks";
export type { PlayerControls } from "./hooks";
export { PlayButton } from "./components/PlayButton";
export type { PlayButtonProps } from "./components/PlayButton";
export { Waveform } from "./components/Waveform";
export type { WaveformProps } from "./components/Waveform";
export { PlayerBar } from "./components/PlayerBar";
export type { PlayerBarProps } from "./components/PlayerBar";
export { PlayerDock } from "./components/PlayerDock";
export type { PlayerDockProps } from "./components/PlayerDock";
export { Equalizer } from "./components/Equalizer";
export { clock } from "./types";
export type { PlayerItem, PlayerState } from "./types";
