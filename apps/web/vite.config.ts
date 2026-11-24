import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the API so the browser talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8765" },
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
