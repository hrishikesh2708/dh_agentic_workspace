import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/bff";
import { parseApiErrorBody } from "@/lib/api-errors";

export async function POST() {
  const res = await backendFetch("/auth/session", { method: "POST" });

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  if (!res.ok) {
    const { message } = parseApiErrorBody(parsed, "session_create_failed");
    return NextResponse.json({ detail: message }, { status: res.status });
  }

  return NextResponse.json(parsed);
}
