/**
 * Reading the slots (K4 contract §2): `useSlot` gives only the entries of
 * modules that are on and that the person may see, a module's loaded links
 * after its fixed ones (decision 0056); `SlotOutlet` shows a slot, each part
 * that loads in its own error boundary.
 */
import { useQueries } from "@tanstack/react-query";
import { Suspense, useCallback, useState } from "react";
import { NavLink } from "react-router";

import { ErrorBoundary } from "../ui/ErrorBoundary";
import { useKernelSetup } from "../app/context";
import { lazyPart } from "../app/lazy";
import { useSession } from "../session/session";
import { SITE, useModulesOn } from "../site/site";
import {
  LINK_SLOTS,
  linkFits,
  type Lazy,
  type LinkSlotName,
  type OutletSlotName,
  type SlotEntryOf,
  type SlotName,
} from "./types";

/** Where TanStack Query keeps a module's loaded links: `[...SLOT_LINKS, module, slot]`. */
export const SLOT_LINKS = ["kernel", "slot-links"] as const;
/** How long a module's loaded links stay fresh before the next page asks again. */
export const SLOT_LINKS_FRESH = 60_000;

type Loaded = { module: string; links: readonly unknown[] | undefined };

/** The loaded links of the modules on for `name`, each module's once its load has answered. */
function useLoadedLinks(name: SlotName, on: (id: string) => boolean): Map<string, readonly unknown[]> {
  const { modules } = useKernelSetup();
  const loaders = isLinkSlot(name)
    ? modules.flatMap((definition) => {
        const load = definition.links?.[name];
        return load && on(definition.id) ? [{ module: definition.id, load }] : [];
      })
    : [];
  const found = useQueries({
    queries: loaders.map(({ module, load }) => ({
      queryKey: [...SLOT_LINKS, module, name],
      queryFn: load,
      staleTime: SLOT_LINKS_FRESH,
    })),
    combine: (results) =>
      results.map((result, at): Loaded => ({ module: loaders[at]?.module ?? "", links: result.data })),
  });
  const byModule = new Map<string, readonly unknown[]>();
  for (const { module, links } of found) if (links) byModule.set(module, links);
  return byModule;
}

/** A loaded entry `useSlot` may show: a link that fits the slot, as a fixed one must; else it's left out, with a warning. */
function fits(name: LinkSlotName, module: string, entry: unknown): entry is SlotEntryOf<LinkSlotName> {
  const link = entry as { label?: unknown; to?: unknown } | null;
  if (typeof link === "object" && link !== null && typeof link.label === "string" && linkFits(name, link.to)) return true;
  console.warn(`${module} loaded a ${name} link that isn't a path on this site, so it's left out.`, entry);
  return false;
}

/**
 * An entry with the module it came from, and its `key`: the module, the slot
 * and its place in that module's own list, fixed before anything is filtered
 * out, so a part keeps its own error boundary and state whatever is hidden
 * around it (cubic and CodeRabbit on #79).
 */
export type Placed<Name extends SlotName> = SlotEntryOf<Name> & { module: string; key: string };

/** The entries of `name` the person may see, in the modules' order. */
export function useSlot<Name extends SlotName>(name: Name): Placed<Name>[] {
  const { modules } = useKernelSetup();
  const on = useModulesOn();
  const session = useSession();
  const may = (permission: string | undefined) =>
    permission === undefined || (session.status === "signed-in" && session.can(permission));
  // The site's are always on, even while the switches are read; a module's wait for them (CodeRabbit on #92).
  const isOn = (id: string) => id === SITE || on?.has(id) === true;
  const loaded = useLoadedLinks(name, isOn);
  const found: Placed<Name>[] = [];
  for (const definition of modules) {
    if (!isOn(definition.id)) continue;
    const entries = (definition.slots?.[name] ?? []) as SlotEntryOf<Name>[];
    entries.forEach((entry, at) => {
      const permission = "permission" in entry ? entry.permission : undefined;
      if (may(permission)) found.push({ ...entry, module: definition.id, key: `${definition.id}:${name}:${String(at)}` });
    });
    if (!isLinkSlot(name)) continue;
    (loaded.get(definition.id) ?? []).forEach((entry, at) => {
      if (!fits(name, definition.id, entry) || !may(entry.permission)) return;
      found.push({ ...(entry as SlotEntryOf<Name>), module: definition.id, key: `${definition.id}:${name}:loaded:${String(at)}` });
    });
  }
  return found;
}

function isLinkSlot(name: SlotName): name is LinkSlotName {
  return (LINK_SLOTS as readonly string[]).includes(name);
}

/**
 * Shows the slot `name`: a list of links for a menu, else each part in turn,
 * each in an error boundary of its own so one part failing leaves the rest.
 */
export function SlotOutlet({ name, label }: { name: OutletSlotName; label?: string }) {
  const entries = useSlot(name);
  // Bumped by Try again, so the parts are made again here: one whose code
  // didn't arrive gets a fresh load (lazyPart forgot the failed one).
  const [, setTries] = useState(0);
  const again = useCallback(() => {
    setTries((tries) => tries + 1);
  }, []);
  if (entries.length === 0) return null;
  if (isLinkSlot(name)) {
    return (
      <ul className="mf-slot-links" aria-label={label}>
        {(entries as Placed<LinkSlotName>[]).map((entry) => (
          <li key={entry.key}>
            <NavLink to={entry.to}>{entry.label}</NavLink>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <>
      {(entries as (Placed<SlotName> & { lazy: Lazy })[]).map((entry) => {
        const Part = lazyPart(entry.lazy);
        return (
          <ErrorBoundary key={entry.key} where={`${entry.module}'s part of ${name}`} onRetry={again}>
            <Suspense fallback={null}>
              <Part />
            </Suspense>
          </ErrorBoundary>
        );
      })}
    </>
  );
}
