import { expect, type Page, test } from "@playwright/test";

async function open(page: Page, route: string) {
  await page.goto(`/#/${route}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
}

test.beforeEach(async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  (page as unknown as { errors: string[] }).errors = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as unknown as { errors: string[] }).errors).toEqual([]);
});

test("book: chapters, pages and page turning", async ({ page }) => {
  await open(page, "book");
  await expect(page.getByRole("tree", { name: "Table of contents" })).toContainText("Code quality");
  const first = await page.locator(".page-title").inputValue();
  await page.locator(".book-desk").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("ArrowRight");
  await expect(page.locator(".page-title")).not.toHaveValue(first);
  await expect(page.locator(".page-no")).toContainText("Page 2 of");
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator(".page-title")).toHaveValue(first);
});

test("book: write a prompt, copy with variables filled in", async ({ page }) => {
  await open(page, "book");
  await page.locator(".toc-row", { hasText: "Testing" }).hover();
  await page.getByRole("button", { name: "Add page to Testing" }).click();
  await expect(page.locator(".page-sheet")).toHaveCount(1);
  await expect(page.locator(".page-title")).toHaveValue("");
  await page.locator(".page-title").fill("Integration test");
  await page.locator(".page-body").fill("Write an integration test for {{endpoint}} using {{client}}");
  await expect(page.locator(".page-vars")).toContainText("{{endpoint}}");
  await expect(page.locator(".sheet-meta")).toContainText("Saved", { timeout: 5000 });
  await page.getByRole("button", { name: "Copy for Copilot" }).click();
  await page.locator(".dialog input").nth(0).fill("/api/today");
  await page.locator(".dialog input").nth(1).fill("TestClient");
  await page.getByRole("button", { name: "Copy", exact: true }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Copied" })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("Write an integration test for /api/today using TestClient");
  await expect(page.locator(".toc-row", { hasText: "Integration test" })).toBeVisible();
});

test("book: improve with local AI keeps the original", async ({ page }) => {
  await open(page, "book");
  await page.locator(".toc-row", { hasText: "Refactor long function" }).click();
  await expect(page.locator(".page-sheet")).toHaveCount(1);
  await expect(page.locator(".page-title")).toHaveValue("Refactor long function");
  const original = await page.locator(".page-body").inputValue();
  await page.getByRole("button", { name: "Improve with AI" }).click();
  await expect(page.locator(".improve")).toContainText("fake-llm");
  await page.getByRole("radio", { name: /More specific/ }).click();
  await page.getByRole("button", { name: "Improve", exact: true }).click();
  await expect(page.locator(".compare")).toContainText("Goal:");
  await page.getByRole("button", { name: "Use suggestion" }).click();
  await expect(page.locator(".page-body")).toHaveValue(/^Goal:/);
  await page.getByRole("button", { name: "History" }).click();
  await expect(page.locator(".sheet")).toContainText("AI suggestion");
  await page.locator(".sheet .note-item", { hasText: "Original" }).click();
  await expect(page.locator(".history-text")).toHaveText(original);
});

test("book: search finds pages from the command menu", async ({ page }) => {
  await open(page, "today");
  await page.keyboard.press("Control+k");
  await page.keyboard.type("hypothesis");
  await page.locator("[cmdk-item]", { hasText: "Unit tests for a function" }).click();
  await expect(page.locator(".page-title")).toHaveValue("Unit tests for a function");
});
