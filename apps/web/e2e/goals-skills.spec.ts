import { expect, type Page, test } from "@playwright/test";

async function open(page: Page, route: string) {
  await page.goto(`/#/${route}`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(250);
}

/** Choose the first option whose text contains `text`. */
async function pick(select: ReturnType<Page["locator"]>, text: string) {
  const value = await select.locator("option", { hasText: text }).first().getAttribute("value");
  await select.selectOption(value!);
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

test("goals: demo tree with progress, add a quarter goal, add a task, link a career expectation", async ({ page }) => {
  await open(page, "goals");
  const senior = page.getByRole("article", { name: "Goal: Grow into a senior engineer" });
  await expect(senior).toBeVisible();
  await expect(page.getByRole("article", { name: "Goal: Share what we learn outside the team" })).toContainText("3 of 4 talks");

  await page.getByRole("button", { name: "Add goal" }).click();
  const dialog = page.getByRole("dialog", { name: "New goal" });
  await dialog.getByPlaceholder(/Lead the retrieval launch/).fill("E2E: write two design docs");
  await pick(dialog.getByLabel("Parent goal"), "Grow into a senior engineer");
  await dialog.getByRole("button", { name: "Add goal" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Goal added" })).toBeVisible();

  const goal = page.getByRole("article", { name: "Goal: E2E: write two design docs" });
  await goal.locator(".goal-name").click(); // expand
  await goal.getByPlaceholder(/Add a task that moves this goal/).fill("Draft design doc one ~1h30");
  await goal.getByPlaceholder(/Add a task that moves this goal/).press("Enter");
  await expect(goal.locator(".task-card", { hasText: "Draft design doc one" })).toBeVisible();
  await expect(goal.locator(".goal-basis")).toContainText("0 of 1 tasks done");

  await pick(goal.getByLabel(/Support a level expectation/), "L5 · Leads projects across a team");
  await expect(goal.locator(".goal-links")).toContainText("L5");

  // the Career view shows the goal under that expectation
  await open(page, "career");
  await expect(page.locator(".expectation", { hasText: "Leads projects across a team." }).locator(".exp-goals")).toContainText("E2E: write two design docs");

  // achieve it
  await open(page, "goals");
  await page.getByRole("article", { name: "Goal: E2E: write two design docs" }).getByRole("button", { name: "Achieved" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Goal achieved" })).toBeVisible();
});

test("skills: demo matrix, rate with the dots, add a skill, link evidence, make a gap a goal", async ({ page }) => {
  await open(page, "skills");
  const design = page.locator(".skill-line", { hasText: "System design" });
  await expect(design.locator(".level-label")).toHaveText("Practitioner");
  await expect(design.locator(".chip.trend")).toContainText("+1");

  // rate by clicking the 4th dot
  await design.getByRole("button", { name: "4 Advanced" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "System design: Advanced (4)" })).toBeVisible();
  await expect(design.locator(".level-label")).toHaveText("Advanced");

  // add a skill
  await page.getByRole("button", { name: "Add skill" }).click();
  await page.getByLabel("Skill name").fill("E2E Retrieval evaluation");
  await page.getByLabel("Category", { exact: true }).fill("Engineering");
  await page.getByLabel("Current level").selectOption("2");
  await page.getByLabel("Target level").selectOption("4");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const row = page.locator(".skill-line", { hasText: "E2E Retrieval evaluation" });
  await expect(row.locator(".level-label")).toHaveText("Working");

  // link evidence (suggested by shared words)
  await row.getByRole("button", { name: "Evidence for E2E Retrieval evaluation" }).click();
  const dialog = page.getByRole("dialog", { name: "Link skill evidence" });
  await dialog.getByRole("button", { name: /Link: Led the hybrid retrieval benchmark/ }).first().click();
  await expect(row.getByRole("button", { name: "Evidence for E2E Retrieval evaluation" })).toContainText("1");

  // gap → goal
  await row.getByRole("button", { name: "Make it a goal" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Goal added for this quarter" })).toBeVisible();
  await expect(row.getByRole("button", { name: "growth goal" })).toBeVisible();
  await open(page, "goals");
  await expect(page.getByRole("article", { name: /Goal: Grow E2E Retrieval evaluation: Working \(2\) → Advanced \(4\)/ })).toBeVisible();
});

test("career: add evidence in your own words; week view adds a meeting on a day", async ({ page }) => {
  await open(page, "career");
  const exp = page.locator(".expectation", { hasText: "Writes tests and reviews code within the team." });
  await exp.getByRole("button", { name: /Link evidence/ }).click();
  const dialog = page.getByRole("dialog", { name: "Link evidence" });
  await dialog.getByRole("button", { name: "Add evidence in your own words" }).click();
  await dialog.getByLabel("Evidence statement").fill("Reviewed 40 pull requests for the retrieval team this quarter");
  await dialog.getByRole("button", { name: "Add & link" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Evidence added and linked" })).toBeVisible();
  await expect(exp.locator(".evidence")).toContainText("Your note");
  await expect(exp.locator(".evidence")).toContainText("Reviewed 40 pull requests");

  await open(page, "week");
  await page.getByRole("button", { name: /Add meeting on/ }).first().click();
  const m = page.getByRole("dialog", { name: "New meeting" });
  await m.getByPlaceholder(/Team stand-up/).fill("E2E week meeting");
  await m.getByLabel("Duration").fill("40");
  await m.getByRole("button", { name: "Add meeting" }).click();
  await expect(page.locator(".wd-meeting", { hasText: "E2E week meeting" })).toBeVisible();
});
