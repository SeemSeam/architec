import { NextResponse } from "next/server";
import { z } from "zod";

import { githubLatestInstallScriptUrl, githubLatestLinuxX64Url, githubLatestReleaseUrl } from "@/lib/config";
import { findRefreshToken, findUserById, withDb } from "@/lib/db";
import { buildLeaseBase, nowIso, sha256Text, signLeaseBody } from "@/lib/security";
import { getCliVersionGate } from "@/lib/version";

const schema = z.object({
  refresh_token: z.string().min(1),
  install_id: z.string().min(1),
  app_version: z.string().trim().optional()
});

export async function POST(request: Request) {
  const body = schema.parse(await request.json());
  const versionGate = getCliVersionGate(body.app_version);

  if (versionGate.invalidMinimumVersion) {
    return NextResponse.json(
      {
        detail: versionGate.detail,
        cli_min_version: versionGate.minimumVersion,
        client_version: versionGate.clientVersion,
        upgrade_required: false,
        latest_release_url: githubLatestReleaseUrl,
        latest_linux_x64_url: githubLatestLinuxX64Url,
        latest_install_script_url: githubLatestInstallScriptUrl
      },
      { status: 500 }
    );
  }

  if (versionGate.invalidClientVersion) {
    return NextResponse.json(
      {
        detail: versionGate.detail,
        cli_min_version: versionGate.minimumVersion,
        client_version: versionGate.clientVersion,
        upgrade_required: false,
        latest_release_url: githubLatestReleaseUrl,
        latest_linux_x64_url: githubLatestLinuxX64Url,
        latest_install_script_url: githubLatestInstallScriptUrl
      },
      { status: 400 }
    );
  }

  if (versionGate.upgradeRequired) {
    return NextResponse.json(
      {
        detail: versionGate.detail,
        cli_min_version: versionGate.minimumVersion,
        client_version: versionGate.clientVersion,
        upgrade_required: true,
        latest_release_url: githubLatestReleaseUrl,
        latest_linux_x64_url: githubLatestLinuxX64Url,
        latest_install_script_url: githubLatestInstallScriptUrl
      },
      { status: 426 }
    );
  }

  try {
    const result = await withDb(async (db) => {
      const token = findRefreshToken(db, sha256Text(body.refresh_token));
      if (!token || token.revokedAt) {
        throw new Error("Refresh token revoked");
      }
      if (new Date(token.expiresAt).getTime() <= Date.now()) {
        throw new Error("Refresh token expired");
      }
      const device = db.devices.find((item) => item.id === token.deviceId);
      const user = token ? findUserById(db, token.userId) : undefined;
      if (!token || !device || !user) {
        throw new Error("Refresh token revoked");
      }
      if (device.installId !== body.install_id) {
        throw new Error("Install id mismatch");
      }
      if (device.revokedAt) {
        throw new Error("Device revoked");
      }
      if (!user.licenseActive || !user.emailVerified) {
        throw new Error("License inactive");
      }
      token.lastUsedAt = nowIso();
      device.lastSeenAt = nowIso();
      const leaseBody = buildLeaseBase(user, device.id, body.install_id);
      const signature = await signLeaseBody(leaseBody);
      return {
        cli_min_version: versionGate.minimumVersion,
        client_version: versionGate.clientVersion,
        upgrade_required: false,
        latest_release_url: githubLatestReleaseUrl,
        latest_linux_x64_url: githubLatestLinuxX64Url,
        latest_install_script_url: githubLatestInstallScriptUrl,
        lease: { ...leaseBody, signature }
      };
    });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Refresh failed" },
      { status: 403 }
    );
  }
}
