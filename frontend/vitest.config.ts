import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      // Rendering whole screens (the sheet, the wizard) takes a few seconds on CI.
      testTimeout: 60_000,
      coverage: {
        provider: "v8",
        include: ["src/**/*.{ts,tsx}"],
        exclude: ["src/test/**", "src/**/*.test.{ts,tsx}", "src/contract/**", "src/main.tsx", "src/vite-env.d.ts"],
        // text — in the log; cobertura — for diff-cover on PRs; json-summary — for the badge.
        reporter: ["text-summary", "cobertura", "json-summary"],
        reportsDirectory: "coverage",
        thresholds: { lines: 80, statements: 80 },
      },
    },
  }),
);
