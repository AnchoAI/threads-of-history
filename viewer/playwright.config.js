import { defineConfig } from "@playwright/test";

// Run `npm run data` first so ../dist/graph.json exists.
// PLAYWRIGHT_CHROMIUM_PATH lets you point at an already-installed Chromium;
// otherwise run `npx playwright install chromium` once.
export default defineConfig({
  testDir: "tests",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:5174",
    viewport: { width: 1400, height: 900 },
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined,
      args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    },
  },
  webServer: {
    command: "npx vite --port 5174 --strictPort",
    url: "http://localhost:5174",
    reuseExistingServer: !process.env.CI,
  },
});
