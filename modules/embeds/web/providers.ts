/**
 * The players' one list (`providers.json`, the backend's `providers.json`'s
 * twin, held equal by its tests): a YouTube, SoundCloud, Spotify or Bandcamp
 * link as that provider's player. Both sides answer the same cases
 * (`tests/providers.cases.json`). Lifted from VybeSite's `lib/embeds.ts`.
 *
 * Nothing here asks a provider anything: the player's address is built from
 * the link alone and the words are the writer's. Bandcamp's id rides in the
 * link's fragment, read once from its own embed code (`fromBandcampCode`).
 */
import list from "./providers.json";

export type Embed = {
  provider: string;
  name: string;
  kind: string;
  /** The iframe's address, on the provider's one player host (the CSP's `frame-src`). */
  player: string;
  /** `video` (16:9), `short` (9:16) or `strip-<height>`: a class, never a style (the CSP). */
  shape: string;
  /** "Watch" or "Listen". */
  verb: string;
  /** The words when the writer gave none: "A video on YouTube". */
  default: string;
  /** The iframe's `allow`. */
  allow: string;
};

type Kind = { shape: string; words: string; player: string };
type Provider = {
  id: string;
  name: string;
  verb: string;
  frame_host: string;
  allow: string;
  hosts: string[];
  kinds: Record<string, Kind>;
  not_profiles?: string[];
  profile_tabs?: string[];
};

const PROVIDERS = new Map<string, Provider>((list.providers as Provider[]).map((provider) => [provider.id, provider]));

function provider(id: string): Provider {
  const found = PROVIDERS.get(id);
  if (!found) throw new Error(`providers.json has no ${id}.`);
  return found;
}

/** Each player's one host, in the list's order: the CSP's `frame-src`. */
export const FRAME_HOSTS: readonly string[] = (list.providers as Provider[]).map((each) => each.frame_host);

