export interface ApiFieldError {
  field: string;
  message: string;
}

export interface ParsedApiError {
  message: string;
  fieldErrors: ApiFieldError[];
}

const FRIENDLY_MESSAGES: Record<string, string> = {
  login_failed: "Sign in failed. Please check your credentials and try again.",
  register_failed: "Registration failed. Please try again.",
  email_and_password_required: "Email and password are required.", // pragma: allowlist secret
  invalid_request_body: "Invalid request. Please try again.",
  invalid_backend_response: "Something went wrong. Please try again later.",
  request_failed: "Something went wrong. Please try again.",
};

function formatValidationMessage(message: string): string {
  return message.replace(/^Value error,\s*/i, "");
}

/** Map raw API field errors to short, user-facing copy. */
export function humanizeFieldError(field: string, message: string): string {
  const normalized = formatValidationMessage(message);

  if (field === "email" && normalized.includes("valid email")) {
    return "Enter a valid email address (e.g. you@example.com)";
  }
  if (field === "email" && normalized.includes("@-sign")) {
    return "Enter a valid email address (e.g. you@example.com)";
  }
  if (field === "username" && normalized.includes("50")) {
    return "Display name must be 50 characters or fewer";
  }

  return normalized;
}

function formatFieldLabel(field: string): string {
  if (!field) return "";
  return field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, " ");
}

function summarizeFieldErrors(fieldErrors: ApiFieldError[]): string {
  return fieldErrors
    .map(({ field, message }) =>
      field ? `${formatFieldLabel(field)}: ${message}` : message,
    )
    .join(". ");
}

function parseFieldErrorsFromArray(items: unknown[]): ApiFieldError[] {
  const fieldErrors: ApiFieldError[] = [];

  for (const item of items) {
    if (!item || typeof item !== "object") continue;

    if ("message" in item && typeof (item as { message: unknown }).message === "string") {
      const err = item as { field?: unknown; message: string };
      const field = typeof err.field === "string" ? err.field : "";
      fieldErrors.push({
        field,
        message: humanizeFieldError(field, err.message),
      });
      continue;
    }

    if ("msg" in item && typeof (item as { msg: unknown }).msg === "string") {
      const err = item as { loc?: unknown; msg: string };
      const locParts = Array.isArray(err.loc)
        ? err.loc.filter((part) => part !== "body").map(String)
        : [];
      const field = locParts.join(" -> ");
      fieldErrors.push({
        field,
        message: humanizeFieldError(field, err.msg),
      });
    }
  }

  return fieldErrors;
}

/** Turn FastAPI / proxy error JSON into a user-visible message and optional field errors. */
export function parseApiErrorBody(
  body: unknown,
  fallback = "request_failed",
): ParsedApiError {
  if (!body || typeof body !== "object") {
    return {
      message: FRIENDLY_MESSAGES[fallback] ?? fallback,
      fieldErrors: [],
    };
  }

  const record = body as Record<string, unknown>;
  let fieldErrors: ApiFieldError[] = [];

  if (Array.isArray(record.errors)) {
    fieldErrors = parseFieldErrorsFromArray(record.errors);
  } else if (Array.isArray(record.detail)) {
    fieldErrors = parseFieldErrorsFromArray(record.detail);
  }

  if (fieldErrors.length > 0) {
    return {
      message: summarizeFieldErrors(fieldErrors),
      fieldErrors,
    };
  }

  if (typeof record.detail === "string") {
    const detail = record.detail;
    if (detail === "Validation error" && fieldErrors.length === 0) {
      return {
        message: "Please check the highlighted fields and try again.",
        fieldErrors: [],
      };
    }
    return {
      message: FRIENDLY_MESSAGES[detail] ?? detail,
      fieldErrors: [],
    };
  }

  return {
    message: FRIENDLY_MESSAGES[fallback] ?? fallback,
    fieldErrors: [],
  };
}

export function fieldErrorsByName(
  fieldErrors: ApiFieldError[],
): Record<string, string> {
  const map: Record<string, string> = {};
  for (const { field, message } of fieldErrors) {
    const key = field.split(" -> ").pop() ?? field;
    if (key) {
      map[key] = humanizeFieldError(key, message);
    }
  }
  return map;
}
