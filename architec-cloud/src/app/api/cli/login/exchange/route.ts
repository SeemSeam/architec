import { NextResponse } from "next/server";
import { z } from "zod";

import { githubLatestInstallScriptUrl, githubLatestLinuxX64Url, githubLatestReleaseUrl } from "@/lib/config";
import { activeDevices, findAuthCode, findDeviceByInstallId, findUserById, withDb } from "@/lib/db";
import { buildLeaseBase, nowIso, randomToken, sha256Text, signLeaseBody, afterSeconds } from "@/lib/security";
import { getCliVersionGate } from "@/lib/version";

const schema = z.object({
  code: z.string().min(1),
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
      const authCode = findAuthCode(db, body.code);
      if (!authCode) {
        throw new Error("Unknown auth code");
      }
      if (authCode.usedAt) {
        throw new Error("Auth code already used");
      }
      if (authCode.installId !== body.install_id) {
        throw new Error("Install id mismatch");
      }
      if (new Date(authCode.expiresAt).getTime() <= Date.now()) {
        throw new Error("Auth code expired");
      }
      const user = findUserById(db, authCode.userId);
      if (!user || !user.licenseActive || !user.emailVerified) {
        throw new Error("License inactive");
      }
      let device = findDeviceByInstallId(db, user.id, body.install_id);
      if (!device) {
        if (activeDevices(db, user.id).length >= user.seatLimit) {
          throw new Error("Seat limit reached. Revoke an existing device first.");
        }
        device = {
          id: randomToken(10),
          userId: user.id,
          installId: body.install_id,
          deviceName: authCode.deviceName,
          createdAt: nowIso(),
          lastSeenAt: nowIso(),
          revokedAt: null
        };
        db.devices.push(device);
      } else {
        device.revokedAt = null;
        device.lastSeenAt = nowIso();
        device.deviceName = authCode.deviceName;
      }
      authCode.usedAt = nowIso();

      const refreshToken = randomToken(24);
      db.refreshTokens.push({
        id: randomToken(10),
        userId: user.id,
        deviceId: device.id,
        tokenHash: sha256Text(refreshToken),
        createdAt: nowIso(),
        expiresAt: afterSeconds(60 * 60 * 24 * 30),
        lastUsedAt: nowIso(),
        revokedAt: null
      });
      const leaseBody = buildLeaseBase(user, device.id, body.install_id);
      const signature = await signLeaseBody(leaseBody);
      return {
        refresh_token: refreshToken,
        refresh_token_expires_at: afterSeconds(60 * 60 * 24 * 30),
        public_key_url: "/api/cli/public-key",
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
      { detail: error instanceof Error ? error.message : "Exchange failed" },
      { status: 403 }
    );
  }
}
