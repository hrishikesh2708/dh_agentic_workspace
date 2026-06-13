"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiClient, ApiError } from "@/lib/api-client";
import { fieldErrorsByName, parseApiErrorBody } from "@/lib/api-errors";
import {
  REGISTER_FIELD_HINTS,
  setRegisterInputValidity,
  validateRegisterFields,
} from "@/lib/register-validation";
import type { UserResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/hooks/use-auth";

type RegisterField = keyof typeof REGISTER_FIELD_HINTS;

function clearFieldError(
  field: RegisterField,
  setFieldErrors: React.Dispatch<
    React.SetStateAction<Record<string, string>>
  >,
) {
  setFieldErrors((prev) => {
    if (!prev[field]) return prev;
    const next = { ...prev };
    delete next[field];
    return next;
  });
}

export function RegisterForm() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  function syncRegisterValidity(form: HTMLFormElement) {
    form.querySelectorAll<HTMLInputElement>("input[data-field]").forEach((input) => {
      const field = input.dataset.field as RegisterField;
      setRegisterInputValidity(input, field);
    });
  }

  function bindFieldHandlers(field: RegisterField) {
    return {
      title: REGISTER_FIELD_HINTS[field],
      onInvalid: (e: React.FormEvent<HTMLInputElement>) => {
        setRegisterInputValidity(e.currentTarget, field);
      },
      onInput: (e: React.FormEvent<HTMLInputElement>) => {
        e.currentTarget.setCustomValidity("");
        clearFieldError(field, setFieldErrors);
      },
      onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
        const errors = validateRegisterFields({ email, username, password });
        if (errors[field]) {
          setFieldErrors((prev) => ({ ...prev, [field]: errors[field] }));
          setRegisterInputValidity(e.currentTarget, field);
        }
      },
    };
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const form = e.currentTarget;
    const clientErrors = validateRegisterFields({ email, username, password });
    syncRegisterValidity(form);

    if (Object.keys(clientErrors).length > 0) {
      setFieldErrors(clientErrors);
      form.reportValidity();
      return;
    }

    setFieldErrors({});

    setSubmitting(true);
    try {
      await apiClient.post<UserResponse>("/auth/register", {
        email: email.trim(),
        password,
        username: username.trim() || undefined,
      });
      await login(email.trim(), password);
      router.push("/chat");
    } catch (err) {
      if (err instanceof ApiError) {
        const parsed = parseApiErrorBody(err.body, "register_failed");
        const nextFieldErrors = fieldErrorsByName(parsed.fieldErrors);
        setFieldErrors(nextFieldErrors);
        setError(
          Object.keys(nextFieldErrors).length > 0 ? null : parsed.message,
        );
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create an account</CardTitle>
        <CardDescription>
          Sign up to start mapping your data. Password needs upper, lower,
          number, and a special character.
        </CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit}>
        <CardContent className="space-y-4">
          {error ? (
            <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
              {error}
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              data-field="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? "email-error" : undefined}
              onChange={(e) => setEmail(e.target.value)}
              {...bindFieldHandlers("email")}
            />
            {fieldErrors.email ? (
              <p id="email-error" className="text-sm text-[var(--destructive)]">
                {fieldErrors.email}
              </p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="username">Display name (optional)</Label>
            <Input
              id="username"
              data-field="username"
              type="text"
              autoComplete="nickname"
              maxLength={50}
              value={username}
              aria-invalid={Boolean(fieldErrors.username)}
              aria-describedby={
                fieldErrors.username ? "username-error" : undefined
              }
              onChange={(e) => setUsername(e.target.value)}
              {...bindFieldHandlers("username")}
            />
            {fieldErrors.username ? (
              <p id="username-error" className="text-sm text-[var(--destructive)]">
                {fieldErrors.username}
              </p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              data-field="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={64}
              value={password}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={
                fieldErrors.password ? "password-error" : undefined
              }
              onChange={(e) => setPassword(e.target.value)}
              {...bindFieldHandlers("password")}
            />
            {fieldErrors.password ? (
              <p id="password-error" className="text-sm text-[var(--destructive)]">
                {fieldErrors.password}
              </p>
            ) : null}
          </div>
        </CardContent>
        <CardFooter className="flex flex-col items-stretch gap-3">
          <Button type="submit" disabled={submitting}>
            {submitting ? <Spinner size="sm" /> : null}
            {submitting ? "Creating..." : "Create account"}
          </Button>
          <p className="text-center text-sm text-[var(--muted-foreground)]">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-[var(--foreground)] underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
