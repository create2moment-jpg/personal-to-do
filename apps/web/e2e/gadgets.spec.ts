import { expect, test } from "@playwright/test";

test("gadget dock: on every page, collapsible, calendar opens a day, choose gadgets", async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/#/notes"); // a wide page: starts as a slim strip
  const slim = page.getByRole("complementary", { name: "Gadgets (collapsed)" });
  await expect(slim).toBeVisible();
  await slim.getByRole("button", { name: "Expand gadgets" }).click();
  const dock = page.getByRole("complementary", { name: "Gadgets" });
  await expect(dock.locator(".clock-time")).toBeVisible();
  await expect(dock).toContainText("Today’s meetings");

  // calendar: click a day → Today opens on that day
  const cal = dock.locator(".cal-grid");
  await cal.getByRole("button", { name: /-15/ }).first().click();
  await expect(page).toHaveURL(/#\/today\/\d{4}-\d{2}-15/);

  // ask from anywhere → Assistant with the question filled in
  await dock.getByLabel("Ask the assistant").fill("What did I decide about retrieval?");
  await dock.getByLabel("Ask the assistant").press("Enter");
  await expect(page.locator("textarea.ask-input")).toHaveValue("What did I decide about retrieval?");

  // Settings → Gadgets: hide the calendar
  await page.goto("/#/settings/gadgets");
  await page.getByRole("checkbox", { name: "Show Calendar" }).uncheck();
  await page.goto("/#/today");
  await expect(page.getByRole("complementary", { name: "Gadgets" }).locator(".cal-grid")).toHaveCount(0);
  await page.goto("/#/settings/gadgets");
  await page.getByRole("button", { name: "Reset to defaults" }).click();
});

test("gadget dock on a laptop screen is a drawer that closes on Escape", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/#/week");
  await page.getByRole("button", { name: "Expand gadgets" }).click();
  const dock = page.getByRole("complementary", { name: "Gadgets" });
  await expect(dock.locator(".clock-time")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("complementary", { name: "Gadgets (collapsed)" })).toBeVisible();
});
