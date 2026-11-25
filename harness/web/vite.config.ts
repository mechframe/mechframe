import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const kernel = fileURLToPath(new URL("../../kernel/web/index.ts", import.meta.url));
// Another module's public surface, as `@/modules/<id>/public` (SPEC 7, decision 0057).
const modules = fileURLToPath(new URL("../../modules/", import.meta.url));

// The harness's web app. `npm run dev` serves it on 5173 and sends /api to the
// harness's FastAPI app on 8000 (`python -m uvicorn harness.main:app`). Four
// pages: the app (index.html), the UI kit's (kit.html, at /kit.html), the site
// frame with a site's own header and footer (frame.html, at /frame.html), and
// audio-player's parts (player.html, at /player.html).
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      input: {
        main: fileURLToPath(new URL("./index.html", import.meta.url)),
        kit: fileURLToPath(new URL("./kit.html", import.meta.url)),
        frame: fileURLToPath(new URL("./frame.html", import.meta.url)),
        player: fileURLToPath(new URL("./player.html", import.meta.url)),
      },
    },
  },
  resolve: {
    alias: [
      { find: /^@\/kernel$/, replacement: kernel },
      { find: /^@\/modules\/([a-z][a-z0-9-]*)\/public$/, replacement: `${modules}$1/web/public.ts` },
    ],
  },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
