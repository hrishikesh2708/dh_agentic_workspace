import { parseApiErrorBody } from "./api-errors";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

/**
 * All API calls go through Next.js BFF routes (/api/*).
 * Paths like "/projects" become "/api/projects".
 * The BFF reads the httpOnly JWT cookie and forwards it to FastAPI —
 * the browser never touches the token or the backend URL directly.
 */
function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (normalized.startsWith("/api/")) return normalized;
  return `/api${normalized}`;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { body, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  };

  let serializedBody: BodyInit | undefined;
  if (body !== undefined) {
    if (
      body instanceof FormData ||
      body instanceof URLSearchParams ||
      body instanceof Blob ||
      typeof body === "string"
    ) {
      serializedBody = body as BodyInit;
    } else {
      serializedBody = JSON.stringify(body);
      finalHeaders["Content-Type"] ??= "application/json";
    }
  }

  const res = await fetch(buildUrl(path), {
    ...rest,
    headers: finalHeaders,
    body: serializedBody,
    credentials: "include", // sends httpOnly cookie to the Next.js BFF
  });

  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    throw new ApiError("unauthorized", 401, null);
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try { parsed = JSON.parse(text); } catch { parsed = text; }
  }

  if (!res.ok) {
    const { message } = parseApiErrorBody(parsed, `request_failed_${res.status}`);
    throw new ApiError(message, res.status, parsed);
  }

  return parsed as T;
}

export const apiClient = {
  get: <T = unknown>(path: string, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T = unknown>(path: string, body?: unknown, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "POST", body }),
  put: <T = unknown>(path: string, body?: unknown, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "PUT", body }),
  patch: <T = unknown>(path: string, body?: unknown, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "PATCH", body }),
  delete: <T = unknown>(path: string, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
};
