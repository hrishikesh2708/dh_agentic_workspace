import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/bff";
import { parseApiErrorBody } from "@/lib/api-errors";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "invalid_request_body" }, { status: 400 });
  }

  const res = await backendFetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    noAuth: true,
  });

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  if (!res.ok) {
    const { message, fieldErrors } = parseApiErrorBody(parsed, "register_failed");
    return NextResponse.json({ detail: message, errors: fieldErrors }, { status: res.status });
  }

  return NextResponse.json(parsed, { status: res.status });
}
