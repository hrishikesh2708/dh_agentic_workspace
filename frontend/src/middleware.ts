import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const JWT_COOKIE = "datahash_jwt";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/mappings",
  "/runs",
  "/golden-rules",
  "/integrations",
  "/chat",
];

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!isProtected(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(JWT_COOKIE)?.value;
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/mappings/:path*",
    "/runs/:path*",
    "/golden-rules/:path*",
    "/integrations/:path*",
    "/chat/:path*",
  ],
};
