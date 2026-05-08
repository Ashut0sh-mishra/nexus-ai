import { defineConfig, devices } from "@playwright/test";

// Playwright config — gallery regression tests.
// Spawns the Vite dev server, navigates to /gallery, snapshots every layout,
// and asserts ZERO console warnings (catches Unsupported-layout regressions).
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5179",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // Pin to a dedicated port so Playwright doesn't fight ports 5173-5176
    // that may be held by an active dev session.
    command: "npx vite --port 5179 --strictPort",
    url: "http://localhost:5179",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
