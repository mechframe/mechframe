/**
 * The kernel's slots, typed (K4 contract §2): what a module's binding may put
 * in each, by name. `defineModule` takes them; `useSlot` and `SlotOutlet`
 * read them. A link slot's entries may also be loaded from the module's own
 * API (`LinkLoaders`, decision 0056).
 */
import type { ComponentType } from "react";

import { safeNext as onThisSite } from "../guards/next";
import type { IconName } from "../ui/icons";

/** An icon's name: one of the UI kit's set (`ICON_NAMES`; contract change 10). */
export type { IconName };

/** Loads a part, so each module's parts are their own chunk. */
export type Lazy = () => Promise<{ default: ComponentType }>;

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
] as const satisfies readonly SlotName[];

export type LinkSlotName = (typeof LINK_SLOTS)[number];
export type PartSlotName = Exclude<SlotName, LinkSlotName>;

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