const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_LIST = /^[A-Za-z0-9_-]{2,64}$/;
const YOUTUBE_TIME = /^(?:(\d{1,2})h)?(?:(\d{1,4})m)?(?:(\d{1,6})s?)?$/;
const SLUG = /^[A-Za-z0-9_-]{1,255}$/;
const SPOTIFY_ID = /^[A-Za-z0-9]{22}$/;
const SPOTIFY_INTL = /^intl-[a-z]{2}(?:-[a-z]{2})?$/i;
const BANDCAMP_HOST = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.bandcamp\.com$/;
const BANDCAMP_FRAGMENT = /^bandcamp-(album|track)=(\d{1,12})$/;
/** Words that are the address itself: a bare link, as Markdown links one. */
const AN_ADDRESS = /^(?:https?:\/\/|www\.)\S*$/i;
/** An address in its parts, read as the server's `urlsplit` reads one. */
const ADDRESS = /^([A-Za-z][A-Za-z0-9+.-]*):\/\/([^/?#]*)([^?#]*)(?:\?([^#]*))?(?:#(.*))?$/s;

function embed(providerId: string, kind: string, id: string, query = ""): Embed {
  const from = provider(providerId);
  const spec = from.kinds[kind];
  if (!spec) throw new Error(`${providerId} has no kind ${kind}.`);
  return {
    provider: providerId,
    name: from.name,
    kind,
    player: spec.player.replace("{id}", id) + query,
    shape: spec.shape,
    verb: from.verb,
    default: spec.words,
    allow: from.allow,
  };
}

/** The path's parts, one trailing slash allowed. */
function segments(path: string): string[] {
  const parts = path.split("/").slice(1);
  if (parts.length > 0 && parts[parts.length - 1] === "") parts.pop();
  return parts;
}

/** `?start=N` for YouTube's time, or nothing for none, zero or one it can't read. */
function start(value: string): string {
  const found = value ? YOUTUBE_TIME.exec(value) : null;
  if (!found) return "";
  // A part that didn't match is undefined, whatever the type says.
  const [hours = 0, minutes = 0, seconds = 0] = found.slice(1).map((part) => Number(part || 0));
  const total = hours * 3600 + minutes * 60 + seconds;
  return total > 0 ? `?start=${String(total)}` : "";
}

function youtube(host: string, parts: string[], query: URLSearchParams): Embed | null {
  const first = (name: string) => query.get(name) ?? "";
  const [head = "", id = ""] = parts;
  if (host === "youtu.be") {
    return parts.length === 1 && YOUTUBE_ID.test(head) ? embed("youtube", "video", head, start(first("t"))) : null;
  }
  const path = parts.join("/");
  if (path === "watch") {
    return YOUTUBE_ID.test(first("v")) ? embed("youtube", "video", first("v"), start(first("t"))) : null;
  }
  if (path === "playlist" || path === "embed/videoseries") {
    return YOUTUBE_LIST.test(first("list")) ? embed("youtube", "playlist", first("list")) : null;
  }
  if (parts.length === 2 && YOUTUBE_ID.test(id)) {
    if (head === "shorts") return embed("youtube", "short", id);
    if (head === "live") return embed("youtube", "video", id);
    if (head === "embed") return embed("youtube", "video", id, start(first("start")));
  }
  return null;
}

function soundcloud(parts: string[]): Embed | null {
  const from = provider("soundcloud");
  const [profile = "", second = ""] = parts;
  if (parts.length === 0 || !parts.every((part) => SLUG.test(part)) || (from.not_profiles ?? []).includes(profile)) {
    return null;
  }
  let kind: string;
  if (parts.length === 2 && !(from.profile_tabs ?? []).includes(second)) kind = "track";
  else if (parts.length === 3 && second === "sets") kind = "set";
  else return null;
  return embed("soundcloud", kind, encodeURIComponent(`https://soundcloud.com/${parts.join("/")}`));
}

function spotify(parts: string[]): Embed | null {
  const rest = parts.length > 0 && SPOTIFY_INTL.test(parts[0] ?? "") ? parts.slice(1) : parts;
  const [kind = "", id = ""] = rest;
  // The list's own kinds alone: `in` would also take `constructor` or `toString`.
  if (rest.length === 2 && Object.prototype.hasOwnProperty.call(provider("spotify").kinds, kind) && SPOTIFY_ID.test(id)) {
    return embed("spotify", kind, id);
  }
  return null;
}

function bandcamp(parts: string[], fragment: string): Embed | null {
  const found = BANDCAMP_FRAGMENT.exec(fragment);
  const [kind = "", slug = ""] = parts;
  if (!found || parts.length !== 2 || kind !== found[1] || !SLUG.test(slug)) return null;
  return embed("bandcamp", kind, found[2] ?? "");
}

/** A link as the server's urlsplit reads it: leading spaces and controls gone, and tabs and line breaks anywhere. */
export function normalised(href: string): string {
  // eslint-disable-next-line no-control-regex -- the controls urlsplit drops.
  return href.replace(/^[\x00-\x20]+/, "").replace(/[\t\r\n]/g, "");
}

/** The player `href` is, or null for a link that stays a link. */
export function recognise(href: string): Embed | null {
  const address = ADDRESS.exec(normalised(href));
  if (!address) return null;
  const [, scheme = "", authority = "", path = "", rawQuery = "", fragment = ""] = address;
  const host = authority.toLowerCase();
  // No port and no user: a host alone, as every provider's links are.
  if (!/^https?$/i.test(scheme) || !host || /[:@]/.test(host)) return null;
  const parts = segments(path);
  if (provider("youtube").hosts.includes(host)) return youtube(host, parts, new URLSearchParams(rawQuery));
  if (provider("soundcloud").hosts.includes(host)) return soundcloud(parts);
  if (provider("spotify").hosts.includes(host)) return spotify(parts);
  if (BANDCAMP_HOST.test(host) && host !== "www.bandcamp.com") return bandcamp(parts, fragment);
  return null;
}

/** The words shown with the player: the writer's link text, or the kind's own
 * ("A video on YouTube") when it's blank or the address itself. */
export function wordsFor(found: Embed, text: string): string {
  const words = text.trim();
  return !words || AN_ADDRESS.test(words) ? found.default : words;
}

/** The Markdown the editor writes: the link with its words, what Markdown
 * would read in them escaped, and the address's brackets and spaces encoded.
 * A link the rules take gets the kind's own words if it has none, and one
 * they don't its address, so it never draws as an empty link. Both are read
 * from the address `recognise` reads (CodeRabbit on #127). */
export function embedMarkdown(href: string, words: string): string {
  const link = normalised(href).trim();
  const found = recognise(link);
  // Words across a line break on one line: a blank line would end the link's paragraph (CodeRabbit on #127).
  const said = (found ? wordsFor(found, words) : words.trim() || link).replace(/\s*[\r\n]+\s*/g, " ");
  // Percent-encoding is of UTF-8 bytes: a space beyond ASCII is two or three of them (CodeRabbit on #127).
  const address = link.replace(/[()\s<>]/g, (c) => (c === "(" ? "%28" : c === ")" ? "%29" : encodeURIComponent(c)));
  return `[${said.replace(/[\\[\]*_`]/g, "\\$&")}](${address})`;
}

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

/** The text of an embed code's link, its few entities decoded. */
function decoded(text: string): string {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, name: string) => {
    if (name.startsWith("#")) {
      const code = name[1] === "x" || name[1] === "X" ? parseInt(name.slice(2), 16) : Number(name.slice(1));
      return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : whole;
    }
    return ENTITIES[name.toLowerCase()] ?? whole;
  });
}

/** The first `<iframe …>…</iframe>` in a paste: its opening tag's attributes, and what it holds. */
const IFRAME = /<iframe\b([^>]*)>([^]*?)<\/iframe>/i;
const BANDCAMP_PLAYER =
  /\bsrc\s*=\s*["']https:\/\/bandcamp\.com\/EmbeddedPlayer\/(?:[^"'/]+\/)*?(album|track)=(\d{1,12})(?:\/[^"']*)?["']/i;
const BANDCAMP_LINK =
  /<a\s[^>]*?\bhref\s*=\s*["'](https:\/\/[a-z0-9-]+\.bandcamp\.com\/(album|track)\/[A-Za-z0-9_-]+)\/?["'][^>]*>([^<]*)<\/a>/i;
/** More than any embed code is long (Bandcamp's is about 400 characters): read no further. */
const MOST_CODE = 4096;

/** What Bandcamp's own embed code (Share, Embed) names: its album's or
 * track's page with the player's id in the fragment, and the words its link
 * says, or null for anything else. Read by pattern, never parsed as HTML, so
 * nothing in a pasted code ever runs or loads; the id and the page from the
 * same `<iframe>`, so two codes pasted together never mix; and nothing longer
 * than a code is, so a huge paste can't hold the dialog up. */
export function fromBandcampCode(code: string): { href: string; words: string } | null {
  const frame = code.length <= MOST_CODE ? IFRAME.exec(code) : null;
  if (!frame) return null;
  const player = BANDCAMP_PLAYER.exec(frame[1] ?? "");
  const link = BANDCAMP_LINK.exec(frame[2] ?? "");
  if (!player || !link || player[1]?.toLowerCase() !== link[2]?.toLowerCase()) return null;
  const href = `${link[1] ?? ""}#bandcamp-${(player[1] ?? "").toLowerCase()}=${player[2] ?? ""}`;
  const found = recognise(href);
  return found ? { href, words: wordsFor(found, decoded(link[3] ?? "")) } : null;
}

/** A YouTube video's id from any of its links, or a bare id (`videos-player.md`), or null. */
export function youtubeId(link: string): string | null {
  const bare = link.trim();
  if (YOUTUBE_ID.test(bare)) return bare;
  const found = recognise(bare);
  if (found?.provider !== "youtube" || found.kind === "playlist") return null;
  return /\/embed\/([A-Za-z0-9_-]{11})/.exec(found.player)?.[1] ?? null;
}
