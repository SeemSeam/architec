import { expect, test } from "@playwright/test";

async function registerAndLogin(page: Parameters<typeof test>[0]["page"], email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await Promise.all([
    page.waitForURL(/\/account$/),
    page.getByRole("button", { name: "Create account" }).click()
  ]);
}

async function approveCliInstallInBrowser(
  page: Parameters<typeof test>[0]["page"],
  {
    email,
    password,
    installId,
    deviceName,
    state,
    redirectUri,
    appVersion = "0.2.0",
    register = false
  }: {
    email: string;
    password: string;
    installId: string;
    deviceName: string;
    state: string;
    redirectUri: string;
    appVersion?: string;
    register?: boolean;
  }
) {
  if (register) {
    await registerAndLogin(page, email, password);
  }
  await page.goto(
    `/cli/login?state=${encodeURIComponent(state)}&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}&redirect_uri=${encodeURIComponent(redirectUri)}&app_version=${encodeURIComponent(appVersion)}`
  );

  await expect(
    page.getByRole("heading", { name: "Approve a local Architec install in one deliberate step." })
  ).toBeVisible();
  await expect(page.getByText(`Install:`).locator("..").getByText(installId)).toBeVisible();
  await expect(page.getByText(`Device:`).locator("..").getByText(deviceName)).toBeVisible();
  await expect(page.getByText(`CLI version:`).locator("..").getByText(appVersion)).toBeVisible();

  await Promise.all([
    page.waitForURL(/\/cli\/complete\?/),
    page.getByRole("button", { name: "Authorize this install" }).click()
  ]);

  await expect(
    page.getByRole("heading", { name: "The install has been approved in the browser." })
  ).toBeVisible();

  const continueHref = await page.getByRole("link", { name: "Continue now" }).getAttribute("href");
  expect(continueHref).toBeTruthy();

  const callbackUrl = new URL(String(continueHref));
  expect(callbackUrl.origin + callbackUrl.pathname).toBe("http://127.0.0.1:46319/callback");
  expect(callbackUrl.searchParams.get("source")).toBe("playwright");
  expect(callbackUrl.searchParams.get("state")).toBe(state);

  const code = callbackUrl.searchParams.get("code");
  expect(code).toBeTruthy();

  return {
    code: String(code)
  };
}

async function exchangeCliCode(
  request: Parameters<typeof test>[0]["request"],
  baseURL: string,
  {
    code,
    installId,
    appVersion = "0.2.0"
  }: {
    code: string;
    installId: string;
    appVersion?: string;
  }
) {
  const exchange = await request.post(`${baseURL}/api/cli/login/exchange`, {
    data: {
      code,
      install_id: installId,
      app_version: appVersion
    }
  });
  return exchange;
}

async function fetchCliStatus(
  request: Parameters<typeof test>[0]["request"],
  baseURL: string,
  {
    refreshToken,
    installId,
    appVersion = "0.2.0"
  }: {
    refreshToken: string;
    installId: string;
    appVersion?: string;
  }
) {
  return request.get(
    `${baseURL}/api/cli/status?refresh_token=${encodeURIComponent(refreshToken)}&install_id=${encodeURIComponent(installId)}&app_version=${encodeURIComponent(appVersion)}`
  );
}

async function authorizeCliInstall(
  page: Parameters<typeof test>[0]["page"],
  request: Parameters<typeof test>[0]["request"],
  baseURL: string,
  {
    email,
    password,
    installId,
    deviceName,
    state,
    redirectUri,
    appVersion = "0.2.0",
    register = false
  }: {
    email: string;
    password: string;
    installId: string;
    deviceName: string;
    state: string;
    redirectUri: string;
    appVersion?: string;
    register?: boolean;
  }
) {
  const browserApproval = await approveCliInstallInBrowser(page, {
    email,
    password,
    installId,
    deviceName,
    state,
    redirectUri,
    appVersion,
    register
  });

  const exchange = await exchangeCliCode(request, baseURL, {
    code: browserApproval.code,
    installId,
    appVersion
  });
  expect(exchange.ok()).toBeTruthy();
  const exchangeJson = await exchange.json();
  expect(exchangeJson.refresh_token).toBeTruthy();
  expect(exchangeJson.lease.email).toBe(email);
  expect(exchangeJson.lease.install_id).toBe(installId);
  expect(exchangeJson.lease.device_id).toBeTruthy();
  expect(exchangeJson.lease.signature).toBeTruthy();
  expect(exchangeJson.cli_min_version).toBe("0.2.0");
  expect(exchangeJson.client_version).toBe("0.2.0");
  expect(exchangeJson.upgrade_required).toBe(false);

  const status = await fetchCliStatus(request, baseURL, {
    refreshToken: exchangeJson.refresh_token,
    installId,
    appVersion
  });
  expect(status.ok()).toBeTruthy();
  const statusJson = await status.json();
  expect(statusJson.email).toBe(email);
  expect(statusJson.install_id).toBe(installId);
  expect(statusJson.device_name).toBe(deviceName);
  expect(statusJson.device_revoked).toBe(false);
  expect(statusJson.cli_min_version).toBe("0.2.0");
  expect(statusJson.client_version).toBe("0.2.0");
  expect(statusJson.upgrade_required).toBe(false);

  return {
    code: browserApproval.code,
    refreshToken: String(exchangeJson.refresh_token),
    statusJson
  };
}

