import { expect, test } from "@playwright/test";

const iso = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

test("timeline: place a task in a free slot, remove it, fill free time and apply", async ({ page, request }) => {
  const before = await (await request.get("/api/settings")).json();
  // every day is a working day for this test
  await request.patch("/api/settings", { data: { workdays: [0, 1, 2, 3, 4, 5, 6], work_start: "00:00", work_end: "23:59" } });
  // tomorrow: the whole day is ahead, so the result does not depend on when the suite runs
  const tomorrow = iso(new Date(Date.now() + 86_400_000));
  try {
    const task = await (await request.post("/api/tasks", { data: { title: "Timebox me", scheduled_date: tomorrow, estimate_minutes: 15 } })).json();
    await page.goto("/#/today");
    await page.getByRole("button", { name: "Next day" }).click();
    const tl = page.getByRole("region", { name: "Day timeline" });
    await expect(tl).toContainText("free");
    await tl.locator(".tl-free").first().click();
    await page.getByRole("menuitem", { name: /Timebox me/ }).click();
    const box = tl.locator(".tl-block.task", { hasText: "Timebox me" });
    await expect(box).toBeVisible();
    const boxed = await (await request.get(`/api/tasks/${task.id}`)).json();
    expect(boxed.timebox_start).toMatch(/^\d\d:\d\d$/);
    await expect(page.locator(".task-card .t-time", { hasText: boxed.timebox_start }).first()).toBeVisible();

    await box.hover(); // the remove button shows on hover or keyboard focus
    await tl.getByRole("button", { name: "Remove the time from Timebox me" }).click();
    await expect(box).toHaveCount(0);
    await expect(tl.locator(".tl-chip", { hasText: "Timebox me" })).toBeVisible();

    await tl.getByRole("button", { name: "Fill my free time" }).click();
    await expect(tl.locator(".tl-block.proposed", { hasText: "Timebox me" })).toBeVisible();
    await tl.getByRole("button", { name: /^Apply/ }).click();
    await expect(box).toBeVisible();
    await expect(tl.locator(".tl-block.proposed")).toHaveCount(0);
  } finally {
    await request.patch("/api/settings", { data: { workdays: before.workdays, work_start: before.work_start, work_end: before.work_end } });
  }
});
