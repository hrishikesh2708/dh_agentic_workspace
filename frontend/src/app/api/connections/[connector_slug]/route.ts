/**
 * BFF proxy for connection endpoints.
 *
 * POST /api/connections/{connector_slug}?action=authorize&project_id=X
 *   → POST backend /api/v1/connections/{connector_slug}/authorize?project_id=X
 *   → { auth_url, state }
 *
 * DELETE /api/connections/{connector_slug}?project_id=X
 *   → DELETE backend /api/v1/connections/{connector_slug}/disconnect?project_id=X
 *   → { deleted, connector_slug }
 *
 * Reads the httpOnly JWT cookie server-side so the browser never needs
 * to touch the token directly.
 */
import { NextRequest, NextResponse } from "next/server";

import { backendFetch } from "@/lib/bff";

type Ctx = { params: Promise<{ connector_slug: string }> };

export async function POST(req: NextRequest, ctx: Ctx) {
  const { connector_slug } = await ctx.params;
  const projectId = req.nextUrl.searchParams.get("project_id");
  if (!projectId) {
    return NextResponse.json({ detail: "missing project_id" }, { status: 400 });
  }

  const sessionId = req.headers.get("x-session-id")?.trim();
  if (!sessionId) {
    return NextResponse.json({ detail: "missing session_id" }, { status: 400 });
  }

  const res = await backendFetch(
    `/connections/${connector_slug}/authorize?project_id=${projectId}`,
    {
      method: "POST",
      headers: { "X-Session-Id": sessionId },
    },
  );

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  return NextResponse.json(parsed, { status: res.status });
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  const { connector_slug } = await ctx.params;
  const projectId = req.nextUrl.searchParams.get("project_id");
  if (!projectId) {
    return NextResponse.json({ detail: "missing project_id" }, { status: 400 });
  }

  const res = await backendFetch(
    `/connections/${connector_slug}/disconnect?project_id=${projectId}`,
    { method: "DELETE" },
  );

  const text = await res.text();
  let parsed: unknown = null;
  try { parsed = JSON.parse(text); } catch { parsed = text; }

  return NextResponse.json(parsed, { status: res.status });
}
