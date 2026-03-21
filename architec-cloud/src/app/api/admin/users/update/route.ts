import { NextResponse } from "next/server";

import { defaultPlanCode } from "@/lib/billing";
import { absoluteAppUrl } from "@/lib/config";
import { currentUser } from "@/lib/auth";
import { withDb } from "@/lib/db";

export async function POST(request: Request) {
  const user = await currentUser();
  if (!user?.isAdmin) {
    return NextResponse.redirect(absoluteAppUrl("/account"), { status: 303 });
  }
  const formData = await request.formData();
  const userId = String(formData.get("userId") || "");
  const seatLimit = Math.max(1, Number(formData.get("seatLimit") || 1));
  const licenseActive = String(formData.get("licenseActive") || "") === "1";
  let updated = false;

  await withDb(async (db) => {
    const target = db.users.find((item) => item.id === userId);
    if (!target) {
      return;
    }
    target.plan = defaultPlanCode;
    target.seatLimit = seatLimit;
    target.licenseActive = licenseActive;
    updated = true;
  });

  return NextResponse.redirect(
    absoluteAppUrl(`/admin?result=${updated ? "user_updated" : "user_missing"}`),
    { status: 303 }
  );
}
