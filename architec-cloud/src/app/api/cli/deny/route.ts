import { NextResponse } from "next/server";

import { absoluteAppUrl } from "@/lib/config";
import { currentUser } from "@/lib/auth";

export async function POST(request: Request) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.redirect(absoluteAppUrl("/login"), { status: 303 });
  }

  const formData = await request.formData();
  const state = String(formData.get("state") || "");
  const installId = String(formData.get("installId") || "");
  const deviceName = String(formData.get("deviceName") || "");
  const redirectUri = String(formData.get("redirectUri") || "");

  const location = redirectUri
    ? `${redirectUri}${redirectUri.includes("?") ? "&" : "?"}error=access_denied&state=${encodeURIComponent(state)}`
    : absoluteAppUrl("/account").toString();
  const completeUrl = absoluteAppUrl(
    `/cli/complete?result=denied&next=${encodeURIComponent(location)}&install_id=${encodeURIComponent(installId)}&device_name=${encodeURIComponent(deviceName)}`
  );
  return NextResponse.redirect(completeUrl, { status: 303 });
}
