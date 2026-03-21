import { NextResponse } from "next/server";

import { publicKeyPem } from "@/lib/security";

export async function GET() {
  return new NextResponse(await publicKeyPem(), {
    headers: {
      "content-type": "text/plain; charset=utf-8"
    }
  });
}
