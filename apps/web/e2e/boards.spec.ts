import { expect, test, type Page } from "@playwright/test";

const canvas = (page: Page) => page.getByRole("application", { name: "Board canvas" });

test("boards: stickies, arrow, shape, frame, undo, to-task, saved across reloads", async ({ page, request }) => {
  await page.setViewportSize({ width: 1500, height: 950 });
  await page.goto("/#/boards");
  await page.locator(".board-templates").getByRole("button", { name: "Blank board" }).click();
  await expect(page.getByLabel("Board title")).toHaveValue("Blank board");
  const stage = canvas(page);
  const box = (await stage.boundingBox())!;

  // double-click empty canvas → sticky, type, click away
  await page.mouse.dblclick(box.x + 400, box.y + 250);
  await page.keyboard.type("Ship the ADR");
  await page.mouse.click(box.x + 900, box.y + 700);
  await page.mouse.dblclick(box.x + 800, box.y + 250);
  await page.keyboard.type("Review with Priya");
  await page.mouse.click(box.x + 900, box.y + 700);
  const a = page.locator(".b-sticky", { hasText: "Ship the ADR" });
  const b = page.locator(".b-sticky", { hasText: "Review with Priya" });
  await expect(a).toBeVisible();
  await expect(b).toBeVisible();

  // arrow tool: drag from one sticky to the other
  await page.keyboard.press("l");
  const ab = (await a.boundingBox())!;
  const bb = (await b.boundingBox())!;
  await page.mouse.move(ab.x + ab.width / 2, ab.y + ab.height / 2);
  await page.mouse.down();
  await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator(".b-link")).toHaveCount(1);

  // shape and frame tools
  await page.keyboard.press("Escape");
  await page.keyboard.press("r");
  await page.mouse.click(box.x + 600, box.y + 550);
  await page.keyboard.type("Decision");
  await page.mouse.click(box.x + 1100, box.y + 800);
  await expect(page.locator(".b-shape", { hasText: "Decision" })).toBeVisible();
  await page.keyboard.press("f");
  await page.mouse.click(box.x + 1200, box.y + 300);
  await expect(page.locator(".b-frame")).toHaveCount(1);

  // undo removes the frame, redo brings it back
  await page.keyboard.press("Control+z");
  await expect(page.locator(".b-frame")).toHaveCount(0);
  await page.keyboard.press("Control+Shift+z");
  await expect(page.locator(".b-frame")).toHaveCount(1);

  // a sticky becomes a live task card
  await a.click();
  await page.getByRole("button", { name: "To task" }).click();
  await expect(page.locator(".b-card", { hasText: "Ship the ADR" })).toBeVisible();
  const tasks = await (await request.get("/api/tasks?tag=board")).json();
  expect(tasks.some((t: { title: string }) => t.title === "Ship the ADR")).toBe(true);

  // everything is saved
  await expect(page.locator(".board-save")).toHaveText("Saved");
  await page.reload();
  await expect(page.locator(".b-card", { hasText: "Ship the ADR" })).toBeVisible();
  await expect(page.locator(".b-sticky", { hasText: "Review with Priya" })).toBeVisible();
  await expect(page.locator(".b-link")).toHaveCount(1);
  await expect(page.locator(".b-shape", { hasText: "Decision" })).toBeVisible();

  // deleting a sticky removes its arrow too
  await page.locator(".b-sticky", { hasText: "Review with Priya" }).click();
  await page.keyboard.press("Delete");
  await expect(page.locator(".b-link")).toHaveCount(0);
});

test("boards: templates give a ready layout", async ({ page }) => {
  await page.goto("/#/boards");
  await page.locator(".board-templates").getByRole("button", { name: "Retrospective" }).click();
  await expect(page.locator(".b-frame")).toHaveCount(3);
  await expect(page.locator(".b-frame-title", { hasText: "To improve" })).toBeVisible();
});

const PNG = Buffer.from(
  "89504e470d0a1a0a0000000d4948445200000001000000010806000000" + "1f15c4890000000d49444154789c63f80f00000101000518d84e0000000049454e44ae426082",
  "hex",
);

test("boards: freehand pen, images, and board text in global search", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 950 });
  await page.goto("/#/boards");
  await page.locator(".board-templates").getByRole("button", { name: "Blank board" }).click();
  await page.getByLabel("Board title").fill("Quokka planning");
  await page.getByLabel("Board title").press("Enter");
  const box = (await page.getByRole("application", { name: "Board canvas" }).boundingBox())!;

  await page.keyboard.press("p");
  await page.mouse.move(box.x + 300, box.y + 300);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(box.x + 300 + i * 20, box.y + 300 + (i % 2) * 30);
  await page.mouse.up();
  await expect(page.locator(".b-drawing")).toHaveCount(1);

  await page.getByLabel("Add an image to the board").setInputFiles({ name: "dot.png", mimeType: "image/png", buffer: PNG });
  await expect(page.locator(".b-image img")).toHaveCount(1);

  await page.keyboard.press("Escape");
  await page.mouse.dblclick(box.x + 700, box.y + 600);
  await page.keyboard.type("Quokka migration risk");
  await page.mouse.click(box.x + 1000, box.y + 800);
  await expect(page.locator(".board-save")).toHaveText("Saved");
  await page.reload();
  await expect(page.locator(".b-drawing")).toHaveCount(1);
  await expect(page.locator(".b-image img")).toHaveCount(1);

  await page.keyboard.press("Control+k");
  await page.keyboard.type("quokka");
  await page.locator("[cmdk-item]", { hasText: "Quokka planning" }).first().click();
  await expect(page).toHaveURL(/#\/boards\//);
});
