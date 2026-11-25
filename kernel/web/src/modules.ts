/**
 * How a module's web binding registers itself (SPEC.md section 8).
 *
 * A binding calls `defineModule` once, in `module.web.ts`, with its routes by
 * access level and the kernel slots it fills. `mountApp` reads these to build
 * the router and the slots. A binding holds no business logic: anything a
 * desktop or mobile app would also need lives in the backend.
 */
import type { ComponentType } from "react";

import { kernelPageTaken } from "./app/pages";
import { LINK_SLOTS, SLOT_NAMES, linkFits, type LinkLoaders, type LinkSlotName, type Slots } from "./slots/types";

export type ModuleRoute = {
  /** The path, in React Router's syntax, such as "/blog/:slug". */
  path: string;
  /** Loads the page, so each module's pages are their own chunk. */
  lazy: () => Promise<{ default: ComponentType }>;
  /** For admin routes: the permission a user needs, such as "blog.post.write". */
  permission?: string;
  /**
   * A public or member page drawn edge to edge: the site frame's `<main>`
   * drops its padding while it's open. Not for an admin route.
   */
  bleed?: boolean;
};

export type ModuleDefinition = {
  /** The module's id, as in its module.json. */
  id: string;
  routes: {
    public: ModuleRoute[];
    member: ModuleRoute[];
    admin: ModuleRoute[];
  };
  /** The kernel slots this module fills (`Slots` says what each takes). */
  slots?: Slots;
  /**
   * Link slots whose entries come from the module's own API, such as a
   * menu its people choose (decision 0056): each loader's links follow the
   * module's fixed ones in `useSlot`, while the module is on.
   */
  links?: LinkLoaders;
};

const MODULE_ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

/** The id the site's own pages and slots go by (`defineSite`, decision 0048): always on. */
export const SITE = "site";

/** The ids the kernel keeps: its own API (`/api/auth`, `/api/kernel`) and the site's, as the backend does. */
const RESERVED = new Set(["auth", "kernel", SITE]);

function checkRoutes(definition: ModuleDefinition): void {
  const seen = new Set<string>();
  for (const [level, routes] of Object.entries(definition.routes)) {
    for (const route of routes) {
      if (seen.has(route.path)) {
        throw new Error(`${definition.id} gives the path ${route.path} twice.`);
      }
      seen.add(route.path);
      if (level === "admin" && !route.path.startsWith("/admin/")) {
        throw new Error(`${definition.id}'s admin route ${route.path} must start with /admin/.`);
      }
      if (level === "admin" && !route.permission) {
        throw new Error(`${definition.id}'s admin route ${route.path} must name a permission.`);
      }
      if (level === "admin" && route.bleed) {
        throw new Error(`${definition.id}'s admin route ${route.path} can't be bleed: the admin frame has its own layout.`);
      }
      if (level !== "admin" && (route.path === "/admin" || route.path.startsWith("/admin/"))) {
        throw new Error(`${definition.id}'s ${level} route ${route.path} is under /admin: list it as an admin route.`);
      }
      const taken = kernelPageTaken(route.path);
      if (taken) {
        throw new Error(
          `${definition.id}'s route ${route.path} takes the kernel's page ${taken.path}: fill the kernel's slots instead.`,
        );
      }
    }
  }
}

function checkSlots(definition: ModuleDefinition): void {
  for (const [name, entries] of Object.entries(definition.slots ?? {})) {
    if (!(SLOT_NAMES as readonly string[]).includes(name)) {
      throw new Error(`${definition.id} fills the slot "${name}", which the kernel doesn't have.`);
    }
    for (const entry of entries as Record<string, unknown>[]) {
      if ((LINK_SLOTS as readonly string[]).includes(name)) {
        if (!linkFits("nav.public", entry.to)) {
          throw new Error(`${definition.id}'s ${name} link must go to a path on this site.`);
        }
        if (!linkFits(name as LinkSlotName, entry.to)) {
          throw new Error(`${definition.id}'s nav.admin link ${String(entry.to)} must go under /admin/.`);
        }
      } else if (typeof entry.lazy !== "function") {
        throw new Error(`${definition.id}'s ${name} entry must load its part (lazy).`);
      } else if ((name === "editor.tools" || name === "content.share") && (typeof entry.id !== "string" || entry.id === "")) {
        throw new Error(`${definition.id}'s ${name} entry must have an id.`);
      } else if (name === "prose.embed" && typeof entry.claims !== "function") {
        throw new Error(`${definition.id}'s prose.embed entry must say which links it claims (claims).`);
      }
    }
  }
  for (const [name, load] of Object.entries(definition.links ?? {})) {
    if (!(LINK_SLOTS as readonly string[]).includes(name)) {
      throw new Error(`${definition.id} loads links for "${name}", which isn't one of the kernel's link slots.`);
    }
    if (typeof load !== "function") {
      throw new Error(`${definition.id}'s links for ${name} must be a function that loads them.`);
    }
  }
}

