import fs from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

const dbPath = path.resolve(process.cwd(), ".data-e2e/dev-db.json");

async function readDb() {
  return JSON.parse(await fs.readFile(dbPath, "utf8")) as {
    users: Array<{
      id: string;
      email: string;
      isAdmin: boolean;
      seatLimit: number;
      licenseActive: boolean;
    }>;
  };
}

async function promoteUserToAdmin(email: string) {
  const db = await readDb();
  const user = db.users.find((item) => item.email === email);
  if (!user) {
    throw new Error(`Cannot find user ${email} in ${dbPath}`);
  }
  user.isAdmin = true;
  await fs.writeFile(dbPath, JSON.stringify(db, null, 2), "utf8");
}

async function registerAndLogin(page: Parameters<typeof test>[0]["page"], email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("button", { name: "Create account" }).click()
  ]);
}

async function logout(page: Parameters<typeof test>[0]["page"]) {
  await Promise.all([
    page.waitForURL(/\/$/),
    page.getByRole("button", { name: "Log out" }).click()
  ]);
}

async function login(page: Parameters<typeof test>[0]["page"], email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("button", { name: "Continue to account" }).click()
  ]);
}

async function authorizeInstallViaBrowser(
  page: Parameters<typeof test>[0]["page"],
  request: Parameters<typeof test>[0]["request"],
  baseURL: string,
  installId: string,
  deviceName: string
) {
  const state = `state-${installId}`;
  const redirectUri = "http://127.0.0.1:46319/callback?source=playwright-admin";

  await page.goto(
    `/cli/login?state=${encodeURIComponent(state)}&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}&redirect_uri=${encodeURIComponent(redirectUri)}`
  );
  await Promise.all([
    page.waitForURL(/\/cli\/complete\?/),
    page.getByRole("button", { name: "Authorize this install" }).click()
  ]);

  const continueHref = await page.getByRole("link", { name: "Continue now" }).getAttribute("href");
  const callbackUrl = new URL(String(continueHref));
  const code = callbackUrl.searchParams.get("code");
  expect(code).toBeTruthy();

  const exchange = await request.post(`${baseURL}/api/cli/login/exchange`, {
    data: {
      code,
      install_id: installId
    }
  });
  expect(exchange.ok()).toBeTruthy();
  const exchangeJson = await exchange.json();
  return {
    refreshToken: String(exchangeJson.refresh_token || "")
  };
}

test("admin can disable a user license and CLI approval is blocked immediately", async ({ page }) => {
  const adminEmail = `playwright.admin.${Date.now()}@example.com`;
  const targetEmail = `playwright.target.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";

  await registerAndLogin(page, adminEmail, password);
  await promoteUserToAdmin(adminEmail);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Commercial control panel" })).toBeVisible();
  await logout(page);

  await registerAndLogin(page, targetEmail, password);
  await logout(page);

  await login(page, adminEmail, password);
  await page.goto("/admin");
  const row = page.locator("tr", { hasText: targetEmail });
  await expect(row).toBeVisible();
  await row.locator('input[name="seatLimit"]').fill("3");
  await row.locator('input[name="licenseActive"]').uncheck();
  page.once("dialog", (dialog) => dialog.accept());
  await Promise.all([
    page.waitForURL(/\/admin\?result=user_updated$/),
    row.getByRole("button", { name: "Save" }).click()
  ]);
  await expect(page.getByText("The user record was updated successfully.")).toBeVisible();
  await expect(page.locator("tr", { hasText: targetEmail }).locator(".status-pill", { hasText: "inactive" })).toBeVisible();
  await logout(page);

  await login(page, targetEmail, password);
  await page.goto(
    `/cli/login?state=${encodeURIComponent(`state-inactive-${Date.now()}`)}&install_id=${encodeURIComponent(`install-inactive-${Date.now()}`)}&device_name=${encodeURIComponent("Inactive Device")}&redirect_uri=${encodeURIComponent("http://127.0.0.1:46319/callback")}`
  );
  await expect(page.locator(".status-pill", { hasText: "License: inactive" })).toBeVisible();
  await expect(
    page.getByText("This account is currently inactive, so the install cannot be approved.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Authorize this install" })).toBeDisabled();
});

test("admin seat-limit reduction is enforced on subsequent CLI approvals", async ({ page, request, baseURL }) => {
  const adminEmail = `playwright.admin.seat.${Date.now()}@example.com`;
  const targetEmail = `playwright.target.seat.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";

  await registerAndLogin(page, adminEmail, password);
  await promoteUserToAdmin(adminEmail);
  await logout(page);

  await registerAndLogin(page, targetEmail, password);
  await logout(page);

  await login(page, adminEmail, password);
  await page.goto("/admin");
  const row = page.locator("tr", { hasText: targetEmail });
  await expect(row).toBeVisible();
  await row.locator('input[name="seatLimit"]').fill("1");
  await row.locator('input[name="licenseActive"]').check();
  page.once("dialog", (dialog) => dialog.accept());
  await Promise.all([
    page.waitForURL(/\/admin\?result=user_updated$/),
    row.getByRole("button", { name: "Save" }).click()
  ]);
  await logout(page);

  await login(page, targetEmail, password);
  await authorizeInstallViaBrowser(
    page,
    request,
    String(baseURL),
    `install-seat-enforced-1-${Date.now()}`,
    "Seat Enforced Device 1"
  );

  await page.goto(
    `/cli/login?state=${encodeURIComponent(`state-seat-limit-${Date.now()}`)}&install_id=${encodeURIComponent(`install-seat-enforced-2-${Date.now()}`)}&device_name=${encodeURIComponent("Seat Enforced Device 2")}&redirect_uri=${encodeURIComponent("http://127.0.0.1:46319/callback")}`
  );
  await expect(page.locator(".status-pill", { hasText: "Seats: 1/1" })).toBeVisible();
  await expect(
    page.getByText("Seat limit is already reached for this account. Revoke an old device before authorizing a new one.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Authorize this install" })).toBeDisabled();
});

test("admin device revoke disables the target install refresh path", async ({ page, request, baseURL }) => {
  const adminEmail = `playwright.admin.revoke.${Date.now()}@example.com`;
  const targetEmail = `playwright.target.revoke.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";
  const installId = `install-admin-revoke-${Date.now()}`;
  const deviceName = "Admin Revoked Device";

  await registerAndLogin(page, adminEmail, password);
  await promoteUserToAdmin(adminEmail);
  await logout(page);

  await registerAndLogin(page, targetEmail, password);
  const session = await authorizeInstallViaBrowser(
    page,
    request,
    String(baseURL),
    installId,
    deviceName
  );
  await logout(page);

  await login(page, adminEmail, password);
  await page.goto("/admin");
  const row = page.locator("tr", { hasText: installId });
  await expect(row).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await Promise.all([
    page.waitForURL(/\/admin\?result=device_revoked$/),
    row.getByRole("button", { name: "Revoke" }).click()
  ]);

  await expect(page.getByText("The device was revoked and its refresh tokens were disabled.")).toBeVisible();
  await expect(page.locator("tr", { hasText: installId }).locator(".status-pill", { hasText: "revoked" })).toBeVisible();

  const refresh = await request.post(`${baseURL}/api/cli/lease/refresh`, {
    data: {
      refresh_token: session.refreshToken,
      install_id: installId
    }
  });
  expect(refresh.status()).toBe(403);
  expect(await refresh.json()).toMatchObject({ detail: "Refresh token revoked" });
});
