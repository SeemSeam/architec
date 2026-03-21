import { NextResponse } from "next/server";

import { defaultPlanCode, defaultSeatLimit } from "@/lib/billing";
import { absoluteAppUrl, sessionCookieName } from "@/lib/config";
import { findUserByEmail, withDb } from "@/lib/db";
import { consumeRateLimit, envRateLimit, requestIp } from "@/lib/rate-limit";
import { afterSeconds, hashPassword, nowIso, randomToken } from "@/lib/security";

export async function GET() {
  return NextResponse.redirect(absoluteAppUrl("/register"));
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const email = String(formData.get("email") || "").trim().toLowerCase();
  const password = String(formData.get("password") || "");

  const ipLimit = consumeRateLimit({
    scope: "auth:register:ip",
    key: requestIp(request),
    limit: envRateLimit("ARCHITEC_CLOUD_RATE_LIMIT_REGISTER_IP", { defaultValue: 6 }),
    windowMs: 30 * 60 * 1000
  });
  const identityLimit = consumeRateLimit({
    scope: "auth:register:email",
    key: email || requestIp(request),
    limit: envRateLimit("ARCHITEC_CLOUD_RATE_LIMIT_REGISTER_EMAIL", { defaultValue: 3 }),
    windowMs: 30 * 60 * 1000
  });
  if (!ipLimit.allowed || !identityLimit.allowed) {
    return NextResponse.redirect(absoluteAppUrl("/register?error=rate_limited"), { status: 303 });
  }

  if (!email || password.length < 8) {
    return NextResponse.redirect(absoluteAppUrl("/register?error=invalid_input"), { status: 303 });
  }

  const sessionId = randomToken();
  try {
    await withDb(async (db) => {
      if (findUserByEmail(db, email)) {
        throw new Error("EMAIL_EXISTS");
      }
      const now = nowIso();
      const userId = randomToken(12);
      db.users.push({
        id: userId,
        email,
        passwordHash: await hashPassword(password),
        plan: defaultPlanCode,
        seatLimit: defaultSeatLimit,
        licenseActive: true,
        emailVerified: true,
        isAdmin: db.users.length === 0,
        createdAt: now,
        stripeCustomerId: null,
        stripeSubscriptionId: null,
        stripeSubscriptionStatus: null
      });
      db.sessions.push({
        id: sessionId,
        userId,
        createdAt: now,
        expiresAt: afterSeconds(60 * 60 * 24 * 7)
      });
    });
  } catch (error) {
    if (error instanceof Error && error.message === "EMAIL_EXISTS") {
      return NextResponse.redirect(absoluteAppUrl("/register?error=email_exists"), { status: 303 });
    }
    return NextResponse.redirect(absoluteAppUrl("/register?error=server_error"), { status: 303 });
  }

  const response = NextResponse.redirect(absoluteAppUrl("/account"), { status: 303 });
  response.cookies.set(sessionCookieName, sessionId, { httpOnly: true, sameSite: "lax", path: "/" });
  return response;
}
