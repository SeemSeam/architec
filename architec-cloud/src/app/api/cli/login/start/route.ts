import { NextResponse } from "next/server";

export async function POST(request: Request) {
  return NextResponse.json({
    message: "Use /cli/login with state, install_id, device_name, and redirect_uri query params."
  });
}
