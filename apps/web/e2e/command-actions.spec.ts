import { expect, test } from "@playwright/test";

test("⌘K does things: done, move, timebox, new note", async ({ page, request }) => {
  const t = await (await request.post("/api/tasks", { data: { title: "Zebra command task", estimate_minutes: 30 } })).json();
  await page.goto("/#/today");
  await expect(page.getByLabel("Daily objective")).toBeVisible(); // app ready before shortcuts
  const menu = async (text: string) => {
    await expect(page.getByRole("dialog", { name: "Command menu" })).toHaveCount(0); // previous one fully closed
    await page.keyboard.press("Control+k");
    await expect(page.getByRole("dialog", { name: "Command menu" })).toBeVisible();
    await page.keyboard.type(text);
    const item = page.locator(".cmd-do");
    await expect(item).toBeVisible();
    return item;
  };

  await (await menu("move zebra command to tomorrow")).click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Moved “Zebra command task”" })).toBeVisible();
  const got = await (await request.get(`/api/tasks/${t.id}`)).json();
  expect(got.scheduled_date).not.toBeNull();

  await (await menu("timebox zebra command 15:30 tomorrow")).click();
  await expect.poll(async () => (await (await request.get(`/api/tasks/${t.id}`)).json()).timebox_start).toBe("15:30");

  await (await menu("done zebra command")).click();
  await expect.poll(async () => (await (await request.get(`/api/tasks/${t.id}`)).json()).status).toBe("done");

  const note = await menu("note Zebra meeting notes");
  await expect(note).toContainText("New note “Zebra meeting notes”");
  await note.click();
  await expect(page.locator(".doc-title")).toHaveValue("Zebra meeting notes");
});
