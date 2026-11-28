import { expect, test } from "@playwright/test";

test("people: a page per person with time together, follow-ups, notes and 1:1 prep", async ({ page, request }) => {
  const now = Date.now();
  await request.post("/api/meetings", { data: { title: "Quill review", start_at: new Date(now - 2 * 86_400_000).toISOString(), minutes: 40, people: ["Quill Rivera"] } }).catch(() => undefined);
  const p = await (await request.post("/api/people-overview", { data: { name: "Quill Rivera", role: "Staff engineer" } })).json();
  await request.post("/api/tasks", { data: { title: "Send Quill Rivera the benchmark" } });
  await request.post("/api/notes", { data: { title: "Quill sync notes", body: "[[Quill Rivera]] wants the RRF numbers." } });

  await page.goto(`/#/people/${p.id}`);
  await expect(page.getByRole("heading", { name: "Quill Rivera" })).toBeVisible();
  await expect(page.getByLabel("Role")).toHaveValue("Staff engineer");
  await expect(page.locator(".person-card", { hasText: "Open follow-ups" })).toContainText("Send Quill Rivera the benchmark");
  await expect(page.locator(".person-card", { hasText: "Notes that mention" })).toContainText("Quill sync notes");

  await page.getByLabel("Talking points").fill("- Promotion packet");
  await page.getByRole("button", { name: "Prep 1:1" }).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "1:1 prep note created" })).toBeVisible();
  await page.locator("[data-sonner-toast]").getByRole("button", { name: "Open" }).click();
  await expect(page.locator(".doc-title")).toHaveValue(/^1:1 Quill Rivera/);
  await expect(page.locator(".ProseMirror")).toContainText("Promotion packet");

  await page.goto(`/#/people/${p.id}`);
  await page.getByRole("button", { name: "Log call" }).click();
  await expect(page.getByRole("dialog")).toContainText("Quill Rivera");
});
