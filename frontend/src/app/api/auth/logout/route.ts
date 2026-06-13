import { NextResponse } from "next/server";

import { JWT_COOKIE, JWT_PUB_COOKIE } from "@/lib/auth";

export async function POST() {
  const response = NextResponse.json({ success: true });
  for (const name of [JWT_COOKIE, JWT_PUB_COOKIE]) {
    response.cookies.set(name, "", {
      path: "/",
      maxAge: 0,
    });
  }
  return response;
}
