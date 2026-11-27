import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against a synthetic demo workspace (scripts/e2e-server.sh).
// Build the UI first: `npm run build`.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:8799",
    // the e2e server runs with this fixed API token (scripts/e2e-server.sh); pages also get the cookie
    extraHTTPHeaders: { Authorization: "Bearer e2e-local-token-0123456789abcdefghij" },
    viewport: { width: 1600, height: 1000 },
    trace: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } } }],
  webServer: {
    command: "bash ../../scripts/e2e-server.sh",
    url: "http://127.0.0.1:8799/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
