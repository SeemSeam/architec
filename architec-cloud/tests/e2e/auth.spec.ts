import { expect, test } from "@playwright/test";

test("registers a new account, logs out, and logs back in", async ({ page }) => {
  const email = `playwright.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("button", { name: "Create account" }).click()
  ]);

  await expect(page.getByRole("heading", { name: email })).toBeVisible();
  await expect(page.locator(".status-pill", { hasText: "License: active" })).toBeVisible();

  await Promise.all([
    page.waitForURL("http://127.0.0.1:3100/"),
    page.getByRole("button", { name: "Log out" }).click()
  ]);

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("button", { name: "Continue to account" }).click()
  ]);

  await expect(page.getByRole("heading", { name: email })).toBeVisible();
  await expect(page.locator(".status-pill", { hasText: "Plan: Standard" })).toBeVisible();

  await page.goto("/account/downloads");
  await expect(
    page.getByRole("heading", { name: "GitHub distributes the build. This account authorizes the install." })
  ).toBeVisible();
  await expect(page.getByText("Downloads remain public on GitHub Releases")).toBeVisible();
  await expect(page.getByRole("link", { name: "Download Linux Build" })).toHaveAttribute(
    "href",
    "https://github.com/bfly123/architec-releases/releases/latest/download/archi-linux-x86_64.tar.gz"
  );
  await expect(page.getByRole("link", { name: "Install Script", exact: true })).toHaveAttribute(
    "href",
    "https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh"
  );
});
