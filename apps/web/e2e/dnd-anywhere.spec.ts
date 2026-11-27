import { expect, type Page, test } from "@playwright/test";

async function open(page: Page, route: string) {
  await page.goto(`/#/${route}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
}
const nav = (page: Page, label: string) => page.locator(".sidebar .nav-item", { hasText: label }).first();

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  (page as unknown as { errors: string[] }).errors = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as unknown as { errors: string[] }).errors).toEqual([]);
});

test("backlog task dropped on sidebar Today is planned for today", async ({ page, request }) => {
  await open(page, "backlog");
  const card = page.locator(".list .task-card", { hasText: "Read: 'Lost in the Middle'" });
  await card.dragTo(nav(page, "Today"));
  await expect(page.locator("[data-sonner-toast]", { hasText: "Planned for Today" })).toBeVisible();
  const today = await (await request.get("/api/today")).json();
  expect(today.tasks.map((t: { title: string }) => t.title)).toContain("Read: 'Lost in the Middle' (long-context retrieval)");
});

test("task dropped on a project card moves into that project", async ({ page, request }) => {
  await open(page, "projects");
  await page.locator(".project-card", { hasText: "Model Evaluation" }).click();
  // wait until the list shows that project's tasks before picking a card
  await expect(page.getByRole("heading", { name: "Model Evaluation", level: 3 })).toBeVisible();
  await expect(page.locator(".list .task-card", { hasText: "Run regression evals" })).toBeVisible();
  await page.waitForLoadState("networkidle"); // project cards settle (counts refresh) before the drag
  const card = page.locator(".list .task-card").first();
  const title = (await card.locator(".t-title").innerText()).trim();
  // a stepwise gesture, like a real pointer (one-step dragTo is unreliable for HTML5 drag)
  const from = (await card.locator(".t-title").boundingBox())!;
  const to = (await page.locator(".project-card", { hasText: "Deep Learning Reading Group" }).boundingBox())!;
  await page.mouse.move(from.x + 10, from.y + from.height / 2);
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) {
    await page.mouse.move(from.x + 10 + ((to.x + to.width / 2 - from.x - 10) * i) / 12, from.y + from.height / 2 + ((to.y + to.height / 2 - from.y - from.height / 2) * i) / 12);
  }
  await page.mouse.up();
  // check the outcome, not the transient toast
  const projects = (await (await request.get("/api/projects")).json()) as { id: string; name: string }[];
  const dl = projects.find((p) => p.name === "Deep Learning Reading Group")!;
  await expect
    .poll(async () => ((await (await request.get(`/api/tasks?project_id=${dl.id}`)).json()) as { title: string }[]).map((t) => t.title))
    .toContain(title);
});

test("note dropped on Prompt Book becomes a page", async ({ page }) => {
  await open(page, "notes");
  await page.locator(".note-item", { hasText: "Hybrid retrieval" }).dragTo(nav(page, "Prompt Book"));
  await expect(page.locator("[data-sonner-toast]", { hasText: "Added to your Prompt Book" })).toBeVisible();
  await expect(page.locator("input.page-title")).toHaveValue("Hybrid retrieval — design notes");
});

test("board card dragged onto sidebar Backlog is unscheduled", async ({ page, request }) => {
  await open(page, "today");
  const card = page.locator('section.column[aria-label="Planned"] .task-card').first();
  const title = (await card.locator(".t-title").innerText()).trim();
  const a = (await card.boundingBox())!;
  const b = (await nav(page, "Backlog").boundingBox())!;
  await page.mouse.move(a.x + 30, a.y + 12);
  await page.mouse.down();
  for (let i = 1; i <= 15; i++) await page.mouse.move(a.x + 30 + ((b.x + 40 - a.x - 30) * i) / 15, a.y + 12 + ((b.y + b.height / 2 - a.y - 12) * i) / 15);
  await page.mouse.up();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Moved to the backlog" })).toBeVisible();
  const backlog = (await (await request.get("/api/tasks?status=backlog")).json()) as { title: string }[];
  expect(backlog.map((t) => t.title)).toContain(title);
});
