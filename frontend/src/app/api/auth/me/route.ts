import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { JWT_COOKIE, decodeJwt } from "@/lib/auth";

export async function GET() {
  const store = await cookies();
  const token = store.get(JWT_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  const user = decodeJwt(token);
  if (!user || user.exp * 1000 < Date.now()) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  return NextResponse.json({ user });
}
