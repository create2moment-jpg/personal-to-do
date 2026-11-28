import { expect, test } from "@playwright/test";

test("habits: off until turned on, then tick today and see the streak", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/#/today");
  const dock = page.getByRole("complementary", { name: "Gadgets" });
  await expect(dock).toBeVisible();
  await expect(dock.locator(".habits-card")).toHaveCount(0); // opt-in

  await page.goto("/#/settings/gadgets");
  await page.getByRole("checkbox", { name: "Show Habits" }).check();
  await page.goto("/#/today");
  const card = page.locator(".habits-card");
  await card.getByLabel("Add a habit").fill("Walk 20 min");
  await card.getByLabel("Add a habit").press("Enter");
  await card.getByRole("checkbox", { name: "Walk 20 min done today" }).check();
  await expect(card.locator(".habit-streak", { hasText: "🔥1" })).toBeVisible();

  await page.goto("/#/settings/gadgets");
  await page.getByRole("button", { name: "Reset to defaults" }).click();
});
