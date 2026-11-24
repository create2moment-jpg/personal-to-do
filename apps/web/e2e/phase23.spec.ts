import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
import { expect, type Page, test } from "@playwright/test";

async function open(page: Page, route: string) {
  await page.goto(`/#/${route}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
}

async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) await page.mouse.move(from.x + ((to.x - from.x) * i) / 12, from.y + ((to.y - from.y) * i) / 12);
  await page.mouse.up();
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

test("week: drag sprint backlog work onto a day", async ({ page }) => {
  await open(page, "week");
  const card = page.locator('section[aria-label="Sprint backlog"] .task-card').first();
  const title = (await card.locator(".t-title").innerText()).trim();
  const target = page.locator("section.week-day").nth(5); // Saturday (empty, short)
  await card.scrollIntoViewIfNeeded();
  const a = (await card.boundingBox())!;
  const b = (await target.boundingBox())!;
  await drag(page, { x: a.x + 30, y: a.y + 12 }, { x: b.x + b.width / 2, y: b.y + 70 });
  await expect(target.getByText(title)).toBeVisible();
});

test("week: objectives and weekly review", async ({ page }) => {
  await open(page, "week");
  await expect(page.getByLabel("Objective 1", { exact: true })).toHaveValue(/ADR/);
  await page.getByRole("tab", { name: "Weekly review" }).click();
  await expect(page.getByText("Meetings vs. focus")).toBeVisible();
  await expect(page.locator(".stat-label", { hasText: "Completed" })).toBeVisible();
});

test("sprint: burndown, lanes and committing backlog work", async ({ page }) => {
  await open(page, "sprint");
  await expect(page.locator(".chart svg[aria-label^='Burndown']")).toBeVisible();
  await page.getByRole("button", { name: "Add from backlog" }).click();
  const row = page.locator(".dialog .list-row", { hasText: "Plan Q1 objectives" });
  await row.getByRole("button", { name: "Commit" }).click();
  await page.keyboard.press("Escape");
  await expect(page.locator('section[aria-label="Committed work"]').getByText("Plan Q1 objectives")).toBeVisible();
});

test("meetings: skipping a recurring series frees capacity", async ({ page, request }) => {
  const day = (await (await request.get("/api/today")).json()).day as string;
  const before = (await (await request.get(`/api/today?day=${day}`)).json()).plan.capacity_minutes as number;
  await open(page, "meetings");
  await page.getByRole("tab", { name: "Recurring" }).click();
  const row = page.locator(".series-row", { hasText: "Team standup" });
  await row.getByRole("button", { name: "Not attending", exact: true }).click();
  await expect(row).toHaveClass(/skipped/);
  const after = (await (await request.get(`/api/today?day=${day}`)).json()).plan.capacity_minutes as number;
  const weekday = new Date(`${day}T12:00:00Z`).getUTCDay();
  if (weekday >= 1 && weekday <= 5) expect(after).toBeGreaterThan(before);
  await row.getByRole("button", { name: "Attending", exact: true }).click();
  await expect(row).not.toHaveClass(/skipped/);
});

test("meetings: log a call with the dialog", async ({ page }) => {
  await open(page, "meetings");
  await page.getByRole("button", { name: "Log a call" }).first().click();
  await page.getByPlaceholder("Name — Enter or comma to add").fill("Yuki");
  await page.keyboard.press("Enter");
  await page.getByPlaceholder("e.g. ADR review, 1:1, debugging session").fill("Vector index design");
  await page.getByPlaceholder("e.g. Retrieval, Hiring, Career").fill("Retrieval");
  await page.locator(".lc-quick button", { hasText: "45m" }).click();
  await page.getByRole("button", { name: "Log call" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Call logged" })).toBeVisible();
  await page.getByRole("tab", { name: "Insights" }).click();
  await expect(page.locator(".rank-bars", { hasText: "Yuki" })).toBeVisible();
});

test("capture: call: grammar logs a call", async ({ page, request }) => {
  await open(page, "today");
  await page.keyboard.press("c");
  await page.locator(".capture-input").fill("call: Zoe / Design chat ~20m #design");
  await expect(page.locator(".capture-preview")).toContainText("Zoe");
  await expect(page.locator(".capture-preview")).toContainText("20m");
  await page.locator(".capture-input").press("Enter");
  await expect(page.locator("[data-sonner-toast]")).toBeVisible();
  const people = (await (await request.get("/api/people")).json()) as { name: string }[];
  expect(people.map((p) => p.name)).toContain("Zoe");
});

test("calendar: import an .ics file", async ({ page }) => {
  await open(page, "meetings");
  await page.locator('input[type="file"]').first().setInputFiles(path.resolve(here, "../../../fixtures/calendar/sample.ics"));
  await expect(page.locator("[data-sonner-toast]", { hasText: "Imported" })).toBeVisible();
  await page.getByRole("tab", { name: "Recurring" }).click();
  await expect(page.locator(".series-row", { hasText: "Architecture review" }).first()).toBeVisible();
});

test("settings: time zone and working hours", async ({ page, request }) => {
  await open(page, "settings");
  await expect(page.getByLabel("Time zone")).toHaveValue("Europe/Berlin");
  await page.getByLabel("Time zone").selectOption("Europe/London");
  await expect(page.locator("[data-sonner-toast]", { hasText: "Settings saved" })).toBeVisible();
  expect((await (await request.get("/api/settings")).json()).timezone).toBe("Europe/London");
  await page.getByLabel("Time zone").selectOption("Europe/Berlin");
});
