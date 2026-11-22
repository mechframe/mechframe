import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const kernel = fileURLToPath(new URL("./src/kernel/index.ts", import.meta.url));
const testing = fileURLToPath(new URL("./src/kernel/testing.ts", import.meta.url));
// Another module's public surface, as `@/modules/<id>/public` (SPEC 7, decision 0057).
const modules = fileURLToPath(new URL("./src/modules/", import.meta.url));

// This site's web app. `npm run dev` serves it on 5173 and sends /api to the
// site's FastAPI app on 8000; `npm run build` writes dist/, which the backend
// serves as WEB_DIST. `npm test` runs Vitest on the site's own pages: the
// kernel's and the modules' are tested where MechFrame keeps them.
export default defineConfig({
  plugins: [react()],
  // Exact names: "@/kernel" alone would also catch "@/kernel/testing".
  resolve: {
    alias: [
      { find: /^@\/kernel\/testing$/, replacement: testing },
      { find: /^@\/kernel$/, replacement: kernel },
      { find: /^@\/modules\/([a-z][a-z0-9-]*)\/public$/, replacement: `${modules}$1/public.ts` },
    ],
  },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  // A font is never inlined as a data: address, which the kernel's security
  // policy refuses (font-src 'self'): Vite inlines any file under 4 KB, and a
  // font's smaller subsets are (VM Website's first deploy, 2026-11-22; e2e
  // "every page loads with no console error once its fonts are in"). Other
  // small files keep Vite's default.
  build: { assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf)$/i.test(file) ? false : undefined) },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/site/**/*.test.{ts,tsx}"],
    testTimeout: 15_000,
    restoreMocks: true,
    unstubGlobals: true,
  },
});
