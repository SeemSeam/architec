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

test("billing page shows stub readiness and checkout/portal feedback in local mode", async ({ page }) => {
  const email = `playwright.billing.${Date.now()}@example.com`;
  const password = "PlaywrightPass123!";

  await registerAndLogin(page, email, password);
  await page.goto("/account/billing");

  await expect(
    page.getByRole("heading", { name: "One subscription, one trial window, one monthly renewal price." })
  ).toBeVisible();
  await expect(page.locator(".status-pill", { hasText: "Billing mode: local stub mode" })).toBeVisible();
  await expect(page.getByText("ARCHITEC_CLOUD_STRIPE_SECRET_KEY is missing.")).toBeVisible();
  await expect(page.getByText("ARCHITEC_CLOUD_STRIPE_PRICE_ID_MONTHLY is missing.")).toBeVisible();

  await Promise.all([
    page.waitForURL(/\/account\/billing\?result=checkout_stub$/),
    page.getByRole("button", { name: "Open checkout stub" }).click()
  ]);
  await expect(
    page.getByText("Checkout is still a local stub. This is the handoff point where Stripe Checkout will be connected later.")
  ).toBeVisible();

  await Promise.all([
    page.waitForURL(/\/account\/billing\?result=portal_stub$/),
    page.getByRole("button", { name: "Open portal stub" }).click()
  ]);
  await expect(
    page.getByText("Customer portal is still a local stub. This endpoint is reserved for a future Stripe billing portal.")
  ).toBeVisible();
});
