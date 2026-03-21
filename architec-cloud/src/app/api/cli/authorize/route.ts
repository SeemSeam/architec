import { NextResponse } from "next/server";

import { absoluteAppUrl } from "@/lib/config";
import { currentUser } from "@/lib/auth";
import { withDb } from "@/lib/db";
import { afterSeconds, nowIso, randomToken } from "@/lib/security";
import { getCliVersionGate } from "@/lib/version";

export async function POST(request: Request) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.redirect(absoluteAppUrl("/login"), { status: 303 });
  }
  const formData = await request.formData();
  const state = String(formData.get("state") || "");
  const installId = String(formData.get("installId") || "");
  const deviceName = String(formData.get("deviceName") || "CLI Device");
  const redirectUri = String(formData.get("redirectUri") || "");
  const appVersion = String(formData.get("appVersion") || "");
  const versionGate = getCliVersionGate(appVersion);
  const code = randomToken(18);

  if (versionGate.invalidClientVersion || versionGate.invalidMinimumVersion || versionGate.upgradeRequired) {
    const location = absoluteAppUrl(
      `/cli/complete?result=upgrade_required&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}`
    );
    return NextResponse.redirect(location, { status: 303 });
  }

  await withDb((db) => {
    db.authCodes.push({
      code,
      userId: user.id,
      installId,
      deviceName,
      redirectUri,
      createdAt: nowIso(),
      expiresAt: afterSeconds(60 * 10),
      usedAt: null
    });
  });

  const location = redirectUri
    ? `${redirectUri}${redirectUri.includes("?") ? "&" : "?"}code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
    : `/account`;
  const completeUrl = absoluteAppUrl(
    `/cli/complete?result=approved&next=${encodeURIComponent(location)}&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}`
  );
  return NextResponse.redirect(completeUrl, { status: 303 });
}