test("approves a CLI install and exchanges the auth code for session state", async ({ page, request, baseURL }) => {
  const email = `playwright.cli.approve.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";
  const installId = `install-e2e-${Date.now()}`;
  const deviceName = "Playwright CLI Device";
  const state = `state-${Date.now()}`;
  const redirectUri = "http://127.0.0.1:46319/callback?source=playwright";

  await authorizeCliInstall(page, request, String(baseURL), {
    email,
    password,
    installId,
    deviceName,
    state,
    redirectUri,
    register: true
  });
});

test("revoking a device disables refresh and removes the active session path", async ({ page, request, baseURL }) => {
  const email = `playwright.cli.revoke.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";
  const installId = `install-revoke-${Date.now()}`;
  const deviceName = "Revoked CLI Device";
  const state = `state-revoke-${Date.now()}`;
  const redirectUri = "http://127.0.0.1:46319/callback?source=playwright";

  const session = await authorizeCliInstall(page, request, String(baseURL), {
    email,
    password,
    installId,
    deviceName,
    state,
    redirectUri,
    register: true
  });

  await page.goto("/account/devices");
  const row = page.locator("tr", { hasText: installId });
  await expect(row).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await Promise.all([
    page.waitForURL(/\/account\/devices\?result=device_revoked$/),
    row.getByRole("button", { name: "Revoke" }).click()
  ]);

  await expect(page.getByText("The device was revoked and its refresh path was disabled.")).toBeVisible();
  await expect(page.locator("tr", { hasText: installId }).locator(".status-pill", { hasText: "revoked" })).toBeVisible();

  const refresh = await request.post(`${baseURL}/api/cli/lease/refresh`, {
    data: {
      refresh_token: session.refreshToken,
      install_id: installId
    }
  });
  expect(refresh.status()).toBe(403);
  expect(await refresh.json()).toMatchObject({ detail: "Refresh token revoked" });

  const status = await request.get(
    `${baseURL}/api/cli/status?refresh_token=${encodeURIComponent(session.refreshToken)}&install_id=${encodeURIComponent(installId)}`
  );
  expect(status.status()).toBe(404);
  expect(await status.json()).toMatchObject({ detail: "Session not found" });
});

