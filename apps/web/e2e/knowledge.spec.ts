import { expect, type Page, test } from "@playwright/test";
import { docx, PAGE_BREAK, para } from "./docx";

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
  // A rejected upload legitimately logs its 422 response; anything else is a bug.
  const errors = (page as unknown as { errors: string[] }).errors.filter((e) => !e.includes("status of 422"));
  expect(errors).toEqual([]);
});

test("upload a document, it gets processed and is searchable with page citations", async ({ page }) => {
  await open(page, "knowledge");
  const text = "Onboarding guide\n\nSet up the dev environment.\f2. Deployment\n\nShip with blue-green deployments and canary checks.\n";
  await page.locator('input[type="file"]').setInputFiles({ name: "onboarding.txt", mimeType: "text/plain", buffer: Buffer.from(text) });
  await expect(page.locator("[data-sonner-toast]", { hasText: "Added" })).toBeVisible();
  await expect(page.locator(".editor-top .chip", { hasText: "Ready" })).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".doc-page-label", { hasText: "Page 2" })).toBeVisible();
  await page.getByLabel("Search documents").fill("canary");
  const hit = page.locator(".note-item", { hasText: "onboarding" });
  await expect(hit).toContainText("p. 2");
  await hit.click();
  await expect(page.locator(".doc-chunk.hit")).toContainText("canary");
});

test("a Word document is imported with its headings and pages", async ({ page }) => {
  await open(page, "knowledge");
  const body = para("Release checklist", "Heading1") + para("Freeze the branch on Monday.") + PAGE_BREAK + para("Rollout", "Heading2") + para("Roll out behind a feature flag to 5 percent first.");
  await page.locator('input[type="file"]').setInputFiles({ name: "release-checklist.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: docx(body) });
  await expect(page.locator(".editor-top .chip", { hasText: "Ready" })).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".doc-page-label", { hasText: "Page 2" })).toBeVisible();
  await page.getByLabel("Search documents").fill("feature flag");
  const hit = page.locator(".note-item", { hasText: "Release checklist" });
  await expect(hit).toContainText("p. 2", { timeout: 10_000 }); // search is debounced; slow under load
});

test("duplicates are detected and unsupported files rejected", async ({ page }) => {
  await open(page, "knowledge");
  const input = page.locator('input[type="file"]');
  await input.setInputFiles({ name: "same.md", mimeType: "text/markdown", buffer: Buffer.from("# Engineering Level Framework (synthetic example)\n") });
  await expect(page.locator("[data-sonner-toast]").first()).toBeVisible();
  await input.setInputFiles({ name: "tool.exe", mimeType: "application/octet-stream", buffer: Buffer.from([0x4d, 0x5a, 0, 1, 2, 3, 0, 0]) });
  await expect(page.locator("[data-sonner-toast]", { hasText: "unsupported file type" })).toBeVisible();
});

test("command menu finds passages inside documents", async ({ page }) => {
  await open(page, "today");
  await page.keyboard.press("Control+k");
  await page.keyboard.type("reciprocal-rank fusion");
  const item = page.locator("[cmdk-item]", { hasText: "Hybrid retrieval design" }).first();
  await expect(item).toBeVisible();
  await item.click();
  await expect(page.locator(".doc-chunk.hit")).toContainText("Reciprocal-rank fusion");
});

test("extract facts with local AI: grounded only, accept, jump to source", async ({ page }) => {
  await open(page, "knowledge");
  await page.locator(".note-item", { hasText: "Mid-year review" }).click();
  await page.getByRole("button", { name: "Extract facts with AI" }).click();
  await expect(page.locator(".facts-run")).toContainText("dropped (no verbatim quote", { timeout: 15_000 });
  // the demo already holds accepted facts for this review; pick a fresh proposal
  const proposal = page.locator(".fact").filter({ has: page.getByRole("button", { name: "Accept fact" }) }).first();
  await expect(proposal).toBeVisible();
  const statement = (await proposal.locator(".fact-statement").textContent()) ?? "";
  const fact = page.locator(".fact", { hasText: statement }).first();
  await expect(page.locator(".facts-panel")).not.toContainText("Won a company award"); // ungrounded fake fact dropped
  await fact.getByRole("button", { name: "Accept fact" }).click();
  await expect(fact.locator(".chip", { hasText: "Accepted" })).toBeVisible();
  await fact.locator(".fact-quote").click();
  await expect(page.locator(".doc-chunk.hit")).toBeVisible();
});
