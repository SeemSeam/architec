import { NextResponse } from "next/server";

import { absoluteAppUrl, sessionCookieName } from "@/lib/config";

export async function POST() {
  const response = NextResponse.redirect(absoluteAppUrl("/"), { status: 303 });
  response.cookies.delete(sessionCookieName);
  return response;
}
