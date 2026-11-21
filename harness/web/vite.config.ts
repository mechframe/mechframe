import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const kernel = fileURLToPath(new URL("../../kernel/web/index.ts", import.meta.url));

// The harness's web app. `npm run dev` serves it on 5173 and sends /api to the
// harness's FastAPI app on 8000 (`python -m uvicorn harness.main:app`). Three
// pages: the app (index.html), the UI kit's (kit.html, at /kit.html), and the
// site frame with a site's own header and footer (frame.html, at /frame.html).
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      input: {
        main: fileURLToPath(new URL("./index.html", import.meta.url)),
        kit: fileURLToPath(new URL("./kit.html", import.meta.url)),
        frame: fileURLToPath(new URL("./frame.html", import.meta.url)),
      },
    },
  },
  resolve: { alias: { "@/kernel": kernel } },
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
