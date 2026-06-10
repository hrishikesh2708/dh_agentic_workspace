"use client";

import { ChatProviders } from "@/app/(app)/chat/providers";
import { HeadlessChat } from "@/components/chat/headless-chat";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { apiClient, ApiError } from "@/lib/api-client";
import { useEffect, useState } from "react";

/** Shape returned by ``POST /api/v1/auth/session`` (see backend ``app/schemas/auth.py``). */
interface SessionCreateResponse {
  session_id: string;
  name: string;
  token: {
    access_token: string;
    token_type: string;
    expires_at: number;
  };
}

const CHAT_SESSION_STORAGE_KEY = "dh_chat_session";

interface StoredChatSession {
  session_id: string;
  access_token: string;
  expires_at: number;
}

function loadStoredSession(): StoredChatSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(CHAT_SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredChatSession;
    // Drop if the token has already expired.
    if (parsed.expires_at && parsed.expires_at * 1000 < Date.now()) {
      window.sessionStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function storeSession(session: StoredChatSession) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(
    CHAT_SESSION_STORAGE_KEY,
    JSON.stringify(session),
  );
}

/**
 * Bootstraps a chat session token, then mounts the CopilotKit-backed
 * HeadlessChat. Each navigation to ``/chat`` either reuses a still-valid
 * session from sessionStorage or creates a new one via the framework's
 * ``POST /api/v1/auth/session`` endpoint.
 */
export function ChatShell() {
  const [stored, setStored] = useState<StoredChatSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const existing = loadStoredSession();
        if (existing) {
          if (!cancelled) {
            setStored(existing);
            setLoading(false);
          }
          return;
        }

        // No usable cached session — create a new one.
        const created = await apiClient.post<SessionCreateResponse>(
          "/auth/session",
        );
        const next: StoredChatSession = {
          session_id: created.session_id,
          access_token: created.token.access_token,
          expires_at: created.token.expires_at,
        };
        storeSession(next);
        if (!cancelled) {
          setStored(next);
          setLoading(false);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          // api-client already redirected to /login; nothing more to do.
          return;
        }
        const message = err instanceof Error ? err.message : "session_create_failed";
        setError(message);
        setLoading(false);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
          <Spinner size="sm" />
          Preparing chat session…
        </div>
      </div>
    );
  }

  if (error || !stored) {
    return (
      <div className="flex h-full items-center justify-center">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Could not start chat</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-[var(--muted-foreground)]">
            <p>
              {error
                ? `Error: ${error}`
                : "Unknown error preparing the chat session."}
            </p>
            <p>
              Check that the backend at{" "}
              <code>{process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}</code>{" "}
              is running and reachable.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <ChatProviders sessionToken={stored.access_token}>
      <HeadlessChat />
    </ChatProviders>
  );
}
