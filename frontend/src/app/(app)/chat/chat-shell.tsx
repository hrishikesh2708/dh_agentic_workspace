"use client";

import { ChatProviders } from "@/app/(app)/chat/providers";
import { ChatErrorBoundary } from "@/components/chat/chat-error-boundary";
import {
  CopilotChatLayout,
  CopilotOfflineBanner,
} from "@/components/chat/copilot-chat-layout";
import { HeadlessChat } from "@/components/chat/headless-chat";
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

function ChatPreviewShell({ message }: { message?: string }) {
  return (
    <CopilotChatLayout
      inputDisabled
      inputPlaceholder="Connect backend session to start chatting"
      banner={
        message ? (
          <CopilotOfflineBanner message={message} />
        ) : undefined
      }
    />
  );
}

/**
 * Bootstraps a chat session token, then mounts the CopilotKit-backed
 * HeadlessChat. Falls back to the visible UI shell when the session or
 * agent runtime is not ready yet.
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
          return;
        }
        const message =
          err instanceof Error ? err.message : "session_create_failed";
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
      <CopilotChatLayout
        inputDisabled
        banner={
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            Preparing chat session…
          </div>
        }
      />
    );
  }

  if (error || !stored) {
    return (
      <ChatPreviewShell
        message={`Session could not be created (${error ?? "unknown error"}). Check that the backend is running — the copilot UI is still available for layout work.`}
      />
    );
  }

  return (
    <ChatErrorBoundary>
      <ChatProviders sessionToken={stored.access_token}>
        <HeadlessChat />
      </ChatProviders>
    </ChatErrorBoundary>
  );
}
