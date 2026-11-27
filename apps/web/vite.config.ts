import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** The API token for the dev proxy: PPOS_API_TOKEN, else <data dir>/config/api_token. */
function apiToken(): string {
  if (process.env.PPOS_API_TOKEN) return process.env.PPOS_API_TOKEN;
  const dir = (process.env.PPOS_LOCAL_DATA_DIR ?? join(homedir(), "PersonalProductivityData")).replace(/^~/, homedir());
  try {
    return readFileSync(join(dir, "config", "api_token"), "utf8").trim();
  } catch {
    return ""; // start `ppos serve` once to create it
  }
}

// Dev server proxies the API so the browser talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        configure: (proxy) => proxy.on("proxyReq", (req) => req.setHeader("Authorization", `Bearer ${apiToken()}`)),
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          ui: ["framer-motion", "@tanstack/react-query", "cmdk", "sonner", "@dnd-kit/core", "@dnd-kit/sortable"],
        },
      },
    },
  },
});
