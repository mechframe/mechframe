# kernel/web

`index.ts` is the public surface; `testing.ts` is for tests only (`@/kernel/testing`).

Built:

- **The typed client** (`src/api/`): `api`, `useApiQuery`, `useApiMutation` and `apiQueryOptions` for the kernel's paths, `createApiClient<paths>()` for a module's, and `ApiProblem`, thrown by any answer but a success. Its types, `src/api/schema.ts`, are generated from `kernel/openapi.json` (`npm run api:types`; decision 0042).
- **`defineModule`** (`src/modules.ts`): a module's routes and its typed slots (`src/slots/types.ts`), checked. **`defineSite`** beside it: the site's own pages and slots, for `mountApp({ site })`, always on and first in a tie, and its own `header` and `footer` for the site frame (decision 0048). A route's `bleed: true` runs its page edge to edge.
- **The app shell** (`src/app/`): `mountApp` (a data router, `createRoot`), the site and admin frames (`SiteAccountLinks`, the site frame's account links, for a site's own header; `AfterFooter`, a page's part after the site frame's footer, such as a docked player), the kernel's own pages (`pages.ts`, held to `kernel.json`), the home, 404, no-access and unreachable pages, the router's error page, and the CSS that hides the server's words until React replaces them (`server-copy.css`).
- **The session** (`src/session/`): `useSession`, `useSignOut`. **The guards** (`src/guards/`): `RequireAuth`, `RequirePermission`, `RequireAdmin`, and `safeNext` for a sign-in's way back.
- **The slots** (`src/slots/`): `useSlot`, `SlotOutlet`, and the admin sidebar's order. **The site** (`src/site/`): `useSite`, `useModuleEnabled`. **`<Seo>`** (`src/seo/`). **Consent** (`src/consent/`, hook 6): `useConsent(category)` and `<ConsentGate category fallback>`, holding a third-party script or iframe until its category is granted, the choice kept in the cookie `__Host-mf_consent`.

- **The UI kit** (`src/ui/`, its `README.md`): every part a screen is built from, with `RouteFocus`, `ScrollMemory` and `ErrorBoundary`, the toasts and the icon set.

- **The look** comes from the site's theme (`themes/`, `<html data-theme>`): `frames.css` puts the page, text, type, links and focus on its `--mf-*` tokens and holds no colour of its own.

Planned (the rest of K4, `dev plans/contracts/k4-web-kernel.md`): `SignedInDevices` with the account screens, `useSettings`, and the auth, account and admin screens.
