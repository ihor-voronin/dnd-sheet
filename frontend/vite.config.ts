import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// У розробці API живе на 8000, у проді — той самий origin, тому проксі лише для dev.
// У dev-контейнері (`docker compose --profile dev up`) API — сусідній сервіс: VITE_API_TARGET.
const api = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Редактор пише файли через тимчасові каталоги поруч; стежити за ними
    // не треба, а на Windows спроба відкрити такий каталог валить watcher.
    watch: { ignored: ["**/*.tmpdir/**", "**/.*.tmpdir/**"] },
    proxy: {
      "/api": api,
      "/healthz": api,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
