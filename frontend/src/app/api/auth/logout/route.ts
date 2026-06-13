import { NextResponse } from "next/server";

import { JWT_COOKIE } from "@/lib/auth";
import { PROJECT_ID_COOKIE } from "@/lib/project-storage";

export async function POST() {
  const response = NextResponse.json({ success: true });
  for (const name of [JWT_COOKIE, PROJECT_ID_COOKIE]) {
    response.cookies.set(name, "", { path: "/", maxAge: 0 });
  }
  return response;
}
