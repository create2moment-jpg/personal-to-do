import { expect, test } from "@playwright/test";

test("linked notes: [[autocomplete]], click to open, backlinks, rename updates links, graph", async ({ page, request }) => {
  const target = await (await request.post("/api/notes", { data: { title: "Zeta retrieval design", body: "# Decision\nUse RRF.\n" } })).json();
  const source = await (await request.post("/api/notes", { data: { title: "Zeta standup", body: "" } })).json();
  await request.post("/api/notes", { data: { title: "Zeta retro", body: "Zeta retrieval design was late." } });

  await page.goto(`/#/notes/${source.id}`);
  await page.locator(".ProseMirror").click();
  await page.keyboard.type("We agreed on [[Zeta retr");
  const suggest = page.getByRole("listbox", { name: "Link to a note" });
  await expect(suggest.getByRole("option", { name: "Zeta retro", exact: true })).toBeVisible(); // both match
  await suggest.getByRole("option", { name: "Zeta retrieval design" }).click();
  await page.keyboard.type(" today.");
  const link = page.locator(".ProseMirror .wikilink", { hasText: "Zeta retrieval design" });
  await expect(link).toBeVisible();
  await expect.poll(async () => (await (await request.get(`/api/notes/${source.id}`)).json()).body as string).toContain("Zeta retrieval design");

  await link.click(); // opens the linked note
  await expect(page).toHaveURL(new RegExp(`#/notes/${target.id}`));
  const conn = page.getByRole("region", { name: "Linked notes" });
  await expect(conn.getByRole("tab", { name: /Backlinks/ })).toContainText("1");
  await expect(conn).toContainText("Zeta standup");
  await conn.getByRole("tab", { name: /Unlinked mentions/ }).click();
  await conn.getByRole("button", { name: "Link" }).click();
  await expect(conn.getByRole("tab", { name: /Backlinks/ })).toContainText("2");

  // rename: links elsewhere follow
  await page.locator(".doc-title").fill("Zeta search design");
  await expect(page.locator("[data-sonner-toast]", { hasText: "Updated links in 2 notes" })).toBeVisible({ timeout: 8000 });
  await expect.poll(async () => (await (await request.get(`/api/notes/${source.id}`)).json()).body as string).toContain("Zeta search design");

  await page.getByRole("button", { name: "Graph" }).click();
  await expect(page.getByRole("img", { name: /Graph of \d+ notes and \d+ links/ })).toBeVisible();
  await expect(page.locator(".g-node", { hasText: "Zeta search design" })).toBeVisible();
});

test("an unresolved [[link]] creates the note when clicked", async ({ page, request }) => {
  const n = await (await request.post("/api/notes", { data: { title: "Zeta ideas", body: "Next: [[Zeta brand new idea]]" } })).json();
  await page.goto(`/#/notes/${n.id}`);
  const ghost = page.locator(".ProseMirror .wikilink.ghost", { hasText: "Zeta brand new idea" });
  await expect(ghost).toBeVisible();
  await ghost.click();
  await expect(page.locator("[data-sonner-toast]", { hasText: "Created “Zeta brand new idea”" })).toBeVisible();
  await expect(page.locator(".doc-title")).toHaveValue("Zeta brand new idea");
});
