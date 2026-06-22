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

  if (
    !body ||
    typeof body !== "object" ||
    !("project_id" in body) ||
    typeof (body as { project_id: unknown }).project_id !== "string" ||
    !(body as { project_id: string }).project_id
  ) {
    return NextResponse.json({ detail: "project_id_required" }, { status: 400 });
  }

  const res = await backendFetch("/auth/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  if (!res.ok) {
    const { message } = parseApiErrorBody(parsed, "session_create_failed");
    return NextResponse.json({ detail: message }, { status: res.status });
  }

  return NextResponse.json(parsed);
}
