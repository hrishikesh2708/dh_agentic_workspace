import { parseApiErrorBody } from "./api-errors";
import { JWT_PUB_COOKIE, readCookieFromDocument } from "./auth";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

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
  /** If provided, used directly as Bearer token instead of reading cookie. */
  token?: string;
  /** Skip Authorization header entirely (e.g. login). */
  noAuth?: boolean;
}

function buildUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (normalized.startsWith("/api/")) {
    return `${BACKEND_URL}${normalized}`;
  }
  return `${BACKEND_URL}${API_PREFIX}${normalized}`;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { body, token, noAuth, headers, ...rest } = options;

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

  if (!noAuth) {
    const bearer = token ?? readCookieFromDocument(JWT_PUB_COOKIE);
    if (bearer) {
      finalHeaders.Authorization = `Bearer ${bearer}`;
    }
  }

  const res = await fetch(buildUrl(path), {
    ...rest,
    headers: finalHeaders,
    body: serializedBody,
    credentials: "include",
  });

  if (res.status === 401 && typeof window !== "undefined") {
    // Drop session and bounce to /login.
    window.location.href = "/login";
    throw new ApiError("unauthorized", 401, null);
  }

  if (res.status === 204) {
    return undefined as T;
  }

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
    const { message } = parseApiErrorBody(parsed, `request_failed_${res.status}`);
    throw new ApiError(message, res.status, parsed);
  }

  return parsed as T;
}

export const apiClient = {
  get: <T = unknown>(path: string, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T = unknown>(
    path: string,
    body?: unknown,
    options: ApiRequestOptions = {},
  ) => apiFetch<T>(path, { ...options, method: "POST", body }),
  put: <T = unknown>(
    path: string,
    body?: unknown,
    options: ApiRequestOptions = {},
  ) => apiFetch<T>(path, { ...options, method: "PUT", body }),
  patch: <T = unknown>(
    path: string,
    body?: unknown,
    options: ApiRequestOptions = {},
  ) => apiFetch<T>(path, { ...options, method: "PATCH", body }),
  delete: <T = unknown>(path: string, options: ApiRequestOptions = {}) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
};
