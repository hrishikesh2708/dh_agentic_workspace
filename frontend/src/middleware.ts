import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { JWT_COOKIE } from "@/lib/auth";

export const PROJECT_ID_COOKIE = "dh_project_id";

function getToken(request: NextRequest): string | undefined {
  return request.cookies.get(JWT_COOKIE)?.value;
}

function getProjectId(request: NextRequest): string | undefined {
  return request.cookies.get(PROJECT_ID_COOKIE)?.value;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // /project — requires JWT only
  if (pathname === "/project" || pathname.startsWith("/project/")) {
    if (!getToken(request)) {
      const url = new URL("/login", request.url);
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  // /chat — requires JWT + active project
  if (pathname === "/chat" || pathname.startsWith("/chat/")) {
    if (!getToken(request)) {
      const url = new URL("/login", request.url);
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
    if (!getProjectId(request)) {
      return NextResponse.redirect(new URL("/project", request.url));
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/project/:path*", "/chat/:path*"],
};
