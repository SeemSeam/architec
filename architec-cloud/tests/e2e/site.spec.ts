import { expect, test } from "@playwright/test";

test("public pages render and protected account redirects to login", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Run Architec locally. Control access online." })
  ).toBeVisible();
  await expect(page.locator("header").getByRole("link", { name: "Support" })).toBeVisible();
  await expect(page.locator("header").getByRole("link", { name: "Status" })).toBeVisible();

  await page.goto("/support");
  await expect(
    page.getByRole("heading", {
      name: "Support should resolve account, seat, and authorization problems without touching repository data."
    })
  ).toBeVisible();
  await expect(page.getByText("support@example.com")).toBeVisible();

  await page.goto("/status");
  await expect(
    page.getByRole("heading", {
      name: "Current service status is local validation, not public production SLA."
    })
  ).toBeVisible();
  await expect(page.getByText("Billing still local stub")).toBeVisible();
  await expect(page.getByText("Minimum supported CLI version: 0.2.0")).toBeVisible();

  await page.goto("/legal/privacy");
  await expect(page.getByRole("heading", { name: "Privacy policy" })).toBeVisible();

  await page.goto("/legal/terms");
  await expect(page.getByRole("heading", { name: "Terms of service" })).toBeVisible();

  await page.goto("/account");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Resume device control and browser authorization." })
  ).toBeVisible();
});

test("download page points users to GitHub Releases and keeps the website as the control plane", async ({
  page
}) => {
  await page.goto("/download");

  await expect(
    page.getByRole("heading", { name: "Download from GitHub. Authorize through the browser." })
  ).toBeVisible();
  await expect(page.getByText("This website only handles registration, login, trial state, device seats")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open GitHub Releases" })).toHaveAttribute(
    "href",
    "https://github.com/bfly123/architec-releases/releases"
  );
  await expect(page.getByRole("link", { name: "Download Linux Build" })).toHaveAttribute(
    "href",
    "https://github.com/bfly123/architec-releases/releases/latest/download/archi-linux-x86_64.tar.gz"
  );
  await expect(page.getByRole("link", { name: "Download Install Script" })).toHaveAttribute(
    "href",
    "https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh"
  );
});