test("denies a CLI install and returns access_denied to the callback target", async ({ page }) => {
  const email = `playwright.cli.deny.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";
  const installId = `install-deny-${Date.now()}`;
  const deviceName = "Denied CLI Device";
  const state = `state-deny-${Date.now()}`;
  const redirectUri = "http://127.0.0.1:46319/callback?source=playwright-deny";

  await registerAndLogin(page, email, password);

  await page.goto(
    `/cli/login?state=${encodeURIComponent(state)}&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}&redirect_uri=${encodeURIComponent(redirectUri)}`
  );

  await Promise.all([
    page.waitForURL(/\/cli\/complete\?/),
    page.getByRole("button", { name: "Deny and return" }).click()
  ]);

  await expect(
    page.getByRole("heading", { name: "The install request was denied." })
  ).toBeVisible();

  const continueHref = await page.getByRole("link", { name: "Continue now" }).getAttribute("href");
  expect(continueHref).toBeTruthy();

  const callbackUrl = new URL(String(continueHref));
  expect(callbackUrl.searchParams.get("source")).toBe("playwright-deny");
  expect(callbackUrl.searchParams.get("state")).toBe(state);
  expect(callbackUrl.searchParams.get("error")).toBe("access_denied");
  expect(callbackUrl.searchParams.get("code")).toBeNull();
});

test("seat limit blocks authorization for a fourth install", async ({ page, request, baseURL }) => {
  const email = `playwright.cli.seats.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";

  await registerAndLogin(page, email, password);

  for (let index = 1; index <= 3; index += 1) {
    await authorizeCliInstall(page, request, String(baseURL), {
      email,
      password,
      installId: `install-seat-${Date.now()}-${index}`,
      deviceName: `Seat Device ${index}`,
      state: `state-seat-${Date.now()}-${index}`,
      redirectUri: "http://127.0.0.1:46319/callback?source=playwright",
      register: false
    });
  }

  const blockedInstallId = `install-seat-blocked-${Date.now()}`;
  await page.goto(
    `/cli/login?state=${encodeURIComponent(`state-blocked-${Date.now()}`)}&install_id=${encodeURIComponent(blockedInstallId)}&device_name=${encodeURIComponent("Seat Device Blocked")}&redirect_uri=${encodeURIComponent("http://127.0.0.1:46319/callback?source=playwright")}`
  );

  await expect(page.locator(".status-pill", { hasText: "Seats: 3/3" })).toBeVisible();
  await expect(
    page.getByText("Seat limit is already reached for this account. Revoke an old device before authorizing a new one.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Authorize this install" })).toBeDisabled();
});

test("outdated CLI version is blocked until the install is upgraded", async ({ page, request, baseURL }) => {
  const email = `playwright.cli.upgrade.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";
  const installId = `install-upgrade-${Date.now()}`;
  const deviceName = "Upgrade Required CLI Device";
  const state = `state-upgrade-${Date.now()}`;
  const redirectUri = "http://127.0.0.1:46319/callback?source=playwright";

  await registerAndLogin(page, email, password);

  await page.goto(
    `/cli/login?state=${encodeURIComponent(state)}&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}&redirect_uri=${encodeURIComponent(redirectUri)}&app_version=${encodeURIComponent("0.0.9")}`
  );

  await expect(page.locator(".status-pill", { hasText: "CLI: 0.0.9" })).toBeVisible();
  await expect(page.locator(".status-pill", { hasText: "Min: 0.2.0" })).toBeVisible();
  await expect(
    page.getByText("CLI 0.0.9 is below minimum supported version 0.2.0. Upgrade required.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Authorize this install" })).toBeDisabled();

  const browserApproval = await approveCliInstallInBrowser(page, {
    email,
    password,
    installId,
    deviceName,
    state,
    redirectUri,
    appVersion: "0.2.0",
    register: false
  });

  const outdatedExchange = await exchangeCliCode(request, String(baseURL), {
    code: browserApproval.code,
    installId,
    appVersion: "0.0.9"
  });
  expect(outdatedExchange.status()).toBe(426);
  expect(await outdatedExchange.json()).toMatchObject({
    cli_min_version: "0.2.0",
    client_version: "0.0.9",
    upgrade_required: true,
    latest_release_url: "https://github.com/bfly123/architec-releases/releases/latest",
    latest_linux_x64_url: "https://github.com/bfly123/architec-releases/releases/latest/download/archi-linux-x86_64.tar.gz",
    latest_install_script_url: "https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh"
  });

  const exchange = await exchangeCliCode(request, String(baseURL), {
    code: browserApproval.code,
    installId,
    appVersion: "0.2.0"
  });
  expect(exchange.ok()).toBeTruthy();
  const exchangeJson = await exchange.json();
  expect(exchangeJson.refresh_token).toBeTruthy();

  const status = await fetchCliStatus(request, String(baseURL), {
    refreshToken: exchangeJson.refresh_token,
    installId,
    appVersion: "0.0.9"
  });
  expect(status.ok()).toBeTruthy();
  expect(await status.json()).toMatchObject({
    cli_min_version: "0.2.0",
    client_version: "0.0.9",
    upgrade_required: true,
    latest_release_url: "https://github.com/bfly123/architec-releases/releases/latest",
    latest_linux_x64_url: "https://github.com/bfly123/architec-releases/releases/latest/download/archi-linux-x86_64.tar.gz",
    latest_install_script_url: "https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh"
  });
});
