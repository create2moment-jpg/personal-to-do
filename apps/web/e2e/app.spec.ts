import { expect, type Page, test } from "@playwright/test";

// Each test reseeds nothing: they run serially against one demo workspace
// and are written so that order does not matter for their assertions.

/** Navigate and wait until data has loaded and the app is idle. */
async function open(page: Page, route: string) {
  await page.goto(`/#/${route}`);
  await page.waitForLoadState("networkidle");
  await page.locator(".main").first().waitFor();
  await page.waitForTimeout(250); // let entrance animations settle
}

const column = (page: Page, name: string) => page.locator(`section.column[aria-label="${name}"]`);

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  (page as unknown as { errors: string[] }).errors = errors;
});

test.afterEach(async ({ page }) => {
  expect((page as unknown as { errors: string[] }).errors).toEqual([]);
});

test("Today renders the demo workspace", async ({ page }) => {
  await open(page, "today");
  await expect(page.locator(".hero-title")).toBeVisible();
  await expect(page.locator(".objective-input")).toHaveValue(/retrieval ADR/);
  await expect(page.getByText("Demo data — nothing here is real")).toBeVisible();
  await expect(column(page, "In progress").locator(".task-card")).not.toHaveCount(0);
});

test("drag a backlog task onto the board with the mouse", async ({ page }) => {
  await open(page, "today");
  const card = page.locator(".tray-panel .task-card", { hasText: "Refactor ingestion pipeline" });
  const target = column(page, "Planned");
  await card.scrollIntoViewIfNeeded();
  const from = (await card.boundingBox())!;
  const to = (await target.boundingBox())!;
  await page.mouse.move(from.x + 30, from.y + 12);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(from.x + 30 + ((to.x + 40 - from.x - 30) * i) / 10, from.y + 12 + ((to.y + 60 - from.y - 12) * i) / 10);
  }
  await page.mouse.up();
  await expect(target.getByText("Refactor ingestion pipeline")).toBeVisible();
});

test("move a task between columns with the keyboard", async ({ page }) => {
  await open(page, "today");
  const card = column(page, "Planned").locator(".task-card").first();
  const title = (await card.locator(".t-title").innerText()).trim();
  await card.focus();
  await page.keyboard.press("Space");
  await expect(page.locator(".task-card.overlay")).toBeVisible(); // drag started and columns measured
  await page.waitForTimeout(150);
  await page.keyboard.press("ArrowRight");
  await expect(column(page, "In progress")).toHaveClass(/drop-active/); // wait for the keyboard move to land
  await page.keyboard.press("Space");
  await expect(column(page, "In progress").getByText(title)).toBeVisible();
});

test("complete with undo", async ({ page }) => {
  await open(page, "today");
  const card = column(page, "In progress").locator(".task-card").first();
  const title = (await card.locator(".t-title").innerText()).trim();
  await card.locator(".check").click();
  await expect(column(page, "Done").getByText(title)).toBeVisible();
  await page.locator("[data-sonner-toast] button", { hasText: "Undo" }).click();
  await expect(column(page, "Done").getByText(title)).toHaveCount(0);
});

test("quick capture shows a live preview and saves", async ({ page }) => {
  await open(page, "backlog");
  await page.keyboard.press("c");
  const input = page.locator(".capture-input");
  await input.fill("Prepare launch demo #demo !1 ~45m +model-evaluation");
  await expect(page.locator(".capture-preview")).toContainText("P1");
  await expect(page.locator(".capture-preview")).toContainText("45m");
  await expect(page.locator(".capture-preview")).toContainText("Model Evaluation");
  await input.press("Enter");
  await expect(page.locator(".list").getByText("Prepare launch demo")).toBeVisible();
});

test("command menu searches tasks and notes", async ({ page }) => {
  await open(page, "today");
  await page.keyboard.press("Control+k");
  await page.keyboard.type("hybrid");
  await expect(page.locator("[cmdk-item]", { hasText: "Hybrid retrieval — design notes" })).toBeVisible();
  await page.keyboard.press("Escape");
});

test("notes autosave as markdown", async ({ page, request }) => {
  await open(page, "notes");
  await page.locator(".notes-sidebar .btn.primary").click();
  await page.locator(".doc-title").fill("E2E note");
  await page.locator(".ProseMirror").click();
  await page.keyboard.type("## Heading\nSome **bold** text");
  await expect(page.locator(".save-indicator")).toContainText("Saved", { timeout: 5000 });
  const id = (await page.evaluate(() => location.hash)).split("/")[2]!;
  const note = await (await request.get(`/api/notes/${id}`)).json();
  expect(note.title).toBe("E2E note");
  expect(note.body).toContain("## Heading");
  expect(note.body).toContain("**bold**");
});

test("theme and accent switch from settings", async ({ page }) => {
  await open(page, "settings");
  await page.getByRole("button", { name: "Dark", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Teal" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent", "teal");
  await page.getByRole("button", { name: "Midnight dark palette" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-dark", "midnight");
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe("rgb(11, 16, 32)");
});

test("installable app: manifest, service worker, and no API data in the cache", async ({ page }) => {
  await open(page, "today");
  const manifest = await page.evaluate(async () => (await fetch("/manifest.webmanifest")).json());
  expect(manifest.display).toBe("standalone");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await page.waitForLoadState("networkidle");
  expect(await page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  const cached = await page.evaluate(async () => {
    const out: string[] = [];
    for (const name of await caches.keys()) for (const req of await (await caches.open(name)).keys()) out.push(new URL(req.url).pathname);
    return out;
  });
  expect(cached).toContain("/");
  expect(cached.some((p) => p.startsWith("/api/"))).toBe(false);
});

test("notes writing assistant: improve the whole note, review the diff, accept", async ({ page }) => {
  await open(page, "notes");
  await page.locator(".notes-sidebar .btn.primary").click();
  await page.getByPlaceholder("Untitled").fill("E2E assist note");
  const body = page.locator(".ProseMirror");
  await body.click();
  await page.keyboard.type("we basically shipped the benchmark today");
  await page.getByRole("button", { name: "Improve" }).click();
  await page.getByRole("menuitem", { name: "Clearer" }).click();
  const dialog = page.getByRole("dialog", { name: "Review the rewrite" });
  await expect(dialog).toContainText("We shipped the benchmark today");
  await dialog.getByRole("button", { name: "Accept" }).click();
  await expect(body).toContainText("We shipped the benchmark today");
  await expect(body).not.toContainText("basically");
});

test("AI capture: plain language becomes a capture line you confirm (and can undo)", async ({ page, request }) => {
  await open(page, "today");
  await page.keyboard.press("c");
  const input = page.getByLabel("Capture text");
  await input.fill("remind me to send the deck to Priya tomorrow, takes half an hour");
  await page.getByRole("button", { name: "Understand" }).click();
  await expect(input).toHaveValue("Send the deck to Priya @tomorrow ~30m");
  await expect(page.locator(".capture-preview")).toContainText("30m");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(input).toHaveValue(/^remind me to send the deck/);
  await page.keyboard.press("Control+i");
  await expect(input).toHaveValue("Send the deck to Priya @tomorrow ~30m");
  await input.press("Enter");
  await expect
    .poll(async () => ((await (await request.get("/api/tasks?limit=1000")).json()) as { title: string; estimate_minutes: number }[]).some((t) => t.title === "Send the deck to Priya" && t.estimate_minutes === 30))
    .toBe(true);
});
