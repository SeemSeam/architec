import { NextResponse } from "next/server";

import { absoluteAppUrl } from "@/lib/config";
import { currentUser } from "@/lib/auth";
import { createCheckoutSession, stripeEnabled } from "@/lib/stripe";

export async function POST() {
  const user = await currentUser();
  if (!user) {
    return NextResponse.redirect(absoluteAppUrl("/login"), { status: 303 });
  }
  if (!stripeEnabled) {
    return NextResponse.redirect(absoluteAppUrl("/account/billing?result=checkout_stub"), { status: 303 });
  }
  try {
    const url = await createCheckoutSession(user);
    return NextResponse.redirect(url, { status: 303 });
  } catch {
    return NextResponse.redirect(absoluteAppUrl("/account/billing?result=checkout_error"), { status: 303 });
  }
}
