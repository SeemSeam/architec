import { NextResponse } from "next/server";

import { absoluteAppUrl } from "@/lib/config";
import { currentUser } from "@/lib/auth";
import { createPortalSession, stripeEnabled } from "@/lib/stripe";

export async function POST() {
  const user = await currentUser();
  if (!user) {
    return NextResponse.redirect(absoluteAppUrl("/login"), { status: 303 });
  }
  if (!stripeEnabled) {
    return NextResponse.redirect(absoluteAppUrl("/account/billing?result=portal_stub"), { status: 303 });
  }
  try {
    const url = await createPortalSession(user);
    return NextResponse.redirect(url, { status: 303 });
  } catch {
    return NextResponse.redirect(absoluteAppUrl("/account/billing?result=portal_error"), { status: 303 });
  }
}
