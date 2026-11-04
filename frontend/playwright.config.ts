import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a running stack (API on :8000 with seeded data, RAZORPAY_MODE=mock,
 * RATE_LIMIT_ENABLED=false) and the Vite dev server, which this config starts automatically.
 *   npx playwright install chromium   # once
 *   npm run e2e
 * Set PW_CHROMIUM_PATH to reuse an existing Chromium binary (offline environments).
 */
const executablePath = process.env.PW_CHROMIUM_PATH;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: /mobile\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "npx vite --port 5173 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
