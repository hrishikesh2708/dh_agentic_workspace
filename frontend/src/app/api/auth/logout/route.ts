import { NextResponse } from "next/server";

const JWT_COOKIE = "datahash_jwt";
const JWT_PUB_COOKIE = "datahash_jwt_pub";

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
