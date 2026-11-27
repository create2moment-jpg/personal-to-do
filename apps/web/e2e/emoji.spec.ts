import { expect, test } from "@playwright/test";

test("projects and weekly objectives take an optional emoji", async ({ page, request }) => {
  await page.goto("/#/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("button", { name: "Add project emoji" }).click();
  await page.getByRole("button", { name: "🧪", exact: true }).click();
  await page.getByPlaceholder("Project name").fill("Eval lab");
  await page.getByRole("button", { name: "Create" }).click();
  const card = page.locator(".project-card", { hasText: "Eval lab" });
  await expect(card.locator(".project-icon")).toHaveText("🧪");

  await card.click();
  await page.getByRole("button", { name: "Project emoji: 🧪 — change" }).click();
  await page.getByRole("button", { name: "None" }).click();
  await expect(card.locator(".project-icon")).toHaveText("E");

  await page.goto("/#/week");
  await page.getByRole("button", { name: "Add objective 3 emoji" }).click();
  await page.getByLabel("Type or paste any emoji").fill("🦄");
  await page.keyboard.press("Enter");
  await page.getByLabel("Objective 3", { exact: true }).fill("Ship the unicorn");
  await page.getByLabel("Objective 3", { exact: true }).blur();
  await expect(page.getByRole("button", { name: "Objective 3 emoji: 🦄 — change" })).toBeVisible();
  await expect
    .poll(async () => {
      const today = new Date().toISOString().slice(0, 10);
      const w = await (await request.get(`/api/weeks/${today}`)).json();
      return w.plan.objectives.find((o: { text: string }) => o.text === "Ship the unicorn")?.emoji;
    })
    .toBe("🦄");
});
