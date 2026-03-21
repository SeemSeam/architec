import path from "node:path";

export const appName = "Architec Cloud";
export const appUrl = process.env.ARCHITEC_CLOUD_APP_URL || "http://127.0.0.1:3000";
export const dataDir = path.resolve(process.cwd(), process.env.ARCHITEC_CLOUD_DATA_DIR || ".data");
export const dbFile = path.join(dataDir, "dev-db.json");
export const sessionCookieName =
  process.env.ARCHITEC_CLOUD_SESSION_COOKIE || "architec_cloud_session";
export const supportEmail = (process.env.ARCHITEC_CLOUD_SUPPORT_EMAIL || "").trim();
export const leaseKid = "architec-cloud-dev-ed25519-1";
export const stripeSecretKey = process.env.ARCHITEC_CLOUD_STRIPE_SECRET_KEY || "";
export const stripePublishableKey = process.env.ARCHITEC_CLOUD_STRIPE_PUBLISHABLE_KEY || "";
export const stripeWebhookSecret = process.env.ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET || "";
export const stripePriceIdMonthly = process.env.ARCHITEC_CLOUD_STRIPE_PRICE_ID_MONTHLY || "";
export const cliMinVersion = (process.env.ARCHITEC_CLOUD_CLI_MIN_VERSION || "").trim();
export const githubRepoUrl = normalizeUrl(
  process.env.ARCHITEC_CLOUD_GITHUB_REPO_URL || "https://github.com/bfly123/architec-releases"
);
export const githubReleasesUrl = normalizeUrl(
  process.env.ARCHITEC_CLOUD_GITHUB_RELEASES_URL || `${githubRepoUrl}/releases`
);
export const githubLatestReleaseUrl = normalizeUrl(
  process.env.ARCHITEC_CLOUD_GITHUB_LATEST_RELEASE_URL || `${githubReleasesUrl}/latest`
);
export const githubLatestLinuxX64Url = normalizeUrl(
  process.env.ARCHITEC_CLOUD_GITHUB_LATEST_LINUX_X64_URL ||
    `${githubReleasesUrl}/latest/download/archi-linux-x86_64.tar.gz`
);
export const githubLatestInstallScriptUrl = normalizeUrl(
  process.env.ARCHITEC_CLOUD_GITHUB_LATEST_INSTALL_SCRIPT_URL ||
    `${githubReleasesUrl}/latest/download/install_prod.sh`
);
export const githubLatestChecksumsUrl = normalizeUrl(
  process.env.ARCHITEC_CLOUD_GITHUB_LATEST_CHECKSUMS_URL ||
    `${githubReleasesUrl}/latest/download/SHA256SUMS.txt`
);

function normalizeUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

export function absoluteAppUrl(targetPath: string): URL {
  return new URL(targetPath, appUrl.endsWith("/") ? appUrl : `${appUrl}/`);
}
