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

test("add meetings manually from Today, the Recurring tab and the command menu", async ({ page, request }) => {
  // Today: one-time meeting
  await open(page, "today");
  await page.getByRole("button", { name: "Add meeting" }).click();
  let dialog = page.getByRole("dialog", { name: "New meeting" });
  await expect(dialog.getByRole("group", { name: "Repeat" }).getByRole("button", { name: "Once" })).toHaveAttribute("aria-pressed", "true");
  await dialog.getByPlaceholder(/Team stand-up/).fill("E2E today sync");
  await dialog.getByLabel("Duration").fill("35");
  await dialog.getByRole("button", { name: "Add meeting" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Meeting added" })).toBeVisible();

  // Recurring tab: dedicated button opens the dialog already set to repeat
  await open(page, "meetings");
  await page.getByRole("tab", { name: "Recurring" }).click();
  await page.getByRole("button", { name: "Add recurring meeting" }).click();
  dialog = page.getByRole("dialog", { name: "New meeting" });
  await expect(dialog.getByRole("group", { name: "Repeat" }).getByRole("button", { name: "Weekly" })).toHaveAttribute("aria-pressed", "true");
  await dialog.getByPlaceholder(/Team stand-up/).fill("E2E weekly 1:1");
  await dialog.getByRole("button", { name: "Add meeting" }).click();
  await expect(page.locator(".series-row", { hasText: "E2E weekly 1:1" })).toBeVisible();

  // Command menu
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder(/Search/).first().fill("recurring meeting");
  await page.getByRole("option", { name: "New recurring meeting" }).click();
  await expect(page.getByRole("dialog", { name: "New meeting" })).toBeVisible();
  await page.keyboard.press("Escape");

  const series = (await (await request.get("/api/meeting-series")).json()) as { title: string; series_key: string }[];
  await request.delete(`/api/meeting-series/${encodeURIComponent(series.find((s) => s.title === "E2E weekly 1:1")!.series_key)}`);
});

test("quick capture adds one-time and recurring meetings with a live preview", async ({ page, request }) => {
  await open(page, "today");
  await page.keyboard.press("c");
  const input = page.getByLabel("Capture text");
  await input.fill("meeting: E2E capture standup @06:15 ~15m weekdays with Ana #team");
  const preview = page.locator(".capture-preview");
  await expect(preview).toContainText("Recurring meeting");
  await expect(preview).toContainText("Every weekday");
  await expect(preview).toContainText("15m");
  await expect(preview).toContainText("Ana");
  await input.press("Enter");
  await expect(page.locator("[data-sonner-toast]", { hasText: "Meeting added" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Quick capture" })).toHaveCount(0);

  await page.keyboard.press("c");
  await page.getByLabel("Capture text").fill("mtg: E2E capture review @tomorrow @14:00 ~50m");
  await expect(page.locator(".capture-preview")).toContainText("E2E capture review");
  await expect(page.locator(".capture-preview")).toContainText("50m");
  await page.getByLabel("Capture text").press("Enter");
  await expect(page.locator("[data-sonner-toast]", { hasText: "E2E capture review" })).toBeVisible();

  const series = (await (await request.get("/api/meeting-series")).json()) as { title: string; series_key: string; plan: { minutes: number } }[];
  const s = series.find((x) => x.title === "E2E capture standup")!;
  expect(s.plan.minutes).toBe(15);
  await request.delete(`/api/meeting-series/${encodeURIComponent(s.series_key)}`);
});

test("repeating task: set a repeat in the task panel; completing it creates the next one", async ({ page, request }) => {
  const created = await (await request.post("/api/tasks", { data: { title: "E2E repeating report", scheduled_date: new Date().toISOString().slice(0, 10) } })).json();
  await open(page, "today");
  await page.locator(".task-card", { hasText: "E2E repeating report" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Task details" });
  await sheet.getByLabel("Repeats").selectOption("weekdays");
  await expect(sheet.locator(".repeat-help")).toContainText("Every weekday");
  await page.keyboard.press("Escape");
  const card = page.locator(".task-card", { hasText: "E2E repeating report" }).first();
  await expect(card.getByLabel("Every weekday")).toBeVisible();
  await card.getByRole("checkbox", { name: "Mark as done" }).click();
  await expect
    .poll(async () => ((await (await request.get("/api/tasks?limit=1000")).json()) as { title: string; status: string; recurrence: string | null }[]).filter((t) => t.title === "E2E repeating report" && t.status !== "done" && t.recurrence === "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR").length)
    .toBe(1);
  expect(created.id).toBeTruthy();
});

test("delete a task with undo, then restore another from Recently deleted", async ({ page, request }) => {
  await request.post("/api/tasks", { data: { title: "E2E trash me" } });
  await request.post("/api/tasks", { data: { title: "E2E trash me too" } });
  await open(page, "backlog");
  // delete + Undo from the toast
  await page.locator(".task-card", { hasText: "E2E trash me" }).first().click();
  await page.getByRole("dialog", { name: "Task details" }).getByRole("button", { name: "Delete task" }).click();
  const toastEl = page.locator("[data-sonner-toast]", { hasText: "to the trash" });
  await expect(toastEl).toBeVisible();
  await toastEl.getByRole("button", { name: "Undo" }).click();
  await expect(page.locator(".list .task-card", { hasText: "E2E trash me" }).first()).toBeVisible();

  // delete the other one, restore it from the Recently deleted panel
  await page.locator(".task-card", { hasText: "E2E trash me too" }).click();
  await page.getByRole("dialog", { name: "Task details" }).getByRole("button", { name: "Delete task" }).click();
  await expect(page.locator(".list .task-card", { hasText: "E2E trash me too" })).toHaveCount(0);
  await page.locator(".trash-panel summary").click();
  await page.locator(".trash-row", { hasText: "E2E trash me too" }).getByRole("button", { name: "Restore" }).click();
  await expect(page.locator(".list .task-card", { hasText: "E2E trash me too" })).toBeVisible();
});
