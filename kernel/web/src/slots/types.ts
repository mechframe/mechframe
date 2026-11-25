/**
 * The kernel's slots, typed (K4 contract §2): what a module's binding may put
 * in each, by name. `defineModule` takes them; `useSlot` and `SlotOutlet`
 * read them. A link slot's entries may also be loaded from the module's own
 * API (`LinkLoaders`, decision 0056). The text slots' parts are given props,
 * and the kit draws them in every editor and every Prose (decision 0060).
 */
import type { ComponentType } from "react";

import { safeNext as onThisSite } from "../guards/next";
import type { IconName } from "../ui/icons";
import type { MarkdownTools } from "../ui/MarkdownEditor";

/** An icon's name: one of the UI kit's set (`ICON_NAMES`; contract change 10). */
export type { IconName };

/** Loads a part, so each module's parts are their own chunk. */
export type Lazy = () => Promise<{ default: ComponentType }>;

/** Loads a part that's given `Props`. */
export type LazyOf<Props> = () => Promise<{ default: ComponentType<Props> }>;

/** A button after the editor's own, given its ways in (`editor.tools`). `id` names it within its module. */
export type EditorToolEntry = { id: string; lazy: LazyOf<{ editor: MarkdownTools }>; permission?: string };

/** A player for the links it `claims`, alone in their paragraph (`prose.embed`), given the link and its words. */
export type ProseEmbedEntry = { claims: (href: string) => boolean; lazy: LazyOf<{ href: string; words: string }> };

/**
 * What a `content.share` part is given (decision 0067): the thing an admin page
 * is about, by its content type (`blog.post`) and id, whether it's public now,
 * and the admin page it's drawn on, where the part's own notices can send people.
 */
export type SharePartProps = { type: string; id: string; live: boolean; adminPath: string };

/** A card on an admin page for sharing what it's about (`content.share`). `id` names it within its module. */
export type ContentShareEntry = { id: string; lazy: LazyOf<SharePartProps>; permission?: string };

/** A link in a menu. `to` is a path on this site. */
export type LinkEntry = {
  label: string;
  to: string;
  /** Hidden unless the person holds this permission. */
  permission?: string;
};

export type AdminLinkEntry = LinkEntry & {
  /** The sidebar group it sits in; `adminSections` orders the groups. */
  section?: string;
  icon?: IconName;
};

export type Slots = {
  "nav.public"?: LinkEntry[];
  "nav.member"?: LinkEntry[];
  "nav.admin"?: AdminLinkEntry[];
  /** The footer's menu (decision 0056): the frame's footer draws it; a site's own places it with `SlotOutlet`. */
  "nav.footer"?: LinkEntry[];
  "admin.dashboard.widget"?: { lazy: Lazy; permission?: string }[];
  "admin.settings.section"?: { id: string; title: string; lazy: Lazy; permission?: string }[];
  "account.section"?: { id: string; title: string; lazy: Lazy }[];
  "site.footer"?: { lazy: Lazy }[];
  /** Every MarkdownEditor's added buttons, after the kernel's own (decision 0060). */
  "editor.tools"?: EditorToolEntry[];
  /** Every Prose's players (decision 0060). */
  "prose.embed"?: ProseEmbedEntry[];
  /** The share cards a module's admin page draws for its content with `ShareParts` (decision 0067). */
  "content.share"?: ContentShareEntry[];
};

export type SlotName = keyof Slots;

/** One entry of a slot, as the slot holds it. */
export type SlotEntryOf<Name extends SlotName> = NonNullable<Slots[Name]>[number];

/** The slots that hold links; the rest hold parts that load. */
export const LINK_SLOTS = ["nav.public", "nav.member", "nav.admin", "nav.footer"] as const satisfies readonly SlotName[];

export const SLOT_NAMES = [
  ...LINK_SLOTS,
  "admin.dashboard.widget",
  "admin.settings.section",
  "account.section",
  "site.footer",
  "editor.tools",
  "prose.embed",
  "content.share",
] as const satisfies readonly SlotName[];

/** The slots the kit draws in its text, their parts given props: never a `SlotOutlet`. */
export const TEXT_SLOTS = ["editor.tools", "prose.embed"] as const satisfies readonly SlotName[];

/** The slots whose parts are given props, each drawn by its own outlet: the text slots and `content.share` (`ShareParts`). */
export const GIVEN_SLOTS = [...TEXT_SLOTS, "content.share"] as const satisfies readonly SlotName[];

export type LinkSlotName = (typeof LINK_SLOTS)[number];
export type TextSlotName = (typeof TEXT_SLOTS)[number];
export type GivenSlotName = (typeof GIVEN_SLOTS)[number];
export type PartSlotName = Exclude<SlotName, LinkSlotName | GivenSlotName>;
/** The slots a `SlotOutlet` can show. */
export type OutletSlotName = Exclude<SlotName, GivenSlotName>;

/**
 * A link slot's entries loaded from the module's own API (decision 0056): each
 * loader answers what the slot holds, and `useSlot` puts them after the
 * module's fixed entries while it's on.
 */
export type LinkLoaders = { [Name in LinkSlotName]?: () => Promise<SlotEntryOf<Name>[]> };

/** Whether `to` may be a link in the slot `name`: a path on this site, under /admin for `nav.admin`. */
export function linkFits(name: LinkSlotName, to: unknown): boolean {
  if (typeof to !== "string" || onThisSite(to) === null) return false;
  if (name !== "nav.admin") return true;
  const path = new URL(to, "https://site.invalid").pathname;
  return path === "/admin" || path.startsWith("/admin/");
}
