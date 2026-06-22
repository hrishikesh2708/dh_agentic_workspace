export interface AuthorizeConnectionResponse {
  auth_url: string;
  state: string;
}

/** Start OAuth for a connector via the Next.js BFF (forwards JWT + session id). */
export async function authorizeConnection(
  connectorSlug: string,
  projectId: string,
  sessionId: string,
): Promise<AuthorizeConnectionResponse> {
  const res = await fetch(
    `/api/connections/${connectorSlug}?project_id=${encodeURIComponent(projectId)}`,
    {
      method: "POST",
      headers: { "X-Session-Id": sessionId },
    },
  );

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    const detail =
      parsed &&
      typeof parsed === "object" &&
      "detail" in parsed &&
      typeof (parsed as { detail: unknown }).detail === "string"
        ? (parsed as { detail: string }).detail
        : `Authorize failed: ${res.status}`;
    throw new Error(detail);
  }

  const data = parsed as AuthorizeConnectionResponse;
  if (!data?.auth_url) {
    throw new Error("No auth_url returned");
  }

  return data;
}
