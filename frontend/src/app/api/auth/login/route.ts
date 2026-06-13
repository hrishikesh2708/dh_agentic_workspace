import { NextResponse } from "next/server";
import { decodeJwt } from "jose";

import { parseApiErrorBody } from "@/lib/api-errors";
import { JWT_COOKIE, JWT_PUB_COOKIE } from "@/lib/auth";

const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  "http://localhost:8000";

interface LoginBody {
  email?: string;
  password?: string;
}

interface BackendTokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export async function POST(request: Request) {
  let body: LoginBody;
  try {
    body = (await request.json()) as LoginBody;
  } catch {
    return NextResponse.json(
      { detail: "invalid_request_body" },
      { status: 400 },
    );
  }

  const { email, password } = body;
  if (!email || !password) {
    return NextResponse.json(
      { detail: "email_and_password_required" },
      { status: 400 },
    );
  }

  const form = new URLSearchParams();
  form.set("email", email);
  form.set("password", password);
  form.set("grant_type", "password");

  const backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body: form.toString(),
    cache: "no-store",
  });

  const text = await backendRes.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!backendRes.ok) {
    const { message, fieldErrors } = parseApiErrorBody(parsed, "login_failed");
    return NextResponse.json(
      { detail: message, errors: fieldErrors },
      { status: backendRes.status },
    );
  }

  const token = parsed as BackendTokenResponse;
  if (!token?.access_token) {
    return NextResponse.json(
      { detail: "invalid_backend_response" },
      { status: 502 },
    );
  }

  let maxAge: number | undefined;
  try {
    const payload = decodeJwt(token.access_token);
    if (typeof payload.exp === "number") {
      const remaining = payload.exp - Math.floor(Date.now() / 1000);
      maxAge = remaining > 0 ? remaining : undefined;
    }
  } catch {
    maxAge = undefined;
  }

  const isProd = process.env.NODE_ENV === "production";
  const response = NextResponse.json({ success: true });
  const cookieOpts = {
    path: "/" as const,
    sameSite: "lax" as const,
    secure: isProd,
    maxAge,
  };

  response.cookies.set(JWT_COOKIE, token.access_token, {
    ...cookieOpts,
    httpOnly: true,
  });
  response.cookies.set(JWT_PUB_COOKIE, token.access_token, {
    ...cookieOpts,
    httpOnly: false,
  });

  return response;
}
