import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/bff";
import { parseApiErrorBody } from "@/lib/api-errors";

export async function GET() {
  const res = await backendFetch("/projects");

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  if (!res.ok) {
    const { message } = parseApiErrorBody(parsed, "projects_fetch_failed");
    return NextResponse.json({ detail: message }, { status: res.status });
  }

  return NextResponse.json(parsed);
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "invalid_request_body" }, { status: 400 });
  }

  const res = await backendFetch("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  if (!res.ok) {
    const { message, fieldErrors } = parseApiErrorBody(parsed, "project_create_failed");
    return NextResponse.json({ detail: message, errors: fieldErrors }, { status: res.status });
  }

  return NextResponse.json(parsed, { status: 201 });
}
