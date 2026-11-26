import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// У розробці API живе на 8000, у проді — той самий origin, тому проксі лише для dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/healthz": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
