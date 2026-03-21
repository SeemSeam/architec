import { NextResponse } from "next/server";

import { absoluteAppUrl, sessionCookieName } from "@/lib/config";
import { findUserByEmail, withDb } from "@/lib/db";
import { consumeRateLimit, envRateLimit, requestIp } from "@/lib/rate-limit";
import { afterSeconds, nowIso, randomToken, verifyPassword } from "@/lib/security";

export async function GET() {
  return NextResponse.redirect(absoluteAppUrl("/login"));
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const email = String(formData.get("email") || "").trim().toLowerCase();
  const password = String(formData.get("password") || "");
  const sessionId = randomToken();
  let ok = false;

  const ipLimit = consumeRateLimit({
    scope: "auth:login:ip",
    key: requestIp(request),
    limit: envRateLimit("ARCHITEC_CLOUD_RATE_LIMIT_LOGIN_IP", { defaultValue: 12 }),
    windowMs: 10 * 60 * 1000
  });
  const identityLimit = consumeRateLimit({
    scope: "auth:login:email",
    key: email || requestIp(request),
    limit: envRateLimit("ARCHITEC_CLOUD_RATE_LIMIT_LOGIN_EMAIL", { defaultValue: 8 }),
    windowMs: 10 * 60 * 1000
  });
  if (!ipLimit.allowed || !identityLimit.allowed) {
    return NextResponse.redirect(absoluteAppUrl("/login?error=rate_limited"), { status: 303 });
  }

  await withDb(async (db) => {
    const user = findUserByEmail(db, email);
    if (!user) {
      return;
    }
    ok = await verifyPassword(password, user.passwordHash);
    if (!ok) {
      return;
    }
    db.sessions.push({
      id: sessionId,
      userId: user.id,
      createdAt: nowIso(),
      expiresAt: afterSeconds(60 * 60 * 24 * 7)
    });
  });

  if (!ok) {
    return NextResponse.redirect(absoluteAppUrl("/login?error=invalid_credentials"), { status: 303 });
  }

  const response = NextResponse.redirect(absoluteAppUrl("/account"), { status: 303 });
  response.cookies.set(sessionCookieName, sessionId, { httpOnly: true, sameSite: "lax", path: "/" });
  return response;
}
