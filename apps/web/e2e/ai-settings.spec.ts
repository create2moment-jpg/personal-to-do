import { expect, type Page, test } from "@playwright/test";

async function open(page: Page, route: string) {
  await page.goto(`/#/${route}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  (page as unknown as { errors: string[] }).errors = errors;
});
test.afterEach(async ({ page }) => {
  // a refused endpoint legitimately logs its 422 response
  expect((page as unknown as { errors: string[] }).errors.filter((e) => !e.includes("status of 422"))).toEqual([]);
});

test("local AI settings: test an OpenAI-compatible endpoint, apply live, refuse remote", async ({ page, request }) => {
  await open(page, "settings");
  const panel = page.getByRole("region", { name: "Local AI" });
  await expect(panel.getByText("from .env")).toBeVisible();
  const endpoint = panel.getByPlaceholder("http://127.0.0.1:8080/v1");
  const good = await endpoint.inputValue();
  expect(good).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/v1$/);

  // Test connection does not change anything; the model is detected from /v1/models
  await panel.getByRole("button", { name: "Test connection" }).click();
  await expect(panel.getByRole("status")).toContainText("Connected to fake-llm");
  await expect(panel.getByRole("status")).toContainText("replied “OK”");

  // Apply new generation settings live
  await panel.getByLabel("Temperature").fill("0.1");
  await panel.getByRole("button", { name: "Apply" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Local AI settings applied" })).toBeVisible();
  await expect(panel.getByText("saved in the app")).toBeVisible();
  const cfg = await (await request.get("/api/ai/config")).json();
  expect(cfg.config.temperature).toBeCloseTo(0.1);
  expect(cfg.active.model).toBe("fake-llm");

  // A cloud endpoint is refused and nothing changes
  await endpoint.fill("https://api.example.com/v1");
  await panel.getByRole("button", { name: "Test connection" }).click();
  await expect(panel.getByRole("status")).toContainText("non-local");
  await panel.getByRole("button", { name: "Apply" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "non-local" })).toBeVisible();
  expect((await (await request.get("/api/ai/config")).json()).config.base_url).toBe(good);
  await endpoint.fill(good);
});
