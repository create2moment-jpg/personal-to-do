import { expect, test } from "@playwright/test";

test("reminders: off by default; once on, a meeting starting soon is announced once", async ({ page, request }) => {
  const start = new Date(Date.now() + 3 * 60_000).toISOString();
  await request.post("/api/meetings", { data: { title: "Reminder e2e sync", start_at: start, minutes: 15 } });
  await page.goto("/#/today");
  await page.waitForTimeout(1500);
  await expect(page.locator("[data-sonner-toast]", { hasText: "Reminder e2e sync" })).toHaveCount(0); // off by default

  await page.goto("/#/settings");
  await page.getByLabel("Turn reminders on").check();
  // fires right away, wherever you are (toasts stack, so check it exists)
  await expect(page.locator("[data-sonner-toast]", { hasText: /Reminder e2e sync in \d min/ })).toHaveCount(1, { timeout: 10_000 });
  await page.reload();
  await page.waitForTimeout(1500);
  await expect(page.locator("[data-sonner-toast]", { hasText: "Reminder e2e sync" })).toHaveCount(0); // not twice
  await page.goto("/#/settings");
  await page.getByLabel("Turn reminders on").uncheck();
});
