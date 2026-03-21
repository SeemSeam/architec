import { NextResponse } from "next/server";

import { absoluteAppUrl } from "@/lib/config";
import { currentUser } from "@/lib/auth";
import { withDb } from "@/lib/db";
import { nowIso } from "@/lib/security";

export async function POST(request: Request) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.redirect(absoluteAppUrl("/login"), { status: 303 });
  }
  const formData = await request.formData();
  const deviceId = String(formData.get("deviceId") || "");
  let revoked = false;
  await withDb(async (db) => {
    const device = db.devices.find((item) => item.id === deviceId && item.userId === user.id);
    if (!device) {
      return;
    }
    device.revokedAt = nowIso();
    for (const token of db.refreshTokens.filter((item) => item.deviceId === device.id)) {
      token.revokedAt = nowIso();
    }
    revoked = true;
  });
  return NextResponse.redirect(
    absoluteAppUrl(`/account/devices?result=${revoked ? "device_revoked" : "device_missing"}`),
    { status: 303 }
  );
}
