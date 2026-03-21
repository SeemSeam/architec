import { NextResponse } from "next/server";

import { githubLatestInstallScriptUrl, githubLatestLinuxX64Url, githubLatestReleaseUrl } from "@/lib/config";
import { findRefreshToken, findUserById, readDb } from "@/lib/db";
import { sha256Text } from "@/lib/security";
import { getCliVersionGate } from "@/lib/version";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const refreshToken = url.searchParams.get("refresh_token") || "";
  const installId = url.searchParams.get("install_id") || "";
  const appVersion = url.searchParams.get("app_version");
  const versionGate = getCliVersionGate(appVersion);
  const db = await readDb();
  const token = findRefreshToken(db, sha256Text(refreshToken));
  if (!token || token.revokedAt) {
    return NextResponse.json({ detail: "Session not found" }, { status: 404 });
  }
  const device = db.devices.find((item) => item.id === token.deviceId);
  const user = findUserById(db, token.userId);
  if (!device || !user || device.installId !== installId) {
    return NextResponse.json({ detail: "Session not found" }, { status: 404 });
  }
  return NextResponse.json({
    email: user.email,
    plan: user.plan,
    seat_limit: user.seatLimit,
    license_active: user.licenseActive,
    install_id: device.installId,
    device_name: device.deviceName,
    device_revoked: Boolean(device.revokedAt),
    devices: db.devices.filter((item) => item.userId === user.id),
    client_version: versionGate.clientVersion,
    cli_min_version: versionGate.minimumVersion,
    invalid_client_version: versionGate.invalidClientVersion,
    invalid_minimum_version: versionGate.invalidMinimumVersion,
    upgrade_required: versionGate.upgradeRequired,
    version_detail: versionGate.detail,
    latest_release_url: githubLatestReleaseUrl,
    latest_linux_x64_url: githubLatestLinuxX64Url,
    latest_install_script_url: githubLatestInstallScriptUrl
  });
}
