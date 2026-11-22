// embeds' part of prose.embed (decision 0060): the player Prose draws in place
// of a paragraph that holds only a link `recognise` takes.
import { Embed } from "./Embed";

export default function ProsePlayer({ href, words }: { href: string; words: string }) {
  return <Embed link={href} words={words} />;
}
