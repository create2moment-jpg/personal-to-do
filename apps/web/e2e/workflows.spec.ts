import { expect, test } from "@playwright/test";

test("workflows: plan my week proposes a checklist, apply only what you keep", async ({ page, request }) => {
  // Plan next week so the result does not depend on how full this week already is.
  const d = new Date();
  d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7));
  const nextMonday = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  await request.post("/api/tasks", { data: { title: "Workflow e2e: overdue item", scheduled_date: "2026-01-05", estimate_minutes: 5 } });
  const proposal = await (await request.post("/api/workflows/plan_week/run", { data: { day: nextMonday } })).json();
  expect(proposal.actions.length).toBeGreaterThan(1);

  await page.goto("/#/workflows");
  await page.getByRole("region", { name: "Recent runs" }).getByRole("button", { name: new RegExp(proposal.title) }).first().click();
  const run = page.getByRole("region", { name: `Proposal: ${proposal.title}` });
  await expect(run).toContainText("Workflow e2e: overdue item");
  await run.getByRole("checkbox").first().uncheck(); // keep all but the first
  await run.getByRole("button", { name: /^Apply/ }).click();
  await expect(run.locator(".chip", { hasText: "applied" })).toBeVisible();
  await expect(run.locator("li.out-skipped")).toHaveCount(1);
  const latest = await (await request.get(`/api/workflows/runs/${proposal.id}`)).json();
  expect(latest.status).toBe("applied");

  // the Run button works from the page too
  await page.getByRole("article", { name: "Plan my week" }).getByRole("button", { name: "Run" }).click();
  await expect(page.getByRole("region", { name: /^Proposal: Plan for the week/ })).toBeVisible();
});

test("workflows: evidence pack ends with a grounded note", async ({ page }) => {
  await page.goto("/#/workflows");
  await page.getByRole("article", { name: "Build a promotion evidence pack" }).getByRole("button", { name: "Run" }).click();
  const run = page.getByRole("region", { name: /^Proposal: Promotion evidence pack/ });
  await expect(run).toContainText("Write the");
  await expect(run).toContainText("not an assessment");
  await run.getByRole("button", { name: "Dismiss" }).click();
  await expect(run.locator(".chip", { hasText: "dismissed" })).toBeVisible();
});
