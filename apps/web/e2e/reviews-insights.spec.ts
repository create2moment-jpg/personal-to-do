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
  expect((page as unknown as { errors: string[] }).errors).toEqual([]);
});

test("reviews: open this month, numbers from records, grounded AI draft, use a suggestion, finalize", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await open(page, "reviews");
  const month = new Date().toLocaleString("en-US", { month: "long" });
  await page.locator(".note-item", { hasText: `${month} ${new Date().getFullYear()}` }).first().click();
  await expect(page.locator(".review-doc .page-title")).toContainText(month);
  await expect(page.locator(".stat", { hasText: "Tasks completed" })).toBeVisible();

  await page.getByRole("button", { name: "Draft with AI" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Draft ready" })).toBeVisible({ timeout: 15_000 });
  // the invented "300 percent" bullet never reaches the page
  await expect(page.locator(".dropped-box")).toContainText("dropped");
  await expect(page.locator(".review-doc")).not.toContainText("300 percent impact [S1]Use");
  await expect(page.locator(".ai-suggestion", { hasText: "300 percent" })).toHaveCount(0);
  const highlights = page.locator(".review-section", { hasText: "Highlights" });
  await expect(highlights.locator(".cite").first()).toBeVisible();
  await highlights.getByRole("button", { name: "Use", exact: true }).first().click();
  await expect(highlights.locator("textarea")).toHaveValue(/^- .+\[S1\]/);

  await page.getByRole("button", { name: "Copy" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Copied as Markdown" })).toBeVisible();

  await page.getByRole("button", { name: "Finalize" }).click();
  await expect(page.locator(".page-sub")).toContainText("numbers frozen");
  await expect(highlights.locator("textarea")).toHaveAttribute("readonly", "");
  await page.getByRole("button", { name: "Reopen" }).click();
  await expect(page.getByRole("button", { name: "Finalize" })).toBeVisible();
});
