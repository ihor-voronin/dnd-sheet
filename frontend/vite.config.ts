import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API lives on 8000, in production on the same origin, so the proxy is dev-only.
// In the dev container (`docker compose --profile dev up`) the API is a neighboring service: VITE_API_TARGET.
const api = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The editor writes files through temporary directories next to them; there's no need
    // to watch those, and on Windows trying to open such a directory crashes the watcher.
    watch: { ignored: ["**/*.tmpdir/**", "**/.*.tmpdir/**"] },
    proxy: {
      "/api": api,
      "/healthz": api,
      // Server-rendered pages: the compendium, guides, sitemaps (backend/src/dndsheet/site).
      "/kb": api,
      "/guides": api,
      "/sitemap.xml": api,
      "/sitemaps": api,
      "/robots.txt": api,
      "/llms.txt": api,
      // Portraits are drawn by the server (backend/src/dndsheet/visuals).
      "/assets/avatars": api,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
