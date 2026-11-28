import { expect, test } from "@playwright/test";
import { zip } from "./docx";

test("notes: import an Obsidian vault and export all notes as Markdown", async ({ page }) => {
  await page.goto("/#/notes");
  const vault = zip({
    "Vault/Vault import hub.md": "---\ntags: [imported]\n---\nLinks to [[Vault import leaf]].",
    "Vault/Ideas/Vault import leaf.md": "A small idea.",
    "Vault/.obsidian/app.md": "ignored",
  });
  await page.getByLabel("Import Markdown notes").setInputFiles({ name: "vault.zip", mimeType: "application/zip", buffer: vault });
  await expect(page.locator("[data-sonner-toast]", { hasText: "Imported 2 notes" })).toBeVisible();
  await page.locator(".note-item", { hasText: "Vault import leaf" }).click();
  await expect(page.getByRole("region", { name: "Linked notes" })).toContainText("Vault import hub");

  await page.getByRole("button", { name: "Markdown vault" }).click();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("menuitem", { name: /Export all notes/ }).click()]);
  expect(download.suggestedFilename()).toBe("personal-os-notes.zip");
});
