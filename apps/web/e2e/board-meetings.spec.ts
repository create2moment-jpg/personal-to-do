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

async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(from.x + ((to.x - from.x) * i) / 10, from.y + ((to.y - from.y) * i) / 10);
  await page.mouse.up();
}

test("task board: all states, quick add with a custom time, drag between states", async ({ page }) => {
  await open(page, "board");
  for (const name of ["Backlog", "Planned", "In progress", "Blocked", "Completed"]) await expect(page.getByRole("region", { name, exact: true })).toBeVisible();
  const backlog = page.getByRole("region", { name: "Backlog", exact: true });
  await backlog.getByPlaceholder(/Add to backlog/).fill("Board e2e task ~50m");
  await backlog.getByPlaceholder(/Add to backlog/).press("Enter");
  const card = backlog.locator(".task-card", { hasText: "Board e2e task" });
  await expect(card.locator(".duration-chip")).toHaveText(/50m/);

  // drag it to In progress
  const progress = page.getByRole("region", { name: "In progress", exact: true });
  const a = (await card.boundingBox())!;
  const b = (await progress.boundingBox())!;
  await drag(page, { x: a.x + 30, y: a.y + 12 }, { x: b.x + 60, y: b.y + 80 });
  await expect(progress.locator(".task-card", { hasText: "Board e2e task" })).toBeVisible();

  // change its time to an odd value from the card
  const moved = progress.locator(".task-card", { hasText: "Board e2e task" });
  await moved.locator(".duration-chip").click();
  await page.getByLabel("Custom duration").fill("1h20");
  await page.getByLabel("Custom duration").press("Enter");
  await expect(moved.locator(".duration-chip")).toHaveText(/1h 20m/);

  // completed filter
  const done = page.getByRole("region", { name: "Completed", exact: true });
  await done.getByRole("button", { name: "All" }).click();
  await expect(done.locator(".task-card").first()).toBeVisible();
});

test("meetings: add a recurring meeting with a custom duration, edit it, end it", async ({ page, request }) => {
  await open(page, "meetings");
  await page.getByRole("button", { name: "New meeting" }).click();
  const dialog = page.getByRole("dialog", { name: "New meeting" });
  await dialog.getByPlaceholder(/Team stand-up/).fill("E2E design sync");
  await dialog.getByLabel("Duration").fill("50");
  await dialog.getByRole("button", { name: "Weekly" }).click();
  await dialog.getByRole("group", { name: "Weekdays" }).getByRole("button", { name: "Tu" }).click();
  await dialog.getByRole("group", { name: "Weekdays" }).getByRole("button", { name: "Th" }).click();
  await expect(dialog.locator(".schedule-summary")).toContainText("50m");
  await dialog.getByRole("button", { name: "Add meeting" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Recurring meeting added" })).toBeVisible();

  const series = (await (await request.get("/api/meeting-series")).json()) as { title: string; source: string; plan: { minutes: number }; cadence: string }[];
  const mine = series.find((s) => s.title === "E2E design sync")!;
  expect(mine.source).toBe("app");
  expect(mine.plan.minutes).toBe(50);

  await page.getByRole("tab", { name: "Recurring" }).click();
  await page.getByRole("button", { name: "Edit E2E design sync" }).click();
  const edit = page.getByRole("dialog", { name: "Edit recurring meeting" });
  await edit.getByLabel("Duration").fill("1h10");
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Series updated" })).toBeVisible();
  const after = (await (await request.get("/api/meeting-series")).json()) as { title: string; plan: { minutes: number } }[];
  expect(after.find((s) => s.title === "E2E design sync")!.plan.minutes).toBe(70);

  page.once("dialog", (d) => void d.accept());
  await page.getByRole("button", { name: "End E2E design sync" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Series ended" })).toBeVisible();
});

test("one-off meeting with an odd duration shows up in the week's log", async ({ page }) => {
  await open(page, "meetings");
  await page.getByRole("button", { name: "New meeting" }).click();
  const dialog = page.getByRole("dialog", { name: "New meeting" });
  await dialog.getByPlaceholder(/Team stand-up/).fill("E2E one-off review");
  await dialog.getByLabel("Duration").fill("1h5");
  await dialog.getByRole("button", { name: "Add meeting" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Meeting added" })).toBeVisible();
  await page.getByRole("tab", { name: "Meetings & calls" }).click();
  await expect(page.locator(".meeting-row, [class*=meeting]", { hasText: "E2E one-off review" }).first()).toBeVisible();
});