/**
 * Registers a module's web binding. Checks what the types can't: the id's
 * shape, admin routes under /admin and each with a permission, no path given
 * twice, no route that takes one of the kernel's pages, and slot entries the
 * kernel can show.
 */
export function defineModule(definition: ModuleDefinition): ModuleDefinition {
  if (!MODULE_ID.test(definition.id)) {
    throw new Error(`"${definition.id}" isn't a module id: lowercase letters, digits and hyphens.`);
  }
  if (RESERVED.has(definition.id)) {
    throw new Error(`"${definition.id}" is the kernel's own id: give the module another (cubic on #79).`);
  }
  checkRoutes(definition);
  checkSlots(definition);
  return definition;
}

/**
 * The site's own pages and the slots it fills (`mountApp({ site })`, decision
 * 0048): its `src/site/site.ts`. They're always on, with no switch on Features,
 * and win a tie with a module's route; a more fixed module route still wins.
 * No admin pages: those are a module's.
 */
export type SiteDefinition = {
  routes: {
    public: ModuleRoute[];
    member: ModuleRoute[];
  };
  /** The kernel slots the site fills, as a module's binding does. */
  slots?: Slots;
  /**
   * The site's header, drawn in place of the frame's on every page in the site
   * frame (not the sign-in or admin frames), after the frame's skip link. Its
   * root is a `<header>`. Build it from `SiteAccountLinks`, `SlotOutlet` and
   * `useSite`, so the modules' links and signing in still show. If it fails to
   * draw, the frame's own is drawn instead.
   */
  header?: ComponentType;
  /** The site's footer, in place of the frame's: its root is a `<footer>`, with `site.footer`'s entries where it puts them. */
  footer?: ComponentType;
};

/** The parts of the site frame a site gives: its header and footer. */
export type SiteFrameParts = Pick<SiteDefinition, "header" | "footer">;

/** A function component, or one React wraps (memo, forwardRef, lazy), all objects with `$$typeof`. */
function isComponent(value: unknown): boolean {
  return typeof value === "function" || (typeof value === "object" && value !== null && "$$typeof" in value);
}

function checkFrame(site: SiteDefinition): void {
  for (const part of ["header", "footer"] as const) {
    const given: unknown = site[part];
    if (given !== undefined && !isComponent(given)) {
      const name = part === "header" ? "Header" : "Footer";
      throw new Error(`The site's ${part} must be a component, such as \`${part}: ${name}\`.`);
    }
  }
}

/** The site's header and footer, as the frame reads them; none for a site that gives neither. */
export function siteFrame(site?: SiteDefinition): SiteFrameParts {
  return {
    ...(site?.header ? { header: site.header } : {}),
    ...(site?.footer ? { footer: site.footer } : {}),
  };
}

/** The site as the router and the slots read it: a module that's always on, under the id `SITE`. */
export function siteModule(site: SiteDefinition): ModuleDefinition {
  checkFrame(site);
  const definition: ModuleDefinition = {
    id: SITE,
    routes: { public: site.routes.public, member: site.routes.member, admin: [] },
    ...(site.slots ? { slots: site.slots } : {}),
  };
  checkRoutes(definition);
  checkSlots(definition);
  return definition;
}

/**
 * Registers the site's own pages, in `src/site/site.ts`. Checks them as
 * `defineModule` checks a module's: nothing under /admin, no path given twice,
 * no route that takes one of the kernel's pages, and slot entries the kernel
 * can show. A header or footer it gives must be a component.
 */
export function defineSite(site: SiteDefinition): SiteDefinition {
  siteModule(site);
  return site;
}
