/**
 * What `mountApp` was given, for the slots and the router to read.
 */
import { createContext, useContext } from "react";

import type { ModuleDefinition, SiteFrameParts } from "../modules";
import type { IconName } from "../slots/types";

/**
 * The sidebar's order and icons for module sections. `pages` orders a
 * section's pages by their addresses (`to`); those it doesn't list come
 * after, in the modules' order.
 */
export type AdminSection = { label: string; icon: IconName; pages?: readonly string[] };

export type KernelSetup = {
  modules: readonly ModuleDefinition[];
  adminSections: readonly AdminSection[];
  /** The site's own header and footer for the site frame (`defineSite`); the frame's own where none. */
  frame?: SiteFrameParts;
};

export const KernelContext = createContext<KernelSetup>({ modules: [], adminSections: [] });

export function useKernelSetup(): KernelSetup {
  return useContext(KernelContext);
}
