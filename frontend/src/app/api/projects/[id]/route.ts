import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/bff";
import { parseApiErrorBody } from "@/lib/api-errors";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const res = await backendFetch(`/projects/${id}`);

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  if (!res.ok) {
    const { message } = parseApiErrorBody(parsed, "project_fetch_failed");
    return NextResponse.json({ detail: message }, { status: res.status });
  }

  return NextResponse.json(parsed);
}
