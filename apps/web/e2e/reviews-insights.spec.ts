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

test("insights: weekly trends with tooltips, range switch and a table view", async ({ page }) => {
  await open(page, "analytics");
  await expect(page.locator(".stat", { hasText: "Tasks per week" })).toBeVisible();
  const chart = page.getByRole("img", { name: "Tasks completed per week" });
  await expect(chart).toBeVisible();
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await expect(page.locator(".chart-tip").first()).toContainText("Week of");
  await expect(page.getByRole("img", { name: "Estimate accuracy per week" })).toBeVisible();
  await page.getByRole("button", { name: "26 weeks" }).click();
  await page.getByText("All numbers as a table").click();
  await expect(page.locator(".insights-table tbody tr")).toHaveCount(26);
});

test("assistant: grounded answer with sources, search by meaning, plan my day with approval", async ({ page }) => {
  await open(page, "ai");
  await expect(page.locator(".assistant-status")).toContainText("Search by meaning");
  await page.getByLabel("Ask the assistant").fill("What did I decide about hybrid retrieval?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /Answer: What did I decide/ });
  await expect(answer).toBeVisible({ timeout: 15_000 });
  await expect(answer.locator(".grounding")).toContainText("Cites 1 of");
  await expect(answer.locator(".source").first()).toBeVisible();
  // open the cited source
  await answer.locator(".answer-text .cite").first().click();
  // a note/document/prompt opens its page; a task opens the task panel
  await expect
    .poll(async () => (page.url().endsWith("#/ai") ? await page.getByRole("dialog").count() : 1))
    .toBeGreaterThan(0);
  await page.keyboard.press("Escape");

  await open(page, "ai");
  const plan = page.getByRole("complementary", { name: "Plan my day" });
  await plan.getByRole("button", { name: "Propose a plan" }).click();
  await expect(plan.locator("ol li")).toHaveCount(2);
  await expect(plan).toContainText("1 suggestion(s) ignored");
  await plan.getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "top priorities set" })).toBeVisible();
});

test("weekly review: grounded AI draft fills Wins only when you press Use", async ({ page }) => {
  await open(page, "week/review");
  await page.getByRole("button", { name: "Draft with AI" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Draft ready" })).toBeVisible({ timeout: 15_000 });
  const wins = page.locator(".ai-suggestions", { hasText: "Wins · suggested" });
  await expect(wins).toBeVisible();
  await expect(page.locator(".grounded-suggestions")).not.toContainText("300 percent impact [S1]Use");
  const winsBox = page.getByPlaceholder("What moved the needle?");
  await expect(winsBox).toHaveValue("");
  await wins.getByRole("button", { name: "Use" }).first().click();
  await expect(winsBox).toHaveValue(/^- .+\[[A-Z]\d+\]/);
});
