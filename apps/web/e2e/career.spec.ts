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

test("career view: framework levels, coverage as hypothesis, confirm a suggestion, gap task", async ({ page }) => {
  await open(page, "career");
  await expect(page.locator(".career-note")).toContainText("not an assessment");
  const l5 = page.getByRole("region", { name: "Level L5" });
  await expect(l5.locator(".level-head")).toContainText("0 of 2 with evidence");
  await expect(page.getByRole("region", { name: "Level L6" }).locator(".level-head")).toContainText("1 of 2 with evidence");

  // Confirm an explainable suggestion
  const lead = l5.locator(".expectation", { hasText: "Leads projects across a team." });
  await lead.getByRole("button", { name: /Link evidence/ }).click();
  const dialog = page.getByRole("dialog", { name: "Link evidence" });
  await expect(dialog.locator(".why")).toContainText("leads");
  await dialog.getByRole("button", { name: "Link: Led the hybrid retrieval benchmark adopted by two teams." }).first().click();
  await expect(l5.locator(".level-head")).toContainText("1 of 2 with evidence");
  await expect(lead.locator(".evidence")).toContainText("Mid-year review");

  // The quote opens the source passage
  await lead.locator(".evidence .fact-quote").click();
  await expect(page).toHaveURL(/#\/knowledge\//);
  await expect(page.locator(".doc-chunk.hit")).toContainText("Led the hybrid retrieval benchmark");

  // A gap becomes a task
  await open(page, "career");
  const gap = page.locator(".expectation.gap", { hasText: "Breaks down ambiguous problems" });
  await gap.getByRole("button", { name: "Create a task to build evidence" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Task added" })).toBeVisible();

  // Undo the link so the demo workspace stays as seeded
  await page.locator(".expectation", { hasText: "Leads projects across a team." }).getByRole("button", { name: "Unlink evidence" }).click();
  await expect(page.getByRole("region", { name: "Level L5" }).locator(".level-head")).toContainText("0 of 2 with evidence");
});

test("career: add an expectation by hand and remove it", async ({ page }) => {
  await open(page, "career");
  await page.getByRole("button", { name: "Add expectation" }).click();
  await page.getByLabel("Level", { exact: true }).fill("L7");
  await page.getByLabel("Expectation text").fill("Shapes the engineering strategy of the organisation");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const row = page.getByRole("region", { name: "Level L7" }).locator(".expectation");
  await expect(row).toContainText("Yours");
  page.once("dialog", (d) => void d.accept());
  await row.getByRole("button", { name: "Remove expectation" }).click();
  await expect(page.getByRole("region", { name: "Level L7" })).toHaveCount(0);
});
