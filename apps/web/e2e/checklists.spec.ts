import { expect, test } from "@playwright/test";

test("checklists: starters, apply for today, edit, and ⌘K checklist", async ({ page, request }) => {
  await page.goto("/#/board");
  await page.getByRole("button", { name: "Checklists" }).click();
  const dlg = page.getByRole("dialog", { name: "Checklists" });
  const starters = dlg.getByRole("button", { name: /Add starters/ });
  if (await starters.isVisible()) await starters.click();
  const row = dlg.locator("li", { hasText: "Release checklist" });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Today" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: /Release checklist — .* added with 6 steps/ })).toBeVisible();
  const parents = (await (await request.get("/api/tasks?tag=checklist")).json()) as { id: string; title: string }[];
  const parent = parents.find((t) => t.title.startsWith("Release checklist"))!;
  const subs = await (await request.get(`/api/tasks?parent_id=${parent.id}`)).json();
  expect(subs.length).toBe(6);

  await page.getByRole("button", { name: "Checklists" }).click();
  await dlg.getByRole("button", { name: "New", exact: true }).click();
  await dlg.getByLabel("Checklist name").fill("Zest trip");
  await dlg.getByLabel("Steps, one per line").fill("Book flights ~20m\nPack ~30m");
  await dlg.getByRole("button", { name: "Save" }).click();
  await expect(dlg.locator("li", { hasText: "Zest trip" })).toContainText("2 steps");
  await page.keyboard.press("Escape");

  await expect(page.getByRole("dialog", { name: "Checklists" })).toHaveCount(0);
  await page.keyboard.press("Control+k");
  await page.keyboard.type("checklist zest");
  await page.locator(".cmd-do").click();
  await expect(page.locator("[data-sonner-toast]", { hasText: /Zest trip — .* added/ })).toBeVisible();
});
