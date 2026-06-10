import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { decodeJwt } from "jose";

const JWT_COOKIE = "datahash_jwt";

interface JwtPayload {
  sub?: string;
  user_id?: string | number;
  email?: string;
  exp?: number;
}

export async function GET() {
  const store = await cookies();
  const token = store.get(JWT_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  try {
    const payload = decodeJwt(token) as JwtPayload;
    if (typeof payload.exp !== "number" || payload.exp * 1000 < Date.now()) {
      return NextResponse.json({ user: null }, { status: 401 });
    }
    const userId = payload.sub ?? payload.user_id;
    if (userId === undefined) {
      return NextResponse.json({ user: null }, { status: 401 });
    }
    return NextResponse.json({
      user: {
        user_id: String(userId),
        email: payload.email,
        exp: payload.exp,
      },
    });
  } catch {
    return NextResponse.json({ user: null }, { status: 401 });
  }
}
